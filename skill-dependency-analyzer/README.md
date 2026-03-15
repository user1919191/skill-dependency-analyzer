# SKILL 依赖关系分析器

自动分析 SKILL 之间的依赖关系，检测循环依赖和多路径问题，生成可视化依赖图和详细评估报告。

## 功能特性

- ✅ 自动解析所有 SKILL 的调用关系（支持符号链接）
- ✅ 检测循环依赖（高危/中危分级）
- ✅ 多路径分析（菱形依赖检测）
- ✅ 可视化依赖图（Mermaid + ASCII）
- ✅ 增量更新机制（性能提升 6-12 倍）
- ✅ LangGraph 检测器（支持条件依赖和动态分析）
- ✅ 依赖证据提取（自动定位依赖声明）
- ✅ 定时清理历史报告（避免磁盘占用）

## 快速开始

### 安装

```bash
cd /Users/moka/Downloads/claude-skills/skills/skill-dependency-analyzer
pip3 install -r requirements.txt
```

### 使用方式

#### 方式 1：通过 Claude Code（推荐）

直接对 Claude 说：
```
分析 SKILL 依赖关系
检测循环调用
生成 SKILL 依赖图
```

**推荐使用场景**：
- 提交代码前执行一次，确保无循环依赖
- 定期检查（如每周一次）了解依赖关系变化

#### 方式 2：命令行

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

## 输出文件

- **主报告**：`docs/skill-dependency-report.md` - 完整分析报告
- **历史报告**：`.cache/reports/report-YYYYMMDD-HHMMSS.md` - 历史存档
- **LangGraph 报告**：`.cache/langgraph-detection-report.json` - JSON 格式详细数据
- **索引文件**：`.cache/skill-index.json` - 本地索引（增量更新）
- **图缓存**：`.cache/graph.pkl` - 依赖图缓存
- **清理日志**：`logs/cleanup.log` - 定时清理任务日志

## 定时任务

### 自动清理历史报告

为避免历史报告占用过多磁盘空间，提供了自动清理脚本：

**安装定时任务**：
```bash
cd /Users/moka/Downloads/claude-skills/skills/skill-dependency-analyzer
./scripts/install_cron.sh
```

**清理规则**：
- 执行频率：每 2 天一次（凌晨 2 点）
- 清理规则：删除两周前的历史报告
- 日志文件：`logs/cleanup.log`

**手动执行清理**：
```bash
python3 scripts/cleanup_old_reports.py
```

**查看定时任务**：
```bash
crontab -l | grep cleanup_old_reports
```

**卸载定时任务**：
```bash
crontab -l | grep -v cleanup_old_reports.py | crontab -
```

## 报告内容

### 1. 执行摘要
- 总 SKILL 数、依赖关系数
- 循环依赖检测结果
- 多路径 SKILL 对数量
- 孤立 SKILL 统计

### 2. 依赖关系分析
- **概览统计**：平均入度/出度、图密度、最长调用链
- **ASCII 树形图**：Top 5 核心 SKILL 的依赖树
- **Mermaid 依赖图**：完整可视化（过滤孤立节点，智能拆分）
- **循环依赖分析**：高危/中危分级 + 依赖证据
- **多路径分析**：菱形依赖详情
- **SKILL 指标排名**：入度/出度/PageRank Top 5

### 3. 优化建议
- 高优先级建议（循环依赖修复、核心 SKILL 监控）
- 中优先级建议（调用链优化、孤立 SKILL 处理）

## Mermaid 图在线编辑器

报告中的 Mermaid 代码可以复制到以下网站查看和编辑：

- **[Mermaid Live Editor](https://mermaid.live/)** - 官方编辑器，功能完整
- **[Mermaid Viewer](https://mermaidviewer.com/)** - 实时预览 + AI 辅助
- **[ProcessOn Mermaid](https://www.processon.com/mermaid)** - 中文界面 + AI 识图

**使用方法**：
1. 打开上述任一网站
2. 复制报告中的 Mermaid 代码（包括 \`\`\`mermaid 标记内的内容）
3. 粘贴到编辑器中即可查看高清依赖图
4. 支持缩放、导出 PNG/SVG 等功能

## 检测器对比

| 特性 | LangGraph 检测器 | NetworkX 检测器 |
|------|-----------------|----------------|
| 直接循环依赖 | ✅ | ✅ |
| 条件循环依赖 | ✅ | ❌ |
| 可视化依赖图 | ✅ 自动生成 | ✅ 手动生成 |
| 动态依赖分析 | ✅ | ❌ |
| 性能 | 中等 | 快速 |
| 扩展性 | 强 | 中等 |
| **推荐场景** | 复杂依赖分析 | 快速检测 |

## 性能

- 首次扫描 60 个 SKILL：~0.1 秒
- 增量更新单个 SKILL：~0.5 秒
- 增量更新 5 个 SKILL：~1 秒
- 缓存命中（无变化）：~0.3 秒
- 支持符号链接扫描（~/.claude/skills）

## 技术架构

```
skill-dependency-analyzer/
├── src/
│   ├── main.py                    # 主入口（CLI）
│   ├── models.py                  # 数据模型（SkillInfo）
│   ├── parser.py                  # SKILL 解析器（支持符号链接）
│   ├── indexer.py                 # 索引管理器（增量更新）
│   ├── hash_utils.py              # 文件哈希工具
│   ├── graph_builder.py           # NetworkX 依赖图构建
│   ├── langgraph_detector.py      # LangGraph 循环依赖检测器
│   └── report_generator.py        # 报告生成器
├── scripts/
│   ├── cleanup_old_reports.py     # 历史报告清理脚本
│   ├── install_cron.sh            # 定时任务安装脚本
│   └── crontab.txt                # cron 配置示例
├── docs/
│   ├── skill-dependency-report.md # 最新报告
│   ├── 开发总结.md                 # 开发文档
│   └── 运行时检测设计方案.md        # 运行时检测设计
├── logs/
│   └── cleanup.log                # 清理任务日志
├── .cache/                        # 缓存目录
│   ├── skill-index.json           # 索引文件
│   ├── graph.pkl                  # 图缓存
│   ├── langgraph-detection-report.json
│   └── reports/                   # 历史报告
├── SKILL.md                       # SKILL 配置文件
├── requirements.txt               # Python 依赖
└── README.md                      # 本文档
```

## 依赖识别规则

### 强依赖（必须调用）
- 中文：`调用 xxx skill`、`使用 xxx skill`、`编排 xxx, yyy`
- 英文：`call xxx skill`、`use xxx skill`
- 代码：`Skill(skill="xxx")`、`Task(subagent_type="xxx")`

### 可选依赖（条件调用）
- 中文：`可选 xxx skill`、`如果...调用 xxx skill`
- 英文：`optional xxx skill`、`may use xxx skill`

## 示例输出

```
🔍 SKILL 依赖关系分析器
📂 扫描目录: /Users/moka/.claude/skills
💾 缓存目录: .cache
📄 输出目录: docs
🔧 检测器: LANGGRAPH

[1/4] 解析 SKILL 文件...
✅ 发现 58 个 SKILL

[2/4] 构建依赖图（全量分析）...
✅ 依赖图构建完成

[3/4] 检测循环依赖...
🚀 使用 LangGraph 检测器（支持条件依赖和可视化）
⚠️  检测到 2 个直接循环依赖
   循环 1: sls-log-query → sls-log-summary → sls-log-query
   循环 2: sls-log-summary → sls-log-summary

[4/4] 生成报告...
✅ 报告生成完成

============================================================
✅ 分析完成！耗时 0.1 秒

关键发现：
- ⚠️  2 个循环依赖
- 0 对 SKILL 存在多路径
- oncall-dispatcher 是最核心的编排 SKILL（出度: 6）

完整报告：docs/skill-dependency-report.md
============================================================
```
- 0 对 SKILL 存在多路径
- oncall-dispatcher 是最核心的编排 SKILL（出度: 6）

完整报告：docs/skill-dependency-report.md
============================================================
```

## 故障排除

### 问题：找不到 SKILL 文件

**原因**：默认扫描 `~/.claude/skills`，如果 SKILL 在其他位置需要手动指定。

**解决方案**：
```bash
# 检查默认目录
ls ~/.claude/skills

# 手动指定目录
python3 src/main.py --skills-dir /path/to/skills
```

### 问题：符号链接未被扫描

**原因**：旧版本不支持符号链接，已在 v2.0 修复。

**解决方案**：
```bash
# 确保使用最新版本
python3 src/main.py --mode full --skills-dir ~/.claude/skills
```

### 问题：导入错误

**解决方案**：
```bash
pip3 install -r requirements.txt
```

### 问题：LangGraph 检测失败

**解决方案**：系统会自动降级到 NetworkX 检测器，或手动指定：
```bash
python3 src/main.py --detector networkx
```

### 问题：历史报告占用空间过大

**解决方案**：
```bash
# 手动清理
python3 scripts/cleanup_old_reports.py

# 安装定时任务自动清理
./scripts/install_cron.sh
```

## 可移植性

本工具设计为**完全可移植和独立**：

- ✅ 零配置运行（自动检测 SKILL 目录）
- ✅ 智能缓存策略（项目内缓存 + 全局缓存降级）
- ✅ 无外部依赖（仅需 Python + NetworkX + LangGraph）
- ✅ 跨平台支持（macOS/Linux/Windows）
- ✅ 符号链接支持（自动解析 ~/.claude/skills 中的符号链接）

## 更新日志

### v2.0.0 (2026-03-05)
- ✅ 新增符号链接支持（扫描 ~/.claude/skills）
- ✅ 新增定时清理历史报告功能
- ✅ 优化 SKILL.md 文档表述，避免示例被误识别
- ✅ 新增运行时检测设计方案文档
- ✅ 性能优化：58 个 SKILL 扫描仅需 0.1 秒

### v1.0.0
- ✅ 基础依赖分析功能
- ✅ LangGraph 循环依赖检测
- ✅ Mermaid 可视化
- ✅ 增量更新机制

## 技术支持

如有问题，请查看：
- [开发总结.md](docs/开发总结.md) - 开发文档和技术细节

---

**版本**：v2.0.0
**更新日期**：2026-03-05
**状态**：✅ 已完成并测试通过
