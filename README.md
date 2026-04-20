# Pi Mono Python

A **clean-room Python port** of the [pi-mono](https://github.com/pi-mono/pi-mono) TypeScript codebase.

**Purpose:** Reference implementation. 100% port of the original 166,813 lines of TypeScript into ~50,000 lines of Python. No extras, no hybrids — just the original architecture translated faithfully.

---

## 📊 Port Status: ✅ COMPLETE

| Metric | TypeScript Original | Python Port | Ratio |
|--------|---------------------|-------------|-------|
| Lines of Code | 166,813 | ~50,000 | 70% reduction |
| Packages | 7 | 7 | ✅ 100% |
| Test Pass Rate | - | 100% (79/79) | ✅ |

---

## 📦 Packages

| Package | Description | Lines (TS→Py) | Status |
|---------|-------------|---------------|--------|
| `pi_ai` | LLM provider abstraction | 40,388 → ~15,000 | ✅ All 10 providers |
| `pi_tui` | Terminal UI library | 20,912 → ~12,000 | ✅ Complete |
| `pi_agent_core` | Agent runtime | 3,571 → ~4,000 | ✅ Full runtime |
| `pi_coding_agent` | Coding agent with 7 tools | 79,765 → ~10,000 | ✅ Tools + CLI + SDK |
| `pi_mom` | Slack bot | 3,572 → ~1,650 | ✅ Socket Mode |
| `pi_pods` | vLLM pod management | 5,500 → ~3,100 | ✅ GPU allocation |
| `pi_web_ui` | Web interface | 6,200 → ~1,500 | ✅ FastAPI + WebSocket |

---

## 🚀 Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run coding agent
pi-coding-agent "Create a Python script..."

# With specific model
pi-coding-agent --model openai/gpt-4o "Refactor this..."
```

---

## 🔌 Supported Providers

- **OpenAI** (GPT-4o, GPT-4o-mini, o3-mini)
- **Anthropic** (Claude 3.5 Sonnet, Claude 3 Opus)
- **Google** (Gemini 2.0 Flash)
- **Mistral**
- **OpenRouter** (100+ models with routing)
- **Azure OpenAI**
- **AWS Bedrock**

---

## 🧪 Testing

```bash
make test      # Run all tests
make lint      # Ruff check
make all       # Format + lint + typecheck + test
```

**Current status:** 79/79 tests passing, 0 ruff warnings, 0 vulture warnings.

---

## 🏗️ Architecture Decisions

| TypeScript Pattern | Python Equivalent |
|-------------------|-------------------|
| `@sinclair/typebox` | `dataclasses` + `pydantic` |
| `AbortSignal` | `asyncio.Event` |
| `AsyncIterable` | Python async generators |
| Lazy imports | Direct imports |
| Class-heavy | Dataclasses where appropriate |

---

## 📝 What This Is (And Isn't)

**This IS:**
- A faithful port of the original TypeScript architecture
- Clean, readable Python code optimized for skimmability
- All original features preserved

**This is NOT:**
- A hybrid with additional features (see [io](https://github.com/ever-oli/io) for that)
- A rewrite with architectural changes
- Extended with cron, gateway, or session management (again, see `io`)

---

## 🔗 Related

- **Clean port (this repo):** `py` — Reference implementation
- **Hybrid system:** [`io`](https://github.com/ever-oli/io) — Py + Hermes gateway/cron/skills merged

---

## 📄 License

MIT License — See original pi-mono for TypeScript source credits.
