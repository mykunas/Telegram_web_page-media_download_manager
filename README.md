# Telegram 媒体下载与管理面板

一个基于 **Pyrogram + FastAPI + Vue3** 的 Telegram 媒体下载系统，支持：

- 自动拉取频道/群组媒体（视频、图片、文件）
- 下载记录管理、失败重试、手动重排队
- 文件管理（列表/卡片视图、分页、缩略图）
- 仪表盘（下载进度、任务速率、系统监控）
- NAS + Docker 部署

---

## 1. 项目结构

```text
.
├─ app/                      # 下载器 Worker 逻辑（Pyrogram）
├─ backend/                  # FastAPI 后端
├─ frontend/                 # Vue3 + Element Plus 前端
├─ docker-compose.yml        # 一键编排 backend / frontend / worker
├─ .env                      # 运行配置（Telegram / 下载目录 / 端口）
└─ session/                  # Telegram 会话文件
```

---

## 2. 技术栈

- Worker: Python + Pyrogram
- API: FastAPI + SQLAlchemy + SQLite
- Frontend: Vue 3 + Vite + Element Plus + ECharts
- Deploy: Docker Compose

---

## 3. 快速启动（Docker）

### 3.1 准备 `.env`

在项目根目录创建或修改 `.env`：

```env
API_ID=你的API_ID
API_HASH=你的API_HASH
PHONE_NUMBER=+8613xxxxxxxxx
SESSION_NAME=/session/telegram_user
DOWNLOAD_DIR=/downloads
TARGET_CHATS=@channel1,@channel2
ALLOW_EXTS=.mp4,.mkv,.mov,.avi,.jpg,.jpeg,.png,.webp
DOWNLOAD_HISTORY=true
HISTORY_LIMIT=2000
MAX_RETRIES=3
RETRY_DELAY=5
MAX_FILE_SIZE_MB=0

# 建议显式指定
BACKEND_PORT=18000
FRONTEND_PORT=13000
DOWNLOADS_VOLUME=/你的真实下载目录
```

### 3.2 启动

```bash
docker compose up -d --build
```

### 3.3 访问

- 前端：`http://<你的IP>:13000`
- 后端健康检查：`http://<你的IP>:18000/health`

---

## 4. NAS 部署建议（重点）

确保三件事一致：

1. `.env` 中 `DOWNLOAD_DIR=/downloads`
2. `.env` 中 `DOWNLOADS_VOLUME=NAS真实目录`
3. `docker-compose.yml` 中 backend 与 worker 都挂载 `${DOWNLOADS_VOLUME}:/downloads`

如果 backend 和 worker 的 `/downloads` 挂载到不同目录，会出现：

- 文件实际在下载，但仪表盘速度=0
- 进度条不更新
- 文件管理“看不到文件”

---

## 5. 常用功能说明

### 5.1 文件管理同步已下载文件

调用接口将 `/downloads` 下已有文件回填到数据库：

```http
POST /api/downloads/reconcile-files
```

常用参数：

- `root`: 自定义扫描根目录（默认 `/downloads`）
- `update_existing`: 是否更新已有记录
- `with_hash`: 是否计算 sha256（更慢）

### 5.2 视频封面

后端按固定秒数生成缩略图（默认第 3 秒）：

```http
GET /api/downloads/{record_id}/thumbnail
```

说明：

- 缩略图在 NAS 端生成与缓存
- 不会整段下载到浏览器再截帧

### 5.3 下载任务管理

- 列表：`GET /api/downloads`
- 单条重试：`POST /api/downloads/{id}/retry`
- 手动入队：`POST /api/downloads/{id}/manual-download`
- 批量重试失败：`POST /api/downloads/batch-retry`

---

## 6. 仪表盘接口

- 汇总：`GET /api/dashboard/summary`
- 趋势：`GET /api/dashboard/trend`
- 频道统计：`GET /api/dashboard/channel-stats`
- 系统监控：`GET /api/dashboard/system-stats`
- 当前下载详情：`GET /api/dashboard/active-downloads`

`active-downloads` 返回当前下载任务、总下载速率、活动任务总进度等字段，用于前端实时进度条和速率卡片。

---

## 7. 常见问题排查

### 7.1 “文件不下载 / 长时间不动”

先看 worker 日志：

```bash
docker logs -f tg-media-worker
```

常见原因：

- Telegram 网络抖动（`Connection lost`）
- 被限速（日志出现 `Waiting for 3 seconds`）
- 历史队列很大，任务在排队

### 7.2 “仪表盘速率不准 / 进度条不动”

优先检查 backend 与 worker 的 `/downloads` 挂载是否一致：

```bash
docker inspect tg-media-backend
docker inspect tg-media-worker
```

### 7.3 “文件管理没内容”

- 先执行 `reconcile-files`
- 确认数据库与下载目录挂载正确

---

## 8. 开发启动（可选）

### 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

### Worker

```bash
python app/downloader.py
```

---

## 9. 安全建议

- 不要把真实 `.env`（API_ID/API_HASH/手机号）提交到公开仓库。
- 不要把 `session/*.session` 提交到仓库。
- 建议新增 `.gitignore` 保护敏感文件。

---

## 10. 当前默认端口（本项目）

- `BACKEND_PORT=18000`
- `FRONTEND_PORT=13000`

如有端口冲突，修改 `.env` 后执行：

```bash
docker compose up -d --build
```
