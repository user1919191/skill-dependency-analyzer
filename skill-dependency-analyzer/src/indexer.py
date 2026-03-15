"""索引管理器 - 增量更新"""
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime

try:
    from .models import SkillInfo
except ImportError:
    from models import SkillInfo


class SkillIndexer:
    """SKILL 索引管理器"""

    def __init__(self, index_path: str = "~/.claude/skill-dependency/skill-index.json"):
        self.index_path = Path(index_path).expanduser()
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index = self._load_index()

    def _load_index(self) -> Dict:
        """加载本地索引"""
        if self.index_path.exists():
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  加载索引失败: {e}")
                return self._create_empty_index()
        return self._create_empty_index()

    def _create_empty_index(self) -> Dict:
        """创建空索引"""
        return {
            "version": "1.0.0",
            "last_full_scan": datetime.now().isoformat(),
            "skills": {}
        }

    def save_index(self):
        """保存索引"""
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  保存索引失败: {e}")

    def get_changed_skills(self, all_skills: List[SkillInfo]) -> List[SkillInfo]:
        """识别变化的 SKILL"""
        changed = []
        for skill in all_skills:
            old_hash = self.index["skills"].get(skill.name, {}).get("hash")
            if old_hash != skill.file_hash:
                changed.append(skill)
        return changed

    def update_skill(self, skill: SkillInfo):
        """更新单个 SKILL 索引"""
        self.index["skills"][skill.name] = skill.to_dict()

    def update_skills(self, skills: List[SkillInfo]):
        """批量更新 SKILL 索引"""
        for skill in skills:
            self.update_skill(skill)
        self.save_index()

    def get_skill(self, name: str) -> SkillInfo:
        """获取 SKILL 信息"""
        data = self.index["skills"].get(name)
        if data:
            return SkillInfo.from_dict(data)
        return None

    def get_all_skills(self) -> List[SkillInfo]:
        """获取所有 SKILL"""
        return [SkillInfo.from_dict(data) for data in self.index["skills"].values()]
