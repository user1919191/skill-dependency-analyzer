"""依赖图构建与分析"""
import networkx as nx
import pickle
from pathlib import Path
from typing import List, Dict, Set, Tuple

try:
    from .models import SkillInfo
except ImportError:
    from models import SkillInfo


class DependencyGraph:
    """依赖图管理器"""

    def __init__(self, cache_path: str = "~/.claude/skill-dependency/graph.pkl"):
        self.cache_path = Path(cache_path).expanduser()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.graph = self._load_cache() or nx.DiGraph()

    def _load_cache(self) -> nx.DiGraph:
        """加载缓存的依赖图"""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"⚠️  加载图缓存失败: {e}")
        return None

    def save_cache(self):
        """保存依赖图到缓存"""
        try:
            with open(self.cache_path, 'wb') as f:
                pickle.dump(self.graph, f)
        except Exception as e:
            print(f"⚠️  保存图缓存失败: {e}")

    def build_from_skills(self, skills: List[SkillInfo]):
        """从 SKILL 列表构建依赖图"""
        self.graph.clear()

        # 添加所有节点
        for skill in skills:
            self.graph.add_node(skill.name, **{
                "description": skill.description,
                "file_path": skill.file_path,
                "raw_content": skill.raw_content
            })

        # 添加所有边（强依赖）
        for skill in skills:
            for dep in skill.dependencies:
                self.graph.add_edge(skill.name, dep, dependency_type="required")

            # 添加可选依赖边
            for dep in skill.optional_dependencies:
                self.graph.add_edge(skill.name, dep, dependency_type="optional")

        self.save_cache()

    def incremental_update(self, changed_skills: List[SkillInfo]):
        """增量更新依赖图"""
        for skill in changed_skills:
            # 移除旧的依赖边
            if skill.name in self.graph:
                old_edges = list(self.graph.out_edges(skill.name))
                self.graph.remove_edges_from(old_edges)

            # 添加/更新节点
            self.graph.add_node(skill.name, **{
                "description": skill.description,
                "file_path": skill.file_path,
                "raw_content": skill.raw_content
            })

            # 添加新的依赖边（强依赖）
            for dep in skill.dependencies:
                self.graph.add_edge(skill.name, dep, dependency_type="required")

            # 添加可选依赖边
            for dep in skill.optional_dependencies:
                self.graph.add_edge(skill.name, dep, dependency_type="optional")

        self.save_cache()

    def detect_cycles(self) -> List[List[str]]:
        """检测循环依赖"""
        try:
            return list(nx.simple_cycles(self.graph))
        except:
            return []

    def find_multiple_paths(self, max_pairs: int = 10) -> Dict[Tuple[str, str], List[List[str]]]:
        """查找多路径"""
        multiple_paths = {}
        nodes = list(self.graph.nodes())
        count = 0

        for i, source in enumerate(nodes):
            if count >= max_pairs:
                break
            for target in nodes[i+1:]:
                if count >= max_pairs:
                    break
                try:
                    paths = list(nx.all_simple_paths(self.graph, source, target, cutoff=5))
                    if len(paths) > 1:
                        multiple_paths[(source, target)] = paths
                        count += 1
                except:
                    continue

        return multiple_paths

    def calculate_metrics(self) -> Dict:
        """计算图指标"""
        node_count = self.graph.number_of_nodes()
        edge_count = self.graph.number_of_edges()

        metrics = {
            "node_count": node_count,
            "edge_count": edge_count,
            "density": nx.density(self.graph) if node_count > 0 else 0,
            "avg_in_degree": sum(d for n, d in self.graph.in_degree()) / max(node_count, 1),
            "avg_out_degree": sum(d for n, d in self.graph.out_degree()) / max(node_count, 1),
        }

        # 计算 PageRank
        if node_count > 0:
            try:
                metrics["pagerank"] = nx.pagerank(self.graph)
            except:
                metrics["pagerank"] = {}
        else:
            metrics["pagerank"] = {}

        # 计算最长路径（修复：即使有循环也计算）
        try:
            if nx.is_directed_acyclic_graph(self.graph):
                # 无循环：使用 DAG 最长路径算法
                metrics["max_depth"] = nx.dag_longest_path_length(self.graph)
            else:
                # 有循环：使用 DFS 计算最长无循环路径
                metrics["max_depth"] = self._calculate_longest_acyclic_path()
        except:
            metrics["max_depth"] = 0

        # 孤立节点
        metrics["isolated_nodes"] = list(nx.isolates(self.graph))

        return metrics

    def _calculate_longest_acyclic_path(self) -> int:
        """计算最长无循环路径长度"""
        max_length = 0

        def dfs(node: str, visited: Set[str], depth: int):
            nonlocal max_length
            max_length = max(max_length, depth)

            for neighbor in self.graph.successors(node):
                if neighbor not in visited:
                    dfs(neighbor, visited | {neighbor}, depth + 1)

        # 从每个节点开始 DFS
        for node in self.graph.nodes():
            dfs(node, {node}, 0)

        return max_length

    def get_top_skills(self, metric: str = "in_degree", top_n: int = 5) -> List[Tuple[str, float]]:
        """获取 Top N SKILL"""
        if metric == "in_degree":
            degrees = dict(self.graph.in_degree())
        elif metric == "out_degree":
            degrees = dict(self.graph.out_degree())
        elif metric == "pagerank":
            try:
                degrees = nx.pagerank(self.graph)
            except:
                degrees = {}
        else:
            return []

        return sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def to_mermaid(self, max_nodes_per_graph: int = 20, highlight_cycles: bool = True) -> List[str]:
        """生成 Mermaid 代码（可能拆分为多个图）

        Args:
            max_nodes_per_graph: 每个图的最大节点数
            highlight_cycles: 是否高亮循环依赖

        Returns:
            Mermaid 代码列表（如果节点数超过限制会拆分为多个图）
        """
        # 检测循环
        cycles = self.detect_cycles() if highlight_cycles else []
        cycle_edges = set()

        # 收集所有循环中的边
        for cycle in cycles:
            for i in range(len(cycle)):
                source = cycle[i]
                target = cycle[(i + 1) % len(cycle)]
                cycle_edges.add((source, target))

        # 过滤孤立节点（入度和出度都为 0）
        non_isolated_nodes = [
            node for node in self.graph.nodes()
            if self.graph.in_degree(node) > 0 or self.graph.out_degree(node) > 0
        ]

        if not non_isolated_nodes:
            return ["graph TD\n    A[无依赖关系]"]

        # 创建非孤立节点的子图
        subgraph = self.graph.subgraph(non_isolated_nodes)

        # 如果节点数少于限制，直接生成一个图
        if len(non_isolated_nodes) <= max_nodes_per_graph:
            return [self._generate_single_mermaid(subgraph, cycle_edges, cycles, "完整依赖图")]

        # 否则，按连通分量拆分
        import networkx as nx

        # 转换为无向图来找连通分量
        undirected = subgraph.to_undirected()
        components = list(nx.connected_components(undirected))

        # 按大小排序连通分量
        components = sorted(components, key=len, reverse=True)

        mermaid_graphs = []

        for i, component in enumerate(components, 1):
            component_subgraph = subgraph.subgraph(component)

            # 如果单个连通分量太大，按 PageRank 取 Top N
            if len(component) > max_nodes_per_graph:
                try:
                    pagerank = nx.pagerank(component_subgraph)
                    top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:max_nodes_per_graph]
                    top_node_names = [n for n, _ in top_nodes]
                    component_subgraph = component_subgraph.subgraph(top_node_names)
                    title = f"依赖图 {i}（Top {max_nodes_per_graph} 核心节点）"
                except:
                    # PageRank 失败，直接截断
                    top_node_names = list(component)[:max_nodes_per_graph]
                    component_subgraph = component_subgraph.subgraph(top_node_names)
                    title = f"依赖图 {i}（前 {max_nodes_per_graph} 节点）"
            else:
                title = f"依赖图 {i}（{len(component)} 个节点）"

            mermaid_code = self._generate_single_mermaid(component_subgraph, cycle_edges, cycles, title)
            mermaid_graphs.append(mermaid_code)

        return mermaid_graphs

    def _generate_single_mermaid(self, subgraph, cycle_edges: set, cycles: List[List[str]], title: str = "") -> str:
        """生成单个 Mermaid 图

        Args:
            subgraph: NetworkX 子图
            cycle_edges: 循环边集合
            cycles: 循环列表
            title: 图标题
        """
        if subgraph.number_of_nodes() == 0:
            return "graph TD\n    A[无数据]"

        lines = ["graph TD"]

        # 添加标题（作为注释）
        if title:
            lines.append(f"    %% {title}")

        node_map = {}

        # 添加节点
        for i, node in enumerate(subgraph.nodes()):
            node_id = f"N{i}"
            node_map[node] = node_id
            # 转义特殊字符
            safe_name = node.replace('"', '\\"')
            lines.append(f"    {node_id}[\"{safe_name}\"]")

        # 添加边
        edge_count = 0
        for source, target in subgraph.edges():
            if source in node_map and target in node_map:
                edge_data = self.graph.get_edge_data(source, target)
                dep_type = edge_data.get('dependency_type', 'required') if edge_data else 'required'

                # 判断是否是循环边
                is_cycle_edge = (source, target) in cycle_edges

                if is_cycle_edge:
                    # 循环依赖用红色粗线
                    lines.append(f"    {node_map[source]} -.->|循环| {node_map[target]}")
                    lines.append(f"    linkStyle {edge_count} stroke:#ff0000,stroke-width:3px")
                elif dep_type == 'optional':
                    # 可选依赖用虚线
                    lines.append(f"    {node_map[source]} -.->|可选| {node_map[target]}")
                else:
                    # 强依赖用实线
                    lines.append(f"    {node_map[source]} --> {node_map[target]}")

                edge_count += 1

        # 高亮循环节点
        cycle_nodes = set()
        for cycle in cycles:
            cycle_nodes.update(cycle)

        for node in cycle_nodes:
            if node in node_map:
                lines.append(f"    style {node_map[node]} fill:#ffcccc,stroke:#ff0000,stroke-width:2px")

        return "\n".join(lines)

    def to_ascii_tree(self, root_nodes: List[str] = None, max_depth: int = 3) -> str:
        """生成 ASCII 树"""
        if not root_nodes:
            out_degrees = sorted(self.graph.out_degree(), key=lambda x: x[1], reverse=True)
            root_nodes = [n for n, d in out_degrees[:5] if d > 0]

        if not root_nodes:
            return "无依赖关系"

        lines = []
        for root in root_nodes:
            lines.append(f"\n{root} (出度: {self.graph.out_degree(root)})")
            self._build_tree(root, "", True, lines, depth=0, max_depth=max_depth, visited=set())

        return "\n".join(lines)

    def _build_tree(self, node: str, prefix: str, is_last: bool, lines: List[str],
                    depth: int, max_depth: int, visited: Set[str]):
        """递归构建树"""
        if depth >= max_depth or node in visited:
            return

        visited.add(node)
        children = list(self.graph.successors(node))

        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            connector = "└── " if is_last_child else "├── "
            lines.append(f"{prefix}{connector}{child}")

            new_prefix = prefix + ("    " if is_last_child else "│   ")
            self._build_tree(child, new_prefix, is_last_child, lines, depth + 1, max_depth, visited)
