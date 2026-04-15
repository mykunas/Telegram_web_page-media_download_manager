<template>
  <div class="recommend-page">
    <section class="card-shell top-hero">
      <div>
        <h1 class="hero-title">今日私享推荐</h1>
        <p class="hero-desc">按你的观看偏好生成当日内容列表，支持筛选、排序与快速操作</p>
      </div>
      <div class="hero-actions">
        <el-tag class="date-tag" effect="light">{{ recommendDate || '-' }}</el-tag>
        <el-button class="pill-btn" @click="batchFavorite">批量收藏</el-button>
        <el-button class="pill-btn dark" :loading="refreshing" @click="refreshRecommendations">手动刷新</el-button>
      </div>
    </section>

    <section class="card-shell filter-shell">
      <div class="filter-grid">
        <el-input v-model="filters.keyword" placeholder="搜索标题 / 频道 / 标签" clearable />

        <el-select v-model="filters.mediaType" placeholder="全部分类">
          <el-option label="全部分类" value="all" />
          <el-option label="视频" value="video" />
          <el-option label="图片" value="photo" />
          <el-option label="文件" value="document" />
        </el-select>

        <el-select v-model="filters.sortBy" placeholder="排序方式">
          <el-option label="推荐分优先" value="score_desc" />
          <el-option label="推荐分由低到高" value="score_asc" />
          <el-option label="最新内容" value="latest" />
          <el-option label="文件名 A-Z" value="name_asc" />
        </el-select>

        <el-radio-group v-model="filters.viewMode" class="view-mode">
          <el-radio-button label="card">卡片</el-radio-button>
          <el-radio-button label="compact">紧凑</el-radio-button>
        </el-radio-group>

        <div class="filter-actions">
          <el-button class="pill-btn" @click="resetFilters">重置</el-button>
          <el-button class="pill-btn dark" @click="applyFilters">应用筛选</el-button>
        </div>
      </div>

      <div class="filter-tags">
        <el-tag effect="light" round>当前排序：{{ sortLabel }}</el-tag>
        <el-tag effect="light" type="primary" round>仅显示{{ mediaTypeLabel }}</el-tag>
        <el-tag effect="light" type="warning" round>未看内容优先</el-tag>
      </div>
    </section>

    <section class="card-shell content-shell" v-loading="loading">
      <div class="content-head">
        <div>
          <div class="content-title">推荐内容</div>
          <div class="content-desc">让视觉更突出，弱化元信息，把操作留到卡片底部和悬浮层</div>
        </div>
        <div class="per-page">
          <span>每页显示</span>
          <el-select v-model="pagination.pageSize" style="width: 90px" @change="onPageSizeChange">
            <el-option :value="8" label="8" />
            <el-option :value="12" label="12" />
            <el-option :value="20" label="20" />
          </el-select>
        </div>
      </div>

      <el-empty v-if="!filteredSortedList.length" description="今天暂无推荐内容" />

      <div v-else class="recommend-grid" :class="{ compact: filters.viewMode === 'compact' }">
        <article class="recommend-card" v-for="item in pagedRecommendations" :key="item.id">
          <div class="media-wrap">
            <img v-if="item.media_type === 'photo'" :src="item.preview_url" class="cover" :alt="item.file_name" />
            <img
              v-else-if="item.media_type === 'video' && !thumbnailFailed[item.id]"
              :src="item.thumbnail_url"
              class="cover"
              :alt="item.file_name"
              @error="markThumbnailFailed(item.id)"
            />
            <div v-else class="cover-fallback">
              <el-icon size="34">
                <VideoPlay v-if="item.media_type === 'video'" />
                <Picture v-else-if="item.media_type === 'photo'" />
                <Document v-else />
              </el-icon>
            </div>

            <div class="badge-row">
              <span class="media-badge">{{ mediaTypeText(item.media_type) }}</span>
              <span class="score-badge">{{ scoreText(item.score) }}</span>
            </div>

            <div class="meta-overlay">
              <span>{{ item.chat_name || '-' }}</span>
              <span>{{ formatBytes(item.file_size) }}</span>
            </div>
          </div>

          <div class="body">
            <div class="title" :title="item.file_name">{{ item.file_name }}</div>
            <div class="reason">{{ item.reason || '根据最近行为推荐' }}</div>
            <div class="card-actions">
              <el-button size="small" class="pill-btn" @click="previewRecommendation(item)">预览</el-button>
              <el-button size="small" class="pill-btn" @click="toggleFavorite(item)">
                {{ isFavorited(item.id) ? '已收藏' : '收藏' }}
              </el-button>
              <el-button size="small" class="pill-btn dark" @click="openDownload(item)">下载</el-button>
            </div>
          </div>
        </article>
      </div>

      <div class="pager-wrap" v-if="filteredSortedList.length">
        <div class="pager-left">显示 {{ pageRange.start }} - {{ pageRange.end }} / 共 {{ filteredSortedList.length }} 条推荐</div>
        <el-pagination
          v-model:current-page="pagination.page"
          :page-size="pagination.pageSize"
          layout="prev, pager, next"
          :total="filteredSortedList.length"
          background
        />
      </div>
    </section>

    <el-dialog
      v-model="previewVisible"
      title="推荐预览"
      width="86vw"
      top="4vh"
      align-center
      class="preview-dialog"
      destroy-on-close
      @closed="onPreviewClosed"
    >
      <template v-if="previewItem">
        <div class="preview-title">{{ previewItem.file_name }}</div>
        <div v-if="previewItem.media_type === 'video'" class="preview-progress-bar">
          <span>{{ progressText }}</span>
          <el-button size="small" @click="restartFromBeginning">从头播放</el-button>
        </div>
        <div class="preview-stage">
          <img v-if="previewItem.media_type === 'photo'" :src="previewItem.preview_url" class="preview-media" alt="预览" />
          <video
            v-else-if="previewItem.media_type === 'video'"
            :key="previewItem.id"
            ref="previewVideoRef"
            :src="previewItem.preview_url"
            controls
            preload="metadata"
            playsinline
            autoplay
            class="preview-media preview-video"
            @loadedmetadata="onPreviewVideoLoadedMeta"
            @timeupdate="onPreviewVideoTimeUpdate"
            @ended="onPreviewVideoEnded"
          />
          <div v-else class="preview-placeholder">
            <p>{{ previewItem.file_name }}</p>
            <el-button type="primary" @click="openDownload(previewItem)">下载文件</el-button>
          </div>
        </div>
        <div v-if="filteredSortedList.length > 1" class="preview-nav">
          <el-button @click="previewPrev">上一个</el-button>
          <span>{{ previewIndex + 1 }} / {{ filteredSortedList.length }}</span>
          <el-button @click="previewNext">下一个</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="collectionDialogVisible" title="加入收藏" width="520px" destroy-on-close>
      <template v-if="collectionTarget">
        <div class="collection-tip">文件：{{ collectionTarget.file_name || `record_${collectionTarget.id}` }}</div>
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
import { Document, Picture, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'

import http from '@/api/http'

const loading = ref(false)
const refreshing = ref(false)
const recommendDate = ref('')
const list = ref([])
const thumbnailFailed = ref({})
const previewVisible = ref(false)
const previewItem = ref(null)
const previewIndex = ref(-1)
const previewVideoRef = ref(null)
const favoriteIds = ref(new Set())
const collections = ref([])
const collectionDialogVisible = ref(false)
const collectionTarget = ref(null)
const selectedCollectionId = ref(null)
const newCollectionName = ref('')
const creatingCollection = ref(false)
const addingCollectionItem = ref(false)

const pagination = reactive({
  page: 1,
  pageSize: 20
})
const filters = reactive({
  keyword: '',
  mediaType: 'all',
  sortBy: 'score_desc',
  viewMode: 'card'
})
const playProgress = reactive({
  lastPositionSec: 0,
  durationSec: 0,
  isCompleted: false
})
const lastProgressUploadAt = ref(0)
const lastUploadedPosition = ref(0)
let timer = null

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}

const apiErrorMessage = (error, fallback) => error?.response?.data?.message || error?.message || fallback

const formatBytes = (bytes) => {
  if (!bytes || Number(bytes) <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = Number(bytes)
  let idx = 0
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024
    idx += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[idx]}`
}

const mediaTypeText = (type) => {
  if (type === 'video') return '视频'
  if (type === 'photo') return '图片'
  if (type === 'document') return '文件'
  return '未知'
}

const scoreText = (score) => `${Math.round(Number(score || 0) * 100)} 分`

const sortLabel = computed(() => {
  if (filters.sortBy === 'score_desc') return '推荐分由高到低'
  if (filters.sortBy === 'score_asc') return '推荐分由低到高'
  if (filters.sortBy === 'latest') return '最新内容'
  if (filters.sortBy === 'name_asc') return '文件名 A-Z'
  return '推荐分由高到低'
})

const mediaTypeLabel = computed(() => {
  if (filters.mediaType === 'all') return '全部'
  return mediaTypeText(filters.mediaType)
})

const filteredSortedList = computed(() => {
  const keyword = String(filters.keyword || '').trim().toLowerCase()
  let arr = [...list.value]

  if (filters.mediaType !== 'all') {
    arr = arr.filter((item) => String(item.media_type || '') === filters.mediaType)
  }

  if (keyword) {
    arr = arr.filter((item) => {
      const fields = [item.file_name, item.chat_name, item.reason].map((v) => String(v || '').toLowerCase())
      return fields.some((v) => v.includes(keyword))
    })
  }

  if (filters.sortBy === 'score_desc') {
    arr.sort((a, b) => Number(b.score || 0) - Number(a.score || 0))
  } else if (filters.sortBy === 'score_asc') {
    arr.sort((a, b) => Number(a.score || 0) - Number(b.score || 0))
  } else if (filters.sortBy === 'latest') {
    arr.sort((a, b) => new Date(b.message_date || b.completed_at || 0).getTime() - new Date(a.message_date || a.completed_at || 0).getTime())
  } else if (filters.sortBy === 'name_asc') {
    arr.sort((a, b) => String(a.file_name || '').localeCompare(String(b.file_name || '')))
  }

  return arr
})

const pagedRecommendations = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize
  return filteredSortedList.value.slice(start, start + pagination.pageSize)
})

const pageRange = computed(() => {
  if (!filteredSortedList.value.length) return { start: 0, end: 0 }
  const start = (pagination.page - 1) * pagination.pageSize + 1
  const end = Math.min(pagination.page * pagination.pageSize, filteredSortedList.value.length)
  return { start, end }
})

watch(
  () => filteredSortedList.value.length,
  (total) => {
    const maxPage = Math.max(1, Math.ceil(total / pagination.pageSize))
    if (pagination.page > maxPage) pagination.page = maxPage
  }
)

watch(
  () => pagination.pageSize,
  () => {
    pagination.page = 1
  }
)

const formatTime = (sec) => {
  const total = Math.max(0, Math.floor(Number(sec || 0)))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const progressText = computed(() => {
  if (!previewItem.value || previewItem.value.media_type !== 'video') return ''
  if (playProgress.isCompleted) return '已看完'
  if (playProgress.lastPositionSec > 0) return `上次看到 ${formatTime(playProgress.lastPositionSec)}`
  return '未开始播放'
})

const fetchRecommendations = async () => {
  loading.value = true
  try {
    const data = parseApiData(await http.get('/personal/recommendations/today')) || {}
    recommendDate.value = String(data.date || '')
    list.value = Array.isArray(data.list) ? data.list : []
    favoriteIds.value = new Set(list.value.filter((item) => Boolean(item.is_favorite)).map((item) => Number(item.id)))
    thumbnailFailed.value = {}
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加载推荐失败'))
  } finally {
    loading.value = false
  }
}

const refreshRecommendations = async () => {
  refreshing.value = true
  try {
    await http.post('/personal/recommendations/refresh')
    await fetchRecommendations()
    ElMessage.success('今日推荐已刷新')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '刷新推荐失败'))
  } finally {
    refreshing.value = false
  }
}

const applyFilters = () => {
  pagination.page = 1
}

const resetFilters = () => {
  filters.keyword = ''
  filters.mediaType = 'all'
  filters.sortBy = 'score_desc'
  filters.viewMode = 'card'
  pagination.page = 1
}

const onPageSizeChange = () => {
  pagination.page = 1
}

const isFavorited = (id) => favoriteIds.value.has(Number(id))

const fetchCollections = async () => {
  try {
    const data = parseApiData(await http.get('/personal/collections')) || {}
    collections.value = Array.isArray(data.list) ? data.list : []
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加载收藏失败'))
  }
}

const openAddToCollection = async (item) => {
  collectionTarget.value = item
  selectedCollectionId.value = null
  newCollectionName.value = ''
  await fetchCollections()
  if (collections.value.length > 0) selectedCollectionId.value = collections.value[0].id
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
    favoriteIds.value = new Set([...favoriteIds.value, Number(collectionTarget.value.id)])
    ElMessage.success('已加入收藏')
    collectionDialogVisible.value = false
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加入收藏失败'))
  } finally {
    addingCollectionItem.value = false
  }
}

const toggleFavorite = (item) => {
  const id = Number(item.id)
  if (favoriteIds.value.has(id)) {
    ElMessage.info('该内容已收藏')
    return
  }
  openAddToCollection(item)
}

const batchFavorite = () => {
  const next = new Set(favoriteIds.value)
  pagedRecommendations.value.forEach((item) => next.add(Number(item.id)))
  favoriteIds.value = next
  ElMessage.success(`已收藏本页 ${pagedRecommendations.value.length} 条`)
}

const markThumbnailFailed = (id) => {
  thumbnailFailed.value[id] = true
}

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
    // ignore
  }
}

const uploadPlayProgress = async ({ isCompleted = false } = {}) => {
  const item = previewItem.value
  const video = previewVideoRef.value
  if (!item || item.media_type !== 'video' || !video) return
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
    // ignore
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
      // ignore
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

const previewRecommendation = async (item) => {
  try {
    await http.post(`/personal/recommendations/click/${item.id}`)
  } catch {
    // ignore click tracking errors
  }

  const idx = filteredSortedList.value.findIndex((row) => row.id === item.id)
  previewIndex.value = idx >= 0 ? idx : 0
  previewItem.value = idx >= 0 ? filteredSortedList.value[idx] : item

  if ((previewItem.value?.media_type || '') === 'video') {
    await loadPlayProgress(previewItem.value.id)
  }
  previewVisible.value = true
}

const previewPrev = async () => {
  if (!filteredSortedList.value.length) return
  const nextIndex = (previewIndex.value - 1 + filteredSortedList.value.length) % filteredSortedList.value.length
  previewIndex.value = nextIndex
  previewItem.value = filteredSortedList.value[nextIndex]
  if ((previewItem.value?.media_type || '') === 'video') await loadPlayProgress(previewItem.value.id)
}

const previewNext = async () => {
  if (!filteredSortedList.value.length) return
  const nextIndex = (previewIndex.value + 1) % filteredSortedList.value.length
  previewIndex.value = nextIndex
  previewItem.value = filteredSortedList.value[nextIndex]
  if ((previewItem.value?.media_type || '') === 'video') await loadPlayProgress(previewItem.value.id)
}

const openDownload = (item) => {
  const url = item.download_url || `/api/downloads/${item.id}/file?mode=download`
  window.open(url, '_blank')
}

const onPreviewClosed = () => {
  previewVideoRef.value = null
  playProgress.lastPositionSec = 0
  playProgress.durationSec = 0
  playProgress.isCompleted = false
  lastProgressUploadAt.value = 0
  lastUploadedPosition.value = 0
}

onMounted(async () => {
  await fetchRecommendations()
  timer = window.setInterval(fetchRecommendations, 30000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
  timer = null
})
</script>

<style scoped>
.recommend-page {
  display: grid;
  gap: 14px;
  background: #edf1f6;
}

.card-shell {
  width: 100%;
  min-width: 0;
  border-radius: 22px;
  border: 1px solid #dce4ef;
  background: #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
  padding: 16px;
}

.top-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.hero-title {
  margin: 0;
  font-size: clamp(24px, 3vw, 38px);
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #0b1324;
}

.hero-desc {
  margin: 6px 0 0;
  color: #7d8da7;
  font-size: 14px;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.pill-btn {
  border-radius: 999px;
  border-color: #d4deeb;
  color: #1b2b49;
  font-weight: 600;
}

.pill-btn.dark {
  background: #071228;
  border-color: #071228;
  color: #fff;
}

.date-tag {
  border-radius: 999px;
  padding-inline: 10px;
}

.filter-shell {
  padding-bottom: 14px;
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.3fr 1fr 1fr 1fr auto;
  gap: 10px;
  align-items: center;
}

.view-mode :deep(.el-radio-button__inner) {
  min-width: 92px;
}

.filter-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.filter-tags {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.content-shell {
  min-width: 0;
}

.content-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.content-title {
  font-size: 28px;
  font-weight: 800;
  color: #0c1934;
}

.content-desc {
  margin-top: 4px;
  color: #7c8ca8;
  font-size: 13px;
}

.per-page {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #7587a4;
  font-size: 13px;
}

.recommend-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.recommend-grid.compact {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.recommend-card {
  border: 1px solid #dfe6f1;
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
}

.media-wrap {
  position: relative;
}

.cover {
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
  display: block;
  background: #111827;
}

.cover-fallback {
  aspect-ratio: 16 / 10;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  background: linear-gradient(140deg, #eef2ff, #f8fafc);
}

.badge-row {
  position: absolute;
  left: 8px;
  right: 8px;
  top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.media-badge,
.score-badge {
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 700;
}

.media-badge {
  background: rgba(7, 18, 40, 0.86);
  color: #fff;
}

.score-badge {
  background: #17b3d6;
  color: #fff;
}

.meta-overlay {
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 8px;
  display: flex;
  justify-content: space-between;
  color: #fff;
  font-size: 12px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
}

.body {
  padding: 10px;
}

.title {
  color: #111827;
  font-weight: 700;
  line-height: 1.45;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.reason {
  margin-top: 6px;
  color: #6d82a4;
  font-size: 12px;
  min-height: 18px;
}

.card-actions {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.pager-wrap {
  margin-top: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.pager-left {
  color: #6f84a5;
  font-size: 13px;
}

.preview-dialog :deep(.el-dialog) {
  max-width: 1200px;
}

.preview-title {
  margin-bottom: 10px;
  color: #111827;
  font-weight: 600;
  line-height: 1.4;
  word-break: break-all;
}

.preview-progress-bar {
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #2563eb;
  font-size: 13px;
}

.preview-stage {
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

.preview-nav {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: #475569;
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

@media (max-width: 1350px) {
  .recommend-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .recommend-grid.compact {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .top-hero,
  .content-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-actions {
    justify-content: flex-start;
  }

  .recommend-grid,
  .recommend-grid.compact {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .filter-grid,
  .recommend-grid,
  .recommend-grid.compact {
    grid-template-columns: 1fr;
  }

  .pager-wrap {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
