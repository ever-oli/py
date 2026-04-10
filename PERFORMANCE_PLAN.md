# Performance Optimization Plan for pi-mono-python

## Issues Identified

### 1. HTTP Connection Pooling (Critical)
- **Location**: `pi_ai/providers/openai_completions.py`, `pi_ai/providers/anthropic_provider.py`
- **Issue**: New `httpx.AsyncClient()` created for every request
- **Impact**: High latency, connection overhead, no keep-alive
- **Fix**: Create shared connection pool with `httpx.AsyncClient(limits=...)`

### 2. Regex Compilation (Medium)
- **Location**: `pi_coding_agent/tools/grep_tool.py`, `pi_ai/utils/json_parse.py`
- **Issue**: Regex patterns compiled on every call
- **Impact**: CPU overhead, especially for repeated searches
- **Fix**: Cache compiled patterns with `functools.lru_cache`

### 3. File Reading (Medium)
- **Location**: `pi_coding_agent/tools/read_tool.py`
- **Issue**: Entire files read into memory even when truncated
- **Impact**: Memory bloat for large files
- **Fix**: Stream files with buffered reading

### 4. Event Stream (Medium)
- **Location**: `pi_ai/event_stream.py`, `pi_agent_core/agent_loop.py`
- **Issue**: Creates new futures for each wait, list pop(0) is O(n)
- **Impact**: Latency in high-frequency event scenarios
- **Fix**: Use deque for waiting list, optimize future creation

### 5. Module Loading (Low)
- **Location**: Multiple providers
- **Issue**: Heavy modules imported at module load time
- **Impact**: Slow startup
- **Fix**: Lazy load with TYPE_CHECKING guards and local imports

### 6. JSON Parsing (Low)
- **Location**: `pi_ai/utils/json_parse.py`
- **Issue**: Multiple try/except blocks, repeated regex compilation
- **Impact**: Slightly slower JSON parsing
- **Fix**: Compile regex once, optimize error handling

## Implementation Order
1. HTTP connection pooling (highest impact)
2. Regex caching
3. File streaming
4. Event stream optimization
5. Lazy loading
6. Benchmarks
