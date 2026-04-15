<template>
  <div>
    <div class="head">
      <div>
        <h1 class="page-title">私人年鉴</h1>
        <p class="page-desc">自动生成你的周报/月报回顾，聚焦下载与观看习惯。</p>
      </div>
      <div class="head-actions">
        <el-radio-group v-model="period" size="small" @change="fetchRecap">
          <el-radio-button label="weekly">周报</el-radio-button>
          <el-radio-button label="monthly">月报</el-radio-button>
        </el-radio-group>
        <el-button size="small" :loading="loading" @click="fetchRecap">刷新</el-button>
        <el-button size="small" @click="exportImage">导出图片</el-button>
      </div>
    </div>

    <el-card class="page-card" shadow="never" style="margin-top: 14px" v-loading="loading">
      <div class="summary-grid">
        <div class="summary-item">
          <div class="label">新增文件数</div>
          <div class="value">{{ recap.new_files_count }}</div>
        </div>
        <div class="summary-item">
          <div class="label">新增体积</div>
          <div class="value">{{ formatBytes(recap.new_files_size_bytes) }}</div>
        </div>
        <div class="summary-item">
          <div class="label">总播放时长</div>
          <div class="value">{{ formatDuration(recap.total_play_seconds) }}</div>
        </div>
        <div class="summary-item">
          <div class="label">最常看频道</div>
          <div class="value ellipsis" :title="recap.most_watched_channel">{{ recap.most_watched_channel || '-' }}</div>
        </div>
      </div>

      <div class="trend-wrap">
        <div class="trend-head">
          <div class="trend-title">完播率趋势</div>
          <el-tag size="small" type="success">整体 {{ Number(recap.completion_rate || 0).toFixed(1) }}%</el-tag>
        </div>

        <div v-if="!trend.length" class="empty-tip">暂无趋势数据</div>

        <div v-else class="trend-grid">
          <svg class="line-chart" viewBox="0 0 100 40" preserveAspectRatio="none">
            <polyline :points="linePoints" fill="none" stroke="#2563eb" stroke-width="1.8" />
            <polyline :points="areaPoints" fill="rgba(37, 99, 235, 0.12)" stroke="none" />
          </svg>
          <div class="bars">
            <div v-for="item in trend" :key="item.label" class="bar-row">
              <div class="bar-label">{{ item.label }}</div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${Math.max(0, Math.min(100, Number(item.completion_rate || 0)))}%` }" />
              </div>
              <div class="bar-value">{{ Number(item.completion_rate || 0).toFixed(1) }}%</div>
            </div>
          </div>
        </div>
      </div>

      <div class="insight">
        <div class="insight-title">摘要</div>
        <p>
          在 {{ periodLabel }}（{{ recap.start_date || '-' }} 至 {{ recap.end_date || '-' }}），你新增 {{ recap.new_files_count }} 个文件，
          累计 {{ formatBytes(recap.new_files_size_bytes) }}；总播放时长 {{ formatDuration(recap.total_play_seconds) }}。
          最活跃频道为「{{ recap.most_watched_channel || '-' }}」，整体完播率 {{ Number(recap.completion_rate || 0).toFixed(1) }}%。
        </p>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'

const loading = ref(false)
const period = ref('weekly')
const recap = ref({
  period: 'weekly',
  start_date: '',
  end_date: '',
  new_files_count: 0,
  new_files_size_bytes: 0,
  total_play_seconds: 0,
  most_watched_channel: '-',
  completion_rate: 0,
  completion_trend: []
})

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}
const apiErrorMessage = (error, fallback) => error?.response?.data?.message || error?.message || fallback

const trend = computed(() => (Array.isArray(recap.value.completion_trend) ? recap.value.completion_trend : []))
const periodLabel = computed(() => (period.value === 'weekly' ? '本周' : '本月'))

const linePoints = computed(() => {
  const arr = trend.value
  if (!arr.length) return ''
  return arr
    .map((item, idx) => {
      const x = (idx / Math.max(arr.length - 1, 1)) * 100
      const y = 36 - (Math.max(0, Math.min(100, Number(item.completion_rate || 0))) / 100) * 30
      return `${x},${y}`
    })
    .join(' ')
})

const areaPoints = computed(() => {
  const pts = linePoints.value
  if (!pts) return ''
  return `0,36 ${pts} 100,36`
})

const formatBytes = (bytes) => {
  const b = Number(bytes || 0)
  if (b <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = b
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`
}

const formatDuration = (seconds) => {
  const total = Math.max(0, Math.floor(Number(seconds || 0)))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  if (h > 0) return `${h}小时${m}分钟`
  return `${m}分钟`
}

const fetchRecap = async () => {
  loading.value = true
  try {
    const data = parseApiData(await http.get('/personal/recap', { params: { period: period.value } })) || {}
    recap.value = {
      period: data.period || period.value,
      start_date: data.start_date || '',
      end_date: data.end_date || '',
      new_files_count: Number(data.new_files_count || 0),
      new_files_size_bytes: Number(data.new_files_size_bytes || 0),
      total_play_seconds: Number(data.total_play_seconds || 0),
      most_watched_channel: data.most_watched_channel || '-',
      completion_rate: Number(data.completion_rate || 0),
      completion_trend: Array.isArray(data.completion_trend) ? data.completion_trend : []
    }
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加载年鉴失败'))
  } finally {
    loading.value = false
  }
}

const exportImage = () => {
  try {
    const width = 1200
    const height = 680
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('canvas not supported')

    ctx.fillStyle = '#f5f7fb'
    ctx.fillRect(0, 0, width, height)
    ctx.fillStyle = '#111827'
    ctx.font = 'bold 34px sans-serif'
    ctx.fillText(`私人年鉴 - ${period.value === 'weekly' ? '周报' : '月报'}`, 48, 72)

    ctx.fillStyle = '#334155'
    ctx.font = '22px sans-serif'
    ctx.fillText(`新增文件：${recap.value.new_files_count} | 新增体积：${formatBytes(recap.value.new_files_size_bytes)}`, 48, 130)
    ctx.fillText(`播放时长：${formatDuration(recap.value.total_play_seconds)} | 完播率：${recap.value.completion_rate.toFixed(1)}%`, 48, 170)
    ctx.fillText(`最常看频道：${recap.value.most_watched_channel || '-'}`, 48, 210)

    const trendTop = 270
    const trendLeft = 48
    const trendWidth = 1100
    const trendHeight = 300
    ctx.strokeStyle = '#dbe3f0'
    ctx.strokeRect(trendLeft, trendTop, trendWidth, trendHeight)

    const items = trend.value
    if (items.length > 0) {
      ctx.beginPath()
      ctx.strokeStyle = '#2563eb'
      ctx.lineWidth = 3
      items.forEach((item, idx) => {
        const x = trendLeft + (idx / Math.max(items.length - 1, 1)) * trendWidth
        const y = trendTop + trendHeight - (Math.max(0, Math.min(100, Number(item.completion_rate || 0))) / 100) * trendHeight
        if (idx === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      ctx.stroke()
    }

    const a = document.createElement('a')
    a.href = canvas.toDataURL('image/png')
    a.download = `recap_${period.value}_${new Date().toISOString().slice(0, 10)}.png`
    a.click()
    ElMessage.success('图片已导出')
  } catch {
    ElMessage.error('导出失败')
  }
}

fetchRecap()
</script>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.head-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.summary-item {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 12px;
}

.label {
  color: #64748b;
  font-size: 12px;
}

.value {
  margin-top: 6px;
  color: #0f172a;
  font-size: 22px;
  font-weight: 700;
}

.ellipsis {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trend-wrap {
  margin-top: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
}

.trend-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.trend-title {
  color: #111827;
  font-weight: 600;
}

.trend-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 10px;
}

.line-chart {
  width: 100%;
  height: 170px;
  background: linear-gradient(180deg, #f8fbff, #ffffff);
  border: 1px solid #dbeafe;
  border-radius: 10px;
}

.bars {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bar-row {
  display: grid;
  grid-template-columns: 90px 1fr 52px;
  align-items: center;
  gap: 8px;
}

.bar-label {
  color: #475569;
  font-size: 12px;
}

.bar-track {
  height: 8px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2563eb, #3b82f6);
}

.bar-value {
  color: #334155;
  font-size: 12px;
  text-align: right;
}

.insight {
  margin-top: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 12px;
}

.insight-title {
  font-weight: 600;
  color: #0f172a;
}

.insight p {
  margin: 8px 0 0;
  color: #334155;
  line-height: 1.6;
}

.empty-tip {
  color: #94a3b8;
  font-size: 13px;
  margin-top: 8px;
}

@media (max-width: 1080px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .trend-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .head {
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
