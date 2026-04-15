<template>
  <div class="files-page">
    <el-card class="section-card header-card" shadow="never">
      <div class="header-main">
        <div>
          <h1 class="page-title">文件管理</h1>
          <p class="page-desc">展示下载目录中的媒体文件，支持搜索、筛选、预览与收藏管理。</p>
        </div>
        <div class="header-actions">
          <el-button round @click="showBatchDeleteTip">批量删除</el-button>
          <el-button round type="success" :loading="syncing" @click="syncFromDisk">同步目录</el-button>
          <el-button round type="primary" @click="exportCurrentPage">导出文件清单</el-button>
        </div>
      </div>
    </el-card>

    <div class="stats-grid">
      <el-card v-for="item in summaryStats" :key="item.label" class="section-card stat-card" shadow="never">
        <div class="stat-label">{{ item.label }}</div>
        <div class="stat-value">{{ item.value }}</div>
        <div class="stat-sub">{{ item.sub }}</div>
      </el-card>
    </div>

    <el-card class="section-card filter-card" shadow="never">
      <el-form class="filter-form" label-position="top" @submit.prevent>
        <el-form-item label="关键词">
          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="搜索文件名 / 路径 / 频道"
            @keyup.enter="onSearch"
          />
        </el-form-item>

        <el-form-item label="频道">
          <el-input v-model="filters.chatName" clearable placeholder="全部频道" />
        </el-form-item>

        <el-form-item label="媒体类型">
          <el-select v-model="filters.mediaType" clearable placeholder="全部类型">
            <el-option label="视频" value="video" />
            <el-option label="图片" value="photo" />
            <el-option label="文件" value="document" />
          </el-select>
        </el-form-item>

        <el-form-item label="排序">
          <el-select :model-value="'最近更新'" disabled>
            <el-option label="最近更新" value="recent" />
          </el-select>
        </el-form-item>

        <el-form-item label="视图">
          <el-radio-group v-model="viewMode" class="mode-switch">
            <el-radio-button label="gallery">网格</el-radio-button>
            <el-radio-button label="list">列表</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item class="filter-buttons">
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="primary" :loading="loading" @click="onSearch">查询</el-button>
        </el-form-item>
      </el-form>

      <div class="filter-tags">
        <span class="filter-chip">当前排序：最近更新</span>
        <span v-if="filters.mediaType === 'video'" class="filter-chip filter-chip-cyan">仅显示视频</span>
        <span v-if="collectionCount > 0" class="filter-chip filter-chip-orange">收藏夹 {{ collectionCount }} 个</span>
      </div>
    </el-card>

    <el-card class="section-card media-card" shadow="never">
      <div class="media-header">
        <div>
          <div class="media-title">媒体库</div>
          <div class="media-desc">保持媒体卡片 9:16 比例，自动根据屏幕宽度调整展示列数。</div>
        </div>
        <div class="media-actions">
          <el-button round :loading="randomLoading" @click="pickRandom">随机来一个</el-button>
          <el-button round @click="showBatchCollectTip">批量收藏</el-button>
          <el-button round type="primary" @click="showBatchDownloadTip">批量下载</el-button>
        </div>
      </div>

      <el-alert
        v-if="lastSyncSummary"
        class="sync-alert"
        type="info"
        show-icon
        :closable="false"
        :title="lastSyncSummary"
      />

      <el-empty v-if="!loading && !rows.length" description="暂无文件数据" />

      <template v-else>
        <el-table
          v-if="viewMode === 'list'"
          :data="rows"
          border
          stripe
          v-loading="loading"
          @selection-change="onTableSelectionChange"
        >
          <el-table-column type="selection" width="44" />
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="fileName" label="文件名" min-width="260" show-overflow-tooltip />
          <el-table-column prop="mediaTypeText" label="类型" width="110" />
          <el-table-column prop="channel" label="频道" min-width="150" show-overflow-tooltip />
          <el-table-column prop="fileSize" label="大小" width="120">
            <template #default="scope">{{ formatBytes(scope.row.fileSize) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120" />
          <el-table-column prop="createdAt" label="记录时间" width="180" />
          <el-table-column prop="savedPath" label="保存路径" min-width="280" show-overflow-tooltip />
          <el-table-column label="操作" width="250" fixed="right">
            <template #default="scope">
              <el-button link type="primary" @click="previewFile(scope.row)">预览</el-button>
              <el-button link @click="downloadFile(scope.row)">下载</el-button>
              <el-button link type="warning" @click="openAddToCollection(scope.row)">加入收藏</el-button>
              <el-button link @click="copyPath(scope.row.savedPath)">复制路径</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-else class="gallery-grid">
          <article v-for="item in rows" :key="item.id" class="gallery-card" @click="previewFile(item)">
            <img v-if="isImage(item)" :src="item.previewUrl" :alt="item.fileName" class="gallery-media" />
            <img
              v-else-if="item.mediaType === 'video' && !thumbnailFailed[item.id]"
              :src="item.thumbnailUrl"
              :alt="item.fileName"
              class="gallery-media"
              @error="markThumbnailFailed(item.id)"
            />
            <div v-else class="gallery-fallback">
              <el-icon size="36">
                <VideoPlay v-if="item.mediaType === 'video'" />
                <Document v-else />
              </el-icon>
            </div>
            <div class="gallery-overlay">
              <div class="gallery-name">{{ item.fileName }}</div>
              <div class="gallery-actions" @click.stop>
                <el-button link type="primary" @click="previewFile(item)">预览</el-button>
                <el-button link @click="downloadFile(item)">下载</el-button>
                <el-button link type="warning" @click="openAddToCollection(item)">加入收藏</el-button>
              </div>
            </div>
          </article>
        </div>
      </template>

      <div class="pager-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="fetchFiles"
          @size-change="onPageSizeChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="previewVisible"
      title="文件预览"
      width="86vw"
      top="4vh"
      align-center
      class="preview-dialog"
      destroy-on-close
      @closed="onPreviewClosed"
    >
      <template v-if="previewItem">
        <div class="preview-title">{{ previewItem.fileName }}</div>
        <div v-if="previewItem.mediaType === 'video'" class="preview-progress-bar">
          <span>{{ progressText }}</span>
          <el-button size="small" @click="restartFromBeginning">从头播放</el-button>
        </div>
        <div class="preview-stage">
          <img
            v-if="previewItem.mediaType === 'photo'"
            :src="previewItem.previewUrl"
            alt="预览"
            class="preview-media"
          />
          <video
            v-else-if="previewItem.mediaType === 'video'"
            :key="previewItem.id"
            ref="previewVideoRef"
            :src="previewItem.previewUrl"
            controls
            :autoplay="previewAutoplay"
            :muted="previewAutoplay"
            preload="metadata"
            playsinline
            class="preview-media preview-video"
            @loadedmetadata="onPreviewVideoLoadedMeta"
            @timeupdate="onPreviewVideoTimeUpdate"
            @ended="onPreviewVideoEnded"
          />
          <div v-else class="preview-placeholder">
            <p style="margin-top: 12px">{{ previewItem.fileName }}</p>
            <el-button type="primary" @click="downloadFile(previewItem)">下载文件</el-button>
          </div>
        </div>
        <div v-if="rows.length > 1 && !previewFromRandom" class="preview-nav">
          <el-button @click="previewPrev">上一个</el-button>
          <span>{{ previewIndex + 1 }} / {{ rows.length }}</span>
          <el-button @click="previewNext">下一个</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="collectionDialogVisible" title="加入收藏" width="520px" destroy-on-close>
      <template v-if="collectionTarget">
        <div class="collection-tip">文件：{{ collectionTarget.fileName }}</div>
        <el-form label-width="90px">
          <el-form-item label="选择收藏">
            <el-select v-model="selectedCollectionId" placeholder="请选择收藏" style="width: 100%">
              <el-option v-for="item in collections" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="快速新建">
            <div class="collection-create-row">
              <el-input
                v-model="newCollectionName"
                placeholder="输入新收藏名称后点击新建"
                @keyup.enter="createCollectionQuick"
              />
              <el-button :loading="creatingCollection" @click="createCollectionQuick">新建</el-button>
            </div>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="collectionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addingCollectionItem" @click="confirmAddToCollection">加入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { Document, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'

import http from '@/api/http'

const loading = ref(false)
const syncing = ref(false)
const randomLoading = ref(false)
const previewVisible = ref(false)
const previewItem = ref(null)
const previewIndex = ref(-1)
const previewFromRandom = ref(false)
const previewAutoplay = ref(false)
const rows = ref([])
const lastSyncSummary = ref('')
const viewMode = ref('gallery')
const thumbnailFailed = ref({})
const selectedRowIds = ref([])
const collections = ref([])
const collectionDialogVisible = ref(false)
const collectionTarget = ref(null)
const selectedCollectionId = ref(null)
const newCollectionName = ref('')
const creatingCollection = ref(false)
const addingCollectionItem = ref(false)
const previewVideoRef = ref(null)
const playProgress = reactive({
  lastPositionSec: 0,
  durationSec: 0,
  isCompleted: false
})
const lastProgressUploadAt = ref(0)
const lastUploadedPosition = ref(0)

const filters = reactive({
  chatName: '',
  mediaType: '',
  keyword: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}

const apiErrorMessage = (error, fallback) => error?.response?.data?.message || error?.message || fallback

const normalizeStatus = (status) => String(status || '').toLowerCase()

const collectionCount = computed(() => collections.value.length)
const pageTotalSize = computed(() => rows.value.reduce((sum, item) => sum + Number(item.fileSize || 0), 0))
const summaryStats = computed(() => {
  const videos = rows.value.filter((item) => item.mediaType === 'video').length
  const photos = rows.value.filter((item) => item.mediaType === 'photo').length
  return [
    { label: '文件总数', value: pagination.total.toLocaleString(), sub: '当前筛选结果' },
    { label: '视频', value: videos.toLocaleString(), sub: '当前页统计' },
    { label: '图片', value: photos.toLocaleString(), sub: '当前页统计' },
    { label: '收藏', value: collectionCount.value.toLocaleString(), sub: '已创建收藏夹' },
    { label: '占用空间', value: formatBytes(pageTotalSize.value), sub: '当前页累计体积' }
  ]
})

const mediaTypeText = (type) => {
  if (type === 'video') return '视频'
  if (type === 'photo') return '图片'
  if (type === 'document') return '文件'
  return '-'
}

const toUiItem = (row) => ({
  id: row.id,
  mediaType: row.media_type || '',
  mediaTypeText: mediaTypeText(row.media_type),
  fileName: row.saved_file_name || row.original_file_name || `record_${row.id}`,
  fileSize: Number(row.file_size || 0),
  channel: row.chat_name || String(row.chat_id || ''),
  createdAt: row.created_at ? String(row.created_at).slice(0, 19).replace('T', ' ') : '-',
  savedPath: row.saved_path || '',
  status: normalizeStatus(row.status),
  previewUrl: `/api/downloads/${row.id}/file?mode=inline`,
  downloadUrl: `/api/downloads/${row.id}/file?mode=download`,
  thumbnailUrl: `/api/downloads/${row.id}/thumbnail`
})

const buildParams = () => {
  const params = {
    page: pagination.page,
    page_size: pagination.pageSize,
    status: 'success'
  }

  if (filters.chatName?.trim()) params.chat_name = filters.chatName.trim()
  if (filters.mediaType) params.media_type = filters.mediaType
  if (filters.keyword?.trim()) params.keyword = filters.keyword.trim()

  return params
}

const fetchFiles = async () => {
  loading.value = true
  try {
    const data = parseApiData(await http.get('/downloads', { params: buildParams() }))
    const list = Array.isArray(data?.list) ? data.list : []
    rows.value = list.map(toUiItem)
    thumbnailFailed.value = {}
    pagination.total = Number(data?.total || 0)
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加载文件失败'))
  } finally {
    loading.value = false
  }
}

const onSearch = async () => {
  pagination.page = 1
  selectedRowIds.value = []
  await fetchFiles()
}

const onPageSizeChange = async () => {
  pagination.page = 1
  selectedRowIds.value = []
  await fetchFiles()
}

const resetFilters = async () => {
  filters.chatName = ''
  filters.mediaType = ''
  filters.keyword = ''
  pagination.page = 1
  selectedRowIds.value = []
  await fetchFiles()
}

const syncFromDisk = async () => {
  syncing.value = true
  try {
    const data = parseApiData(
      await http.post('/downloads/reconcile-files', null, {
        params: {
          update_existing: true,
          with_hash: false
        }
      })
    )

    lastSyncSummary.value = `同步完成：扫描 ${data.scanned_files}，匹配 ${data.matched_files}，新增 ${data.inserted}，更新 ${data.updated}，跳过 ${data.skipped_existing}，错误 ${data.errors}`
    ElMessage.success('下载目录同步完成')
    pagination.page = 1
    selectedRowIds.value = []
    await fetchFiles()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '同步下载目录失败'))
  } finally {
    syncing.value = false
  }
}

const fetchCollections = async () => {
  try {
    const data = parseApiData(await http.get('/personal/collections')) || {}
    collections.value = Array.isArray(data.list) ? data.list : []
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加载收藏失败'))
  }
}

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

const isImage = (item) => item.mediaType === 'photo'

const markThumbnailFailed = (id) => {
  thumbnailFailed.value[id] = true
}

const onTableSelectionChange = (selection) => {
  selectedRowIds.value = selection.map((item) => item.id)
}

const showBatchDeleteTip = () => {
  if (!selectedRowIds.value.length) {
    ElMessage.info('请先在列表模式勾选需要处理的文件')
    return
  }
  ElMessage.warning('批量删除接口未接入，已为你保留入口')
}

const showBatchCollectTip = () => {
  ElMessage.info('批量收藏入口已预留，可按需接入批量加入收藏接口')
}

const showBatchDownloadTip = () => {
  if (!rows.value.length) {
    ElMessage.info('当前页暂无可下载文件')
    return
  }
  ElMessage.info('批量下载入口已预留，可按需接入下载队列接口')
}

const exportCurrentPage = () => {
  if (!rows.value.length) {
    ElMessage.warning('当前页没有可导出的文件')
    return
  }
  const headers = ['ID', '文件名', '媒体类型', '频道', '大小', '状态', '记录时间', '保存路径']
  const lines = rows.value.map((item) =>
    [
      item.id,
      item.fileName,
      item.mediaTypeText,
      item.channel,
      formatBytes(item.fileSize),
      item.status,
      item.createdAt,
      item.savedPath
    ]
      .map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`)
      .join(',')
  )
  const csv = [headers.join(','), ...lines].join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `files_page_${pagination.page}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success('文件清单已导出')
}

const formatTime = (sec) => {
  const total = Math.max(0, Math.floor(Number(sec || 0)))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const progressText = computed(() => {
  if (!previewItem.value || previewItem.value.mediaType !== 'video') return ''
  if (playProgress.isCompleted) return '已看完'
  if (playProgress.lastPositionSec > 0) return `上次看到 ${formatTime(playProgress.lastPositionSec)}`
  return '未开始播放'
})

const loadPlayProgress = async (recordId) => {
  playProgress.lastPositionSec = 0
  playProgress.durationSec = 0
  playProgress.isCompleted = false
  lastProgressUploadAt.value = 0
  lastUploadedPosition.value = 0
  try {
    const data = parseApiData(await http.get(`/personal/progress/${recordId}`)) || {}
    playProgress.lastPositionSec = Number(data.last_position_sec || 0)
    playProgress.durationSec = Number(data.duration_sec || 0)
    playProgress.isCompleted = Boolean(data.is_completed)
  } catch {
    // ignore progress fetch error
  }
}

const uploadPlayProgress = async ({ isCompleted = false } = {}) => {
  const item = previewItem.value
  const video = previewVideoRef.value
  if (!item || item.mediaType !== 'video' || !video) return
  const durationSec = Number(video.duration || playProgress.durationSec || 0)
  const lastPositionSec = Number(video.currentTime || 0)
  try {
    await http.put(`/personal/progress/${item.id}`, {
      last_position_sec: lastPositionSec,
      duration_sec: durationSec,
      is_completed: isCompleted
    })
    playProgress.lastPositionSec = lastPositionSec
    playProgress.durationSec = durationSec
    playProgress.isCompleted = Boolean(isCompleted)
  } catch {
    // ignore progress upload error
  }
}

const onPreviewVideoLoadedMeta = () => {
  const video = previewVideoRef.value
  if (!video) return
  const resumeSec = Number(playProgress.lastPositionSec || 0)
  if (!playProgress.isCompleted && resumeSec > 1 && resumeSec < Number(video.duration || 0) - 1) {
    try {
      video.currentTime = resumeSec
    } catch {
      // ignore seek error
    }
  }
}

const onPreviewVideoTimeUpdate = async () => {
  const video = previewVideoRef.value
  if (!video) return
  const now = Date.now()
  const current = Number(video.currentTime || 0)
  if (now - lastProgressUploadAt.value < 5000 && Math.abs(current - lastUploadedPosition.value) < 5) return
  lastProgressUploadAt.value = now
  lastUploadedPosition.value = current
  await uploadPlayProgress({ isCompleted: false })
}

const onPreviewVideoEnded = async () => {
  await uploadPlayProgress({ isCompleted: true })
}

const restartFromBeginning = async () => {
  const video = previewVideoRef.value
  if (!video) return
  video.currentTime = 0
  video.play().catch(() => {})
  playProgress.lastPositionSec = 0
  playProgress.isCompleted = false
  await uploadPlayProgress({ isCompleted: false })
}

const previewFile = (item, options = {}) => {
  const idx = rows.value.findIndex((row) => row.id === item.id)
  previewIndex.value = idx >= 0 ? idx : 0
  previewItem.value = idx >= 0 ? rows.value[idx] : item
  previewFromRandom.value = Boolean(options.fromRandom)
  previewAutoplay.value = Boolean(options.autoplay)
  if ((previewItem.value?.mediaType || '') === 'video') {
    loadPlayProgress(previewItem.value.id)
  }
  previewVisible.value = true
}

const previewPrev = () => {
  if (!rows.value.length) return
  const nextIndex = (previewIndex.value - 1 + rows.value.length) % rows.value.length
  previewIndex.value = nextIndex
  previewItem.value = rows.value[nextIndex]
  if ((previewItem.value?.mediaType || '') === 'video') {
    loadPlayProgress(previewItem.value.id)
  }
}

const previewNext = () => {
  if (!rows.value.length) return
  const nextIndex = (previewIndex.value + 1) % rows.value.length
  previewIndex.value = nextIndex
  previewItem.value = rows.value[nextIndex]
  if ((previewItem.value?.mediaType || '') === 'video') {
    loadPlayProgress(previewItem.value.id)
  }
}

const downloadFile = (item) => {
  window.open(item.downloadUrl, '_blank')
}

const pickRandom = async () => {
  randomLoading.value = true
  try {
    const req = {
      media_type: filters.mediaType || null,
      exclude_recent_minutes: 30
    }
    const data = parseApiData(await http.post('/personal/random/pick', req))
    const record = data?.record
    if (!record) {
      ElMessage.warning('当前筛选条件下没有可随机内容')
      return
    }

    const item = {
      id: record.id,
      mediaType: record.media_type || '',
      mediaTypeText: mediaTypeText(record.media_type),
      fileName: record.file_name || `record_${record.id}`,
      fileSize: Number(record.file_size || 0),
      channel: record.chat_name || '-',
      createdAt: '-',
      savedPath: '',
      status: 'success',
      previewUrl: record.preview_url || `/api/downloads/${record.id}/file?mode=inline`,
      downloadUrl: record.download_url || `/api/downloads/${record.id}/file?mode=download`,
      thumbnailUrl: `/api/downloads/${record.id}/thumbnail`
    }
    previewFile(item, { autoplay: true, fromRandom: true })
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '随机选片失败'))
  } finally {
    randomLoading.value = false
  }
}

const openAddToCollection = async (item) => {
  collectionTarget.value = item
  selectedCollectionId.value = null
  newCollectionName.value = ''
  await fetchCollections()
  if (collections.value.length > 0) {
    selectedCollectionId.value = collections.value[0].id
  }
  collectionDialogVisible.value = true
}

const createCollectionQuick = async () => {
  const name = String(newCollectionName.value || '').trim()
  if (!name) {
    ElMessage.warning('请先输入收藏名称')
    return
  }
  creatingCollection.value = true
  try {
    await http.post('/personal/collections', { name })
    await fetchCollections()
    const created = collections.value.find((item) => item.name === name)
    if (created) selectedCollectionId.value = created.id
    newCollectionName.value = ''
    ElMessage.success('收藏已创建')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '创建收藏失败'))
  } finally {
    creatingCollection.value = false
  }
}

const confirmAddToCollection = async () => {
  if (!collectionTarget.value) return
  if (!selectedCollectionId.value) {
    ElMessage.warning('请先选择收藏')
    return
  }
  addingCollectionItem.value = true
  try {
    await http.post(`/personal/collections/${selectedCollectionId.value}/items`, {
      record_id: collectionTarget.value.id
    })
    ElMessage.success('已加入收藏')
    collectionDialogVisible.value = false
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加入收藏失败'))
  } finally {
    addingCollectionItem.value = false
  }
}

const onPreviewClosed = () => {
  previewFromRandom.value = false
  previewAutoplay.value = false
  previewVideoRef.value = null
  playProgress.lastPositionSec = 0
  playProgress.durationSec = 0
  playProgress.isCompleted = false
}

const copyPath = async (path) => {
  if (!path) {
    ElMessage.warning('暂无路径可复制')
    return
  }

  try {
    await navigator.clipboard.writeText(path)
    ElMessage.success('路径已复制')
  } catch {
    ElMessage.error('复制失败，请检查浏览器权限')
  }
}

fetchFiles()
fetchCollections()
</script>

<style scoped>
.files-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-bottom: 6px;
}

.section-card {
  border-radius: 18px;
  border: 1px solid #d8dee9;
  background: #ffffff;
}

.header-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.page-title {
  margin: 0;
  color: #0f172a;
  font-size: 30px;
  font-weight: 800;
  line-height: 1.2;
}

.page-desc {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.stat-card {
  min-height: 108px;
}

.stat-label {
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
}

.stat-value {
  margin-top: 8px;
  color: #0f172a;
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
}

.stat-sub {
  margin-top: 8px;
  color: #14b8a6;
  font-size: 12px;
  font-weight: 600;
}

.filter-form {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr 1fr 1fr auto;
  gap: 10px;
}

.filter-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.filter-form :deep(.el-form-item__label) {
  padding-bottom: 6px;
  color: #64748b;
  font-size: 12px;
  line-height: 1;
}

.filter-form :deep(.el-input__wrapper),
.filter-form :deep(.el-select__wrapper) {
  border-radius: 12px;
}

.mode-switch {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.mode-switch :deep(.el-radio-button__inner) {
  width: 100%;
  border-radius: 12px;
}

.filter-buttons {
  align-self: flex-end;
}

.filter-tags {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  color: #334155;
  background: #f1f5f9;
}

.filter-chip-cyan {
  color: #0e7490;
  background: #ecfeff;
}

.filter-chip-orange {
  color: #c2410c;
  background: #fff7ed;
}

.media-header {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.media-title {
  color: #0f172a;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}

.media-desc {
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
}

.media-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.sync-alert {
  margin-bottom: 12px;
}

.pager-wrap {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

.preview-placeholder {
  height: 260px;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.preview-dialog :deep(.el-dialog) {
  max-width: 1200px;
}

.preview-dialog :deep(.el-dialog__body) {
  padding-top: 8px;
}

.preview-title {
  margin-bottom: 10px;
  color: #111827;
  font-weight: 600;
  line-height: 1.4;
  word-break: break-all;
}

.preview-stage {
  min-height: 0;
  max-height: calc(100vh - 220px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-media {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: calc(100vh - 240px);
  border-radius: 10px;
  object-fit: contain;
}

.preview-video {
  width: min(100%, 1000px);
  background: #000;
}

.preview-nav {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: #475569;
}

.preview-progress-bar {
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #2563eb;
  font-size: 13px;
}

.gallery-grid {
  --card-min: clamp(170px, 16vw, 270px);
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(var(--card-min), 1fr));
}

.gallery-card {
  position: relative;
  overflow: hidden;
  border-radius: 12px;
  cursor: pointer;
  background: #f5f7fa;
  aspect-ratio: 9 / 16;
}

.gallery-media {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.gallery-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  background: linear-gradient(140deg, #eef2ff, #f8fafc);
}

.gallery-overlay {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  color: #fff;
  padding: 8px 10px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.7), transparent);
}

.gallery-name {
  font-size: 12px;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gallery-actions {
  display: flex;
  gap: 10px;
  margin-top: 2px;
}

.collection-tip {
  margin-bottom: 10px;
  color: #334155;
  font-size: 13px;
}

.collection-create-row {
  width: 100%;
  display: flex;
  gap: 10px;
}

@media (max-width: 1280px) {
  .filter-form {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .filter-buttons {
    justify-self: end;
  }
}

@media (max-width: 980px) {
  .header-main,
  .media-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-buttons {
    justify-self: stretch;
  }
}

@media (max-width: 700px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .stat-value {
    font-size: 34px;
  }

  .filter-form {
    grid-template-columns: 1fr;
  }
}
</style>



