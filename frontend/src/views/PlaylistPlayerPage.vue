<template>
  <div class="playlist-player-page">
    <el-card class="section-card header-card" shadow="never">
      <div class="header-row">
        <h1 class="page-title">播放收藏</h1>
        <div class="stats-chips">
          <span class="chip">总数 {{ stats.total }}</span>
          <span class="chip chip-green">已完成 {{ stats.completed }}</span>
          <span class="chip chip-cyan">播放中 {{ stats.playing }}</span>
          <span class="chip chip-orange">剩余 {{ stats.remaining }}</span>
        </div>
      </div>
    </el-card>

    <el-card class="section-card control-card" shadow="never" v-loading="loading">
      <div class="control-row">
        <div class="left-controls">
          <el-button round @click="goBack">返回收藏</el-button>
          <el-button round type="primary" :disabled="!stats.total" @click="startPlayback">开始播放</el-button>
          <el-button round :disabled="playState !== 'playing'" @click="pauseAll">暂停全部</el-button>
          <el-button round :disabled="playState !== 'paused'" @click="resumeAll">继续全部</el-button>
          <el-button round class="btn-yellow" :disabled="!stats.total" @click="startRandomPlayback">随机播放</el-button>
          <el-button round class="btn-red" @click="stopAll">停止全部</el-button>
          <el-button round class="btn-green" @click="restartPlayback">重新开始</el-button>
          <el-button round :disabled="mutedAll" @click="muteAll">一键静音</el-button>
          <el-button round :disabled="!mutedAll" @click="unmuteAll">取消静音</el-button>
        </div>

        <div class="right-controls">
          <span>状态：{{ stateText }}</span>
          <div class="slot-control">
            <span>窗口数</span>
            <el-input-number
              v-model="slotCountInput"
              :min="1"
              :max="256"
              :step="1"
              size="small"
              controls-position="right"
              style="width: 96px"
            />
            <el-button size="small" type="primary" round @click="applySlotCount">应用</el-button>
          </div>
          <span>队列剩余：{{ queue.length }}</span>
        </div>
      </div>
    </el-card>

    <div class="content-grid">
      <el-card class="section-card stage-card" shadow="never" v-loading="loading">
        <VideoGridPlayer
          :slots="slots"
          :total="stats.total"
          :collection-name="collectionName"
          :command="command"
          :muted="mutedAll"
          @ended="onSlotEnded"
          @error="onSlotError"
          @play="onSlotPlay"
          @pause="onSlotPause"
          @next="onSlotNext"
        />
      </el-card>

      <el-card class="section-card queue-card" shadow="never">
        <template #header>
          <div class="card-head queue-head">
            <span>播放队列</span>
            <span class="queue-badge">{{ queuePreview.length }} 条待播</span>
          </div>
        </template>

        <div v-if="queuePreview.length" class="queue-list">
          <div v-for="(item, idx) in queuePreview" :key="`q_${item.id}_${idx}`" class="queue-item">
            <div class="queue-top">
              <span class="queue-index">#{{ idx + 1 }}</span>
              <span class="queue-time">{{ formatDuration(item) }}</span>
            </div>
            <div class="queue-name" :title="item.file_name || item.title || '-'">{{ item.file_name || item.title || '-' }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无待播队列" :image-size="70" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import http from '@/api/http'
import VideoGridPlayer from '@/components/player/VideoGridPlayer.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const mode = ref('sequential')
const collectionId = ref(Number(route.params.id || 0))
const collectionName = ref('')
const allVideos = ref([])
const queue = ref([])
const slotCount = ref(8)
const slotCountInput = ref(8)
const command = reactive({ type: '', token: 0 })
const mutedAll = ref(true)
const playState = ref('idle')
const completedIds = ref(new Set())
const failedIds = ref(new Set())
const indexMap = ref({})
let persistTimer = null

const createEmptySlots = (count) => Array.from({ length: count }, (_, i) => ({ slot_index: i, status: 'waiting', video: null, currentIndex: 0 }))
const slots = ref(createEmptySlots(slotCount.value))

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}

const apiErrorMessage = (error, fallback) => error?.response?.data?.message || error?.message || fallback

const stats = computed(() => {
  const total = Number(allVideos.value.length || 0)
  const completed = completedIds.value.size
  const playing = slots.value.filter((slot) => slot.status === 'playing').length
  const active = slots.value.filter((slot) => slot.video && slot.status !== 'finished').length
  const remaining = Math.max(0, queue.value.length + active)
  return { total, completed, playing, remaining }
})

const stateText = computed(() => {
  if (playState.value === 'playing') return '播放中'
  if (playState.value === 'paused') return '已暂停'
  if (playState.value === 'finished') return '本次播放已结束'
  if (playState.value === 'stopped') return '已停止'
  return '待开始'
})

const queuePreview = computed(() => queue.value.slice(0, 12))

const setCommand = (type) => {
  command.type = type
  command.token += 1
}

const markSlotWithVideo = (slot, video, status) => {
  slot.video = video
  slot.status = status
  slot.currentIndex = indexMap.value[video.id] || 0
}

const nextVideo = () => {
  if (!queue.value.length) return null
  return queue.value.shift() || null
}

const evaluateFinished = () => {
  if (!stats.value.total) return
  if (stats.value.completed + failedIds.value.size >= stats.value.total && stats.value.remaining === 0) {
    playState.value = 'finished'
    slots.value.forEach((slot) => {
      if (!slot.video) slot.status = 'finished'
    })
  }
}

const assignNextToSlot = (slotIndex) => {
  const slot = slots.value[slotIndex]
  if (!slot) return
  const next = nextVideo()
  if (!next) {
    slot.video = null
    slot.currentIndex = 0
    slot.status = 'finished'
    evaluateFinished()
    schedulePersist()
    return
  }
  markSlotWithVideo(slot, next, playState.value === 'paused' ? 'paused' : 'playing')
  if (playState.value === 'playing') setCommand('resume')
  schedulePersist()
}

const normalizeSlots = (inputSlots, totalSlots) => {
  const normalized = createEmptySlots(totalSlots)
  inputSlots.forEach((slot, idx) => {
    if (idx >= totalSlots) return
    const target = normalized[idx]
    target.status = slot?.status || 'waiting'
    target.video = slot?.video || null
    target.currentIndex = slot?.video ? indexMap.value[slot.video.id] || 0 : 0
  })
  return normalized
}

const loadCollectionMeta = async () => {
  const data = parseApiData(await http.get('/personal/collections')) || {}
  const list = Array.isArray(data.list) ? data.list : []
  const found = list.find((item) => Number(item.id) === Number(collectionId.value))
  collectionName.value = found?.name || `收藏#${collectionId.value}`
}

const initPlayback = async (useSavedState = true) => {
  loading.value = true
  try {
    const videoData = parseApiData(await http.get(`/personal/collections/${collectionId.value}/videos`)) || {}
    allVideos.value = Array.isArray(videoData.list) ? videoData.list : []
    indexMap.value = {}
    allVideos.value.forEach((item, idx) => {
      indexMap.value[item.id] = idx + 1
    })

    const initData = parseApiData(
      await http.post(`/personal/collections/${collectionId.value}/playback/init`, {
        mode: mode.value,
        slot_count: slotCount.value,
        use_saved_state: useSavedState
      })
    )

    queue.value = Array.isArray(initData.queue) ? [...initData.queue] : []
    slots.value = normalizeSlots(Array.isArray(initData.initial_slots) ? initData.initial_slots : [], slotCount.value)

    completedIds.value = new Set()
    failedIds.value = new Set()
    slots.value.forEach((slot) => {
      if (slot.status === 'finished' && slot.video?.id) completedIds.value.add(slot.video.id)
      if (slot.status === 'error' && slot.video?.id) failedIds.value.add(slot.video.id)
    })

    const anyActive = slots.value.some((slot) => !!slot.video)
    if (!anyActive && !queue.value.length) playState.value = 'finished'
    else playState.value = 'paused'
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '初始化播放收藏失败'))
  } finally {
    loading.value = false
  }
}

const startPlayback = () => {
  mode.value = 'sequential'
  if (!stats.value.total) {
    ElMessage.warning('当前收藏没有可播放视频')
    return
  }
  if (playState.value === 'finished') {
    restartPlayback()
    return
  }
  playState.value = 'playing'
  slots.value.forEach((slot) => {
    if (slot.video && slot.status !== 'finished') slot.status = 'playing'
  })
  setCommand('resume')
  schedulePersist()
}

const startRandomPlayback = async () => {
  mode.value = 'random'
  await initPlayback(false)
  playState.value = 'playing'
  slots.value.forEach((slot) => {
    if (slot.video && slot.status !== 'finished') slot.status = 'playing'
  })
  setCommand('resume')
  schedulePersist()
}

const pauseAll = () => {
  playState.value = 'paused'
  slots.value.forEach((slot) => {
    if (slot.status === 'playing') slot.status = 'paused'
  })
  setCommand('pause')
  schedulePersist()
}

const resumeAll = () => {
  playState.value = 'playing'
  slots.value.forEach((slot) => {
    if (slot.video && slot.status !== 'finished') slot.status = 'playing'
  })
  setCommand('resume')
  schedulePersist()
}

const muteAll = () => {
  mutedAll.value = true
}

const unmuteAll = () => {
  mutedAll.value = false
}

const stopAll = () => {
  playState.value = 'stopped'
  setCommand('stop')
  queue.value = []
  slots.value = createEmptySlots(slotCount.value)
  completedIds.value = new Set()
  failedIds.value = new Set()
  schedulePersist()
}

const restartPlayback = async () => {
  await initPlayback(false)
  playState.value = 'playing'
  slots.value.forEach((slot) => {
    if (slot.video && slot.status !== 'finished') slot.status = 'playing'
  })
  setCommand('resume')
  schedulePersist()
}

const onSlotEnded = (slotIndex) => {
  const slot = slots.value[slotIndex]
  if (!slot) return
  if (slot.video?.id) completedIds.value.add(slot.video.id)
  assignNextToSlot(slotIndex)
}

const onSlotError = (slotIndex) => {
  const slot = slots.value[slotIndex]
  if (!slot) return
  if (slot.video?.id) failedIds.value.add(slot.video.id)
  slot.status = 'error'
  assignNextToSlot(slotIndex)
}

const onSlotPlay = (slotIndex) => {
  if (playState.value === 'playing') {
    const slot = slots.value[slotIndex]
    if (slot && slot.video) slot.status = 'playing'
  }
}

const onSlotPause = (slotIndex) => {
  if (playState.value === 'paused') {
    const slot = slots.value[slotIndex]
    if (slot && slot.video && slot.status !== 'finished') slot.status = 'paused'
  }
}

const onSlotNext = (slotIndex) => {
  const slot = slots.value[slotIndex]
  if (!slot) return
  if (slot.video?.id) failedIds.value.add(slot.video.id)
  assignNextToSlot(slotIndex)
}

const serializeState = () => ({
  mode: mode.value,
  queue_ids: queue.value.map((item) => Number(item.id)),
  slots: slots.value.map((slot) => ({
    slot_index: slot.slot_index,
    status: slot.status,
    current_id: slot.video?.id || null
  })),
  stats: {
    total: stats.value.total,
    completed: stats.value.completed,
    playing: stats.value.playing,
    remaining: stats.value.remaining,
    play_state: playState.value,
    slot_count: slotCount.value
  }
})

const persistState = async () => {
  try {
    await http.put(`/personal/collections/${collectionId.value}/playback/state`, serializeState())
  } catch {
    // ignore
  }
}

const schedulePersist = () => {
  if (persistTimer) window.clearTimeout(persistTimer)
  persistTimer = window.setTimeout(() => {
    persistState()
  }, 500)
}

const onSlotCountChange = async () => {
  const shouldResume = playState.value === 'playing'
  await initPlayback(false)
  if (shouldResume) startPlayback()
}

const applySlotCount = async () => {
  const next = Number(slotCountInput.value || 0)
  if (!Number.isFinite(next) || next < 1) {
    ElMessage.warning('窗口数至少为 1')
    return
  }
  const normalized = Math.min(256, Math.floor(next))
  if (normalized === slotCount.value) return
  slotCount.value = normalized
  slotCountInput.value = normalized
  await onSlotCountChange()
}

const formatDuration = (item) => {
  const sec = Number(item?.duration || item?.duration_sec || item?.duration_seconds || 0)
  if (!sec || sec <= 0) return '--:--'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const goBack = () => {
  router.push('/collections')
}

watch(
  () => [queue.value.length, slots.value.map((s) => `${s.status}:${s.video?.id || 0}`).join('|'), playState.value],
  () => {
    if (!loading.value) schedulePersist()
  }
)

onMounted(async () => {
  if (!collectionId.value) {
    ElMessage.warning('无效的收藏 ID')
    router.push('/collections')
    return
  }
  await loadCollectionMeta()
  await initPlayback(true)
  slotCountInput.value = slotCount.value
})

onBeforeUnmount(() => {
  setCommand('stop')
  if (persistTimer) window.clearTimeout(persistTimer)
})
</script>

<style scoped>
.playlist-player-page {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-card {
  border-radius: 18px;
  border: 1px solid #d8e0eb;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.page-title {
  margin: 0;
  color: #0f172a;
  font-size: 42px;
  font-weight: 800;
  line-height: 1;
}

.stats-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chip {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  color: #334155;
  background: #eff3f8;
}

.chip-green {
  color: #166534;
  background: #ecfdf3;
}

.chip-cyan {
  color: #0e7490;
  background: #ecfeff;
}

.chip-orange {
  color: #c2410c;
  background: #fff7ed;
}

.control-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.left-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.right-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  color: #334155;
  font-size: 13px;
}

.slot-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-yellow {
  color: #a16207;
  border-color: #facc15;
  background: #fefce8;
}

.btn-red {
  color: #dc2626;
  border-color: #fecaca;
  background: #fef2f2;
}

.btn-green {
  color: #15803d;
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.content-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr 290px;
  align-items: start;
}

.card-head {
  color: #0f172a;
  font-size: 30px;
  font-weight: 800;
  line-height: 1;
}

.queue-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.queue-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: #ecfeff;
  color: #0e7490;
  font-size: 12px;
  font-weight: 600;
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: calc(100vh - 276px);
  overflow-y: auto;
  padding-right: 4px;
}

.queue-item {
  border: 1px solid #e4ecf6;
  border-radius: 12px;
  padding: 8px 10px;
  background: #fff;
}

.queue-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}

.queue-index {
  color: #64748b;
  font-size: 12px;
}

.queue-time {
  color: #64748b;
  font-size: 12px;
}

.queue-name {
  color: #0f172a;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-card :deep(.el-card__body) {
  padding-top: 8px;
}

.stage-card :deep(.grid-stage) {
  height: calc(100vh - 290px);
  min-height: 420px;
}

@media (max-width: 1200px) {
  .content-grid {
    grid-template-columns: 1fr;
  }

  .queue-list {
    max-height: none;
  }
}

@media (max-width: 900px) {
  .header-row,
  .control-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-title,
  .card-head {
    font-size: 32px;
  }

  .stage-card :deep(.grid-stage) {
    height: calc(100vh - 340px);
    min-height: 360px;
  }
}
</style>
