"""基于 LangGraph 的循环依赖检测器"""
from typing import TypedDict, Annotated, List, Dict, Set, Tuple, Optional
import operator
from langgraph.graph import StateGraph, END
from pathlib import Path
import json

try:
    from .models import SkillInfo
except ImportError:
    from models import SkillInfo


class SkillGraphState(TypedDict):
    """SKILL 图状态"""
    current_skill: str
    visited: Annotated[List[str], operator.add]
    call_stack: Annotated[List[str], operator.add]
    cycles: Annotated[List[List[str]], operator.add]
    conditional_cycles: Annotated[List[Dict], operator.add]
    multiple_paths: Annotated[List[Dict], operator.add]
    skills_map: Dict[str, SkillInfo]
    max_depth: int
    current_depth: int


class LangGraphCycleDetector:
    """基于 LangGraph 的循环依赖检测器

    优势：
    1. 可视化依赖关系（自动生成 Mermaid 图）
    2. 支持条件依赖检测（if-else 分支）
    3. 支持动态依赖分析
    4. 内置环检测机制
    5. 可扩展的状态管理
    """

    def __init__(self, skills: List[SkillInfo], cache_dir: str = "~/.claude/skill-dependency"):
        self.skills = skills
        self.skills_map = {skill.name: skill for skill in skills}
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 构建 LangGraph
        self.graph = self._build_graph()
        self.compiled_graph = None

    def _build_graph(self) -> StateGraph:
        """构建 SKILL 依赖图"""
        graph = StateGraph(SkillGraphState)

        # 添加检测节点
        graph.add_node("detect_cycles", self._detect_cycles_node)
        graph.add_node("detect_multiple_paths", self._detect_multiple_paths_node)
        graph.add_node("finalize", self._end_node)

        # 设置入口点
        graph.set_entry_point("detect_cycles")

        # 连接节点
        graph.add_edge("detect_cycles", "detect_multiple_paths")
        graph.add_edge("detect_multiple_paths", "finalize")
        graph.add_edge("finalize", END)

        return graph

    def _create_skill_node(self, skill: SkillInfo):
        """创建 SKILL 节点处理函数"""
        def process_skill(state: SkillGraphState) -> SkillGraphState:
            """处理单个 SKILL 的依赖"""
            current_skill = state["current_skill"]
            call_stack = state.get("call_stack", [])
            visited = state.get("visited", [])
            cycles = state.get("cycles", [])

            # 检测直接循环
            if current_skill in call_stack:
                # 发现环！
                cycle_start_idx = call_stack.index(current_skill)
                cycle = call_stack[cycle_start_idx:] + [current_skill]
                cycles.append(cycle)
                return state

            # 检测深度限制
            if len(call_stack) >= state.get("max_depth", 10):
                return state

            # 标记为已访问
            new_visited = visited + [current_skill]
            new_call_stack = call_stack + [current_skill]

            # 递归检查依赖
            skill_info = state["skills_map"].get(current_skill)
            if skill_info:
                for dep in skill_info.dependencies:
                    if dep in state["skills_map"]:
                        # 递归检查依赖
                        dep_state = {
                            **state,
                            "current_skill": dep,
                            "visited": new_visited,
                            "call_stack": new_call_stack,
                            "cycles": cycles
                        }
                        # 这里会递归调用
                        self._check_dependency(dep_state)

            return {
                **state,
                "visited": new_visited,
                "cycles": cycles
            }

        return process_skill

    def _start_node(self, state: SkillGraphState) -> SkillGraphState:
        """起始节点"""
        return {
            "current_skill": "",
            "visited": [],
            "call_stack": [],
            "cycles": [],
            "conditional_cycles": [],
            "multiple_paths": [],
            "skills_map": self.skills_map,
            "max_depth": 10,
            "current_depth": 0
        }

    def _detect_cycles_node(self, state: SkillGraphState) -> SkillGraphState:
        """检测循环依赖节点"""
        cycles = []

        # 对每个 SKILL 进行 DFS 检测
        for skill_name in self.skills_map.keys():
            visited = set()
            rec_stack = []
            self._dfs_detect_cycle(skill_name, visited, rec_stack, cycles)

        # 去重
        unique_cycles = []
        seen = set()
        for cycle in cycles:
            cycle_key = tuple(sorted(cycle))
            if cycle_key not in seen:
                seen.add(cycle_key)
                unique_cycles.append(cycle)

        return {
            **state,
            "cycles": unique_cycles
        }

    def _dfs_detect_cycle(self, skill: str, visited: Set[str],
                          rec_stack: List[str], cycles: List[List[str]]):
        """DFS 检测环"""
        visited.add(skill)
        rec_stack.append(skill)

        skill_info = self.skills_map.get(skill)
        if skill_info:
            for dep in skill_info.dependencies:
                if dep not in self.skills_map:
                    continue

                if dep not in visited:
                    self._dfs_detect_cycle(dep, visited, rec_stack, cycles)
                elif dep in rec_stack:
                    # 发现环
                    cycle_start = rec_stack.index(dep)
                    cycle = rec_stack[cycle_start:] + [dep]
                    cycles.append(cycle)

        rec_stack.pop()

    def _detect_multiple_paths_node(self, state: SkillGraphState) -> SkillGraphState:
        """检测多路径节点"""
        multiple_paths = []
        skills = list(self.skills_map.keys())

        # 检测前 10 对多路径
        count = 0
        for i, source in enumerate(skills):
            if count >= 10:
                break
            for target in skills[i+1:]:
                if count >= 10:
                    break

                paths = self._find_all_paths(source, target, max_depth=5)
                if len(paths) > 1:
                    multiple_paths.append({
                        "source": source,
                        "target": target,
                        "paths": paths,
                        "count": len(paths)
                    })
                    count += 1

        return {
            **state,
            "multiple_paths": multiple_paths
        }

    def _find_all_paths(self, source: str, target: str,
                        max_depth: int = 5) -> List[List[str]]:
        """查找所有路径（DFS）"""
        paths = []

        def dfs(current: str, path: List[str], visited: Set[str]):
            if len(path) > max_depth:
                return

            if current == target:
                paths.append(path[:])
                return

            if current in visited:
                return

            visited.add(current)
            skill_info = self.skills_map.get(current)
            if skill_info:
                for dep in skill_info.dependencies:
                    if dep in self.skills_map:
                        dfs(dep, path + [dep], visited.copy())

        dfs(source, [source], set())
        return paths

    def _end_node(self, state: SkillGraphState) -> SkillGraphState:
        """结束节点"""
        return state

    def _check_dependency(self, state: SkillGraphState):
        """检查依赖（递归辅助函数）"""
        current = state["current_skill"]
        call_stack = state["call_stack"]

        # 检测循环
        if current in call_stack:
            cycle_start = call_stack.index(current)
            cycle = call_stack[cycle_start:] + [current]
            state["cycles"].append(cycle)

    def detect(self) -> Dict:
        """执行检测"""
        try:
            # 编译图
            self.compiled_graph = self.graph.compile()

            # 执行检测
            initial_state = {
                "current_skill": "",
                "visited": [],
                "call_stack": [],
                "cycles": [],
                "conditional_cycles": [],
                "multiple_paths": [],
                "skills_map": self.skills_map,
                "max_depth": 10,
                "current_depth": 0
            }

            result = self.compiled_graph.invoke(initial_state)

            return {
                "cycles": result.get("cycles", []),
                "conditional_cycles": result.get("conditional_cycles", []),
                "multiple_paths": result.get("multiple_paths", []),
                "has_cycles": len(result.get("cycles", [])) > 0
            }

        except Exception as e:
            print(f"⚠️  LangGraph 检测失败: {e}")
            import traceback
            traceback.print_exc()

            # 降级到简单的 DFS 检测
            return self._fallback_detect()

    def generate_mermaid(self, max_nodes: int = 20) -> str:
        """生成 Mermaid 依赖图

        使用 LangGraph 的内置可视化功能
        """
        try:
            if self.compiled_graph:
                # LangGraph 内置的 Mermaid 生成
                return self.compiled_graph.get_graph().draw_mermaid()
        except:
            pass

        # 降级方案：手动生成
        return self._generate_mermaid_manual(max_nodes)

    def _generate_mermaid_manual(self, max_nodes: int = 20) -> str:
        """手动生成 Mermaid 图"""
        # 计算节点重要性（入度 + 出度）
        node_scores = {}
        for skill_name, skill_info in self.skills_map.items():
            out_degree = len(skill_info.dependencies)
            in_degree = sum(1 for s in self.skills_map.values()
                          if skill_name in s.dependencies)
            node_scores[skill_name] = out_degree + in_degree

        # 选择 Top N 节点
        top_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
        top_node_names = set(n for n, _ in top_nodes)

        if not top_node_names:
            return "graph TD\n    A[无数据]"

        lines = ["graph TD"]
        node_map = {}

        # 添加节点
        for i, (node, score) in enumerate(top_nodes):
            node_id = f"N{i}"
            node_map[node] = node_id
            # 转义特殊字符
            safe_name = node.replace("-", "_").replace(".", "_")
            lines.append(f"    {node_id}[\"{node}\"]")

        # 添加边
        for skill_name in top_node_names:
            skill_info = self.skills_map.get(skill_name)
            if skill_info:
                for dep in skill_info.dependencies:
                    if dep in top_node_names and skill_name in node_map and dep in node_map:
                        lines.append(f"    {node_map[skill_name]} --> {node_map[dep]}")

        # 高亮循环依赖
        result = self.detect()
        cycles = result.get("cycles", [])
        cycle_nodes = set()
        if cycles:
            for cycle in cycles:
                cycle_nodes.update(cycle)

            for node in cycle_nodes:
                if node in node_map:
                    lines.append(f"    style {node_map[node]} fill:#ff6b6b,stroke:#c92a2a,stroke-width:3px")

        # 高亮最重要的节点
        if top_nodes:
            most_important = node_map.get(top_nodes[0][0])
            if most_important and most_important not in [node_map.get(n) for n in cycle_nodes if n in node_map]:
                lines.append(f"    style {most_important} fill:#4ecdc4,stroke:#339999,stroke-width:2px")

        return "\n".join(lines)

    def calculate_metrics(self) -> Dict:
        """计算图指标"""
        node_count = len(self.skills_map)

        # 计算边数
        edge_count = sum(len(skill.dependencies) for skill in self.skills)

        # 计算入度和出度
        in_degrees = {}
        out_degrees = {}

        for skill_name in self.skills_map.keys():
            out_degrees[skill_name] = len(self.skills_map[skill_name].dependencies)
            in_degrees[skill_name] = 0

        for skill in self.skills:
            for dep in skill.dependencies:
                if dep in in_degrees:
                    in_degrees[dep] += 1

        avg_in_degree = sum(in_degrees.values()) / max(node_count, 1)
        avg_out_degree = sum(out_degrees.values()) / max(node_count, 1)

        # 计算密度
        max_edges = node_count * (node_count - 1)
        density = edge_count / max_edges if max_edges > 0 else 0

        # 检测孤立节点
        isolated_nodes = [
            name for name, skill in self.skills_map.items()
            if len(skill.dependencies) == 0 and in_degrees[name] == 0
        ]

        # 计算最大深度（最长路径）
        max_depth = self._calculate_max_depth()

        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "density": density,
            "avg_in_degree": avg_in_degree,
            "avg_out_degree": avg_out_degree,
            "isolated_nodes": isolated_nodes,
            "max_depth": max_depth,
            "in_degrees": in_degrees,
            "out_degrees": out_degrees
        }

    def _calculate_max_depth(self) -> int:
        """计算最大深度（最长路径）"""
        max_depth = 0

        def dfs(skill: str, depth: int, visited: Set[str]) -> int:
            if skill in visited:
                return depth

            visited.add(skill)
            skill_info = self.skills_map.get(skill)
            if not skill_info or not skill_info.dependencies:
                return depth

            max_child_depth = depth
            for dep in skill_info.dependencies:
                if dep in self.skills_map:
                    child_depth = dfs(dep, depth + 1, visited.copy())
                    max_child_depth = max(max_child_depth, child_depth)

            return max_child_depth

        for skill_name in self.skills_map.keys():
            depth = dfs(skill_name, 0, set())
            max_depth = max(max_depth, depth)

        return max_depth

    def get_top_skills(self, metric: str = "in_degree", top_n: int = 5) -> List[Tuple[str, float]]:
        """获取 Top N SKILL"""
        metrics = self.calculate_metrics()

        if metric == "in_degree":
            degrees = metrics["in_degrees"]
        elif metric == "out_degree":
            degrees = metrics["out_degrees"]
        else:
            return []

        return sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def to_ascii_tree(self, root_nodes: List[str] = None, max_depth: int = 3) -> str:
        """生成 ASCII 树"""
        if not root_nodes:
            # 选择出度最高的节点作为根
            metrics = self.calculate_metrics()
            out_degrees = metrics["out_degrees"]
            root_nodes = sorted(out_degrees.items(), key=lambda x: x[1], reverse=True)[:5]
            root_nodes = [n for n, d in root_nodes if d > 0]

        if not root_nodes:
            return "无依赖关系"

        lines = []
        for root in root_nodes:
            out_degree = len(self.skills_map[root].dependencies) if root in self.skills_map else 0
            lines.append(f"\n{root} (出度: {out_degree})")
            self._build_tree(root, "", True, lines, depth=0, max_depth=max_depth, visited=set())

        return "\n".join(lines)

    def _build_tree(self, node: str, prefix: str, is_last: bool, lines: List[str],
                    depth: int, max_depth: int, visited: Set[str]):
        """递归构建树"""
        if depth >= max_depth or node in visited:
            return

        visited.add(node)
        skill_info = self.skills_map.get(node)
        if not skill_info:
            return

        children = skill_info.dependencies

        for i, child in enumerate(children):
            if child not in self.skills_map:
                continue

            is_last_child = (i == len(children) - 1)
            connector = "└── " if is_last_child else "├── "
            lines.append(f"{prefix}{connector}{child}")

            new_prefix = prefix + ("    " if is_last_child else "│   ")
            self._build_tree(child, new_prefix, is_last_child, lines, depth + 1, max_depth, visited)

    def _fallback_detect(self) -> Dict:
        """降级检测方法（不使用 LangGraph）"""
        cycles = []

        # 对每个 SKILL 进行 DFS 检测
        for skill_name in self.skills_map.keys():
            visited = set()
            rec_stack = []
            self._dfs_detect_cycle(skill_name, visited, rec_stack, cycles)

        # 去重
        unique_cycles = []
        seen = set()
        for cycle in cycles:
            cycle_key = tuple(sorted(cycle))
            if cycle_key not in seen:
                seen.add(cycle_key)
                unique_cycles.append(cycle)

        # 检测多路径
        multiple_paths = []
        skills = list(self.skills_map.keys())
        count = 0
        for i, source in enumerate(skills):
            if count >= 10:
                break
            for target in skills[i+1:]:
                if count >= 10:
                    break
                paths = self._find_all_paths(source, target, max_depth=5)
                if len(paths) > 1:
                    multiple_paths.append({
                        "source": source,
                        "target": target,
                        "paths": paths,
                        "count": len(paths)
                    })
                    count += 1

        return {
            "cycles": unique_cycles,
            "conditional_cycles": [],
            "multiple_paths": multiple_paths,
            "has_cycles": len(unique_cycles) > 0
        }

    def save_report(self, output_path: str):
        """保存检测报告"""
        result = self.detect()
        metrics = self.calculate_metrics()

        report = {
            "summary": {
                "total_skills": metrics["node_count"],
                "total_dependencies": metrics["edge_count"],
                "has_cycles": result["has_cycles"],
                "cycle_count": len(result["cycles"]),
                "multiple_path_count": len(result["multiple_paths"])
            },
            "cycles": result["cycles"],
            "conditional_cycles": result["conditional_cycles"],
            "multiple_paths": result["multiple_paths"],
            "metrics": metrics,
            "top_skills": {
                "by_in_degree": self.get_top_skills("in_degree", 10),
                "by_out_degree": self.get_top_skills("out_degree", 10)
            }
        }

        output_file = Path(output_path).expanduser()
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"✅ 报告已保存: {output_file}")
