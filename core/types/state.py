"""
状态追踪类型
真相文件、世界状态、关系网络、信息边界、因果链、叙事线程、时间轴
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from .narrative import Character, Location, Faction, WorldRule, StoryEvent, NarrativeThread, TimelineEvent


# ── 真相文件 Key ──────────────────────────────────────────────────────────────

class TruthFileKey(str, Enum):
    CURRENT_STATE     = "current_state"      # 世界当前状态
    STORY_BIBLE       = "story_bible"        # 世界观圣经（人工维护，不被覆盖）
    CHAPTER_SUMMARIES = "chapter_summaries"  # 各章摘要
    PENDING_HOOKS     = "pending_hooks"      # 未闭合伏笔
    EMOTIONAL_ARCS    = "emotional_arcs"     # 各角色情感弧线
    CHARACTER_MATRIX  = "character_matrix"   # 角色交互矩阵与信息边界
    CAUSAL_CHAIN      = "causal_chain"       # 因果链日志（核心差异点）
    THREAD_STATUS     = "thread_status"      # 叙事线程状态与支线预警


TRUTH_FILE_NAMES: dict[TruthFileKey, str] = {
    TruthFileKey.CURRENT_STATE:     "current_state.md",
    TruthFileKey.STORY_BIBLE:       "story_bible.md",
    TruthFileKey.CHAPTER_SUMMARIES: "chapter_summaries.md",
    TruthFileKey.PENDING_HOOKS:     "pending_hooks.md",
    TruthFileKey.EMOTIONAL_ARCS:    "emotional_arcs.md",
    TruthFileKey.CHARACTER_MATRIX:  "character_matrix.md",
    TruthFileKey.CAUSAL_CHAIN:      "causal_chain.md",
    TruthFileKey.THREAD_STATUS:     "thread_status.md",
}


# ── 关系网络 ──────────────────────────────────────────────────────────────────

class RelationshipType(str, Enum):
    ALLY     = "ally"
    ENEMY    = "enemy"
    NEUTRAL  = "neutral"
    FAMILY   = "family"
    MENTOR   = "mentor"
    RIVAL    = "rival"
    ROMANTIC = "romantic"


@dataclass
class RelationshipDelta:
    chapter: int
    delta: int      # 关系强度变化量
    reason: str


@dataclass
class RelationshipRecord:
    character_a: str
    character_b: str
    type: RelationshipType
    # -100（极度敌对）到 100（深度同盟）
    strength: int
    known_to: list[str] = field(default_factory=list)  # 谁知道这段关系
    history: list[RelationshipDelta] = field(default_factory=list)

    @property
    def key(self) -> str:
        """关系唯一键，与顺序无关"""
        return ":".join(sorted([self.character_a, self.character_b]))


# ── 信息边界 ──────────────────────────────────────────────────────────────────

@dataclass
class KnownInfoRecord:
    """
    角色只知道亲眼见过 / 亲耳听到的信息。
    这是防止"信息越界"（角色知道了不该知道的事）的核心数据结构。
    """
    character_id: str
    info_key: str       # 信息标识符，如 "protagonist_true_identity"
    content: str
    learned_in_chapter: int
    source: Literal["witnessed", "hearsay", "deduced", "document"]


# ── 情感状态 ──────────────────────────────────────────────────────────────────

@dataclass
class EmotionalSnapshot:
    character_id: str
    emotion: str
    intensity: int   # 1–10
    chapter: int
    trigger: str


# ── 伏笔与承诺 ────────────────────────────────────────────────────────────────

class HookType(str, Enum):
    FORESHADOW = "foreshadow"  # 伏笔
    PROMISE    = "promise"     # 对读者的承诺（如三年之约）
    MYSTERY    = "mystery"     # 悬念（未解之谜）
    CONFLICT   = "conflict"    # 未解决冲突


class HookStatus(str, Enum):
    OPEN      = "open"
    RESOLVED  = "resolved"
    ABANDONED = "abandoned"


@dataclass
class Hook:
    id: str
    type: HookType
    description: str
    planted_in_chapter: int
    # 预期回收章节范围 [earliest, latest]
    expected_resolution_range: tuple[int, int]
    status: HookStatus = HookStatus.OPEN
    resolved_in_chapter: int | None = None


# ── 因果链（核心差异点，InkOS 缺失） ─────────────────────────────────────────

@dataclass
class AffectedDecision:
    character_id: str
    decision: str


@dataclass
class CausalLink:
    """
    因果链节点：记录事件之间的因果关系。

    每个事件都必须回答：
        "因为 [cause]，所以发生了 [event]，
         导致 [consequence]，
         因此 [character] 决定 [decision]"

    这是与 InkOS 最大的架构差异：
    强制建模因果，确保故事是有机叙事而非事件堆砌。
    多线叙事扩展：支持跨线程因果追踪。
    """
    id: str
    chapter: int
    cause: str                              # 触发原因
    event: str                              # 发生了什么
    consequence: str                        # 直接后果
    affected_decisions: list[AffectedDecision] = field(default_factory=list)
    triggered_events: list[str]             = field(default_factory=list)  # 下游事件描述
    # 多线叙事扩展
    thread_id: str = "thread_main"          # 该因果链所属线程
    source_thread_id: str = ""              # 原因来源线程（跨线程因果时不同于 thread_id）


# ── 状态快照（用于章节回滚） ──────────────────────────────────────────────────

@dataclass
class StateSnapshot:
    book_id: str
    chapter: int
    created_at: str  # ISO timestamp
    world_state: "WorldState"
    truth_files: dict[TruthFileKey, str]  # 快照时的真相文件内容


# ── 世界状态（内存中的结构化版本） ───────────────────────────────────────────

@dataclass
class WorldState:
    book_id: str
    current_chapter: int = 0
    character_positions: dict[str, str]          = field(default_factory=dict)   # char_id → loc_id
    relationships: list[RelationshipRecord]       = field(default_factory=list)
    known_info: list[KnownInfoRecord]             = field(default_factory=list)
    emotional_snapshots: list[EmotionalSnapshot]  = field(default_factory=list)
    pending_hooks: list[Hook]                     = field(default_factory=list)
    causal_chain: list[CausalLink]                = field(default_factory=list)
    # ── 多线叙事扩展字段 ──
    threads: list[NarrativeThread]                = field(default_factory=list)
    timeline: list[TimelineEvent]                 = field(default_factory=list)

    def get_relationship(self, a: str, b: str) -> RelationshipRecord | None:
        key = ":".join(sorted([a, b]))
        return next((r for r in self.relationships if r.key == key), None)

    def character_knows(self, character_id: str, info_key: str) -> bool:
        return any(
            i.character_id == character_id and i.info_key == info_key
            for i in self.known_info
        )

    def open_hooks(self) -> list[Hook]:
        return [h for h in self.pending_hooks if h.status == HookStatus.OPEN]

    def overdue_hooks(self, current_chapter: int) -> list[Hook]:
        """超过预期回收章节还未回收的伏笔"""
        return [
            h for h in self.open_hooks()
            if current_chapter > h.expected_resolution_range[1]
        ]

    # ── 多线叙事辅助方法 ──

    def get_thread(self, thread_id: str) -> NarrativeThread | None:
        return next((t for t in self.threads if t.id == thread_id), None)

    def get_active_threads(self) -> list[NarrativeThread]:
        return [t for t in self.threads if t.status == "active"]

    def dormant_threads(self, current_chapter: int, threshold: int = 5) -> list[NarrativeThread]:
        """掉线预警：超过 threshold 章未活跃的线程"""
        return [
            t for t in self.get_active_threads()
            if current_chapter - t.last_active_chapter >= threshold
        ]

    def thread_chapter_map(self) -> dict[str, list[int]]:
        """按线程索引已写章节号（从 timeline 反推）"""
        result: dict[str, list[int]] = {}
        for te in self.timeline:
            result.setdefault(te.thread_id, []).append(te.chapter)
        return {k: sorted(set(v)) for k, v in result.items()}


# ── 书籍配置 ──────────────────────────────────────────────────────────────────

@dataclass
class BookConfig:
    id: str
    title: str
    genre: str
    target_words_per_chapter: int
    target_chapters: int
    protagonist_id: str
    status: Literal["planning", "writing", "paused", "complete"] = "planning"
    created_at: str = ""
    custom_forbidden_words: list[str] = field(default_factory=list)
    style_guide: str = ""  # 文风指南（文风仿写用）
    # ── 多线叙事扩展字段 ──
    pov_characters: list[str] = field(default_factory=list)  # POV 视角角色 ID 列表（多主角时使用）


# ── 完整项目状态 ──────────────────────────────────────────────────────────────

@dataclass
class ProjectState:
    config: BookConfig
    characters: dict[str, Character]   = field(default_factory=dict)
    locations: dict[str, Location]     = field(default_factory=dict)
    factions: dict[str, Faction]       = field(default_factory=dict)
    world_rules: list[WorldRule]       = field(default_factory=list)
    seed_events: list[StoryEvent]      = field(default_factory=list)
    world_state: WorldState            = field(default_factory=lambda: WorldState(book_id=""))
    truth_files: dict[TruthFileKey, str] = field(default_factory=dict)
