# GenericAgent × nmem Session-Save SSOT

**Status date**: 2026-05-20  
**Tracking issue**: https://github.com/HamsteRider-m/community/issues/1

## Decision

Use an in-process GenericAgent **task-queue/display-queue completion bridge** as the primary automatic session-save path. Current GA enqueues dict tasks through `agent.put_task(...)` into `agent.task_queue`; `GenericAgent.run()` later emits the final assistant result to the per-task display queue as `{"done": ...}`. The plugin installs an instance-level proxy around `agent.task_queue`, wraps each task's display queue, and archives exactly when the final `done` item is posted.

Do **not** promote the out-of-process `session_watcher` as the main automatic-save mechanism. It may remain only as fallback/backfill for existing `model_responses` logs.

## Rationale

GenericAgent's checked source does not currently call an `agent._turn_end_hooks` list from `run()`. The stable completion signal observed in code is the display queue `done` event. Installing a proxy on the live agent instance's `task_queue` gives one conversation-end event per queued task, avoids frontend-specific save code, avoids modifying GenericAgent source, avoids patching the `GenericAgent` class or `put_task` signature, and avoids watcher races over partially-written log files.

`agent_loop` turn-level callbacks are not the preferred primary save point because they can fire inside a tool/turn loop and do not represent a completed user task.

## Current capability claims

| Capability | Status | Acceptance basis |
| --- | --- | --- |
| Working-memory injection / AutoRecall | Usable | Plugin API tests and GenericAgent import/injection validation |
| Session parser / manual backfill | Partial | Parser/API/unit-level validation; use for fallback/backfill |
| Automatic session-save | Implemented in plugin | `src/genericagent_session_hook.py` installs an instance-level `task_queue` proxy that wraps per-task display queues; unit acceptance covers create/append plus readback message-count verification and verifies current `put_task(query, source='user', images=None)` behavior is preserved |
| Legacy `src/session_watcher.py` | Fallback only | Not the SSOT automatic-save mechanism |

## Minimum implementation requirements

1. Install `src/genericagent_session_hook.py` from the plugin/wrapper path without modifying GenericAgent core source.
2. Replace only the target agent instance's `task_queue` with an idempotent delegating proxy; do not monkey-patch `put_task`, do not patch the `GenericAgent` class, and do not assume a historical `put_task(query, ret)` signature.
3. Wrap each dict task's `output` display queue and save the user/assistant turn when a final `{"done": ...}` item is emitted; save failures must remain non-fatal and be stored on the agent as diagnostics.
4. Verify saved thread state by `get_thread_message_count(...)` readback after create/append.
5. Keep manual scan/backfill available for historical logs.

## Required tests before claiming automatic save

Implemented/covered in this plugin PR:

- Success path: `tests/test_genericagent_session_hook.py` verifies one completed queued task creates one nmem thread with user+assistant messages.
- Append path: the same test verifies later completed queued tasks append to the same thread using an idempotency key.
- Non-completed path: empty direct save contexts are ignored.
- Non-fatal/signature path: current GA-style `put_task(query, source='user', images=None)` behavior is preserved and not patched.
- nmem acceptance: create/append results are verified by readback via `get_thread_message_count(...)` in `NmemSessionArchive.save_turn`.
- Fallback/backfill: existing parser/manual scan tests remain in `tests/test_session_save.py`.

Still environment-gated before claiming real production telemetry:

- Run the bridge against a live nmem API instance and capture readback evidence from that API, not only the fake client used in unit acceptance.
- Confirm the deployed GenericAgent launcher calls `genericagent_session_hook.install(agent)` on the live agent instance before frontend traffic starts.

## Documentation rule

This community plugin directory is the SSOT for nmem GenericAgent plugin documentation. Future changes should start with a GitHub issue and land through a PR that references the issue.
