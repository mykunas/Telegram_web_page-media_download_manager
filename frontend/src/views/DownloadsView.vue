<template>
  <div class="downloads-page">
    <section class="hero-section card-shell">
      <div class="hero-left">
        <h1 class="hero-title">下载记录</h1>
        <p class="hero-desc">按频道、状态、类型与时间范围筛选下载任务，并支持批量处理</p>
      </div>
      <div class="hero-actions">
        <el-button class="pill-btn" @click="exportRecords">导出记录</el-button>
        <el-button class="pill-btn" @click="refreshList">刷新列表</el-button>
        <el-button class="pill-btn dark" type="primary" :disabled="failedRowIds.length === 0" @click="retryFailedRecords">
          批量重试失败任务
        </el-button>
      </div>
    </section>

    <section class="filter-panel card-shell">
      <el-alert
        v-if="!syncState.serviceRunning && syncState.waitingCount > 0"
        type="warning"
        show-icon
        :closable="false"
        class="sync-alert"
      >
        <template #title>
          当前有 {{ syncState.waitingCount }} 条任务排队，但下载服务未运行。
          <el-button size="small" type="warning" @click="startSyncService" style="margin-left: 8px">
            启动下载服务
          </el-button>
        </template>
      </el-alert>

      <el-form class="filter-grid" label-position="top" @submit.prevent>
        <el-form-item label="频道">
          <el-select v-model="filters.chatId" clearable filterable placeholder="全部频道">
            <el-option v-for="item in channelOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>

        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态">
            <el-option label="等待中" value="waiting" />
            <el-option label="下载中" value="downloading" />
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="已跳过" value="skipped" />
            <el-option label="重复文件" value="duplicate" />
          </el-select>
        </el-form-item>

        <el-form-item label="媒体类型">
          <el-select v-model="filters.mediaType" clearable placeholder="全部类型">
            <el-option label="视频" value="video" />
            <el-option label="图片" value="photo" />
            <el-option label="文档" value="document" />
          </el-select>
        </el-form-item>

        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" clearable placeholder="搜索文件名 / 路径 / 消息ID" @keyup.enter="handleSearch" />
        </el-form-item>

        <el-form-item label="时间范围" class="date-item">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>

        <el-form-item label="操作" class="action-item">
          <div class="filter-actions">
            <el-button class="pill-btn dark" type="primary" @click="handleSearch">查询</el-button>
            <el-button class="pill-btn" @click="handleReset">重置</el-button>
          </div>
        </el-form-item>
      </el-form>

      <div class="filter-hints">
        <el-tag effect="light" round>默认排序：创建时间倒序</el-tag>
        <el-tag effect="light" type="danger" round>失败任务 {{ overviewStats.failed }} 条</el-tag>
        <el-tag effect="light" type="primary" round>下载中 {{ overviewStats.downloading }} 条</el-tag>
        <el-tag v-if="filters.status" effect="light" type="info" round>状态：{{ formatStatusText(filters.status) }}</el-tag>
        <el-tag v-if="filters.mediaType" effect="light" type="info" round>类型：{{ formatMediaType(filters.mediaType) }}</el-tag>
      </div>
    </section>

    <section class="table-section card-shell">
      <div class="table-toolbar">
        <div class="toolbar-title">任务列表</div>
        <div class="toolbar-actions">
          <el-tag class="hint-tag" type="info" round>已选择 {{ selectedRowIds.length }} 项</el-tag>
          <el-button class="pill-btn" size="small" :disabled="!selectedRowIds.length" @click="copySelectedPaths">
            批量复制路径
          </el-button>
          <el-button class="pill-btn" size="small" :disabled="!selectedRowIds.length" @click="reserveBatchAction">
            批量下载
          </el-button>
        </div>
      </div>

      <el-table
        :data="rows"
        v-loading="loading"
        row-key="id"
        class="download-table"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" reserve-selection />

        <el-table-column label="记录" min-width="220">
          <template #default="scope">
            <div class="single-cell">
              <span class="chip id">#{{ scope.row.id }}</span>
              <span class="text-ellipsis strong" :title="scope.row.chat_name || '-'">{{ scope.row.chat_name || '-' }}</span>
              <span class="sub">MID: {{ scope.row.message_id || '-' }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="文件信息" min-width="420">
          <template #default="scope">
            <div class="single-cell">
              <el-tag size="small" effect="plain" type="info">{{ formatMediaType(scope.row.media_type) }}</el-tag>
              <el-tooltip :content="scope.row.original_file_name || '-'" placement="top" :show-after="350">
                <span class="text-ellipsis strong">{{ scope.row.original_file_name || '-' }}</span>
              </el-tooltip>
              <el-tooltip :content="scope.row.saved_path || '-'" placement="top" :show-after="350">
                <span class="text-ellipsis sub path">{{ scope.row.saved_path || '-' }}</span>
              </el-tooltip>
              <span class="sub size">{{ formatBytes(scope.row.file_size) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="来源" width="118" align="center">
          <template #default="scope">
            <el-tag size="small" effect="light">{{ formatSourceType(scope.row.source_type) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="118" align="center">
          <template #default="scope">
            <el-tag :type="statusTagType(scope.row.status)" size="small" effect="light" round>
              {{ formatStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="时间" min-width="250">
          <template #default="scope">
            <div class="single-cell">
              <span class="sub">创建 {{ formatDateTime(scope.row.created_at) }}</span>
              <span class="sub">完成 {{ formatDateTime(scope.row.completed_at) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="320" fixed="right">
          <template #default="scope">
            <div class="op-actions">
              <el-button size="small" class="op-btn" plain @click="showDetail(scope.row.id)">详情</el-button>
              <el-button size="small" class="op-btn" plain @click="copyPath(scope.row.saved_path)">复制路径</el-button>
              <el-button
                size="small"
                class="op-btn op-main"
                type="primary"
                :disabled="scope.row.status === 'downloading'"
                @click="manualDownload(scope.row.id)"
              >
                手动下载
              </el-button>
              <el-button
                size="small"
                class="op-btn op-danger"
                type="danger"
                plain
                :disabled="scope.row.status !== 'failed'"
                @click="retryRecord(scope.row.id)"
              >
                重试
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager-wrap">
        <div class="pager-left">
          显示第
          <strong>{{ pageRange.start }}</strong>
          -
          <strong>{{ pageRange.end }}</strong>
          条，共
          <strong>{{ formatNumber(pagination.total) }}</strong>
          条
        </div>
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          background
          layout="sizes, prev, pager, next, jumper"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          @size-change="handlePageSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </section>

    <el-drawer v-model="detailVisible" title="下载记录详情" size="46%">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="频道名称">{{ detail.chat_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="消息ID">{{ detail.message_id }}</el-descriptions-item>
        <el-descriptions-item label="媒体类型">{{ formatMediaType(detail.media_type) }}</el-descriptions-item>
        <el-descriptions-item label="原始文件名">{{ detail.original_file_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="保存文件名">{{ detail.saved_file_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="保存路径">{{ detail.saved_path || '-' }}</el-descriptions-item>
        <el-descriptions-item label="文件大小">{{ formatBytes(detail.file_size) }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ formatStatusText(detail.status) }}</el-descriptions-item>
        <el-descriptions-item label="来源类型">{{ formatSourceType(detail.source_type) }}</el-descriptions-item>
        <el-descriptions-item label="错误信息">{{ detail.error_message || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ formatDateTime(detail.completed_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import http from '@/api/http'

// 若只想演示 UI 结构，可临时改为 true 使用 mock 数据
const USE_MOCK = false

const loading = ref(false)
const rows = ref([])
const channelOptions = ref([])
const detailVisible = ref(false)
const detail = ref(null)
const selectedRowIds = ref([])
const syncState = reactive({
  serviceRunning: true,
  waitingCount: 0
})

const filters = reactive({
  chatId: undefined,
  status: '',
  mediaType: '',
  keyword: '',
  dateRange: []
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const mockRows = [
  {
    id: 1061,
    chat_id: -100123,
    chat_name: '撸撸视频',
    message_id: 45981,
    media_type: 'video',
    original_file_name: '2026-03-05_12-03-17_小萝莉体验视频.mp4',
    saved_file_name: '2026-03-05_12-03-17_小萝莉体验视频.mp4',
    saved_path: '/downloads/撸撸视频/videos/2026-03/2026-03-05/2026-03-05_12-03-17_小萝莉体验视频.mp4',
    file_size: 1427151332,
    status: 'downloading',
    source_type: 'history',
    error_message: null,
    created_at: '2026-04-14 19:10:05',
    completed_at: null
  },
  {
    id: 1060,
    chat_id: -100123,
    chat_name: '撸撸视频',
    message_id: 45980,
    media_type: 'photo',
    original_file_name: 'cover_2026_04_13.webp',
    saved_file_name: 'cover_2026_04_13.webp',
    saved_path: '/downloads/撸撸视频/photos/2026-04/2026-04-13/cover_2026_04_13.webp',
    file_size: 982313,
    status: 'success',
    source_type: 'live',
    error_message: null,
    created_at: '2026-04-14 18:00:12',
    completed_at: '2026-04-14 18:00:18'
  },
  {
    id: 1059,
    chat_id: -100456,
    chat_name: '频道 A',
    message_id: 90032,
    media_type: 'document',
    original_file_name: 'archive_pack_2026_04.zip',
    saved_file_name: null,
    saved_path: null,
    file_size: 4831021222,
    status: 'failed',
    source_type: 'history',
    error_message: 'Connection lost',
    created_at: '2026-04-14 17:49:40',
    completed_at: '2026-04-14 17:50:01'
  }
]

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}

const failedRowIds = computed(() =>
  rows.value
    .filter((item) => String(item.status || '') === 'failed')
    .map((item) => Number(item.id))
    .filter((id) => Number.isFinite(id) && id > 0)
)

const overviewStats = computed(() => {
  let downloading = 0
  let success = 0
  let failed = 0

  rows.value.forEach((row) => {
    if (row.status === 'downloading') downloading += 1
    if (row.status === 'failed') failed += 1
    if (['success', 'duplicate', 'skipped'].includes(String(row.status || ''))) success += 1
  })

  return { downloading, success, failed }
})

const pageRange = computed(() => {
  if (!pagination.total) return { start: 0, end: 0 }
  const start = (pagination.page - 1) * pagination.pageSize + 1
  const end = Math.min(pagination.page * pagination.pageSize, pagination.total)
  return { start, end }
})

const statusTagType = (status) => {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'downloading') return 'primary'
  if (status === 'waiting') return 'warning'
  if (status === 'duplicate') return 'info'
  if (status === 'skipped') return 'info'
  return 'info'
}

const formatStatusText = (status) => {
  if (status === 'success') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'downloading') return '下载中'
  if (status === 'waiting') return '等待中'
  if (status === 'duplicate') return '重复文件'
  if (status === 'skipped') return '已跳过'
  return status || '-'
}

const formatSourceType = (sourceType) => {
  if (sourceType === 'history') return '历史消息'
  if (sourceType === 'live') return '实时消息'
  return sourceType || '-'
}

const formatMediaType = (mediaType) => {
  if (mediaType === 'video') return '视频'
  if (mediaType === 'photo') return '图片'
  if (mediaType === 'document') return '文档'
  return mediaType || '-'
}

const formatNumber = (value) => Number(value || 0).toLocaleString('zh-CN')

const formatDateTime = (value) => value || '-'

const formatBytes = (bytes) => {
  if (!bytes || Number(bytes) <= 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = Number(bytes)
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`
}

const buildQuery = () => {
  const params = {
    page: pagination.page,
    page_size: pagination.pageSize
  }

  if (filters.chatId !== undefined && filters.chatId !== null && filters.chatId !== '') params.chat_id = filters.chatId
  if (filters.status) params.status = filters.status
  if (filters.mediaType) params.media_type = filters.mediaType
  if (filters.keyword) params.keyword = filters.keyword

  if (filters.dateRange && filters.dateRange.length === 2) {
    params.date_from = filters.dateRange[0]
    params.date_to = filters.dateRange[1]
  }

  return params
}

const loadChannels = async () => {
  try {
    const resp = await http.get('/dashboard/channel-stats')
    const data = parseApiData(resp)
    channelOptions.value = (Array.isArray(data) ? data : []).map((item) => ({
      label: item.chat_name ? `${item.chat_name} (${item.chat_id})` : String(item.chat_id),
      value: item.chat_id
    }))
  } catch {
    channelOptions.value = []
  }
}

const loadDownloads = async () => {
  loading.value = true
  try {
    if (USE_MOCK) {
      rows.value = mockRows
      pagination.total = mockRows.length
      return
    }

    const resp = await http.get('/downloads', { params: buildQuery() })
    const data = parseApiData(resp)

    rows.value = Array.isArray(data.list) ? data.list : []
    pagination.total = Number(data.total || 0)
    pagination.page = Number(data.page || pagination.page)
    pagination.pageSize = Number(data.page_size || pagination.pageSize)
  } catch (error) {
    if (USE_MOCK) {
      rows.value = mockRows
      pagination.total = mockRows.length
    } else {
      ElMessage.error(error?.message || '加载下载记录失败')
    }
  } finally {
    loading.value = false
  }
}

const loadSyncState = async () => {
  try {
    const [syncResp, activeResp] = await Promise.all([
      http.get('/sync/status'),
      http.get('/dashboard/active-downloads')
    ])
    const syncData = parseApiData(syncResp) || {}
    const activeData = parseApiData(activeResp) || {}
    syncState.serviceRunning = Boolean(syncData?.service?.service_running)
    syncState.waitingCount = Number(activeData?.waiting_count || 0)
  } catch {
    syncState.serviceRunning = true
    syncState.waitingCount = 0
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadDownloads()
}

const handleReset = () => {
  filters.chatId = undefined
  filters.status = ''
  filters.mediaType = ''
  filters.keyword = ''
  filters.dateRange = []
  pagination.page = 1
  loadDownloads()
}

const handlePageChange = (page) => {
  pagination.page = page
  loadDownloads()
}

const handlePageSizeChange = (size) => {
  pagination.pageSize = size
  pagination.page = 1
  loadDownloads()
}

const handleSelectionChange = (selection) => {
  selectedRowIds.value = selection
    .map((item) => Number(item.id))
    .filter((id) => Number.isFinite(id) && id > 0)
}

const reserveBatchAction = () => {
  ElMessage.info('批量下载能力已预留，可按已选任务继续扩展')
}

const copySelectedPaths = async () => {
  if (!selectedRowIds.value.length) {
    ElMessage.warning('请先选择记录')
    return
  }
  const pathList = rows.value
    .filter((item) => selectedRowIds.value.includes(Number(item.id)))
    .map((item) => String(item.saved_path || '').trim())
    .filter(Boolean)
  if (!pathList.length) {
    ElMessage.warning('所选记录没有可复制路径')
    return
  }
  try {
    await navigator.clipboard.writeText(pathList.join('\n'))
    ElMessage.success(`已复制 ${pathList.length} 条路径`)
  } catch {
    ElMessage.error('复制失败，请检查浏览器权限')
  }
}

const showDetail = async (id) => {
  try {
    if (USE_MOCK) {
      detail.value = rows.value.find((item) => item.id === id) || null
      detailVisible.value = true
      return
    }
    const resp = await http.get(`/downloads/${id}`)
    detail.value = parseApiData(resp)
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(error?.message || '获取详情失败')
  }
}

const retryRecord = async (id) => {
  try {
    await ElMessageBox.confirm('确认重试该失败记录？', '重试确认', { type: 'warning' })
    if (!USE_MOCK) {
      const resp = await http.post(`/downloads/${id}/retry`)
      parseApiData(resp)
    }
    ElMessage.success('已加入重试队列')
    loadDownloads()
    loadSyncState()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '重试失败')
    }
  }
}

const retryFailedRecords = async () => {
  if (!failedRowIds.value.length) {
    ElMessage.warning('当前列表没有失败任务')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认重试当前列表中的 ${failedRowIds.value.length} 条失败任务？`,
      '批量重试确认',
      { type: 'warning' }
    )

    if (!USE_MOCK) {
      const resp = await http.post('/downloads/batch-retry', { ids: failedRowIds.value })
      const data = parseApiData(resp) || {}
      ElMessage.success(`已加入重试队列：${Number(data.retried_count || 0)} 条`)
    } else {
      ElMessage.success(`已加入重试队列：${failedRowIds.value.length} 条`)
    }

    loadDownloads()
    loadSyncState()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '批量重试失败')
    }
  }
}

const startSyncService = async () => {
  try {
    if (!USE_MOCK) {
      await http.post('/sync/start')
    }
    ElMessage.success('下载服务已启动')
    await Promise.all([loadDownloads(), loadSyncState()])
  } catch (error) {
    ElMessage.error(error?.message || '启动下载服务失败')
  }
}

const manualDownload = async (id) => {
  try {
    await ElMessageBox.confirm('确认手动加入下载队列？', '手动下载确认', { type: 'warning' })
    if (!USE_MOCK) {
      const resp = await http.post(`/downloads/${id}/manual-download`)
      parseApiData(resp)
    }
    ElMessage.success('已加入手动下载队列')
    loadDownloads()
    loadSyncState()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '手动下载失败')
    }
  }
}

const copyPath = async (path) => {
  if (!path) {
    ElMessage.warning('暂无可复制路径')
    return
  }
  try {
    await navigator.clipboard.writeText(path)
    ElMessage.success('路径已复制')
  } catch {
    ElMessage.error('复制失败，请检查浏览器权限')
  }
}

const exportRecords = () => {
  if (!rows.value.length) {
    ElMessage.warning('暂无可导出的记录')
    return
  }

  const headers = ['ID', '频道名称', '消息ID', '媒体类型', '文件名', '保存路径', '文件大小', '状态', '来源', '创建时间', '完成时间']
  const lines = rows.value.map((row) => [
    row.id,
    row.chat_name || '',
    row.message_id || '',
    formatMediaType(row.media_type),
    row.original_file_name || '',
    row.saved_path || '',
    formatBytes(row.file_size),
    formatStatusText(row.status),
    formatSourceType(row.source_type),
    formatDateTime(row.created_at),
    formatDateTime(row.completed_at)
  ])

  const escapeCell = (value) => `"${String(value ?? '').replace(/"/g, '""')}"`
  const csv = [headers.map(escapeCell).join(','), ...lines.map((line) => line.map(escapeCell).join(','))].join('\n')
  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `downloads_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

const refreshList = async () => {
  await Promise.all([loadDownloads(), loadSyncState()])
  ElMessage.success('列表已刷新')
}

onMounted(async () => {
  await Promise.all([loadChannels(), loadDownloads(), loadSyncState()])
})
</script>

<style scoped>
.downloads-page {
  display: grid;
  gap: 14px;
  background: #edf1f6;
  width: 100%;
  min-width: 0;
}

.card-shell {
  background: #fff;
  border-radius: 22px;
  padding: clamp(12px, 2vw, 18px) clamp(12px, 2.2vw, 20px);
  border: 1px solid #dde3ec;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
  width: 100%;
  min-width: 0;
}

.hero-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.hero-title {
  margin: 0;
  font-size: clamp(24px, 3.2vw, 40px);
  font-weight: 700;
  letter-spacing: -0.03em;
  color: #0b1324;
}

.hero-desc {
  margin: 8px 0 0;
  color: #7d8ca4;
  font-size: clamp(13px, 1.3vw, 16px);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.pill-btn {
  border-radius: 999px;
  border-color: #d7deea;
  color: #1b2840;
  font-weight: 600;
}

.pill-btn.dark {
  background: #071228;
  border-color: #071228;
  color: #fff;
}

.filter-panel {
  padding-bottom: 16px;
}

.sync-alert {
  margin-bottom: 12px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px 12px;
}

.filter-grid :deep(.el-form-item) {
  margin-bottom: 4px;
}

.filter-grid :deep(.el-form-item__label) {
  color: #7a8ba6;
  font-weight: 600;
  padding-bottom: 6px;
}

.filter-grid :deep(.el-select),
.filter-grid :deep(.el-input),
.filter-grid :deep(.el-date-editor) {
  width: 100%;
}

.filter-grid :deep(.el-input__wrapper),
.filter-grid :deep(.el-select__wrapper) {
  border-radius: 16px;
  background: #f6f8fc;
}

.date-item {
  grid-column: span 2;
}

.action-item {
  display: flex;
  align-items: flex-end;
}

.filter-actions {
  display: flex;
  gap: 8px;
}

.filter-hints {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.table-section {
  padding-top: 14px;
  min-width: 0;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.toolbar-title {
  font-size: clamp(20px, 2.2vw, 30px);
  font-weight: 700;
  color: #0b1324;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hint-tag {
  border-radius: 999px;
}

.download-table {
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid #e4e9f2;
  width: 100%;
}

.single-cell {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
  white-space: nowrap;
}

.single-cell .strong {
  color: #1a2945;
  font-weight: 600;
}

.sub {
  color: #8092ad;
  font-size: 12px;
}

.chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid #dce4f0;
  background: #f5f8fd;
  color: #21304c;
}

.path {
  color: #94a3b8;
}

.size {
  margin-left: auto;
}

.text-ellipsis {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.op-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
  align-items: center;
}

.op-btn {
  border-radius: 999px;
  border-color: #d5deeb;
  color: #1d2d4a;
  background: linear-gradient(180deg, #fff 0%, #f6f9ff 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.op-main {
  background: linear-gradient(135deg, #06152e 0%, #123a71 100%);
  border-color: #0f3568;
  color: #fff;
}

.op-danger {
  border-color: #f0c7d0;
  color: #b4234a;
}

.pager-wrap {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.pager-left {
  color: #64748b;
  font-size: 13px;
}

.pager-left strong {
  color: #111827;
}

:deep(.el-table .cell) {
  padding-top: 10px;
  padding-bottom: 10px;
}

:deep(.el-table__body-wrapper) {
  overflow-x: auto;
}

:deep(.el-table th.el-table__cell) {
  background: #f3f6fb;
  color: #627490;
  font-weight: 700;
}

:deep(.el-table__row) {
  transition: background-color 0.2s ease;
}

:deep(.el-table__row:hover > td.el-table__cell) {
  background: #f7f9fd !important;
}

:deep(.el-descriptions__label) {
  width: 130px;
}

@media (max-width: 1400px) {
  .date-item {
    grid-column: span 2;
  }
}

@media (max-width: 1100px) {
  .hero-section {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .pager-wrap {
    flex-direction: column;
    align-items: flex-start;
  }

  .date-item {
    grid-column: span 1;
  }
}

@media (max-width: 760px) {
  .date-item {
    grid-column: span 1;
  }

  .hero-title {
    font-size: 24px;
  }
}
</style>
