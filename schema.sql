-- ============================================================
-- 智能衣橱 + 轻量穿搭日记 数据库建表脚本
-- MySQL 5.7+ / utf8mb4 / InnoDB
-- ============================================================

CREATE DATABASE IF NOT EXISTS `smart_wardrobe`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `smart_wardrobe`;

-- ==========================================
-- 1. user（用户表）
-- ==========================================
CREATE TABLE `user` (
    `id`              BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `username`        VARCHAR(50)         NOT NULL COMMENT '登录用户名',
    `email`           VARCHAR(100)        DEFAULT NULL COMMENT '邮箱地址（选填）',
    `password_hash`   VARCHAR(255)        NOT NULL COMMENT '密码哈希（如 bcrypt）',
    `nickname`        VARCHAR(50)         DEFAULT NULL COMMENT '用户昵称',
    `avatar`          VARCHAR(500)        DEFAULT NULL COMMENT '头像图片URL',
    `created_at`      DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted_at`      DATETIME            DEFAULT NULL COMMENT '软删除时间，NULL表示未删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_email` (`email`),
    KEY `idx_deleted_at` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ==========================================
-- 2. item（衣物表）
-- ==========================================
CREATE TABLE `item` (
    `id`              BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `user_id`         BIGINT UNSIGNED     NOT NULL COMMENT '所属用户ID',
    `image_url`       VARCHAR(500)        NOT NULL COMMENT '衣物照片URL',
    `type`            VARCHAR(20)         NOT NULL COMMENT '类型：上装/下装/外套/鞋子/配饰等',
    `color`           VARCHAR(20)         DEFAULT NULL COMMENT '颜色',
    `season`          VARCHAR(10)         DEFAULT NULL COMMENT '适用季节：春/夏/秋/冬/全季',
    `occasion`        VARCHAR(20)         DEFAULT NULL COMMENT '适用场合：日常/工作/运动/正式等',
    `material`        VARCHAR(50)         DEFAULT NULL COMMENT '材质',
    `brand`           VARCHAR(50)         DEFAULT NULL COMMENT '品牌',
    `price`           DECIMAL(10,2)       DEFAULT NULL COMMENT '购买价格（元）',
    `purchase_date`   DATE                DEFAULT NULL COMMENT '购买日期',
    `status`          VARCHAR(20)         NOT NULL DEFAULT '正常' COMMENT '状态：正常/洗衣中/收纳中',
    `remark`          TEXT                DEFAULT NULL COMMENT '备注',
    `wear_count`      INT UNSIGNED        NOT NULL DEFAULT 0 COMMENT '累计穿着次数',
    `created_at`      DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted_at`      DATETIME            DEFAULT NULL COMMENT '软删除时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_type` (`type`),
    KEY `idx_season` (`season`),
    KEY `idx_color` (`color`),
    KEY `idx_status` (`status`),
    KEY `idx_deleted_at` (`deleted_at`),
    KEY `idx_user_deleted` (`user_id`, `deleted_at`),
    CONSTRAINT `fk_item_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='衣物表';

-- ==========================================
-- 3. outfit（搭配方案表）
-- ==========================================
CREATE TABLE `outfit` (
    `id`              BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `user_id`         BIGINT UNSIGNED     NOT NULL COMMENT '所属用户ID',
    `name`            VARCHAR(100)        DEFAULT NULL COMMENT '搭配名称（可选）',
    `created_at`      DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted_at`      DATETIME            DEFAULT NULL COMMENT '软删除时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_deleted_at` (`deleted_at`),
    KEY `idx_user_deleted` (`user_id`, `deleted_at`),
    CONSTRAINT `fk_outfit_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='搭配方案表';

-- ==========================================
-- 4. outfit_item（搭配-衣物关系表）
-- ==========================================
CREATE TABLE `outfit_item` (
    `id`              BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `outfit_id`       BIGINT UNSIGNED     NOT NULL COMMENT '搭配方案ID',
    `item_id`         BIGINT UNSIGNED     NOT NULL COMMENT '衣物ID',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_outfit_item` (`outfit_id`, `item_id`),
    KEY `idx_outfit_id` (`outfit_id`),
    KEY `idx_item_id` (`item_id`),
    CONSTRAINT `fk_oi_outfit` FOREIGN KEY (`outfit_id`) REFERENCES `outfit` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_oi_item`   FOREIGN KEY (`item_id`)   REFERENCES `item` (`id`)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='搭配-衣物多对多关系表';

-- ==========================================
-- 5. wear_log（穿搭日记表）
-- ==========================================
CREATE TABLE `wear_log` (
    `id`              BIGINT UNSIGNED     NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `user_id`         BIGINT UNSIGNED     NOT NULL COMMENT '所属用户ID',
    `outfit_id`       BIGINT UNSIGNED     DEFAULT NULL COMMENT '已保存搭配ID；日记主路径用 item_ids 写快照，此时为 NULL',
    `wear_date`       DATE                NOT NULL COMMENT '穿搭日期',
    `mood`            VARCHAR(10)         DEFAULT NULL COMMENT '心情：开心/平静/专注/疲惫/期待/低落/自信/随性',
    `content`         VARCHAR(500)        DEFAULT NULL COMMENT '一句话日记（选填）',
    `photo_url`       VARCHAR(500)        DEFAULT NULL COMMENT '现场照片URL（选填）',
    `temperature`     DECIMAL(4,1)        DEFAULT NULL COMMENT '当日温度，如 25.5',
    `weather`         VARCHAR(20)         DEFAULT NULL COMMENT '天气：晴/多云/阴/雨/雪等',
    `items_snapshot`  JSON                DEFAULT NULL COMMENT '当天衣物快照（item_id列表及当时信息），支持非outfit穿搭记录',
    `created_at`      DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`      DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted_at`      DATETIME            DEFAULT NULL COMMENT '软删除时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_outfit_id` (`outfit_id`),
    KEY `idx_wear_date` (`wear_date`),
    KEY `idx_deleted_at` (`deleted_at`),
    KEY `idx_user_date` (`user_id`, `wear_date`),
    KEY `idx_user_deleted` (`user_id`, `deleted_at`),
    CONSTRAINT `fk_wl_user`   FOREIGN KEY (`user_id`)   REFERENCES `user` (`id`)   ON DELETE CASCADE,
    CONSTRAINT `fk_wl_outfit` FOREIGN KEY (`outfit_id`) REFERENCES `outfit` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='穿搭日记表';
