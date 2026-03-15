#!/usr/bin/env python3
"""
清理历史报告定时任务
每2天执行一次，删除两周前的报告文件
"""
import os
import time
from pathlib import Path
from datetime import datetime, timedelta


def cleanup_old_reports(reports_dir: Path, days_to_keep: int = 14):
    """
    清理指定天数之前的报告文件

    Args:
        reports_dir: 报告目录路径
        days_to_keep: 保留最近多少天的报告（默认14天）
    """
    if not reports_dir.exists():
        print(f"⚠️  报告目录不存在: {reports_dir}")
        return

    # 计算截止时间
    cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
    cutoff_date = datetime.fromtimestamp(cutoff_time)

    print(f"🗑️  开始清理 {days_to_keep} 天前的报告...")
    print(f"📅 截止日期: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")

    deleted_count = 0
    total_size = 0

    # 遍历报告目录
    for report_file in reports_dir.glob("report-*.md"):
        # 获取文件修改时间
        file_mtime = report_file.stat().st_mtime

        # 如果文件早于截止时间，删除
        if file_mtime < cutoff_time:
            file_size = report_file.stat().st_size
            file_date = datetime.fromtimestamp(file_mtime)

            try:
                report_file.unlink()
                deleted_count += 1
                total_size += file_size
                print(f"  ✅ 删除: {report_file.name} (创建于 {file_date.strftime('%Y-%m-%d')})")
            except Exception as e:
                print(f"  ❌ 删除失败: {report_file.name} - {e}")

    # 输出统计信息
    if deleted_count > 0:
        size_mb = total_size / (1024 * 1024)
        print(f"\n✅ 清理完成！")
        print(f"   删除文件数: {deleted_count}")
        print(f"   释放空间: {size_mb:.2f} MB")
    else:
        print(f"\n✅ 无需清理，所有报告都在保留期内")


def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = Path(__file__).parent

    # 报告目录路径
    reports_dir = script_dir.parent / ".cache" / "reports"

    print("=" * 60)
    print("📊 SKILL 依赖分析报告清理工具")
    print("=" * 60)
    print(f"📂 报告目录: {reports_dir}")
    print()

    # 执行清理
    cleanup_old_reports(reports_dir, days_to_keep=14)

    print("=" * 60)


if __name__ == "__main__":
    main()
