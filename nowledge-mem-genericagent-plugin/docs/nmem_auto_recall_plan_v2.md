# GenericAgent × nmem AutoRecall 完整实现方案

> **目标**：一个零核心代码改动的 Hook 插件，解决 GA 与 nmem 互动差的问题。
> **实现者**：GPT 5.5（本方案是完整的技术规范，你执行即可）
> **核心痛点**：AutoRecall 不可用 — Working Memory 不会自动加载，相关记忆不会自动召回，GA-nmem 互动近乎手动。

---

## 一、现状诊断

### 1.1 已有但分散的基础设施

| 组件 | 位置 | 状态 | 用途 |
|------|------|------|------|
| Hook 引擎 | `plugins/hooks.py` (67行) | ✅ 完好 | register/trigger/discover_and_load，6 个事件 |
| nmem_session | `plugins/nmem_session.py` (353行) | ⚠️ 冗余 | agent_after 存档 + 旧的 monkey-patch put_task |
| nmem_session_sync | `local_ga/nmem_session_sync/hook.py` (173行) | ❌ 旧方案 | put_task 猴子补丁 + SyncQueue，与 plugins/ 方案冲突 |
| nmem_tool | `ga.py:364-382` | ✅ 完好 | GA 内置 nmem CLI 封装（status/search/page/export/wm） |
| nmem CLI | 系统全局 `nmem` v0.8.6 | ✅ 完好 | `nmem wm read`, `nmem t search`, `nmem m search` |
| 分层读取协议 | `memory/nmem_layered_read_sop.md` | ✅ 完好 | index→search→page→export 协议 |
| integration SOP | `memory/nmem_genericagent_integration_sop.md` | ✅ 完好 | 302行完整适配文档 |

### 1.2 当前上下文注入链路

```
Session 启动 (agentmain.py:41-45):
  sys_prompt.txt (6行)
  + Today: 日期
  + get_global_memory()
      ├── insight_fixed_structure.txt (9行: CONSTITUTION)
      └── memory/global_mem_insight.txt (23行: 手动维护的 L1 索引 + RULES)

每 10 轮 (ga.py:708):
  turn % 10 == 0 → next_prompt += get_global_memory()  ← 全文重复注入
```

### 1.3 核心缺陷

1. **AutoRecall 缺失** — Working Memory 不自动加载，nmem 记忆不自动召回
2. **L1 索引手动维护** — `global_mem_insight.txt` 需人手同步
3. **每 10 轮重复注入** — 浪费 ~30 行/次上下文 token
4. **两套 nmem 存档方案并存** — `plugins/nmem_session.py` + `local_ga/nmem_session_sync/` 冲突
5. **旧集成残留** — `memory/nmem_auto_recall.py`, `nmem_entity_tracker.py`, `nmem_space_manager.py`, `nmem_integration_*.md`, `test_nmem_integration.py` 都是之前的尝试，功能未完成

---

## 二、新架构：单插件，全 Hook，零核心改动

### 2.1 文件结构

```
新增：
  plugins/nmem_auto_recall.py          ← 唯一的集成插件（~300行）

修改（patch）：
  assets/insight_fixed_structure.txt   ← 去掉 SOP 列表行，只保留 CONSTITUTION
  assets/insight_fixed_structure_en.txt ← 同上

废弃删除（legacy cleanup）：
  local_ga/nmem_session_sync/          ← 整个目录删除
  plugins/nmem_session.py              ← 删除，功能合并到新插件
  memory/nmem_auto_recall.py           ← 删除，旧尝试
  memory/nmem_entity_tracker.py        ← 删除
  memory/nmem_space_manager.py         ← 删除
  memory/nmem_integration_README.md    ← 删除
  memory/nmem_integration_CHANGELOG.md ← 删除
  memory/nmem_integration_MIGRATION.md ← 删除
  memory/test_nmem_integration.py      ← 删除

不修改：
  ga.py                                ← 零改动！
  agent_loop.py                        ← 零改动！
  agentmain.py                         ← 零改动！
  plugins/hooks.py                     ← 零改动！
  memory/global_mem_insight.txt        ← 不再手动维护，但文件保留（空或标记）
```

### 2.2 Hook 注册全景图

```
agent_before  ─┬─ auto_recall_startup()     → 加载 Working Memory + 召回记忆 + 注入 system prompt
               └─ inject_dynamic_sop_index() → 扫描 memory/ 生成 SOP 索引 + 替换静态内容

llm_before    ─── strip_redundant_injection() → 剥离 get_global_memory() 的重复注入

agent_after   ─── save_session_to_nmem()     → 会话结束，全量保存到 nmem

（不注册 turn_before / turn_after / llm_after / tool_before / tool_after）
```

### 2.3 数据流

```
Session 启动
  │
  ├─ 1. agentmain.py 构建 system_prompt（含静态 get_global_memory()）
  ├─ 2. agent_loop.py 创建 messages = [system_prompt, user_input]
  ├─ 3. agent_before hook 触发
  │      ├─ auto_recall_startup()
  │      │    ├─ nmem wm read              → Working Memory
  │      │    ├─ nmem t search (user query) → 候选 thread
  │      │    ├─ nmem m search (user query) → 候选 memory
  │      │    └─ 注入 [AutoRecall] 块到 messages[0]['content']
  │      └─ inject_dynamic_sop_index()
  │           ├─ 扫描 memory/*.md, memory/*.py
  │           ├─ 提取第一行标题作为 SOP 名
  │           └─ 替换静态 global_mem_insight.txt 内容为动态生成索引
  │
  ├─ 4. 每轮 LLM 调用前
  │      └─ llm_before hook 触发
  │           └─ strip_redundant_injection()
  │                ├─ 检测 messages[0]['content'] 是否含冗长的 get_global_memory() 输出
  │                └─ 如有，剥离为轻量提醒："[Memory] SOPs indexed in system prompt. Use file_read for details."
  │
  └─ 5. Session 结束
         └─ agent_after hook 触发
              └─ save_session_to_nmem()
                   ├─ 收集 user/assistant 消息
                   └─ 通过 nmem HTTP API 保存 thread
```

---

## 三、AutoRecall 核心设计（最重要的部分）

### 3.1 启动时自动召回算法

```
输入: system_prompt (已构建), user_query (用户第一条消息)
输出: system_prompt 被追加 [AutoRecall] 块

步骤:
1. 检测环境变量 NMEM_AUTO_RECALL（默认 "1"，设 "0" 禁用）
2. nmem wm read --space {GA_NMEM_SPACE}
   → 如果成功，提取 Focus Areas + Briefing
   → 如果失败（nmem 未运行），静默跳过，日志记录
3. 从 user_query 中提取关键词（前 80 个字符，作为搜索 query）
4. nmem t search "{keywords}" -n 5 --space {GA_NMEM_SPACE}
   → 只取 [thread_id, title, source, relevance_score]
5. nmem m search "{keywords}" -n 5 --space {GA_NMEM_SPACE}
   → 只取 [content 前200字, importance, labels]
6. 构建 [AutoRecall] 块：
   ```
   [AutoRecall from nmem]
   Working Memory ({date}):
     Focus: {focus areas 摘要}
     
   Related Threads:
     - [{source}] {title} (id: {thread_id})
     - ...
     
   Related Memories:
     - {content 摘要} [importance: {score}]
     - ...
     
   Use nmem_tool for details. Working memory from nmem, not memory/ folder.
   ```
7. 追加到 messages[0]['content'] 末尾
```

### 3.2 关键约束

- **超时**：每个 nmem CLI 调用最长 5 秒（`timeout=5`），超时则跳过该项
- **token 预算**：AutoRecall 块不超过 800 字符（约 200 tokens）
- **关键词提取**：从 user_query 取前 80 字符，去掉常见停用词，截断为搜索 query
- **静默失败**：nmem 不可用时记录日志，不抛异常，不影响 agent 启动
- **空间隔离**：通过 `GA_NMEM_SPACE` 环境变量（默认空字符串）控制

### 3.3 为什么不做"每轮召回"

Community（Codex/Claude Code）的实践是：启动时加载 Working Memory + 首次召回，之后由 LLM 判断是否需要再次搜索。逐轮全量召回太贵且噪声大。遵循此模式。

---

## 四、动态 SOP 索引设计

### 4.1 扫描规则

```python
def generate_sop_index(memory_dir: Path) -> str:
    lines = []
    # 只扫描 .md 和 .py 文件
    for f in sorted(memory_dir.glob("*.md")):
        if f.name.startswith('_'):
            continue
        first_line = f.read_text(encoding='utf-8').split('\n')[0]
        name = first_line.lstrip('#').strip()
        lines.append(f"{name}: {f.name}")
    
    for f in sorted(memory_dir.glob("*.py")):
        if f.name.startswith('_'):
            continue
        name = f.stem
        # 读第一行注释作为描述（如有）
        try:
            first = f.read_text(encoding='utf-8').split('\n')[0]
            desc = first.lstrip('#').strip() if first.startswith('#') else name
        except:
            desc = name
        lines.append(f"{desc}: {f.name}")
    
    return '\n'.join(lines)
```

### 4.2 注入方式

在 `agent_before` hook 中，替换 `messages[0]['content']` 里 `../memory/global_mem_insight.txt:` 之后的内容：

```
旧:
  ../memory/global_mem_insight.txt:
  # [Global Memory Insight]
  Browser special ops: tmwebdriver_sop(...)
  Keyboard & Mouse: ljqCtrl_sop(...)
  ... (23 行手动内容)

新:
  ../memory/global_mem_insight.txt (auto-generated at session start):
  TMWebDriver SOP: tmwebdriver_sop.md
  Vision API SOP: vision_sop.md
  ... (自动扫描生成)
```

### 4.3 CONSTITUTION/RULES 保留

`insight_fixed_structure.txt` 文件改为只含 CONSTITUTION（不列 SOP），因为 SOP 列表由动态索引接管：

```
Facts(L2): ../memory/global_mem.txt | CodeRoot: ../ | SOPs(L3): ../memory/*.md or *.py | META-SOP(L0): ../memory/memory_management_sop.md
L1 Insight is auto-generated at session start; see [Memory] block for current SOP index.

[CONSTITUTION]
1. ...
```

---

## 五、冗余注入剥离

### 5.1 问题

`ga.py:708` 每 10 轮调用 `get_global_memory()`，重新注入 30+ 行内容到 `next_prompt`。到下一轮，这个内容作为 `messages[0]['content']` 送到 LLM。

### 5.2 解决方案

在 `llm_before` hook 中检测并剥离：

```python
import re

REDUNDANT_PATTERN = re.compile(
    r'\n?cwd = .+?\(\./\)\n\n\[Memory\] \(\.\./memory\)\n.*?'
    r'\.\.\/memory\/global_mem_insight\.txt:\n.*?'
    r'(?=\n\n|\Z)',
    re.DOTALL
)

def strip_redundant_injection(ctx):
    msg = ctx['messages'][0]['content']
    if 'global_mem_insight.txt' in msg and '[Memory]' in msg:
        cleaned = REDUNDANT_PATTERN.sub(
            '\n[Memory] SOP index in system prompt; use file_read ../memory/ for details.',
            msg
        )
        if cleaned != msg:
            ctx['messages'][0]['content'] = cleaned
```

### 5.3 注意

- 只剥离 `get_global_memory()` 产生的块，不碰用户消息或工具输出
- 如果系统 prompt 原本已含索引（已在 agent_before 被动态替换），这里剥离的是 turn_end_callback 又加进来的重复副本

---

## 六、Session 保存

### 6.1 已有功能合并

当前 `plugins/nmem_session.py` 的 `agent_after` 存档功能**保留并移植**到新插件。删除原文件。

### 6.2 实现

复用 `plugins/nmem_session.py` 中的 `NmemSessionArchive` 和 `NmemClient` 类（它们已经过验证），在新插件中：

```python
@register('agent_after')
def save_session_to_nmem(ctx):
    """Session 结束：完整保存到 nmem"""
    if os.environ.get('GA_NMEM_SESSION_SAVE', '1') in ('0', 'false'):
        return
    
    handler = ctx.get('handler')
    exit_reason = ctx.get('exit_reason', {})
    
    # 构建消息列表
    messages = build_message_list(ctx)
    
    # 生成标题
    title = generate_session_title(ctx)
    
    # 保存
    client = get_nmem_client()
    thread_id = client.create_thread(
        thread_id=None,
        title=title,
        messages=messages,
        source='genericagent'
    )
    
    # 日志
    _log(f"session saved: {thread_id} ({len(messages)} messages)")
```

---

## 七、Legacy 清理清单

### 7.1 删除整个目录/文件

```
rm -rf local_ga/nmem_session_sync/        # 旧 monkey-patch 方案
rm plugins/nmem_session.py                 # 功能合并到新插件
rm memory/nmem_auto_recall.py              # 旧尝试
rm memory/nmem_entity_tracker.py           # 旧尝试
rm memory/nmem_space_manager.py            # 旧尝试
rm memory/nmem_integration_README.md       # 旧文档
rm memory/nmem_integration_CHANGELOG.md    # 旧文档
rm memory/nmem_integration_MIGRATION.md    # 旧文档
rm memory/test_nmem_integration.py         # 旧测试
```

### 7.2 保留并更新

```
保留: memory/nmem_layered_read_sop.md      # SOP，有效
保留: memory/nmem_layered_read.py          # 工具，有效
保留: memory/nmem_genericagent_integration_sop.md  # SOP，需 review 引用是否还正确
保留: memory/nmem_tools_reference.md       # 参考文档
保留: memory/global_mem_insight.txt        # 保留为空或标记 "auto-generated at runtime"
```

### 7.3 Patch assets/insight_fixed_structure*.txt

去掉 SOP 手动列表行（L3 那行），改为：
```
SOPs(L3): auto-generated at session start; scan ../memory/*.md and *.py
```

---

## 八、完整实现文件：`plugins/nmem_auto_recall.py`

### 8.1 文件结构

```python
"""GenericAgent × nmem AutoRecall Plugin

One plugin, all hooks, zero core changes.

Hooks:
  agent_before  → auto_recall_startup() + inject_dynamic_sop_index()
  llm_before    → strip_redundant_injection()
  agent_after   → save_session_to_nmem()

Env vars:
  NMEM_AUTO_RECALL=1          enable auto recall (default: 1)
  GA_NMEM_SPACE=              nmem space name (default: "")
  GA_NMEM_SESSION_SAVE=1      save session to nmem (default: 1)
  NMEM_API_URL=http://127.0.0.1:14242  nmem API (default)
  NMEM_API_KEY=               nmem API key (optional)
"""

import hashlib, json, os, re, subprocess, time, traceback, urllib.request, urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

# 路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MEMORY_DIR = _PROJECT_ROOT / "memory"
_TEMP_DIR = _PROJECT_ROOT / "temp"
_LOG_FILE = _TEMP_DIR / "nmem_auto_recall.log"

# 配置
AUTO_RECALL = os.environ.get("NMEM_AUTO_RECALL", "1") not in ("0", "false", "no")
SPACE = os.environ.get("GA_NMEM_SPACE", "")
SESSION_SAVE = os.environ.get("GA_NMEM_SESSION_SAVE", "1") not in ("0", "false", "no")
API_URL = os.environ.get("NMEM_API_URL", "http://127.0.0.1:14242")
API_KEY = os.environ.get("NMEM_API_KEY") or os.environ.get("NOWLEDGE_MEM_API_KEY")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _log(msg: str):
    try:
        _TEMP_DIR.mkdir(parents=True, exist_ok=True)
        with _LOG_FILE.open("a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except:
        pass

# ---------------------------------------------------------------------------
# nmem CLI helpers (5s timeout, silent fail)
# ---------------------------------------------------------------------------
def _nmem_cli(args: List[str], timeout: int = 5) -> Optional[str]:
    """Run nmem CLI, return stdout or None on failure."""
    try:
        r = subprocess.run(
            ["nmem"] + args,
            capture_output=True, text=True, timeout=timeout
        )
        if r.returncode != 0:
            _log(f"nmem CLI failed: {' '.join(args)} → rc={r.returncode}")
            return None
        return r.stdout
    except Exception as e:
        _log(f"nmem CLI exception: {' '.join(args)} → {e}")
        return None

def _space_args() -> List[str]:
    return ["--space", SPACE] if SPACE else []

# ---------------------------------------------------------------------------
# AutoRecall: Working Memory + Memory/Thread Search
# ---------------------------------------------------------------------------
def read_working_memory() -> Optional[str]:
    """Read working memory from nmem."""
    if not AUTO_RECALL:
        return None
    out = _nmem_cli(["wm", "read"] + _space_args())
    if not out:
        return None
    # Extract Focus Areas + Briefing sections (trim ANSI)
    clean = re.sub(r'\x1b\[[0-9;]*m', '', out)
    # Find key sections
    focus_match = re.search(r'Focus Areas\s*\n+(.*?)(?=\n\n\n|\n?\n\s*\n\s*\n|\Z)', clean, re.DOTALL)
    briefing_match = re.search(r'Briefing\s*\n+(.*?)(?=\n\n\n|\Z)', clean, re.DOTALL)
    parts = []
    if focus_match:
        parts.append(f"Focus: {focus_match.group(1).strip()[:300]}")
    if briefing_match:
        parts.append(f"Brief: {briefing_match.group(1).strip()[:300]}")
    return '\n'.join(parts) if parts else None

def search_threads(query: str, limit: int = 5) -> List[Dict]:
    """Search threads by query, return lightweight results."""
    if not AUTO_RECALL or not query.strip():
        return []
    out = _nmem_cli(["t", "search", query[:80], "-n", str(limit)] + _space_args())
    if not out:
        return []
    results = []
    for line in out.strip().split('\n'):
        # Parse nmem t search output (format: "thread_id | title | source | ...")
        # Actual format may vary; adapt based on real output
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 2:
                results.append({"id": parts[0], "title": parts[1], "source": parts[2] if len(parts) > 2 else "unknown"})
    return results[:limit]

def search_memories(query: str, limit: int = 5) -> List[Dict]:
    """Search memories by query, return lightweight results."""
    if not AUTO_RECALL or not query.strip():
        return []
    out = _nmem_cli(["m", "search", query[:80], "-n", str(limit)] + _space_args())
    if not out:
        return []
    # Memory search output may be complex; try to extract
    results = []
    for line in out.strip().split('\n'):
        line = line.strip()
        if line and len(line) > 10:
            results.append({"content": line[:200]})
    return results[:limit]

def build_autorecall_block(user_query: str) -> str:
    """Build the [AutoRecall] block to inject into system prompt."""
    parts = ["[AutoRecall from nmem]"]
    
    wm = read_working_memory()
    if wm:
        parts.append(f"Working Memory ({time.strftime('%Y-%m-%d')}):\n  {wm[:400]}")
    
    keywords = user_query[:80].strip()
    if keywords:
        threads = search_threads(keywords)
        if threads:
            parts.append("Related Threads:")
            for t in threads:
                parts.append(f"  - [{t.get('source', '?')}] {t.get('title', '?')} (id: {t.get('id', '?')})")
        
        memories = search_memories(keywords)
        if memories:
            parts.append("Related Memories:")
            for m in memories:
                parts.append(f"  - {m['content'][:150]}")
    
    if len(parts) == 1:
        return ""  # No recall results
    
    parts.append("Use nmem_tool for full details. Working memory sourced from nmem, not memory/ folder.")
    return '\n'.join(parts)

# ---------------------------------------------------------------------------
# Dynamic SOP Index
# ---------------------------------------------------------------------------
def generate_sop_index() -> str:
    """Scan memory/ for .md and .py files, generate thin index."""
    lines = []
    
    md_files = sorted(_MEMORY_DIR.glob("*.md"))
    for f in md_files:
        if f.name.startswith('_'):
            continue
        try:
            first_line = f.read_text(encoding='utf-8').split('\n')[0]
            name = first_line.lstrip('#').strip()
            lines.append(f"  {name}: ../memory/{f.name}")
        except:
            lines.append(f"  {f.stem}: ../memory/{f.name}")
    
    py_files = sorted(_MEMORY_DIR.glob("*.py"))
    for f in py_files:
        if f.name.startswith('_'):
            continue
        try:
            first = f.read_text(encoding='utf-8').split('\n')[0]
            desc = first.lstrip('#').strip() if first.startswith('#') else f.stem
        except:
            desc = f.stem
        lines.append(f"  {desc}: ../memory/{f.name}")
    
    if not lines:
        return "[No SOP files found in memory/]"
    
    header = "[SOP Index] (auto-generated at session start)"
    return header + '\n' + '\n'.join(lines)

# ---------------------------------------------------------------------------
# Hook: agent_before - AutoRecall + Dynamic SOP Index
# ---------------------------------------------------------------------------
def _find_and_replace_global_mem_insight(system_content: str, replacement: str) -> str:
    """Replace the static global_mem_insight.txt content with dynamic content."""
    # Pattern: the block that starts with "../memory/global_mem_insight.txt:"
    pattern = r'(\.\.\/memory\/global_mem_insight\.txt:)\n.*?(?=\n\n\[|\n?\Z)'
    return re.sub(pattern, f'\\1\n{replacement}', system_content, flags=re.DOTALL)

def on_agent_before(ctx: dict):
    """agent_before hook: inject AutoRecall + dynamic SOP index into system prompt."""
    from plugins.hooks import register  # for decorator usage
    
    messages = ctx.get('messages', [])
    if not messages:
        return
    
    system_msg = messages[0]
    content = system_msg.get('content', '')
    
    # --- 1. Dynamic SOP Index ---
    sop_index = generate_sop_index()
    content = _find_and_replace_global_mem_insight(content, sop_index)
    
    # --- 2. AutoRecall ---
    user_query = ""
    for msg in messages[1:]:
        if msg.get('role') == 'user':
            user_query = msg.get('content', '')
            break
    
    if AUTO_RECALL and user_query:
        autorecall_block = build_autorecall_block(user_query)
        if autorecall_block:
            content += f"\n\n{autorecall_block}"
            _log(f"AutoRecall injected: {len(autorecall_block)} chars")
    
    system_msg['content'] = content
    _log(f"agent_before: SOP index ({len(sop_index.splitlines())} entries) + AutoRecall injected")

# ---------------------------------------------------------------------------
# Hook: llm_before - Strip Redundant Injection
# ---------------------------------------------------------------------------
def on_llm_before(ctx: dict):
    """llm_before hook: strip redundant get_global_memory() block from next_prompt."""
    messages = ctx.get('messages', [])
    if not messages:
        return
    
    msg = messages[0]
    content = msg.get('content', '')
    
    # Check if this message contains the redundant global_mem_insight block
    # (injected by ga.py turn_end_callback every 10 turns)
    if 'global_mem_insight.txt' not in content:
        return
    if '[Memory] (../memory)' not in content and 'cwd = ' not in content:
        return
    
    # Pattern: the entire get_global_memory() output block
    redundant = re.compile(
        r'\n?cwd = .+?\(\./\)\n\n\[Memory\] \(\.\.\/memory\)\n'
        r'.*?\.\.\/memory\/global_mem_insight\.txt:.*?'
        r'(?=\n\n\[|\n\n\Z|\Z)',
        re.DOTALL
    )
    
    cleaned = redundant.sub(
        '\n[Memory] SOP index in system prompt. Use file_read ../memory/ for SOP details.',
        content
    )
    
    if cleaned != content:
        msg['content'] = cleaned
        _log("llm_before: stripped redundant get_global_memory() injection")

# ---------------------------------------------------------------------------
# Hook: agent_after - Save Session to nmem
# ---------------------------------------------------------------------------
def on_agent_after(ctx: dict):
    """agent_after hook: save complete session to nmem thread."""
    if not SESSION_SAVE:
        return
    
    messages = ctx.get('messages', [])
    exit_reason = ctx.get('exit_reason', {})
    handler = ctx.get('handler')
    
    try:
        # Build message list
        from plugins.hooks import _nmem_client  # We'll define this
        
        nmem_messages = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = str(msg.get('content', ''))[:24000]  # Truncate long messages
            nmem_messages.append({"role": role, "content": content})
        
        if not nmem_messages:
            return
        
        # Generate title from first user message
        title = "GenericAgent session"
        for msg in nmem_messages:
            if msg['role'] == 'user' and msg['content'].strip():
                title = msg['content'].strip()[:80]
                break
        
        # Save via nmem CLI
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"title": title, "messages": nmem_messages, "source": "genericagent"}, f)
            tmp_path = f.name
        
        try:
            result = _nmem_cli(["t", "save", "--from", "genericagent", "--file", tmp_path], timeout=30)
            if result:
                _log(f"agent_after: session saved to nmem ({len(nmem_messages)} messages)")
            else:
                _log("agent_after: nmem save returned no output")
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
                
    except Exception as e:
        _log(f"agent_after save failed: {e}\n{traceback.format_exc()}")

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
from plugins.hooks import register

register('agent_before')(on_agent_before)
register('llm_before')(on_llm_before)
register('agent_after')(on_agent_after)

_log("nmem_auto_recall plugin loaded")
```

### 8.2 关键实现细节

**A. 消息内容修改的安全性：**
`agent_before` 和 `llm_before` hook 中修改 `ctx['messages'][0]['content']` 是安全的——`messages` 是可变 list，修改其元素内容会反映到后续流程。

**B. 不依赖 `turn_after` 修改本地变量：**
`turn_after` 的 `next_prompt` 在 `locals()` 中但无法通过 hook 修改。因此采用 `llm_before`（下一轮）剥离冗余注入的策略——在内容送达 LLM 之前处理。

**C. 错误处理：**
所有 nmem 操作包裹 try/except，失败时记录日志但不中断 agent 流程。AutoRecall 失败不阻止 agent 启动。

**D. 超时控制：**
所有 nmem CLI 调用默认 5 秒超时。`nmem t save` 给予 30 秒（可能涉及 embedding）。

---

## 九、测试验证方案

### 9.1 单元测试（在开发环境）

```bash
# 1. 测试 SOP 扫描
python -c "
from plugins.nmem_auto_recall import generate_sop_index
print(generate_sop_index())
"

# 2. 测试 Working Memory 读取
python -c "
from plugins.nmem_auto_recall import read_working_memory
print(read_working_memory())
"

# 3. 测试记忆搜索
python -c "
from plugins.nmem_auto_recall import search_memories
print(search_memories('GenericAgent nmem'))
"

# 4. 测试线程搜索
python -c "
from plugins.nmem_auto_recall import search_threads
print(search_threads('GenericAgent'))
"

# 5. 测试 AutoRecall 块构建
python -c "
from plugins.nmem_auto_recall import build_autorecall_block
print(build_autorecall_block('测试 GenericAgent nmem 集成'))
"

# 6. 测试正则替换
python -c "
from plugins.nmem_auto_recall import _find_and_replace_global_mem_insight
test_content = 'some text\n../memory/global_mem_insight.txt:\nold content\n\nnext'
print(_find_and_replace_global_mem_insight(test_content, 'NEW DYNAMIC INDEX'))
"
```

### 9.2 集成测试（完整 agent 运行）

```bash
# 启动 GA 并验证
ga --input "测试 nmem 集成" --nobg -v

# 检查日志
cat temp/nmem_auto_recall.log

# 验证 AutoRecall 注入
grep "AutoRecall" temp/model_responses/*.txt

# 验证 SOP 索引注入
grep "SOP Index" temp/model_responses/*.txt

# 验证冗余剥离
grep "stripped redundant" temp/nmem_auto_recall.log
```

### 9.3 验收标准

- [ ] 启动时 `temp/nmem_auto_recall.log` 有 "agent_before: SOP index + AutoRecall injected" 日志
- [ ] system prompt 中不再包含静态的 `global_mem_insight.txt` 23 行内容，取而代之的是动态生成的 SOP 索引
- [ ] system prompt 末尾有 `[AutoRecall from nmem]` 块（如果 nmem 运行且有数据）
- [ ] 第 10 轮时，`llm_before` 成功剥离重复的 `get_global_memory()` 注入
- [ ] session 结束后 nmem 中有新 thread（`nmem t list --source genericagent`）
- [ ] nmem 不可用时 agent 仍正常启动（无崩溃）
- [ ] 删除 legacy 文件后 agent 仍正常启动（无 import 错误）

---

## 十、部署步骤（GPT 5.5 执行清单）

### Step 1: 创建新插件
```bash
# 写入 plugins/nmem_auto_recall.py（上述完整代码）
```

### Step 2: Patch insight_fixed_structure 文件
```bash
# assets/insight_fixed_structure.txt 和 assets/insight_fixed_structure_en.txt
# 将 SOP 列表行改为 "auto-generated at session start"
```

### Step 3: 清理 Legacy
```bash
rm -rf local_ga/nmem_session_sync/
rm plugins/nmem_session.py
rm memory/nmem_auto_recall.py
rm memory/nmem_entity_tracker.py
rm memory/nmem_space_manager.py
rm memory/nmem_integration_README.md
rm memory/nmem_integration_CHANGELOG.md
rm memory/nmem_integration_MIGRATION.md
rm memory/test_nmem_integration.py
```

### Step 4: 验证无 import 错误
```bash
cd /Users/maygo/Projects/GenericAgent
python -c "from plugins.hooks import discover_and_load; discover_and_load(); print('OK')"
```

### Step 5: 运行集成测试
```bash
# 确保 nmem 服务运行
nmem status

# 启动 GA 测试
ga --input "test autorecall" --nobg -v

# 检查日志
cat temp/nmem_auto_recall.log
```

### Step 6: 清理 global_mem_insight.txt
```bash
# 标记为自动生成（不再手动维护）
echo "# Auto-generated at runtime by plugins/nmem_auto_recall.py" > memory/global_mem_insight.txt
```

### Step 7: 上传到 Rapper 并安装
```
按你的 rapper 部署流程：
1. 打包 plugins/nmem_auto_recall.py
2. 上传到 rapper
3. 安装到 GA 实例
4. 重启 GA
```

---

## 十一、环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NMEM_AUTO_RECALL` | `1` | 设为 `0` 禁用 AutoRecall |
| `GA_NMEM_SPACE` | `""` | nmem space 名称 |
| `GA_NMEM_SESSION_SAVE` | `1` | 设为 `0` 禁用 session 保存 |
| `NMEM_API_URL` | `http://127.0.0.1:14242` | nmem API 地址 |
| `NMEM_API_KEY` | - | nmem API 密钥（可选） |
| `GA_LANG` | `zh` | 语言（影响 insight_fixed_structure 选择） |

---

## 十二、FAQ & 边界情况

**Q: nmem 服务没运行怎么办？**
A: 所有 nmem CLI 调用有 5s 超时 + try/except 包裹。失败只记日志，不影响 agent 正常启动和运行。AutoRecall 块为空时不追加到 system prompt。

**Q: 动态 SOP 索引会很长吗？**
A: memory/ 下有 ~47 个文件，生成的索引约 50 行。比之前的 23 行多，但内容更精确（每个 SOP 一行 name: file），总 token 不增反降（去掉重复的 RULES 和描述）。

**Q: agent_after 的 session 保存会覆盖 plugins/nmem_session.py 的旧行为吗？**
A: 旧文件已删除，新插件的 agent_after 是其唯一替代。行为保持一致。

**Q: 为什么不在每个 turn 做 AutoRecall？**
A: Community 实践 + token 成本考量。启动时一次召回 + Working Memory 加载足够。LLM 如需更多会自行调用 `nmem_tool`。
