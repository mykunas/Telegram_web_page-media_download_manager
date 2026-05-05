# Telegram 媒体下载与管理系统

一个基于 **Pyrogram + FastAPI + Vue 3** 的 Telegram 媒体管理项目，提供从频道/群组媒体抓取、下载、管理到可视化监控的一站式能力。

## 项目介绍

本项目由 3 个服务组成：
- `worker`：连接 Telegram，拉取历史消息和实时消息并执行下载
- `backend`：提供 API、状态管理、下载记录、系统日志
- `frontend`：提供 Web 管理面板（仪表盘、下载记录、文件管理、配置）

核心能力：
- 按频道/群组批量下载媒体（视频、图片、文件）
- 失败任务重试、手动入队、批量管理
- 文件列表与缩略图展示（支持视频封面）
- 下载速率、任务趋势、系统状态可视化
- 支持 Docker Compose 一键部署，适合 NAS / 服务器长期运行

## 项目结构

```text
.
├─ app/                   # 下载器与同步逻辑（worker）
├─ backend/               # FastAPI 服务
├─ frontend/              # Vue3 前端
├─ session/               # Telegram 会话文件目录
├─ docker-compose.yml     # Docker 编排文件
└─ .env                   # 全局运行配置
```

## Docker 部署教程

### 1. 部署前准备

请先确认环境：
- 已安装 Docker（建议 24+）
- 已安装 Docker Compose（`docker compose` 可用）
- 可访问 Telegram 网络
- 已准备 Telegram `API_ID` 与 `API_HASH`

### 2. 准备目录与配置文件

在项目根目录创建/修改 `.env`（不要提交真实凭据到公开仓库）：

```env
# Telegram 基础配置
API_ID=12345678
API_HASH=your_api_hash
PHONE_NUMBER=+8613800000000
SESSION_NAME=/app/session/telegram_user

# 下载配置
DOWNLOAD_DIR=/downloads
TARGET_CHATS=@channel_a,@channel_b
ALLOW_EXTS=.mp4,.mkv,.mov,.avi,.jpg,.jpeg,.png,.webp
DOWNLOAD_HISTORY=true
HISTORY_LIMIT=2000
MAX_RETRIES=3
RETRY_DELAY=5
MAX_FILE_SIZE_MB=0

# 端口映射（宿主机端口）
BACKEND_PORT=18000
FRONTEND_PORT=13000

# 下载目录挂载（宿主机绝对路径）
# Windows 示例: D:/tg_downloads
# Linux/NAS 示例: /volume1/tg_downloads
DOWNLOADS_VOLUME=/your/download/path
```

说明：
- `DOWNLOADS_VOLUME` 会挂载到容器内统一路径 `/downloads`
- `backend` 与 `worker` 必须挂载到同一个实际目录，否则会出现“已下载但面板看不到”的问题

### 3. 启动服务

在项目根目录执行：

```bash
docker compose up -d --build
```

查看运行状态：

```bash
docker compose ps
```

### 4. 首次 Telegram 授权

启动后打开前端：
- `http://<服务器IP>:13000`

然后在“系统配置/Telegram 配置”中完成：
1. 保存 `API_ID / API_HASH / PHONE_NUMBER / SESSION_NAME`
2. 点击开始授权（发送验证码）
3. 输入验证码
4. 如账号开启 2FA，再输入二步验证密码

授权成功后，会话文件会写入 `session/` 目录，`worker` 即可持续拉取与下载。

### 5. 访问地址与健康检查

- 前端：`http://<服务器IP>:13000`
- 后端健康检查：`http://<服务器IP>:18000/health`

### 6. 常用运维命令

```bash
# 查看全部日志
docker compose logs -f

# 查看 worker 日志
docker compose logs -f worker

# 重启某个服务
docker compose restart worker

# 停止服务
docker compose down

# 重新构建并启动
docker compose up -d --build
```

### 7. 常见问题

1. 前端能打开但没有下载任务
- 检查 Telegram 是否已授权成功
- 检查 `TARGET_CHATS` 是否正确（多个用英文逗号分隔）

2. 文件已经下载但页面看不到
- 检查 `DOWNLOADS_VOLUME` 是否有效
- 检查 `backend` 与 `worker` 的 `/downloads` 是否挂载到同一宿主机目录

3. 下载速度为 0 或任务长时间卡住
- 先看 `worker` 日志定位是否网络抖动/限速
- 检查目标频道是否仍可访问、是否存在权限变更

## 安全建议

- 不要在公开仓库提交 `.env`
- 不要提交 `session/*.session`
- 建议在 `.gitignore` 中忽略敏感文件与运行时数据
