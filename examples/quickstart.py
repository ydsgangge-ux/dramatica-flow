"""
快速开始示例
展示如何用 Python API 驱动完整写作管线
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

from core.llm import LLMConfig, DeepSeekProvider
from core.types.narrative import (
    Character, CharacterNeed, CharacterWorldview, Obstacle,
    ObstacleType, Location, StoryEvent, DramaticFunction,
)
from core.types.state import BookConfig
from core.state import StateManager
from core.narrative import NarrativeEngine
from core.agents import ArchitectAgent, WriterAgent, AuditorAgent, ReviserAgent, SummaryAgent
from core.validators import PostWriteValidator
from core.pipeline import WritingPipeline


def main():
    # ── 1. 配置 LLM Provider ─────────────────────────────────────────────────
    config = LLMConfig(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
    )
    auditor_config = LLMConfig(**{**config.__dict__, "temperature": 0.0})

    llm     = DeepSeekProvider(config)
    llm_t0  = DeepSeekProvider(auditor_config)

    # ── 2. 定义世界 ───────────────────────────────────────────────────────────
    locations = {
        "loc_arena": Location(
            id="loc_arena",
            name="林家演武场",
            description="家族比试之地，四面石台，观众台层层叠叠",
            connections=["loc_main_hall"],
            dramatic_potential="公开羞辱与逆袭的天然舞台",
        ),
        "loc_mountain": Location(
            id="loc_mountain",
            name="青峰山",
            description="妖兽出没之地，灵气浓郁，险象环生",
            connections=["loc_arena"],
            dramatic_potential="孤立修炼、生死考验",
        ),
    }

    # ── 3. 定义角色 ───────────────────────────────────────────────────────────
    protagonist = Character(
        id="lin_chen",
        name="林尘",
        need=CharacterNeed(
            external="逆天改命，登顶巅峰，让所有瞧不起他的人跪地认错",
            internal="证明自己的存在有价值，不是废物",
        ),
        obstacles=[
            Obstacle(
                type=ObstacleType.ANTAGONIST,
                description="未婚妻家族（慕家）——权贵阶层对底层的压迫",
                mechanism="慕家控制了林尘获得资源和机遇的渠道",
            ),
            Obstacle(
                type=ObstacleType.SELF,
                description="被封印的灵根，修炼速度极慢",
                mechanism="客观实力差距让外部目标看似不可能",
            ),
        ],
        worldview=CharacterWorldview(power="seeks", trust="suspicious", coping="fight"),
        arc="positive",
        profile="十七岁少年，外表平凡，眼神有一股不服输的倔劲。说话简短有力，不废话。",
        behavior_lock=[
            "关键时刻不圣母心软",
            "对挑衅者不忍气吞声",
            "不做无意义的自我怀疑独白",
        ],
    )

    all_characters = [protagonist]

    # ── 4. 定义种子事件 ───────────────────────────────────────────────────────
    seed_event = StoryEvent(
        id="event_divorce",
        name="退婚羞辱",
        description="未婚妻慕雪当众退婚，声称林尘是废物，"
                    "不配与慕家联姻，并当场与他人定亲",
        preconditions=[],
        effects=["林尘公开蒙羞", "林尘立下三年之约", "林尘决心变强"],
        triggers=["event_mountain_training"],
        suggested_act=1,
        suggested_function=DramaticFunction.INCITING,
    )

    # ── 5. 初始化状态管理器 ───────────────────────────────────────────────────
    book_config = BookConfig(
        id="tiantun_madi",
        title="吞天魔帝",
        genre="玄幻",
        target_words_per_chapter=4000,
        target_chapters=90,
        protagonist_id="lin_chen",
        custom_forbidden_words=["瞳孔骤缩", "不可置信"],
    )

    sm = StateManager(project_root=".", book_id="tiantun_madi")
    sm.init(book_config)

    # ── 6. 生成故事大纲 ───────────────────────────────────────────────────────
    engine = NarrativeEngine(llm)

    print("正在生成故事大纲...")
    world_context = """
    玄幻世界，修炼体系：炼体、聚气、元婴、化神四大境界。
    林家是中等世家，地位不稳。慕家是上等世家，财雄势大。
    灵根品质决定修炼速度，林尘的灵根被认为是最劣等的废灵根。
    """
    outline = engine.generate_outline(
        seed_event=seed_event,
        protagonist=protagonist,
        world_context=world_context,
        target_chapters=90,
        genre="玄幻",
    )
    print(f"大纲生成完成：《{outline.title}》")
    print(f"Logline：{outline.logline}")
    print(f"共 {len(outline.sequences)} 个序列")

    # ── 7. 生成第一个序列的章纲 ──────────────────────────────────────────────
    print("\n正在生成第一序列章纲...")
    first_sequence = outline.sequences[0]
    chapter_outlines = engine.generate_chapter_outlines(
        sequence=first_sequence,
        protagonist=protagonist,
        world_context=world_context,
        chapter_start=1,
        words_per_chapter=4000,
    )
    print(f"章纲生成完成：{len(chapter_outlines)} 章")

    # ── 8. 构建管线 ───────────────────────────────────────────────────────────
    pipeline = WritingPipeline(
        state_manager=sm,
        architect=ArchitectAgent(llm),
        writer=WriterAgent(llm, genre="玄幻"),
        auditor=AuditorAgent(llm_t0),
        reviser=ReviserAgent(llm),
        narrative_engine=engine,
        summary_agent=SummaryAgent(llm),
        validator=PostWriteValidator(custom_forbidden_words=book_config.custom_forbidden_words),
        protagonist=protagonist,
        all_characters=all_characters,
    )

    # ── 9. 写第一章 ───────────────────────────────────────────────────────────
    print("\n开始写第一章...")
    result = pipeline.run(chapter_outlines[0])

    print(f"\n{'='*50}")
    print(f"第 {result.chapter_number} 章写作完成")
    print(f"字数：{len(result.content)}")
    print(f"验证：{'通过' if result.validation_passed else '未通过'}")
    print(f"审计：{'通过' if result.audit_report.passed else f'未通过（Critical: {result.audit_report.critical_count}）'}")
    print(f"修订轮次：{result.revision_rounds}")
    print(f"提取因果链：{result.causal_links} 条")
    print(f"\n正文预览（前200字）：")
    print(result.content[:200] + "...")


if __name__ == "__main__":
    main()
