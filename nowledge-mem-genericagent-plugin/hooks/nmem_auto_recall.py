"""nmem AutoRecall plugin for GenericAgent.

Registers 2 hooks via agent_loop.py's native trigger points:
- agent_before (line 49): AutoRecall + dynamic SOP index
- llm_before  (line 58): strip redundant get_global_memory() injections

Zero core changes. Supplements (not replaces) existing L1 and nmem_session.py.
SOP ref: nmem_genericagent_integration_sop.md, nmem_layered_read_sop.md

Calling convention: hooks receive ctx=locals() dict from agent_loop.py.
Hooks modify ctx['messages'] in-place; return value ignored by trigger().
"""
import os
import re
import subprocess
from pathlib import Path
from plugins.hooks import register

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / 'memory'
AUTORECALL_DONE_ATTR = '_nmem_autorecall_done'
NMEM_CLI = 'nmem'
TIMEOUT = 10
SPACE = os.environ.get('NMEM_SPACE', '')


def _run_nmem(args, timeout=TIMEOUT):
    """Run nmem CLI. Returns (stdout, stderr, success)."""
    try:
        r = subprocess.run([NMEM_CLI] + args, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode == 0
    except Exception as e:
        return '', str(e), False


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


def _build_wm_block(wm_text):
    if not wm_text or len(wm_text) < 10:
        return ''
    brief = wm_text[:500]
    if len(wm_text) > 500:
        brief += '\n... (truncated)'
    return f'Working Memory:\n{brief}'


def _build_thread_block(threads_text):
    if not threads_text or len(threads_text) < 5:
        return ''
    lines = threads_text.strip().split('\n')[:5]
    block = 'Related Threads (candidates \u2014 verify with page/export):\n'
    for line in lines:
        if len(line) > 120:
            line = line[:117] + '...'
        block += f'  {line}\n'
    return block


def _build_memory_block(memories_text):
    if not memories_text or len(memories_text) < 5:
        return ''
    lines = memories_text.strip().split('\n')[:5]
    block = 'Related Memories (candidates \u2014 verify before citing):\n'
    for line in lines:
        if len(line) > 150:
            line = line[:147] + '...'
        block += f'  {line}\n'
    return block


def _generate_sop_index():
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


# ============================================================
# Hook: agent_before
# ============================================================

@register('agent_before')
def on_agent_before(ctx):
    """AutoRecall + dynamic SOP index (first run only).
    ctx contains: messages, system_prompt, user_input, client, handler, etc.
    Modifies ctx['messages'] in-place."""
    messages = ctx.get('messages')
    if not messages:
        return

    # --- Idempotency: use a marker on the handler to survive locals() snapshots ---
    handler = ctx.get('handler')
    marker_target = handler if handler is not None else ctx
    if getattr(marker_target, AUTORECALL_DONE_ATTR, False):
        return
    setattr(marker_target, AUTORECALL_DONE_ATTR, True)

    # --- 1. Dynamic SOP index ---
    sop_index = _generate_sop_index()
    if sop_index and messages and messages[0].get('role') == 'system':
        messages[0]['content'] = messages[0]['content'] + f'\n[SOP Index]\n{sop_index}\n'

    # --- 2. AutoRecall ---
    if len(messages) < 2:
        return

    user_query = ''
    for m in messages:
        if m.get('role') == 'user':
            user_query = m.get('content', '')
            if user_query:
                break
    if not user_query:
        return

    space_args = ['--space', SPACE] if SPACE else []

    wm_out, wm_err, wm_ok = _run_nmem(['wm', 'read'] + space_args)
    wm_block = _build_wm_block(wm_out) if wm_ok else ''

    keywords = _extract_keywords(user_query)
    thread_block = ''
    if keywords:
        tout, terr, tok = _run_nmem(['t', 'search'] + space_args + keywords[:3])
        if tok:
            thread_block = _build_thread_block(tout)

    memory_block = ''
    if keywords:
        mout, merr, mok = _run_nmem(['m', 'search'] + space_args + ['-n', '5'] + keywords[:3])
        if mok:
            memory_block = _build_memory_block(mout)

    if wm_block or thread_block or memory_block:
        block = '\n\n[AutoRecall from nmem]\n'
        if wm_block:
            block += wm_block + '\n\n'
        if thread_block:
            block += thread_block + '\n'
        if memory_block:
            block += memory_block + '\n'
        block += '\u26a0\ufe0f \u4ee5\u4e0a\u4e3a\u5019\u9009\u6458\u8981\uff0c\u975e\u9a8c\u8bc1\u4e8b\u5b9e\u3002\u9700\u8981\u7cbe\u786e\u5f15\u7528\u65f6\u8bf7\u7528 nmem_tool page/export\u3002\n'
        messages[0]['content'] += block


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
    Modifies ctx['messages'] in-place."""
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
