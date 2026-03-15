"""文件哈希计算工具"""
import hashlib
from pathlib import Path


def calculate_file_hash(file_path: Path) -> str:
    """计算文件 MD5 哈希"""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        print(f"⚠️  计算哈希失败: {file_path} - {e}")
        return ""
