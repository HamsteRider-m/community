# GenericAgent × Nowledge Mem 兼容性验证报告

**日期**: 2026-05-19  
**基于文档**: GENERIC_AGENT_HANDBOOK.md, README.md, 实际代码检查  
**目的**: 确保所有特性符合 GA 架构，避免引入不兼容特性

---

## 错误复盘：hooks.json 事件

### 问题
照搬了 Droid plugin 的 `hooks.json` 配置文件，但 GenericAgent **不使用 JSON 配置钩子**。

### 根本原因
1. **未先查阅 GA 文档**：直接参考其他插件（Droid）的模式
2. **假设错误**：认为 community 仓库的所有插件都用相同机制
3. **缺少验证**：没有在 GA 代码中确认钩子加载方式

### 正确的 GA 钩子机制
```python
# .omx/ga_nmem_hook/run_agentmain.py
import nmem_session_sync
nmem_session_sync.install(agentmain.GeneraticAgent)  # Python 代码注入
```

---

## GA 核心架构（基于文档）

### 1. 设计哲学
- **极简内核**: ~3K 行核心代码，~100 行 Agent Loop
- **原子工具组合**: 不预装专用工具，用少量原子工具组合出复杂能力
- **自我进化**: 任务成功后沉淀为 SOP/Skill，形成个人技能树
- **分层记忆**: L0(元规则) → L1(索引) → L2(事实) → L3(SOP) → L4(归档)

### 2. 核心工具（原子级）
```
code_run          - 执行脚本
file_read/write/patch - 文件操作
web_scan          - 扫描浏览器
web_execute_js    - 注入 JS
update_working_checkpoint - 短期工作便签
ask_user          - 中断提问
start_long_term_update - 长期记忆提炼
```

### 3. 目录结构
```
GenericAgent/
├── memory/           # ✅ 工具脚本、SOP、记忆文件
├── .omx/             # ✅ 插件、状态、日志
│   ├── ga_nmem_hook/ # ✅ nmem 钩子目录
│   ├── context/      # 上下文
│   ├── plans/        # 计划
│   └── logs/         # 日志
├── agentmain.py      # 主程序
└── agent_loop.py     # Agent Loop
```

### 4. 插件机制
- **位置**: `.omx/<plugin_name>/`
- **加载**: 通过 `run_agentmain.py` 中的 Python 代码注入
- **不使用**: JSON 配置文件、声明式钩子

---

## 现有实现兼容性检查

### ✅ 符合 GA 架构的部分

| 项目 | 实现方式 | 符合度 | 说明 |
|------|---------|--------|------|
| **工具脚本位置** | `memory/nmem_*.py` | ✅ 完全符合 | GA 标准位置 |
| **钩子位置** | `.omx/ga_nmem_hook/` | ✅ 完全符合 | GA 插件标准位置 |
| **钩子加载** | `run_agentmain.py` 中 `install()` | ✅ 完全符合 | Python 代码注入 |
| **测试套件** | `memory/test_nmem_integration.py` | ✅ 完全符合 | 9/9 测试通过 |
| **分层记忆对齐** | L1(index) → L2(facts) → L3(SOP) | ✅ 完全符合 | 符合 GA 记忆层次 |
| **原子工具复用** | 通过 `code_run` 调用 nmem CLI | ✅ 完全符合 | 不修改 ga.py |

### ❌ 已修正的错误

| 项目 | 错误实现 | 修正方式 | 状态 |
|------|---------|---------|------|
| **hooks.json** | 照搬 Droid 的 JSON 配置 | 删除，改为 `hooks/README.md` 说明实际机制 | ✅ 已修正 |

### ⚠️ 需要注意的边界

| 项目 | 当前状态 | 风险 | 建议 |
|------|---------|------|------|
| **Community 插件结构** | 包含 hooks/, scripts/, .factory-plugin/ | 其他插件（Droid）用 hooks.json，GA 不用 | 在 README 中明确说明 GA 特殊性 |
| **安装脚本** | 自动复制到 memory/ 和 .omx/ | 可能覆盖用户自定义文件 | 添加备份和确认机制 |
| **文档一致性** | Community README vs GA 实际机制 | 可能误导其他开发者 | 强调 GA 的 Python 注入机制 |

---

## 兼容性检查清单（防错机制）

### 引入新特性前必须验证：

#### 1. 文档验证
- [ ] 阅读 GA 官方文档（README.md, HANDBOOK.md）
- [ ] 检查 https://datawhalechina.github.io/hello-generic-agent/
- [ ] 确认特性在 GA 中的实现方式

#### 2. 代码验证
- [ ] 检查 GA 源码中是否有类似实现
- [ ] 确认目录结构符合 GA 规范
- [ ] 验证不修改 GA 核心代码（ga.py, agent_loop.py）

#### 3. 测试验证
- [ ] 在 GA 环境中实际运行
- [ ] 编写测试用例验证功能
- [ ] 确认不破坏现有功能

#### 4. 社区验证
- [ ] 检查其他 GA 插件的实现方式
- [ ] 确认不照搬其他 AI 工具（Droid/Copilot）的模式
- [ ] 在 Community 文档中明确 GA 特殊性

---

## 改进建议

### 1. 更新 Community Plugin README

在 `nowledge-mem-genericagent-plugin/README.md` 中添加：

```markdown
## ⚠️ GenericAgent 特殊说明

GenericAgent 使用 **Python 代码注入** 而非 JSON 配置钩子。

**不同于其他插件**：
- ❌ 不使用 `hooks.json`（Droid/Copilot CLI 使用）
- ✅ 使用 `run_agentmain.py` 中的 `install()` 方法

**钩子机制**：
```python
# .omx/ga_nmem_hook/run_agentmain.py
import nmem_session_sync
nmem_session_sync.install(agentmain.GeneraticAgent)
```

详见 [hooks/README.md](hooks/README.md)。
```

### 2. 增强安装脚本安全性

```bash
# 备份现有文件
if [ -f "$GA_ROOT/memory/nmem_layered_read.py" ]; then
    echo "⚠️  检测到现有 nmem 文件，是否覆盖？(y/n)"
    read -r response
    if [ "$response" != "y" ]; then
        echo "安装已取消"
        exit 0
    fi
    # 备份
    cp -r "$GA_ROOT/memory/nmem_*.py" "$GA_ROOT/memory/.nmem_backup_$(date +%Y%m%d_%H%M%S)/"
fi
```

### 3. 添加兼容性检查脚本

```python
# scripts/check_ga_compatibility.py
"""验证当前实现是否符合 GA 架构"""

def check_ga_structure():
    """检查 GA 目录结构"""
    required_dirs = [
        "memory/",
        ".omx/ga_nmem_hook/",
    ]
    # ... 检查逻辑

def check_no_core_modification():
    """确认未修改 GA 核心文件"""
    core_files = ["ga.py", "agent_loop.py", "agentmain.py"]
    # ... 检查逻辑

def check_hook_mechanism():
    """验证钩子加载方式"""
    # 检查 run_agentmain.py 中是否有 install() 调用
    # ... 检查逻辑
```

---

## 总结

### ✅ 当前状态
- 核心实现（工具、钩子、测试）**完全符合** GA 架构
- hooks.json 错误已修正
- 9/9 测试通过

### 📋 待改进
1. 更新 Community README，明确 GA 特殊性
2. 增强安装脚本安全性（备份、确认）
3. 添加兼容性检查脚本

### 🛡️ 防错机制
- **强制规则**: 引入新特性前必须先查阅 GA 文档
- **验证流程**: 文档 → 代码 → 测试 → 社区
- **检查清单**: 见上文"兼容性检查清单"

---

**下一步行动**:
1. 更新 Community Plugin README
2. 提交改进到 GitHub
3. 在实际使用中持续验证和迭代

**参考文档**:
- [FILE:/Users/maygo/Projects/GenericAgent/GENERIC_AGENT_HANDBOOK.md]
- [FILE:/Users/maygo/Projects/GenericAgent/README.md]
- https://datawhalechina.github.io/hello-generic-agent/
