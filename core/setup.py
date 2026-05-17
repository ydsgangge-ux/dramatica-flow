"""
输入系统：从 JSON 文件加载角色、世界、事件
修复：worldview 字段非法值容错，缺失字段给默认值
"""
from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

from .types.narrative import (
    Character, CharacterNeed, CharacterWorldview, Obstacle, ObstacleType,
    Location, Faction, WorldRule, StoryEvent, DramaticFunction,
)
from .types.state import ProjectState, BookConfig, WorldState, TruthFileKey
from .state import StateManager


# ── JSON → Dataclass 转换（带容错） ──────────────────────────────────────────

def load_character(data: dict) -> Character:
    need = CharacterNeed(
        external=data.get("need", {}).get("external", "（未设置）"),
        internal=data.get("need", {}).get("internal", "（未设置）"),
    )

    # worldview 容错：非法值替换为默认值
    wv_raw = data.get("worldview", {})
    _power_map  = {"seeks": "seeks", "rejects": "rejects", "accepts": "accepts"}
    _trust_map  = {"trusting": "trusting", "suspicious": "suspicious", "selective": "selective"}
    _coping_map = {"fight": "fight", "flee": "flee", "freeze": "freeze", "fawn": "fawn"}
    worldview = CharacterWorldview(
        power  = _power_map.get(wv_raw.get("power", ""), "seeks"),
        trust  = _trust_map.get(wv_raw.get("trust", ""), "suspicious"),
        coping = _coping_map.get(wv_raw.get("coping", ""), "fight"),
    )

    # obstacles 容错
    obstacles = []
    for o in data.get("obstacles", []):
        try:
            obs_type = ObstacleType(o.get("type", "antagonist"))
        except ValueError:
            obs_type = ObstacleType.ANTAGONIST
        obstacles.append(Obstacle(
            type=obs_type,
            description=o.get("description", ""),
            mechanism=o.get("mechanism", ""),
        ))

    # arc 容错
    _arc_valid = {"positive", "negative", "flat", "corrupt"}
    arc = data.get("arc", "positive")
    if arc not in _arc_valid:
        arc = "positive"

    return Character(
        id=data.get("id", f"char_{id(data)}"),
        name=data.get("name", "未命名角色"),
        need=need,
        obstacles=obstacles,
        worldview=worldview,
        arc=arc,  # type: ignore
        profile=data.get("profile", ""),
        behavior_lock=data.get("behavior_lock", []),
    )


def load_location(data: dict) -> Location:
    return Location(
        id=data.get("id", ""),
        name=data.get("name", "未命名地点"),
        description=data.get("description", ""),
        connections=data.get("connections", []),
        faction=data.get("faction"),
        dramatic_potential=data.get("dramatic_potential"),
    )


def load_faction(data: dict) -> Faction:
    return Faction(
        id=data.get("id", ""),
        name=data.get("name", ""),
        description=data.get("description", ""),
        relations=data.get("relations", {}),
        core_interest=data.get("core_interest", ""),
    )


def load_world_rule(data: dict) -> WorldRule:
    return WorldRule(
        name=data.get("name", ""),
        description=data.get("description", ""),
        consequence=data.get("consequence", ""),
        is_hard=data.get("is_hard", False),
    )


def load_event(data: dict) -> StoryEvent:
    func_raw = data.get("suggested_function")
    try:
        func = DramaticFunction(func_raw) if func_raw else None
    except ValueError:
        func = None
    return StoryEvent(
        id=data.get("id", ""),
        name=data.get("name", ""),
        description=data.get("description", ""),
        preconditions=data.get("preconditions", []),
        effects=data.get("effects", []),
        triggers=data.get("triggers", []),
        suggested_act=data.get("suggested_act"),
        suggested_function=func,
    )


# ── SetupLoader ───────────────────────────────────────────────────────────────

class SetupLoader:
    def __init__(self, project_root: str | Path, book_id: str):
        self.sm           = StateManager(project_root, book_id)
        self.setup_dir    = self.sm.book_dir / "setup"
        self.templates_dir = Path(__file__).parent.parent / "templates"

    # ── 模板初始化 ────────────────────────────────────────────────────────────

    def init_templates(self) -> None:
        self.setup_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for tmpl in self.templates_dir.glob("*.json"):
            dest = self.setup_dir / tmpl.name
            if not dest.exists():
                shutil.copy(tmpl, dest)
                print(f"  [OK] 复制：{tmpl.name}")
                copied += 1
            else:
                print(f"  - 已存在：{tmpl.name}")
        print(f"\n{'复制了 ' + str(copied) + ' 个文件' if copied else '模板已存在'}。")
        print(f"请编辑：{self.setup_dir}")
        print("完成后运行：df setup load <book_id>")

    # ── 加载全部配置 ──────────────────────────────────────────────────────────

    def load_all(self) -> ProjectState:
        print("加载配置...")
        characters = self._load_characters()
        locations, factions, world_rules = self._load_world()
        seed_events, seed_event_id = self._load_events()

        config_data = self.sm.read_config()
        config = BookConfig(
            id=config_data["id"],
            title=config_data["title"],
            genre=config_data["genre"],
            target_words_per_chapter=config_data["target_words_per_chapter"],
            target_chapters=config_data["target_chapters"],
            protagonist_id=config_data.get("protagonist_id", ""),
            custom_forbidden_words=config_data.get("custom_forbidden_words", []),
            style_guide=config_data.get("style_guide", ""),
        )

        # 自动设置主角
        if not config.protagonist_id and characters:
            config.protagonist_id = next(iter(characters.keys()))
            self.sm.write_config(config)
            print(f"  -> 自动设置主角：{config.protagonist_id}")

        # 初始化角色位置
        world_state = WorldState(book_id=config.id)
        first_loc = next(iter(locations.keys()), "")
        for char_id in characters:
            world_state.character_positions[char_id] = first_loc
        self.sm.write_world_state(world_state)

        # 生成 story_bible.md
        self._generate_story_bible(characters, locations, factions, world_rules, seed_events)

        # 保存结构化配置
        self._save_setup_state(characters, locations, factions, world_rules, seed_events, seed_event_id)

        return ProjectState(
            config=config,
            characters=characters,
            locations=locations,
            factions=factions,
            world_rules=world_rules,
            seed_events=seed_events,
            world_state=world_state,
        )

    # ── 各文件加载 ────────────────────────────────────────────────────────────

    def _load_characters(self) -> dict[str, Character]:
        path = self.setup_dir / "characters.json"
        if not path.exists():
            raise FileNotFoundError(
                f"找不到角色文件：{path}\n请先运行：df setup init-templates <book_id>"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        chars = {}
        for c in data.get("characters", []):
            char = load_character(c)
            chars[char.id] = char
        print(f"  [OK] 角色：{len(chars)} 个 — {'、'.join(c.name for c in chars.values())}")
        return chars

    def _load_world(self) -> tuple[dict[str, Location], dict[str, Faction], list[WorldRule]]:
        path = self.setup_dir / "world.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到世界文件：{path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        locations  = {d["id"]: load_location(d)  for d in data.get("locations", [])}
        factions   = {d["id"]: load_faction(d)   for d in data.get("factions", [])}
        world_rules = [load_world_rule(r) for r in data.get("world_rules", [])]
        print(f"  [OK] 地点 {len(locations)} / 势力 {len(factions)} / 规则 {len(world_rules)}")
        return locations, factions, world_rules

    def _load_events(self) -> tuple[list[StoryEvent], str]:
        path = self.setup_dir / "events.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到事件文件：{path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        events = [load_event(e) for e in data.get("events", [])]
        seed_id = data.get("seed_event", events[0].id if events else "")
        print(f"  [OK] 事件 {len(events)} 个，种子：{seed_id}")
        return events, seed_id

    # ── story_bible.md 自动生成 ───────────────────────────────────────────────

    def _generate_story_bible(
        self,
        characters: dict[str, Character],
        locations: dict[str, Location],
        factions: dict[str, Faction],
        world_rules: list[WorldRule],
        events: list[StoryEvent],
    ) -> None:
        existing = self.sm.read_truth(TruthFileKey.STORY_BIBLE)
        # 判断是否还是空模板
        is_template = (
            not existing.strip()
            or "尚未更新" in existing
            or existing.strip().endswith("## 数值系统（如有）")
        )
        if not is_template:
            print("  - story_bible.md 已有内容，不覆盖")
            return

        lines = ["# 世界观圣经\n\n> 由 df setup load 自动生成，可直接编辑，系统不会覆盖已有内容。\n\n"]

        lines.append("## 角色\n\n")
        for c in characters.values():
            lines.append(f"### {c.name}（{c.id}）\n")
            lines.append(f"- **外部目标**：{c.need.external}\n")
            lines.append(f"- **内在渴望**：{c.need.internal}\n")
            lines.append(f"- **角色弧线**：{c.arc}\n")
            lines.append(f"- **简介**：{c.profile}\n")
            lines.append(f"- **性格锁定**：{'、'.join(c.behavior_lock) if c.behavior_lock else '无'}\n")
            for obs in c.obstacles:
                lines.append(f"- **障碍（{obs.type.value}）**：{obs.description}（{obs.mechanism}）\n")
            lines.append("\n")

        lines.append("## 地点\n\n")
        for loc in locations.values():
            conn = "、".join(loc.connections) if loc.connections else "无"
            lines.append(f"### {loc.name}（{loc.id}）\n")
            lines.append(f"{loc.description}\n")
            if loc.dramatic_potential:
                lines.append(f"- **戏剧潜力**：{loc.dramatic_potential}\n")
            lines.append(f"- **连接地点**：{conn}\n\n")

        lines.append("## 势力\n\n")
        for fac in factions.values():
            lines.append(f"### {fac.name}（{fac.id}）\n")
            lines.append(f"{fac.description}\n")
            lines.append(f"- **核心利益**：{fac.core_interest}\n\n")

        lines.append("## 世界规则\n\n")
        for rule in world_rules:
            hard = "【硬规则，不可违反】" if rule.is_hard else "【软规则】"
            lines.append(f"### {rule.name} {hard}\n")
            lines.append(f"{rule.description}\n")
            lines.append(f"- **违反后果**：{rule.consequence}\n\n")

        lines.append("## 事件时间线\n\n")
        for evt in events:
            lines.append(f"### {evt.name}（{evt.id}）\n")
            lines.append(f"{evt.description}\n")
            if evt.effects:
                lines.append(f"- **效果**：{'、'.join(evt.effects)}\n")
            if evt.triggers:
                lines.append(f"- **触发**：{'>'.join(evt.triggers)}\n")
            lines.append("\n")

        self.sm.write_truth(TruthFileKey.STORY_BIBLE, "".join(lines))
        print("  [OK] story_bible.md 已生成")

    # ── 保存 + 恢复 setup_state ───────────────────────────────────────────────

    def _save_setup_state(
        self,
        characters: dict,
        locations: dict,
        factions: dict,
        world_rules: list,
        events: list,
        seed_event_id: str,
    ) -> None:
        def _to_dict(obj):
            if dataclasses.is_dataclass(obj):
                return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, list):
                return [_to_dict(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _to_dict(v) for k, v in obj.items()}
            if hasattr(obj, "value"):  # Enum
                return obj.value
            return obj

        state = {
            "seed_event_id": seed_event_id,
            "characters":  {k: _to_dict(v) for k, v in characters.items()},
            "locations":   {k: _to_dict(v) for k, v in locations.items()},
            "factions":    {k: _to_dict(v) for k, v in factions.items()},
            "world_rules": [_to_dict(r) for r in world_rules],
            "events":      [_to_dict(e) for e in events],
        }
        path = self.sm.state_dir / "setup_state.json"
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  [OK] setup_state.json 已保存")

    @classmethod
    def restore(cls, project_root: str | Path, book_id: str) -> ProjectState:
        """从 setup_state.json 快速重建 ProjectState"""
        sm = StateManager(project_root, book_id)
        path = sm.state_dir / "setup_state.json"
        if not path.exists():
            raise FileNotFoundError(
                f"setup_state.json 不存在，请先运行：df setup load {book_id}"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        config_raw = sm.read_config()
        config = BookConfig(
            id=config_raw["id"],
            title=config_raw["title"],
            genre=config_raw["genre"],
            target_words_per_chapter=config_raw["target_words_per_chapter"],
            target_chapters=config_raw["target_chapters"],
            protagonist_id=config_raw.get("protagonist_id", ""),
            custom_forbidden_words=config_raw.get("custom_forbidden_words", []),
            style_guide=config_raw.get("style_guide", ""),
        )
        characters  = {k: load_character(v) for k, v in data["characters"].items()}
        locations   = {k: load_location(v)  for k, v in data["locations"].items()}
        factions    = {k: load_faction(v)   for k, v in data["factions"].items()}
        world_rules = [load_world_rule(r)   for r in data["world_rules"]]
        events      = [load_event(e)        for e in data["events"]]
        return ProjectState(
            config=config,
            characters=characters,
            locations=locations,
            factions=factions,
            world_rules=world_rules,
            seed_events=events,
            world_state=sm.read_world_state(),
        )
