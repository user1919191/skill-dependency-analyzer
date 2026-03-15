"""报告生成器"""
from typing import List, Dict, Tuple
from datetime import datetime

try:
    from .graph_builder import DependencyGraph
except ImportError:
    from graph_builder import DependencyGraph


class ReportGenerator:
    """依赖关系报告生成器"""

    def __init__(self, graph: DependencyGraph):
        self.graph = graph
        self.metrics = graph.calculate_metrics()

    def generate_report(self, mode: str = "full", changed_count: int = 0) -> str:
        """生成完整报告"""
        sections = [
            self._generate_header(mode, changed_count),
            self._generate_summary(),
            self._generate_overview(),
            self._generate_visualization(),
            self._generate_cycle_analysis(),
            self._generate_multipath_analysis(),
            self._generate_ranking(),
            self._generate_recommendations(),
            self._generate_footer()
        ]

        return "\n\n".join(sections)

    def _generate_header(self, mode: str, changed_count: int) -> str:
        """生成报告头部"""
        mode_text = f"增量更新（{changed_count} 个 SKILL 变化）" if mode == "incremental" else "全量分析"
        return f"""# SKILL 依赖关系分析报告

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
分析模式：{mode_text}"""

    def _generate_summary(self) -> str:
        """生成执行摘要"""
        cycles = self.graph.detect_cycles()
        multiple_paths = self.graph.find_multiple_paths(max_pairs=10)
        isolated = self.metrics.get("isolated_nodes", [])

        cycle_status = "✅" if len(cycles) == 0 else f"⚠️ {len(cycles)}"

        return f"""## 1. 执行摘要

- 总 SKILL 数：{self.metrics['node_count']}
- 依赖关系数：{self.metrics['edge_count']}
- 检测到循环：{cycle_status}
- 多路径 SKILL 对：{len(multiple_paths)}
- 孤立 SKILL：{len(isolated)}"""

    def _generate_overview(self) -> str:
        """生成概览统计"""
        return f"""## 2. 依赖关系分析

### 2.1 概览统计

- 平均入度：{self.metrics['avg_in_degree']:.2f}
- 平均出度：{self.metrics['avg_out_degree']:.2f}
- 图密度：{self.metrics['density']:.3f}
- 最长调用链：{self.metrics.get('max_depth', 0)} 层"""

    def _generate_visualization(self) -> str:
        """生成可视化"""
        ascii_tree = self.graph.to_ascii_tree(max_depth=3)
        # 生成 Mermaid 图（可能拆分为多个）
        mermaid_graphs = self.graph.to_mermaid(max_nodes_per_graph=20, highlight_cycles=True)

        # 构建 Mermaid 部分
        mermaid_section = []
        if len(mermaid_graphs) == 1:
            mermaid_section.append("#### Mermaid Flowchart（依赖关系图）\n")
            mermaid_section.append("```mermaid")
            mermaid_section.append(mermaid_graphs[0])
            mermaid_section.append("```")
        else:
            mermaid_section.append(f"#### Mermaid Flowchart（共 {len(mermaid_graphs)} 个依赖图）\n")
            for i, mermaid_code in enumerate(mermaid_graphs, 1):
                mermaid_section.append(f"##### 图 {i}\n")
                mermaid_section.append("```mermaid")
                mermaid_section.append(mermaid_code)
                mermaid_section.append("```\n")

        mermaid_text = "\n".join(mermaid_section)

        return f"""### 2.2 依赖图可视化

#### ASCII 树形图（Top 5 核心 SKILL）

```
{ascii_tree}
```

{mermaid_text}

**图例说明**：
- 实线箭头：强依赖（必须调用）
- 虚线箭头：可选依赖（条件调用）
- 红色节点和边：循环依赖（需要修复）

**在线编辑器**（可复制 Mermaid 代码到以下网站查看和编辑）：
- [Mermaid Live Editor](https://mermaid.live/) - 官方编辑器
- [Mermaid Viewer](https://mermaidviewer.com/) - 实时预览 + AI 辅助
- [ProcessOn Mermaid](https://www.processon.com/mermaid) - 中文界面 + AI 识图"""

    def _generate_cycle_analysis(self) -> str:
        """生成循环依赖分析"""
        cycles = self.graph.detect_cycles()

        if not cycles:
            return """### 2.3 循环依赖分析

✅ **未检测到循环依赖**

系统依赖关系健康，无循环调用风险。"""

        # 分类循环依赖：高危（强依赖）和中危（可选依赖）
        high_risk_cycles = []
        medium_risk_cycles = []

        for cycle in cycles:
            # 检查循环中是否包含可选依赖
            has_optional = False
            for i in range(len(cycle)):
                source = cycle[i]
                target = cycle[(i + 1) % len(cycle)]
                edge_data = self.graph.graph.get_edge_data(source, target)
                if edge_data and edge_data.get('dependency_type') == 'optional':
                    has_optional = True
                    break

            if has_optional:
                medium_risk_cycles.append(cycle)
            else:
                high_risk_cycles.append(cycle)

        # 生成报告
        sections = [f"### 2.3 循环依赖分析\n\n⚠️ **检测到 {len(cycles)} 个循环依赖**"]

        # 高危循环
        if high_risk_cycles:
            sections.append(f"\n#### 🔴 高危循环（强依赖）：{len(high_risk_cycles)} 个\n")
            for i, cycle in enumerate(high_risk_cycles, 1):
                cycle_path = ' → '.join(cycle + [cycle[0]])
                sections.append(f"**循环 {i}**")
                sections.append(f"- 路径：`{cycle_path}`")
                sections.append(f"- 风险等级：🔴 高危")
                sections.append(f"- 影响：可能导致无限递归调用，系统崩溃")

                # 提取证据
                evidence = self._extract_cycle_evidence(cycle)
                if evidence:
                    sections.append(f"- 依赖证据：")
                    for skill_name, ev in evidence.items():
                        sections.append(f"  - **{skill_name}**：{ev}")

                sections.append("")

        # 中危循环
        if medium_risk_cycles:
            sections.append(f"\n#### 🟡 中危循环（可选依赖）：{len(medium_risk_cycles)} 个\n")
            for i, cycle in enumerate(medium_risk_cycles, 1):
                cycle_path = ' → '.join(cycle + [cycle[0]])
                sections.append(f"**循环 {i}**")
                sections.append(f"- 路径：`{cycle_path}`")
                sections.append(f"- 风险等级：🟡 中危")
                sections.append(f"- 影响：可选依赖，运行时可能不触发")

                # 提取证据
                evidence = self._extract_cycle_evidence(cycle)
                if evidence:
                    sections.append(f"- 依赖证据：")
                    for skill_name, ev in evidence.items():
                        sections.append(f"  - **{skill_name}**：{ev}")

                sections.append("")

        # 修复建议
        sections.append("\n**修复建议**：")
        if high_risk_cycles:
            sections.append("- 🔴 高危循环：立即修复，重构依赖关系，避免无限递归")
        if medium_risk_cycles:
            sections.append("- 🟡 中危循环：评估运行时触发概率，考虑添加深度限制或缓存机制")

        return "\n".join(sections)

    def _extract_cycle_evidence(self, cycle: List[str]) -> Dict[str, str]:
        """提取循环依赖的证据

        Args:
            cycle: 循环路径

        Returns:
            {skill_name: evidence_text}
        """
        evidence = {}

        for i in range(len(cycle)):
            source = cycle[i]
            target = cycle[(i + 1) % len(cycle)]

            # 获取源 SKILL 的原始内容
            node_data = self.graph.graph.nodes.get(source, {})
            raw_content = node_data.get('raw_content', '')

            if not raw_content:
                continue

            # 在内容中查找提及目标 SKILL 的地方
            lines = raw_content.split('\n')
            evidence_lines = []

            for line in lines:
                if target in line and ('调用' in line or '使用' in line or '编排' in line or
                                       'call' in line.lower() or 'use' in line.lower() or
                                       'Skill(' in line or 'Task(' in line):
                    # 清理行内容
                    clean_line = line.strip().strip('-').strip('*').strip()
                    if clean_line and len(clean_line) < 200:
                        evidence_lines.append(clean_line)

            if evidence_lines:
                # 只保留前2条证据
                evidence[f"{source} → {target}"] = "; ".join(evidence_lines[:2])

        return evidence

    def _generate_multipath_analysis(self) -> str:
        """生成多路径分析"""
        multiple_paths = self.graph.find_multiple_paths(max_pairs=5)

        if not multiple_paths:
            return """### 2.4 多路径分析

✅ **未检测到多路径依赖**"""

        path_texts = []
        for i, ((source, target), paths) in enumerate(multiple_paths.items(), 1):
            path_list = "\n".join([
                f"  {j}. `{' → '.join(path)}`"
                for j, path in enumerate(paths, 1)
            ])
            path_texts.append(f"""#### 路径 {i}：{source} → {target}
- 路径数量：{len(paths)}
- 路径详情：
{path_list}
- 类型：菱形依赖
- 风险等级：🟢 低""")

        return f"""### 2.4 多路径分析

检测到 {len(multiple_paths)} 对 SKILL 存在多条路径：

{chr(10).join(path_texts)}"""

    def _generate_ranking(self) -> str:
        """生成 SKILL 指标排名"""
        top_in = self.graph.get_top_skills("in_degree", 5)
        top_out = self.graph.get_top_skills("out_degree", 5)
        top_pagerank = self.graph.get_top_skills("pagerank", 5)

        # 最常被调用的 SKILL
        in_table = self._format_table(
            ["排名", "SKILL", "入度"],
            [[i+1, name, int(degree)] for i, (name, degree) in enumerate(top_in)]
        )

        # 调用最多 SKILL 的 SKILL
        out_table = self._format_table(
            ["排名", "SKILL", "出度"],
            [[i+1, name, int(degree)] for i, (name, degree) in enumerate(top_out)]
        )

        # PageRank 重要性排名
        pr_table = self._format_table(
            ["排名", "SKILL", "PageRank"],
            [[i+1, name, f"{score:.3f}"] for i, (name, score) in enumerate(top_pagerank)]
        )

        return f"""### 2.5 SKILL 指标排名

#### 最常被调用的 SKILL（Top 5）

{in_table}

#### 调用最多 SKILL 的 SKILL（Top 5）

{out_table}

#### PageRank 重要性排名（Top 5）

{pr_table}"""

    def _format_table(self, headers: List[str], rows: List[List]) -> str:
        """格式化 Markdown 表格"""
        header_line = "| " + " | ".join(str(h) for h in headers) + " |"
        separator = "|" + "|".join(["------"] * len(headers)) + "|"
        row_lines = [
            "| " + " | ".join(str(cell) for cell in row) + " |"
            for row in rows
        ]
        return "\n".join([header_line, separator] + row_lines)

    def _generate_recommendations(self) -> str:
        """生成优化建议"""
        recommendations = []

        # 检查高入度 SKILL
        top_in = self.graph.get_top_skills("in_degree", 3)
        if top_in and top_in[0][1] > 5:
            recommendations.append(f"""1. **监控核心 SKILL**
   - {top_in[0][0]} 入度过高（{int(top_in[0][1])}），需要监控性能
   - 建议：添加性能监控和告警""")

        # 检查调用链深度
        max_depth = self.metrics.get('max_depth', 0)
        if max_depth > 4:
            recommendations.append(f"""2. **优化调用链深度**
   - 最长调用链 {max_depth} 层，可能影响性能
   - 建议：考虑扁平化设计""")

        # 检查孤立 SKILL
        isolated = self.metrics.get("isolated_nodes", [])
        if len(isolated) > 0:
            recommendations.append(f"""3. **处理孤立 SKILL**
   - {len(isolated)} 个孤立 SKILL 可能需要整合或废弃
   - 建议：评估使用频率""")

        if not recommendations:
            recommendations.append("✅ 系统依赖关系健康，暂无优化建议")

        return f"""## 3. 优化建议

### 3.1 高优先级

{chr(10).join(recommendations)}"""

    def _generate_footer(self) -> str:
        """生成报告尾部"""
        return """---

**报告版本**：v1.0
**生成工具**：skill-dependency-analyzer"""
