<template>
  <div class="fav-page" v-loading="loading">
    <el-card class="section-card top-card" shadow="never">
      <div class="top-head">
        <div>
          <h1 class="page-title">我的收藏</h1>
        </div>
        <div class="top-actions">
          <el-button round @click="showBatchMoveTip">批量移出</el-button>
          <el-button round @click="exportCollections">导出收藏夹</el-button>
          <el-button round type="primary" @click="openCreateDialog">新建收藏夹</el-button>
        </div>
      </div>
    </el-card>

    <div class="fav-layout">
      <aside class="fav-side">
        <el-card class="section-card side-card" shadow="never">
          <div class="side-title-row">
            <div class="side-title">收藏播放</div>
            <el-tag size="small" type="info" effect="plain">多窗口</el-tag>
          </div>
          <div class="side-desc">从当前收藏夹按顺序抽取视频，启动多窗口回看。</div>
          <el-button class="wide-btn" type="primary" round @click="openPlaylistPlayer">开始多窗口播放</el-button>
        </el-card>

        <el-card class="section-card side-card" shadow="never">
          <div class="side-title-row">
            <div class="side-title">收藏夹</div>
            <el-button link @click="sortCollectionsByName">排序</el-button>
          </div>
          <el-button class="wide-btn create-btn" round @click="openCreateDialog">+ 新建收藏夹</el-button>

          <el-empty v-if="!collections.length" description="暂无收藏" :image-size="74" />
          <div v-else class="collection-list">
            <article
              v-for="item in collections"
              :key="item.id"
              class="collection-item"
              :class="{ active: item.id === selectedCollectionId }"
              @click="selectedCollectionId = item.id"
            >
              <div class="collection-row">
                <div class="name">{{ item.name }}</div>
                <el-tag v-if="item.id === selectedCollectionId" size="small" type="primary" effect="dark">当前</el-tag>
              </div>
              <div class="meta">{{ item.item_count || 0 }} 个文件</div>
              <div class="actions" @click.stop>
                <el-button link @click="moveCollection(item, -1)">上移</el-button>
                <el-button link @click="moveCollection(item, 1)">下移</el-button>
                <el-button link type="primary" @click="openEditDialog(item)">编辑</el-button>
                <el-button link type="danger" @click="removeCollection(item)">删除</el-button>
              </div>
            </article>
          </div>
        </el-card>

        <el-card class="section-card side-card" shadow="never">
          <div class="side-title-row">
            <div class="side-title">今日重温</div>
            <el-tag size="small" type="warning" effect="plain">随机推荐</el-tag>
          </div>
          <el-button class="wide-btn" round @click="pickRandomOne" :loading="randomLoading">随机播放一条</el-button>
        </el-card>
      </aside>

      <section class="fav-main">
        <el-card class="section-card inline-summary-card" shadow="never">
          <div class="inline-summary-grid">
            <div v-for="item in summaryStats" :key="item.label" class="inline-summary-item">
              <div class="inline-label">{{ item.label }}</div>
              <div class="inline-value">{{ item.value }}</div>
              <div class="inline-sub">{{ item.sub }}</div>
            </div>
          </div>
        </el-card>

        <el-card class="section-card filter-card" shadow="never">
          <el-form class="filter-form" label-position="top" @submit.prevent>
            <el-form-item label="搜索当前收藏夹">
              <el-input v-model="filters.keyword" placeholder="搜索标题 / 文件名" clearable />
            </el-form-item>
            <el-form-item label="排序">
              <el-select v-model="filters.sort" placeholder="最近加入">
                <el-option label="最近加入" value="recent" />
                <el-option label="文件名" value="name" />
                <el-option label="文件大小" value="size" />
              </el-select>
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="filters.mediaType" placeholder="全部类型" clearable>
                <el-option label="全部类型" value="" />
                <el-option label="视频" value="video" />
                <el-option label="图片" value="photo" />
                <el-option label="文件" value="document" />
              </el-select>
            </el-form-item>
            <el-form-item class="filter-action">
              <el-button round @click="resetFilters">重置</el-button>
              <el-button type="primary" round @click="applyFilters">应用</el-button>
            </el-form-item>
          </el-form>

          <div class="filter-tags">
            <span class="chip">当前收藏夹：{{ currentCollection?.name || '未选择' }}</span>
            <span class="chip chip-cyan">排序：{{ sortText }}</span>
            <span class="chip chip-orange">共 {{ filteredItems.length }} 项</span>
          </div>
        </el-card>

        <el-card class="section-card media-card" shadow="never">
          <div class="main-head">
            <div class="main-title">{{ currentCollection?.name || '收藏内容' }}</div>
          </div>

          <el-empty v-if="!currentCollection" description="请选择左侧收藏夹" />
          <el-empty v-else-if="!filteredItems.length" description="该收藏夹暂无匹配内容" />

          <div v-else class="media-grid">
            <article v-for="item in filteredItems" :key="item.record_id" class="media-card-item">
              <div class="cover-wrap" @click="previewItem(item)">
                <img
                  v-if="item.record?.media_type === 'photo'"
                  :src="item.record?.preview_url"
                  class="cover"
                  :alt="item.record?.file_name || ''"
                />
                <img
                  v-else-if="item.record?.media_type === 'video'"
                  :src="item.record?.thumbnail_url"
                  class="cover"
                  :alt="item.record?.file_name || ''"
                />
                <div v-else class="cover-fallback">FILE</div>

                <div class="cover-top">
                  <el-tag size="small" effect="dark">{{ mediaTypeText(item.record?.media_type) }}</el-tag>
                </div>
                <div class="cover-bottom">
                  <span>{{ itemDurationText(item) }}</span>
                  <span>{{ formatBytes(item.record?.file_size) }}</span>
                </div>
              </div>

              <div class="body">
                <div class="title" :title="item.record?.file_name || ''">{{ item.record?.file_name || `record_${item.record_id}` }}</div>
                <div class="meta-row">
                  <span>{{ item.record?.chat_name || '未知频道' }}</span>
                  <span>{{ relativeAddedAt(item) }}</span>
                </div>
                <div class="card-actions">
                  <el-button size="small" round @click="previewItem(item)">预览</el-button>
                  <el-button size="small" round type="danger" plain @click="removeItem(item)">移出</el-button>
                  <el-button size="small" round type="primary" @click="downloadItem(item)">下载</el-button>
                </div>
              </div>
            </article>
          </div>
        </el-card>
      </section>
    </div>

    <el-dialog v-model="editDialogVisible" :title="editDialogTitle" width="520px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="收藏名称">
          <el-input v-model="editForm.name" placeholder="请输入收藏名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewVisible" title="收藏预览" width="86vw" top="4vh" align-center destroy-on-close>
      <template v-if="previewRecord">
        <div class="preview-title">{{ previewRecord.file_name }}</div>
        <div class="preview-stage">
          <img v-if="previewRecord.media_type === 'photo'" :src="previewRecord.preview_url" class="preview-media" alt="预览" />
          <video
            v-else-if="previewRecord.media_type === 'video'"
            :src="previewRecord.preview_url"
            controls
            preload="metadata"
            playsinline
            autoplay
            class="preview-media preview-video"
          />
          <div v-else class="preview-placeholder">
            <el-button type="primary" @click="downloadByRecord(previewRecord)">下载文件</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import http from '@/api/http'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const randomLoading = ref(false)
const collections = ref([])
const selectedCollectionId = ref(null)
const editDialogVisible = ref(false)
const editMode = ref('create')
const editingCollectionId = ref(null)
const previewVisible = ref(false)
const previewRecord = ref(null)
const editForm = reactive({
  name: '',
  description: ''
})

const filters = reactive({
  keyword: '',
  sort: 'recent',
  mediaType: ''
})

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}

const apiErrorMessage = (error, fallback) => error?.response?.data?.message || error?.message || fallback

const editDialogTitle = computed(() => (editMode.value === 'create' ? '新建收藏夹' : '编辑收藏夹'))

const currentCollection = computed(() => {
  if (!selectedCollectionId.value) return null
  return collections.value.find((item) => item.id === selectedCollectionId.value) || null
})

const currentItems = computed(() => {
  const list = currentCollection.value?.items
  return Array.isArray(list) ? list : []
})

const sortText = computed(() => {
  if (filters.sort === 'name') return '文件名'
  if (filters.sort === 'size') return '文件大小'
  return '最近加入'
})

const filteredItems = computed(() => {
  let list = [...currentItems.value]
  const keyword = String(filters.keyword || '').trim().toLowerCase()
  if (keyword) {
    list = list.filter((item) => {
      const name = String(item.record?.file_name || '').toLowerCase()
      const chat = String(item.record?.chat_name || '').toLowerCase()
      return name.includes(keyword) || chat.includes(keyword)
    })
  }

  if (filters.mediaType) {
    list = list.filter((item) => String(item.record?.media_type || '') === filters.mediaType)
  }

  if (filters.sort === 'name') {
    list.sort((a, b) => String(a.record?.file_name || '').localeCompare(String(b.record?.file_name || '')))
  } else if (filters.sort === 'size') {
    list.sort((a, b) => Number(b.record?.file_size || 0) - Number(a.record?.file_size || 0))
  } else {
    list.sort((a, b) => getItemTimestamp(b) - getItemTimestamp(a))
  }

  return list
})

const summaryStats = computed(() => {
  const filesCount = currentItems.value.length
  const videoCount = currentItems.value.filter((item) => item.record?.media_type === 'video').length
  const recentAdded = currentItems.value.filter((item) => Date.now() - getItemTimestamp(item) < 7 * 24 * 3600 * 1000).length
  const sizeTotal = currentItems.value.reduce((sum, item) => sum + Number(item.record?.file_size || 0), 0)
  return [
    { label: '当前收藏夹', value: filesCount.toLocaleString(), sub: currentCollection.value?.name || '未选择' },
    { label: '视频数量', value: videoCount.toLocaleString(), sub: '可直接预览' },
    { label: '最近新增', value: recentAdded.toLocaleString(), sub: '近 7 天加入' },
    { label: '占用空间', value: formatBytes(sizeTotal), sub: '收藏内容体积' }
  ]
})

const getItemTimestamp = (item) => {
  const t = item?.created_at || item?.added_at || item?.updated_at || item?.record?.created_at
  const v = new Date(t || 0).getTime()
  return Number.isFinite(v) ? v : 0
}

const relativeAddedAt = (item) => {
  const ts = getItemTimestamp(item)
  if (!ts) return '时间未知'
  const diff = Date.now() - ts
  if (diff < 24 * 3600 * 1000) return '今天加入'
  if (diff < 2 * 24 * 3600 * 1000) return '昨天加入'
  return `${Math.floor(diff / (24 * 3600 * 1000))} 天前加入`
}

const itemDurationText = (item) => {
  const d = Number(item?.record?.duration || item?.record?.duration_sec || 0)
  if (!d) return '--:--'
  const m = Math.floor(d / 60)
  const s = Math.floor(d % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
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

const mediaTypeText = (type) => {
  if (type === 'video') return '视频'
  if (type === 'photo') return '图片'
  if (type === 'document') return '文件'
  return '-'
}

const fetchCollections = async () => {
  loading.value = true
  try {
    const data = parseApiData(await http.get('/personal/collections')) || {}
    const list = Array.isArray(data.list) ? data.list : []
    collections.value = list
    if (!selectedCollectionId.value && list.length > 0) {
      selectedCollectionId.value = list[0].id
    }
    if (selectedCollectionId.value && !list.find((item) => item.id === selectedCollectionId.value)) {
      selectedCollectionId.value = list[0]?.id || null
    }
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加载收藏失败'))
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  ElMessage.success('筛选已应用')
}

const resetFilters = () => {
  filters.keyword = ''
  filters.sort = 'recent'
  filters.mediaType = ''
}

const openCreateDialog = () => {
  editMode.value = 'create'
  editingCollectionId.value = null
  editForm.name = ''
  editForm.description = ''
  editDialogVisible.value = true
}

const openEditDialog = (item) => {
  editMode.value = 'edit'
  editingCollectionId.value = item.id
  editForm.name = item.name || ''
  editForm.description = item.description || ''
  editDialogVisible.value = true
}

const submitEdit = async () => {
  const name = String(editForm.name || '').trim()
  if (!name) {
    ElMessage.warning('收藏名称不能为空')
    return
  }

  saving.value = true
  try {
    if (editMode.value === 'create') {
      await http.post('/personal/collections', {
        name,
        description: String(editForm.description || '').trim() || null
      })
      ElMessage.success('收藏夹已创建')
    } else {
      await http.put(`/personal/collections/${editingCollectionId.value}`, {
        name,
        description: String(editForm.description || '').trim() || null
      })
      ElMessage.success('收藏夹已更新')
    }
    editDialogVisible.value = false
    await fetchCollections()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '保存收藏夹失败'))
  } finally {
    saving.value = false
  }
}

const removeCollection = async (item) => {
  try {
    await ElMessageBox.confirm(`确认删除收藏夹「${item.name}」吗？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }

  try {
    await http.delete(`/personal/collections/${item.id}`)
    ElMessage.success('收藏夹已删除')
    await fetchCollections()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '删除收藏夹失败'))
  }
}

const moveCollection = async (item, direction) => {
  const idx = collections.value.findIndex((row) => row.id === item.id)
  if (idx < 0) return
  const targetIdx = idx + direction
  if (targetIdx < 0 || targetIdx >= collections.value.length) return

  const current = collections.value[idx]
  const target = collections.value[targetIdx]
  try {
    await http.put(`/personal/collections/${current.id}`, { sort_order: target.sort_order })
    await http.put(`/personal/collections/${target.id}`, { sort_order: current.sort_order })
    await fetchCollections()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '调整排序失败'))
  }
}

const sortCollectionsByName = () => {
  collections.value = [...collections.value].sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
}

const previewItem = (item) => {
  if (!item.record) {
    ElMessage.warning('文件详情缺失，无法预览')
    return
  }
  previewRecord.value = item.record
  previewVisible.value = true
}

const downloadByRecord = (record) => {
  if (!record) return
  const url = record.download_url || `/api/downloads/${record.id}/file?mode=download`
  window.open(url, '_blank')
}

const downloadItem = (item) => {
  downloadByRecord(item.record)
}

const removeItem = async (item) => {
  if (!currentCollection.value) return
  try {
    await http.delete(`/personal/collections/${currentCollection.value.id}/items/${item.record_id}`)
    ElMessage.success('已从收藏夹移除')
    await fetchCollections()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '移除失败'))
  }
}

const openPlaylistPlayer = () => {
  if (!selectedCollectionId.value) {
    ElMessage.warning('请先选择一个收藏夹')
    return
  }
  router.push(`/collections/${selectedCollectionId.value}/player`)
}

const pickRandomOne = async () => {
  randomLoading.value = true
  try {
    const data = parseApiData(
      await http.post('/personal/random/pick', {
        media_type: filters.mediaType || null,
        exclude_recent_minutes: 30
      })
    )
    const record = data?.record
    if (!record) {
      ElMessage.warning('当前条件下没有可随机内容')
      return
    }

    previewRecord.value = {
      id: record.id,
      file_name: record.file_name || `record_${record.id}`,
      media_type: record.media_type || '',
      file_size: Number(record.file_size || 0),
      preview_url: record.preview_url || `/api/downloads/${record.id}/file?mode=inline`,
      download_url: record.download_url || `/api/downloads/${record.id}/file?mode=download`
    }
    previewVisible.value = true
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '随机播放失败'))
  } finally {
    randomLoading.value = false
  }
}

const showBatchMoveTip = () => {
  ElMessage.info('批量移出入口已保留，可继续接入批量操作接口')
}

const exportCollections = () => {
  const payload = collections.value.map((c) => ({
    id: c.id,
    name: c.name,
    description: c.description,
    item_count: c.item_count,
    sort_order: c.sort_order
  }))
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'collections-export.json'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success('收藏夹已导出')
}

fetchCollections()
</script>

<style scoped>
.fav-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-card {
  border-radius: 18px;
  border: 1px solid #d6dee9;
}

.top-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-title {
  margin: 0;
  color: #0f172a;
  font-size: 32px;
  font-weight: 800;
  line-height: 1.2;
}

.page-desc {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
}

.top-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.stat-label {
  color: #64748b;
  font-size: 13px;
}

.stat-value {
  margin-top: 8px;
  color: #0f172a;
  font-size: 42px;
  font-weight: 700;
  line-height: 1;
}

.stat-sub {
  margin-top: 10px;
  color: #0ea5e9;
  font-size: 12px;
  font-weight: 600;
}

.fav-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 14px;
}

.fav-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: sticky;
  top: 10px;
  align-self: start;
  max-height: calc(100vh - 24px);
  overflow-y: auto;
  padding-right: 2px;
}

.side-card :deep(.el-card__body) {
  padding: 14px;
}

.side-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.side-title {
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

.side-desc {
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.wide-btn {
  width: 100%;
  margin-top: 12px;
}

.create-btn {
  background: #0ea5e9;
  border-color: #0ea5e9;
  color: #fff;
}

.collection-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.collection-item {
  border: 1px solid #dbe4ef;
  border-radius: 14px;
  padding: 10px;
  cursor: pointer;
  background: #fff;
  transition: all 0.2s ease;
}

.collection-item:hover {
  border-color: #90cdf4;
  background: #f8fcff;
}

.collection-item.active {
  border-color: #22b3e6;
  background: #eefbff;
}

.collection-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.name {
  color: #0f172a;
  font-weight: 700;
}

.meta {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
}

.actions {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fav-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.inline-summary-card :deep(.el-card__body) {
  padding: 10px 14px;
  background: #ffffff;
  border-radius: 16px;
}

.inline-summary-grid {
  display: grid;
  gap: 0;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.inline-summary-item {
  padding: 10px 12px;
}

.inline-summary-item + .inline-summary-item {
  border-left: 1px solid #e5edf7;
}

.inline-label {
  color: #64748b;
  font-size: 12px;
}

.inline-value {
  margin-top: 6px;
  color: #0f172a;
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
}

.inline-sub {
  margin-top: 6px;
  color: #0ea5e9;
  font-size: 12px;
}

.filter-form {
  display: grid;
  grid-template-columns: 1.4fr 0.7fr 0.7fr auto;
  gap: 10px;
}

.filter-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.filter-form :deep(.el-form-item__label) {
  color: #64748b;
  font-size: 12px;
  padding-bottom: 6px;
}

.filter-action {
  align-self: flex-end;
}

.filter-tags {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  padding: 6px 12px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #334155;
  font-size: 12px;
}

.chip-cyan {
  background: #ecfeff;
  color: #0e7490;
}

.chip-orange {
  background: #fff7ed;
  color: #c2410c;
}

.main-head {
  margin-bottom: 12px;
}

.main-title {
  color: #0f172a;
  font-size: 30px;
  font-weight: 800;
}

.media-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
}

.media-card-item {
  border: 1px solid #dbe4ef;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
}

.cover-wrap {
  position: relative;
  aspect-ratio: 9 / 16;
  background: #0f172a;
  cursor: pointer;
}

.cover {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.cover-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  background: #111827;
}

.cover-top {
  position: absolute;
  left: 8px;
  top: 8px;
}

.cover-bottom {
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 8px;
  display: flex;
  justify-content: space-between;
  color: #fff;
  font-size: 12px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.55);
}

.body {
  padding: 10px;
}

.title {
  color: #0f172a;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.meta-row {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
}

.card-actions {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.preview-title {
  margin-bottom: 10px;
  color: #111827;
  font-weight: 600;
  line-height: 1.4;
  word-break: break-all;
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
  align-items: center;
  justify-content: center;
}

@media (max-width: 1200px) {
  .fav-layout {
    grid-template-columns: 1fr;
  }

  .fav-side {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .inline-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .top-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-form {
    grid-template-columns: 1fr;
  }

  .inline-summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
