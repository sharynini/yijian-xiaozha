# 部署文档（单台云服务器）

> 适用：一台国内云服务器 + 一个**已备案**的域名，部署后端接口给微信小程序使用。
> 标「⚠️ 你自己操作」的步骤涉及密码或密钥：只在服务器上手动输入，**不要发给任何人（包括 AI 助手）**，也不要提交到 git。
> 服务器系统按 **Ubuntu 24.04** 编写；其它系统命令会略有不同（待确认）。

```
小程序 ──HTTPS──▶ nginx ──/api/*──▶ gunicorn(127.0.0.1:5001, 1 进程 × 8 线程) ──▶ MySQL
                     └──/uploads/*──▶ 直接读 /srv/smart-wardrobe/server/uploads
```

---

## 0. 准备清单

| 项 | 要求 |
|---|---|
| 服务器 | 2 核 4G 起（抠图模型常驻内存约几百 MB）；系统 Ubuntu 24.04；安全组放行 22、80、443 |
| 域名 | 已完成 ICP 备案；添加一条 A 记录，例如 `api.你的域名` → 服务器公网 IP |
| 小程序 | 已注册，拿到 AppID、AppSecret；已完成小程序备案 |
| 本机 | 代码已提交到 git（`launch-prep` 合并到 `main` 之后再部署） |

下文用 `api.example.com` 代表你的接口域名，请全部替换。

---

## 1. 安装系统软件

```bash
sudo apt update
sudo apt install -y nginx mysql-server git rsync certbot python3-certbot-nginx build-essential
```

项目依赖锁定在 **Python 3.13**（`server/requirements.lock.txt` 按 3.13 生成）。Ubuntu 24.04 自带 3.12，需另装 3.13：

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev
python3.13 --version
```

## 2. 建运行用户和目录

```bash
sudo useradd --system --create-home --shell /bin/bash wardrobe
sudo mkdir -p /srv/smart-wardrobe /srv/backups/smart-wardrobe
sudo chown -R wardrobe:wardrobe /srv/smart-wardrobe /srv/backups/smart-wardrobe
```

## 3. 上传代码

仓库目前没有远程地址，二选一：

**方式 A：从本机用 rsync 直接传**（在你的 Mac 上执行，`服务器IP` 换成实际值）：

```bash
cd "/Users/shenhaimeiyouyu/Desktop/个人项目/智能衣柜+轻手帐/secret" && rsync -av --delete --exclude '.git' --exclude 'node_modules' --exclude 'venv' --exclude '__pycache__' --exclude '.env' --exclude '.env.*.local' --exclude 'server/uploads/*' --exclude 'backup*.sql' --exclude 'client/dist' ./ root@服务器IP:/srv/smart-wardrobe/
```

传完在服务器上执行 `sudo chown -R wardrobe:wardrobe /srv/smart-wardrobe`。

**方式 B：推到私有仓库（GitHub / Gitee）再在服务器 `git clone`**。仓库务必设为**私有**。

> 两种方式都**不会**带上 `server/.env`，它要在第 5 步在服务器上单独创建。

## 4. 建数据库（⚠️ 你自己操作）

```bash
sudo mysql
```

在 MySQL 里执行（`强密码` 换成你自己生成的密码，不要和其它地方重复）：

```sql
CREATE DATABASE smart_wardrobe DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'wardrobe'@'localhost' IDENTIFIED BY '强密码';
GRANT ALL PRIVILEGES ON smart_wardrobe.* TO 'wardrobe'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

## 5. 配置后端环境变量（⚠️ 你自己操作）

```bash
sudo -u wardrobe -i
cd /srv/smart-wardrobe/server
cp .env.example .env
chmod 600 .env
nano .env
```

逐项填写（`.env.example` 里每项都有说明）：

| 变量 | 服务器上填什么 |
|---|---|
| `FLASK_CONFIG` | `production` |
| `TRUST_PROXY` | `1`（在 nginx 后面） |
| `LOG_LEVEL` | 留空或 `INFO` |
| `SECRET_KEY`、`JWT_SECRET_KEY` | 各生成一串随机值：在服务器执行 `python3.13 -c "import secrets;print(secrets.token_urlsafe(48))"` 两次，**不要沿用本机开发用的值** |
| `DB_USER`、`DB_PASSWORD`、`DB_NAME` | 第 4 步建的 `wardrobe`、你设的密码、`smart_wardrobe` |
| `PUBLIC_BASE_URL` | `https://api.example.com` |
| `ALLOWED_ORIGINS` | 只给小程序用可以填 `https://servicewechat.com`；以后上线 H5 再加 H5 域名（逗号分隔） |
| `WX_APPID`、`WX_APPSECRET` | 小程序后台「开发管理 → 开发设置」 |
| `QWEATHER_*`、`DASHSCOPE_API_KEY` | 和本机一致即可（建议在各平台控制台给服务器单独建一个 Key） |

保存后 `exit` 回到你自己的账号。

## 6. 安装 Python 依赖并建表

```bash
sudo -u wardrobe -i
cd /srv/smart-wardrobe/server
python3.13 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.lock.txt
venv/bin/flask --app wsgi db upgrade
mkdir -p uploads /srv/smart-wardrobe/.rembg
exit
```

`db upgrade` 会从空库一路建好所有表。若最后一行是 `Running upgrade ... -> d4f6b8a0c2e3`（或更新的版本号）即成功。

> 想把本机已有数据搬上去：在本机用 `mysqldump` 导出、在服务器导入，再把本机 `server/uploads/` 里的图片用 rsync 传到服务器同一目录。导出文件含用户数据，传完即删。

## 7. 启动后端服务

```bash
sudo cp /srv/smart-wardrobe/deploy/smart-wardrobe.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now smart-wardrobe
sudo systemctl status smart-wardrobe
curl -s http://127.0.0.1:5001/api/health
```

看到 `"status":"ok","database":"ok"` 说明后端和数据库都正常。启动日志里如果有「生产环境未配置 …」的警告，回第 5 步补齐：

```bash
sudo journalctl -u smart-wardrobe -n 50
```

## 8. 配置 nginx 和 HTTPS 证书

```bash
sudo cp /srv/smart-wardrobe/deploy/nginx.conf.example /etc/nginx/sites-available/smart-wardrobe
sudo sed -i 's/api.example.com/你的接口域名/g' /etc/nginx/sites-available/smart-wardrobe
sudo ln -s /etc/nginx/sites-available/smart-wardrobe /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

首次还没有证书，先申请（certbot 会临时用 80 端口验证域名，并自动续期）：

```bash
sudo certbot certonly --webroot -w /var/www/html -d 你的接口域名
```

如果此时 nginx 因为找不到证书文件而无法启动，先把配置里 `listen 443` 那整个 server 块注释掉，`sudo nginx -t && sudo systemctl reload nginx`，申请成功后再取消注释。

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -s https://你的接口域名/api/health
```

## 9. 定时备份（⚠️ `.my.cnf` 你自己操作）

```bash
sudo -u wardrobe -i
nano ~/.my.cnf
```

写入（用第 4 步的账号密码）：

```
[mysqldump]
user=wardrobe
password=你的数据库密码
```

```bash
chmod 600 ~/.my.cnf
bash /srv/smart-wardrobe/deploy/backup.sh
ls -lh /srv/backups/smart-wardrobe
crontab -e
```

在 crontab 最后加一行（每天 3:30 备份）：

```
30 3 * * * bash /srv/smart-wardrobe/deploy/backup.sh >> /srv/backups/smart-wardrobe/backup.log 2>&1
```

备份和数据在同一台机器上，建议每周把 `/srv/backups/smart-wardrobe` 下载到本机一次，或同步到对象存储。

## 10. 小程序后台配置（⚠️ 你自己操作）

小程序后台 →「开发管理 → 开发设置 → 服务器域名」：

| 类型 | 填写 |
|---|---|
| request 合法域名 | `https://你的接口域名` |
| uploadFile 合法域名 | `https://你的接口域名` |
| downloadFile 合法域名 | `https://你的接口域名`（图片在这个域名下） |

天气、AI 识别都由后端调用，不需要加到小程序域名里。

## 11. 前端打包（第 7 步提审前做）

在本机：`client/.env.production` 的 `VITE_API_BASE` 改成 `https://你的接口域名`，`client/src/manifest.json` 填好 AppID，然后：

```bash
cd "/Users/shenhaimeiyouyu/Desktop/个人项目/智能衣柜+轻手帐/secret/client" && npm run build:mp-weixin
```

用微信开发者工具导入 `client/dist/build/mp-weixin` 上传体验版。

---

## 以后更新代码

```bash
# 本机：重新执行第 3 步的 rsync（或 git pull）
sudo -u wardrobe -i
cd /srv/smart-wardrobe/server
venv/bin/pip install -r requirements.lock.txt   # 依赖有变化时
venv/bin/flask --app wsgi db upgrade            # 有新迁移时
exit
sudo systemctl restart smart-wardrobe
curl -s https://你的接口域名/api/health
```

## 常见问题

| 现象 | 排查 |
|---|---|
| `/api/health` 返回 `database: error` | `.env` 里数据库账号密码；`sudo systemctl status mysql` |
| 小程序请求失败「不在合法域名列表」 | 第 10 步域名是否填对、是否 https |
| 图片打不开 | `.env` 的 `PUBLIC_BASE_URL`；nginx 的 `/uploads/` alias 路径；文件权限是否属于 wardrobe |
| 登录总提示「太频繁」 | `.env` 是否 `TRUST_PROXY=1`（否则所有人被当成同一个 IP） |
| 第一次抠图很慢 | 正常，首次会下载模型到 `/srv/smart-wardrobe/.rembg`，之后常驻内存 |
| 服务起不来 | `sudo journalctl -u smart-wardrobe -n 100` 看报错 |
