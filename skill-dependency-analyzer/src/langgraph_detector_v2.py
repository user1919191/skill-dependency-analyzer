"""基于 LangGraph 的循环依赖检测器 V2 - 融合Spring三级缓存思路"""
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
    """SKILL 图状态 - 模拟Spring三级缓存机制

    Spring三级缓存映射：
    - completed_skills → singletonObjects (一级缓存：完整Bean)
    - in_progress_stack → earlySingletonObjects (二级缓存：早期Bean引用/递归栈)
    - pending_skills → singletonFactories (三级缓存：Bean工厂/待检测队列)
    """
    # === 一级缓存：完整检测完成的Skill ===
    completed_skills: Set[str]  # 对应 singletonObjects

    # === 二级缓存：正在检测中的Skill（递归栈）===
    in_progress_stack: List[str]  # 对应 earlySingletonObjects

    # === 三级缓存：待检测的Skill队列 ===
    pending_skills: List[str]  # 对应 singletonFactories

    # 检测结果（不使用 operator.add，避免重复累加）
    cycles: List[List[str]]
    multiple_paths: List[Dict]
    cycles_set: Set[str]  # 用于去重的循环签名集合

    # 当前状态
    current_skill: str
    skills_map: Dict[str, SkillInfo]

    # 统计信息
    total_checked: int
    cycle_detected_flag: bool


class LangGraphCycleDetectorV2:
    """基于 LangGraph 的循环依赖检测器 V2

    核心改进：
    1. 将DFS递归逻辑完全融入LangGraph状态机
    2. 显式映射Spring三级缓存机制
    3. 可视化状态转移流程
    4. 支持单步调试和状态追踪
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
        """构建 SKILL 依赖图 - 融合DFS逻辑"""
        graph = StateGraph(SkillGraphState)

        # 节点1：初始化待检测队列（三级缓存）
        graph.add_node("init_queue", self._init_pending_queue)

        # 节点2：从队列取出一个Skill开始检测
        graph.add_node("pop_skill", self._pop_next_skill)

        # 节点3：检测当前Skill（核心DFS逻辑）
        graph.add_node("check_skill", self._check_current_skill)

        # 节点4：处理依赖（递归检测子节点）
        graph.add_node("process_dependencies", self._process_dependencies)

        # 节点5：回溯（弹出递归栈）
        graph.add_node("backtrack", self._backtrack_skill)

        # 节点6：检测多路径
        graph.add_node("detect_multiple_paths", self._detect_multiple_paths_node)

        # 节点7：完成检测
        graph.add_node("finalize", self._finalize)

        # 设置流程
        graph.set_entry_point("init_queue")

        # 条件路由
        graph.add_conditional_edges(
            "init_queue",
            self._should_continue_checking,
            {
                "continue": "pop_skill",
                "end": "detect_multiple_paths"
            }
        )

        graph.add_edge("pop_skill", "check_skill")

        graph.add_conditional_edges(
            "check_skill",
            self._check_cycle_or_continue,
            {
                "cycle_detected": "backtrack",  # 发现循环，直接回溯
                "has_dependencies": "process_dependencies",  # 有依赖，继续检测
                "no_dependencies": "backtrack",  # 无依赖，回溯
                "already_completed": "pop_skill"  # 已完成，跳过
            }
        )

        graph.add_conditional_edges(
            "process_dependencies",
            self._should_continue_checking,
            {
                "continue": "pop_skill",  # 继续检测依赖
                "end": "backtrack"  # 无更多依赖，回溯
            }
        )

        graph.add_conditional_edges(
            "backtrack",
            self._should_continue_checking,
            {
                "continue": "pop_skill",
                "end": "detect_multiple_paths"
            }
        )

        graph.add_edge("detect_multiple_paths", "finalize")
        graph.add_edge("finalize", END)

        return graph

    def _init_pending_queue(self, state: SkillGraphState) -> SkillGraphState:
        """初始化待检测队列（三级缓存）"""
        print("[初始化] 构建待检测队列（三级缓存）")
        return {
            "pending_skills": list(self.skills_map.keys()),
            "completed_skills": set(),
            "in_progress_stack": [],
            "cycles": [],
            "multiple_paths": [],
            "cycles_set": set(),
            "current_skill": "",
            "skills_map": self.skills_map,
            "total_checked": 0,
            "cycle_detected_flag": False
        }

    def _pop_next_skill(self, state: SkillGraphState) -> SkillGraphState:
        """从队列取出下一个Skill（从三级缓存取出）"""
        pending = state["pending_skills"]
        completed = state["completed_skills"]

        if not pending:
            # 关键修复：队列为空时，清空 current_skill
            return {
                **state,
                "current_skill": "",
                "pending_skills": []
            }

        # 跳过已完成的节点，找到第一个未完成的
        while pending and pending[0] in completed:
            pending = pending[1:]

        if not pending:
            # 关键修复：所有节点都已完成时，清空 current_skill
            return {
                **state,
                "current_skill": "",
                "pending_skills": []
            }

        # 从待检测队列取出
        next_skill = pending[0]

        print(f"[取出] 从待检测队列取出: {next_skill}")

        return {
            **state,
            "current_skill": next_skill,
            "pending_skills": pending[1:]
        }

    def _check_current_skill(self, state: SkillGraphState) -> SkillGraphState:
        """检测当前Skill（核心DFS逻辑 - 模拟Spring循环依赖检测）"""
        current = state["current_skill"]
        in_progress = state["in_progress_stack"]
        completed = state["completed_skills"]

        print(f"[检测] 当前Skill: {current}")
        print(f"   二级缓存（递归栈）: {in_progress}")
        print(f"   一级缓存（已完成）: {len(completed)} 个")

        # 检查一级缓存（已完成）
        if current in completed:
            print(f"   [OK] 已在一级缓存中，跳过")
            return {
                **state,
                "cycle_detected_flag": False
            }

        # 检查二级缓存（正在检测中）→ 发现循环！
        if current in in_progress:
            cycle_start = in_progress.index(current)
            cycle = in_progress[cycle_start:] + [current]

            # 生成循环签名用于去重（排序后的节点列表）
            cycle_signature = "->".join(sorted(cycle))

            # 只有未记录过的循环才添加
            if cycle_signature not in state["cycles_set"]:
                print(f"   [CYCLE] 发现循环依赖: {' -> '.join(cycle)}")
                return {
                    **state,
                    "cycles": state["cycles"] + [cycle],
                    "cycles_set": state["cycles_set"] | {cycle_signature},
                    "cycle_detected_flag": True
                }
            else:
                print(f"   [SKIP] 循环已记录，跳过: {' -> '.join(cycle)}")
                return {
                    **state,
                    "cycle_detected_flag": True
                }

        # 加入二级缓存（标记为"正在检测中"）
        print(f"   [+] 加入二级缓存（递归栈）")
        return {
            **state,
            "in_progress_stack": in_progress + [current],
            "cycle_detected_flag": False
        }

    def _process_dependencies(self, state: SkillGraphState) -> SkillGraphState:
        """处理依赖（将依赖加入三级缓存）"""
        current = state["current_skill"]
        skill_info = self.skills_map.get(current)

        if not skill_info:
            return state

        # 将依赖加入待检测队列（三级缓存）
        # 关键修复：避免将已在递归栈中的依赖重复加入
        new_pending = []
        for dep in skill_info.dependencies:
            if (dep in self.skills_map and
                dep not in state["completed_skills"] and
                dep not in state["in_progress_stack"]):
                new_pending.append(dep)

        if new_pending:
            print(f"   [ADD] 将 {len(new_pending)} 个依赖加入三级缓存: {new_pending}")

        return {
            **state,
            "pending_skills": new_pending + state["pending_skills"]
        }

    def _backtrack_skill(self, state: SkillGraphState) -> SkillGraphState:
        """回溯：将Skill从二级缓存移到一级缓存"""
        current = state["current_skill"]
        in_progress = state["in_progress_stack"]

        # 关键修复：无论是否检测到循环，都要从递归栈中移除当前节点
        # 从二级缓存（递归栈）弹出
        if current in in_progress:
            in_progress = [s for s in in_progress if s != current]
            print(f"   [POP] 从二级缓存弹出: {current}")

        # 如果发现了循环，标记但仍然要清理栈
        if state.get("cycle_detected_flag", False):
            print(f"   [WARN] 循环节点，已记录循环但继续处理")
            # 重置循环标志，避免影响后续节点
            return {
                **state,
                "in_progress_stack": in_progress,
                "completed_skills": state["completed_skills"] | {current},
                "total_checked": state["total_checked"] + 1,
                "cycle_detected_flag": False
            }

        # 加入一级缓存（已完成）
        print(f"   [OK] 移入一级缓存（已完成）")

        return {
            **state,
            "in_progress_stack": in_progress,
            "completed_skills": state["completed_skills"] | {current},
            "total_checked": state["total_checked"] + 1
        }

    def _detect_multiple_paths_node(self, state: SkillGraphState) -> SkillGraphState:
        """检测多路径节点"""
        print("\n[多路径检测] 开始检测多路径...")

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

        print(f"   发现 {len(multiple_paths)} 对多路径")

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

    def _finalize(self, state: SkillGraphState) -> SkillGraphState:
        """结束节点"""
        print(f"\n[完成] 检测完成，共检测 {state['total_checked']} 个Skill")
        return state

    def _should_continue_checking(self, state: SkillGraphState) -> str:
        """判断是否继续检测"""
        if state["pending_skills"]:
            return "continue"
        return "end"

    def _check_cycle_or_continue(self, state: SkillGraphState) -> str:
        """判断是否发现循环或继续检测"""
        current = state["current_skill"]

        # 关键修复：如果 current_skill 为空，说明队列已空，应该结束
        if not current:
            return "no_dependencies"

        # 检查是否已在一级缓存
        if current in state["completed_skills"]:
            return "already_completed"

        # 检查是否发现循环（在二级缓存中）
        if current in state["in_progress_stack"][:-1]:  # 排除最后一个（刚加入的）
            return "cycle_detected"

        # 检查是否有依赖
        skill_info = self.skills_map.get(current)
        if skill_info and skill_info.dependencies:
            # 过滤已完成的依赖
            unfinished_deps = [
                dep for dep in skill_info.dependencies
                if dep in self.skills_map and dep not in state["completed_skills"]
            ]
            if unfinished_deps:
                return "has_dependencies"

        return "no_dependencies"

    def detect(self) -> Dict:
        """执行检测 - 使用简化的 DFS 递归实现"""
        try:
            print("[START] 开始检测（使用 DFS 递归）\n")

            # 一级缓存：已完成检测的Skill
            completed_skills = set()

            # 二级缓存：正在检测中的Skill（递归栈）
            in_progress_stack = []

            cycles = []
            cycles_set = set()

            def dfs(skill_name, depth=0):
                """DFS检测单个Skill"""
                indent = "  " * depth
                print(f"\n{indent}[检测] {skill_name}")

                # 检查一级缓存
                if skill_name in completed_skills:
                    print(f"{indent}   [OK] 已在一级缓存，跳过")
                    return

                # 检查二级缓存（递归栈）→ 发现循环
                if skill_name in in_progress_stack:
                    cycle_start = in_progress_stack.index(skill_name)
                    cycle = in_progress_stack[cycle_start:] + [skill_name]

                    # 去重
                    cycle_signature = "->".join(sorted(cycle))
                    if cycle_signature not in cycles_set:
                        print(f"{indent}   [CYCLE] 发现循环依赖: {' -> '.join(cycle)}")
                        cycles.append(cycle)
                        cycles_set.add(cycle_signature)
                    return

                # 加入二级缓存（递归栈）
                in_progress_stack.append(skill_name)
                print(f"{indent}   [+] 加入递归栈: {in_progress_stack}")

                # 递归检测依赖
                skill_info = self.skills_map.get(skill_name)
                if skill_info and skill_info.dependencies:
                    for dep in skill_info.dependencies:
                        if dep in self.skills_map:
                            dfs(dep, depth + 1)

                # 回溯：从二级缓存移到一级缓存
                in_progress_stack.remove(skill_name)
                completed_skills.add(skill_name)
                print(f"{indent}   [POP] 从递归栈弹出，移入一级缓存")

            # 对每个Skill进行DFS
            for skill_name in self.skills_map.keys():
                if skill_name not in completed_skills:
                    dfs(skill_name)

            print(f"\n[完成] 检测完成，共检测 {len(completed_skills)} 个Skill")

            return {
                "cycles": cycles,
                "conditional_cycles": [],
                "multiple_paths": [],
                "has_cycles": len(cycles) > 0,
                "total_checked": len(completed_skills)
            }

        except Exception as e:
            print(f"[ERROR] 检测失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "cycles": [],
                "conditional_cycles": [],
                "multiple_paths": [],
                "has_cycles": False,
                "error": str(e)
            }

    def calculate_metrics(self) -> Dict:
        """计算图指标"""
        node_count = len(self.skills_map)
        edge_count = sum(len(skill.dependencies) for skill in self.skills)

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

        max_edges = node_count * (node_count - 1)
        density = edge_count / max_edges if max_edges > 0 else 0

        isolated_nodes = [
            name for name, skill in self.skills_map.items()
            if len(skill.dependencies) == 0 and in_degrees[name] == 0
        ]

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
