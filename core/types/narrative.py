"""
叙事理论核心类型
基于 Dramatica 理论 + 三幕结构 + 多线叙事支持
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# ── 戏剧功能 ──────────────────────────────────────────────────────────────────

class DramaticFunction(str, Enum):
    SETUP        = "setup"        # 建立角色/世界/规则
    INCITING     = "inciting"     # 激励事件，打破平衡
    TURNING      = "turning"      # 转折点，方向改变
    MIDPOINT     = "midpoint"     # 中点，承诺升级或假胜利
    CRISIS       = "crisis"       # 危机，最低点
    CLIMAX       = "climax"       # 高潮，终极对决
    REVEAL       = "reveal"       # 信息揭示，改变认知
    DECISION     = "decision"     # 角色做出关键选择
    CONSEQUENCE  = "consequence"  # 行动的后果落地
    TRANSITION   = "transition"   # 过渡，节奏调节


Act = Literal[1, 2, 3]


# ── 角色职能（Dramatica Roles）─────────────────────────────────────────────

class CharacterRole(str, Enum):
    PROTAGONIST   = "protagonist"    # 主角
    ANTAGONIST    = "antagonist"     # 反派
    IMPACT        = "impact"         # 冲击者（改变主角认知的人）
    GUARDIAN      = "guardian"       # 守护者（导师/引导者）
    CONTAGONIST   = "contagonist"    # 阻碍者（表面帮主角，实际拖延）
    SIDEKICK      = "sidekick"       # 伙伴（忠诚支持者）
    SKEPTIC       = "skeptic"        # 怀疑者
    REASON        = "reason"         # 理性者
    EMOTION       = "emotion"        # 感性者
    LOVE_INTEREST = "love_interest"  # 恋人
    MENTOR        = "mentor"         # 导师
    SUPPORTING    = "supporting"     # 普通配角


@dataclass
class Beat:
    """故事节拍——比场景更细的叙事单元"""
    id: str
    description: str
    dramatic_function: DramaticFunction
    target_words: int | None = None
    # 读者在这个节拍后应该感受到什么
    emotional_target: str | None = None
    # 该节拍的视角角色（多线叙事用）
    pov_character_id: str | None = None
    # 节拍的详细写作指导
    detail: str = ""


# ── 角色动力学 ────────────────────────────────────────────────────────────────

@dataclass
class CharacterNeed:
    """
    双层需求（Dramatica 核心）
    外部目标：角色想要得到什么（可见的、可量化的）
    内在渴望：角色真正需要的是什么（往往自己不自知）
    """
    external: str  # "逆天改命，登顶巅峰"
    internal: str  # "证明自己不是废物"


@dataclass
class CharacterWorldview:
    """角色对世界的根本看法，决定行为模式"""
    power: Literal["seeks", "rejects", "accepts"]
    trust: Literal["trusting", "suspicious", "selective"]
    coping: Literal["fight", "flee", "freeze", "fawn"]


class ObstacleType(str, Enum):
    ANTAGONIST  = "antagonist"  # 对手（人）
    ENVIRONMENT = "environment" # 环境/自然力量
    SOCIETY     = "society"     # 社会/体制
    SELF        = "self"        # 自我（内在障碍）
    FATE        = "fate"        # 命运/不可抗力


@dataclass
class Obstacle:
    type: ObstacleType
    description: str
    # 障碍如何具体阻碍外部目标
    mechanism: str


@dataclass
class EmotionalArcPoint:
    chapter: int
    emotion: str
    intensity: int  # 1–10
    trigger: str
    direction: Literal["ascending", "descending", "plateau"]


@dataclass
class Character:
    id: str
    name: str
    need: CharacterNeed
    obstacles: list[Obstacle]
    worldview: CharacterWorldview
    # positive=成长 negative=堕落 flat=不变 corrupt=腐化
    arc: Literal["positive", "negative", "flat", "corrupt"]
    profile: str                   # 外貌、背景、说话风格
    behavior_lock: list[str]       # 绝对不会做的事（性格锁定）
    # ── 多线叙事扩展字段 ──
    role: str = "supporting"       # 角色职能（CharacterRole 枚举值）
    personality: list[str] = field(default_factory=list)   # 性格特征列表
    backstory: str = ""             # 背景故事
    # 动态动机系统：每个重要角色拥有独立的因果链
    current_goal: str = ""          # 当前短期目标（随剧情变化）
    hidden_agenda: str = ""         # 隐藏动机（其他角色/读者可能不知道）


# ── 叙事线程（多线叙事核心）───────────────────────────────────────────────

class ThreadType(str, Enum):
    MAIN = "main"           # 主线
    SUBPLOT = "subplot"     # 支线
    PARALLEL = "parallel"   # 并行线（同时发生，最终汇合）
    FLASHBACK = "flashback" # 闪回线


@dataclass
class NarrativeThread:
    """
    叙事线程——多线叙事的基本单元。
    每条线程有独立的视角角色、目标弧线和进度追踪。
    """
    id: str                              # "thread_main", "thread_villain"
    name: str                            # "主角线", "反派线"
    type: ThreadType = ThreadType.MAIN
    pov_character_id: str = ""           # 该线程的主视角角色
    # 线程角色列表（不仅是视角角色，也包括该线程的重要角色）
    character_ids: list[str] = field(default_factory=list)
    # 目标弧线
    goal: str = ""                       # 线程的终极目标
    growth_arc: str = ""                 # 线程的角色成长弧线描述
    # 进度追踪
    start_chapter: int = 1               # 线程起始章节
    last_active_chapter: int = 0         # 上一次活跃的章节（掉线预警用）
    weight: float = 1.0                  # 篇幅权重（1.0 = 主线，0.3 = 支线）
    # 状态
    status: Literal["active", "dormant", "resolved", "merged"] = "active"
    merge_target_thread: str | None = None  # 合并目标线程 ID
    # 期待感指数（0-100，每章由 strategist 更新）
    hook_score: int = 80
    # 预计汇合章节（用于并行线/支线的收束规划）
    merge_chapter: int | None = None
    end_hook: str = ""                   # 线程当前的悬念钩子


# ── 全局时间轴 ────────────────────────────────────────────────────────────────

@dataclass
class TimelineEvent:
    """
    全局时间轴事件——记录"谁在什么时候，在什么地方，做了什么"。
    这是多线叙事的"上帝视角"账本。
    """
    id: str
    chapter: int                          # 叙事章节号
    # 物理时间标记（可以是相对的，如"第一天清晨"）
    physical_time: str = ""               # "第一天清晨" / "T+3h" / "第三天傍晚"
    # 物理时间排序键（数值越大越晚，用于排序）
    time_order: float = 0.0
    character_id: str = ""                # 执行动作的角色
    location_id: str = ""                 # 发生地点
    action: str = ""                      # 发生了什么
    thread_id: str = ""                   # 属于哪条线程
    # 跨线程影响：该事件是否影响了其他线程的角色
    affected_threads: list[str] = field(default_factory=list)
    affected_characters: list[str] = field(default_factory=list)


# ── 世界观 ────────────────────────────────────────────────────────────────────

@dataclass
class Location:
    id: str
    name: str
    description: str
    connections: list[str] = field(default_factory=list)  # 相邻地点 ID
    faction: str | None = None
    dramatic_potential: str | None = None  # 该地点的戏剧潜力


@dataclass
class Faction:
    id: str
    name: str
    description: str
    # 与其他势力的关系值 -100（死敌）到 100（同盟）
    relations: dict[str, int] = field(default_factory=dict)
    core_interest: str = ""


@dataclass
class WorldRule:
    name: str
    description: str
    consequence: str  # 违反规则的后果
    is_hard: bool     # 不可违反的硬规则


# ── 事件与因果 ────────────────────────────────────────────────────────────────

@dataclass
class StoryEvent:
    id: str
    name: str
    description: str
    preconditions: list[str] = field(default_factory=list)
    effects: list[str]       = field(default_factory=list)
    # 直接因果：哪些事件会因此被触发（事件 ID）
    triggers: list[str]      = field(default_factory=list)
    suggested_act: Act | None = None
    suggested_function: DramaticFunction | None = None


# ── 大纲层级 ──────────────────────────────────────────────────────────────────

@dataclass
class SequenceOutline:
    """序列大纲——对应约 8–15 分钟的戏剧时间"""
    id: str
    number: int
    act: Act
    summary: str
    narrative_goal: str            # 该序列要完成的叙事任务
    dramatic_function: DramaticFunction
    key_events: list[str]
    estimated_scenes: int
    # 序列结尾的「转折钩子」——驱动读者读下去
    end_hook: str
    # 多线叙事：该序列主要服务的线程
    thread_id: str = "thread_main"


@dataclass
class ChapterOutline:
    chapter_number: int
    title: str
    summary: str
    sequence_id: str
    beats: list[Beat]
    emotional_arc: dict[str, str]  # {"start": "...", "end": "..."}
    mandatory_tasks: list[str]     # 必须完成，否则审计不通过
    target_words: int
    # ── 多线叙事扩展字段 ──
    thread_id: str = "thread_main"         # 该章节所属的叙事线程
    pov_character_id: str = ""             # 该章节的视角角色
    physical_time: str = ""                # 物理时间标记（用于时间轴同步）


@dataclass
class StoryOutline:
    id: str
    title: str
    logline: str                   # 一句话概括：主角+目标+障碍+代价
    genre: str
    sequences: list[SequenceOutline]
    # 全书情感弧线节拍（用于审计大纲偏离）
    emotional_roadmap: list[dict[str, str]]  # [{"chapter": "1", "target_emotion": "..."}]


# ── 场景卡片 ──────────────────────────────────────────────────────────────────

@dataclass
class SceneCard:
    id: str
    chapter_number: int
    heading: str                    # 内部标题，不出现在正文
    location: str
    characters: list[str]           # 角色 ID 列表
    dramatic_function: DramaticFunction
    scene_goal: str                 # 这个场景结束时世界发生了什么变化
    beats: list[Beat]
    conflict_core: str              # 冲突核心
    end_state: Literal["better", "worse", "twist"]
    # ── 多线叙事扩展字段 ──
    pov_character_id: str = ""             # 该场景的视角角色
    thread_id: str = ""                    # 所属线程
    parallel_group: str | None = None      # 并发组 ID（同时发生的场景）
