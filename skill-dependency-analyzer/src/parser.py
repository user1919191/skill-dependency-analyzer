"""SKILL 信息解析器"""
import re
from pathlib import Path
from typing import List, Tuple

try:
    from .models import SkillInfo
    from .hash_utils import calculate_file_hash
except ImportError:
    from models import SkillInfo
    from hash_utils import calculate_file_hash


# 依赖关系识别正则
DEPENDENCY_PATTERNS = [
    # 中文模式
    r"调用\s+`?(\w+[-\w]*)`?\s+skill",
    r"使用\s+`?(\w+[-\w]*)`?\s+skill",
    r"编排\s+([`\w\-、，,\s]+)",
    r"配合\s+`?(\w+[-\w]*)`?\s+skill",

    # 英文模式
    r"call\s+`?(\w+[-\w]*)`?\s+skill",
    r"use\s+`?(\w+[-\w]*)`?\s+skill",

    # 代码模式
    r"Skill\(.*?skill=['\"](\w+[-\w]*)['\"]",
    r"Task\(.*?subagent_type=['\"](\w+[-\w]*)['\"]",
]

# 可选依赖识别正则
OPTIONAL_DEPENDENCY_PATTERNS = [
    r"可选.*?`?(\w+[-\w]*)`?\s+skill",
    r"optional.*?`?(\w+[-\w]*)`?\s+skill",
    r"如果.*?调用\s+`?(\w+[-\w]*)`?\s+skill",
    r"可能.*?使用\s+`?(\w+[-\w]*)`?\s+skill",
]


def parse_skill_file(file_path: Path) -> SkillInfo:
    """解析单个 SKILL 文件"""
    content = file_path.read_text(encoding='utf-8')

    # 提取 SKILL 名称
    name = extract_skill_name(file_path, content)

    # 提取描述
    description = extract_description(content)

    # 提取依赖关系
    dependencies, optional_dependencies = extract_dependencies(content)

    # 提取触发关键词
    trigger_keywords = extract_trigger_keywords(content)

    # 计算文件哈希
    file_hash = calculate_file_hash(file_path)

    return SkillInfo(
        name=name,
        description=description,
        dependencies=dependencies,
        optional_dependencies=optional_dependencies,
        trigger_keywords=trigger_keywords,
        file_path=str(file_path),
        file_hash=file_hash,
        raw_content=content
    )


def extract_skill_name(file_path: Path, content: str) -> str:
    """提取 SKILL 名称"""
    # 从 frontmatter 提取
    match = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # 从文件名提取
    if file_path.name == "SKILL.md":
        return file_path.parent.name
    else:
        return file_path.stem


def extract_description(content: str) -> str:
    """提取描述"""
    match = re.search(r'^description:\s*(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return ""


def extract_dependencies(content: str) -> Tuple[List[str], List[str]]:
    """提取依赖关系

    Returns:
        (强依赖列表, 可选依赖列表)
    """
    dependencies = set()
    optional_dependencies = set()

    # 提取强依赖
    for pattern in DEPENDENCY_PATTERNS:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            dep = match.group(1)
            # 处理编排模式（可能包含多个 SKILL）
            if '、' in dep or '，' in dep or ',' in dep:
                deps = re.split(r'[、，,\s]+', dep)
                for d in deps:
                    d = d.strip('`').strip()
                    if d and d not in ['skill', 'skills']:
                        dependencies.add(d)
            else:
                dep = dep.strip('`').strip()
                if dep and dep not in ['skill', 'skills']:
                    dependencies.add(dep)

    # 提取可选依赖
    for pattern in OPTIONAL_DEPENDENCY_PATTERNS:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            dep = match.group(1).strip('`').strip()
            if dep and dep not in ['skill', 'skills']:
                optional_dependencies.add(dep)

    # 从强依赖中移除可选依赖
    dependencies = dependencies - optional_dependencies

    return sorted(list(dependencies)), sorted(list(optional_dependencies))


def extract_trigger_keywords(content: str) -> List[str]:
    """提取触发关键词"""
    keywords = []

    # 从触发条件章节提取
    trigger_section = re.search(r'##\s*触发条件.*?(?=##|$)', content, re.DOTALL | re.IGNORECASE)
    if trigger_section:
        section_text = trigger_section.group(0)
        # 提取引号中的关键词
        quoted = re.findall(r'["""\'](.*?)["""\']', section_text)
        keywords.extend(quoted)

    return keywords


def find_skill_files(skills_dir: Path) -> List[Path]:
    """查找所有 SKILL 文件（支持符号链接）"""
    skill_files = []

    # 遍历目录，支持符号链接
    for item in skills_dir.iterdir():
        if item.is_dir() or item.is_symlink():
            # 解析符号链接
            resolved_item = item.resolve() if item.is_symlink() else item

            if resolved_item.is_dir():
                # 在子目录中查找 SKILL.md
                skill_md = resolved_item / "SKILL.md"
                if skill_md.exists():
                    skill_files.append(skill_md)

                # 递归查找子目录
                for skill_file in resolved_item.rglob("SKILL.md"):
                    if skill_file not in skill_files:
                        skill_files.append(skill_file)

                # 查找 *.skill 文件
                for skill_file in resolved_item.rglob("*.skill"):
                    skill_files.append(skill_file)
        elif item.suffix == '.skill':
            skill_files.append(item)
        elif item.name == 'SKILL.md':
            skill_files.append(item)

    return skill_files


def parse_all_skills(skills_dir: Path) -> List[SkillInfo]:
    """解析所有 SKILL"""
    skill_files = find_skill_files(skills_dir)
    skills = []

    for file_path in skill_files:
        try:
            skill = parse_skill_file(file_path)
            skills.append(skill)
        except Exception as e:
            print(f"⚠️  解析失败: {file_path} - {e}")

    return skills
