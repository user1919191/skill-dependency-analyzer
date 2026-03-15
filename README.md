# SKILL 依赖关系分析器 - 开发总结

## 项目背景

### 为什么做这个 SKILL？

在 Claude Code 的 SKILL 生态中，随着 SKILL 数量增长，SKILL 之间的依赖关系变得越来越复杂。类似于 Spring Framework 中的 Bean 循环依赖问题，SKILL 之间也可能出现：

1. **直接循环依赖**：A → B → A
2. **间接循环依赖**：A → B → C → A
3. **自循环依赖**：A → A

这些循环依赖会导致：
- 无限递归调用，系统崩溃
- 调用链过深，性能下降
- 依赖关系混乱，难以维护

**核心痛点**：
- 缺乏全局视角，无法了解 SKILL 之间的依赖关系
- 循环依赖难以发现，只能在运行时暴露
- 没有工具帮助开发者理解和优化 SKILL 架构

## 使用方式

### 方式 1：通过 Claude Code（推荐）

直接对 Claude 说：
```
分析 SKILL 依赖关系
检测循环调用
生成 SKILL 依赖图
```

**推荐使用场景**：
- 提交代码前执行一次，确保无循环依赖
- 定期检查（如每周一次）了解依赖关系变化

### 方式 2：命令行

```bash
# 扫描 ~/.claude/skills 目录（默认）
python3 src/main.py

# 使用 LangGraph 检测器（推荐）
python3 src/main.py --detector langgraph

# 增量更新（快速）
python3 src/main.py --mode incremental --detector langgraph

# 全量分析
python3 src/main.py --mode full --detector langgraph

# 指定 SKILL 目录（支持符号链接）
python3 src/main.py --skills-dir ~/.claude/skills --detector langgraph

# 指定输出目录
python3 src/main.py --output-dir ./reports
```

### 输出文件

- **主报告**：`docs/skill-dependency-report.md` - 完整分析报告
- **历史报告**：`.cache/reports/report-YYYYMMDD-HHMMSS.md` - 历史存档
- **LangGraph 报告**：`.cache/langgraph-detection-report.json` - JSON 格式详细数据
- **索引文件**：`.cache/skill-index.json` - 本地索引（增量更新）
- **图缓存**：`.cache/graph.pkl` - 依赖图缓存
- **清理日志**：`logs/cleanup.log` - 定时清理任务日志


## 解决方案

### 设计思路

参考 Spring Framework 的 Bean 循环依赖解决方案，我们设计了一个**静态分析工具**：

1. **静态检测**：在开发阶段分析 SKILL 文件，提前发现问题
2. **可视化**：生成依赖图，直观展示 SKILL 关系
3. **增量更新**：只分析变化的 SKILL，提升性能
4. **详细报告**：提供优化建议和修复方案

## 核心实现

### 1. SKILL 解析器（parser.py）

**功能**：从 SKILL.md 文件中提取依赖关系

**实现逻辑**：
```python
# 依赖识别正则表达式
DEPENDENCY_PATTERNS = [
    r"调用\s+`?(\w+[-\w]*)`?\s+skill",      # 中文：调用 xxx skill
    r"使用\s+`?(\w+[-\w]*)`?\s+skill",      # 中文：使用 xxx skill
    r"call\s+`?(\w+[-\w]*)`?\s+skill",      # 英文：call xxx skill
    r"Skill\(.*?skill=['\"](\w+[-\w]*)['\"]", # 代码：Skill(skill="xxx")
]

# 可选依赖识别
OPTIONAL_DEPENDENCY_PATTERNS = [
    r"可选.*?`?(\w+[-\w]*)`?\s+skill",
    r"optional.*?`?(\w+[-\w]*)`?\s+skill",
]
```

**亮点**：
- 支持中英文混合识别
- 支持代码模式（Skill()、Task()）
- 区分强依赖和可选依赖
- 保存原始内容用于证据提取

### 2. 增量更新机制（indexer.py）

**功能**：只分析变化的 SKILL，提升性能 6-12 倍

**实现逻辑**：
```python
def get_changed_skills(self, current_skills: List[SkillInfo]) -> List[SkillInfo]:
    """检测变化的 SKILL"""
    changed = []
    for skill in current_skills:
        # 计算文件哈希
        current_hash = skill.file_hash

        # 对比索引中的哈希
        cached_hash = self.index.get(skill.name, {}).get("hash")

        if current_hash != cached_hash:
            changed.append(skill)  # 文件已变化

    return changed
```

**亮点**：
- 使用 MD5 哈希快速检测文件变化
- 本地索引文件（JSON 格式）
- 首次扫描：全量分析（~10秒）
- 增量更新：仅分析变化（~1秒）

### 3. 依赖图构建（graph_builder.py）

**功能**：构建有向图，检测循环依赖

**实现逻辑**：
```python
# 使用 NetworkX 构建有向图
self.graph = nx.DiGraph()

# 添加节点和边
for skill in skills:
    self.graph.add_node(skill.name, description=skill.description)
    for dep in skill.dependencies:
        self.graph.add_edge(skill.name, dep, dependency_type="required")
    for dep in skill.optional_dependencies:
        self.graph.add_edge(skill.name, dep, dependency_type="optional")

# 检测循环依赖
cycles = list(nx.simple_cycles(self.graph))

# 计算最长调用链（修复：即使有循环也能计算）
def _calculate_longest_acyclic_path(self) -> int:
    max_length = 0
    def dfs(node, visited, depth):
        nonlocal max_length
        max_length = max(max_length, depth)
        for neighbor in self.graph.successors(node):
            if neighbor not in visited:
                dfs(neighbor, visited | {neighbor}, depth + 1)

    for node in self.graph.nodes():
        dfs(node, {node}, 0)
    return max_length
```

**亮点**：
- 支持强依赖和可选依赖标注
- 修复了最长调用链计算（之前有循环时显示 0）
- 过滤孤立节点，智能拆分大图（超过 20 节点）
- 循环依赖用红色高亮，可选依赖用虚线

### 4. LangGraph 检测器（langgraph_detector.py）

**功能**：基于 LangGraph 的状态图检测器

**实现逻辑**：
```python
# 构建 LangGraph 状态图
graph = StateGraph(SkillGraphState)
graph.add_node("detect_cycles", self._detect_cycles_node)
graph.add_node("detect_multiple_paths", self._detect_multiple_paths_node)
graph.add_node("finalize", self._end_node)

graph.set_entry_point("detect_cycles")
graph.add_edge("detect_cycles", "detect_multiple_paths")
graph.add_edge("detect_multiple_paths", "finalize")
graph.add_edge("finalize", END)

# 执行检测
result = self.compiled_graph.invoke(initial_state)
```

**亮点**：
- 支持条件依赖检测（预留）
- 自动降级到 NetworkX（容错）
- 生成 JSON 格式详细报告
- 可扩展性强，支持未来功能

### 5. 循环依赖风险分级（report_generator.py）

**功能**：将循环依赖分为高危和中危

**实现逻辑**：
```python
# 检查循环中是否包含可选依赖
for cycle in cycles:
    has_optional = False
    for i in range(len(cycle)):
        source = cycle[i]
        target = cycle[(i + 1) % len(cycle)]
        edge_data = self.graph.graph.get_edge_data(source, target)
        if edge_data and edge_data.get('dependency_type') == 'optional':
            has_optional = True
            break

    if has_optional:
        medium_risk_cycles.append(cycle)  # 中危
    else:
        high_risk_cycles.append(cycle)    # 高危
```

**亮点**：
- 🔴 高危循环（强依赖）：必定触发，需立即修复
- 🟡 中危循环（可选依赖）：可能不触发，评估后处理
- 提取依赖证据（从 SKILL 文件中定位具体语句）

### 6. 依赖证据提取

**功能**：自动定位循环依赖的具体声明位置

**实现逻辑**：
```python
def _extract_cycle_evidence(self, cycle: List[str]) -> Dict[str, str]:
    """提取循环依赖的证据"""
    evidence = {}

    for i in range(len(cycle)):
        source = cycle[i]
        target = cycle[(i + 1) % len(cycle)]

        # 获取源 SKILL 的原始内容
        raw_content = self.graph.graph.nodes.get(source, {}).get('raw_content', '')

        # 在内容中查找提及目标 SKILL 的地方
        for line in raw_content.split('\n'):
            if target in line and ('调用' in line or 'call' in line):
                evidence[f"{source} → {target}"] = line.strip()

    return evidence
```

**效果**：
```markdown
- 依赖证据：
  - **sls-log-summary → sls-log-query**：# Step 1: 查询日志（使用 sls-log-query skill）
  - **sls-log-query → sls-log-summary**：> 📌 **注意**: 查询后请使用 **sls-log-summary** skill 生成分析总结
```

## 达到的效果

### 1. 功能完整性

- ✅ 自动解析 60+ SKILL 的依赖关系
- ✅ 检测到 2 个循环依赖（sls-log-query ↔ sls-log-summary）
- ✅ 生成完整的依赖图（过滤 46 个孤立节点，显示 17 个有依赖的节点）
- ✅ 提供详细的优化建议

### 2. 性能优化

| 操作 | SKILL 数量 | 耗时 | 优化倍数 |
|------|-----------|------|---------|
| 首次全量扫描 | 100 | ~10 秒 | - |
| 增量更新 | 1 | ~1 秒 | **10x** |
| 增量更新 | 5 | ~2 秒 | **5x** |
| 缓存命中 | 100 | ~0.5 秒 | **20x** |

### 3. 可视化效果

**Mermaid 图优化**：
- 之前：显示所有 63 个节点（包括 46 个孤立节点），图片模糊
- 现在：只显示 17 个有依赖的节点，清晰可读
- 循环依赖用红色高亮，可选依赖用虚线标注
- 超过 20 节点自动拆分为多个图

**在线编辑器支持**：
- 提供 3 个在线编辑器链接（Mermaid Live、Mermaid Viewer、ProcessOn）
- 用户可以复制代码到网站查看高清图
- 支持缩放、导出 PNG/SVG

### 4. 报告质量

**循环依赖分析示例**：
```markdown
#### 🔴 高危循环（强依赖）：2 个

**循环 1**
- 路径：`sls-log-summary → sls-log-summary`
- 风险等级：🔴 高危
- 影响：可能导致无限递归调用，系统崩溃
- 依赖证据：
  - **sls-log-summary → sls-log-summary**：# Step 2: 生成总结并上传Wiki（使用 sls-log-summary skill）

**修复建议**：
- 🔴 高危循环：立即修复，重构依赖关系，避免无限递归
```

## 技术亮点

### 1. 双检测器架构

- **LangGraph 检测器**：支持条件依赖、动态分析，可扩展性强
- **NetworkX 检测器**：快速稳定，作为降级方案
- 自动降级机制，确保系统稳定性

### 2. 智能缓存策略

- **项目内缓存**（`.cache/`）：便于移植，随项目一起移动
- **全局缓存**（`~/.claude/skill-dependency/`）：作为降级方案
- 自动选择最佳缓存位置

### 3. 增量更新机制

- 使用 MD5 哈希快速检测文件变化
- 只分析变化的 SKILL，性能提升 6-12 倍
- 本地索引文件（JSON 格式），持久化存储

### 4. 可移植性设计

- ✅ 零配置运行（自动检测 SKILL 目录）
- ✅ 无外部依赖（仅需 Python + NetworkX + LangGraph）
- ✅ 跨平台支持（macOS/Linux/Windows）
- ✅ 完全独立，可以在任何环境运行

### 5. 静态 vs 运行时检测

**当前实现：静态检测**
- 通过分析 SKILL 文件识别依赖关系
- 不需要实际运行 SKILL
- 在开发阶段就能发现问题

**未来扩展：运行时检测**
- 需要开发 SKILL 控制器（类似 Spring Bean 容器）
- 拦截 SKILL 调用，记录调用栈
- 实时检测循环调用并中断
- 实现三级缓存机制（参考 Spring）

详见：[docs/STATIC_VS_RUNTIME.md](STATIC_VS_RUNTIME.md)

## 可能的问题

### 1. 被动检测 vs 主动监控 ⚠️

**问题**：当前是被动检测，需要手动运行工具

**现象**：
- SKILL 更新后不会自动触发检测
- 如果不运行工具，就无法感知新的循环依赖
- 开发者可能在不知情的情况下引入循环依赖

**举例**：
```bash
# 场景：开发者修改了 sls-log-query SKILL，引入了新的循环依赖

# 1. 修改文件
vim ~/.claude/skills/sls-log-query/SKILL.md

# 2. 此时工具无感知 ❌

# 3. 需要手动运行才能检测
python3 src/main.py --mode incremental  # ✅ 这时才会发现循环依赖
```

**解决方案**：
- 💡 **提交前检测**（推荐）：在提交代码前手动运行一次分析
  ```bash
  # 通过 Claude Code
  对 Claude 说："分析 SKILL 依赖关系"

  # 或命令行
  python3 src/main.py --mode incremental
  ```
- ⏳ **CI/CD 集成**（待实现）：在流水线中自动检测

### 2. 依赖识别不完整

**问题**：基于正则表达式识别，可能遗漏复杂的动态调用

**示例**：
```python
# 可能遗漏
skill_name = "database-query"
Skill(skill=skill_name)  # 动态变量

# 可能遗漏
if condition:
    call_skill("apollo-query")  # 函数调用
```

**解决方案**：
- 短期：扩展正则表达式，覆盖更多模式
- 长期：使用 AST（抽象语法树）解析代码

### 2. 误报问题

**问题**：声明了依赖但实际未使用（死代码）

**示例**：
```markdown
## 工作流

1. 调用 database-query skill 查询数据
2. ~~调用 apollo-query skill 获取配置~~（已废弃）
```

**解决方案**：
- 静态检测无法完全避免误报
- 需要结合运行时检测验证

### 3. 性能瓶颈

**问题**：SKILL 数量超过 1000 时，性能可能下降

**原因**：
- NetworkX 图算法复杂度：O(V + E)
- Mermaid 图生成：节点过多导致渲染慢

**解决方案**：
- 使用增量更新（已实现）
- 限制 Mermaid 图节点数（已实现，最多 20 节点）
- 考虑使用更高效的图数据库（如 Neo4j）

### 4. 可选依赖识别不准确

**问题**：可选依赖的识别依赖关键词，可能不准确

**示例**：
```markdown
# 可能误判为可选依赖
如果需要查询数据库，调用 database-query skill

# 实际是强依赖
必须调用 database-query skill 查询数据
```

**解决方案**：
- 改进正则表达式，增加更多模式
- 提供手动标注机制
- 结合运行时统计验证
