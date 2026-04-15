<template>
  <div class="dashboard-redesign" v-loading="loading">
    <section class="top-bar panel-card">
      <div>
        <h1 class="title">仪表盘总览</h1>
        <p class="desc">查看同步状态、下载任务、系统资源与近期趋势</p>
      </div>
      <div class="top-actions">
        <el-tag :type="summary.service_status === 'running' ? 'success' : 'info'" effect="light" round>
          服务{{ summary.service_status === 'running' ? '运行中' : '空闲' }}
        </el-tag>
        <el-button @click="refreshAll">刷新数据</el-button>
        <el-button type="primary" @click="router.push('/settings')">配置同步</el-button>
      </div>
    </section>

    <section class="overview-grid">
      <article class="hero-card">
        <div class="hero-label">核心指标</div>
        <div class="hero-value">{{ formatNumber(summary.total_download_files) }}</div>
        <div class="hero-sub">今日累计下载量，系统整体运行稳定</div>
        <div class="hero-mini-row">
          <div class="hero-mini">
            <div>在线任务</div>
            <strong>{{ activeDownloads.downloading_count }}</strong>
          </div>
          <div class="hero-mini">
            <div>排队任务</div>
            <strong>{{ activeDownloads.waiting_count }}</strong>
          </div>
        </div>
      </article>

      <div class="overview-side">
        <div class="stats-grid">
          <article class="stat-tile" v-for="item in statTiles" :key="item.label">
            <div class="tile-label">{{ item.label }}</div>
            <div class="tile-value" :class="item.tone || ''">{{ item.value }}</div>
            <div class="tile-sub">{{ item.sub }}</div>
          </article>
        </div>

        <article class="progress-card">
          <template v-if="primaryDownloadTask">
            <div class="progress-top">
              <div class="progress-title">当前下载进度</div>
              <div class="progress-percent">{{ Number(primaryDownloadTask.progress_percent || 0).toFixed(1) }}%</div>
            </div>
            <div class="progress-file-row">
              <div class="progress-file" :title="primaryDownloadTask.file_name">{{ primaryDownloadTask.file_name || '-' }}</div>
              <el-button size="small" round @click="router.push('/downloads')">详情</el-button>
            </div>
            <div class="progress-track">
              <div class="progress-bar" :style="{ width: `${Number(primaryDownloadTask.progress_percent || 0)}%` }" />
            </div>
            <div class="progress-meta">
              <span>进度：{{ Number(primaryDownloadTask.progress_percent || 0).toFixed(2) }}%</span>
              <span>已下载：{{ formatBytes(primaryDownloadTask.current_bytes) }}</span>
              <span>总大小：{{ formatBytes(primaryDownloadTask.total_bytes) }}</span>
              <span>频道：{{ primaryDownloadTask.chat_name || '-' }}</span>
              <span>时间：{{ formatDateTime(primaryDownloadTask.updated_at || primaryDownloadTask.created_at) }}</span>
              <span>速度：{{ formatSpeed(primaryDownloadTask.speed_bytes_per_sec) }}</span>
            </div>
          </template>
          <template v-else>
            <div class="progress-empty">
              <div class="progress-title">当前下载进度</div>
              <div class="progress-empty-text">暂无下载任务</div>
              <div class="progress-track">
                <div class="progress-bar is-empty" style="width: 0%" />
              </div>
              <div class="progress-meta">
                <span>进度：0.00%</span>
                <span>已下载：0 B</span>
                <span>总大小：0 B</span>
                <span>频道：-</span>
                <span>时间：-</span>
                <span>速度：0 B/s</span>
              </div>
            </div>
          </template>
        </article>
      </div>
    </section>

    <section class="monitor-grid">
      <article class="panel-card">
        <div class="monitor-head">
          <div>
            <div class="section-title">下载速率</div>
            <div class="section-sub">当前下载速度、平均速率与峰值监控</div>
          </div>
          <div class="current-rate">
            <span>当前速度</span>
            <strong>{{ formatSpeed(activeDownloads.download_speed_bytes_per_sec) }}</strong>
          </div>
        </div>

        <div class="speed-bars">
          <div class="bar-col" v-for="(h, idx) in speedBarHeights" :key="idx">
            <div class="bar" :style="{ height: `${h}%` }" />
          </div>
        </div>

        <div class="mini-grid">
          <div class="mini-card">
            <div>峰值速率</div>
            <strong>{{ formatSpeed(peakDownloadSpeed) }}</strong>
          </div>
          <div class="mini-card">
            <div>平均速率</div>
            <strong>{{ formatSpeed(avgDownloadSpeed) }}</strong>
          </div>
          <div class="mini-card">
            <div>排队任务</div>
            <strong>{{ activeDownloads.waiting_count }}</strong>
          </div>
        </div>
      </article>

      <article class="panel-card">
        <div class="monitor-head">
          <div>
            <div class="section-title">CPU 与内存</div>
            <div class="section-sub">帮助快速判断系统资源是否接近瓶颈</div>
          </div>
          <el-tag type="success" round>系统状态稳定</el-tag>
        </div>

        <div class="usage-item">
          <div class="usage-row">
            <span>CPU 使用率</span>
            <strong>{{ Number(systemStats.cpu.usage_percent || 0).toFixed(1) }}%</strong>
          </div>
          <el-progress :percentage="Number(systemStats.cpu.usage_percent || 0)" :stroke-width="10" :show-text="false" />
        </div>

        <div class="usage-item">
          <div class="usage-row">
            <span>内存使用率</span>
            <strong>{{ Number(systemStats.memory.usage_percent || 0).toFixed(1) }}%</strong>
          </div>
          <el-progress
            :percentage="Number(systemStats.memory.usage_percent || 0)"
            :stroke-width="10"
            :show-text="false"
            color="#f59e0b"
          />
        </div>

        <div class="mini-grid">
          <div class="mini-card">
            <div>已用内存</div>
            <strong>{{ formatBytes(systemStats.memory.used_bytes) }}</strong>
          </div>
          <div class="mini-card">
            <div>可用内存</div>
            <strong>{{ formatBytes(systemStats.memory.available_bytes) }}</strong>
          </div>
          <div class="mini-card">
            <div>CPU 核心</div>
            <strong>{{ systemStats.cpu.cores_logical || 0 }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="chart-grid">
      <article class="panel-card">
        <div class="section-head chart-head">
          <div>
            <div class="section-title">最近 7 天下载趋势</div>
            <div class="section-sub">突出显示总量与成功量，方便观察峰值与波动</div>
          </div>
          <div class="ratio-badge">环比 {{ trendGrowth }}</div>
        </div>
        <div ref="trendChartRef" class="chart-box" />
      </article>

      <article class="panel-card">
        <div class="section-head chart-head">
          <div>
            <div class="section-title">频道下载统计（Top 8）</div>
            <div class="section-sub">按近期活跃度统计 Top 频道</div>
          </div>
        </div>
        <div ref="channelChartRef" class="chart-box" />
      </article>
    </section>
  </div>
</template>

<script setup>
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import http from '@/api/http'

const router = useRouter()
const loading = ref(false)

const summary = reactive({
  service_status: 'unknown',
  total_download_files: 0,
  total_failed: 0,
  total_skipped: 0,
  total_size_bytes: 0,
  configured_channel_count: 0,
  downloaded_last_24h: 0
})

const activeDownloads = reactive({
  downloading_count: 0,
  waiting_count: 0,
  download_speed_bytes_per_sec: 0,
  downloaded_bytes_active: 0,
  download_total_bytes_active: 0,
  items: []
})

const systemStats = reactive({
  cpu: { usage_percent: 0, cores_logical: 0, load_avg_1m: 0, load_avg_5m: 0, load_avg_15m: 0 },
  memory: { total_bytes: 0, used_bytes: 0, available_bytes: 0, usage_percent: 0, swap_total_bytes: 0, swap_used_bytes: 0 },
  network: { rx_bytes_per_sec: 0, tx_bytes_per_sec: 0, rx_total_bytes: 0, tx_total_bytes: 0 }
})

const monitorHistory = reactive({
  time: [],
  downloadKbps: []
})

const MAX_POINTS = 24
const trendRows = ref([])
const channelRows = ref([])

const trendChartRef = ref(null)
const channelChartRef = ref(null)
let trendChart = null
let channelChart = null
let dashboardTimer = null
let systemTimer = null
let activeTimer = null
let monitorTimer = null

const successCount = computed(() => Math.max(0, summary.total_download_files - summary.total_failed - summary.total_skipped))

const statTiles = computed(() => [
  { label: '成功数', value: formatNumber(successCount.value), sub: `成功率 ${summary.total_download_files ? ((successCount.value / summary.total_download_files) * 100).toFixed(1) : '0.0'}%`, tone: 'is-success' },
  { label: '失败数', value: formatNumber(summary.total_failed), sub: summary.total_failed > 0 ? '建议在下载记录里重试' : '无异常任务', tone: 'is-danger' },
  { label: '跳过数', value: formatNumber(summary.total_skipped), sub: '重复/过滤项目', tone: 'is-warning' },
  { label: '24h 新增', value: formatNumber(summary.downloaded_last_24h), sub: '等待新消息同步' },
  { label: '总文件体积', value: formatBytes(summary.total_size_bytes), sub: '当前媒体库存' }
])

const primaryDownloadTask = computed(() => {
  const list = Array.isArray(activeDownloads.items) ? activeDownloads.items : []
  return list.find((item) => item.status === 'downloading') || list[0] || null
})

const speedBarHeights = computed(() => {
  const points = monitorHistory.downloadKbps.slice(-12)
  if (!points.length) return Array.from({ length: 12 }, () => 2)
  const max = Math.max(...points, 1)
  return points.map((v) => Math.max(2, Math.round((v / max) * 100)))
})

const peakDownloadSpeed = computed(() => {
  if (!monitorHistory.downloadKbps.length) return 0
  return Math.max(...monitorHistory.downloadKbps) * 1024
})

const avgDownloadSpeed = computed(() => {
  if (!monitorHistory.downloadKbps.length) return 0
  const sum = monitorHistory.downloadKbps.reduce((acc, cur) => acc + cur, 0)
  return (sum / monitorHistory.downloadKbps.length) * 1024
})

const trendGrowth = computed(() => {
  if (trendRows.value.length < 2) return '--'
  const last = Number(trendRows.value.at(-1)?.total || 0)
  const prev = Number(trendRows.value.at(-2)?.total || 0)
  if (prev <= 0) return '+100%'
  const rate = ((last - prev) / prev) * 100
  const sign = rate >= 0 ? '+' : ''
  return `${sign}${rate.toFixed(1)}%`
})

const formatNumber = (value) => Number(value || 0).toLocaleString('zh-CN')

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

const formatSpeed = (bytesPerSec) => `${formatBytes(bytesPerSec)}/s`
const formatDateTime = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  const ss = String(date.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`
}

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}

const pushHistory = () => {
  monitorHistory.time.push(Date.now())
  monitorHistory.downloadKbps.push(Number(activeDownloads.download_speed_bytes_per_sec || 0) / 1024)
  if (monitorHistory.time.length > MAX_POINTS) {
    monitorHistory.time.shift()
    monitorHistory.downloadKbps.shift()
  }
}

const fetchSystemStats = async () => {
  try {
    const data = parseApiData(await http.get('/dashboard/system-stats')) || {}
    Object.assign(systemStats.cpu, data.cpu || {})
    Object.assign(systemStats.memory, data.memory || {})
    Object.assign(systemStats.network, data.network || {})
  } catch {
    // ignore background error
  }
}

const fetchActiveDownloads = async () => {
  try {
    const data = parseApiData(await http.get('/dashboard/active-downloads')) || {}
    activeDownloads.downloading_count = Number(data.downloading_count || 0)
    activeDownloads.waiting_count = Number(data.waiting_count || 0)
    activeDownloads.download_speed_bytes_per_sec = Number(data.download_speed_bytes_per_sec || 0)
    activeDownloads.downloaded_bytes_active = Number(data.downloaded_bytes_active || 0)
    activeDownloads.download_total_bytes_active = Number(data.download_total_bytes_active || 0)
    activeDownloads.items = Array.isArray(data.items) ? data.items : []
  } catch {
    // ignore background error
  }
}

const fetchDashboardData = async () => {
  loading.value = true
  try {
    const [summaryResp, trendResp, channelResp] = await Promise.all([
      http.get('/dashboard/summary'),
      http.get('/dashboard/trend'),
      http.get('/dashboard/channel-stats')
    ])

    const summaryData = parseApiData(summaryResp) || {}
    summary.service_status = summaryData.service_status || 'unknown'
    summary.total_download_files = Number(summaryData.total_download_files || 0)
    summary.total_failed = Number(summaryData.total_failed || 0)
    summary.total_skipped = Number(summaryData.total_skipped || 0)
    summary.total_size_bytes = Number(summaryData.total_size_bytes || 0)
    summary.configured_channel_count = Number(summaryData.configured_channel_count || 0)
    summary.downloaded_last_24h = Number(summaryData.downloaded_last_24h || 0)

    trendRows.value = Array.isArray(parseApiData(trendResp)) ? parseApiData(trendResp) : []
    channelRows.value = Array.isArray(parseApiData(channelResp)) ? parseApiData(channelResp) : []

    await nextTick()
    renderTrendChart()
    renderChannelChart()
  } catch (error) {
    ElMessage.error(error?.message || '加载仪表盘数据失败')
  } finally {
    loading.value = false
  }
}

const refreshAll = async () => {
  await Promise.all([fetchDashboardData(), fetchSystemStats(), fetchActiveDownloads()])
  pushHistory()
}

const retryRecord = async (id) => {
  if (!id) return
  try {
    await ElMessageBox.confirm('确认重试该任务？', '重试确认', { type: 'warning' })
    const resp = await http.post(`/downloads/${id}/retry`)
    parseApiData(resp)
    ElMessage.success('已加入重试队列')
    await fetchActiveDownloads()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(error?.message || '重试失败')
  }
}

const statusText = (status) => {
  if (status === 'downloading') return '下载中'
  if (status === 'success') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'waiting') return '排队中'
  return status || '-'
}

const statusTagType = (status) => {
  if (status === 'downloading') return 'warning'
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
}

const renderTrendChart = () => {
  if (!trendChartRef.value) return
  if (!trendChart) trendChart = echarts.init(trendChartRef.value)

  const days = trendRows.value.map((item) => item.day)
  trendChart.setOption({
    color: ['#111827', '#10b981', '#ef4444', '#f59e0b'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 12, right: 12, top: 38, bottom: 12, containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: days },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '总量', type: 'line', smooth: true, data: trendRows.value.map((item) => item.total || 0) },
      { name: '成功', type: 'line', smooth: true, data: trendRows.value.map((item) => item.success || 0) },
      { name: '失败', type: 'line', smooth: true, data: trendRows.value.map((item) => item.failed || 0) },
      { name: '跳过', type: 'line', smooth: true, data: trendRows.value.map((item) => item.skipped || 0) }
    ]
  })
}

const renderChannelChart = () => {
  if (!channelChartRef.value) return
  if (!channelChart) channelChart = echarts.init(channelChartRef.value)

  const topRows = [...channelRows.value].sort((a, b) => (b.total || 0) - (a.total || 0)).slice(0, 8)
  const labels = topRows.map((item) => item.chat_name || String(item.chat_id))
  const totals = topRows.map((item) => item.total || 0)

  channelChart.setOption({
    color: ['#06b6d4'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 12, top: 8, bottom: 12, containLabel: true },
    xAxis: { type: 'value', minInterval: 1 },
    yAxis: { type: 'category', data: labels, axisLabel: { width: 120, overflow: 'truncate' } },
    series: [{ name: '下载总量', type: 'bar', data: totals, barMaxWidth: 18, label: { show: true, position: 'right' } }]
  })
}

const handleResize = () => {
  trendChart?.resize()
  channelChart?.resize()
}

onMounted(async () => {
  await refreshAll()
  dashboardTimer = window.setInterval(fetchDashboardData, 15000)
  systemTimer = window.setInterval(fetchSystemStats, 3000)
  activeTimer = window.setInterval(fetchActiveDownloads, 3000)
  monitorTimer = window.setInterval(pushHistory, 3000)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (dashboardTimer) window.clearInterval(dashboardTimer)
  if (systemTimer) window.clearInterval(systemTimer)
  if (activeTimer) window.clearInterval(activeTimer)
  if (monitorTimer) window.clearInterval(monitorTimer)

  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  channelChart?.dispose()
  trendChart = null
  channelChart = null
})
</script>

<style scoped>
.dashboard-redesign {
  display: grid;
  gap: 14px;
}

.panel-card {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 24px;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.desc {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.overview-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 14px;
  align-items: stretch;
}

.hero-card {
  border-radius: 24px;
  padding: 20px;
  color: #fff;
  background: linear-gradient(135deg, #0f172a 0%, #111827 48%, #164e63 100%);
  min-height: 312px;
}

.overview-side {
  min-height: 312px;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: 10px;
}

.hero-label {
  font-size: 13px;
  color: rgba(207, 250, 254, 0.9);
}

.hero-value {
  margin-top: 8px;
  font-size: 42px;
  font-weight: 700;
  line-height: 1;
}

.hero-sub {
  margin-top: 10px;
  color: rgba(226, 232, 240, 0.92);
  font-size: 13px;
}

.hero-mini-row {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.hero-mini {
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  padding: 10px 12px;
  font-size: 12px;
}

.hero-mini strong {
  display: block;
  margin-top: 4px;
  font-size: 21px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.progress-card {
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 14px;
  background: #fff;
  min-height: 170px;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.progress-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.progress-title {
  color: #334155;
  font-size: 13px;
  font-weight: 600;
}

.progress-percent {
  color: #0284c7;
  font-size: 16px;
  font-weight: 700;
}

.progress-file {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-file-row {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress-file-row .progress-file {
  flex: 1;
  min-width: 0;
}

.progress-track {
  margin-top: 10px;
  height: 12px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
}

.progress-bar.is-empty {
  background: #cbd5e1;
}

.progress-meta {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px 12px;
  font-size: 12px;
  color: #64748b;
}

.progress-empty {
  min-height: 142px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.progress-empty-text {
  margin-top: 8px;
  color: #94a3b8;
  font-size: 14px;
}

.stat-tile {
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 14px;
  background: #fff;
  min-height: 170px;
}

.tile-label {
  color: #64748b;
  font-size: 13px;
}

.tile-value {
  margin-top: 9px;
  font-size: 28px;
  line-height: 1.1;
  font-weight: 700;
  color: #0f172a;
}

.tile-value.is-success {
  color: #059669;
}

.tile-value.is-danger {
  color: #e11d48;
}

.tile-value.is-warning {
  color: #d97706;
}

.tile-sub {
  margin-top: 8px;
  color: #94a3b8;
  font-size: 12px;
}

.active-section {
  border-radius: 24px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.section-sub {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}

.task-list {
  display: grid;
  gap: 10px;
  max-height: 460px;
  overflow: auto;
  padding-right: 2px;
}

.task-item {
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  padding: 12px;
  background: #fff;
}

.task-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.task-type {
  margin-left: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.task-speed {
  color: #0284c7;
  font-size: 13px;
}

.task-name {
  margin-top: 10px;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-wrap {
  margin-top: 10px;
  background: #f1f5f9;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
}

.progress-inner {
  height: 100%;
  border-radius: 999px;
  background: #0f172a;
}

.task-meta {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  font-size: 12px;
  color: #64748b;
}

.task-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.monitor-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.monitor-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.current-rate {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 14px;
  padding: 8px 10px;
  text-align: right;
  font-size: 12px;
  color: #64748b;
}

.current-rate strong {
  display: block;
  margin-top: 3px;
  color: #111827;
  font-size: 13px;
}

.speed-bars {
  margin-top: 14px;
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 170px;
  padding: 8px;
  border-radius: 16px;
  background: #f8fafc;
}

.bar-col {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: flex-end;
}

.bar {
  width: 100%;
  border-radius: 8px 8px 0 0;
  background: linear-gradient(180deg, #111827 0%, #334155 100%);
}

.usage-item {
  margin-top: 14px;
}

.usage-row {
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  color: #475569;
  font-size: 13px;
}

.mini-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.mini-card {
  border-radius: 14px;
  padding: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  color: #64748b;
}

.mini-card strong {
  display: block;
  margin-top: 4px;
  font-size: 15px;
  color: #111827;
}

.chart-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 14px;
}

.chart-head {
  margin-bottom: 8px;
}

.ratio-badge {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 6px 10px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 12px;
}

.chart-box {
  height: 320px;
}

@media (max-width: 1460px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .overview-side {
    min-height: auto;
  }

  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 920px) {
  .title {
    font-size: 22px;
  }

  .top-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .monitor-grid {
    grid-template-columns: 1fr;
  }

  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .progress-meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .mini-grid {
    grid-template-columns: 1fr;
  }

  .chart-box {
    height: 260px;
  }
}

@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .progress-meta {
    grid-template-columns: 1fr;
  }
}
</style>
