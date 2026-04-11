# Hermes → Py Hybrid Port Plan

## Current State
- ✅ py repo: 7 packages ported (pi_ai, pi_tui, pi_agent_core, pi_coding_agent, pi_mom, pi_pods, pi_web_ui)
- ❌ Missing: io CLI layer (gateway, cron, config management, diff preview)

## Hermes Features to Port (Priority Order)

### P0: Core Infrastructure
1. **Config System** (`io_cli.config`)
   - `get_io_home()` - Returns ~/.io directory path
   - Profile management (YAML-based config)
   - Environment variable integration
   - API key management

2. **Path Constants** (`io_cli.constants` or `io_constants`)
   - IO_HOME directory structure
   - Default paths for sessions, logs, cache

### P1: CLI Foundation  
3. **CLI Main** (`io_cli.cli`)
   - Entry point with subcommands
   - Command routing
   - Global flags (--verbose, --config, etc.)

4. **Argument Parsing** (`io_cli.args`)
   - Subcommand definitions
   - Flag parsing
   - Help generation

### P2: Distributed Execution
5. **Gateway** (`io_cli.gateway` or `io_gateway`)
   - Node management (register, list, connect)
   - Remote execution routing
   - Load balancing across nodes
   - Health checks
   - Authentication/authorization

6. **Cron Manager** (`io_cli.cron`)
   - Scheduled task definitions
   - Cron expression parsing
   - Task execution engine
   - Persistence (JSON/YAML store)

### P3: Developer Experience
7. **Edit Diff Preview** (`io_cli.edit_diff_preview`)
   - Capture local file state before edits
   - Generate diff summaries
   - Preview changes before applying
   - Syntax highlighting for diffs

8. **Banner/Branding** (`io_cli.banner`)
   - Startup banner display
   - Version info
   - ASCII art (optional)

### P4: Advanced Features
9. **Session Management** (`io_cli.session`)
   - Multi-session tracking
   - Session persistence beyond pi_coding_agent
   - Cross-session context sharing

10. **Plugin System** (`io_cli.plugins`)
    - Dynamic tool loading
    - Extension registry
    - Hot-reload

## Proposed Architecture

```
io/                          # New package (or io-cli)
├── src/io_cli/
│   ├── __init__.py
│   ├── __main__.py         # Entry point: python -m io_cli
│   ├── cli.py              # Main CLI router
│   ├── args.py             # Argument parsing
│   ├── config.py           # Configuration management
│   ├── constants.py        # Path constants
│   ├── banner.py           # Branding
│   ├── cron.py             # CronManager
│   ├── gateway.py          # Gateway client/server
│   ├── edit_diff_preview.py # Diff preview utilities
│   └── session.py          # Enhanced session management
├── pyproject.toml
└── tests/
```

## Integration Points

### pi_coding_agent → io_cli
- pi_coding_agent CLI becomes `io code` or `io agent`
- Session store unified under io_cli.session
- Config system shared

### pi_pods → io_cli  
- pi_pods CLI becomes `io pods` subcommand
- Gateway integration for distributed pods

### pi_mom → io_cli
- pi_mom becomes `io mom` or `io slack`
- Shared gateway for multi-bot management

## Build Order

**Phase 1: Foundation (Day 1-2)**
1. Create io_cli package structure
2. Implement config.py with get_io_home()
3. Implement constants.py
4. Basic CLI entry point

**Phase 2: Cron (Day 3)**
5. CronManager class
6. Cron expression parser (use python-crontab or croniter)
7. Task persistence

**Phase 3: Gateway (Day 4-5)**
8. Gateway server (FastAPI/HTTP)
9. Gateway client
10. Node registration protocol

**Phase 4: Polish (Day 6)**
11. Edit diff preview
12. Banner/branding
13. Integration tests

## Dependencies to Add

```toml
[project.dependencies]
"pi-coding-agent" = { path = "../pi_coding_agent" }
"pi-pods" = { path = "../pi_pods" }
click = "^8.1"          # CLI framework (or use argparse)
pyyaml = "^6.0"         # Config files
croniter = "^2.0"       # Cron parsing
fastapi = "^0.110"      # Gateway server
websockets = "^12.0"    # Real-time comms
rich = "^13.0"          # Terminal UI enhancements
```

## Open Questions

1. **Gateway protocol**: REST + WebSocket? gRPC? Custom?
2. **Cron persistence**: SQLite? JSON files? Existing pi_coding_agent session store?
3. **Config format**: YAML? TOML? Keep compatible with pi-mono TypeScript?
4. **Namespace**: `io` command? `pi` command? `py` command?
