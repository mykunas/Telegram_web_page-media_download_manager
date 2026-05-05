# Telegram 媒体下载与管理系统

基于 **Pyrogram + FastAPI + Vue 3 + Docker Compose** 的 Telegram 媒体下载和管理项目。它可以连接指定频道或群组，批量下载视频、图片和文件，并通过网页后台查看下载进度、文件列表、日志、收藏和推荐内容。

适合部署在 NAS、Linux 服务器、Windows Docker Desktop 或长期运行的小主机上。

## 功能概览

- 自动连接 Telegram 账号，监听频道/群组新消息
- 支持拉取历史消息并批量下载媒体
- 按扩展名过滤下载内容
- 下载失败自动重试，可在后台查看失败原因
- 下载记录写入 SQLite 数据库，前端可分页、筛选、搜索
- 视频支持缩略图和在线播放预览
- 支持收藏夹、随机推荐、多窗口播放等个人媒体管理功能
- 前端提供仪表盘、下载记录、文件管理、日志、配置和同步状态页面
- 使用 Docker Compose 一键启动 `backend`、`frontend`、`worker`

## 服务说明

本项目启动后有 3 个容器：

| 服务 | 容器名 | 作用 |
| --- | --- | --- |
| `backend` | `tg-media-backend` | FastAPI 后端，提供接口、数据库、日志和文件访问能力 |
| `frontend` | `tg-media-frontend` | Vue 3 前端，提供网页管理后台 |
| `worker` | `tg-media-worker` | Telegram 下载器，负责登录、监听、拉历史消息和下载文件 |

`backend` 和 `worker` 必须挂载同一个下载目录。否则会出现“文件已经下载，但页面看不到”的情况。

## 目录结构

```text
.
├─ app/                   # worker 下载器代码
│  ├─ downloader.py       # worker 入口
│  ├─ runtime_config.py   # 运行配置读取
│  ├─ telegram_service.py # Telegram 登录、监听、历史消息拉取
│  └─ download_service.py # 下载队列、重试、写入记录
├─ backend/               # FastAPI 后端
│  ├─ Dockerfile
│  ├─ requirements.txt
│  └─ app/
├─ frontend/              # Vue 3 前端
│  ├─ Dockerfile
│  ├─ nginx.conf
│  └─ src/
├─ session/               # Telegram session 文件目录
├─ data/                  # SQLite 数据库和后端数据，运行后生成
├─ logs/                  # backend/frontend/worker 日志，运行后生成
├─ downloads/             # 默认下载目录，未设置 DOWNLOADS_VOLUME 时使用
├─ docker-compose.yml     # Docker 编排配置
└─ .env                   # 全局运行配置
```

## 部署前准备

请先确认：

- 已安装 Docker
- 已安装 Docker Compose，命令为 `docker compose`
- 服务器可以访问 Telegram
- 已申请 Telegram `API_ID` 和 `API_HASH`
- 项目完整目录中必须包含 `backend/`、`frontend/`、`app/`、`docker-compose.yml`

如果你是从 `deploy_ai_tg.tar.gz` 部署，可以在目标目录执行：

```bash
tar -xzf deploy_ai_tg.tar.gz
```

如果之前遇到 `backend/.env not found` 或 `context ./backend not found`，说明 `backend/` 目录没有完整解压。

## 配置 `.env`

项目主要配置都在根目录 `.env`：

```bash
/home/AIDE/telegram/.env
```

示例配置：

```env
# Telegram 基础配置
API_ID=12345678
API_HASH=your_api_hash
PHONE_NUMBER=+8613800000000
SESSION_NAME=/app/session/feiniu_user

# 容器内下载目录，通常不要改
DOWNLOAD_DIR=/downloads

# 多个频道或群组用英文逗号分隔
TARGET_CHATS=@channel_a,@channel_b

# 只下载这些扩展名
ALLOW_EXTS=.mp4,.mkv,.mov,.avi,.jpg,.jpeg,.png,.webp

# 是否拉取历史消息
DOWNLOAD_HISTORY=true
HISTORY_LIMIT=2000

# 重试和大小限制
MAX_RETRIES=3
RETRY_DELAY=5
MAX_FILE_SIZE_MB=0

# 宿主机端口
BACKEND_PORT=18000
FRONTEND_PORT=13000

# 宿主机实际下载目录
DOWNLOADS_VOLUME=/home/AIDE/telegram_downloads
```

配置项说明：

| 配置项 | 必填 | 说明 |
| --- | --- | --- |
| `API_ID` | 是 | Telegram API ID |
| `API_HASH` | 是 | Telegram API Hash |
| `PHONE_NUMBER` | 是 | Telegram 登录手机号，建议带国家码，例如 `+86...` |
| `SESSION_NAME` | 是 | Telegram session 路径，Docker 部署建议使用 `/app/session/feiniu_user` |
| `DOWNLOAD_DIR` | 是 | 容器内部下载目录，保持 `/downloads` 即可 |
| `TARGET_CHATS` | 是 | 要下载的频道、群组或用户名，多个用英文逗号分隔 |
| `ALLOW_EXTS` | 否 | 允许下载的文件扩展名 |
| `DOWNLOAD_HISTORY` | 否 | 是否启动时拉取历史消息 |
| `HISTORY_LIMIT` | 否 | 每个频道最多拉取多少条历史消息 |
| `MAX_RETRIES` | 否 | 下载失败后的最大重试次数 |
| `RETRY_DELAY` | 否 | 重试间隔，单位秒 |
| `MAX_FILE_SIZE_MB` | 否 | 最大文件大小，`0` 表示不限制 |
| `BACKEND_PORT` | 否 | 后端映射到宿主机的端口 |
| `FRONTEND_PORT` | 否 | 前端映射到宿主机的端口 |
| `DOWNLOADS_VOLUME` | 否 | 宿主机真实下载目录，不配置时默认使用项目下的 `./downloads` |

注意：同一个 `.env` 里不要重复写同一个配置项。如果重复，Docker 通常会以后面的值为准，容易造成误判。

## 修改下载位置

下载位置只需要改 `.env` 里的：

```env
DOWNLOADS_VOLUME=/你的新下载目录
```

Linux 或 NAS 示例：

```env
DOWNLOADS_VOLUME=/volume1/telegram_downloads
```

当前服务器示例：

```env
DOWNLOADS_VOLUME=/home/AIDE/telegram_downloads
```

Windows Docker Desktop 示例：

```env
DOWNLOADS_VOLUME=D:/telegram_downloads
```

然后创建目录并重启：

```bash
mkdir -p /home/AIDE/telegram_downloads
cd /home/AIDE/telegram
docker compose down
docker compose up -d
```

不要把 `DOWNLOAD_DIR=/downloads` 改成宿主机路径。`DOWNLOAD_DIR` 是容器内路径，`DOWNLOADS_VOLUME` 才是宿主机真实路径。

## 启动项目

进入项目目录：

```bash
cd /home/AIDE/telegram
```

首次启动或代码有变化时：

```bash
docker compose up -d --build
```

普通重启：

```bash
docker compose up -d
```

查看容器状态：

```bash
docker compose ps
```

正常情况下应看到：

- `tg-media-backend`
- `tg-media-frontend`
- `tg-media-worker`

## 访问地址

假设服务器 IP 是 `192.168.3.11`，并且 `.env` 使用：

```env
BACKEND_PORT=18000
FRONTEND_PORT=13000
```

访问：

```text
前端后台：http://192.168.3.11:13000
后端健康检查：http://192.168.3.11:18000/health
```

健康检查正常时会返回成功状态和 `status=ok`。

## 首次 Telegram 授权

首次部署后需要完成 Telegram 登录授权：

1. 打开前端后台。
2. 进入系统配置或 Telegram 配置页面。
3. 填写并保存 `API_ID`、`API_HASH`、`PHONE_NUMBER`、`SESSION_NAME`。
4. 点击开始授权，等待 Telegram 发送验证码。
5. 输入验证码。
6. 如果账号开启了两步验证，再输入 2FA 密码。
7. 授权成功后，session 文件会保存到 `session/` 目录。

授权成功后，`worker` 才能持续监听和下载。

## 日志查看

查看全部服务日志：

```bash
docker compose logs -f
```

查看下载器日志：

```bash
docker compose logs -f worker
```

查看后端日志：

```bash
docker compose logs -f backend
```

查看前端 Nginx 日志：

```bash
docker compose logs -f frontend
```

项目也会把日志挂载到：

```text
logs/backend/
logs/worker/
logs/frontend/
```

## 常用维护命令

重启下载器：

```bash
docker compose restart worker
```

重启后端：

```bash
docker compose restart backend
```

停止全部服务：

```bash
docker compose down
```

重新构建并启动：

```bash
docker compose up -d --build
```

查看端口占用：

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
sudo ss -lntp | grep ':18000'
```

检查下载目录挂载：

```bash
docker inspect tg-media-backend --format '{{json .Mounts}}'
docker inspect tg-media-worker --format '{{json .Mounts}}'
```

## 升级或迁移

升级前建议备份：

```text
.env
session/
data/
logs/
```

如果下载目录不在项目内，还要备份或确认：

```text
DOWNLOADS_VOLUME 指向的目录
```

迁移到新机器时，至少需要带走：

- `.env`
- `session/`
- `data/`
- 下载目录

迁移后执行：

```bash
docker compose up -d --build
```

## 常见问题

### 1. `env file backend/.env not found`

原因：旧的 `docker-compose.yml` 可能引用了 `./backend/.env`，或者部署包没有完整解压。

处理：

```bash
cd /home/AIDE/telegram
tar -xzf deploy_ai_tg.tar.gz ./backend
```

当前 compose 只依赖根目录 `.env`，正常不需要 `backend/.env`。

### 2. `Bind for 0.0.0.0:8000 failed: port is already allocated`

原因：宿主机 `8000` 端口已被占用。

处理：在 `.env` 中设置一个空闲端口：

```env
BACKEND_PORT=18000
```

然后重启：

```bash
docker compose down
docker compose up -d
```

### 3. 前端能打开，但没有下载任务

检查：

- Telegram 是否授权成功
- `TARGET_CHATS` 是否正确
- 目标频道/群组账号是否有访问权限
- `worker` 日志是否有登录、限流或权限错误

命令：

```bash
docker compose logs -f worker
```

### 4. 文件已经下载，但页面看不到

通常是 `backend` 和 `worker` 看到的下载目录不是同一个。

检查：

```bash
docker inspect tg-media-backend --format '{{json .Mounts}}'
docker inspect tg-media-worker --format '{{json .Mounts}}'
```

确认两个容器都把同一个宿主机目录挂载到了 `/downloads`。

### 5. 下载速度为 0 或长时间卡住

可能原因：

- Telegram 限速
- 服务器网络无法稳定访问 Telegram
- 频道权限变更
- 文件过大或磁盘空间不足

建议先看：

```bash
docker compose logs -f worker
df -h
```

### 6. 修改 `.env` 后没有生效

修改 `.env` 后需要重启容器：

```bash
docker compose down
docker compose up -d
```

如果改的是前端构建相关配置，建议重新构建：

```bash
docker compose up -d --build
```

## 安全建议

- 不要把真实 `.env` 上传到公开仓库
- 不要公开 `API_ID`、`API_HASH`、手机号和 session 文件
- 不要公开 `session/*.session`
- 给下载目录预留足够磁盘空间
- 如果部署在公网服务器，建议通过反向代理、登录鉴权或防火墙限制访问

## 快速命令汇总

```bash
cd /home/AIDE/telegram

# 启动
docker compose up -d --build

# 查看状态
docker compose ps

# 查看 worker 日志
docker compose logs -f worker

# 修改配置后重启
docker compose down
docker compose up -d

# 停止
docker compose down
```
