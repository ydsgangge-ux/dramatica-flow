"""
四个核心 Agent：建筑师、写手、审计员、修订者
修复：
- ArchitectAgent 用 pydantic 校验，不再裸 json.loads
- AuditorAgent blueprint 序列化改用 dataclasses.asdict
- AuditIssue 增加 excerpt 字段（pipeline 需要）
- WriterAgent 增加前情摘要注入参数
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, field_validator, Field

from ..llm import LLMProvider, LLMMessage, parse_llm_json, with_retry
from ..types.narrative import Character
from ..narrative import ChapterOutlineSchema


# ─────────────────────────────────────────────────────────────────────────────
# 1. 建筑师 Agent
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PreWriteChecklist:
    active_characters: list[str]
    required_locations: list[str]
    resources_in_play: list[str]
    hooks_status: list[str]
    risk_scan: str


@dataclass
class ArchitectBlueprint:
    core_conflict: str
    hooks_to_advance: list[str]
    hooks_to_plant: list[str]
    emotional_journey: dict[str, str]
    chapter_end_hook: str
    pace_notes: str
    pre_write_checklist: PreWriteChecklist
    # ── 多线叙事扩展 ──
    pov_character_id: str = ""             # 本章视角角色
    thread_id: str = ""                     # 本章所属线程
    thread_context: str = ""               # 其他线程的当前状态摘要（跨线程感知）


# ── pydantic schema 用于 LLM 输出校验 ────────────────────────────────────────

class _ChecklistSchema(BaseModel):
    active_characters: list[str] = Field(default_factory=list)
    required_locations: list[str] = Field(default_factory=list)
    resources_in_play: list[str] = Field(default_factory=list)
    hooks_status: list[str] = Field(default_factory=list)
    risk_scan: str = ""

    @field_validator("active_characters", "required_locations", "resources_in_play", "hooks_status", mode="before")
    @classmethod
    def _ensure_list(cls, v):
        if isinstance(v, str):
            return [line.strip() for line in v.replace("；", "\n").replace(";", "\n").split("\n") if line.strip()]
        if isinstance(v, dict):
            return [f"{k}: {val}" if val else k for k, val in v.items()]
        return v


class _BlueprintSchema(BaseModel):
    core_conflict: str
    hooks_to_advance: list[str] = Field(default_factory=list)
    hooks_to_plant: list[str] = Field(default_factory=list)
    emotional_journey: dict[str, str] = Field(default_factory=dict)
    chapter_end_hook: str = ""
    pace_notes: str = ""
    pre_write_checklist: _ChecklistSchema = Field(default_factory=_ChecklistSchema)
    # 多线叙事扩展
    pov_character_id: str = ""
    thread_id: str = ""
    thread_context: str = ""

    @field_validator("hooks_to_advance", "hooks_to_plant", mode="before")
    @classmethod
    def _ensure_list(cls, v):
        if isinstance(v, str):
            return [line.strip() for line in v.replace("；", "\n").replace(";", "\n").split("\n") if line.strip()]
        return v


class ArchitectAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def plan_chapter(
        self,
        chapter_outline: ChapterOutlineSchema,
        world_context: str,
        pending_hooks: str,
        prior_chapter_summary: str = "",
        pov_character: Character | None = None,
        thread_context: str = "",
    ) -> ArchitectBlueprint:

        prior_ctx = f"\n## 上章摘要\n{prior_chapter_summary}" if prior_chapter_summary else ""

        # ── POV 视角角色（多线叙事） ──
        pov_section = ""
        resolved_pov_id = ""
        if pov_character:
            resolved_pov_id = pov_character.id
            pov_section = f"""
## 视角角色（POV：{pov_character.name}）
- 当前短期目标：{pov_character.current_goal or '（未设定）'}
- 隐藏动机：{pov_character.hidden_agenda or '（无）'}
- 性格锁定（绝对不做）：{'、'.join(pov_character.behavior_lock)}
- 角色职能：{pov_character.role}
> 蓝图设计应围绕 {pov_character.name} 的视角，情感旅程以该角色为准。
"""

        # ── 跨线程上下文（多线叙事） ──
        thread_section = ""
        resolved_thread_id = getattr(chapter_outline, "thread_id", "thread_main") or "thread_main"
        if thread_context.strip():
            thread_section = f"""
## 其他线程状态（跨线程感知）
{thread_context}
> 注意：确保本章事件与其他线程的时间线不冲突。
"""

        prompt = f"""\
你是精通戏剧结构的故事建筑师，为写手规划本章写作蓝图。

## 章纲
- 章节：第 {chapter_outline.chapter_number} 章《{chapter_outline.title}》
- 摘要：{chapter_outline.summary}
- 必完任务：{'；'.join(chapter_outline.mandatory_tasks)}
- 情感弧：{chapter_outline.emotional_arc.get('start', '')} → {chapter_outline.emotional_arc.get('end', '')}
- 字数目标：{chapter_outline.target_words} 字
- 节拍序列：{' → '.join(b.description for b in chapter_outline.beats)}
{prior_ctx}
{pov_section}{thread_section}
## 当前世界状态
{world_context}

## 未闭合伏笔
{pending_hooks if pending_hooks.strip() else "（暂无）"}

请输出完整 JSON，字段说明：
- core_conflict：本章核心冲突（一句话，必须源于角色目标与障碍的碰撞）
- hooks_to_advance：需要在本章推进的伏笔 ID 列表
- hooks_to_plant：本章可以埋下的新伏笔描述列表（每条一句话）
- emotional_journey：{{"start": "章节开始时主角的情绪状态", "end": "章节结束时的情绪状态"}}
- chapter_end_hook：本章最后一个场景/句子的悬念钩子，驱动读者读下一章
- pace_notes：节奏建议（快/慢场景的分配，张弛安排）
- pre_write_checklist：
  - active_characters：本章登场的所有角色名列表
  - required_locations：本章涉及的地点列表
  - resources_in_play：本章涉及的道具/资源/物品列表
  - hooks_status：每条相关伏笔的当前推进状态（一句话）
  - risk_scan：最可能引发连续性错误的高风险点（具体说明）

只输出 JSON，不要任何前言、说明或 Markdown。"""

        def _call() -> ArchitectBlueprint:
            resp = self.llm.complete([
                LLMMessage("system", "你是故事建筑师，只输出合法 JSON，不输出任何说明文字。"),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _BlueprintSchema, "plan_chapter")
            cl_data = parsed.pre_write_checklist
            checklist = PreWriteChecklist(
                active_characters=cl_data.active_characters,
                required_locations=cl_data.required_locations,
                resources_in_play=cl_data.resources_in_play,
                hooks_status=cl_data.hooks_status,
                risk_scan=cl_data.risk_scan,
            )
            return ArchitectBlueprint(
                core_conflict=parsed.core_conflict,
                hooks_to_advance=parsed.hooks_to_advance,
                hooks_to_plant=parsed.hooks_to_plant,
                emotional_journey=parsed.emotional_journey,
                chapter_end_hook=parsed.chapter_end_hook,
                pace_notes=parsed.pace_notes,
                pre_write_checklist=checklist,
                pov_character_id=resolved_pov_id,
                thread_id=resolved_thread_id,
                thread_context=thread_context,
            )

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 2. 写手 Agent
# ─────────────────────────────────────────────────────────────────────────────

SETTLEMENT_SEPARATOR = "===SETTLEMENT==="


@dataclass
class PostWriteSettlement:
    """写后结算表：本章对世界状态的改变"""
    resource_changes: list[str] = field(default_factory=list)
    new_hooks: list[str] = field(default_factory=list)
    resolved_hooks: list[str] = field(default_factory=list)
    relationship_changes: list[str] = field(default_factory=list)
    info_revealed: list[dict[str, str]] = field(default_factory=list)
    character_position_changes: list[dict[str, str]] = field(default_factory=list)
    emotional_changes: list[dict[str, str]] = field(default_factory=list)


@dataclass
class WriterOutput:
    content: str
    settlement: PostWriteSettlement


WRITER_SYSTEM_PROMPT = """\
你是一位优秀的中文小说写手，专注于{genre}题材。

## 创作铁律（不可违反）
1. 只写动作、感知、对话——不替读者下结论，不做心理分析式独白
2. 冲突必须源于角色目标与障碍的碰撞，绝对不靠巧合推进
3. 每个场景必须推进叙事 OR 揭示角色，二者至少占其一
4. 场景结尾状态必须比开始更极端（更好/更坏/意外转折）
5. 对话要有潜台词，人物说的话和真正想说的话之间要有张力

## 语言规范
- AI 标记词（仿佛/忽然/竟然/不禁/宛如/猛地/顿时）：每 3000 字各最多 1 次
- 绝对禁止：元叙事（核心动机/叙事节奏/人物弧线）
- 绝对禁止：报告式语言（分析了形势/从…角度来看/综合考虑）
- 绝对禁止：作者说教（显然/不言而喻/毫无疑问）
- 绝对禁止：集体反应套话（全场震惊/众人哗然/所有人都）
- 破折号「——」：全书最多用 3 次，珍惜使用

## 写后必须输出结算表
正文写完后，用 ===SETTLEMENT=== 分隔，输出 JSON 结算表。"""


class WriterAgent:
    def __init__(self, llm: LLMProvider, style_guide: str = "", genre: str = "玄幻"):
        self.llm = llm
        self.style_guide = style_guide
        self.genre = genre

    def write_chapter(
        self,
        scene_summaries: str,
        blueprint: ArchitectBlueprint,
        protagonist: Character,
        world_context: str,
        chapter_number: int,
        target_words: int,
        prior_summaries: str = "",
        chapter_title: str = "",
        pov_character: Character | None = None,
        thread_context: str = "",
        pending_hooks: str = "",
        causal_chain: str = "",
        emotional_arcs: str = "",
        writing_notes: str = "",
        pov_instruction: str = "",
    ) -> WriterOutput:
        system = WRITER_SYSTEM_PROMPT.format(genre=self.genre)
        if self.style_guide:
            system += f"\n\n## 文风要求\n{self.style_guide}"

        prior_ctx = ""
        if prior_summaries.strip():
            # 只取最近 3 章摘要，避免 context 过长
            lines = prior_summaries.strip().split("\n## ")
            recent = lines[-3:] if len(lines) > 3 else lines
            prior_ctx = f"\n### 前情回顾（最近章节）\n## {'## '.join(recent)}"

        # scene_summaries 已经是格式化好的节拍序列
        beats_str = scene_summaries

        # ── POV 视角角色（多线叙事） ──
        effective_pov = pov_character or protagonist
        pov_section = ""
        if pov_character and pov_character.id != protagonist.id:
            pov_section = f"""
### 视角角色（POV：{pov_character.name}）
- 当前短期目标：{pov_character.current_goal or '（未设定）'}
- 隐藏动机：{pov_character.hidden_agenda or '（无）'}
- 性格锁定（绝对不做）：{'、'.join(pov_character.behavior_lock)}
- 角色职能：{pov_character.role}
> 重要：本章以 {pov_character.name} 的视角叙事，描写风格、感知范围、
> 情感反应均应以该角色为准。该角色不知道的信息不可描写。
"""
        # ── 跨线程上下文（多线叙事） ──
        thread_section = ""
        if thread_context.strip():
            thread_section = f"""
### 其他线程状态（不可在本章直接展现，但可间接暗示）
{thread_context}
> 以上信息仅供写手把握全局节奏，不可直接告诉视角角色。
"""

        settlement_schema = """{
  "resource_changes": ["道具/资源变化，如「林尘的玉佩碎裂」"],
  "new_hooks": ["新埋下的伏笔，一句话描述"],
  "resolved_hooks": ["已回收的伏笔 ID 列表"],
  "relationship_changes": ["关系变化，如「林尘-慕雪：从-80变为-60，原因：慕雪第一次动摇」"],
  "info_revealed": [{"character_id": "角色ID", "info_key": "信息标识", "content": "角色得知了什么"}],
  "character_position_changes": [{"character_id": "角色ID", "location_id": "地点ID"}],
  "emotional_changes": [{"character_id": "角色ID", "emotion": "情绪", "intensity": 7, "trigger": "触发原因"}]
}"""

        prompt = f"""\
## 写作任务：第 {chapter_number} 章{f'《{chapter_title}》' if chapter_title else ''}

### 节拍序列（按顺序写完所有节拍）
{scene_summaries}
{pov_section}{thread_section}{f'''### 视角要求
{pov_instruction.strip()}
''' if pov_instruction and pov_instruction.strip() else ''}
{f'''### 写作基调（本章重要指导）
{writing_notes.strip()}
''' if writing_notes and writing_notes.strip() else ''}
### 主角
姓名：{protagonist.name}
外部目标：{protagonist.need.external}
内在渴望：{protagonist.need.internal}
本章情感旅程：{blueprint.emotional_journey.get('start', '??')} → {blueprint.emotional_journey.get('end', '??')}
性格锁定（绝对不做）：{'、'.join(protagonist.behavior_lock)}

### 核心冲突（必须贯穿全章）
{blueprint.core_conflict}

### 本章结尾钩子（最后必须实现）
{blueprint.chapter_end_hook}

### 节奏建议
{blueprint.pace_notes}

### 本章登场角色
{', '.join(blueprint.pre_write_checklist.active_characters)}

### 当前世界状态
{world_context}
{prior_ctx}
{f'''### 未闭合伏笔（需要在正文中自然推进或埋设）
{pending_hooks.strip()}
''' if pending_hooks and pending_hooks.strip() else ''}
{f'''### 近期因果链（确保本章事件与已有因果关系一致）
{causal_chain[-1200:].strip()}
''' if causal_chain and causal_chain.strip() else ''}
{f'''### 情感弧线（角色情感走向，请保持延续性）
{emotional_arcs[-600:].strip()}
''' if emotional_arcs and emotional_arcs.strip() else ''}

### 高风险连续性点（写时注意）
{blueprint.pre_write_checklist.risk_scan}

### 字数要求
目标 {target_words} 字（允许 ±10%，即 {int(target_words*0.9)}–{int(target_words*1.1)} 字）

---
请直接开始写正文，写完后输出：
{SETTLEMENT_SEPARATOR}
{settlement_schema}"""

        def _call() -> WriterOutput:
            resp = self.llm.complete([
                LLMMessage("system", system),
                LLMMessage("user", prompt),
            ])
            parts = resp.content.split(SETTLEMENT_SEPARATOR, 1)
            content = parts[0].strip()

            settlement = PostWriteSettlement()
            if len(parts) > 1:
                try:
                    raw = json.loads(parts[1].strip())
                    settlement = PostWriteSettlement(
                        resource_changes=raw.get("resource_changes", []),
                        new_hooks=raw.get("new_hooks", []),
                        resolved_hooks=raw.get("resolved_hooks", []),
                        relationship_changes=raw.get("relationship_changes", []),
                        info_revealed=raw.get("info_revealed", []),
                        character_position_changes=raw.get("character_position_changes", []),
                        emotional_changes=raw.get("emotional_changes", []),
                    )
                except Exception:
                    pass  # 结算表解析失败不崩溃，用默认空值

            return WriterOutput(content=content, settlement=settlement)

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 3. 审计员 Agent
# ─────────────────────────────────────────────────────────────────────────────

AuditSeverity = Literal["critical", "warning", "info"]


@dataclass
class AuditIssue:
    dimension: str
    severity: AuditSeverity
    description: str
    location: str | None = None   # 问题在原文的关键句引用
    suggestion: str | None = None
    excerpt: str | None = None    # 触发规则的文本片段（验证器用）


@dataclass
class AuditReport:
    chapter_number: int
    passed: bool
    issues: list[AuditIssue]
    overall_note: str

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


class _AuditIssueSchema(BaseModel):
    dimension: str
    severity: str  # "critical" | "warning" | "info"
    description: str
    location: str | None = None
    suggestion: str | None = None


class _AuditReportSchema(BaseModel):
    chapter_number: int
    passed: bool
    issues: list[_AuditIssueSchema] = Field(default_factory=list)
    overall_note: str = ""


AUDIT_DIMENSIONS = [
    "OOC（角色行为是否符合性格锁定，性格锁定的事绝对不能做）",
    "信息边界（角色是否知道了他不应知道的信息，信息获取是否有合理来源）",
    "因果一致性（每个事件的发生是否有前因，是否靠巧合推进）",
    "情感弧线（本章情感弧是否符合章纲目标，情绪变化是否有足够铺垫）",
    "大纲偏离（本章是否完成了所有 mandatory_tasks，核心冲突是否落地）",
    "节奏（快场景与慢场景的分配是否合理，是否有张弛）",
    "伏笔管理（新开伏笔是否有铺垫，已声明回收的伏笔是否在正文中落地）",
    "去AI味（AI标记词密度、套话、元叙事、报告式语言、集体反应）",
    "连续性（角色位置/道具/时间线/称谓/数值是否前后一致）",
    "冲突质量（每个场景的冲突是否源于角色目标与障碍的张力，不靠巧合）",
    "结尾钩子（章末钩子是否有效实现，是否能驱动读者继续读）",
    "跨线程一致性（多线叙事时，不同线程的角色位置/时间线/信息是否冲突）",
]


class AuditorAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm  # 应传入 temperature=0 的实例

    def audit_chapter(
        self,
        chapter_content: str,
        chapter_number: int,
        blueprint: ArchitectBlueprint,
        truth_context: str,
        settlement: PostWriteSettlement,
        cross_thread_context: str = "",
    ) -> AuditReport:

        # 安全序列化 blueprint（dataclass → dict，避免 json.dumps 崩溃）
        blueprint_dict = dataclasses.asdict(blueprint)
        blueprint_summary = f"""\
- 核心冲突：{blueprint.core_conflict}
- 情感旅程：{blueprint.emotional_journey.get('start','')} → {blueprint.emotional_journey.get('end','')}
- 必须推进伏笔：{blueprint.hooks_to_advance}
- 计划埋下伏笔：{blueprint.hooks_to_plant}
- 结尾钩子：{blueprint.chapter_end_hook}
- 风险点：{blueprint.pre_write_checklist.risk_scan}
- 登场角色：{blueprint.pre_write_checklist.active_characters}"""

        settlement_summary = f"""\
- 资源变化：{settlement.resource_changes}
- 新开伏笔：{settlement.new_hooks}
- 回收伏笔：{settlement.resolved_hooks}
- 关系变化：{settlement.relationship_changes}
- 信息揭示：{settlement.info_revealed}
- 位置变化：{settlement.character_position_changes}
- 情感变化：{settlement.emotional_changes}"""

        dimensions_str = "\n".join(f"{i+1}. {d}" for i, d in enumerate(AUDIT_DIMENSIONS))

        # 正文截断（避免超 token）
        content_for_audit = chapter_content
        if len(chapter_content) > 6000:
            content_for_audit = chapter_content[:3000] + "\n\n...[中间省略]...\n\n" + chapter_content[-2000:]

        # ── 跨线程上下文注入（多线叙事） ──
        cross_thread_section = ""
        if cross_thread_context.strip():
            cross_thread_section = f"""
### 跨线程一致性参照
以下是其他线程最近的时间轴和因果链，用于检测跨线程冲突：
{cross_thread_context[:2000]}

> 请特别检查：
> - 同一角色是否同时出现在不同地点
> - 不同线程中的时间线是否矛盾
> - 一个线程的事件是否与另一个线程的已确立事实冲突
"""

        prompt = f"""\
## 叙事审计：第 {chapter_number} 章

### 审计维度（逐一检查，不可遗漏）
{dimensions_str}

### 章节正文
{content_for_audit}

### 写前蓝图（参照标准）
{blueprint_summary}
{cross_thread_section}
### 写后结算表（需与正文交叉验证）
{settlement_summary}

### 真相文件（连续性参照）
{truth_context[:3000] if len(truth_context) > 3000 else truth_context}

## 评判标准
- critical：叙事逻辑断裂、明显 OOC、重大连续性错误、mandatory_task 完全未完成、跨线程时间线矛盾
- warning：轻微节奏问题、AI 痕迹、伏笔处理不当、情感弧线偏差
- info：可选优化建议

## 输出格式（严格 JSON）
{{
  "chapter_number": {chapter_number},
  "passed": true,
  "issues": [
    {{
      "dimension": "维度名称",
      "severity": "critical",
      "description": "具体问题描述，指出原文哪里出了问题",
      "location": "原文关键句引用（30字以内）",
      "suggestion": "具体修复建议"
    }}
  ],
  "overall_note": "整体评价（1-2句话）"
}}

只输出 JSON，不要任何说明。"""

        def _call() -> AuditReport:
            resp = self.llm.complete([
                LLMMessage(
                    "system",
                    "你是严格的叙事审计员，专注叙事质量，"
                    "对 critical 问题零容忍但不制造假阳性。"
                    "只输出合法 JSON，不输出任何说明文字。",
                ),
                LLMMessage("user", prompt),
            ])
            parsed = parse_llm_json(resp.content, _AuditReportSchema, "audit_chapter")
            issues = [
                AuditIssue(
                    dimension=i.dimension,
                    severity=i.severity,  # type: ignore
                    description=i.description,
                    location=i.location,
                    suggestion=i.suggestion,
                )
                for i in parsed.issues
            ]
            passed = not any(i.severity == "critical" for i in issues)
            return AuditReport(
                chapter_number=parsed.chapter_number,
                passed=passed,
                issues=issues,
                overall_note=parsed.overall_note,
            )

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 4. 修订者 Agent
# ─────────────────────────────────────────────────────────────────────────────

ReviseMode = Literal["spot-fix", "rewrite-section", "polish"]

CHANGELOG_SEPARATOR = "===CHANGELOG==="

_MODE_INSTRUCTIONS: dict[str, str] = {
    "spot-fix":
        "只修改有问题的句子/段落，其余正文一字不动。"
        "保持原段落结构，只替换问题文本。",
    "rewrite-section":
        "重写包含问题的段落（前后各保留一段作为锚点），"
        "保持整体情节不变。",
    "polish":
        "在不改变情节的前提下提升文笔流畅度，"
        "禁止增删段落、修改角色名、加入新情节。",
}


@dataclass
class ReviseResult:
    content: str
    change_log: list[str]


class ReviserAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def revise(
        self,
        original_content: str,
        issues: list[AuditIssue],
        mode: ReviseMode = "spot-fix",
    ) -> ReviseResult:
        critical = [i for i in issues if i.severity == "critical"]
        warnings  = [i for i in issues if i.severity == "warning"]

        if not critical and mode == "spot-fix":
            return ReviseResult(
                content=original_content,
                change_log=["无 critical 问题，跳过修订"],
            )

        issue_lines = []
        for i in (critical + warnings):
            line = f"- [{i.severity.upper()}] {i.dimension}：{i.description}"
            if i.location:
                line += f"\n  原文位置：「{i.location}」"
            if i.suggestion:
                line += f"\n  修复建议：{i.suggestion}"
            issue_lines.append(line)

        prompt = f"""\
## 修订任务
模式：{mode}
规则：{_MODE_INSTRUCTIONS[mode]}
硬约束：不得引入新情节，不得修改角色名，不得改变情节走向。

## 需修订的问题
{chr(10).join(issue_lines)}

## 原文
{original_content}

---
直接输出修订后的完整正文（不要任何前言），然后输出：
{CHANGELOG_SEPARATOR}
["改动说明1", "改动说明2", ...]"""

        def _call() -> ReviseResult:
            resp = self.llm.complete([
                LLMMessage(
                    "system",
                    f"你是精准的小说修订者，模式：{mode}。"
                    f"{_MODE_INSTRUCTIONS[mode]}"
                    "直接输出修订后正文，不要任何前言。",
                ),
                LLMMessage("user", prompt),
            ])
            parts = resp.content.split(CHANGELOG_SEPARATOR, 1)
            content = parts[0].strip()
            change_log: list[str] = []
            if len(parts) > 1:
                try:
                    change_log = json.loads(parts[1].strip())
                except Exception:
                    change_log = [parts[1].strip()[:200]]
            return ReviseResult(content=content, change_log=change_log)

        return with_retry(_call)


# ─────────────────────────────────────────────────────────────────────────────
# 5. 摘要 Agent（新增）
# 写完章节后自动生成章节摘要，注入 chapter_summaries.md
# ─────────────────────────────────────────────────────────────────────────────

class _SummarySchema(BaseModel):
    chapter_number: int
    title: str
    summary: str               # 200字以内的情节摘要
    key_events: list[str]      # 关键事件列表
    characters_appeared: list[str]
    state_changes: list[str]   # 世界状态变化（位置/关系/信息）
    hook_updates: list[str]    # 伏笔动态（新开/推进/回收）
    emotional_note: str        # 主角本章情感变化一句话


class SummaryAgent:
    """章节摘要生成器，写完章节后调用，产出注入 chapter_summaries.md 的内容"""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def generate_summary(
        self,
        chapter_content: str,
        chapter_number: int,
        chapter_title: str,
        settlement: PostWriteSettlement,
    ) -> _SummarySchema:

        content_excerpt = chapter_content[:4000]
        if len(chapter_content) > 4000:
            content_excerpt += "\n...(截断)"

        prompt = f"""\
请为以下章节生成结构化摘要，供后续章节写作时作上下文参考。

## 章节正文（第 {chapter_number} 章《{chapter_title}》）
{content_excerpt}

## 写后结算表（已知的状态变化）
资源变化：{settlement.resource_changes}
新开伏笔：{settlement.new_hooks}
回收伏笔：{settlement.resolved_hooks}
关系变化：{settlement.relationship_changes}
信息揭示：{settlement.info_revealed}

## 输出要求（JSON）
{{
  "chapter_number": {chapter_number},
  "title": "{chapter_title}",
  "summary": "200字以内的情节摘要，说清楚发生了什么、谁做了什么决定",
  "key_events": ["关键事件1", "关键事件2"],
  "characters_appeared": ["出场角色名"],
  "state_changes": ["世界状态变化，如「林尘到达青峰山」「林尘得知灵根封印」"],
  "hook_updates": ["伏笔动态，如「新开：玉佩发热之谜」「推进：退婚之仇」"],
  "emotional_note": "主角本章情感轨迹一句话，如「从屈辱到坚定」"
}}

只输出 JSON。"""

        def _call() -> _SummarySchema:
            resp = self.llm.complete([
                LLMMessage("system", "你是叙事编辑，生成精准的章节摘要，只输出 JSON。"),
                LLMMessage("user", prompt),
            ])
            return parse_llm_json(resp.content, _SummarySchema, "generate_summary")

        return with_retry(_call)

    def format_for_truth_file(self, summary: _SummarySchema) -> str:
        """格式化为写入 chapter_summaries.md 的 Markdown"""
        lines = [
            f"\n## 第 {summary.chapter_number} 章《{summary.title}》\n",
            f"{summary.summary}\n\n",
            f"**出场角色**：{', '.join(summary.characters_appeared)}\n\n",
            "**关键事件**：\n" + "\n".join(f"- {e}" for e in summary.key_events) + "\n\n",
            "**状态变化**：\n" + "\n".join(f"- {c}" for c in summary.state_changes) + "\n\n",
            "**伏笔动态**：\n" + "\n".join(f"- {h}" for h in summary.hook_updates) + "\n\n",
            f"**情感**：{summary.emotional_note}\n",
            "---\n",
        ]
        return "".join(lines)
