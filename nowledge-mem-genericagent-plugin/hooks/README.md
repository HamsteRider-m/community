# GenericAgent Hooks

GenericAgent v2+ uses a native Python hook system (`plugins/hooks.py`). Place hook files in `GenericAgent/plugins/` and they auto-load on agent start.

## Hook Architecture

```
agent_loop.py triggers 6 lifecycle hooks via locals():
  agent_before  → system prompt + SOP index injection
  turn_before   → per-turn pre-processing
  llm_before    → pre-LLM message filtering
  llm_after     → post-LLM response processing
  turn_after    → per-turn cleanup
  agent_after   → session sync (nmem_session.py)
```

Hooks receive `ctx=locals()` dict and modify `ctx['messages']` in-place. No monkey-patching required.

## Included Hooks

- **nmem_auto_recall.py** — `agent_before`: AutoRecall (working memory + thread/memory search) + dynamic SOP index; `llm_before`: strips redundant get_global_memory() injections
- **nmem_session_sync.py** — `agent_after`: archives completed turns to nmem (legacy monkey-patch version; GA core now has `plugins/nmem_session.py` with native hook)

## Installation

1. Copy `nmem_auto_recall.py` into `GenericAgent/plugins/`
2. Restart GenericAgent. Hooks auto-discover via `plugins/hooks.py` `discover_and_load()`.

No manual `install()` call needed. No `.omx/` directory required.

## Testing

```bash
cd GenericAgent
python3 -c "
from plugins.hooks import discover_and_load, trigger
discover_and_load()
# Test agent_before:
ctx = {'messages': [{'role':'system','content':'Test'},{'role':'user','content':'查询 VPS'}], 'handler': type('H',(),{})()}
trigger('agent_before', ctx)
print('PASS' if '[AutoRecall' in ctx['messages'][0]['content'] else 'FAIL')
"
```
