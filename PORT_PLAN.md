# Pi Mono Python Port - Implementation Plan

## Project Overview
Porting pi-mono (TypeScript AI coding agent) to Python with 100% fidelity + OpenRouter support.

**Total Scope:** 166,813 lines across 575 TypeScript files

## Package Breakdown

| Package | TS Lines | Files | Priority | Dependencies |
|---------|----------|-------|----------|--------------|
| **pi_ai** | 40,388 | 95 | P0 | None (foundation) |
| **pi_tui** | 20,912 | 53 | P0 | None (parallel) |
| **pi_agent_core** | 3,571 | 11 | P1 | pi_ai |
| **pi_coding_agent** | 79,765 | 315 | P2 | pi_ai, pi_tui, pi_agent_core |
| **pi_mom** | 4,167 | 17 | P3 | pi_agent_core, pi_ai, pi_coding_agent |
| **pi_pods** | 1,773 | 9 | P3 | pi_agent_core |
| **pi_web_ui** | 15,237 | 75 | P3 | pi_ai, pi_tui |

## pi_ai Core Types (Priority 1)

### API Types
```python
KnownApi = Literal[
    "openai-completions",
    "mistral-conversations", 
    "openai-responses",
    "azure-openai-responses",
    "openai-codex-responses",
    "anthropic-messages",
    "bedrock-converse-stream",
    "google-generative-ai",
    "google-gemini-cli",
    "google-vertex",
]

KnownProvider = Literal[
    "amazon-bedrock", "anthropic", "google", "openai",
    "azure-openai-responses", "github-copilot", "xai", "groq",
    "cerebras", "openrouter", "mistral", "kimi-coding",
    # ... 20+ providers
]
```

### Message Types
- `UserMessage` - Input from user (text + images)
- `AssistantMessage` - Model response with content blocks
- `TextContent`, `ThinkingContent`, `ImageContent`, `ToolCall`

### Stream Architecture
- `AssistantMessageEventStream` - Async iterable event stream
- Events: `text`, `thinking`, `toolCall`, `usage`, `error`, `end`

## Provider Architecture

Each provider implements:
```python
async def stream(
    model: Model[TApi],
    context: Context, 
    options: StreamOptions
) -> AsyncIterable[AssistantMessageEvent]: ...
```

### Providers to Port (in order)
1. **faux** - Mock provider for testing
2. **openai-completions** - OpenAI + OpenRouter + compatible APIs
3. **anthropic** - Claude API
4. **openai-responses** - OpenAI Responses API
5. **google-generative-ai** - Gemini API
6. **mistral** - Mistral API
7. **bedrock** - AWS Bedrock
8. **azure-openai** - Azure OpenAI

## OpenRouter Integration
OpenRouter is supported via `openai-completions` provider with special handling:
- Detect `openrouter.ai` in baseUrl
- Add OpenRouter-specific headers
- Support provider routing preferences
- Handle Anthropic cache control through OpenRouter

See `pi-mono/packages/ai/src/providers/openai-completions.ts` lines 295-465 for implementation.

## Key Implementation Notes

### TypeScript → Python Mapping
| TypeScript | Python |
|------------|--------|
| `@sinclair/typebox` | `pydantic.BaseModel` |
| `AbortSignal` | `asyncio.Event` or `anyio.CancelScope` |
| `AsyncIterable` | `AsyncGenerator` / `AsyncIterator` |
| Lazy imports | `importlib` dynamic imports |
| Provider registry | Module-level dict with lazy loading |

### Dependencies
```
pydantic>=2.0
httpx[http2]>=0.27
anthropic>=0.30
openai>=1.35
google-generativeai>=0.7
boto3>=1.34  # Bedrock
orjson>=3.10  # Fast JSON
anyio>=4.4  # Async primitives
```

## Next Steps

### Phase 1: Foundation (Week 1)
1. [x] Workspace structure
2. [ ] pi_ai types + registry
3. [ ] pi_ai faux provider
4. [ ] pi_ai openai-completions (with OpenRouter)
5. [ ] pi_ai anthropic

### Phase 2: Core Providers (Week 2)
6. [ ] pi_ai remaining providers
7. [ ] pi_tui differential renderer
8. [ ] pi_tui components

### Phase 3: Agent Layer (Week 3-4)
9. [ ] pi_agent_core
10. [ ] pi_coding_agent (80K lines - major work)

### Phase 4: Utilities (Week 5)
11. [ ] pi_mom
12. [ ] pi_pods
13. [ ] pi_web_ui

## Current Status
- ✅ Project structure created
- 🔄 pi_ai types in progress
- ⏳ Providers pending
- ⏳ pi_tui pending
- ⏳ Downstream packages pending
