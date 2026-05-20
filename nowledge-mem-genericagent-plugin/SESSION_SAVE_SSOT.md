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
| Automatic session-save | Implemented in plugin | `src/genericagent_session_hook.py` patches the central `put_task` completion path; unit acceptance covers create/append plus readback message-count verification |
| Legacy `src/session_watcher.py` | Fallback only | Not the SSOT automatic-save mechanism |

## Minimum implementation requirements

1. Install `src/genericagent_session_hook.py` from the plugin/wrapper path without modifying GenericAgent core source.
2. Patch the central `put_task(query, ret)` completion path and emit exactly one save attempt when `query` is present and `ret` is a non-empty assistant string.
3. Invoke nmem save from that hook without breaking frontend completion; original `put_task` behavior runs first and hook failures are stored on the agent as non-fatal diagnostics.
4. Verify saved thread state by `get_thread_message_count(...)` readback after create/append.
5. Keep manual scan/backfill available for historical logs.

## Required tests before claiming automatic save

Implemented/covered in this plugin PR:

- Success path: `tests/test_genericagent_session_hook.py` verifies one completed task creates one nmem thread with user+assistant messages.
- Append path: the same test verifies later completed tasks append to the same thread using an idempotency key.
- Non-completed path: empty or assistant-only/non-final queue events are ignored.
- Non-fatal path: original `put_task` behavior is preserved before hook save state is recorded.
- nmem acceptance: create/append results are verified by readback via `get_thread_message_count(...)` in `NmemSessionArchive.save_turn`.
- Fallback/backfill: existing parser/manual scan tests remain in `tests/test_session_save.py`.

Still environment-gated before claiming real production telemetry:

- Run the hook against a live nmem API instance and capture readback evidence from that API, not only the fake client used in unit acceptance.
- Confirm the deployed GenericAgent launcher imports `genericagent_session_hook.install(...)` before frontend traffic starts.

## Documentation rule

This community plugin directory is the SSOT for nmem GenericAgent plugin documentation. Future changes should start with a GitHub issue and land through a PR that references the issue.
