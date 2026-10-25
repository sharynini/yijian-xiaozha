-- 可重复执行：将 wear_log.outfit_id 改为可空（已可空则跳过）
-- 表名以 schema.sql 为准：wear_log（不是 wear_logs）
-- 用法：mysql -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < server/sql/alter_wear_log_outfit_id_nullable.sql

SET @need_alter := (
    SELECT IF(COUNT(*) = 1 AND MAX(IS_NULLABLE) = 'NO', 1, 0)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'wear_log'
      AND COLUMN_NAME = 'outfit_id'
);

SET @sql := IF(
    @need_alter = 1,
    'ALTER TABLE `wear_log` MODIFY `outfit_id` BIGINT UNSIGNED DEFAULT NULL COMMENT ''已保存搭配ID；日记主路径用 item_ids 写快照，此时为 NULL''',
    'SELECT ''wear_log.outfit_id already nullable or column missing'' AS msg'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
