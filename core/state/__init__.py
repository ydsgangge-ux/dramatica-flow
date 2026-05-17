"""
状态管理器
文件驱动的单一真相源 + 快照回滚
修复：read_truth/write_truth 同时接受 TruthFileKey 和字符串
新增：update_current_state_md（章后完整更新 current_state.md）
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path

from ..types.state import (
    BookConfig, WorldState, TruthFileKey, TRUTH_FILE_NAMES,
    StateSnapshot, RelationshipRecord, KnownInfoRecord,
    EmotionalSnapshot, Hook, HookStatus, CausalLink, AffectedDecision,
)
from ..types.narrative import NarrativeThread, TimelineEvent


# ── 真相文件初始模板 ──────────────────────────────────────────────────────────

_TRUTH_TEMPLATES: dict[TruthFileKey, str] = {
    TruthFileKey.CURRENT_STATE: """\
# 当前世界状态

## 角色位置
（尚未更新）

## 角色情感快照
（尚未更新）

## 关系网络
（尚未更新）
""",
    TruthFileKey.STORY_BIBLE: """\
# 世界观圣经

> 此文件由人工维护，系统不会覆盖已有内容。

## 地点

## 势力

## 世界规则

## 数值系统（如有）
""",
    TruthFileKey.CHAPTER_SUMMARIES: "# 章节摘要\n\n",
    TruthFileKey.PENDING_HOOKS: """\
# 未闭合伏笔

| ID | 类型 | 描述 | 植入章 | 预计回收 | 状态 |
|---|---|---|---|---|---|
""",
    TruthFileKey.EMOTIONAL_ARCS: "# 情感弧线\n\n",
    TruthFileKey.CHARACTER_MATRIX: """\
# 角色交互矩阵

## 相遇记录

## 信息边界（谁知道了什么）
""",
    TruthFileKey.CAUSAL_CHAIN: """\
# 因果链

> 记录每个关键事件的因果关系，确保故事是有机叙事而非事件堆砌。
> 格式：因为 [cause]，发生了 [event]，导致 [consequence]。

""",
    TruthFileKey.THREAD_STATUS: """\
# 叙事线程状态

> 追踪多线叙事中各线程的进度、掉线预警和汇合规划。

## 线程列表

| 线程 | 视角角色 | 类型 | 权重 | 上次活跃 | 期待感 | 状态 |
|---|---|---|---|---|---|---|

## 支线掉线预警

（暂无预警）

## 近期时间轴

| 章节 | 时间 | 角色 | 地点 | 动作 | 线程 |
|---|---|---|---|---|---|

""",
}


def _key(k: TruthFileKey | str) -> TruthFileKey:
    """统一接受 TruthFileKey 或字符串"""
    if isinstance(k, TruthFileKey):
        return k
    return TruthFileKey(k)


class StateManager:
    """
    目录结构：
        books/{book_id}/
            state/
                config.json
                world_state.json
                current_state.md
                story_bible.md
                chapter_summaries.md
                pending_hooks.md
                emotional_arcs.md
                character_matrix.md
                causal_chain.md
                setup_state.json       ← 角色/世界/事件配置
                outline.json           ← 故事大纲
                chapter_outlines.json  ← 全书章纲
            snapshots/
                ch0001.json
                ...
            chapters/
                ch0001_draft.md
                ch0001_final.md
                ...
    """

    def __init__(self, project_root: str | Path, book_id: str):
        self.book_id      = book_id
        self.book_dir     = Path(project_root) / "books" / book_id
        self.state_dir    = self.book_dir / "state"
        self.snapshot_dir = self.book_dir / "snapshots"
        self.chapter_dir  = self.book_dir / "chapters"

    # ── 初始化 ──────────────────────────────────────────────────────────────────

    def init(self, config: BookConfig) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.chapter_dir.mkdir(parents=True, exist_ok=True)

        # 不重复初始化
        config_path = self.state_dir / "config.json"
        if not config_path.exists():
            self._write_json("config.json", dataclasses.asdict(config))

        ws_path = self.state_dir / "world_state.json"
        if not ws_path.exists():
            ws = WorldState(book_id=self.book_id)
            self._write_json("world_state.json", dataclasses.asdict(ws))

        for key, template in _TRUTH_TEMPLATES.items():
            path = self.state_dir / TRUTH_FILE_NAMES[key]
            if not path.exists():
                path.write_text(template, encoding="utf-8")

    # ── 真相文件读写（同时接受 TruthFileKey 和字符串） ─────────────────────────

    def read_truth(self, key: TruthFileKey | str) -> str:
        path = self.state_dir / TRUTH_FILE_NAMES[_key(key)]
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def write_truth(self, key: TruthFileKey | str, content: str) -> None:
        path = self.state_dir / TRUTH_FILE_NAMES[_key(key)]
        path.write_text(content, encoding="utf-8")

    def append_truth(self, key: TruthFileKey | str, content: str) -> None:
        existing = self.read_truth(key)
        self.write_truth(key, existing + content)

    def read_truth_bundle(self, keys: list[TruthFileKey | str]) -> str:
        """读取多个真相文件拼接，供 Agent 上下文使用"""
        parts = []
        for k in keys:
            content = self.read_truth(k)
            if content.strip():
                filename = TRUTH_FILE_NAMES[_key(k)]
                parts.append(f"## [{filename}]\n\n{content}")
        return "\n\n---\n\n".join(parts)

    # ── 世界状态读写 ─────────────────────────────────────────────────────────────

    def read_world_state(self) -> WorldState:
        data = self._read_json("world_state.json")
        ws = WorldState(book_id=data.get("book_id", self.book_id))
        ws.current_chapter       = data.get("current_chapter", 0)
        ws.character_positions   = data.get("character_positions", {})

        # 重建 relationships
        for r in data.get("relationships", []):
            from ..types.state import RelationshipType, RelationshipDelta
            deltas = [RelationshipDelta(**d) for d in r.get("history", [])]
            rel = RelationshipRecord(
                character_a=r["character_a"],
                character_b=r["character_b"],
                type=RelationshipType(r.get("type", "neutral")),
                strength=r.get("strength", 0),
                known_to=r.get("known_to", []),
                history=deltas,
            )
            ws.relationships.append(rel)

        # 重建 known_info
        for i in data.get("known_info", []):
            ws.known_info.append(KnownInfoRecord(**i))

        # 重建 emotional_snapshots
        for s in data.get("emotional_snapshots", []):
            ws.emotional_snapshots.append(EmotionalSnapshot(**s))

        # 重建 pending_hooks
        for h in data.get("pending_hooks", []):
            from ..types.state import HookType
            hook = Hook(
                id=h["id"],
                type=HookType(h.get("type", "foreshadow")),
                description=h.get("description", ""),
                planted_in_chapter=h.get("planted_in_chapter", 0),
                expected_resolution_range=tuple(h.get("expected_resolution_range", [0, 0])),
                status=HookStatus(h.get("status", "open")),
                resolved_in_chapter=h.get("resolved_in_chapter"),
            )
            ws.pending_hooks.append(hook)

        # 重建 causal_chain
        for c in data.get("causal_chain", []):
            from ..types.state import AffectedDecision
            decisions = [AffectedDecision(**d) for d in c.get("affected_decisions", [])]
            cl = CausalLink(
                id=c["id"],
                chapter=c["chapter"],
                cause=c["cause"],
                event=c["event"],
                consequence=c["consequence"],
                affected_decisions=decisions,
                triggered_events=c.get("triggered_events", []),
                thread_id=c.get("thread_id", "thread_main"),
                source_thread_id=c.get("source_thread_id", ""),
            )
            ws.causal_chain.append(cl)

        # 重建 threads
        for t in data.get("threads", []):
            thread = NarrativeThread(
                id=t["id"],
                name=t.get("name", ""),
                type=t.get("type", "main"),
                pov_character_id=t.get("pov_character_id", ""),
                character_ids=t.get("character_ids", []),
                goal=t.get("goal", ""),
                growth_arc=t.get("growth_arc", ""),
                start_chapter=t.get("start_chapter", 1),
                last_active_chapter=t.get("last_active_chapter", 0),
                weight=t.get("weight", 1.0),
                status=t.get("status", "active"),
                merge_target_thread=t.get("merge_target_thread"),
                hook_score=t.get("hook_score", 80),
                merge_chapter=t.get("merge_chapter"),
                end_hook=t.get("end_hook", ""),
            )
            ws.threads.append(thread)

        # 重建 timeline
        for te in data.get("timeline", []):
            event = TimelineEvent(
                id=te["id"],
                chapter=te["chapter"],
                physical_time=te.get("physical_time", ""),
                time_order=te.get("time_order", 0.0),
                character_id=te.get("character_id", ""),
                location_id=te.get("location_id", ""),
                action=te.get("action", ""),
                thread_id=te.get("thread_id", ""),
                affected_threads=te.get("affected_threads", []),
                affected_characters=te.get("affected_characters", []),
            )
            ws.timeline.append(event)

        return ws

    def write_world_state(self, state: WorldState) -> None:
        self._write_json("world_state.json", dataclasses.asdict(state))

    # ── 原子状态更新 ─────────────────────────────────────────────────────────────

    def move_character(self, character_id: str, location_id: str) -> None:
        state = self.read_world_state()
        state.character_positions[character_id] = location_id
        self.write_world_state(state)

    def update_relationship(
        self,
        char_a: str,
        char_b: str,
        delta: int,
        chapter: int,
        reason: str,
    ) -> None:
        from ..types.state import RelationshipType, RelationshipDelta
        state = self.read_world_state()
        key = ":".join(sorted([char_a, char_b]))
        rel = next(
            (r for r in state.relationships if r.key == key),
            None,
        )
        if rel is None:
            rel = RelationshipRecord(
                character_a=char_a,
                character_b=char_b,
                type=RelationshipType.NEUTRAL,
                strength=0,
            )
            state.relationships.append(rel)
        rel.strength = max(-100, min(100, rel.strength + delta))
        rel.history.append(RelationshipDelta(chapter=chapter, delta=delta, reason=reason))
        # 自动更新关系类型
        if rel.strength >= 50:
            rel.type = RelationshipType.ALLY
        elif rel.strength <= -50:
            rel.type = RelationshipType.ENEMY
        else:
            rel.type = RelationshipType.NEUTRAL
        self.write_world_state(state)

    def learn_info(
        self,
        character_id: str,
        info_key: str,
        content: str,
        chapter: int,
        source: str = "witnessed",
    ) -> None:
        state = self.read_world_state()
        if not state.character_knows(character_id, info_key):
            state.known_info.append(KnownInfoRecord(
                character_id=character_id,
                info_key=info_key,
                content=content,
                learned_in_chapter=chapter,
                source=source,  # type: ignore
            ))
            self.write_world_state(state)

    def record_emotion(self, snapshot: EmotionalSnapshot) -> None:
        state = self.read_world_state()
        state.emotional_snapshots.append(snapshot)
        self.write_world_state(state)

    def open_hook(self, hook: Hook) -> None:
        state = self.read_world_state()
        # 避免重复
        if not any(h.id == hook.id for h in state.pending_hooks):
            state.pending_hooks.append(hook)
            self.write_world_state(state)
            row = (
                f"| {hook.id} | {hook.type.value} | {hook.description} "
                f"| {hook.planted_in_chapter} "
                f"| {hook.expected_resolution_range[0]}-{hook.expected_resolution_range[1]} "
                f"| {hook.status.value} |\n"
            )
            self.append_truth(TruthFileKey.PENDING_HOOKS, row)

    def resolve_hook(self, hook_id: str, chapter: int) -> None:
        state = self.read_world_state()
        hook = next((h for h in state.pending_hooks if h.id == hook_id), None)
        if hook:
            hook.status = HookStatus.RESOLVED
            hook.resolved_in_chapter = chapter
            self.write_world_state(state)

    def add_causal_link(self, link: CausalLink) -> None:
        state = self.read_world_state()
        state.causal_chain.append(link)
        self.write_world_state(state)
        decisions = "\n".join(
            f"  - **{d.character_id}** 决定：{d.decision}"
            for d in link.affected_decisions
        )
        entry = (
            f"\n### Ch.{link.chapter} — {link.event}\n"
            f"- **因**：{link.cause}\n"
            f"- **果**：{link.consequence}\n"
            + (decisions + "\n" if decisions else "")
        )
        self.append_truth(TruthFileKey.CAUSAL_CHAIN, entry)

    # ── 叙事线程管理 ─────────────────────────────────────────────────────────────

    def create_thread(self, thread: NarrativeThread) -> None:
        state = self.read_world_state()
        if not any(t.id == thread.id for t in state.threads):
            state.threads.append(thread)
            self.write_world_state(state)

    def update_thread(self, thread_id: str, **kwargs) -> None:
        state = self.read_world_state()
        for t in state.threads:
            if t.id == thread_id:
                for k, v in kwargs.items():
                    if hasattr(t, k):
                        setattr(t, k, v)
                break
        self.write_world_state(state)

    def delete_thread(self, thread_id: str) -> None:
        """删除线程及其关联的时间轴事件"""
        state = self.read_world_state()
        state.threads = [t for t in state.threads if t.id != thread_id]
        state.timeline = [e for e in state.timeline if e.thread_id != thread_id]
        self.write_world_state(state)

    def add_timeline_event(self, event: TimelineEvent) -> None:
        state = self.read_world_state()
        state.timeline.append(event)
        # 更新线程的 last_active_chapter
        if event.thread_id:
            for t in state.threads:
                if t.id == event.thread_id and event.chapter > t.last_active_chapter:
                    t.last_active_chapter = event.chapter
        self.write_world_state(state)

    def get_thread_timeline(self, thread_id: str) -> list[TimelineEvent]:
        state = self.read_world_state()
        return [e for e in state.timeline if e.thread_id == thread_id]

    def get_character_timeline(self, character_id: str) -> list[TimelineEvent]:
        state = self.read_world_state()
        return [e for e in state.timeline if e.character_id == character_id]

    def get_cross_thread_causal_links(self) -> list[CausalLink]:
        """获取所有跨线程因果链（source_thread_id != thread_id）"""
        state = self.read_world_state()
        return [cl for cl in state.causal_chain
                if cl.source_thread_id and cl.source_thread_id != cl.thread_id]

    def update_thread_status_md(self) -> None:
        """更新 thread_status.md（章后调用）"""
        state = self.read_world_state()
        current_ch = state.current_chapter

        lines = [f"# 叙事线程状态（更新至第 {current_ch} 章）\n\n"]

        # 线程列表
        lines.append("## 线程列表\n\n")
        lines.append("| 线程 | 视角角色 | 类型 | 权重 | 上次活跃 | 期待感 | 状态 |\n")
        lines.append("|---|---|---|---|---|---|---|\n")
        for t in state.threads:
            status_icon = {"active": "活跃", "dormant": "休眠", "resolved": "已结束", "merged": "已合并"}.get(t.status, t.status)
            type_val = t.type.value if hasattr(t.type, 'value') else t.type
            lines.append(
                f"| {t.name}（{t.id}）| {t.pov_character_id} | {type_val} "
                f"| {t.weight:.1f} | Ch.{t.last_active_chapter} "
                f"| {t.hook_score}/100 | {status_icon} |\n"
            )

        # 支线掉线预警
        dormant = state.dormant_threads(current_ch, threshold=5)
        lines.append(f"\n## 支线掉线预警\n\n")
        if dormant:
            for t in dormant:
                gap = current_ch - t.last_active_chapter
                lines.append(f"- **{t.name}**（{t.id}）：已 {gap} 章未活跃（视角：{t.pov_character_id}）\n")
        else:
            lines.append("（暂无预警）\n")

        # 近期时间轴（最近 20 条）
        recent_timeline = state.timeline[-20:]
        if recent_timeline:
            lines.append(f"\n## 近期时间轴（最近 {len(recent_timeline)} 条）\n\n")
            lines.append("| 章节 | 时间 | 角色 | 地点 | 动作 | 线程 |\n")
            lines.append("|---|---|---|---|---|---|\n")
            for te in recent_timeline:
                lines.append(
                    f"| Ch.{te.chapter} | {te.physical_time} | {te.character_id} "
                    f"| {te.location_id} | {te.action[:30]}... | {te.thread_id} |\n"
                )

        self.write_truth(TruthFileKey.THREAD_STATUS, "".join(lines))

    # ── current_state.md 完整更新（章后调用） ────────────────────────────────────

    def update_current_state_md(self) -> None:
        """
        根据当前 world_state.json 重新生成 current_state.md。
        每章结束后调用，确保下一章的 Agent 看到准确的世界状态。
        """
        ws = self.read_world_state()

        lines = [f"# 当前世界状态（更新至第 {ws.current_chapter} 章）\n\n"]

        # 角色位置
        lines.append("## 角色位置\n")
        if ws.character_positions:
            for char_id, loc_id in ws.character_positions.items():
                lines.append(f"- {char_id}：{loc_id}\n")
        else:
            lines.append("（无记录）\n")

        # 最新情感状态（每个角色只取最新一条）
        lines.append("\n## 角色情感状态\n")
        latest_emotions: dict[str, EmotionalSnapshot] = {}
        for snap in ws.emotional_snapshots:
            if snap.character_id not in latest_emotions or \
               snap.chapter > latest_emotions[snap.character_id].chapter:
                latest_emotions[snap.character_id] = snap
        if latest_emotions:
            for char_id, snap in latest_emotions.items():
                lines.append(
                    f"- {char_id}：{snap.emotion}（强度 {snap.intensity}/10）"
                    f"  — 触发：{snap.trigger}（Ch.{snap.chapter}）\n"
                )
        else:
            lines.append("（无记录）\n")

        # 关系网络
        lines.append("\n## 关系网络\n")
        if ws.relationships:
            for rel in ws.relationships:
                lines.append(
                    f"- {rel.character_a} ↔ {rel.character_b}："
                    f"{rel.type.value}，强度 {rel.strength:+d}\n"
                )
        else:
            lines.append("（无记录）\n")

        # 未闭合伏笔摘要
        open_hooks = ws.open_hooks()
        lines.append(f"\n## 未闭合伏笔（{len(open_hooks)} 条）\n")
        for h in open_hooks:
            overdue = ws.current_chapter > h.expected_resolution_range[1]
            flag = "⚠️ 逾期！" if overdue else ""
            lines.append(f"- [{h.id}] {h.description}  {flag}\n")

        # 最新因果链（最近 5 条）
        recent_causal = ws.causal_chain[-5:]
        if recent_causal:
            lines.append(f"\n## 近期因果链（最近 {len(recent_causal)} 条）\n")
            for cl in recent_causal:
                lines.append(f"- Ch.{cl.chapter}：{cl.event}（因：{cl.cause}）\n")

        self.write_truth(TruthFileKey.CURRENT_STATE, "".join(lines))

    # ── 章节正文存储 ─────────────────────────────────────────────────────────────

    def save_draft(self, chapter: int, content: str) -> Path:
        path = self.chapter_dir / f"ch{chapter:04d}_draft.md"
        path.write_text(content, encoding="utf-8")
        return path

    def save_final(self, chapter: int, content: str) -> Path:
        path = self.chapter_dir / f"ch{chapter:04d}_final.md"
        path.write_text(content, encoding="utf-8")
        return path

    def read_draft(self, chapter: int) -> str:
        path = self.chapter_dir / f"ch{chapter:04d}_draft.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def read_final(self, chapter: int) -> str:
        path = self.chapter_dir / f"ch{chapter:04d}_final.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    # ── 快照 ─────────────────────────────────────────────────────────────────────

    def create_snapshot(self, chapter: int) -> None:
        ws = self.read_world_state()
        truth_contents = {
            key.value: self.read_truth(key)
            for key in TruthFileKey
        }
        snapshot = {
            "book_id": self.book_id,
            "chapter": chapter,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "world_state": dataclasses.asdict(ws),
            "truth_files": truth_contents,
        }
        path = self.snapshot_dir / f"ch{chapter:04d}.json"
        path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def restore_snapshot(self, chapter: int) -> None:
        path = self.snapshot_dir / f"ch{chapter:04d}.json"
        if not path.exists():
            raise FileNotFoundError(f"快照不存在：第 {chapter} 章")
        data = json.loads(path.read_text(encoding="utf-8"))
        self._write_json("world_state.json", data["world_state"])
        for key_str, content in data["truth_files"].items():
            self.write_truth(TruthFileKey(key_str), content)

    # ── 配置读写 ─────────────────────────────────────────────────────────────────

    def read_config(self) -> dict:
        return self._read_json("config.json")

    def write_config(self, config: BookConfig) -> None:
        self._write_json("config.json", dataclasses.asdict(config))

    # ── 内部工具 ─────────────────────────────────────────────────────────────────

    def _read_json(self, filename: str) -> dict:
        path = self.state_dir / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, filename: str, data: dict) -> None:
        path = self.state_dir / filename
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
