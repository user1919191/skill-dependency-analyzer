"""数据模型定义"""
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime


@dataclass
class SkillInfo:
    """SKILL 信息"""
    name: str
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)  # 可选依赖
    trigger_keywords: List[str] = field(default_factory=list)
    file_path: str = ""
    file_hash: str = ""
    last_updated: datetime = field(default_factory=datetime.now)
    raw_content: str = ""  # 原始内容，用于提取证据

    def to_dict(self):
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "dependencies": self.dependencies,
            "optional_dependencies": self.optional_dependencies,
            "trigger_keywords": self.trigger_keywords,
            "file_path": self.file_path,
            "hash": self.file_hash,
            "last_updated": self.last_updated.isoformat(),
            "raw_content": self.raw_content
        }

    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建"""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            dependencies=data.get("dependencies", []),
            optional_dependencies=data.get("optional_dependencies", []),
            trigger_keywords=data.get("trigger_keywords", []),
            file_path=data.get("file_path", ""),
            file_hash=data.get("hash", ""),
            last_updated=datetime.fromisoformat(data.get("last_updated", datetime.now().isoformat())),
            raw_content=data.get("raw_content", "")
        )
