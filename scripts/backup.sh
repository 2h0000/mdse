#!/bin/bash
# Markdown 搜索引擎数据库备份脚本
# 用法: ./backup.sh [backup_directory]

set -e

# 配置
BACKUP_DIR="${1:-/backup/md-search}"
DATE=$(date +%Y%m%d_%H%M%S)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB_PATH="${DB_PATH:-$PROJECT_DIR/data/md_search.db}"
RETENTION_DAYS=30

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查数据库文件是否存在
if [ ! -f "$DB_PATH" ]; then
    log_error "数据库文件不存在: $DB_PATH"
    exit 1
fi

# 创建备份目录
mkdir -p "$BACKUP_DIR"
if [ $? -ne 0 ]; then
    log_error "无法创建备份目录: $BACKUP_DIR"
    exit 1
fi

log_info "开始备份数据库..."
log_info "源文件: $DB_PATH"
log_info "备份目录: $BACKUP_DIR"

# 备份文件名
BACKUP_FILE="$BACKUP_DIR/md_search_$DATE.db"

# 执行备份
cp "$DB_PATH" "$BACKUP_FILE"
if [ $? -ne 0 ]; then
    log_error "备份失败"
    exit 1
fi

log_info "数据库已备份到: $BACKUP_FILE"

# 压缩备份
log_info "压缩备份文件..."
gzip "$BACKUP_FILE"
if [ $? -ne 0 ]; then
    log_warn "压缩失败，但备份文件已创建"
else
    log_info "备份文件已压缩: $BACKUP_FILE.gz"
    BACKUP_FILE="$BACKUP_FILE.gz"
fi

# 获取备份文件大小
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log_info "备份文件大小: $BACKUP_SIZE"

# 清理旧备份
log_info "清理 $RETENTION_DAYS 天前的旧备份..."
OLD_BACKUPS=$(find "$BACKUP_DIR" -name "md_search_*.db.gz" -mtime +$RETENTION_DAYS)
if [ -n "$OLD_BACKUPS" ]; then
    echo "$OLD_BACKUPS" | while read -r file; do
        rm -f "$file"
        log_info "已删除旧备份: $(basename "$file")"
    done
else
    log_info "没有需要清理的旧备份"
fi

# 列出当前所有备份
log_info "当前备份列表:"
ls -lh "$BACKUP_DIR"/md_search_*.db.gz 2>/dev/null | awk '{print $9, $5}' | while read -r file size; do
    echo "  - $(basename "$file") ($size)"
done

log_info "备份完成！"

exit 0
