# GenericAgent × nmem Session-Save SSOT

**Status date**: 2026-05-20  
**Tracking issue**: https://github.com/HamsteRider-m/community/issues/1

## Decision

Use an in-process GenericAgent central completion hook as the primary automatic session-save path. The hook should run from the central queue consumer in `GenericAgent.run`, after a frontend `done` event is emitted and before/around `task_queue.task_done()`.

Do **not** promote the out-of-process `session_watcher` as the main automatic-save mechanism. It may remain only as fallback/backfill for existing `model_responses` logs.

## Rationale

GenericAgent routes CLI/subagent, Telegram, Streamlit, and other queue-based frontends through `agent.put_task(...)` into one queue consumer. A completion hook at that consumer gives one conversation-end event per task, avoids frontend-specific save code, and avoids watcher races over partially-written log files.

`agent_loop` turn-level callbacks are not the preferred primary save point because they can fire inside a tool/turn loop and do not represent a completed user task.

## Current capability claims

| Capability | Status | Acceptance basis |
| --- | --- | --- |
| Working-memory injection / AutoRecall | Usable | Plugin API tests and GenericAgent import/injection validation |
| Session parser / manual backfill | Partial | Parser/API/unit-level validation; use for fallback/backfill |
| Automatic session-save | Planned | Requires central completion hook implementation plus write/readback acceptance |
| Legacy `src/session_watcher.py` | Fallback only | Not the SSOT automatic-save mechanism |

## Minimum implementation requirements

1. Add a central completion-hook registration point in GenericAgent runtime, e.g. `conversation_end_hooks`.
2. Emit exactly one event per completed task with query/source/response/log path/status metadata.
3. Invoke nmem save from that hook without blocking or breaking frontend completion.
4. Treat hook failures as non-fatal; always preserve frontend `done` and queue `task_done()` semantics.
5. Keep manual scan/backfill available for historical logs.

## Required tests before claiming automatic save

- Success path: hook fires exactly once for one completed task.
- Non-fatal path: a failing hook does not prevent frontend `done` or `task_done()`.
- Multi-turn/tool-loop path: no duplicate saves per turn.
- Frontend coverage: CLI/subagent, Telegram, and Streamlit all use the central hook rather than frontend-specific save code.
- nmem acceptance: saved thread/session is verified by readback from nmem, not only by parser/unit tests.
- Fallback/backfill: manual scan still works for existing GenericAgent response logs.

## Documentation rule

This community plugin directory is the SSOT for nmem GenericAgent plugin documentation. Future changes should start with a GitHub issue and land through a PR that references the issue.
