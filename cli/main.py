"""
dramatica-flow CLI
命令：init / book / setup / write / audit / revise / status / export / doctor
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

load_dotenv()

# Windows 下强制 UTF-8，避免 GBK 编码报错
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(
    name="df",
    help="Dramatica-Flow — 叙事优先的 AI 写作系统",
    add_completion=False,
)
setup_app = typer.Typer(help="配置角色、世界、事件")
app.add_typer(setup_app, name="setup")
threads_app = typer.Typer(help="叙事线程管理（多线叙事）")
app.add_typer(threads_app, name="threads")

console = Console()


# ── LLM 工厂 ──────────────────────────────────────────────────────────────────

def _require_key() -> str:
    provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    if provider == "ollama":
        return "ollama"
    env_prefix = provider.upper() + "_"
    key = os.environ.get(f"{env_prefix}API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key or key.startswith("sk-xxx"):
        console.print(f"[red]✗ 请先在 .env 中配置 {provider} 的 API Key[/red]")
        raise typer.Exit(1)
    return key


def _llm(temperature: float | None = None, model_env: str = "DEEPSEEK_MODEL"):
    from core.llm import create_provider, LLMConfig
    provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()

    if provider == "ollama":
        return create_provider(None, provider_type="ollama")

    env_prefix = provider.upper() + "_"
    cfg = LLMConfig(
        api_key=_require_key(),
        base_url=os.environ.get(f"{env_prefix}BASE_URL",
                                 os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")),
        model=os.environ.get(f"{env_prefix}MODEL",
                              os.environ.get(model_env, os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))),
        temperature=temperature if temperature is not None
                    else float(os.environ.get("DEFAULT_TEMPERATURE", "0.7")),
    )
    return create_provider(cfg, provider_type=provider)


# ── df init ───────────────────────────────────────────────────────────────────

@app.command()
def init(
    name: str = typer.Argument(..., help="项目名称"),
    path: str = typer.Option(".", "--path", "-p", help="创建位置"),
):
    """初始化新项目目录"""
    import shutil
    project_dir = Path(path) / name
    if project_dir.exists():
        console.print(f"[red]✗ 目录已存在：{project_dir}[/red]")
        raise typer.Exit(1)
    (project_dir / "books").mkdir(parents=True)
    env_src = Path(__file__).parent.parent / ".env.example"
    if env_src.exists():
        shutil.copy(env_src, project_dir / ".env")
    console.print(Panel(
        f"[green]✓ 项目已初始化：[bold]{project_dir}[/bold][/green]\n\n"
        "下一步：\n"
        "  1. 编辑 [bold].env[/bold] → 填入 DEEPSEEK_API_KEY\n"
        "  2. [bold]df book --title 书名 --genre 玄幻[/bold]\n"
        "  3. [bold]df setup init-templates <book_id>[/bold]",
        title="dramatica-flow",
        border_style="green",
    ))


# ── df book ───────────────────────────────────────────────────────────────────

@app.command()
def book(
    title: str    = typer.Option(..., "--title",   "-t", help="书名"),
    genre: str    = typer.Option(..., "--genre",   "-g", help="题材"),
    chapters: int = typer.Option(90,   "--chapters", "-c", help="目标总章数"),
    words: int    = typer.Option(4000, "--words",   "-w", help="每章目标字数"),
    project: str  = typer.Option(".",  "--project", "-p", help="项目根目录"),
    forbidden: str = typer.Option("", "--forbidden", help="自定义禁止词，逗号分隔"),
):
    """创建新书"""
    from core.state import StateManager
    from core.types.state import BookConfig
    from datetime import datetime, timezone

    book_id = title.replace(" ", "_")[:20]
    config = BookConfig(
        id=book_id,
        title=title,
        genre=genre,
        target_words_per_chapter=words,
        target_chapters=chapters,
        protagonist_id="",
        status="planning",
        created_at=datetime.now(timezone.utc).isoformat(),
        custom_forbidden_words=[w.strip() for w in forbidden.split(",") if w.strip()],
    )
    sm = StateManager(project, book_id)
    sm.init(config)
    console.print(Panel(
        f"[green]✓ 书籍「[bold]{title}[/bold]」已创建[/green]\n\n"
        f"Book ID：[cyan]{book_id}[/cyan]\n"
        f"目标：{chapters} 章 × {words} 字/章\n\n"
        f"下一步：  [bold]df setup init-templates {book_id}[/bold]",
        title="新书创建", border_style="cyan",
    ))


# ── df setup ─────────────────────────────────────────────────────────────────

@setup_app.command("init-templates")
def setup_init(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """复制 JSON 配置模板到书籍目录"""
    from core.setup import SetupLoader
    console.print(f"初始化配置模板 → books/{book_id}/setup/\n")
    SetupLoader(project, book_id).init_templates()


@setup_app.command("load")
def setup_load(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """加载 JSON 配置 → 更新状态 + 生成 story_bible.md"""
    from core.setup import SetupLoader
    console.print(f"[bold]加载配置：{book_id}[/bold]\n")
    try:
        state = SetupLoader(project, book_id).load_all()
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)

    protagonist = state.characters.get(state.config.protagonist_id)
    pname = protagonist.name if protagonist else "未设置"
    console.print(Panel(
        f"[green]✓ 加载完成[/green]\n\n"
        f"主角：[cyan]{pname}[/cyan]\n"
        f"角色 {len(state.characters)} / 地点 {len(state.locations)} / "
        f"势力 {len(state.factions)} / 事件 {len(state.seed_events)}\n\n"
        f"下一步：  [bold]df write {book_id}[/bold]",
        title="配置加载", border_style="green",
    ))


@setup_app.command("show")
def setup_show(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """查看已加载的配置摘要"""
    from core.setup import SetupLoader
    try:
        state = SetupLoader.restore(project, book_id)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)

    t = Table(title="角色", box=box.SIMPLE)
    t.add_column("ID", style="dim"); t.add_column("姓名", style="cyan bold")
    t.add_column("外部目标"); t.add_column("弧线", style="magenta")
    for c in state.characters.values():
        mark = "★ " if c.id == state.config.protagonist_id else ""
        t.add_row(c.id, mark + c.name, c.need.external[:35], c.arc)
    console.print(t)

    t2 = Table(title="事件", box=box.SIMPLE)
    t2.add_column("ID", style="dim"); t2.add_column("名称", style="yellow")
    t2.add_column("幕", style="magenta"); t2.add_column("功能")
    for e in state.seed_events:
        t2.add_row(
            e.id, e.name, str(e.suggested_act or "-"),
            e.suggested_function.value if e.suggested_function else "-",
        )
    console.print(t2)


# ── df write ──────────────────────────────────────────────────────────────────

@app.command()
def write(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    count: int   = typer.Option(1,   "--count", "-n", help="连续写几章"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """写下一章（完整管线）"""
    from core.setup import SetupLoader
    from core.state import StateManager
    from core.narrative import NarrativeEngine, ChapterOutlineSchema
    from core.agents import ArchitectAgent, WriterAgent, AuditorAgent, ReviserAgent, SummaryAgent
    from core.validators import PostWriteValidator
    from core.pipeline import WritingPipeline

    try:
        state = SetupLoader.restore(project, book_id)
    except FileNotFoundError as e:
        console.print(f"[red]✗ {e}[/red]"); raise typer.Exit(1)

    sm = StateManager(project, book_id)
    # protagonist fallback: config id → role match → first character
    _pid = state.config.protagonist_id
    if _pid in state.characters:
        protagonist = state.characters[_pid]
    else:
        for c in state.characters.values():
            if getattr(c, "role", "") in ("protagonist", "主角"):
                protagonist = c; break
        else:
            protagonist = next(iter(state.characters.values()))
    engine = NarrativeEngine(_llm())

    # 大纲缓存
    outline_path          = sm.state_dir / "outline.json"
    chapter_outlines_path = sm.state_dir / "chapter_outlines.json"

    if not outline_path.exists():
        console.print("[bold]生成故事大纲...[/bold]")
        world_ctx = sm.read_truth("story_bible")
        outline = engine.generate_outline(
            seed_event=state.seed_events[0],
            protagonist=protagonist,
            world_context=world_ctx,
            target_chapters=state.config.target_chapters,
            genre=state.config.genre,
        )
        outline_path.write_text(outline.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"  ✓ 大纲：《{outline.title}》")
    else:
        from core.narrative import StoryOutlineSchema
        outline = StoryOutlineSchema.model_validate_json(outline_path.read_text(encoding="utf-8"))
        console.print(f"[dim]加载大纲：《{outline.title}》[/dim]")

    if not chapter_outlines_path.exists():
        console.print("[bold]生成章纲...[/bold]")
        all_outlines = []
        ch_start = 1
        for seq in outline.sequences:
            cos = engine.generate_chapter_outlines(
                sequence=seq, protagonist=protagonist,
                world_context=sm.read_truth("story_bible"),
                chapter_start=ch_start,
                words_per_chapter=state.config.target_words_per_chapter,
            )
            all_outlines.extend(cos)
            ch_start += len(cos)
        chapter_outlines_path.write_text(
            json.dumps([o.model_dump() for o in all_outlines], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"  ✓ 章纲：{len(all_outlines)} 章")
    else:
        raw = json.loads(chapter_outlines_path.read_text(encoding="utf-8"))
        # 修复 AI 输出的非法 dramatic_function 和缺失的 beat id
        from core.llm import _fix_df
        for r in raw:
            if r.get("dramatic_function"):
                r["dramatic_function"] = _fix_df(r["dramatic_function"])
            for bi, beat in enumerate(r.get("beats", [])):
                if not beat.get("id"):
                    beat["id"] = f"beat_{r.get('chapter_number', bi)}_{bi+1}"
                if beat.get("dramatic_function"):
                    beat["dramatic_function"] = _fix_df(beat["dramatic_function"])
        all_outlines = [ChapterOutlineSchema.model_validate(r) for r in raw]
        console.print(f"[dim]加载章纲：{len(all_outlines)} 章[/dim]")

    pipeline = WritingPipeline(
        state_manager=sm,
        architect=ArchitectAgent(_llm()),
        writer=WriterAgent(_llm(), style_guide=state.config.style_guide, genre=state.config.genre),
        auditor=AuditorAgent(_llm(temperature=0.0, model_env="AUDITOR_MODEL")),
        reviser=ReviserAgent(_llm()),
        narrative_engine=engine,
        summary_agent=SummaryAgent(_llm()),
        validator=PostWriteValidator(state.config.custom_forbidden_words),
        protagonist=protagonist,
        all_characters=list(state.characters.values()),
    )

    ws = sm.read_world_state()
    next_ch = ws.current_chapter + 1

    for i in range(count):
        ch_num = next_ch + i
        if ch_num > len(all_outlines):
            console.print(f"[yellow]全部 {len(all_outlines)} 章已写完[/yellow]"); break
        co = all_outlines[ch_num - 1]
        console.print(f"\n[bold]第 {ch_num} 章《{co.title}》[/bold]")
        result = pipeline.run(co)
        ok = "[green]✓[/green]" if result.audit_report.passed else "[yellow]⚠[/yellow]"
        console.print(
            f"  {ok} 审计{'通过' if result.audit_report.passed else '未通过'}"
            f"  修订 {result.revision_rounds} 轮"
            f"  {len(result.content)} 字"
            f"  因果链 {result.causal_links} 条"
        )


# ── df audit ──────────────────────────────────────────────────────────────────

@app.command()
def audit(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    chapter: int = typer.Argument(..., help="章节号"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """手动审计指定章节"""
    from core.state import StateManager
    from core.agents import AuditorAgent, ArchitectBlueprint, PreWriteChecklist, PostWriteSettlement
    from core.types.state import TruthFileKey

    sm = StateManager(project, book_id)
    content = sm.read_final(chapter) or sm.read_draft(chapter)
    if not content:
        console.print(f"[red]✗ 第 {chapter} 章不存在[/red]"); raise typer.Exit(1)

    console.print(f"[bold]审计第 {chapter} 章...[/bold]")
    blueprint = ArchitectBlueprint(
        core_conflict="", hooks_to_advance=[], hooks_to_plant=[],
        emotional_journey={}, chapter_end_hook="", pace_notes="",
        pre_write_checklist=PreWriteChecklist([], [], [], [], ""),
    )
    truth_ctx = sm.read_truth_bundle([
        TruthFileKey.CURRENT_STATE, TruthFileKey.PENDING_HOOKS,
        TruthFileKey.CHARACTER_MATRIX, TruthFileKey.CAUSAL_CHAIN,
    ])
    report = AuditorAgent(_llm(temperature=0.0, model_env="AUDITOR_MODEL")).audit_chapter(
        content, chapter, blueprint, truth_ctx,
        PostWriteSettlement([], [], [], [], []),
    )

    icon = "[green]✓ 通过[/green]" if report.passed else "[red]✗ 未通过[/red]"
    console.print(f"\n{icon}  Critical: [red]{report.critical_count}[/red]  Warning: [yellow]{report.warning_count}[/yellow]")

    if report.issues:
        t = Table(box=box.SIMPLE)
        t.add_column("维度", style="cyan", width=22)
        t.add_column("严重度", width=10)
        t.add_column("描述")
        t.add_column("建议", style="dim")
        for issue in report.issues:
            sc = "red" if issue.severity == "critical" else "yellow"
            t.add_row(issue.dimension, f"[{sc}]{issue.severity}[/{sc}]",
                      issue.description, issue.suggestion or "")
        console.print(t)
    console.print(f"\n[dim]{report.overall_note}[/dim]")


# ── df revise ─────────────────────────────────────────────────────────────────

@app.command()
def revise(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    chapter: int = typer.Argument(..., help="章节号"),
    mode: str    = typer.Option("spot-fix", "--mode", "-m",
                                help="spot-fix / rewrite-section / polish"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """手动修订指定章节"""
    from core.state import StateManager
    from core.agents import AuditorAgent, ReviserAgent, ArchitectBlueprint, PreWriteChecklist, PostWriteSettlement
    from core.types.state import TruthFileKey

    sm = StateManager(project, book_id)
    content = sm.read_final(chapter) or sm.read_draft(chapter)
    if not content:
        console.print(f"[red]✗ 第 {chapter} 章不存在[/red]"); raise typer.Exit(1)

    blueprint = ArchitectBlueprint(
        core_conflict="", hooks_to_advance=[], hooks_to_plant=[],
        emotional_journey={}, chapter_end_hook="", pace_notes="",
        pre_write_checklist=PreWriteChecklist([], [], [], [], ""),
    )
    truth_ctx = sm.read_truth_bundle([TruthFileKey.CURRENT_STATE, TruthFileKey.PENDING_HOOKS])
    report = AuditorAgent(_llm(temperature=0.0, model_env="AUDITOR_MODEL")).audit_chapter(
        content, chapter, blueprint, truth_ctx, PostWriteSettlement([], [], [], [], []),
    )

    if report.passed and mode == "spot-fix":
        console.print("[green]✓ 审计通过，无需修订[/green]"); return

    console.print(f"发现 {report.critical_count} critical，修订模式：{mode}")
    result = ReviserAgent(_llm()).revise(content, report.issues, mode=mode)  # type: ignore
    sm.save_final(chapter, result.content)
    console.print(f"[green]✓ 修订完成，改动 {len(result.change_log)} 处[/green]")


# ── df status ─────────────────────────────────────────────────────────────────

@app.command()
def status(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """查看书籍状态"""
    from core.state import StateManager
    from core.types.state import TruthFileKey

    sm = StateManager(project, book_id)
    try:
        config = sm.read_config()
        ws = sm.read_world_state()
    except FileNotFoundError:
        console.print(f"[red]✗ 书籍不存在：{book_id}[/red]"); raise typer.Exit(1)

    drafts = list(sm.chapter_dir.glob("*_draft.md"))
    finals = list(sm.chapter_dir.glob("*_final.md"))
    snaps  = list(sm.snapshot_dir.glob("*.json"))
    hooks_md   = sm.read_truth(TruthFileKey.PENDING_HOOKS)
    open_hooks = hooks_md.count("| open |")

    # 支线掉线预警
    dormant = ws.dormant_threads(ws.current_chapter, threshold=5)
    dormant_lines = ""
    if dormant:
        dormant_lines = "\n[yellow]支线掉线预警：[/yellow]\n"
        for t in dormant:
            gap = ws.current_chapter - t.last_active_chapter
            dormant_lines += f"  · [yellow]{t.name}（{t.id}）[/yellow]：已 {gap} 章未活跃\n"

    thread_info = ""
    if ws.threads:
        thread_info = f"\n叙事线程：[cyan]{len(ws.threads)}[/cyan] 条（活跃 {len(ws.get_active_threads())}）"
        thread_info += dormant_lines

    console.print(Panel(
        f"[bold cyan]{config['title']}[/bold cyan]  [dim]{book_id}[/dim]\n\n"
        f"题材：{config['genre']}  状态：{config['status']}\n"
        f"目标：{config['target_chapters']} 章 × {config['target_words_per_chapter']} 字/章\n\n"
        f"进度：第 [bold]{ws.current_chapter}[/bold] / {config['target_chapters']} 章\n"
        f"草稿 {len(drafts)} 章  最终稿 {len(finals)} 章  快照 {len(snaps)} 个\n"
        f"未闭合伏笔：[yellow]{open_hooks}[/yellow] 条"
        f"{thread_info}\n\n"
        f"[dim]{sm.state_dir}[/dim]",
        title="书籍状态", border_style="cyan",
    ))


# ── df threads ────────────────────────────────────────────────────────────────

@threads_app.command("list")
def threads_list(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """查看叙事线程状态（多线叙事）"""
    from core.state import StateManager

    sm = StateManager(project, book_id)
    try:
        ws = sm.read_world_state()
    except FileNotFoundError:
        console.print(f"[red]✗ 书籍不存在：{book_id}[/red]"); raise typer.Exit(1)

    if not ws.threads:
        console.print("[dim]暂无叙事线程（单线叙事模式）[/dim]")
        console.print("提示：可通过 df threads create 创建线程")
        return

    # 线程概览表
    t = Table(title="叙事线程", box=box.SIMPLE)
    t.add_column("线程", style="cyan bold")
    t.add_column("视角角色")
    t.add_column("类型")
    t.add_column("权重", justify="right")
    t.add_column("上次活跃")
    t.add_column("期待感", justify="right")
    t.add_column("状态")

    for thread in ws.threads:
        gap = ws.current_chapter - thread.last_active_chapter
        status_style = {
            "active": "green", "dormant": "yellow",
            "resolved": "dim", "merged": "dim",
        }.get(thread.status, "")
        status_text = {
            "active": "活跃", "dormant": "休眠",
            "resolved": "已结束", "merged": "已合并",
        }.get(thread.status, thread.status)
        warning = ""
        if thread.status == "active" and gap >= 5:
            warning = f" [yellow]({gap}章未活跃!)[/yellow]"

        t.add_row(
            f"{thread.name}\n[dim]{thread.id}[/dim]",
            thread.pov_character_id or "-",
            thread.type.value,
            f"{thread.weight:.1f}",
            f"Ch.{thread.last_active_chapter}{warning}",
            f"{thread.hook_score}/100",
            f"[{status_style}]{status_text}[/{status_style}]",
        )
    console.print(t)

    # 掉线预警
    dormant = ws.dormant_threads(ws.current_chapter, threshold=5)
    if dormant:
        console.print(f"\n[yellow]掉线预警（超过 5 章未活跃）：[/yellow]")
        for thread in dormant:
            gap = ws.current_chapter - thread.last_active_chapter
            console.print(f"  [yellow]· {thread.name}（{thread.id}）：{gap} 章[/yellow]")

    # 跨线程因果链
    cross_links = sm.get_cross_thread_causal_links()
    if cross_links:
        console.print(f"\n[cyan]跨线程因果链：{len(cross_links)} 条[/cyan]")
        for cl in cross_links[-5:]:
            console.print(
                f"  [dim]Ch.{cl.chapter}[/dim] {cl.source_thread_id} → {cl.thread_id}：{cl.event[:40]}"
            )

    # 近期时间轴
    if ws.timeline:
        console.print(f"\n[cyan]近期时间轴（最近 10 条）：[/cyan]")
        for te in ws.timeline[-10:]:
            console.print(
                f"  [dim]Ch.{te.chapter}[/dim] [{te.thread_id}] "
                f"{te.character_id} @ {te.location_id} — {te.action[:40]}"
            )


@threads_app.command("create")
def threads_create(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    thread_id: str = typer.Option(..., "--id", help="线程 ID（如 thread_villain）"),
    name: str = typer.Option(..., "--name", "-n", help="线程名称"),
    type: str = typer.Option("subplot", "--type", "-t", help="类型：main/subplot/parallel/flashback"),
    pov: str = typer.Option("", "--pov", help="视角角色 ID"),
    weight: float = typer.Option(0.7, "--weight", "-w", help="篇幅权重（0.1-2.0）"),
    goal: str = typer.Option("", "--goal", help="线程终极目标"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """创建新的叙事线程"""
    from core.state import StateManager
    from core.types.narrative import NarrativeThread, ThreadType

    sm = StateManager(project, book_id)
    try:
        sm.read_world_state()
    except FileNotFoundError:
        console.print(f"[red]✗ 书籍不存在：{book_id}[/red]"); raise typer.Exit(1)

    thread = NarrativeThread(
        id=thread_id,
        name=name,
        type=ThreadType(type),
        pov_character_id=pov,
        weight=weight,
        goal=goal,
    )
    sm.create_thread(thread)
    sm.update_thread_status_md()
    console.print(f"[green]✓ 线程「{name}」（{thread_id}）已创建[/green]")


@threads_app.command("update")
def threads_update(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    thread_id: str = typer.Argument(..., help="线程 ID"),
    name: str = typer.Option("", "--name", "-n"),
    pov: str = typer.Option("", "--pov"),
    weight: float = typer.Option(None, "--weight", "-w"),
    status: str = typer.Option("", "--status", help="active/dormant/resolved/merged"),
    goal: str = typer.Option("", "--goal"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """更新叙事线程"""
    from core.state import StateManager

    sm = StateManager(project, book_id)
    kwargs = {}
    if name:
        kwargs["name"] = name
    if pov:
        kwargs["pov_character_id"] = pov
    if weight is not None:
        kwargs["weight"] = weight
    if status:
        kwargs["status"] = status
    if goal:
        kwargs["goal"] = goal

    if not kwargs:
        console.print("[yellow]未指定更新字段[/yellow]"); return

    sm.update_thread(thread_id, **kwargs)
    sm.update_thread_status_md()
    console.print(f"[green]✓ 线程 {thread_id} 已更新：{', '.join(kwargs.keys())}[/green]")


@threads_app.command("delete")
def threads_delete(
    book_id: str = typer.Argument(..., help="书籍 ID"),
    thread_id: str = typer.Argument(..., help="线程 ID"),
    project: str = typer.Option(".", "--project", "-p"),
):
    """删除叙事线程（同时删除关联时间轴事件）"""
    from core.state import StateManager

    sm = StateManager(project, book_id)
    try:
        ws = sm.read_world_state()
    except FileNotFoundError:
        console.print(f"[red]✗ 书籍不存在：{book_id}[/red]"); raise typer.Exit(1)

    if not ws.get_thread(thread_id):
        console.print(f"[red]✗ 线程不存在：{thread_id}[/red]"); raise typer.Exit(1)

    sm.delete_thread(thread_id)
    sm.update_thread_status_md()
    console.print(f"[green]✓ 线程 {thread_id} 已删除[/green]")


# ── df export ─────────────────────────────────────────────────────────────────

@app.command()
def export(
    book_id: str       = typer.Argument(..., help="书籍 ID"),
    output: str        = typer.Option("", "--output", "-o", help="输出路径（默认：书名.md）"),
    approved_only: bool = typer.Option(False, "--approved-only", help="只导出最终稿"),
    project: str       = typer.Option(".", "--project", "-p"),
):
    """导出书籍正文"""
    from core.state import StateManager
    sm = StateManager(project, book_id)
    try:
        config = sm.read_config()
    except FileNotFoundError:
        console.print(f"[red]✗ 书籍不存在：{book_id}[/red]"); raise typer.Exit(1)

    ch_files: dict[int, Path] = {}
    for f in sm.chapter_dir.glob("*_final.md"):
        n = int(f.stem.split("_")[0].replace("ch", ""))
        ch_files[n] = f
    if not approved_only:
        for f in sm.chapter_dir.glob("*_draft.md"):
            n = int(f.stem.split("_")[0].replace("ch", ""))
            if n not in ch_files:
                ch_files[n] = f

    if not ch_files:
        console.print("[red]✗ 没有找到章节文件[/red]"); raise typer.Exit(1)

    files = [ch_files[n] for n in sorted(ch_files)]
    parts = [f.read_text(encoding="utf-8") for f in files]
    out = Path(output) if output else Path(f"{config['title']}.md")
    out.write_text("\n\n---\n\n".join(parts), encoding="utf-8")
    total_chars = sum(len(p) for p in parts)
    console.print(f"[green]✓ 导出：{out}（{len(files)} 章，{total_chars} 字）[/green]")


# ── df doctor ─────────────────────────────────────────────────────────────────

@app.command()
def doctor(
    project: str = typer.Option(".", "--project", "-p"),
):
    """诊断 API 连通性与配置问题"""
    console.print("[bold]诊断中...[/bold]\n")

    provider = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    env_path = Path(project) / ".env"
    console.print(("[green]✓[/green]" if env_path.exists() else "[dim]-[/dim]") + " .env 文件")

    if provider == "ollama":
        console.print("[green]✓[/green] 使用 Ollama 本地模型")
    else:
        env_prefix = provider.upper() + "_"
        key = os.environ.get(f"{env_prefix}API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
        if key and not key.startswith("sk-xxx"):
            console.print(f"[green]✓[/green] {provider} API Key（{key[:8]}...）")
        else:
            console.print(f"[red]✗[/red] {provider} API Key 未设置"); return

    console.print("\n测试 API 连通性...")
    try:
        from core.llm import LLMMessage
        resp = _llm().complete([LLMMessage("user", "只回复数字 42。")])
        ok = "42" in resp.content
        icon = "[green]✓[/green]" if ok else "[yellow]⚠[/yellow]"
        model_name = os.environ.get(f"{provider.upper()}_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
        console.print(f"{icon} API {'正常' if ok else '响应异常：' + resp.content[:40]}"
                      f"（模型：{model_name}）")
    except Exception as e:
        console.print(f"[red]✗[/red] 连接失败：{e}")

    books_dir = Path(project) / "books"
    if books_dir.exists():
        books = [b.name for b in books_dir.iterdir() if b.is_dir()]
        console.print(f"\n[green]✓[/green] books 目录：{len(books)} 本书")
        for b in books:
            console.print(f"  · {b}")


if __name__ == "__main__":
    app()
