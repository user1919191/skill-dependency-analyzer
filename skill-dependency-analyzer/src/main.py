"""SKILL 依赖关系分析器 - 主入口"""
import argparse
import time
import os
import sys
from pathlib import Path

try:
    from .parser import parse_all_skills
    from .indexer import SkillIndexer
    from .graph_builder import DependencyGraph
    from .langgraph_detector import LangGraphCycleDetector
    from .report_generator import ReportGenerator
except ImportError:
    from parser import parse_all_skills
    from indexer import SkillIndexer
    from graph_builder import DependencyGraph
    from langgraph_detector import LangGraphCycleDetector
    from report_generator import ReportGenerator


def get_platform_name() -> str:
    """获取当前平台名称"""
    return {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux")


def auto_detect_skills_dir():
    """自动检测 SKILL 目录（支持 Windows / macOS / Linux）"""
    candidates = []

    # 通用路径（Python expanduser 跨平台处理 ~ 符号）
    candidates.append(Path("~/.claude/skills").expanduser())

    # Windows 专用路径
    if sys.platform == "win32":
        userprofile = os.environ.get("USERPROFILE", "")
        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if userprofile:
            candidates.append(Path(userprofile) / ".claude" / "skills")
        if appdata:
            candidates.append(Path(appdata) / "Claude" / "skills")
        if localappdata:
            candidates.append(Path(localappdata) / "Claude" / "skills")

    # macOS 专用路径
    elif sys.platform == "darwin":
        home = Path.home()
        candidates.append(home / "Library" / "Application Support" / "Claude" / "skills")

    # 相对路径候选（当前目录及父目录）
    candidates.extend([
        Path.cwd() / "skills",
        Path.cwd().parent / "skills",
        Path(__file__).parent.parent.parent,  # 当前 skill 的父目录
    ])

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_dir():
                skill_files = list(candidate.rglob("SKILL.md")) + list(candidate.rglob("*.skill"))
                if len(skill_files) > 0:
                    return candidate
        except PermissionError:
            continue

    # 默认返回 ~/.claude/skills
    return Path("~/.claude/skills").expanduser()


def get_cache_dir():
    """获取缓存目录（优先使用项目内缓存）"""
    # 优先级1: 项目内 .cache 目录（便于移植）
    project_cache = Path(__file__).parent.parent / ".cache"

    # 优先级2: 全局缓存目录
    global_cache = Path("~/.claude/skill-dependency").expanduser()

    # 如果项目内缓存存在或可创建，优先使用
    try:
        project_cache.mkdir(parents=True, exist_ok=True)
        return project_cache
    except:
        # 降级到全局缓存
        global_cache.mkdir(parents=True, exist_ok=True)
        return global_cache


def get_output_dir():
    """获取输出目录（优先使用项目内 docs 目录）"""
    # 优先级1: 项目内 docs 目录
    project_docs = Path(__file__).parent.parent / "docs"

    # 优先级2: 当前工作目录
    cwd_docs = Path.cwd() / "docs"

    # 如果项目内 docs 存在或可创建，优先使用
    try:
        project_docs.mkdir(parents=True, exist_ok=True)
        return project_docs
    except:
        # 降级到当前工作目录
        try:
            cwd_docs.mkdir(parents=True, exist_ok=True)
            return cwd_docs
        except:
            # 最后降级到当前目录
            return Path.cwd()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="SKILL 依赖关系分析器")
    parser.add_argument("--skills-dir", type=str, default=None,
                        help="SKILL 目录路径（默认自动检测）")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="报告输出目录（默认：项目内 docs/ 目录）")
    parser.add_argument("--mode", type=str, default="incremental",
                        choices=["full", "incremental"],
                        help="分析模式：full=全量分析，incremental=增量更新")
    parser.add_argument("--max-nodes", type=int, default=20,
                        help="Mermaid 图最大节点数")
    parser.add_argument("--cache-dir", type=str, default=None,
                        help="缓存目录路径（默认自动选择）")
    parser.add_argument("--use-langgraph", action="store_true",
                        help="使用 LangGraph 进行循环依赖检测（推荐）")
    parser.add_argument("--detector", type=str, default="langgraph",
                        choices=["langgraph", "networkx"],
                        help="检测器类型：langgraph=LangGraph检测器（推荐），networkx=NetworkX检测器")

    args = parser.parse_args()

    start_time = time.time()

    # 自动检测或使用指定的 SKILL 目录
    if args.skills_dir:
        skills_dir = Path(args.skills_dir).expanduser()
    else:
        skills_dir = auto_detect_skills_dir()

    # 自动选择缓存目录
    if args.cache_dir:
        cache_dir = Path(args.cache_dir).expanduser()
        cache_dir.mkdir(parents=True, exist_ok=True)
    else:
        cache_dir = get_cache_dir()

    # 自动选择输出目录
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = get_output_dir()

    print("🔍 SKILL 依赖关系分析器")
    print(f"🖥️  运行平台: {get_platform_name()}")
    print(f"📂 扫描目录: {skills_dir}")
    print(f"💾 缓存目录: {cache_dir}")
    print(f"📄 输出目录: {output_dir}")
    print(f"🔧 检测器: {args.detector.upper()}")
    print()

    # 1. 解析所有 SKILL
    print("[1/4] 解析 SKILL 文件...")
    all_skills = parse_all_skills(skills_dir)
    print(f"✅ 发现 {len(all_skills)} 个 SKILL")

    if len(all_skills) == 0:
        print("\n⚠️  未找到任何 SKILL 文件")
        print(f"   请检查目录: {skills_dir}")
        print("   或使用 --skills-dir 指定正确的路径")
        return

    # 2. 增量更新检测
    index_path = cache_dir / "skill-index.json"
    indexer = SkillIndexer(str(index_path))
    changed_skills = indexer.get_changed_skills(all_skills)

    graph_cache_path = cache_dir / "graph.pkl"

    if args.mode == "incremental" and len(changed_skills) == 0:
        print("\n✅ 所有 SKILL 均无变化，使用缓存数据")
        graph = DependencyGraph(str(graph_cache_path))
        mode = "incremental"
        changed_count = 0
    elif args.mode == "incremental" and len(changed_skills) > 0:
        print(f"\n[2/4] 增量更新 {len(changed_skills)} 个 SKILL...")
        graph = DependencyGraph(str(graph_cache_path))
        graph.incremental_update(changed_skills)
        indexer.update_skills(changed_skills)
        print(f"✅ 增量更新完成")
        mode = "incremental"
        changed_count = len(changed_skills)
    else:
        print("\n[2/4] 构建依赖图（全量分析）...")
        graph = DependencyGraph(str(graph_cache_path))
        graph.build_from_skills(all_skills)
        indexer.update_skills(all_skills)
        print(f"✅ 依赖图构建完成")
        mode = "full"
        changed_count = len(all_skills)

    # 3. 检测循环依赖
    print("\n[3/4] 检测循环依赖...")

    if args.detector == "langgraph":
        # 使用 LangGraph 检测器
        print("🚀 使用 LangGraph 检测器（支持条件依赖和可视化）")
        try:
            langgraph_detector = LangGraphCycleDetector(all_skills, str(cache_dir))
            detection_result = langgraph_detector.detect()

            cycles = detection_result.get("cycles", [])
            conditional_cycles = detection_result.get("conditional_cycles", [])
            multiple_paths = detection_result.get("multiple_paths", [])

            if cycles:
                print(f"⚠️  检测到 {len(cycles)} 个直接循环依赖")
                for i, cycle in enumerate(cycles, 1):
                    print(f"   循环 {i}: {' → '.join(cycle)}")
            else:
                print("✅ 无直接循环依赖")

            if conditional_cycles:
                print(f"⚠️  检测到 {len(conditional_cycles)} 个条件循环依赖")

            # 保存 LangGraph 检测报告
            langgraph_report_path = cache_dir / "langgraph-detection-report.json"
            langgraph_detector.save_report(str(langgraph_report_path))
            print(f"📊 LangGraph 检测报告: {langgraph_report_path}")

            # 为了兼容后续代码，也使用 NetworkX 图
            graph = DependencyGraph(str(graph_cache_path))
            if mode == "incremental" and changed_count > 0:
                graph.incremental_update(changed_skills)
            else:
                graph.build_from_skills(all_skills)

        except Exception as e:
            print(f"⚠️  LangGraph 检测失败: {e}")
            print("   降级使用 NetworkX 检测器")
            args.detector = "networkx"

    if args.detector == "networkx":
        # 使用 NetworkX 检测器（传统方式）
        print("🔧 使用 NetworkX 检测器")
        cycles = graph.detect_cycles()
        multiple_paths = {}

        if cycles:
            print(f"⚠️  检测到 {len(cycles)} 个循环依赖")
            for i, cycle in enumerate(cycles, 1):
                print(f"   循环 {i}: {' → '.join(cycle + [cycle[0]])}")
        else:
            print("✅ 无循环依赖")

    # 4. 生成报告
    print("\n[4/4] 生成报告...")
    reporter = ReportGenerator(graph)
    report = reporter.generate_report(mode=mode, changed_count=changed_count)

    # 保存报告
    report_path = output_dir / "skill-dependency-report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    # 保存历史报告
    history_dir = cache_dir / "reports"
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    history_path = history_dir / f"report-{timestamp}.md"
    with open(history_path, 'w', encoding='utf-8') as f:
        f.write(report)

    elapsed = time.time() - start_time

    print(f"✅ 报告生成完成")
    print()
    print("=" * 60)
    print(f"✅ 分析完成！耗时 {elapsed:.1f} 秒")
    print()
    print("关键发现：")
    if len(cycles) == 0:
        print("- ✅ 无循环依赖")
    else:
        print(f"- ⚠️  {len(cycles)} 个循环依赖")

    if args.detector == "langgraph":
        print(f"- {len(multiple_paths)} 对 SKILL 存在多路径")
        if conditional_cycles:
            print(f"- ⚠️  {len(conditional_cycles)} 个条件循环依赖")
    else:
        multiple_paths_dict = graph.find_multiple_paths(max_pairs=10)
        print(f"- {len(multiple_paths_dict)} 对 SKILL 存在多路径")

    top_skills = graph.get_top_skills("out_degree", 1)
    if top_skills:
        print(f"- {top_skills[0][0]} 是最核心的编排 SKILL（出度: {int(top_skills[0][1])}）")

    print()
    print(f"完整报告：{report_path}")
    print(f"历史报告：{history_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
