#!/usr/bin/env bash
# 每日备份：数据库 + 上传图片，保留最近 KEEP_DAYS 天
#
# 用法（在服务器上，用 wardrobe 用户）：
#   bash /srv/smart-wardrobe/deploy/backup.sh
# 定时（crontab -e，每天凌晨 3:30）：
#   30 3 * * * bash /srv/smart-wardrobe/deploy/backup.sh >> /srv/backups/smart-wardrobe/backup.log 2>&1
#
# 数据库账号密码不写在脚本里，从 ~/.my.cnf 读取（权限必须是 600），内容形如：
#   [mysqldump]
#   user=备份用的数据库账号
#   password=该账号的密码
# 这个文件由你在服务器上手动创建，见 deploy/README.md 第 9 步。
#
# 注意：备份和数据在同一台服务器上，服务器整机损坏时会一起丢失。
# 建议定期把 BACKUP_DIR 下载到本机，或同步到对象存储（如阿里云 OSS / 腾讯云 COS）。
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/smart-wardrobe}"
DB_NAME="${DB_NAME:-smart_wardrobe}"
BACKUP_DIR="${BACKUP_DIR:-/srv/backups/smart-wardrobe}"
KEEP_DAYS="${KEEP_DAYS:-14}"

STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
umask 077

echo "[$(date '+%F %T')] 开始备份 ${STAMP}"

# 1. 数据库：--single-transaction 不锁表；结果 gzip 压缩
mysqldump --single-transaction --routines --triggers --no-tablespaces "$DB_NAME" \
  | gzip > "$BACKUP_DIR/db-${STAMP}.sql.gz"

# 2. 上传图片
tar -czf "$BACKUP_DIR/uploads-${STAMP}.tar.gz" -C "$APP_DIR/server" uploads

# 3. 校验压缩包完整
gzip -t "$BACKUP_DIR/db-${STAMP}.sql.gz"
gzip -t "$BACKUP_DIR/uploads-${STAMP}.tar.gz"

# 4. 删除过期备份
find "$BACKUP_DIR" -maxdepth 1 -type f \( -name 'db-*.sql.gz' -o -name 'uploads-*.tar.gz' \) \
  -mtime +"$KEEP_DAYS" -delete

echo "[$(date '+%F %T')] 备份完成：$(du -sh "$BACKUP_DIR" | cut -f1)"
