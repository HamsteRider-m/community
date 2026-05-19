# GenericAgent Plugin Notes

This document provides operational guidance for GenericAgent when integrated with Nowledge Mem. It is designed to be read by the agent at startup or when working memory context is needed.

---

## Operating Model

GenericAgent operates in a **hybrid-aware, hook-assisted** mode when integrated with Nowledge Mem:

- **Hybrid-aware**: The agent is aware of both its local memory system (L1-L4 layers in `memory/`) and the external Nowledge Mem system. Local memory remains the primary source of truth for SOPs, tools, and working checkpoints. Nowledge Mem serves as an external L4 layer for long-term project context, cross-session handoffs, and searchable knowledge.

- **Hook-assisted**: The integration uses a wrapper (`run_genericagent_with_nmem.py`) that patches the system prompt builder to inject Nowledge working memory at the start of each conversation. This ensures the agent has access to relevant context without modifying GenericAgent's core files.

- **SOP-first**: GenericAgent's existing SOPs (in `memory/*.md`) take precedence. Nowledge Mem is used to supplement, not replace, these SOPs. When a conflict arises, follow the local SOP and use `nmem` to record the decision for future reference.

- **Minimal context injection**: The integration injects only the working memory (via `nmem wm read`), not the entire Nowledge Mem database. This keeps the system prompt lean and focused. Additional context is retrieved on-demand using `nmem search` or `nmem page`.

---

## Working Memory

**What it is**: Nowledge working memory is a short-term, high-priority context buffer that persists across GenericAgent sessions. It typically contains:
- Current project focus or active task
- Key constraints or user preferences
- Recent decisions or findings that should inform the next session
- Cross-session handoffs (e.g., "Continue implementing feature X")

**When to read**:
1. **Session start**: Automatically injected into the system prompt by the wrapper. Review it to understand the current context.
2. **User request**: When the user explicitly asks to recall something (e.g., "What were we working on?").
3. **Idle resume**: When resuming after a long pause or context switch, check working memory to re-orient.

**When to update**:
- **Task completion**: After finishing a significant task, use `nmem wm add "Task X completed. Next: Y"` to set up the next session.
- **Context switch**: When switching projects or focus areas, clear old context with `nmem wm clear` and add new context.
- **Key decisions**: When making an important decision (e.g., choosing a design pattern), record it in working memory so future sessions don't revisit the same question.

**How to update**:
```bash
# Add to working memory
nmem wm add "Currently implementing GenericAgent nmem plugin. Focus: test coverage."

# Read working memory
nmem wm read

# Clear working memory
nmem wm clear
```

---

## Proactive Search

**Purpose**: Retrieve relevant context from Nowledge Mem before starting a task, to avoid reinventing the wheel or missing important constraints.

**When to search** (strong signals):
- User mentions a **specific project, feature, or past decision** (e.g., "Continue the nmem integration work").
- User asks a **question that requires historical context** (e.g., "Why did we choose approach X?").
- Starting a **new task in a familiar domain** (e.g., "Add tests for the plugin" → search for "GenericAgent testing patterns").
- User explicitly requests a search (e.g., "Search nmem for X").

**When to search** (weak signals):
- User mentions a **general topic** that might have prior context (e.g., "Fix the bug" → search for "GenericAgent bug fixes").
- Starting a **complex task** that likely has prior art (e.g., "Integrate with external API" → search for "GenericAgent API integration").

**When to skip**:
- **Simple, self-contained tasks** (e.g., "Fix typo in README").
- **Tasks with explicit instructions** (e.g., "Run this command: ...").
- **First-time tasks** with no prior context (e.g., "Set up a new project").
- **Search already failed** (don't retry the same query without refining it).

**How to search**:
```bash
# Basic search
nmem search "GenericAgent testing patterns"

# Search with filters
nmem search "nmem integration" --label genericagent --unit-type learning

# Search with date range
nmem search "bug fixes" --after 2026-05-01
```

**Interpreting results**:
- Search returns **summaries**, not full content. Use `nmem page <id>` to read the full memory if needed.
- **Don't treat summaries as evidence**. If a decision or fact is critical, verify it by reading the full memory or checking the source.
- If search returns too many results, refine the query or add filters (e.g., `--label`, `--unit-type`, `--after`).

---

## Distill

**Purpose**: Save a concise summary of the current conversation or task into Nowledge Mem for future reference.

**When to distill**:
- **Task completion**: After finishing a significant task (e.g., "Implemented feature X with approach Y").
- **Key decision**: After making an important decision (e.g., "Chose library Z over W because...").
- **Learning**: After discovering a useful pattern or solving a tricky problem (e.g., "GenericAgent wrapper pattern works by...").
- **Handoff**: When ending a session with work in progress (e.g., "Paused at step 3 of 5. Next: implement step 4").

**When to skip**:
- **Simple tasks** (e.g., "Fixed typo").
- **Failed attempts** (unless the failure itself is a learning, e.g., "Approach X doesn't work because...").
- **Redundant information** (if the same context is already in Nowledge Mem, don't duplicate it).

**Search first to avoid duplication**:
Before distilling, search Nowledge Mem to check if similar context already exists. If it does, either skip the distill or update the existing memory (if supported).

**How to distill**:
```bash
# Save a learning
nmem m add "GenericAgent wrapper pattern: use monkey patching to inject nmem context without modifying core files" \
  -t "GenericAgent integration pattern" \
  -l genericagent \
  --unit-type learning

# Save a decision
nmem m add "Chose pytest over unittest for GenericAgent plugin tests because pytest has better fixture support" \
  -t "Testing framework decision" \
  -l genericagent \
  --unit-type decision

# Save a handoff
nmem m add "GenericAgent nmem plugin: completed AGENTS.md and unit tests. Next: implement e2e tests" \
  -t "GenericAgent handoff" \
  -l genericagent \
  --unit-type learning
```

---

## Save Thread

**Purpose**: Save the entire conversation thread (including user messages and agent responses) into Nowledge Mem for future reference.

**When to save**:
- **Automatic** (if Stop hook is implemented): The thread is automatically saved when the agent exits.
- **Manual**: Use `nmem t create` to save the thread manually if the automatic hook is not available.

**How to save manually**:
```bash
# Save the current thread
nmem t create --title "GenericAgent nmem plugin development" \
  --label genericagent \
  --from-file temp/model_responses/model_responses_<session_id>.txt
```

**Note**: GenericAgent's current implementation does not have an automatic Stop hook. Thread saving must be done manually or via an external process that monitors `temp/model_responses/`.

---

## Remote

**Purpose**: Use Nowledge Mem in remote mode to share context across multiple machines or with other agents.

**When to use remote**:
- **Cross-platform collaboration**: When working on the same project from multiple machines (e.g., laptop + desktop).
- **Multi-agent collaboration**: When multiple agents (e.g., GenericAgent + Codex) need to share context.
- **Centralized knowledge base**: When you want a single source of truth for project context.

**How to configure remote**:
1. Set up a remote Nowledge Mem server (see Nowledge Mem documentation).
2. Configure GenericAgent to use the remote server:
   ```bash
   nmem config client set url https://your-nmem-server.com
   nmem config client set api-key your-api-key
   ```
3. Verify the connection:
   ```bash
   nmem status
   ```

**MCP support**:
- Nowledge Mem supports MCP (Model Context Protocol) for direct integration with MCP-compatible hosts.
- GenericAgent does not natively support MCP. If you need MCP integration, use the `nmem config mcp show` command to generate MCP configuration for your host, then configure the host (not GenericAgent) to use it.
- Remote/custom configs can be generated with `nmem config mcp show --host <host>` after setting the client URL and API key.
- Direct MCP clients do not automatically read `~/.nowledge-mem/config.json`; configure the host MCP settings explicitly.

**Space/SSOT strategy**:
- By default, GenericAgent uses the local `nmem` instance without setting a space.
- For long-term projects or multi-agent collaboration, set a space before starting:
  ```bash
  export NMEM_SPACE="<project-or-agent-lane>"
  ```
- Only select a lane; do not redefine space profiles.
- When collaborating across platforms, ensure all hosts point to the same Mem server and space.
- If space affects retrieval scope, document the current `NMEM_SPACE` in your working checkpoint.

---

## Failure and Degradation

**CLI not available**:
- First, confirm the error and environment state (e.g., `which nmem`, `nmem status`).
- Don't immediately assume nmem data doesn't exist; the issue might be a PATH or installation problem.

**Search not ready**:
- Fall back to navigation commands: `nmem page`, `nmem export`, or list-based browsing.
- Document the degraded retrieval capability in your working checkpoint.

**Page/export fails**:
- Read the error message and check `nmem help` or API status.
- Don't retry the same command more than 3 times without changing the approach.

**Remote Mem unavailable**:
- Degrade to local memory (`memory/` in GenericAgent).
- If necessary, write handoffs to `temp/` and import them to nmem when the connection is restored.

**Hook trimming**:
- Distinguish between "save-time trimming" (intentional summarization) and "read-time pagination" (rate limiting).
- For fact verification, prioritize reading the source/path directly rather than relying on summaries.

---

## GenericAgent Adaptation Red Lines

**Do not**:
- Treat nmem as a prompt dump. Don't inject 30K characters of context into the system prompt.
- Dump MCP documentation, tool schemas, path trees, or long results into the context all at once. Extract only the minimal rules and evidence needed.
- Assume GenericAgent natively supports MCP. Real MCP is an optional execution channel; default to SOP-first.
- Let nmem replace L1 startup navigation (global_mem_insight.txt).
- Let nmem replace L3 SOPs (executable rules in `memory/*.md`).
- Treat search summaries as evidence. Always verify critical facts by reading the full memory or source.
- Read or move key/secret files (e.g., `.env`, private keys).
- Directly modify nowledge plugin installation files. Use GenericAgent SOPs, tool scripts, or host overrides instead.
- Claim "memory is saved and available" just because auto-capture exists. Always verify.

---

## Maintenance

- When Nowledge MCP tools, host plugins, `nmem` CLI, or community registry change, re-fetch `integrations.json` and related READMEs to verify.
- The maintenance focus is not to copy MCP information, but to compress new/changed MCP/plugin behaviors into GenericAgent-executable SOPs, scripts, or minimal evidence rules.
- If GenericAgent explicitly supports real MCP in the future, still follow the small-context principle: prioritize SOP decomposition and on-demand fragment reading. Prohibit full injection of external memory layers.
- L1 (global_mem_insight.txt) should only index this file name, not the details of this SOP.
