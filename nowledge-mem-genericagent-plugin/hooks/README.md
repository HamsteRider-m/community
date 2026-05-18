# GenericAgent Hooks

GenericAgent uses a Python-based hook injection mechanism, not JSON configuration.

## How It Works

The hook is installed via `run_agentmain.py`:

```python
import nmem_session_sync
nmem_session_sync.install(agentmain.GeneraticAgent)
```

This injects session sync functionality directly into the GenericAgent class lifecycle.

## Installation

The `nmem_session_sync.py` script should be placed in:
```
GenericAgent/.omx/ga_nmem_hook/nmem_session_sync.py
```

And called from:
```
GenericAgent/.omx/ga_nmem_hook/run_agentmain.py
```

## Files

- `nmem_session_sync.py` - Session sync hook implementation
- No `hooks.json` needed (GenericAgent doesn't use JSON hook configs)

## Testing

```bash
cd GenericAgent/.omx/ga_nmem_hook
python3 test_nmem_session_sync.py
```
