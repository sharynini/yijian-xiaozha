# 项目上下文文档（PROJECT_CONTEXT）

> 依据仓库实际代码通读生成（`client/`、`server/`、`schema.sql`）。不确定处标注「待确认」。  
> 生成日期：2026-10-23。只读整理，未改业务代码。

---

## 1. 技术栈与目录结构

### 1.1 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | uni-app（Vue 3 + `<script setup>`）+ Pinia + Vite；目标端 H5 / 微信小程序（`package.json` scripts） |
| 后端 | Python Flask 3.0.3 + Flask-SQLAlchemy + Flask-JWT-Extended + Flask-CORS |
| 数据库 | MySQL（`schema.sql` 标注 5.7+ / utf8mb4 / InnoDB）；驱动 PyMySQL |
| 鉴权 | JWT Bearer（`Authorization: Bearer <token>`），默认过期 7 天 |
| 统一响应 | `{ code, msg, data }`；业务成功 `code === 0`，HTTP 多为 200 |

开发端口：

- 后端：`server/run.py` → `0.0.0.0:5001`
- 前端 H5：`client/vite.config.js` → `8081`

### 1.2 仓库目录结构（实际存在）

```
secret/
├── schema.sql                 # 建库建表脚本
├── MVP规划文档.md             # 产品规划（与实现可能有偏差）
├── docs/
│   └── PROJECT_CONTEXT.md     # 本文件
├── client/                    # uni-app 前端
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── pages.json         # 页面路由 + tabBar
│       ├── manifest.json
│       ├── uni.scss
│       ├── pages/             # 业务页面
│       ├── components/        # AppLoading、AppEmpty
│       ├── store/             # user.js、outfit.js
│       ├── utils/             # config / request / constants
│       └── composables/       # useRequest.js
└── server/                    # Flask 后端
    ├── requirements.txt
    ├── config.py
    ├── run.py
    └── app/
        ├── __init__.py        # 应用工厂、蓝图注册
        ├── extensions.py
        ├── common/            # response、errors
        ├── models/            # user / item / outfit / wear_log
        └── modules/           # auth / item / outfit / wear_log / recommend / upload / test / home
```

说明：`server/uploads/` 为运行时上传目录（配置在 `config.py`），不在静态源码树中强制存在。

---

## 2. 后端接口一览

注册位置：`server/app/__init__.py`。  
统一成功结构：`{ "code": 0, "msg": "...", "data": ... }`。  
JWT：需鉴权接口使用 `@jwt_required()`，请求头 `Authorization: Bearer <token>`。

### 2.1 测试（前缀 `/api/v1/test`，无需 JWT）

| 方法 | 路径 | JWT | 请求 | 响应 `data` |
|------|------|-----|------|-------------|
| GET | `/api/v1/test/ping` | 否 | 无 | `{ "message": "pong" }` |
| GET | `/api/v1/test/db` | 否 | 无 | 成功 `{ "database": "connected" }`；失败业务码 500 |

### 2.2 认证（前缀 `/api/auth`）

| 方法 | 路径 | JWT | 请求字段 | 响应 `data` |
|------|------|-----|----------|-------------|
| POST | `/api/auth/register` | 否 | Body JSON：`username`、`email`、`password`（服务端均必填；用户名 2–20；密码 ≥6；邮箱正则校验） | `User.to_dict()`：`user_id`、`username`、`email`、`nickname`、`avatar`、`created_at` |
| POST | `/api/auth/login` | 否 | Body：`account`（用户名或邮箱）、`password` | `{ "access_token", "user": User.to_dict() }` |
| GET | `/api/auth/profile` | 是 | 无 | `User.to_dict()` |

### 2.3 衣物（前缀 `/api/items`，均需 JWT）

| 方法 | 路径 | JWT | 请求字段 | 响应 `data` |
|------|------|-----|----------|-------------|
| POST | `/api/items` | 是 | Body：必填 `image_url`、`type`；可选 `color`、`season`、`occasion`、`material`、`brand`、`price`、`purchase_date`、`status`、`remark`。`type` ∈ {上装,下装,外套,鞋子,配饰}；`season` ∈ {春,夏,秋,冬,全季}；`occasion` ∈ {日常,工作,运动,正式}；`status` ∈ {正常,洗衣中,收纳中} | `Item.to_dict()` |
| GET | `/api/items` | 是 | Query：`type`、`color`、`season`（可选，等值 AND）；`page`（默认 1）、`per_page`（默认 10，最大 50） | `{ total, page, per_page, list: Item.to_dict[] }` |
| GET | `/api/items/<item_id>` | 是 | 路径参数 `item_id` | `Item.to_dict()` |
| PUT | `/api/items/<item_id>` | 是 | Body：部分更新，字段同创建白名单 | `Item.to_dict()` |
| DELETE | `/api/items/<item_id>` | 是 | 无 | `data` 可为 null；`msg`「删除成功」（软删除） |

`Item.to_dict()` 字段：`item_id`、`user_id`、`image_url`、`type`、`color`、`season`、`occasion`、`material`、`brand`、`price`、`purchase_date`、`status`、`remark`、`wear_count`、`created_at`、`updated_at`。

### 2.4 搭配（前缀 `/api/outfits`，均需 JWT）

| 方法 | 路径 | JWT | 请求字段 | 响应 `data` |
|------|------|-----|----------|-------------|
| POST | `/api/outfits` | 是 | Body：`item_ids`（非空整数数组，必填）；`name`（可选，空串/空 → 存 `null`） | 搭配详情：`outfit_id`、`user_id`、`name`、`created_at`、`items`（`Item.to_dict[]`）、`item_count` |
| GET | `/api/outfits/<outfit_id>` | 是 | 路径参数 | 同上详情结构 |

说明：无列表、更新、删除 outfit 接口（以当前 `routes.py` 为准）。

### 2.5 穿搭日记（前缀 `/api/wear-logs`，均需 JWT）

| 方法 | 路径 | JWT | 请求字段 | 响应 `data` |
|------|------|-----|----------|-------------|
| POST | `/api/wear-logs` | 是 | Body：`item_ids`（整数数组，去重后 1~12 件）与 `outfit_id` 二选一，**优先 `item_ids`**（此时 `outfit_id` 存 NULL）；仅传 `outfit_id` 时沿用旧逻辑。可选 `wear_date`（YYYY-MM-DD，缺省今天）、`mood`、`content`（≤500）、`photo_url`、`temperature`、`weather`（≤20）、`increase_wear_count`（默认 false） | `WearLog.to_dict()` |
| GET | `/api/wear-logs` | 是 | Query：`page`、`per_page` | `{ total, page, per_page, list: WearLog.to_dict[] }` |
| GET | `/api/wear-logs/<log_id>` | 是 | 路径参数 | `WearLog.to_dict()` |
| PUT | `/api/wear-logs/<log_id>` | 是 | Body：仅 `mood`、`content`（出现的字段才更新） | `WearLog.to_dict()` |
| DELETE | `/api/wear-logs/<log_id>` | 是 | 无 | 软删除成功 |

`WearLog.to_dict()`：`log_id`、`user_id`、`outfit_id`、`wear_date`、`mood`、`content`、`photo_url`、`temperature`、`weather`、`items`（来自 `items_snapshot`）、`created_at`、`updated_at`。

`mood` 枚举（`wear_log.py`）：开心 / 平静 / 专注 / 疲惫 / 期待 / 低落 / 自信 / 随性。

创建时按 `item_ids`（或旧路径下搭配内衣物）生成 `items_snapshot`（每项含 `item_id`、`image_url`、`type`、`color`、`season`），与写 `wear_log`、可选 `wear_count += 1` 同一事务。`item_ids` 须全部属于当前用户且未删除；空数组 `code=4002`，他人衣物 `code=4003`，已删除衣物 `code=4004`。

### 2.6 今日推荐（前缀 `/api/recommend`，需 JWT）

| 方法 | 路径 | JWT | 请求字段 | 响应 `data` |
|------|------|-----|----------|-------------|
| GET | `/api/recommend` | 是 | Query：`temperature` **必填**（数字，-50~60） | `{ temperature, seasons, season_label, total_candidates, count, list: [{ items: Item.to_dict[], reason }] }`；最多 3 套 |

规则摘要（`recommend/services.py`）：温度映射季节；仅 `status=正常` 且季节匹配或「全季」；模板为上装+下装（有外套则加一件）；按 `wear_count` 升序优先。

### 2.7 上传与静态资源（`upload` 蓝图无 url_prefix）

| 方法 | 路径 | JWT | 请求字段 | 响应 |
|------|------|-----|----------|------|
| POST | `/api/upload` | 是 | `multipart/form-data`，字段名固定 `file`；扩展名 jpg/jpeg/png/webp/gif | `data: { url }`（绝对 URL，基于 `request.host_url`） |
| GET | `/uploads/<filename>` | 否 | 路径文件名 | 直接返回图片文件（非 JSON 统一结构） |

单请求体上限：`MAX_CONTENT_LENGTH = 5MB`（`config.py`）。

### 2.8 首页调试台

| 方法 | 路径 | JWT | 说明 |
|------|------|-----|------|
| GET | `/` | 否 | 返回内嵌 HTML 接口调试台（`home/routes.py`），非业务 API |

### 2.9 接口前缀约定（事实）

| 模块 | 前缀 |
|------|------|
| test | `/api/v1/test` |
| 其余业务 | `/api/...`（无 `v1`） |
| 静态图 | `/uploads/...` |

详见第 5 节「已知问题」。

---

## 3. 数据库表与字段

依据：`schema.sql` + `server/app/models/*`。表名均为**单数**。

### 3.1 `user`

| 字段 | 类型（schema） | 说明 |
|------|----------------|------|
| id | BIGINT UNSIGNED PK AI | 主键 |
| username | VARCHAR(50) UNIQUE NOT NULL | 登录名 |
| email | VARCHAR(100) UNIQUE NULL | schema 可空；**注册接口强制必填** |
| password_hash | VARCHAR(255) NOT NULL | werkzeug 哈希 |
| nickname | VARCHAR(50) NULL | 注册时默认等于 username |
| avatar | VARCHAR(500) NULL | |
| created_at / updated_at | DATETIME | |
| deleted_at | DATETIME NULL | 软删除 |

模型序列化对外字段名用 `user_id`（非 `id`）。

### 3.2 `item`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 对外 `item_id` |
| user_id | BIGINT NOT NULL FK→user | |
| image_url | VARCHAR(500) NOT NULL | |
| type | VARCHAR(20) NOT NULL | 上装/下装/外套/鞋子/配饰 |
| color / season / occasion / material / brand | 可空字符串 | |
| price | DECIMAL(10,2) NULL | |
| purchase_date | DATE NULL | |
| status | VARCHAR(20) NOT NULL DEFAULT '正常' | 正常/洗衣中/收纳中 |
| remark | TEXT NULL | |
| wear_count | INT UNSIGNED DEFAULT 0 | |
| created_at / updated_at / deleted_at | DATETIME | 软删除 |

### 3.3 `outfit`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 对外 `outfit_id` |
| user_id | BIGINT NOT NULL FK→user | |
| name | VARCHAR(100) NULL | 可为 null（前端确认穿搭时传 `name: null`） |
| created_at / updated_at / deleted_at | DATETIME | |

### 3.4 `outfit_item`（搭配–衣物多对多关联表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 行主键 |
| outfit_id | BIGINT NOT NULL FK→outfit ON DELETE CASCADE | |
| item_id | BIGINT NOT NULL FK→item ON DELETE CASCADE | |
| UNIQUE(outfit_id, item_id) | | 同一搭配内同一衣物不重复 |

**如何使用（以代码为准）：**

1. **写入**：`POST /api/outfits` → `OutfitService.create` 先插入 `outfit`，`flush` 得 `outfit.id`，再对每个去重后的 `item_id` 插入一行 `OutfitItem(outfit_id, item_id)`。
2. **读取搭配详情**：`OutfitService._load_items` / `WearLogService._load_outfit_items` 通过 `Item JOIN OutfitItem`，按 `OutfitItem.id` 升序，且 `Item.deleted_at IS NULL`。
3. **写穿搭日记**：主路径按 `item_ids` 拉当前用户未删除衣物生成 `items_snapshot`；旧请求仍可从 `outfit_item` 拉取。之后列表/详情展示主要靠快照。
4. **无独立 REST CRUD**：没有直接增删 `outfit_item` 的接口；模型 `OutfitItem` 也无 `to_dict`。
5. **无软删除字段**：删 outfit（若将来做）会 CASCADE 清关联行；删 item 会 CASCADE 清关联行（schema）。当前业务对 item/outfit 多为软删除，**软删 item 后关联行仍可能残留**，但查询已过滤 `Item.deleted_at`（待确认：是否需定期清理孤儿关联）。

### 3.5 `wear_log`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 对外 `log_id` |
| user_id | BIGINT NOT NULL FK→user | |
| outfit_id | BIGINT NULL FK→outfit ON DELETE SET NULL | 主路径为 NULL；仅兼容旧请求传入有效 `outfit_id` 时填写 |
| wear_date | DATE NOT NULL | |
| mood | VARCHAR(10) NULL | |
| content | VARCHAR(500) NULL | |
| photo_url | VARCHAR(500) NULL | |
| temperature | DECIMAL(4,1) NULL | |
| weather | VARCHAR(20) NULL | |
| items_snapshot | JSON NULL | 创建时写入；序列化为响应字段 `items` |
| created_at / updated_at / deleted_at | DATETIME | |

### 3.6 关系简图

```
user 1───* item
user 1───* outfit
user 1───* wear_log
outfit *───* item   （经 outfit_item）
wear_log *───? outfit（可空 FK；当前创建路径几乎总有 outfit）
```

---

## 4. 前端页面与接口调用

依据：`client/src/pages.json` + 各页脚本。  
HTTP 封装：`utils/request.js`（自动带 Token；成功 resolve `body.data`）。  
`BASE_URL`：见第 5 节。

### 4.1 路由与 tabBar

| path | 标题 | tabBar |
|------|------|--------|
| pages/index/index | 今日推荐 | 首页 |
| pages/item/list | 我的衣橱 | 衣橱 |
| pages/item/add | 添加衣物 | 否（编辑同页 `?id=`） |
| pages/outfit/select | 选择今日穿搭 | 否 |
| pages/diary/create | 轻量日记 | 否 |
| pages/timeline/index | 穿搭时间轴 | 时间轴 |
| pages/diary/edit | 编辑日记 | 否 |
| pages/mine/index | 我的 | 我的 |
| pages/login/login | 登录 | 否 |
| pages/register/register | 注册 | 否 |

`App.vue` `onLaunch`：无本地 token 则 `reLaunch` 登录页。

### 4.2 各页调用的接口

| 页面 | 调用的接口 | 说明 |
|------|------------|------|
| **login** | `POST /api/auth/login`（经 `userStore.login`） | 成功后 `switchTab` 首页 |
| **register** | `POST /api/auth/register`（经 `userStore.register`） | 成功后返回登录页，不自动登录 |
| **index（首页）** | `GET /api/wear-logs?page=1&per_page=1`；`GET /api/recommend?temperature=` | 用最新一条 `wear_date` 是否等于今天判断「已记录」；「用这套去记录」只写 Pinia，跳 `diary/create`，本页不调 outfits |
| **item/list** | `GET /api/items`（筛选 + 分页）；`DELETE /api/items/:id` | 左滑软删除；点卡片进 `item/add?id=` |
| **item/add** | `POST /api/upload`（`uploadFile`）；`GET /api/items/:id`（编辑）；`POST /api/items` 或 `PUT /api/items/:id` | 先上传再提交 `image_url` |
| **outfit/select** | `GET /api/items?page=1&per_page=50` | 多选写入 `outfit` store；确认后进日记页（本页不建 outfit） |
| **diary/create** | `POST /api/upload`（可选现场照）；`POST /api/wear-logs`（`item_ids` + `increase_wear_count: true`，可选 mood/content/photo_url） | 跳过/完成都只调一次 wear-logs，不再建临时 outfit |
| **timeline** | `GET /api/wear-logs`；`DELETE /api/wear-logs/:id` | 编辑跳转 `diary/edit?log_id=` |
| **diary/edit** | `GET /api/wear-logs/:id`；`PUT /api/wear-logs/:id`（仅 mood、content） | |
| **mine** | `GET /api/auth/profile`；`GET /api/items?page=1&per_page=1`；`GET /api/wear-logs?page=1&per_page=1` | 用两接口的 `total` 作统计；退出仅清本地态 |

未在前端页面直接调用的后端能力：`GET /api/outfits/:id`、`GET /api/v1/test/*`、浏览器调试台 `/`。

### 4.3 前端状态与常量

- `store/user.js`：token / userInfo ↔ `sw_token` / `sw_user`
- `store/outfit.js`：跨页已选衣物；`selectedItemIds` 供 `POST /api/wear-logs`
- `utils/constants.js`：类型/季节/场合/颜色/心情与后端枚举对齐

---

## 5. 已知问题

（以下为仓库现状事实，与用户指定条目一致。）

### 5.1 日记提交不再创建临时 outfit

`pages/diary/create.vue` 只 `POST /api/wear-logs`（`item_ids`）。历史无名 outfit 仍可能留在库中，无自动清理。

### 5.2 `BASE_URL` 写死

`client/src/utils/config.js`：

```js
export const BASE_URL = 'http://127.0.0.1:5001'
```

注释提到真机需改局域网 IP，但代码无环境变量/构建替换。微信小程序真机若仍用 `127.0.0.1` 会连不上本机后端。

### 5.3 接口前缀 `/api` 与 `/api/v1/test` 不一致

`create_app` 中 test 蓝图为 `/api/v1/test`，auth/items/outfits/wear-logs/recommend/upload 为 `/api/...`（无版本段）。客户端业务路径均走 `/api/...`，仅调试台会打 test。

### 5.4 `config.py` 弱默认密钥与数据库密码

缺省环境变量时：

| 配置项 | 默认值 |
|--------|--------|
| `SECRET_KEY` | `dev-secret-key-change-me` |
| `JWT_SECRET_KEY` | `jwt-dev-secret-change-me` |
| `DB_PASSWORD` | `root`（另有 `DB_USER=root` 等） |

仅适合本地开发；生产若未覆盖环境变量存在风险。

---

## 6. 其它已观察到的差异（非猜测结论处标待确认）

| 点 | 说明 |
|----|------|
| schema vs 注册 | `user.email` schema 可空，注册服务强制邮箱 |
| schema vs 创建日记 | `wear_log.outfit_id` 可空；服务层主路径写 NULL，旧请求仍可传 `outfit_id` |
| 日记字数 | 前端日记页限制 100 字；后端 `content` 最长 500 |
| MVP 文档 vs 实现 | 规划中有「搭配命名保存/搭配 tab」等；当前无 outfit 列表页，确认穿搭走 `item_ids` 直写日记 |
| `AppLoading` / `AppEmpty` | 组件已实现；多数业务页仍手写 loading/empty（待确认是否计划统一替换） |
| `useRequest` | 已封装，首页/时间轴等多数未采用 |

---

## 7. 快速启动备忘（只读归纳）

1. MySQL 执行 `schema.sql`（库名默认 `smart_wardrobe`）。
2. `server`：配置 `.env`（可选）→ `pip install -r requirements.txt` → `python run.py`（5001）。
3. `client`：`npm i` → `npm run dev:h5`（8081）或 `dev:mp-weixin`；确保 `BASE_URL` 可达后端。
