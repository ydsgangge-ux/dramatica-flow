"""
叙事引擎
修复：
- generate_chapter_outlines 增加 max_chapters 控制，防止章数爆炸
- StoryOutlineSchema 增加 estimated_total_chapters 字段
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, parse_llm_json_list, with_retry, _fix_df
from ..types.narrative import (
    Character, StoryEvent, DramaticFunction,
)
from ..types.state import CausalLink, AffectedDecision


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class BeatSchema(BaseModel):
    id: str
    description: str
    dramatic_function: DramaticFunction
    target_words: int | None = None
    emotional_target: str | None = None
    detail: str = ""  # 节拍的详细写作指导


class SequenceSchema(BaseModel):
    id: str
    number: int
    act: int
    summary: str
    narrative_goal: str
    dramatic_function: DramaticFunction
    key_events: list[str] = Field(default_factory=list)
    estimated_scenes: int = 3
    end_hook: str = ""


class ChapterOutlineSchema(BaseModel):
    chapter_number: int
    title: str
    summary: str
    sequence_id: str
    beats: list[BeatSchema] = Field(default_factory=list)
    emotional_arc: dict[str, str] = Field(default_factory=dict)
    mandatory_tasks: list[str] = Field(default_factory=list)
    target_words: int = 4000
    writing_notes: str = ""  # 整章写作基调指导
    pov: str = ""  # 视角角色说明
    # ── 多线叙事字段（供 WritingPipeline 的线程/POV 解析读取）──
    thread_id: str = "thread_main"  # 该章节所属叙事线程；单线写作固定为 thread_main
    pov_character_id: str = ""  # 该章节视角角色 ID


class SceneCardSchema(BaseModel):
    id: str
    chapter_number: int
    heading: str
    location: str
    characters: list[str] = Field(default_factory=list)
    dramatic_function: DramaticFunction
    scene_goal: str
    beats: list[BeatSchema] = Field(default_factory=list)
    conflict_core: str
    end_state: str = "worse"


class AffectedDecisionSchema(BaseModel):
    character_id: str
    decision: str


class CausalLinkSchema(BaseModel):
    id: str
    chapter: int
    cause: str
    event: str
    consequence: str
    affected_decisions: list[AffectedDecisionSchema] = Field(default_factory=list)
    triggered_events: list[str] = Field(default_factory=list)


class StoryOutlineSchema(BaseModel):
    id: str
    title: str
    logline: str
    genre: str
    sequences: list[SequenceSchema]
    emotional_roadmap: list[dict[str, str]] = Field(default_factory=list)


# ── NarrativeEngine ───────────────────────────────────────────────────────────

class NarrativeEngine:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    # ── 1. 生成故事大纲 ──────────────────────────────────────────────────────────

    def generate_outline(
        self,
        seed_event: StoryEvent,
        protagonist: Character,
        world_context: str,
        target_chapters: int,
        genre: str,
    ) -> StoryOutlineSchema:
        act1 = round(target_chapters * 0.25)
        act2 = round(target_chapters * 0.50)
        act3 = target_chapters - act1 - act2

        # 序列数量控制：每个序列约覆盖 8-15 章
        seq_count_hint = max(6, target_chapters // 10)

        prompt = f"""\
你是精通 Dramatica 叙事理论的故事架构师。

## 任务
为一部 {target_chapters} 章的{genre}小说生成完整故事大纲。
序列数量建议：{seq_count_hint} 个左右（不要过多也不要过少）。

## 种子事件（第一幕激励事件）
名称：{seed_event.name}
描述：{seed_event.description}
效果：{'、'.join(seed_event.effects)}

## 主角
姓名：{protagonist.name}
外部目标：{protagonist.need.external}
内在渴望：{protagonist.need.internal}
角色弧线：{protagonist.arc}（positive=成长变好 negative=堕落 flat=不变 corrupt=腐化）
性格锁定：{'、'.join(protagonist.behavior_lock)}

## 世界背景
{world_context[:2000]}

## 三幕章节分配
- 第一幕：约 {act1} 章  目的：建立世界+角色+冲突，激励事件发生
- 第二幕：约 {act2} 章  目的：持续升级对抗，中点处有重大转折，危机最低点
- 第三幕：约 {act3} 章  目的：高潮对决，解决冲突，角色完成弧线

## 核心要求
1. 因果链：每个序列的发生必须是前一序列后果的直接结果
2. 钩子：每个序列的 end_hook 必须制造具体的悬念（不能是模糊的"xxx将何去何从"）
3. Logline 格式：「[主角] 必须在 [时限/代价] 内 [目标]，但 [障碍]」
4. 序列 estimated_scenes 是这个序列预计展开的章节数，所有序列的 estimated_scenes 之和必须等于 {target_chapters}

## JSON 输出格式
{{
  "id": "outline_001",
  "title": "书名",
  "logline": "...",
  "genre": "{genre}",
  "sequences": [
    {{
      "id": "seq_01",
      "number": 1,
      "act": 1,
      "summary": "序列内容摘要（2句话）",
      "narrative_goal": "这个序列要完成的叙事任务",
      "dramatic_function": "inciting",
      "key_events": ["关键事件1", "关键事件2"],
      "estimated_scenes": 5,
      "end_hook": "具体的悬念钩子（一句话，要有画面感）"
    }}
  ],
  "emotional_roadmap": [
    {{"chapter": "1", "target_emotion": "屈辱"}},
    {{"chapter": "10", "target_emotion": "坚定"}}
  ]
}}

只输出 JSON，不要任何说明。"""

        def _call() -> StoryOutlineSchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是精通戏剧理论的故事架构师，只输出合法 JSON。"),
                LLMMessage("user", prompt),
            ])

            _VALID_DF = {"setup", "inciting", "turning", "midpoint", "crisis", "climax", "reveal", "decision", "consequence", "transition"}

            def _patch_outline(data: dict) -> dict:
                """修复大纲中常见的 AI 输出问题"""
                for seq in data.get("sequences", []):
                    if not isinstance(seq, dict):
                        continue
                    # 补 narrative_goal
                    if not seq.get("narrative_goal"):
                        seq["narrative_goal"] = seq.get("summary", "推进剧情")
                    # 修正 dramatic_function
                    if seq.get("dramatic_function") and seq["dramatic_function"] not in _VALID_DF:
                        seq["dramatic_function"] = _fix_df(seq["dramatic_function"])
                    # estimated_scenes 至少为 1
                    if seq.get("estimated_scenes", 0) < 1:
                        seq["estimated_scenes"] = 1
                return data

            outline = parse_llm_json(resp.content, StoryOutlineSchema, "generate_outline", patch_fn=_patch_outline)

            # 校验并修正章数
            total = sum(s.estimated_scenes for s in outline.sequences)
            if total != target_chapters and total > 0:
                # 等比缩放到目标章数
                ratio = target_chapters / total
                remaining = target_chapters
                for i, seq in enumerate(outline.sequences):
                    if i == len(outline.sequences) - 1:
                        seq.estimated_scenes = remaining
                    else:
                        scaled = max(1, round(seq.estimated_scenes * ratio))
                        seq.estimated_scenes = scaled
                        remaining -= scaled

            return outline

        return with_retry(_call)

    # ── 2. 章纲生成（序列 → 章，有章数上限控制） ──────────────────────────────

    def generate_chapter_outlines(
        self,
        sequence: SequenceSchema,
        protagonist: Character,
        world_context: str,
        chapter_start: int,
        words_per_chapter: int,
    ) -> list[ChapterOutlineSchema]:
        """
        将一个序列展开为 estimated_scenes 个章纲。
        严格按照 estimated_scenes 控制生成章数。
        如果章数过多则分批调用 LLM，避免输出超出 max_tokens 被截断。
        """
        n_chapters = sequence.estimated_scenes
        # 每批最多生成 5 章，防止 JSON 太长被截断
        BATCH_SIZE = 5
        all_outlines = []

        # AI 常用的非法 dramatic_function 别名映射到合法值
        _DF_ALIASES = {
            "twist": "turning", "turn": "turning", "turning_point": "turning", "progressive complication": "turning",
            "complication": "turning", "转折": "turning",
            "hook": "inciting", "trigger": "inciting", "钩子": "inciting",
            "conflict": "crisis", "crash": "crisis", "dark night": "crisis", "all is lost": "crisis", "冲突": "crisis",
            "battle": "climax", "peak": "climax", "showdown": "climax", "confrontation": "climax", "战斗": "climax",
            "ending": "consequence", "result": "consequence", "resolution": "consequence", "denouement": "consequence", "后果": "consequence",
            "info": "reveal", "discover": "reveal", "revelation": "reveal", "揭示": "reveal",
            "choice": "decision", "select": "decision", "commitment": "decision", "选择": "decision",
            "build": "setup", "intro": "setup", "introduct": "setup", "exposition": "setup", "建立": "setup",
            "bridge": "transition", "pause": "transition", "interlude": "transition", "过渡": "transition",
            "middle": "midpoint", "mid": "midpoint", "中点": "midpoint",
        }
        _VALID_DF = {"setup", "inciting", "turning", "midpoint", "crisis", "climax", "reveal", "decision", "consequence", "transition"}

        def _patch(item: dict) -> dict:
            if "chapter" in item and "chapter_number" not in item:
                item["chapter_number"] = item.pop("chapter")
            if "summary" not in item:
                item["summary"] = item.get("title", "章节摘要")
            if "title" not in item:
                item["title"] = f"第{item.get('chapter_number', '?')}章"
            # 修正序列级的 dramatic_function
            if item.get("dramatic_function") and item["dramatic_function"] not in _VALID_DF:
                item["dramatic_function"] = _DF_ALIASES.get(item["dramatic_function"].lower().strip(), "transition")
            for bi, beat in enumerate(item.get("beats", [])):
                if not beat.get("id"):
                    beat["id"] = f"beat_{item.get('chapter_number', bi)}_{bi+1}"
                # 修正 beat 的 dramatic_function
                if beat.get("dramatic_function") and beat["dramatic_function"] not in _VALID_DF:
                    beat["dramatic_function"] = _DF_ALIASES.get(str(beat["dramatic_function"]).lower().strip(), "transition")
            return item

        for batch_start in range(0, n_chapters, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, n_chapters)
            batch_count = batch_end - batch_start
            actual_ch_start = chapter_start + batch_start

            prompt = f"""\
将以下故事序列展开为 **恰好 {batch_count} 个**章纲。

## 序列信息
摘要：{sequence.summary}
叙事目标：{sequence.narrative_goal}
戏剧功能：{sequence.dramatic_function.value}
关键事件：{'、'.join(sequence.key_events)}
结尾钩子（最后一章必须实现）：{sequence.end_hook}

## 主角
{protagonist.name}：
- 外部目标：{protagonist.need.external}
- 内在渴望：{protagonist.need.internal}
- 性格锁定：{'、'.join(protagonist.behavior_lock)}

## 当前世界状态
{world_context[:1500]}

## 严格要求
- 每章必须包含 summary（章节摘要，50字以内）
- 每章必须包含 beats 数组，每个 beat 必须包含 id、description、dramatic_function 字段
- 章节编号从第 {actual_ch_start} 章开始
- 必须生成 **恰好 {batch_count} 个**章纲，不多不少
- 每章 {words_per_chapter} 字
- beats 每章 2-3 个即可，description 控制在20字内
- beats 的 dramatic_function 必须是以下之一：
  setup/inciting/turning/midpoint/crisis/climax/reveal/decision/consequence/transition
- mandatory_tasks 列出本章不完成就审计不通过的叙事任务（1-2个）
- emotional_arc 格式：{{"start": "开始情绪", "end": "结束情绪"}}
- sequence_id 统一填 "{sequence.id}"

只输出 JSON 数组（{batch_count} 个元素），不要任何说明。"""

            def _call() -> list[ChapterOutlineSchema]:
                resp = self.llm.complete([
                    LLMMessage("system", "你是精通节拍表的故事编辑，只输出合法 JSON 数组，章数必须精确。"),
                    LLMMessage("user", prompt),
                ])
                outlines = parse_llm_json_list(
                    resp.content, ChapterOutlineSchema, "generate_chapter_outlines",
                    patch_fn=_patch,
                )
                for i, co in enumerate(outlines):
                    co.chapter_number = actual_ch_start + i
                    if co.target_words == 0:
                        co.target_words = words_per_chapter
                if len(outlines) > batch_count:
                    outlines = outlines[:batch_count]
                elif len(outlines) < batch_count:
                    # 不再用「情节推进」占位章补齐：占位章会污染细纲与正文。
                    # 章数不足视为 LLM 输出不合格，交给外层 with_retry 重试。
                    raise ValueError(
                        f"章纲数量不足：需要 {batch_count} 个，实际 {len(outlines)} 个"
                    )
                return outlines

            batch_result = with_retry(_call)
            all_outlines.extend(batch_result)
        return all_outlines

    # ── 2.5 单章章纲（逐章生成，不覆盖已有章纲） ───────────────────────────────

    def generate_single_chapter_outline(
        self,
        sequence: SequenceSchema | None,
        protagonist: Character,
        world_context: str,
        chapter_number: int,
        words_per_chapter: int,
        prev_context: str = "",
        recent_outlines: str = "",
        user_hint: str = "",
    ) -> ChapterOutlineSchema:
        """
        只生成 1 个章纲。用于「生成下一章」和「重新生成本章」，
        避免一次性重生成整卷导致手工修改丢失。
        """
        _DF_ALIASES = {
            "twist": "turning", "turn": "turning", "turning_point": "turning",
            "complication": "turning", "转折": "turning",
            "hook": "inciting", "trigger": "inciting", "钩子": "inciting",
            "conflict": "crisis", "crash": "crisis", "冲突": "crisis",
            "battle": "climax", "showdown": "climax", "战斗": "climax",
            "ending": "consequence", "result": "consequence", "后果": "consequence",
            "info": "reveal", "revelation": "reveal", "揭示": "reveal",
            "choice": "decision", "选择": "decision",
            "build": "setup", "intro": "setup", "建立": "setup",
            "bridge": "transition", "pause": "transition", "过渡": "transition",
            "mid": "midpoint", "中点": "midpoint",
        }
        _VALID_DF = {"setup", "inciting", "turning", "midpoint", "crisis",
                     "climax", "reveal", "decision", "consequence", "transition"}

        seq_block = "（本章不属于任何已有序列，请承接前文自然推进主线）"
        seq_id = ""
        if sequence is not None:
            seq_id = sequence.id
            seq_block = f"""\
- 序列摘要：{sequence.summary}
- 叙事目标：{sequence.narrative_goal}
- 戏剧功能：{sequence.dramatic_function.value}
- 关键事件：{'、'.join(sequence.key_events)}
- 该序列结尾钩子：{sequence.end_hook}"""

        prev_block = ""
        if prev_context.strip():
            prev_block = f"\n## 前文衔接（必须承接）\n{prev_context.strip()[:2000]}\n"

        recent_block = ""
        if recent_outlines.strip():
            recent_block = f"\n## 最近几章章纲（保持连贯，不要重复）\n{recent_outlines.strip()[:1500]}\n"

        hint_block = ""
        if user_hint.strip():
            hint_block = f"\n## 用户追加的剧情点（必须体现）\n{user_hint.strip()}\n"

        prompt = f"""\
请为一部小说生成**第 {chapter_number} 章**的章节大纲（只生成这 1 章，不要多也不要少）。

## 故事序列
{seq_block}

## 主角
{protagonist.name}：
- 外部目标：{protagonist.need.external}
- 内在渴望：{protagonist.need.internal}
- 性格锁定：{'、'.join(protagonist.behavior_lock)}

## 当前世界状态
{world_context[:1200] if world_context.strip() else '（尚未建立）'}
{prev_block}{recent_block}{hint_block}
## 严格要求
- 只输出 1 个 JSON 对象，不要数组、不要任何说明
- summary 为本章剧情摘要（50 字以内）
- beats 为 2-3 个节拍，每个必须包含 id、description、dramatic_function
- dramatic_function 只能是：setup/inciting/turning/midpoint/crisis/climax/reveal/decision/consequence/transition
- 本章目标字数 {words_per_chapter} 字
- mandatory_tasks 列出本章不完成就审计不通过的叙事任务（1-2 个）
- emotional_arc 格式：{{"start": "开始情绪", "end": "结束情绪"}}
- sequence_id 填 "{seq_id}"

## JSON 输出格式
{{
  "chapter_number": {chapter_number},
  "title": "第{chapter_number}章 标题",
  "summary": "本章剧情摘要",
  "sequence_id": "{seq_id}",
  "beats": [
    {{"id": "beat_{chapter_number}_1", "description": "节拍描述", "dramatic_function": "setup"}}
  ],
  "emotional_arc": {{"start": "平静", "end": "紧张"}},
  "mandatory_tasks": ["必须完成的叙事任务"],
  "target_words": {words_per_chapter},
  "pov": "",
  "writing_notes": ""
}}

只输出 JSON，不要任何说明。"""

        def _patch(item: dict) -> dict:
            if "chapter" in item and "chapter_number" not in item:
                item["chapter_number"] = item.pop("chapter")
            if not item.get("summary"):
                item["summary"] = item.get("title", "章节摘要")
            if not item.get("title"):
                item["title"] = f"第{chapter_number}章"
            if not item.get("sequence_id") and seq_id:
                item["sequence_id"] = seq_id
            for bi, beat in enumerate(item.get("beats", []) or []):
                if not isinstance(beat, dict):
                    continue
                if not beat.get("id"):
                    beat["id"] = f"beat_{chapter_number}_{bi+1}"
                fn = str(beat.get("dramatic_function", "") or "").lower().strip()
                if fn and fn not in _VALID_DF:
                    beat["dramatic_function"] = _DF_ALIASES.get(fn, "transition")
                elif not fn:
                    beat["dramatic_function"] = "transition"
            return item

        def _call() -> ChapterOutlineSchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是精通节拍表的故事编辑，只输出合法 JSON 对象。"),
                LLMMessage("user", prompt),
            ])
            raw = resp.content.strip()
            # 模型偶尔会输出数组，取第一个即可
            if raw.lstrip().startswith("["):
                items = parse_llm_json_list(
                    raw, ChapterOutlineSchema, "generate_single_chapter_outline",
                    patch_fn=_patch,
                )
                if not items:
                    raise ValueError("单章章纲输出为空")
                co = items[0]
            else:
                co = parse_llm_json(
                    raw, ChapterOutlineSchema, "generate_single_chapter_outline",
                    patch_fn=_patch,
                )
            if not co.beats:
                raise ValueError("单章章纲缺少 beats，输出不合格")
            co.chapter_number = chapter_number
            if not co.target_words:
                co.target_words = words_per_chapter
            for bi, beat in enumerate(co.beats):
                if not beat.id:
                    beat.id = f"beat_{chapter_number}_{bi+1}"
            return co

        return with_retry(_call)

    # ── 3. 因果链提取 ──────────────────────────────────────────────────────────

    def extract_causal_links(
        self,
        chapter_content: str,
        chapter_number: int,
        characters: list[Character],
    ) -> list[CausalLinkSchema]:
        char_list = "、".join(f"{c.id}（{c.name}）" for c in characters)
        content_excerpt = chapter_content[:4000]
        if len(chapter_content) > 4000:
            content_excerpt += "\n...(截断)"

        prompt = f"""\
分析第 {chapter_number} 章，提取关键因果关系（2-5 条，不要过多）。

## 章节内容
{content_excerpt}

## 角色列表
{char_list}

## 要求
每条因果链必须回答：
- 因为什么（cause）→ 发生了什么（event）→ 导致什么后果（consequence）
- 哪个角色因此做了什么决定（affected_decisions）
- 下游会触发什么事件（triggered_events，自然语言）

ID 格式：causal_ch{chapter_number}_001

只输出 JSON 数组（CausalLinkSchema[]），不要说明。"""

        def _call() -> list[CausalLinkSchema]:
            resp = self.llm.complete([
                LLMMessage("system", "你是叙事分析师，分析因果结构，只输出合法 JSON 数组。"),
                LLMMessage("user", prompt),
            ])
            return parse_llm_json_list(
                resp.content, CausalLinkSchema, "extract_causal_links"
            )

        try:
            return with_retry(_call)
        except Exception:
            return []  # 因果链提取失败不阻塞主流程
