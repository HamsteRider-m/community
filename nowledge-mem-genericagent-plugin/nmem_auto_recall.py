"""nmem AutoRecall plugin for GenericAgent.

Registers hooks via agent_loop.py's native trigger points:
- agent_before (line 49): AutoRecall using nmem_recall.py tool
- llm_before  (line 58): strip redundant get_global_memory() injections

Uses the new nmem_recall.py tool for comprehensive recall:
- Memories Search (historical experiences)
- Threads Search (session history)
- Working Memory (current priorities)
- Entities & Graph (optional deep context)

Zero core changes. Supplements existing L1 and nmem_session.py.
SOP ref: nmem_genericagent_integration_sop.md, nmem_layered_read_sop.md
"""
import os
import re
import sys
from pathlib import Path
from plugins.hooks import register

# ============================================================
# Behavioral Guidance for nmem Tools
# ============================================================
# Injected into system prompt to guide LLM on when/how to use nmem.
# Cost: ~100 tokens. Based on nowledge-mem-bub-plugin best practices.

NMEM_BEHAVIORAL_GUIDANCE = """
You have access to the user's personal knowledge graph (Nowledge Mem / nmem).
It contains knowledge from all their tools and sessions — not just this conversation.

**Auto-recalled context** is already injected above (Working Memory + relevant threads/memories).
This gives you immediate context without extra tool calls.

**When to use nmem tools**:
- Use `nmem m show <id>` to read full memory content when the auto-recalled summary is insufficient
- Use `nmem t page <id>` to read full thread conversations (paginated, 10 messages at a time)
- Use `nmem m search <query>` for specific follow-ups beyond what was auto-recalled
- Use `nmem e search <name>` to find entities (people, projects, concepts)
- Use `nmem graph explore <entity>` to discover related context through the knowledge graph

**When to save**:
Save proactively when the conversation produces:
- Decisions, preferences, plans, procedures, learnings, or important context
- Do not wait to be asked — save as you go
- Use `nmem m add` with appropriate unit_type (fact/preference/decision/plan/procedure/learning/context)

**Verification**:
The auto-recalled content shows candidates only. When citing specific facts, verify with `nmem m show <id>` first.
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / 'memory'
TEMP_DIR = PROJECT_ROOT / 'temp'
AUTORECALL_DONE_ATTR = '_nmem_autorecall_done'

# Add temp/nmem_capability_research to path for nmem_recall import
NMEM_RECALL_DIR = TEMP_DIR / 'nmem_capability_research'
if NMEM_RECALL_DIR.exists() and str(NMEM_RECALL_DIR) not in sys.path:
    sys.path.insert(0, str(NMEM_RECALL_DIR))

try:
    from nmem_recall import NmemRecall
    NMEM_RECALL_AVAILABLE = True
except ImportError:
    NMEM_RECALL_AVAILABLE = False
    print('[nmem_auto_recall] WARNING: nmem_recall.py not found, falling back to basic mode', file=sys.stderr)


def _extract_keywords(text, max_kw=5):
    """Extract keywords from user query for nmem search."""
    en_words = re.findall(r'[a-zA-Z]{4,}', text)
    en_words = sorted(set(w.lower() for w in en_words), key=len, reverse=True)
    cn_chars = re.findall(r'[\u4e00-\u9fff]+', text)
    cn_words = []
    for seg in cn_chars:
        for i in range(len(seg) - 1):
            cn_words.append(seg[i:i + 2])
    cn_words = sorted(set(cn_words), key=lambda w: cn_words.count(w), reverse=True)
    return (en_words + cn_words)[:max_kw]


def _generate_sop_index():
    """Generate dynamic SOP index from memory/ directory."""
    if not MEMORY_DIR.is_dir():
        return ''
    items = []
    for f in sorted(MEMORY_DIR.iterdir()):
        if f.suffix == '.md' and not f.name.startswith('_'):
            try:
                first_line = f.read_text(encoding='utf-8').split('\n')[0]
                name = first_line.lstrip('# ').strip()
                items.append(f'{f.stem} ({name})' if name else f.stem)
            except Exception:
                items.append(f.stem)
        elif f.suffix == '.py' and not f.name.startswith('_'):
            items.append(f.stem)
    if not items:
        return ''
    return 'L3: ' + ' | '.join(items)


def _do_recall_with_tool(user_query):
    """Use nmem_recall.py tool for comprehensive recall."""
    try:
        recall = NmemRecall()
        keywords = _extract_keywords(user_query)
        query = ' '.join(keywords[:3]) if keywords else user_query[:50]
        
        # Perform recall with WM, without graph (to save tokens)
        result = recall.recall(query, include_wm=True, include_graph=False)
        
        # Format for prompt injection (max 2KB)
        prompt_content = recall.format_for_prompt(result, max_tokens=500)
        
        return prompt_content
    except Exception as e:
        print(f'[nmem_auto_recall] Error using nmem_recall tool: {e}', file=sys.stderr)
        return ''


def _do_recall_fallback(user_query):
    """Fallback to basic nmem CLI calls if tool not available."""
    import subprocess
    
    def _run_nmem(args, timeout=10):
        try:
            r = subprocess.run(['nmem'] + args, capture_output=True,
                             text=True, timeout=timeout)
            return r.stdout.strip(), r.returncode == 0
        except Exception:
            return '', False
    
    space_args = ['--space', os.environ.get('NMEM_SPACE', '')] if os.environ.get('NMEM_SPACE') else []
    keywords = _extract_keywords(user_query)
    
    blocks = []
    
    # Working Memory
    wm_out, wm_ok = _run_nmem(['wm', 'read'] + space_args)
    if wm_ok and wm_out and len(wm_out) > 10:
        brief = wm_out[:500]
        if len(wm_out) > 500:
            brief += '\n... (truncated)'
        blocks.append(f'Working Memory:\n{brief}')
    
    # Threads
    if keywords:
        tout, tok = _run_nmem(['t', 'search'] + space_args + keywords[:3])
        if tok and tout and len(tout) > 5:
            lines = tout.strip().split('\n')[:5]
            block = 'Related Threads (candidates — verify with page/export):\n'
            for line in lines:
                if len(line) > 120:
                    line = line[:117] + '...'
                block += f'  {line}\n'
            blocks.append(block)
    
    # Memories
    if keywords:
        mout, mok = _run_nmem(['m', 'search'] + space_args + ['-n', '5'] + keywords[:3])
        if mok and mout and len(mout) > 5:
            lines = mout.strip().split('\n')[:5]
            block = 'Related Memories (candidates — verify before citing):\n'
            for line in lines:
                if len(line) > 150:
                    line = line[:147] + '...'
                block += f'  {line}\n'
            blocks.append(block)
    
    if blocks:
        content = '\n\n[AutoRecall from nmem]\n' + '\n\n'.join(blocks)
        content += '\n\n⚠️ 以上为候选摘要，非验证事实。需要精确引用时请用 nmem_tool page/export。\n'
        return content
    return ''


# ============================================================
# Hook: agent_before
# ============================================================

@register('agent_before')
def on_agent_before(ctx):
    """Inject nmem context at session start.
    
    ctx contains: messages, handler, client, turn, etc.
    Modifies ctx['messages'] in-place.
    """
    messages = ctx.get('messages')
    if not messages:
        return
    
    # --- Idempotency: only run once per session ---
    # Attach marker to the handler to survive locals() snapshots
    handler = ctx.get('handler')
    marker_target = handler if handler is not None else ctx
    if getattr(marker_target, AUTORECALL_DONE_ATTR, False):
        return
    setattr(marker_target, AUTORECALL_DONE_ATTR, True)
    
    # --- 1. Inject nmem behavioral guidance into system prompt ---
    if messages and messages[0].get('role') == 'system':
        messages[0]['content'] = messages[0]['content'] + '\n' + NMEM_BEHAVIORAL_GUIDANCE
    
    # --- 2. Dynamic SOP index ---
    sop_index = _generate_sop_index()
    if sop_index and messages and messages[0].get('role') == 'system':
        messages[0]['content'] = messages[0]['content'] + f'\n[SOP Index]\n{sop_index}\n'
    
    # --- 3. AutoRecall ---
    if len(messages) < 2:
        return
    
    # Extract user query from first user message
    user_query = ''
    for m in messages:
        if m.get('role') == 'user':
            user_query = m.get('content', '')
            if user_query:
                break
    if not user_query:
        return
    
    # Perform recall using tool or fallback
    if NMEM_RECALL_AVAILABLE:
        recall_content = _do_recall_with_tool(user_query)
    else:
        recall_content = _do_recall_fallback(user_query)
    
    # Inject into system prompt
    if recall_content and messages[0].get('role') == 'system':
        messages[0]['content'] += recall_content


# ============================================================
# Pattern for get_global_memory() injection block
# ============================================================

GM_PATTERN = re.compile(
    r'\n\[Memory\] \(\.\./memory\)\n.*?Read L2 or ls \.\./memory/ for L3 when needed\n',
    re.DOTALL
)

# ============================================================
# Hook: llm_before
# ============================================================

@register('llm_before')
def on_llm_before(ctx):
    """Strip redundant get_global_memory() injections.
    
    Keep first occurrence (in system prompt), strip 2nd+ (every 10 turns).
    ctx contains: messages, turn, client, handler, etc.
    Modifies ctx['messages'] in-place.
    """
    messages = ctx.get('messages')
    if not messages:
        return
    
    count = sum(
        1 for m in messages
        if m.get('role') == 'user' and GM_PATTERN.search(m.get('content', ''))
    )
    if count <= 1:
        return  # Only first occurrence → keep it
    
    seen_first = False
    for m in messages:
        if m.get('role') != 'user':
            continue
        content = m.get('content', '')
        match = GM_PATTERN.search(content)
        if match:
            if not seen_first:
                seen_first = True
                continue
            new_content = GM_PATTERN.sub('', content).strip()
            if new_content:
                m['content'] = new_content
