#!/bin/bash
# 安装定时任务脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "SKILL Dependency Analyzer - 定时任务安装"
echo "=================================================="
echo ""

# 创建日志目录
LOGS_DIR="$PROJECT_DIR/logs"
if [ ! -d "$LOGS_DIR" ]; then
    mkdir -p "$LOGS_DIR"
    echo "✅ 创建日志目录: $LOGS_DIR"
fi

# 生成 crontab 条目
CRON_ENTRY="0 2 */2 * * cd $PROJECT_DIR && /usr/bin/python3 scripts/cleanup_old_reports.py >> logs/cleanup.log 2>&1"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "cleanup_old_reports.py"; then
    echo "⚠️  定时任务已存在"
    echo ""
    echo "当前定时任务："
    crontab -l | grep "cleanup_old_reports.py"
    echo ""
    read -p "是否要更新定时任务？(y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 取消安装"
        exit 0
    fi

    # 删除旧的定时任务
    crontab -l | grep -v "cleanup_old_reports.py" | crontab -
    echo "✅ 已删除旧的定时任务"
fi

# 添加新的定时任务
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✅ 定时任务安装成功！"
echo ""
echo "定时任务配置："
echo "  执行频率: 每2天一次（凌晨2点）"
echo "  清理规则: 删除两周前的报告"
echo "  日志文件: $LOGS_DIR/cleanup.log"
echo ""
echo "查看定时任务："
echo "  crontab -l | grep cleanup_old_reports"
echo ""
echo "手动执行清理："
echo "  python3 $SCRIPT_DIR/cleanup_old_reports.py"
echo ""
echo "卸载定时任务："
echo "  crontab -l | grep -v cleanup_old_reports.py | crontab -"
echo ""
echo "=================================================="
