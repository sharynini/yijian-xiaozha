# 项目上下文文档（PROJECT_CONTEXT）

> 依据仓库实际代码通读生成（`client/`、`server/`、`schema.sql`、`server/migrations/`）。不确定处标注「待确认」。  
> 首版：2026-10-23。2026-11-05：同步 10-25 之后的天气、AI 识别、抠图、手动搭配画布、拼贴日记、数据库迁移等改动；同日加入微信一键登录（`/api/auth/wx-login`、`user.openid`），以及隐私合规：注销账号、隐私授权弹窗、用户协议与隐私政策页；搭配方案（保存、列表、编辑、删除，衣橱页「搭配」标签），删除旧的 `outfit/select` 页；推荐升级（近 7 天降权、场合、配鞋、真实推荐理由）；时间轴详情页，日记记录当天温度与天气；时间轴按月分段与按日期筛选；衣物不足提示。

---

## 1. 技术栈与目录结构

### 1.1 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | uni-app（Vue 3 + `<script setup>`）+ Pinia + Vite；目标端 H5 / 微信小程序（`package.json` scripts） |
| 后端 | Python Flask 3.0.3 + Flask-SQLAlchemy + Flask-JWT-Extended + Flask-CORS + Flask-Migrate |
| 数据库 | MySQL（utf8mb4 / InnoDB）；驱动 PyMySQL；表结构变更走 Alembic 迁移（`server/migrations/`） |
| 鉴权 | JWT Bearer（`Authorization: Bearer <token>`），默认过期 7 天（`JWT_ACCESS_TOKEN_EXPIRES`） |
| 外部服务 | 和风天气（实时天气）、阿里云百炼 · 通义千问视觉模型（衣物识别）；均用标准库 `urllib` 调用 |
| 本地 AI | rembg（`isnet-general-use` 模型，CPU）抠图去背景，模型首次使用时下载到 `~/.rembg/models/` |
| 测试 | pytest（`server/tests/`，内存 SQLite，不连业务库） |
| 统一响应 | `{ code, msg, data }`；业务成功 `code === 0`，HTTP 多为 200 |

开发端口：

- 后端：`server/run.py` → `0.0.0.0:5001`（Flask 自带开发服务器）
- 前端 H5：`client/vite.config.js` → `8081`

### 1.2 仓库目录结构（实际存在）

```
secret/
├── CLAUDE.md / .cursor/rules/   # AI 协作规则
├── schema.sql                   # 初始建表脚本（已落后于迁移，见 5.x）
├── MVP规划文档.md               # 产品规划（与实现有偏差，见第 6 节）
├── docs/PROJECT_CONTEXT.md      # 本文件
├── client/                      # uni-app 前端
│   ├── .env.development / .env.production   # 仅 VITE_API_BASE（后端地址），无密钥
│   └── src/
│       ├── App.vue / main.js / manifest.json / pages.json / uni.scss
│       ├── pages/               # 业务页面（见 4.1）
│       ├── components/          # AppTabBar、AppLoading、AppEmpty、OutfitCollage、SafeImage、TaotaoSprite
│       ├── custom-tab-bar/      # 小程序自定义 tabBar 容器
│       ├── static/              # tabbar 图标、taotao 插画
│       ├── store/               # user.js、outfit.js
│       ├── utils/               # config / request / constants
│       └── composables/         # useRequest.js
└── server/                      # Flask 后端
    ├── .env.example             # 环境变量模板（无值）；真实值在 server/.env（已 gitignore）
    ├── requirements.txt / config.py / run.py / pytest.ini
    ├── migrations/              # Flask-Migrate / Alembic
    ├── scripts/                 # cleanup_orphan_outfits.py、migrate_image_urls.py（一次性运维脚本）
    ├── sql/                     # 历史手工 SQL
    ├── tests/                   # pytest
    ├── uploads/                 # 运行时上传目录（仅 .gitkeep 入库）
    └── app/
        ├── __init__.py          # 应用工厂、蓝图注册
        ├── extensions.py        # db / jwt / cors / migrate
        ├── common/              # response、errors、media（图片地址工具）
        ├── models/              # user / item / outfit(+outfit_item) / wear_log
        └── modules/             # auth / item / outfit / wear_log / recommend / weather / ai / upload / test / home
```

---

## 2. 后端接口一览

注册位置：`server/app/__init__.py`。  
统一成功结构：`{ "code": 0, "msg": "...", "data": ... }`。  
JWT：需鉴权接口使用 `@jwt_required()`，请求头 `Authorization: Bearer <token>`。  
用户隔离：所有业务查询均按 JWT 中的 `user_id` 过滤。

### 2.0 业务错误码（按模块，来自各 `services.py`）

| 区段 | 模块 | 已用码 |
|------|------|--------|
| 1xxx | 认证 | 1001 用户名已存在；1002 邮箱已注册；1003 用户名或密码错误；1004 参数错误；1005 用户不存在或已删除；1006 微信登录未配置；1007 微信 code 无效或已使用；1008 微信服务异常；1009 注销失败 |
| 2xxx | 衣物 | 2001 不存在；2002 参数不合法 |
| 3xxx | 搭配 | 3001 搭配不存在 / 含无效衣物；3002 参数错误（item_ids、名称、collage） |
| 4xxx | 穿搭日记 | 4001 不存在；4002 参数错误；4003 衣物不属于当前用户；4004 衣物已删除；4005 collage 结构错误 |
| 5xxx | 推荐 | 5002 temperature 缺失 / 非数字 / 超范围 |
| 6xxx | 上传 | 6001 未选文件 / 格式不支持 |
| 7xxx | 天气 | 7001 未配置；7002 经纬度错误；7003 天气服务不可用 |
| 8xxx | AI | 8001 识别未配置；8002 图片无效（非本人/非本站/不存在）；8003 识别失败；8004 太频繁；8005 抠图组件未安装；8006 没抠出衣物；8007 抠图失败 |

### 2.1 测试与调试台（仅 DEBUG 模式注册，生产不暴露）

| 方法 | 路径 | JWT | 说明 |
|------|------|-----|------|
| GET | `/api/v1/test/ping` | 否 | `{ "message": "pong" }` |
| GET | `/api/v1/test/db` | 否 | 数据库连通性 |
| GET | `/` | 否 | 内嵌 HTML 接口调试台（`home/routes.py`） |

### 2.2 认证（前缀 `/api/auth`）

| 方法 | 路径 | JWT | 请求字段 | 响应 `data` |
|------|------|-----|----------|-------------|
| POST | `/api/auth/register` | 否 | Body：`username`、`email`、`password`（均必填；用户名 2–20；密码 ≥6；邮箱正则） | `User.to_dict()`：`user_id`、`username`、`email`、`nickname`、`avatar`、`created_at` |
| POST | `/api/auth/login` | 否 | Body：`account`（用户名或邮箱）、`password` | `{ "access_token", "user" }` |
| POST | `/api/auth/wx-login` | 否 | Body：`code`（小程序 `wx.login` 返回） | `{ "access_token", "user", "is_new" }` |
| GET | `/api/auth/profile` | 是 | 无 | `User.to_dict()` |
| DELETE | `/api/auth/account` | 是 | 无 | `{ deleted_files }`；`msg`「账号已注销」 |

注销账号（`AuthService.delete_account`）：

- **彻底删除**（不是软删除），不可恢复：同一事务内按 `user_id` 显式删除 `wear_log` → `outfit_item` → `outfit` → `item` → `user`，不依赖外键级联
- 事务提交后删除上传目录里文件名以 `<user_id>_` 开头的全部图片（衣物照、抠图、现场照）；单个文件删除失败只记日志
- 旧 token 立即失效：`common/errors.py` 注册了 `token_in_blocklist_loader`，每个需登录的请求按主键查一次用户，用户不存在或已软删除时返回 401「Token 已失效」
- 注销后同一用户名、邮箱、微信 openid 可以重新注册（会是全新的空账号）

微信一键登录（`auth/services.py`）：

- 后端用 `WX_APPID` + `WX_APPSECRET` 调微信 `jscode2session` 换 openid（标准库 `urllib`，超时 5 秒），不保存 `session_key`，日志里不带含 AppSecret 的 URL
- openid 已存在 → 直接登录；不存在 → 自动建号：`username = wx_<10 位随机>`、`nickname = 衣橱主人`、`password_hash = NULL`
- openid 对应的账号已软删除时，先把旧账号的 openid 置空，再建新账号
- 微信账号没有密码，不能走账号密码登录（`check_password` 对空哈希恒为 False）；暂不支持把已有账号密码用户与微信绑定
- `User.to_dict()` 不返回 openid

无修改资料/密码、绑定微信接口。

### 2.3 衣物（前缀 `/api/items`，均需 JWT）

| 方法 | 路径 | 请求字段 | 响应 `data` |
|------|------|----------|-------------|
| POST | `/api/items` | 必填 `image_url`、`type`；可选 `color`、`season`、`occasion`、`material`、`brand`、`price`、`purchase_date`、`status`、`remark` | `Item.to_dict()` |
| GET | `/api/items` | Query：`type`、`color`、`season`（可选，等值 AND）；`page`（默认 1）、`per_page`（默认 10，最大 50） | `{ total, page, per_page, list }` |
| GET | `/api/items/<item_id>` | — | `Item.to_dict()` |
| PUT | `/api/items/<item_id>` | 部分更新，字段同创建白名单 | `Item.to_dict()` |
| DELETE | `/api/items/<item_id>` | — | 软删除 |

枚举（`item/services.py`，前端 `utils/constants.js` 对齐）：

- `type` ∈ {上装, 下装, 连衣裙, 外套, 鞋子, 包包, 帽子, 配饰}
- `season` ∈ {春, 夏, 秋, 冬, 全季}
- `occasion` ∈ {日常, 工作, 运动, 正式}
- `status` ∈ {正常, 洗衣中, 收纳中}
- `color`：前端与 AI 使用 15 个固定选项（黑色、白色、灰色、米色、卡其、棕色、蓝色、牛仔蓝、绿色、红色、粉色、紫色、黄色、橙色、花色）；后端不校验颜色取值，按纯文本存储（空串存 NULL）

`image_url` 写库前经 `to_storage_path` 转为相对路径 `/uploads/xxx`，返回时经 `to_public_url` 拼完整地址（见 2.9）。

`Item.to_dict()` 字段：`item_id`、`user_id`、`image_url`、`type`、`color`、`season`、`occasion`、`material`、`brand`、`price`、`purchase_date`、`status`、`remark`、`wear_count`、`created_at`、`updated_at`。

### 2.4 搭配（前缀 `/api/outfits`，均需 JWT）

| 方法 | 路径 | 请求字段 | 响应 `data` |
|------|------|----------|-------------|
| POST | `/api/outfits` | `item_ids`（1~12 件）；`name`（选填，≤30 字，空则自动命名「M月D日的搭配」）；`collage`（选填） | 搭配详情（见下） |
| GET | `/api/outfits` | Query：`page`、`per_page`（默认 10，最大 50） | `{ total, page, per_page, list: 搭配详情[] }` |
| GET | `/api/outfits/<outfit_id>` | — | 搭配详情 |
| PUT | `/api/outfits/<outfit_id>` | 部分更新：`name`（不能为空）、`item_ids`（整体替换）、`collage` | 搭配详情 |
| DELETE | `/api/outfits/<outfit_id>` | — | 软删除；`msg`「搭配已删除」 |

搭配详情：`outfit_id`、`user_id`、`name`、`collage`、`created_at`、`updated_at`、`items`（`Item.to_dict[]`，只含未删除衣物，按加入顺序）、`item_count`。

规则（`outfit/services.py`）：

- 列表只返回 `name` 非空、未删除的搭配，按 `updated_at` 倒序；`name` 为 NULL 的是早期日记流程自动建的临时搭配，不展示
- 衣物被删除后，详情和列表里自动去掉该衣物以及 `collage` 中对应的项；全部被删时 `item_count = 0`
- `PUT` 只改 `item_ids` 不传 `collage` 时，旧布局里已移除的衣物会被去掉；任何更新都会刷新 `updated_at`
- `collage` 校验与日记共用 `app/common/collage.py`（搭配用错误码 3002，日记用 4005）
- 删除搭配不影响已记录的日记（日记有自己的衣物快照）

### 2.5 穿搭日记（前缀 `/api/wear-logs`，均需 JWT）

| 方法 | 路径 | 请求字段 | 响应 `data` |
|------|------|----------|-------------|
| POST | `/api/wear-logs` | `item_ids`（去重后 1~12 件）与 `outfit_id` 二选一，优先 `item_ids`；可选 `wear_date`（YYYY-MM-DD，缺省今天）、`mood`、`content`（≤100 字）、`photo_url`、`temperature`、`weather`（≤20）、`collage`（见下）、`increase_wear_count`（默认 false） | `WearLog.to_dict()` |
| GET | `/api/wear-logs` | Query：`page`、`per_page`；`date`（选填，YYYY-MM-DD，只返回这一天，格式错误 4002） | `{ total, page, per_page, list }`，按 `wear_date` 倒序、同日按创建倒序 |
| GET | `/api/wear-logs/<log_id>` | — | `WearLog.to_dict()` |
| PUT | `/api/wear-logs/<log_id>` | 仅 `mood`、`content` | `WearLog.to_dict()` |
| DELETE | `/api/wear-logs/<log_id>` | — | 软删除 |

`collage`（手动搭配画布布局，选填）：数组，最多 12 项，每项 `{ item_id, x, y, w, z }`。`item_id` 必须在本次 `item_ids` 内；`x`/`y` 为左上角相对画布边长 0~1，`w` 为宽度比例 0.05~1，`z` 层级 0~99；越界值会被夹到合法范围，结构错误返回 4005。

`WearLog.to_dict()`：`log_id`、`user_id`、`outfit_id`、`wear_date`、`mood`、`content`、`photo_url`、`temperature`、`weather`、`items`（来自 `items_snapshot`，图片转完整地址）、`collage`、`created_at`、`updated_at`。

`mood` 枚举：开心 / 平静 / 专注 / 疲惫 / 期待 / 低落 / 自信 / 随性。

创建时生成 `items_snapshot`（每项含 `item_id`、`image_url`、`type`、`color`、`season`），与写 `wear_log`、可选 `wear_count += 1` 同一事务。

### 2.6 今日推荐（前缀 `/api/recommend`，需 JWT）

| 方法 | 路径 | 请求字段 | 响应 `data` |
|------|------|----------|-------------|
| GET | `/api/recommend` | Query：`temperature` 必填（-50~60）；`occasion` 选填（日常/工作/运动/正式） | `{ temperature, seasons, season_label, occasion, recent_days, total_candidates, count, list: [{ items, reason }] }`，最多 3 套 |

规则（`recommend/services.py`）：

1. 温度映射季节：<10℃ 冬；10~25℃ 春秋；≥25℃ 夏；「全季」始终参与
2. 仅当前用户、未删除、`status=正常` 的衣物
3. 指定 `occasion` 时只用该场合或**没填场合**的衣物
4. 基础单元为「上装+下装」或「连衣裙」单穿，两类交替取用；有外套、鞋子则各轮流附加一件（包包、帽子、配饰不参与）
5. 单品排序：近 7 天（含今天，`RECENT_DAYS`）日记快照里出现过的排后面（降权不排除），其次 `wear_count` 少的优先
6. `reason` 说明温度、季节、场合、是否配了外套/鞋子，以及「避开了近 7 天穿过的单品」或「有单品近 7 天穿过，衣橱里暂时没有更合适的替换」
7. 已保存的搭配方案不参与推荐

### 2.7 天气（前缀 `/api/weather`，需 JWT）

| 方法 | 路径 | 请求字段 | 响应 `data` |
|------|------|----------|-------------|
| GET | `/api/weather` | Query：`lat`、`lon` | `{ temperature, text, city }` |

- 和风天气 `/v7/weather/now` + `/geo/v2/city/lookup`；Key 只在后端
- 经纬度保留 2 位小数做进程内缓存 10 分钟
- 未配置返回 7001，前端退回手动调温度

### 2.8 AI（前缀 `/api/ai`，均需 JWT）

| 方法 | 路径 | 请求字段 | 响应 `data` |
|------|------|----------|-------------|
| POST | `/api/ai/recognize-item` | Body：`image_url`（上传接口返回的 url 或 path） | `{ type, color, season, occasion }`，识别不出或不合法的项为 null |
| POST | `/api/ai/cutout` | Body：`image_url` | `{ url, path }`：新生成的透明 PNG（原图文件保留） |

- 两个接口都只接受本人上传到本站的图片（文件名须以 `<user_id>_` 开头，禁止目录穿越）
- 识别：图片转 base64 发给通义千问 VL（默认模型 `qwen3-vl-plus`），后端再按枚举校验一遍；每用户每小时 30 次
- 抠图：本地 rembg，先缩放到最长边 `CUTOUT_MAX_SIDE`（默认 1024），只保留最大主体并裁掉透明边；每用户每小时 60 次；掩码后处理默认关闭
- 频率限制为进程内计数（多进程部署时各进程独立计数）

### 2.9 上传与静态资源（`upload` 蓝图无 url_prefix）

| 方法 | 路径 | JWT | 请求 | 响应 |
|------|------|-----|------|------|
| POST | `/api/upload` | 是 | `multipart/form-data`，字段 `file`；扩展名 jpg/jpeg/png/webp/gif | `data: { url, path }` |
| GET | `/uploads/<filename>` | 否 | — | 直接返回图片文件 |

- 文件名 `<user_id>_<uuid>.<ext>`；单请求上限 5MB（`MAX_CONTENT_LENGTH`）
- 只按扩展名判断格式，不校验文件内容
- 图片地址约定（`common/media.py`）：库里只存相对路径 `/uploads/xxx`；返回时优先用 `PUBLIC_BASE_URL` 拼接，未配置则用当前请求域名

### 2.10 接口前缀约定

| 模块 | 前缀 |
|------|------|
| test（仅 DEBUG） | `/api/v1/test` |
| 其余业务 | `/api/...`（无 `v1`） |
| 静态图 | `/uploads/...` |

---

## 3. 数据库表与字段

依据：`server/app/models/*` + `server/migrations/versions/*`。表名均为单数。

### 3.0 迁移

- 迁移链：`82555c282131_baseline` → `0b71cec01715_sync_wear_log_outfit_id_comment` → `a1a163ff1dc8_add_wear_log_collage` → `c3e5a7d9b1f2_add_user_openid` → `d4f6b8a0c2e3_add_outfit_collage`
- 已有库升级：`cd server && flask db upgrade`（需已加载 `server/.env`；具体 `FLASK_APP` 设置：待确认）
- 新建库：执行 `schema.sql`（已与最新迁移同步），再执行 `flask db stamp head`
- 改模型后：`flask db migrate -m "说明"` 生成脚本，检查后 `flask db upgrade`

### 3.1 `user`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT UNSIGNED PK AI | 对外 `user_id` |
| username | VARCHAR(50) UNIQUE NOT NULL | 登录名 |
| email | VARCHAR(100) UNIQUE NULL | 库里可空；注册接口强制必填 |
| password_hash | VARCHAR(255) NULL | werkzeug 哈希；微信建的账号为 NULL |
| openid | VARCHAR(64) UNIQUE NULL | 微信小程序 openid（不对外返回） |
| nickname | VARCHAR(50) NULL | 注册时默认等于 username |
| avatar | VARCHAR(500) NULL | |
| created_at / updated_at / deleted_at | DATETIME | 软删除 |

无 `unionid` 字段（目前只有小程序一个端，暂不需要）。

### 3.2 `item`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 对外 `item_id` |
| user_id | BIGINT NOT NULL FK→user | |
| image_url | VARCHAR(500) NOT NULL | 相对路径 `/uploads/xxx` |
| type | VARCHAR(20) NOT NULL | 见 2.3 枚举 |
| color / season / occasion / material / brand | 可空字符串 | |
| price | DECIMAL(10,2) NULL | |
| purchase_date | DATE NULL | |
| status | VARCHAR(20) NOT NULL DEFAULT '正常' | 正常/洗衣中/收纳中 |
| remark | TEXT NULL | |
| wear_count | INT UNSIGNED DEFAULT 0 | 记录日记时可 +1 |
| created_at / updated_at / deleted_at | DATETIME | 软删除 |

### 3.3 `outfit` / 3.4 `outfit_item`

- `outfit`：`id`、`user_id`、`name`（可空；新建时一定有值，NULL 为早期遗留）、`collage`（JSON，可空，画布布局）、`created_at`、`updated_at`、`deleted_at`
- `outfit_item`：`id`、`outfit_id`（FK CASCADE）、`item_id`（FK CASCADE），UNIQUE(outfit_id, item_id)
- 由 `POST/PUT /api/outfits` 写入；历史上日记流程创建过的无名 outfit 不会出现在列表里，也可用 `server/scripts/cleanup_orphan_outfits.py` 清理

### 3.5 `wear_log`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 对外 `log_id` |
| user_id | BIGINT NOT NULL FK→user（CASCADE） | |
| outfit_id | BIGINT NULL FK→outfit（SET NULL） | 主路径为 NULL |
| wear_date | DATE NOT NULL | |
| mood | VARCHAR(10) NULL | |
| content | VARCHAR(500) NULL | 业务上限 100 字（前后端一致） |
| photo_url | VARCHAR(500) NULL | 相对路径 |
| temperature | DECIMAL(4,1) NULL | 前端目前未传 |
| weather | VARCHAR(20) NULL | 前端目前未传 |
| items_snapshot | JSON NULL | 响应字段 `items` |
| collage | JSON NULL | 画布布局，见 2.5 |
| created_at / updated_at / deleted_at | DATETIME | 软删除 |

索引：`idx_wear_date`、`idx_deleted_at`、`idx_user_date(user_id, wear_date)`、`idx_user_deleted(user_id, deleted_at)`。

### 3.6 关系简图

```
user 1───* item
user 1───* outfit ───* outfit_item *─── item
user 1───* wear_log ──? outfit（可空）
wear_log.items_snapshot / collage 为 JSON，不建外键
```

---

## 4. 前端页面与接口调用

HTTP 封装：`utils/request.js`。功能：自动带 Token；小程序端没有 token 时先静默微信登录、遇到 401 先静默重登并重试一次（`_withAuth`，`uploadFile` 同样适用；`auth: false` 的请求如登录注册不走这一层）；仍 401 则清登录态并跳转登录页（防重复跳转）；1 秒内相同 GET 请求去重；`silent` 选项不弹错误提示；请求成功 resolve `body.data`，失败 reject 带 `code` 的错误体。  
`BASE_URL`：`utils/config.js` 读取 `import.meta.env.VITE_API_BASE`，来源见 7.2。

### 4.1 路由与 tabBar

tabBar 为自定义（`"custom": true`，组件 `components/AppTabBar.vue` + `custom-tab-bar/index.vue`），4 个 tab：首页 / 衣橱 / 时间轴 / 我的。

| path | 标题 | tabBar | 备注 |
|------|------|--------|------|
| pages/index/index | 今日推荐 | 首页 | 自定义导航栏 |
| pages/item/list | 我的衣橱 | 衣橱 | 自定义导航栏；顶部「衣物 / 搭配」标签 |
| pages/item/add | 添加衣物 | 否 | 编辑同页 `?id=` |
| pages/outfit/canvas | 手动搭配 | 否 | `?from=recommend` 载入推荐结果；`?outfit_id=` 载入已保存搭配（标题「编辑搭配」） |
| pages/diary/create | 轻量日记 | 否 | |
| pages/timeline/index | 穿搭日记 | 时间轴 | 自定义导航栏 |
| pages/timeline/detail | 日记详情 | 否 | `?log_id=`；时间轴点卡片进入 |
| pages/diary/edit | 编辑日记 | 否 | |
| pages/mine/index | 我的小窝 | 我的 | 自定义导航栏 |
| pages/login/login | 登录 | 否 | |
| pages/register/register | 注册 | 否 | |
| pages/legal/agreement | 用户协议 | 否 | 静态文本，含【待填写】占位 |
| pages/legal/privacy | 隐私政策 | 否 | 静态文本，含【待填写】占位；须与小程序后台「用户隐私保护指引」一致 |

`App.vue` 的 `onLaunch`：监听 `AUTH_EVENT`（`sw:auth-changed`）把静默登录结果同步到 Pinia；没有 token 时，小程序端后台静默 `wx.login`，不跳登录页；H5 端仍 `reLaunch` 到登录页。

用户在「我的」主动退出后写入 `sw_manual_logout`，小程序端不再自动静默登录，直到用户在登录页手动登录。

### 4.2 各页调用的接口与主要跳转

| 页面 | 接口 | 说明 |
|------|------|------|
| login | 小程序：`POST /api/auth/wx-login`（「微信一键登录」按钮），可展开账号密码表单；H5：`POST /api/auth/login` | 须先勾选同意《用户协议》《隐私政策》；成功后 `switchTab` 首页 |
| register | `POST /api/auth/register` | 成功后返回登录页，不自动登录 |
| index | `GET /api/wear-logs?page=1&per_page=1`；`uni.getLocation` → `GET /api/weather`；`GET /api/recommend`（带所选 `occasion`） | 场合选择（全部/日常/工作/运动/正式）记在本机 `sw_occasion`；推荐卡片最多显示 4 件，文案直接用后端 `reason`；天气结果本地缓存 30 分钟（key `sw_weather`）；定位失败或 7001 时改为手动调温度；推荐结果写入 outfit store；「用这套」跳 `outfit/canvas?from=recommend`，「自己搭」跳 `outfit/canvas` |
| item/list | 衣物标签：`GET /api/items`（筛选+分页）、`DELETE /api/items/:id`；搭配标签：`components/OutfitList.vue` 调 `GET/PUT/DELETE /api/outfits` | 衣物卡片进 `item/add?id=`；搭配卡片弹出「今天穿这套（写 store → `diary/create`）/ 在画布中编辑（`outfit/canvas?outfit_id=`）/ 重命名 / 删除」；下拉刷新、上拉加载按当前标签分别处理 |
| item/add | `POST /api/upload` → `POST /api/ai/cutout` → `POST /api/ai/recognize-item`；`GET/POST/PUT/DELETE /api/items` | 新增时上传后自动抠图（可用回原图或重新抠），抠完自动识别并回填合法选项；AI 调用均 silent，失败不打断手动填写 |
| outfit/canvas | `GET /api/items`；`GET /api/outfits/:id`（编辑时）；`POST /api/outfits`（保存）；`PUT /api/outfits/:id`（更新这套） | 拖动、缩放衣物生成 `collage`；「♡ 保存」存为搭配（名字选填）；编辑已有搭配时可选「更新这套 / 另存为新搭配」；「用这套去打卡」写入 outfit store 跳 `diary/create`；推荐进入时可「换一套」 |
| diary/create | `POST /api/upload`（可选现场照）；`POST /api/wear-logs`（`item_ids`、`mood`、`content`、`photo_url`、`collage`、`temperature`、`weather`、`increase_wear_count: true`） | 温度、天气取首页 30 分钟内的天气缓存 `sw_weather`，没有则为 null（手动调的温度不记录）；成功后清空 store，`switchTab` 时间轴 |
| timeline | `GET /api/wear-logs`（筛选时带 `date`） | 按「月份分段标题 → 日（N日 周X，今天/昨天）→ 小卡」三层展示，最新在前；标题左侧「📅 选日期」（`picker mode="date"`，最晚今天）筛选某一天，显示「只看 M月D日 ✕」标签，点 ✕ 恢复；筛选无结果时显示「看全部 / 去记录」；切换筛选只采用最后一次请求结果；有 `collage` 时用 `OutfitCollage` 还原拼贴；点卡片进 `timeline/detail?log_id=`；卡片上「💬」直接进 `diary/edit`；「⭐」只存在页面内存，刷新即丢失；`onShow` 时刷新列表 |
| timeline/detail | `GET /api/wear-logs/:id`；逐件静默 `GET /api/items/:id`（检查是否已删除）；`DELETE /api/wear-logs/:id` | 展示日期、天气温度、拼贴图（无则缩略图）、心情、一句话、现场照（可预览）、衣物清单（在衣橱的可点进编辑，已删的标注）；底部「删除这条记录 / 编辑心情和日记」；从编辑页返回时重新加载 |
| diary/edit | `GET /api/wear-logs/:id`；`PUT /api/wear-logs/:id` | 仅改 mood、content |
| mine | `GET /api/auth/profile`；`GET /api/items` 与 `GET /api/wear-logs`（取 total）；`DELETE /api/auth/account` | 退出只清本地状态；底部有用户协议、隐私政策、注销账号入口；注销需两次确认并输入「注销」，成功后清空本机全部缓存 |

前端未调用的后端能力：测试接口、调试台。

`utils/wardrobe.js`：`getItemCount()` 用 `GET /api/items?page=1&per_page=1` 的 `total` 取衣物数；`ensureHasItems()` 衣橱为空时弹框「衣橱还是空的」→「去添加」跳 `item/add`，并返回 false 拦住跳转；查询失败时不拦截。

连续弹两个系统弹窗（`showModal` / `showActionSheet`）时，后一个要延迟约 350ms 再弹，否则 H5 端会被吞掉（`mine` 注销、`canvas` 另存、`OutfitList` 重命名/删除都已这样处理）。

### 4.3 前端状态与常量

- `store/user.js`：token / userInfo，本地缓存 key 为 `sw_token` / `sw_user`；`wxLogin()` 手动微信登录；`logout()` 写入 `sw_manual_logout`；`deleteAccount()` 注销并 `clearStorageSync`
- `store/outfit.js`：`selectedItems`（跨页已选衣物，只保留 item_id/image_url/type/color/season）、`collage`、`recommendList` / `recommendIndex`（首页推荐整批结果，画布页轮换用）；`setOutfit()` 供画布、推荐、「今天穿这套」写入
- `utils/constants.js`：类型/季节/场合/颜色/心情与后端枚举对齐

### 4.4 小程序配置（`manifest.json` → `mp-weixin`）

- `appid` 为空（尚未注册小程序）
- 已声明 `scope.userLocation`（用途说明：获取当地气温推荐穿搭）与 `requiredPrivateInfos: ["getLocation"]`
- `urlCheck: false`（仅开发期可用，上线须配置合法域名）
- `__usePrivacyCheck__: true`（基础库新版本默认开启隐私校验，此字段是否仍需要：待确认，保留无副作用）
- 隐私授权弹窗：`components/PrivacyPopup.vue`，模块加载时注册一次 `wx.onNeedPrivacyAuthorization`，同意按钮为 `open-type="agreePrivacyAuthorization"`；已挂在会调用隐私接口的三个页面（index：`getLocation`；item/add、diary/create：`chooseImage`）。**以后新增调用隐私接口的页面，必须同样 import 并放置 `<PrivacyPopup />`**
- 组件需在页面里手动 import：`easycom.autoscan` 只自动识别 `components/名称/名称.vue` 结构

---

## 5. 已知问题与上线差距

### 5.1 小程序上线阻塞项

| 项 | 现状 |
|----|------|
| 微信登录联调 | 代码已完成（静默登录、不强制跳登录页），需注册小程序后在 `server/.env` 配置 `WX_APPID` / `WX_APPSECRET`，并在 `manifest.json` 填 appid 后真机验证 |
| 隐私合规 | 代码已完成；协议与政策中的【待填写】（运营者名称、联系邮箱、云服务商及地域、备份保留天数）需补全；小程序后台「用户隐私保护指引」需按隐私政策填写 |
| 内容安全 | 日记文字、上传图片没有接入内容安全检测（是否必须：待确认） |
| 生产部署 | 只有 Flask 开发服务器（`run.py`），无 WSGI 服务器、反向代理、HTTPS 配置；`ProductionConfig` 仅设 `DEBUG=False` |
| 域名与 AppID | `client/.env.production` 中 `VITE_API_BASE` 为占位地址 `https://api.example.com`；`manifest.json` 的 `appid` 为空 |

### 5.2 安全与运维

- `/uploads/<filename>` 无需鉴权即可访问，靠 uuid 文件名防猜测；日记现场照等私人图片也走这里
- 上传只按扩展名判断格式，不校验图片内容；服务端不做压缩
- 登录、注册没有频率限制；AI 频率限制和天气缓存都是进程内存，多进程或重启后失效
- 没有数据库与上传目录的备份方案
- rembg 首次加载模型较慢、内存占用较大，服务器配置需评估（待确认具体占用）
- `ALLOWED_ORIGINS` 默认 `*`，生产需收紧（小程序请求不受 CORS 影响，H5 受影响）

### 5.3 功能缺口（相对 `MVP规划文档.md`）

- 搭配方案不参与「今日推荐」（4b 评估后暂不做，等实际使用再定）
- 推荐：不含包包、帽子、配饰；「换一批」只在同一批 3 套内轮换
- 日记编辑只能改心情和文字（照片、日期、衣物不能改）；时间轴「⭐」收藏未持久化
- 衣物不足提示（`utils/wardrobe.js`）：衣橱 0 件时，首页「自己搭 / 去打卡」、时间轴「去记录」和浮动按钮、搭配标签「去搭一套」都会先弹框引导去添加；1 件时可进画布。首页推荐为空时按 0 件 / 1 件 / 2 件及以上给不同提示（与规划的「少于 2 件」不同：单件连衣裙也能推荐和记录）
- 2026-11-05 之前的日记没有温度、天气；之后只有在首页成功定位查到天气时才会记录

### 5.4 工程与一致性

- `schema.sql` 缺 `wear_log.collage`，与迁移不同步
- 接口前缀 `/api` 与 `/api/v1/test` 不一致（test 仅 DEBUG 注册，影响小）
- `AppLoading` / `AppEmpty` / `useRequest` 已封装，多数页面未使用
- 测试中大量使用 `datetime.utcnow()`，pytest 有弃用警告（不影响结果）
- 本机 `server/venv` 曾随项目目录移动，venv 内脚本路径可能指向旧目录，必要时重建

---

## 6. 与 MVP 规划的主要差异

| 点 | 规划 | 实际 |
|----|------|------|
| tabBar | 衣橱 / 搭配 / 记录 / 我的 | 首页 / 衣橱 / 时间轴 / 我的（无搭配 tab） |
| 确认穿搭 | 选已保存方案或临时多选 | 画布手动拼或用推荐结果，直接按 `item_ids` 写日记 |
| AI / 天气 | 列为后期扩展 | 已实现 AI 识别、本地抠图、和风天气 |
| 接口前缀 | `/api/v1` | `/api`（无版本段） |
| 注册字段 | 用户名 + 密码 | 用户名 + 邮箱 + 密码 |

---

## 7. 启动与配置备忘

### 7.1 后端环境变量（`server/.env`，模板见 `server/.env.example`）

> ⚠️ `server/.env` 含真实密钥，只在本机手动编辑，不提交仓库，也不要发给 AI 或他人。

| 变量 | 必填 | 用途 |
|------|------|------|
| `SECRET_KEY`、`JWT_SECRET_KEY` | 是 | 非 testing 环境缺失时启动直接报错 |
| `JWT_ACCESS_TOKEN_EXPIRES` | 否 | Token 有效期（秒），默认 7 天 |
| `WX_APPID`、`WX_APPSECRET` | 小程序必填 | 微信一键登录；不填则 `/api/auth/wx-login` 返回 1006 |
| `DB_USER`、`DB_PASSWORD`、`DB_HOST`、`DB_PORT`、`DB_NAME` | 是 | MySQL 连接（host/port/name 有默认值） |
| `ALLOWED_ORIGINS` | 否 | CORS 来源，逗号分隔，默认 `*` |
| `UPLOAD_FOLDER` | 否 | 上传目录，默认 `server/uploads` |
| `PUBLIC_BASE_URL` | 上线必填 | 图片对外域名前缀（如 `https://api.xxx.com`） |
| `QWEATHER_API_KEY`、`QWEATHER_API_HOST` | 否 | 和风天气；不填则前端手动调温度 |
| `DASHSCOPE_API_KEY` | 否 | 阿里云百炼；不填则不做 AI 识别 |
| `DASHSCOPE_BASE_URL`、`QWEN_VL_MODEL` | 否 | 一般留空用默认 |
| `REMBG_MODEL`、`CUTOUT_MAX_SIDE`、`CUTOUT_POST_PROCESS` | 否 | 抠图模型、缩放边长、掩码后处理开关 |
| `FLASK_CONFIG` | 否 | `run.py` 读取，`development`（默认）/ `production` |

`run.py` 先 `load_dotenv(server/.env, override=True)` 再导入 app。

### 7.2 前端环境变量

| 文件 | 内容 | 是否入库 |
|------|------|----------|
| `client/.env.development` | `VITE_API_BASE=http://127.0.0.1:5001` | 是 |
| `client/.env.production` | `VITE_API_BASE=https://api.example.com`（占位） | 是 |
| `client/.env.development.local` | 真机调试时写电脑局域网 IP | 否（gitignore） |

### 7.3 启动步骤

1. MySQL 建库（默认 `smart_wardrobe`），执行 `schema.sql`，再执行迁移补齐字段（见 3.0）
2. `server`：按 `.env.example` 手动创建并填写 `server/.env` → `pip install -r requirements.txt` → `python run.py`（5001）
3. `client`：`npm i` → `npm run dev:h5`（8081）或 `npm run dev:mp-weixin`
4. 测试：`cd server && python -m pytest -q`（2026-11-05 共 125 项通过）
