"""
多线叙事核心逻辑单元测试

覆盖范围：
- WorldState：dormant_threads / get_active_threads / thread_chapter_map / get_thread
- StateManager：create_thread / delete_thread / add_timeline_event / get_cross_thread_causal_links
- Pipeline 辅助方法：_build_thread_context / _build_cross_thread_audit_context / _record_timeline_events
- NarrativeThread / TimelineEvent 数据结构
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from unittest.mock import MagicMock

from core.types.narrative import (
    NarrativeThread, TimelineEvent, ThreadType,
)
from core.types.state import (
    WorldState, BookConfig, CausalLink,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def _make_thread(
    tid: str = "thread_main",
    name: str = "主角线",
    thread_type: ThreadType = ThreadType.MAIN,
    pov: str = "char_a",
    last_active: int = 5,
    status: str = "active",
    weight: float = 1.0,
    hook_score: int = 80,
    end_hook: str = "",
    goal: str = "",
) -> NarrativeThread:
    return NarrativeThread(
        id=tid,
        name=name,
        type=thread_type,
        pov_character_id=pov,
        last_active_chapter=last_active,
        status=status,
        weight=weight,
        hook_score=hook_score,
        end_hook=end_hook,
        goal=goal,
    )


def _make_timeline(
    thread_id: str,
    chapter: int,
    char_id: str = "char_a",
    loc_id: str = "loc_1",
    action: str = "移动到 loc_1",
    time_order: float = 1.0,
) -> TimelineEvent:
    return TimelineEvent(
        id=f"te_{thread_id}_ch{chapter}",
        chapter=chapter,
        time_order=time_order,
        character_id=char_id,
        location_id=loc_id,
        action=action,
        thread_id=thread_id,
    )


def _make_world_state(
    threads: list[NarrativeThread] | None = None,
    timeline: list[TimelineEvent] | None = None,
    causal_chain: list[CausalLink] | None = None,
    current_chapter: int = 10,
) -> WorldState:
    return WorldState(
        book_id="test_book",
        current_chapter=current_chapter,
        threads=threads or [],
        timeline=timeline or [],
        causal_chain=causal_chain or [],
    )


def _make_causal_link(
    lid: str = "cl_1",
    chapter: int = 3,
    thread_id: str = "thread_main",
    source_thread_id: str = "",
) -> CausalLink:
    return CausalLink(
        id=lid,
        chapter=chapter,
        cause="某事件",
        event="结果事件",
        consequence="后果",
        thread_id=thread_id,
        source_thread_id=source_thread_id,
    )


@pytest.fixture
def tmp_project(tmp_path):
    """创建临时项目目录，返回 (tmp_path, StateManager)"""
    from core.state import StateManager
    book_id = "test_book"
    sm = StateManager(tmp_path, book_id)
    config = BookConfig(
        id=book_id,
        title="测试书",
        genre="玄幻",
        target_words_per_chapter=3000,
        target_chapters=50,
        protagonist_id="char_a",
    )
    sm.init(config)
    return tmp_path, sm


# ═══════════════════════════════════════════════════════════════════════════════
# WorldState 辅助方法测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorldStateGetThread:
    """get_thread 方法"""

    def test_existing_thread(self):
        ws = _make_world_state(threads=[_make_thread("thread_main")])
        t = ws.get_thread("thread_main")
        assert t is not None
        assert t.name == "主角线"

    def test_nonexistent_thread(self):
        ws = _make_world_state(threads=[_make_thread("thread_main")])
        assert ws.get_thread("thread_sub") is None

    def test_empty_threads(self):
        ws = _make_world_state()
        assert ws.get_thread("thread_main") is None


class TestWorldStateGetActiveThreads:
    """get_active_threads 方法"""

    def test_filters_active_only(self):
        ws = _make_world_state(threads=[
            _make_thread("thread_main", status="active"),
            _make_thread("thread_dormant", status="dormant"),
            _make_thread("thread_resolved", status="resolved"),
        ])
        active = ws.get_active_threads()
        assert len(active) == 1
        assert active[0].id == "thread_main"

    def test_all_active(self):
        ws = _make_world_state(threads=[
            _make_thread("thread_main", status="active"),
            _make_thread("thread_sub", status="active", name="支线"),
        ])
        assert len(ws.get_active_threads()) == 2

    def test_empty_threads(self):
        ws = _make_world_state()
        assert ws.get_active_threads() == []


class TestWorldStateDormantThreads:
    """dormant_threads 掉线预警"""

    def test_no_dormant(self):
        ws = _make_world_state(
            threads=[_make_thread("thread_main", last_active=10)],
            current_chapter=10,
        )
        assert ws.dormant_threads(10, threshold=5) == []

    def test_just_at_threshold(self):
        """恰好在阈值线上不算掉线（gap >= threshold 才报警）"""
        ws = _make_world_state(
            threads=[_make_thread("thread_sub", last_active=5)],
            current_chapter=10,
        )
        # gap = 10 - 5 = 5 >= 5 → 报警
        dormant = ws.dormant_threads(10, threshold=5)
        assert len(dormant) == 1
        assert dormant[0].id == "thread_sub"

    def test_below_threshold(self):
        ws = _make_world_state(
            threads=[_make_thread("thread_sub", last_active=6)],
            current_chapter=10,
        )
        # gap = 10 - 6 = 4 < 5 → 不报警
        assert ws.dormant_threads(10, threshold=5) == []

    def test_custom_threshold(self):
        ws = _make_world_state(
            threads=[_make_thread("thread_sub", last_active=7)],
            current_chapter=10,
        )
        # threshold=3: gap=3 >= 3 → 报警
        assert len(ws.dormant_threads(10, threshold=3)) == 1
        # threshold=4: gap=3 < 4 → 不报警
        assert ws.dormant_threads(10, threshold=4) == []

    def test_dormant_excludes_non_active(self):
        """休眠和已结束的线程不参与掉线预警"""
        ws = _make_world_state(
            threads=[
                _make_thread("thread_resolved", last_active=0, status="resolved"),
                _make_thread("thread_sub", last_active=2, status="active"),
            ],
            current_chapter=10,
        )
        dormant = ws.dormant_threads(10, threshold=5)
        ids = [t.id for t in dormant]
        assert "thread_resolved" not in ids
        assert "thread_sub" in ids

    def test_multiple_dormant(self):
        ws = _make_world_state(
            threads=[
                _make_thread(tid="thread_a", last_active=2),
                _make_thread(tid="thread_b", last_active=1),
                _make_thread(tid="thread_c", last_active=9),
            ],
            current_chapter=10,
        )
        dormant = ws.dormant_threads(10, threshold=5)
        assert len(dormant) == 2


class TestWorldStateThreadChapterMap:
    """thread_chapter_map 按线程索引已写章节"""

    def test_basic_mapping(self):
        ws = _make_world_state(timeline=[
            _make_timeline("thread_main", 1),
            _make_timeline("thread_main", 2),
            _make_timeline("thread_sub", 3),
        ])
        m = ws.thread_chapter_map()
        assert m == {"thread_main": [1, 2], "thread_sub": [3]}

    def test_deduplicates_chapters(self):
        ws = _make_world_state(timeline=[
            _make_timeline("thread_main", 1),
            _make_timeline("thread_main", 1),
        ])
        m = ws.thread_chapter_map()
        assert m["thread_main"] == [1]

    def test_sorted_output(self):
        ws = _make_world_state(timeline=[
            _make_timeline("thread_main", 5),
            _make_timeline("thread_main", 2),
            _make_timeline("thread_main", 8),
        ])
        m = ws.thread_chapter_map()
        assert m["thread_main"] == [2, 5, 8]

    def test_empty_timeline(self):
        ws = _make_world_state()
        assert ws.thread_chapter_map() == {}


# ═══════════════════════════════════════════════════════════════════════════════
# StateManager 线程管理测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateManagerCreateThread:
    """create_thread 线程创建"""

    def test_create_new_thread(self, tmp_project):
        _, sm = tmp_project
        thread = _make_thread("thread_villain", name="反派线")
        sm.create_thread(thread)

        ws = sm.read_world_state()
        assert len(ws.threads) == 1
        assert ws.threads[0].id == "thread_villain"
        assert ws.threads[0].name == "反派线"

    def test_no_duplicate(self, tmp_project):
        _, sm = tmp_project
        thread = _make_thread("thread_main")
        sm.create_thread(thread)
        sm.create_thread(thread)  # 重复创建

        ws = sm.read_world_state()
        assert len(ws.threads) == 1


class TestStateManagerDeleteThread:
    """delete_thread 线程删除"""

    def test_delete_thread(self, tmp_project):
        _, sm = tmp_project
        sm.create_thread(_make_thread(tid="thread_main"))
        sm.create_thread(_make_thread(tid="thread_sub", name="支线"))

        # 添加时间轴事件
        sm.add_timeline_event(_make_timeline("thread_main", 1))
        sm.add_timeline_event(_make_timeline("thread_sub", 2))
        sm.add_timeline_event(_make_timeline("thread_sub", 3))

        # 删除 thread_sub
        sm.delete_thread("thread_sub")

        ws = sm.read_world_state()
        assert len(ws.threads) == 1
        assert ws.threads[0].id == "thread_main"
        # thread_sub 的时间轴事件也被删除
        assert len(ws.timeline) == 1
        assert ws.timeline[0].thread_id == "thread_main"

    def test_delete_nonexistent(self, tmp_project):
        """删除不存在的线程不会报错"""
        _, sm = tmp_project
        sm.delete_thread("nonexistent")  # 不应抛出

        ws = sm.read_world_state()
        assert ws.threads == []


class TestStateManagerUpdateThread:
    """update_thread 线程更新"""

    def test_update_fields(self, tmp_project):
        _, sm = tmp_project
        sm.create_thread(_make_thread("thread_main"))
        sm.update_thread("thread_main", hook_score=60, status="dormant")

        ws = sm.read_world_state()
        t = ws.get_thread("thread_main")
        assert t.hook_score == 60
        assert t.status == "dormant"

    def test_update_nonexistent(self, tmp_project):
        """更新不存在的线程不会报错，也不会创建"""
        _, sm = tmp_project
        sm.update_thread("nonexistent", hook_score=50)

        ws = sm.read_world_state()
        assert ws.threads == []


class TestStateManagerAddTimelineEvent:
    """add_timeline_event 时间轴事件 + 自动更新 last_active_chapter"""

    def test_add_event(self, tmp_project):
        _, sm = tmp_project
        event = _make_timeline("thread_main", 5)
        sm.add_timeline_event(event)

        ws = sm.read_world_state()
        assert len(ws.timeline) == 1
        assert ws.timeline[0].chapter == 5

    def test_updates_last_active_chapter(self, tmp_project):
        _, sm = tmp_project
        sm.create_thread(_make_thread("thread_main", last_active=0))

        sm.add_timeline_event(_make_timeline("thread_main", 3))
        ws = sm.read_world_state()
        assert ws.get_thread("thread_main").last_active_chapter == 3

        sm.add_timeline_event(_make_timeline("thread_main", 7))
        ws = sm.read_world_state()
        assert ws.get_thread("thread_main").last_active_chapter == 7

    def test_no_backtrack_last_active(self, tmp_project):
        """添加更早章节的事件不会倒退 last_active_chapter"""
        _, sm = tmp_project
        sm.create_thread(_make_thread("thread_main", last_active=10))

        sm.add_timeline_event(_make_timeline("thread_main", 5))
        ws = sm.read_world_state()
        assert ws.get_thread("thread_main").last_active_chapter == 10

    def test_event_without_thread(self, tmp_project):
        """thread_id 为空的事件不影响线程"""
        _, sm = tmp_project
        sm.create_thread(_make_thread("thread_main", last_active=5))

        event = TimelineEvent(
            id="te_orphan", chapter=8, thread_id="",
        )
        sm.add_timeline_event(event)

        ws = sm.read_world_state()
        assert ws.get_thread("thread_main").last_active_chapter == 5


class TestStateManagerGetTimeline:
    """get_thread_timeline / get_character_timeline"""

    def test_thread_timeline(self, tmp_project):
        _, sm = tmp_project
        sm.add_timeline_event(_make_timeline("thread_main", 1))
        sm.add_timeline_event(_make_timeline("thread_sub", 2))
        sm.add_timeline_event(_make_timeline("thread_main", 3))

        events = sm.get_thread_timeline("thread_main")
        assert len(events) == 2

    def test_character_timeline(self, tmp_project):
        _, sm = tmp_project
        sm.add_timeline_event(_make_timeline("thread_main", 1, char_id="char_a"))
        sm.add_timeline_event(_make_timeline("thread_main", 2, char_id="char_b"))

        events = sm.get_character_timeline("char_a")
        assert len(events) == 1
        assert events[0].character_id == "char_a"


class TestStateManagerGetCrossThreadCausalLinks:
    """get_cross_thread_causal_links 跨线程因果链过滤"""

    def test_filters_cross_thread(self, tmp_project):
        _, sm = tmp_project
        sm.add_causal_link(_make_causal_link("cl_1", thread_id="thread_main", source_thread_id=""))
        sm.add_causal_link(_make_causal_link("cl_2", thread_id="thread_sub", source_thread_id="thread_main"))
        sm.add_causal_link(_make_causal_link("cl_3", thread_id="thread_main", source_thread_id="thread_sub"))

        links = sm.get_cross_thread_causal_links()
        assert len(links) == 2
        ids = {l.id for l in links}
        assert "cl_1" not in ids
        assert "cl_2" in ids
        assert "cl_3" in ids

    def test_same_source_and_target_excluded(self, tmp_project):
        """source_thread_id == thread_id 的不算跨线程"""
        _, sm = tmp_project
        sm.add_causal_link(_make_causal_link("cl_same", thread_id="thread_main", source_thread_id="thread_main"))

        links = sm.get_cross_thread_causal_links()
        assert len(links) == 0

    def test_empty_source_excluded(self, tmp_project):
        """source_thread_id 为空的不是跨线程"""
        _, sm = tmp_project
        sm.add_causal_link(_make_causal_link("cl_empty", thread_id="thread_main", source_thread_id=""))

        links = sm.get_cross_thread_causal_links()
        assert len(links) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline 辅助方法测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineBuildThreadContext:
    """_build_thread_context 跨线程感知上下文"""

    def _make_pipeline(self, sm):
        """创建一个最小化的 Pipeline 实例（仅用于测试辅助方法）"""
        from unittest.mock import MagicMock
        from core.pipeline import WritingPipeline

        sm_mock = sm
        pipeline = WritingPipeline(
            state_manager=sm_mock,
            architect=MagicMock(),
            writer=MagicMock(),
            auditor=MagicMock(),
            reviser=MagicMock(),
            narrative_engine=MagicMock(),
            summary_agent=MagicMock(),
            validator=MagicMock(),
            protagonist=MagicMock(id="char_a", name="主角"),
            all_characters=[],
        )
        return pipeline

    def test_empty_threads(self, tmp_project):
        _, sm = tmp_project
        ws = _make_world_state()
        pipeline = self._make_pipeline(sm)
        ctx = pipeline._build_thread_context(ws, "thread_main", 5)
        assert ctx == ""

    def test_excludes_current_thread(self):
        ws = _make_world_state(threads=[
            _make_thread("thread_main", name="主角线", hook_score=90, end_hook="主角即将爆发"),
            _make_thread("thread_sub", name="支线", hook_score=70, goal="找到线索"),
        ])
        from unittest.mock import MagicMock
        pipeline = MagicMock()

        from core.pipeline import WritingPipeline
        ctx = WritingPipeline._build_thread_context(pipeline, ws, "thread_main", 5)
        assert "支线" in ctx
        assert "主角线" not in ctx

    def test_includes_hook_and_goal(self):
        ws = _make_world_state(threads=[
            _make_thread("thread_main", name="主线"),
            _make_thread("thread_sub", name="支线", hook_score=70, end_hook="重要发现", goal="找到秘籍"),
        ])
        from unittest.mock import MagicMock
        pipeline = MagicMock()

        from core.pipeline import WritingPipeline
        ctx = WritingPipeline._build_thread_context(pipeline, ws, "thread_main", 5)
        assert "重要发现" in ctx
        assert "找到秘籍" in ctx

    def test_no_other_active_threads(self):
        ws = _make_world_state(threads=[
            _make_thread("thread_main", name="主线", status="active"),
            _make_thread("thread_resolved", name="已结束", status="resolved"),
        ])
        from unittest.mock import MagicMock
        pipeline = MagicMock()

        from core.pipeline import WritingPipeline
        # get_active_threads 只返回 active，resolved 被排除
        # 但只有 thread_main 是 active 且被排除 → 空
        ctx = WritingPipeline._build_thread_context(pipeline, ws, "thread_main", 5)
        assert ctx == ""


class TestPipelineBuildCrossThreadAuditContext:
    """_build_cross_thread_audit_context 跨线程审计上下文"""

    def test_includes_other_thread_events(self):
        ws = _make_world_state(
            threads=[
                _make_thread(tid="thread_main", name="主线"),
                _make_thread(tid="thread_sub", name="支线"),
            ],
            timeline=[
                _make_timeline("thread_main", 5, char_id="char_a", action="主线事件"),
                _make_timeline("thread_sub", 3, char_id="char_b", action="支线事件1"),
                _make_timeline("thread_sub", 4, char_id="char_b", action="支线事件2"),
            ],
            current_chapter=5,
        )
        from unittest.mock import MagicMock
        pipeline = MagicMock()

        from core.pipeline import WritingPipeline
        ctx = WritingPipeline._build_cross_thread_audit_context(pipeline, ws, "thread_main", 5)
        assert "支线" in ctx
        assert "主线事件" not in ctx
        assert "支线事件" in ctx

    def test_includes_cross_causal_links(self):
        ws = _make_world_state(
            threads=[
                _make_thread("thread_main", name="主线"),
            ],
            causal_chain=[
                _make_causal_link("cl_1", chapter=3, thread_id="thread_main", source_thread_id="thread_sub"),
            ],
        )
        from unittest.mock import MagicMock
        pipeline = MagicMock()

        from core.pipeline import WritingPipeline
        ctx = WritingPipeline._build_cross_thread_audit_context(pipeline, ws, "thread_main", 5)
        assert "thread_sub" in ctx

    def test_empty_context(self):
        ws = _make_world_state()
        from unittest.mock import MagicMock
        pipeline = MagicMock()

        from core.pipeline import WritingPipeline
        ctx = WritingPipeline._build_cross_thread_audit_context(pipeline, ws, "thread_main", 5)
        assert ctx == ""


class TestPipelineRecordTimelineEvents:
    """_record_timeline_events 时间轴事件记录"""

    @staticmethod
    def _make_real_pipeline(sm):
        """创建一个真实的 Pipeline 实例（仅 sm 是真实的，其他 mock）"""
        from unittest.mock import MagicMock
        from core.pipeline import WritingPipeline

        return WritingPipeline(
            state_manager=sm,
            architect=MagicMock(),
            writer=MagicMock(),
            auditor=MagicMock(),
            reviser=MagicMock(),
            narrative_engine=MagicMock(),
            summary_agent=MagicMock(),
            validator=MagicMock(),
            protagonist=MagicMock(id="char_a", name="主角"),
            all_characters=[],
        )

    def test_records_position_changes(self, tmp_project):
        _, sm = tmp_project
        sm.create_thread(_make_thread(tid="thread_main"))
        ws = sm.read_world_state()

        from core.agents import PostWriteSettlement

        pipeline = self._make_real_pipeline(sm)
        writer_output = MagicMock()
        writer_output.settlement = PostWriteSettlement(
            character_position_changes=[
                {"character_id": "char_a", "location_id": "loc_1"},
                {"character_id": "char_b", "location_id": "loc_2"},
            ],
        )
        blueprint = MagicMock()
        blueprint.core_conflict = ""
        blueprint.pov_character_id = ""

        pipeline._record_timeline_events(5, writer_output, blueprint, "thread_main", ws)

        events = sm.get_thread_timeline("thread_main")
        assert len(events) == 2

    def test_records_emotional_changes_high_intensity(self, tmp_project):
        _, sm = tmp_project
        sm.create_thread(_make_thread(tid="thread_main"))
        ws = sm.read_world_state()

        from core.agents import PostWriteSettlement

        pipeline = self._make_real_pipeline(sm)
        writer_output = MagicMock()
        writer_output.settlement = PostWriteSettlement(
            emotional_changes=[
                {"character_id": "char_a", "emotion": "愤怒", "intensity": 8, "trigger": "被背叛"},
                {"character_id": "char_b", "emotion": "平静", "intensity": 3, "trigger": "日常"},  # 低于7，不记录
            ],
        )
        blueprint = MagicMock()
        blueprint.core_conflict = ""
        blueprint.pov_character_id = ""

        pipeline._record_timeline_events(5, writer_output, blueprint, "thread_main", ws)

        events = sm.get_thread_timeline("thread_main")
        assert len(events) == 1
        assert "愤怒" in events[0].action

    def test_records_info_revealed(self, tmp_project):
        _, sm = tmp_project
        sm.create_thread(_make_thread(tid="thread_main"))
        ws = sm.read_world_state()

        from core.agents import PostWriteSettlement

        pipeline = self._make_real_pipeline(sm)
        writer_output = MagicMock()
        writer_output.settlement = PostWriteSettlement(
            info_revealed=[
                {"character_id": "char_a", "info_key": "秘籍位置", "content": "在山洞里"},
            ],
        )
        blueprint = MagicMock()
        blueprint.core_conflict = ""
        blueprint.pov_character_id = ""

        pipeline._record_timeline_events(5, writer_output, blueprint, "thread_main", ws)

        events = sm.get_thread_timeline("thread_main")
        assert len(events) == 1
        assert "秘籍位置" in events[0].action

    def test_records_core_conflict(self, tmp_project):
        _, sm = tmp_project
        sm.create_thread(_make_thread(tid="thread_main"))
        ws = sm.read_world_state()

        from core.agents import PostWriteSettlement

        pipeline = self._make_real_pipeline(sm)
        writer_output = MagicMock()
        writer_output.settlement = PostWriteSettlement()
        blueprint = MagicMock()
        blueprint.core_conflict = "主角被师父背叛，陷入绝境"
        blueprint.pov_character_id = "char_a"

        pipeline._record_timeline_events(5, writer_output, blueprint, "thread_main", ws)

        events = sm.get_thread_timeline("thread_main")
        assert len(events) == 1
        assert "背叛" in events[0].action

    def test_time_order_increments(self, tmp_project):
        """time_order 应递增（chapter + 0.1, 0.2, ...）"""
        _, sm = tmp_project
        sm.create_thread(_make_thread(tid="thread_main"))
        ws = sm.read_world_state()

        from core.agents import PostWriteSettlement

        pipeline = self._make_real_pipeline(sm)
        writer_output = MagicMock()
        writer_output.settlement = PostWriteSettlement(
            character_position_changes=[
                {"character_id": "char_a", "location_id": "loc_1"},
            ],
            emotional_changes=[
                {"character_id": "char_a", "emotion": "愤怒", "intensity": 9, "trigger": "被背叛"},
            ],
        )
        blueprint = MagicMock()
        blueprint.core_conflict = "核心冲突"
        blueprint.pov_character_id = ""

        pipeline._record_timeline_events(5, writer_output, blueprint, "thread_main", ws)

        events = sm.get_thread_timeline("thread_main")
        orders = [e.time_order for e in events]
        assert orders == sorted(orders), "time_order 应递增"
        assert all(orders[i] < orders[i + 1] for i in range(len(orders) - 1))


# ═══════════════════════════════════════════════════════════════════════════════
# NarrativeThread / TimelineEvent 数据结构测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestNarrativeThread:
    """NarrativeThread 数据类"""

    def test_defaults(self):
        t = NarrativeThread(id="thread_1", name="测试线程")
        assert t.type == ThreadType.MAIN
        assert t.pov_character_id == ""
        assert t.weight == 1.0
        assert t.status == "active"
        assert t.hook_score == 80
        assert t.character_ids == []
        assert t.end_hook == ""

    def test_subplot(self):
        t = NarrativeThread(
            id="thread_sub", name="支线",
            type=ThreadType.SUBPLOT,
            weight=0.5,
            pov_character_id="char_b",
        )
        assert t.type == ThreadType.SUBPLOT
        assert t.weight == 0.5
        assert t.pov_character_id == "char_b"

    def test_all_types(self):
        for tt in ThreadType:
            t = NarrativeThread(id=f"t_{tt.value}", name=tt.value, type=tt)
            assert t.type == tt


class TestTimelineEvent:
    """TimelineEvent 数据类"""

    def test_defaults(self):
        e = TimelineEvent(id="te_1", chapter=3)
        assert e.physical_time == ""
        assert e.time_order == 0.0
        assert e.character_id == ""
        assert e.action == ""
        assert e.thread_id == ""

    def test_full_event(self):
        e = TimelineEvent(
            id="te_1",
            chapter=3,
            physical_time="第一天清晨",
            time_order=3.1,
            character_id="char_a",
            location_id="loc_1",
            action="发现秘籍",
            thread_id="thread_main",
            affected_threads=["thread_sub"],
            affected_characters=["char_b"],
        )
        assert e.chapter == 3
        assert len(e.affected_threads) == 1
        assert e.affected_characters[0] == "char_b"


# ═══════════════════════════════════════════════════════════════════════════════
# CausalLink 跨线程测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestCausalLinkCrossThread:
    """跨线程因果链逻辑"""

    def test_same_thread_is_not_cross(self):
        cl = _make_causal_link(thread_id="thread_main", source_thread_id="thread_main")
        assert cl.source_thread_id == cl.thread_id

    def test_cross_thread_link(self):
        cl = _make_causal_link(thread_id="thread_sub", source_thread_id="thread_main")
        assert cl.source_thread_id != cl.thread_id

    def test_empty_source_is_internal(self):
        cl = _make_causal_link(thread_id="thread_main", source_thread_id="")
        assert cl.source_thread_id == ""


# ═══════════════════════════════════════════════════════════════════════════════
# WorldState 序列化/反序列化一致性
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorldStateSerialization:
    """WorldState 通过 StateManager 存取后的完整性"""

    def test_thread_persistence(self, tmp_project):
        _, sm = tmp_project
        sm.create_thread(_make_thread(tid="thread_main"))
        sm.create_thread(_make_thread(tid="thread_sub", name="支线",
                                       thread_type=ThreadType.SUBPLOT, weight=0.6))

        ws = sm.read_world_state()
        assert len(ws.threads) == 2
        sub = ws.get_thread("thread_sub")
        assert sub is not None
        assert sub.weight == 0.6
        assert sub.type == ThreadType.SUBPLOT

    def test_timeline_persistence(self, tmp_project):
        _, sm = tmp_project
        sm.add_timeline_event(_make_timeline("thread_main", 1, action="事件1"))
        sm.add_timeline_event(_make_timeline("thread_sub", 2, action="事件2"))

        ws = sm.read_world_state()
        assert len(ws.timeline) == 2
        assert ws.timeline[0].action == "事件1"

    def test_causal_chain_with_thread_fields(self, tmp_project):
        _, sm = tmp_project
        cl = CausalLink(
            id="cl_cross",
            chapter=5,
            cause="主线事件",
            event="支线受影响",
            consequence="支线角色做出反应",
            thread_id="thread_sub",
            source_thread_id="thread_main",
        )
        sm.add_causal_link(cl)

        ws = sm.read_world_state()
        assert len(ws.causal_chain) == 1
        assert ws.causal_chain[0].source_thread_id == "thread_main"
