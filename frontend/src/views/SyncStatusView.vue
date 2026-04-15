<template>
  <div>
    <h1 class="page-title">同步状态</h1>
    <p class="page-desc">实时查看频道同步进度，并执行同步控制操作。</p>

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
        </div>
        <div class="meta">
          <el-tag type="info" effect="plain">最后动作：{{ formatAction(serviceState.last_action) }}</el-tag>
          <el-tag type="info" effect="plain">更新时间：{{ serviceState.last_action_at || '-' }}</el-tag>
          <el-button link type="primary" @click="loadSyncStatus">刷新</el-button>
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
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import http from '@/api/http'

const loading = ref(false)
const rows = ref([])
const timerRef = ref(null)

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
  recheck: false
})

const serviceRunning = computed(() => Boolean(serviceState.service_running))
const channelCount = computed(() => rows.value.length)

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
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

const triggerAction = async (action) => {
  const mapping = {
    start: '/sync/start',
    stop: '/sync/stop',
    history: '/sync/history',
    recheck: '/sync/recheck'
  }

  const url = mapping[action]
  if (!url) return

  actionLoading[action] = true
  try {
    const resp = await http.post(url)
    const data = parseApiData(resp)

    ElMessage.success(data?.detail || '操作已提交')
    await loadSyncStatus()
  } catch (error) {
    ElMessage.error(error?.message || '操作失败')
  } finally {
    actionLoading[action] = false
  }
}

onMounted(() => {
  loadSyncStatus()
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

.buttons,
.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
