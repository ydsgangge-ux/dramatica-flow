<div align="center">

# Dramatica-Flow

### AI-Powered Long-Form Novel Writing System

**Making AI understand stories, not just write text.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Quick Start](#quick-start) · [Core Features](#core-features) · [Architecture](#architecture) · [API Reference](#api-reference) · [Internationalization](#internationalization)

</div>

---

## What is Dramatica-Flow?

Dramatica-Flow is an **AI-assisted novel writing platform** built on **Dramatica narrative theory**. Unlike generic AI text generators, it enforces structural story logic through:

- **Causal Chain Engine** — Every event must answer "Why → What → Consequence → Decision"
- **Hook Lifecycle** — Foreshadowing tracking with auto-warnings for unresolved threads
- **Emotional Arcs** — Per-character emotion tracking (1–10 intensity scale)
- **Relationship Network** — Dynamic character relationships (-100 to +100)
- **Multi-thread Narrative** — Global timeline with parallel story management
- **Information Boundaries** — Characters can only know what they've witnessed

### Key Differences from Generic AI Writers

| Aspect | Generic AI Writers | **Dramatica-Flow** |
|--------|-------------------|--------------------|
| Narrative logic | Paragraph-by-paragraph, no global causality | **Forced causal chain modeling** |
| Character consistency | Prone to OOC (out-of-character) | **Information boundary system** |
| Long-form coherence | Frequent contradictions | **World state snapshots + truth files** |
| Foreshadowing | None | **Full lifecycle: plant → track → warn → resolve** |
| Quality control | No auditing | **3-layer audit: rules → narrative → revision loop** |
| Multi-thread stories | None | **Global timeline with cross-thread awareness** |

---

## Quick Start

### Prerequisites

- **Python** >= 3.11 ([Download](https://www.python.org/downloads/) — check "Add Python to PATH" during install)
- **LLM Backend** (choose one): DeepSeek API key or Ollama local environment

### Installation

```bash
git clone https://github.com/ydsgangge-ux/dramatica-flow.git
cd dramatica-flow
```

**One-click install (Recommended):**

| OS | Action |
|----|--------|
| Windows | Double-click `install.bat` |
| Linux / macOS | `bash install.sh` |

The script automatically handles:
- Python version check (prompts download if < 3.11)
- Install all dependencies (auto-fills missing packages)
- Create `.env` config file (if not exists)
- Generate startup script `launch_web.bat` / `start.sh`

**Manual install (if script fails):**

```bash
python -m pip install -e .
```

### Configure AI Backend

After installation, open the `.env` file in the project root with any text editor and configure **one of the following**:

**Option A: DeepSeek API (Best quality, paid)**

1. Register at [DeepSeek Platform](https://platform.deepseek.com) and get an API Key
2. Replace `sk-xxx` in `.env` with your real API Key

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-real-api-key
```

**Option B: Ollama Local Model (Free)**

1. Download and install from [ollama.ai](https://ollama.ai)
2. Run `ollama pull qwen2.5` in terminal to download a model
3. Update `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5
```

> For detailed configuration, see [Ollama Guide](docs/OLLAMA_GUIDE.md)

### Launch

```bash
# Windows: double-click launch_web.bat (auto-opens browser)
# Linux/macOS: ./start.sh

# Or manually:
python -m uvicorn core.server:app --reload --port 8766
```

Then open **http://localhost:8766** in your browser.

### Import Existing Novel

If you already have a completed novel, you can extract its worldview via an external LLM and import it:

1. Open the [extraction prompt template](templates/novel_extract_prompt.md), copy the prompt and JSON format
2. Send the prompt + full novel text to an external LLM (e.g., [DeepSeek Chat](https://chat.deepseek.com), free with ultra-long context)
3. Copy the JSON output from the LLM
4. In Web UI **Step 3**, click **"Import JSON"** and paste it in

---

## Core Features

### 1. Causal Chain Engine — The Story's Skeleton

Every event follows a strict causal structure:

```
Ch.1: Public Humiliation
├── Cause     : The Mu family considers Lin Chen (waste spiritual root) worthless
├── Event     : Lin Chen is publicly humiliated
├── Effect    : Lin Chen makes a three-year pact
└── Decision  : Lin Chen → ventures into Qingfeng Mountain alone
```

### 2. Smart Hook System — No Forgotten Promises

Manages four types of narrative commitments:

| Type | Description | Example |
|------|-------------|---------|
| **Foreshadow** | Hidden clues | A mysterious jade pendant in Ch.3, reveals identity in Ch.28 |
| **Promise** | Reader commitment | A "three-year pact" that must be fulfilled |
| **Mystery** | Unsolved questions | Where did the vanished spiritual energy go? |
| **Conflict** | Unresolved tension | When will the two factions' shadow war erupt? |

Auto-tracks hook status with overdue warnings.

### 3. Emotional Arcs — Visual Character Growth

1–10 intensity emotion tracking per character, supporting Dramatica's dual-need model: **external goal** (visible, quantifiable) vs. **internal need** (what the character truly needs but doesn't realize).

### 4. Relationship Network — Dynamic Interpersonal Graph

Relationship strength ranges from **-100 (mortal enemy) to +100 (sworn ally)**, auto-updated after each event.

### 5. Multi-thread Narrative — Global Timeline

Supports **main plot, subplot, parallel, and flashback** threads, each with:
- Dedicated POV characters
- Independent goal arcs
- Weight-based word count allocation
- Dormancy warnings (auto-alert after 5+ chapters of inactivity)

### 6. Information Boundaries — No Omniscient Contamination

Each character maintains an independent knowledge record:

```python
@dataclass
class KnownInfoRecord:
    character_id: str      # Who knows it
    info_key: str          # What information
    content: str           # Specific details
    learned_in_chapter: int
    source: Literal["witnessed", "hearsay", "deduced", "document"]
```

**Characters cannot know what they haven't seen** — this is the fundamental difference.

---

## Architecture

### 5-Layer Agent Pipeline

```
Snapshot Backup
    ↓
① Architect Agent ── Plans blueprint (causal chain context + prior summary + hook status)
    ↓
② Writer Agent ── Generates chapter text + settlement table
    ↓
③ Post-write Validator ── Zero-LLM hard rule checks (word count, forbidden words, format)
    ↓ error → spot-fix
④ Auditor Agent ── Narrative quality audit (temperature=0 for objectivity)
    ↓ critical → Reviser Agent → re-audit (max 2 rounds)
⑤ Causal Chain Extractor ── Extracts causality from text → writes to world state
    ↓
Summary Generator ── Chapter summary → truth files
    ↓
State Settlement ── Positions / emotions / relationships / hooks → world_state.json
```

### Dramatica Theory Integration

Built-in **Dramatica character role system**: Protagonist, Antagonist, Impact Character, Guardian, Contagonist, Sidekick, Skeptic, Reason, Emotion, Love Interest, Mentor, Supporting.

Plus **11 dramatic function beats**: Setup, Inciting Incident, Turning Point, Midpoint, Crisis, Climax, Reveal, Decision, Consequence, Transition.

### Tech Stack

```
┌──────────────────────────────────────────────────┐
│                   Web UI Layer                    │
│   Modern SPA · 7 feature modules · Timeline view  │
├──────────────────────────────────────────────────┤
│                  REST API Layer                   │
│   FastAPI · 50+ endpoints · Pydantic validation   │
├──────────────────────────────────────────────────┤
│                 Agent Pipeline Layer              │
│   Architect · Writer · Auditor · Reviser · Summary│
├──────────────────────────────────────────────────┤
│               Narrative Engine Layer              │
│   Causal chain · Hooks · Emotions · Relationships │
│   Multi-thread · Info boundaries · World state     │
├──────────────────────────────────────────────────┤
│                  LLM Abstraction Layer             │
│   DeepSeek API · Ollama local · OpenAI compatible │
└──────────────────────────────────────────────────┘
```

---

## API Reference

The system provides **50+ REST API endpoints**:

### Book Management
```
GET    /api/books                            # List books
POST   /api/books                            # Create book
GET    /api/books/{id}                       # Book details
DELETE /api/books/{id}                       # Delete book
```

### Story Configuration
```
GET    /api/books/{id}/setup/status          # Setup status
POST   /api/books/{id}/setup/init            # Initialize config templates
GET    /api/books/{id}/setup/{type}          # Get config (characters/factions/locations/events)
PUT    /api/books/{id}/setup/{type}          # Update config
POST   /api/books/{id}/setup/load            # Load config into world state
```

### AI Generation
```
POST   /api/books/{id}/ai-generate/outline           # AI generate outline
POST   /api/books/{id}/ai-generate/chapter-outlines  # AI generate chapter outlines
POST   /api/books/{id}/ai-generate/detailed-outline   # AI generate detailed chapter outline
POST   /api/books/{id}/ai-generate/chapter-content    # AI generate chapter content
POST   /api/books/{id}/ai-rewrite-segment             # AI rewrite specific segment
POST   /api/action/write                              # Execute writing pipeline
POST   /api/action/audit                              # Execute audit
POST   /api/action/revise                             # Execute revision
POST   /api/action/export                             # Export full book
```

### Story Tracking
```
GET    /api/books/{id}/causal-chain          # Causal chain
GET    /api/books/{id}/emotional-arcs        # Emotional arcs
GET    /api/books/{id}/hooks                 # Hook list
GET    /api/books/{id}/relationships         # Relationship network
GET    /api/books/{id}/threads               # Narrative threads
GET    /api/books/{id}/timeline              # Global timeline
```

### Story Analysis
```
POST   /api/books/{id}/extract-from-novel    # Extract worldview from existing novel
POST   /api/books/{id}/extract-story-state   # Extract story state (characters/events/relations)
POST   /api/books/{id}/three-layer-audit     # Three-layer audit
GET    /api/books/{id}/audit-results         # Audit results list
```

### System Configuration
```
GET    /api/settings                         # Get settings
POST   /api/settings                         # Update settings
GET    /api/settings/status                  # Settings health check
```

---

## Project Structure

```
dramatica_flow/
├── core/                           # Core engine
│   ├── agents/                     # AI Agents (Architect/Writer/Auditor/Reviser/Summary)
│   ├── llm/                        # LLM abstraction layer (DeepSeek + Ollama)
│   ├── narrative/                  # Narrative engine (outline parsing, causal extraction)
│   ├── state/                      # State management (world state, truth files, snapshots)
│   ├── types/                      # Data types (characters/events/causal_chain/hooks...)
│   ├── validators/                 # Content validators (zero-LLM hard rules)
│   ├── pipeline.py                 # 5-layer writing pipeline
│   └── server.py                   # FastAPI server (50+ endpoints)
├── cli/                            # CLI tools
│   ├── main.py                     # CLI entry (Typer)
│   └── commands/                   # Subcommands
├── books/                          # Book data directory
├── templates/                      # Config templates + extraction prompts
├── tests/                          # Test suite (30+ cases)
├── docs/                           # Documentation
│   ├── CHANGELOG.md
│   ├── OLLAMA_GUIDE.md
│   ├── QUICKSTART.md
│   └── screenshots/                # UI screenshots
├── dramatica_flow_web_ui.html      # Main Web UI
├── dramatica_flow_timeline.html    # Timeline swimlane view
├── install.bat                     # Windows one-click installer
├── install.sh                      # Linux/macOS installer
├── .env.example                    # Environment variable template
└── pyproject.toml                  # Project config
```

---

## Internationalization

> **Note:** The default interface and prompts are in Chinese. To use Dramatica-Flow in another language, you need to modify the following files. This guide covers what to change and where.

### Overview of Required Changes

| Module | Files to Modify | Effort | Description |
|--------|----------------|--------|-------------|
| **Web UI** | `dramatica_flow_web_ui.html` | Medium | ~200+ hardcoded Chinese strings |
| **Timeline UI** | `dramatica_flow_timeline.html` | Small | ~50 Chinese labels |
| **LLM Prompts** | `core/server.py`, `core/pipeline.py`, `core/agents/__init__.py` | Large | ~50+ prompt templates |
| **Templates** | `templates/*.json` | Small | Field descriptions and placeholders |
| **CLI Output** | `cli/main.py`, `cli/commands/` | Small | Help text and status messages |
| **Error Messages** | `core/server.py` | Small | HTTP error messages |

---

### 1. Web UI Localization

**File:** `dramatica_flow_web_ui.html`

All UI text is hardcoded as Chinese strings. To localize:

**Step 1:** Add a language configuration at the top of the `<script>` section:

```javascript
// Add near the top of <script>
const LANG = {
  // Navigation
  "nav.overview": "Overview",
  "nav.config": "Story Config",
  "nav.outline": "Outline",
  "nav.chapters": "Chapters",
  "nav.tracking": "Story Tracking",
  "nav.timeline": "Timeline",
  "nav.settings": "Settings",

  // Buttons
  "btn.create": "Create",
  "btn.save": "Save",
  "btn.delete": "Delete",
  "btn.cancel": "Cancel",
  "btn.generate": "AI Generate",
  "btn.audit": "Audit",
  "btn.export": "Export",

  // ... add all other strings you need
};

function t(key) {
  return LANG[key] || key;
}
```

**Step 2:** Replace hardcoded Chinese text with `t()` calls:

```javascript
// Before:
innerHTML = `<div class="card-header">因果链 (${causal.length})</div>`;

// After:
innerHTML = `<div class="card-header">${t('tracking.causal_chain')} (${causal.length})</div>`;
```

**Key areas to translate in the HTML file:**

| Line Range | Content |
|------------|---------|
| Top navigation bar | Step labels: 创建书籍, 故事配置, 大纲, etc. |
| `renderOverview()` | Dashboard statistics labels |
| `renderConfig()` | Character/faction/location form labels |
| `renderOutline()` | Act names, sequence labels |
| `renderChapters()` | Chapter list labels, audit buttons |
| `renderStoryTracking()` | Section labels for causal chain, hooks, emotions, relationships |
| `renderSettings()` | Form labels, model names |
| All `alert()` / `confirm()` calls | Dialog messages |

---

### 2. Timeline UI Localization

**File:** `dramatica_flow_timeline.html`

Similar approach — replace Chinese labels in the sidebar, header, and rendering functions.

Key areas:
- Thread type badges: 主线, 支线, 并行线, 闪回线
- Status badges: 活跃, 休眠, 已完结, 已合并
- Column headers: 章节, 角色, 地点, 行动

---

### 3. LLM Prompt Translation (Most Important)

This is the **most critical** change — it determines what language the AI outputs.

**File:** `core/server.py`

All prompts sent to the LLM are in Chinese. Search for `prompt = f"""` or `prompt = """` patterns.

**Key prompt locations in `core/server.py`:**

| Approximate Line | Endpoint | What It Does |
|-----------------|----------|--------------|
| ~975 | `extract-story-state` | Extracts story state from chapter text |
| ~827 | `ai-generate/setup` | Generates character/faction/location configs |
| ~1166 | `ai-generate/outline` | Generates story outline |
| ~1268 | `ai-generate/chapter-outlines` | Generates chapter outlines |
| ~1668 | `ai-generate/detailed-outline` | Generates detailed chapter outline |
| ~1789 | `ai-generate/chapter-content` | Generates chapter content |

**Example — Before (Chinese):**

```python
prompt = f"""你是一位小说分析专家。请仔细阅读以下章节正文，提取其中的故事状态变化。
请严格按以下 JSON 结构输出（直接输出 JSON，不要任何说明）："""
```

**Example — After (English):**

```python
prompt = f"""You are a novel analysis expert. Carefully read the following chapter text and extract story state changes.
Output strictly in the following JSON format (JSON only, no explanations):"""
```

**Important:** When translating prompts, also update:
- **JSON field names in examples** — Keep them in English for consistency
- **Analysis instructions** — Translate all Chinese instructions
- **Character name hints** — Keep actual character names as-is

**File:** `core/pipeline.py`

The pipeline contains prompts in the agent classes (Architect, Writer, Auditor, etc.). These are imported from `core/agents/__init__.py`.

**File:** `core/agents/__init__.py`

Search for all prompt templates (look for `prompt`, `system_prompt`, or `PROMPT` variables) and translate them.

---

### 4. Template Files

**Files:** `templates/characters.json`, `templates/world.json`, `templates/events.json`

These are JSON config templates with Chinese field descriptions. Translate the `description`, `placeholder`, and example values:

```json
// Before:
{"name": "character_name", "label": "角色名", "description": "角色在小说中的名字"}

// After:
{"name": "character_name", "label": "Character Name", "description": "Character's name in the novel"}
```

---

### 5. CLI Localization

**File:** `cli/main.py`

The Typer CLI has Chinese help text and status messages. Key areas:

```python
# Before:
@app.command(help="创建新书")
def book(...):

# After:
@app.command(help="Create a new book")
def book(...):
```

---

### 6. Error Messages

**File:** `core/server.py`

HTTP error responses contain Chinese messages:

```python
# Before:
raise HTTPException(404, f"第 {req.chapter} 章不存在")

# After:
raise HTTPException(404, f"Chapter {req.chapter} not found")
```

---

### Quick Localization Checklist

If you want to adapt Dramatica-Flow to your language, follow this order:

- [ ] **1. LLM Prompts** (`core/server.py`, `core/agents/__init__.py`, `core/pipeline.py`) — This is the **highest priority**. Without this, the AI will still output Chinese.
- [ ] **2. Web UI** (`dramatica_flow_web_ui.html`) — Translate all visible text.
- [ ] **3. Timeline UI** (`dramatica_flow_timeline.html`) — Translate labels.
- [ ] **4. Templates** (`templates/*.json`) — Translate field descriptions.
- [ ] **5. Error Messages** (`core/server.py`) — Translate HTTP error responses.
- [ ] **6. CLI** (`cli/main.py`) — Translate help text (optional, Web UI is primary).

> **Tip:** The core logic (causal chain, hook management, audit pipeline, world state) is **language-agnostic**. You only need to translate the interface layer and prompts — no architectural changes required.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `df book` | Create a new book |
| `df setup init-templates <book>` | Initialize config templates |
| `df setup load <book>` | Load configuration |
| `df write <book>` | AI write next chapter |
| `df write <book> --count 5` | Write 5 chapters consecutively |
| `df audit <book> <chapter>` | Audit a specific chapter |
| `df revise <book> <chapter>` | Revise a chapter |
| `df status <book>` | View book status |
| `df export <book>` | Export full book |
| `df doctor` | Diagnose project configuration |

---

## Testing

```bash
python run_tests.py
# or
python -m pytest tests/ -v
```

---

## Tech Specs

| Item | Specification |
|------|---------------|
| Language | Python 3.11+ |
| Web Framework | FastAPI |
| LLM Interface | OpenAI SDK (compatible protocol) |
| Data Validation | Pydantic v2 |
| CLI Framework | Typer + Rich |
| Test Framework | pytest + pytest-asyncio |
| Frontend | Vanilla HTML/CSS/JS (zero build dependencies) |
| Supported Models | DeepSeek, Ollama (qwen2.5/llama3.1/mistral, etc.) |

---

## License

MIT License

---

## Acknowledgements

- [Dramatica Theory](https://dramatica.com/) — Narrative theory framework
- [FastAPI](https://fastapi.tiangolo.com/) — High-performance web framework
- [Ollama](https://ollama.ai/) — Local LLM runtime
- [OpenAI SDK](https://github.com/openai/openai-python) — LLM interface standard
