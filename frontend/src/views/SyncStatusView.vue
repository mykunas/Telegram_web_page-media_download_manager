<template>
  <div>
    <h1 class="page-title">同步与频道</h1>
    <p class="page-desc">集中管理频道列表、同步进度和异常状态恢复。</p>

    <el-row :gutter="12" style="margin-top: 14px">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="page-card metric-card" shadow="hover">
          <div class="metric-label">服务状态</div>
          <div class="metric-value">
            <el-tag :type="serviceRunning ? 'success' : 'info'" effect="dark">
              {{ serviceRunning ? '运行中' : '已停止' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="page-card metric-card" shadow="hover">
          <div class="metric-label">频道数量</div>
          <div class="metric-value text">{{ channelCount }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="page-card metric-card" shadow="hover">
          <div class="metric-label">历史补齐任务</div>
          <div class="metric-value">
            <el-tag :type="serviceState.history_task_running ? 'warning' : 'info'" effect="plain">
              {{ serviceState.history_task_running ? '执行中' : '空闲' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="page-card metric-card" shadow="hover">
          <div class="metric-label">一致性校验任务</div>
          <div class="metric-value">
            <el-tag :type="serviceState.recheck_task_running ? 'warning' : 'info'" effect="plain">
              {{ serviceState.recheck_task_running ? '执行中' : '空闲' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="page-card" shadow="never" style="margin-top: 12px">
      <div class="action-row">
        <div class="buttons">
          <el-button type="success" :loading="actionLoading.start" @click="triggerAction('start')">启动同步</el-button>
          <el-button type="warning" :loading="actionLoading.stop" @click="triggerAction('stop')">停止同步</el-button>
          <el-button :loading="actionLoading.history" @click="triggerAction('history')">触发历史补齐</el-button>
          <el-button :loading="actionLoading.recheck" @click="triggerAction('recheck')">触发一致性校验</el-button>
          <el-button type="danger" plain :loading="actionLoading.reset" @click="triggerAction('reset')">一键重置</el-button>
        </div>
        <div class="meta">
          <el-tag type="info" effect="plain">最后动作：{{ formatAction(serviceState.last_action) }}</el-tag>
          <el-tag type="info" effect="plain">更新时间：{{ serviceState.last_action_at || '-' }}</el-tag>
          <el-button link type="primary" @click="loadAll">刷新</el-button>
        </div>
      </div>
    </el-card>

    <el-card class="page-card" shadow="never" style="margin-top: 12px">
      <div class="section-head">
        <div>
          <div class="section-title">频道管理</div>
          <div class="section-desc">添加、删除、更新频道，并对异常频道执行重置或重新同步。</div>
        </div>
        <div class="buttons">
          <el-button round size="small" :loading="configLoading" @click="loadChannelConfig">刷新频道</el-button>
          <el-button round size="small" type="danger" plain :loading="actionLoading.reset" @click="triggerAction('reset')">
            一键重置
          </el-button>
          <el-button round size="small" type="success" :loading="actionLoading.history" @click="triggerAction('history')">
            全部重新同步
          </el-button>
        </div>
      </div>

      <div class="channel-add-row">
        <el-input v-model.trim="channelDraft" placeholder="输入频道 ID、@username 或邀请链接" clearable @keyup.enter="addChannel" />
        <el-button type="primary" :loading="channelActionLoading.add" @click="addChannel">添加频道</el-button>
      </div>

      <el-table :data="managedChannelRows" border stripe class="channel-table" empty-text="暂无目标频道">
        <el-table-column label="频道" min-width="220">
          <template #default="scope">
            <el-input v-model.trim="channelEdits[scope.row.ref]" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="名称" min-width="150">
          <template #default="scope">{{ scope.row.chatName || '-' }}</template>
        </el-table-column>
        <el-table-column label="同步状态" width="120" align="center">
          <template #default="scope">
            <el-tag :type="syncStatusTagType(scope.row.syncStatus)" size="small" effect="light">
              {{ formatSyncStatus(scope.row.syncStatus) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发现/成功/失败" width="140" align="center">
          <template #default="scope">
            {{ scope.row.totalFound }}/{{ scope.row.totalSuccess }}/{{ scope.row.totalFailed }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="scope">
            <el-button link type="primary" :loading="channelRowLoading[scope.row.ref]?.update" @click="updateChannel(scope.row)">
              更新
            </el-button>
            <el-button link type="danger" :loading="channelRowLoading[scope.row.ref]?.delete" @click="deleteChannel(scope.row)">
              删除
            </el-button>
            <el-button link type="warning" :loading="channelRowLoading[scope.row.ref]?.reset" @click="resetManagedChannel(scope.row)">
              重置
            </el-button>
            <el-button link type="success" :loading="channelRowLoading[scope.row.ref]?.resync" @click="resyncManagedChannel(scope.row)">
              重新同步
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="page-card" shadow="never" style="margin-top: 12px">
      <div class="section-head">
        <div>
          <div class="section-title">同步状态明细</div>
          <div class="section-desc">按频道查看扫描、下载和缺失统计。</div>
        </div>
      </div>
      <el-table :data="rows" border stripe v-loading="loading">
        <el-table-column prop="chat_id" label="频道ID" min-width="160" sortable />
        <el-table-column prop="chat_name" label="频道名称" min-width="160" sortable>
          <template #default="scope">{{ scope.row.chat_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="last_scanned_message_id" label="最近扫描消息ID" min-width="170" sortable />
        <el-table-column
          prop="last_downloaded_message_id"
          label="最近下载消息ID"
          min-width="190"
          sortable
        />
        <el-table-column prop="total_found" label="发现总数" width="110" sortable />
        <el-table-column prop="total_success" label="成功总数" width="120" sortable />
        <el-table-column prop="total_failed" label="失败总数" width="110" sortable />
        <el-table-column prop="total_skipped" label="跳过总数" width="120" sortable />
        <el-table-column prop="missing_count" label="缺失数" width="120" sortable />
        <el-table-column prop="sync_status" label="同步状态" width="130" sortable>
          <template #default="scope">
            <el-tag :type="syncStatusTagType(scope.row.sync_status)" size="small">
              {{ formatSyncStatus(scope.row.sync_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_sync_at" label="最后同步时间" min-width="180" sortable />
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="scope">
            <el-button link type="primary" :loading="rowLoading[scope.row.chat_id]?.reset" @click="resetChannel(scope.row)">
              重置
            </el-button>
            <el-button link type="success" :loading="rowLoading[scope.row.chat_id]?.resync" @click="resyncChannel(scope.row)">
              重新同步
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import http from '@/api/http'

const loading = ref(false)
const configLoading = ref(false)
const rows = ref([])
const timerRef = ref(null)
const channelDraft = ref('')

const serviceState = reactive({
  service_running: false,
  history_task_running: false,
  recheck_task_running: false,
  last_action: '',
  last_action_at: ''
})

const actionLoading = reactive({
  start: false,
  stop: false,
  history: false,
  recheck: false,
  reset: false
})
const rowLoading = reactive({})
const channelEdits = reactive({})
const channelRowLoading = reactive({})
const channelActionLoading = reactive({
  add: false
})
const downloadConfig = reactive({
  DOWNLOAD_DIR: '/downloads',
  TARGET_CHATS: '',
  ALLOW_EXTS: '.mp4,.mkv,.mov,.avi,.jpg,.jpeg,.png,.webp',
  DOWNLOAD_HISTORY: true,
  HISTORY_LIMIT: 2000,
  MAX_RETRIES: 3,
  RETRY_DELAY: 5,
  MAX_FILE_SIZE_MB: 0
})

const serviceRunning = computed(() => Boolean(serviceState.service_running))
const channelCount = computed(() => rows.value.length)
const targetChannelRefs = computed(() => parseTargetChats())
const syncStatusMap = computed(() => {
  const map = new Map()
  rows.value.forEach((row) => {
    map.set(String(row.chat_id), row)
  })
  return map
})
const managedChannelRows = computed(() =>
  targetChannelRefs.value.map((refValue, index) => {
    const statusRow = syncStatusMap.value.get(refValue) || {}
    return {
      ref: refValue,
      index,
      chatId: Number.isFinite(Number(refValue)) ? Number(refValue) : null,
      chatName: statusRow.chat_name || statusRow.chat_id || '',
      syncStatus: statusRow.sync_status || '',
      totalFound: Number(statusRow.total_found || 0),
      totalSuccess: Number(statusRow.total_success || 0),
      totalFailed: Number(statusRow.total_failed || 0)
    }
  })
)

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}

const apiErrorMessage = (error, fallback) => error?.response?.data?.message || error?.message || fallback

function parseTargetChats() {
  return String(downloadConfig.TARGET_CHATS || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

const dedupeChannels = (items) => {
  const seen = new Set()
  const result = []
  items.forEach((item) => {
    const value = String(item || '').trim()
    if (!value || seen.has(value)) return
    seen.add(value)
    result.push(value)
  })
  return result
}

const syncChannelEdits = () => {
  Object.keys(channelEdits).forEach((key) => {
    if (!targetChannelRefs.value.includes(key)) delete channelEdits[key]
  })
  targetChannelRefs.value.forEach((refValue) => {
    if (!channelEdits[refValue]) channelEdits[refValue] = refValue
  })
}

const setTargetChats = (items) => {
  downloadConfig.TARGET_CHATS = dedupeChannels(items).join(',')
  syncChannelEdits()
}

const assignDownloadConfig = (data = {}) => {
  downloadConfig.DOWNLOAD_DIR = data.DOWNLOAD_DIR || '/downloads'
  downloadConfig.TARGET_CHATS = data.TARGET_CHATS || ''
  downloadConfig.ALLOW_EXTS = data.ALLOW_EXTS || ''
  downloadConfig.DOWNLOAD_HISTORY = Boolean(data.DOWNLOAD_HISTORY)
  downloadConfig.HISTORY_LIMIT = Number(data.HISTORY_LIMIT || 0)
  downloadConfig.MAX_RETRIES = Number(data.MAX_RETRIES || 0)
  downloadConfig.RETRY_DELAY = Number(data.RETRY_DELAY || 0)
  downloadConfig.MAX_FILE_SIZE_MB = Number(data.MAX_FILE_SIZE_MB || 0)
  syncChannelEdits()
}

const syncStatusTagType = (status) => {
  const val = String(status || '').toLowerCase()
  if (val === 'running' || val === 'scanning_history') return 'primary'
  if (val === 'completed' || val === 'idle') return 'success'
  if (val === 'error') return 'danger'
  return 'info'
}

const formatSyncStatus = (status) => {
  const val = String(status || '').toLowerCase()
  if (val === 'running') return '运行中'
  if (val === 'scanning_history') return '扫描历史'
  if (val === 'completed') return '已完成'
  if (val === 'idle') return '空闲'
  if (val === 'error') return '异常'
  return status || '-'
}

const formatAction = (action) => {
  const val = String(action || '').toLowerCase()
  if (val === 'start') return '启动'
  if (val === 'stop') return '停止'
  if (val === 'history') return '历史补齐'
  if (val === 'recheck') return '一致性校验'
  if (val === 'reset') return '重置'
  if (val === 'initialized') return '已初始化'
  return action || '-'
}

const loadSyncStatus = async () => {
  loading.value = true
  try {
    const resp = await http.get('/sync/status')
    const data = parseApiData(resp)

    const service = data?.service || {}
    serviceState.service_running = Boolean(service.service_running)
    serviceState.history_task_running = Boolean(service.history_task_running)
    serviceState.recheck_task_running = Boolean(service.recheck_task_running)
    serviceState.last_action = service.last_action || ''
    serviceState.last_action_at = service.last_action_at || ''

    const channels = Array.isArray(data?.channels) ? data.channels : []
    rows.value = channels.map((item) => ({
      ...item,
      chat_name: item.chat_name || null
    }))
  } catch (error) {
    ElMessage.error(error?.message || '加载同步状态失败')
  } finally {
    loading.value = false
  }
}

const loadChannelConfig = async () => {
  configLoading.value = true
  try {
    const resp = await http.get('/telegram-config')
    const data = parseApiData(resp)
    assignDownloadConfig(data?.download || {})
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加载频道配置失败'))
  } finally {
    configLoading.value = false
  }
}

const loadAll = async () => {
  await Promise.all([loadSyncStatus(), loadChannelConfig()])
}

const saveDownloadConfig = async () => {
  const payload = {
    DOWNLOAD_DIR: downloadConfig.DOWNLOAD_DIR,
    TARGET_CHATS: downloadConfig.TARGET_CHATS,
    ALLOW_EXTS: downloadConfig.ALLOW_EXTS,
    DOWNLOAD_HISTORY: downloadConfig.DOWNLOAD_HISTORY,
    HISTORY_LIMIT: downloadConfig.HISTORY_LIMIT,
    MAX_RETRIES: downloadConfig.MAX_RETRIES,
    RETRY_DELAY: downloadConfig.RETRY_DELAY,
    MAX_FILE_SIZE_MB: downloadConfig.MAX_FILE_SIZE_MB
  }
  const resp = await http.put('/telegram-config/download', payload)
  assignDownloadConfig(parseApiData(resp))
}

const persistTargetChannels = async (successMessage) => {
  await saveDownloadConfig()
  await loadSyncStatus()
  ElMessage.success(successMessage)
}

const triggerAction = async (action) => {
  const mapping = {
    start: '/sync/start',
    stop: '/sync/stop',
    history: '/sync/history',
    recheck: '/sync/recheck',
    reset: '/sync/reset'
  }

  const url = mapping[action]
  if (!url) return

  actionLoading[action] = true
  try {
    const resp = await http.post(url)
    const data = parseApiData(resp)

    ElMessage.success(data?.detail || '操作已提交')
    await loadAll()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '操作失败'))
  } finally {
    actionLoading[action] = false
  }
}

const setRowLoading = (chatId, key, value) => {
  if (!rowLoading[chatId]) rowLoading[chatId] = {}
  rowLoading[chatId][key] = value
}

const setChannelRowLoading = (refValue, action, value) => {
  if (!channelRowLoading[refValue]) channelRowLoading[refValue] = {}
  channelRowLoading[refValue][action] = value
}

const addChannel = async () => {
  const value = channelDraft.value.trim()
  if (!value) {
    ElMessage.warning('请先输入频道')
    return
  }
  if (targetChannelRefs.value.includes(value)) {
    ElMessage.warning('该频道已存在')
    return
  }

  channelActionLoading.add = true
  try {
    setTargetChats([...targetChannelRefs.value, value])
    await persistTargetChannels('频道已添加')
    channelDraft.value = ''
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '添加频道失败'))
  } finally {
    channelActionLoading.add = false
  }
}

const updateChannel = async (row) => {
  const nextValue = String(channelEdits[row.ref] || '').trim()
  if (!nextValue) {
    ElMessage.warning('频道不能为空')
    return
  }

  const channels = [...targetChannelRefs.value]
  const duplicated = channels.some((item, index) => item === nextValue && index !== row.index)
  if (duplicated) {
    ElMessage.warning('该频道已存在')
    return
  }

  setChannelRowLoading(row.ref, 'update', true)
  try {
    channels[row.index] = nextValue
    setTargetChats(channels)
    await persistTargetChannels('频道已更新')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '更新频道失败'))
  } finally {
    setChannelRowLoading(row.ref, 'update', false)
  }
}

const deleteChannel = async (row) => {
  setChannelRowLoading(row.ref, 'delete', true)
  try {
    setTargetChats(targetChannelRefs.value.filter((_, index) => index !== row.index))
    await persistTargetChannels('频道已删除')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '删除频道失败'))
  } finally {
    setChannelRowLoading(row.ref, 'delete', false)
  }
}

const resetManagedChannel = async (row) => {
  if (!row.chatId || !syncStatusMap.value.has(String(row.chatId))) {
    ElMessage.warning('该频道还没有同步记录，运行一次历史补齐后可重置')
    return
  }

  setChannelRowLoading(row.ref, 'reset', true)
  try {
    const resp = await http.post(`/sync/status/${row.chatId}/reset`)
    const data = parseApiData(resp)
    ElMessage.success(data?.detail || '频道同步状态已重置')
    await loadSyncStatus()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '频道重置失败'))
  } finally {
    setChannelRowLoading(row.ref, 'reset', false)
  }
}

const resyncManagedChannel = async (row) => {
  setChannelRowLoading(row.ref, 'resync', true)
  try {
    const url = row.chatId && syncStatusMap.value.has(String(row.chatId)) ? `/sync/status/${row.chatId}/resync` : '/sync/history'
    const resp = await http.post(url)
    const data = parseApiData(resp)
    if (data?.accepted === false) {
      ElMessage.warning(data?.detail || '重新同步未提交，请先启动同步服务')
    } else {
      ElMessage.success(data?.detail || '重新同步已提交')
    }
    await loadSyncStatus()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '重新同步失败'))
  } finally {
    setChannelRowLoading(row.ref, 'resync', false)
  }
}

const resetChannel = async (row) => {
  if (!row?.chat_id) return

  setRowLoading(row.chat_id, 'reset', true)
  try {
    const resp = await http.post(`/sync/status/${row.chat_id}/reset`)
    const data = parseApiData(resp)
    ElMessage.success(data?.detail || '频道同步状态已重置')
    await loadSyncStatus()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.message || '频道重置失败')
  } finally {
    setRowLoading(row.chat_id, 'reset', false)
  }
}

const resyncChannel = async (row) => {
  if (!row?.chat_id) return

  setRowLoading(row.chat_id, 'resync', true)
  try {
    const resp = await http.post(`/sync/status/${row.chat_id}/resync`)
    const data = parseApiData(resp)
    if (data?.accepted === false) {
      ElMessage.warning(data?.detail || '重新同步未提交，请先启动同步服务')
    } else {
      ElMessage.success(data?.detail || '重新同步已提交')
    }
    await loadSyncStatus()
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.message || '重新同步失败')
  } finally {
    setRowLoading(row.chat_id, 'resync', false)
  }
}

onMounted(() => {
  loadAll()
  timerRef.value = window.setInterval(loadSyncStatus, 15000)
})

onUnmounted(() => {
  if (timerRef.value) {
    window.clearInterval(timerRef.value)
    timerRef.value = null
  }
})
</script>

<style scoped>
.metric-card {
  min-height: 98px;
}

.metric-label {
  color: var(--text-muted);
  font-size: 12px;
}

.metric-value {
  margin-top: 10px;
}

.metric-value.text {
  font-size: 24px;
  font-weight: 700;
  color: #111827;
}

.action-row {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.section-head {
  margin-bottom: 12px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.section-title {
  color: #0f172a;
  font-size: 22px;
  font-weight: 800;
  line-height: 1.2;
}

.section-desc {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}

.buttons,
.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.channel-add-row {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.channel-add-row .el-input {
  flex: 1;
  min-width: 240px;
}

.channel-table :deep(.el-button + .el-button) {
  margin-left: 4px;
}
</style>
