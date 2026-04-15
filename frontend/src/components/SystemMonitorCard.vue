<template>
  <el-card class="monitor-card" shadow="never">
    <template #header>
      <div class="monitor-title">{{ title }}</div>
    </template>

    <div ref="chartRef" class="monitor-chart" />

    <div class="detail-grid">
      <div v-for="item in details" :key="item.label" class="detail-item">
        <el-tag size="small" effect="plain" :type="item.tagType || 'info'">{{ item.label }}</el-tag>
        <span class="detail-value">{{ item.value }}</span>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import * as echarts from 'echarts'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  xData: { type: Array, default: () => [] },
  series: { type: Array, default: () => [] },
  details: { type: Array, default: () => [] },
  yAxisSuffix: { type: String, default: '' }
})

const chartRef = ref(null)
let chart = null

const chartSeries = computed(() =>
  props.series.map((item) => ({
    name: item.name,
    type: 'line',
    smooth: true,
    showSymbol: false,
    data: Array.isArray(item.data) ? item.data : [],
    lineStyle: {
      width: 2,
      color: item.color
    },
    areaStyle: {
      opacity: 0.18,
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: item.color },
        { offset: 1, color: 'rgba(255,255,255,0.03)' }
      ])
    },
    animationDuration: 500
  }))
)

const renderChart = () => {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)

  chart.setOption(
    {
      color: props.series.map((item) => item.color),
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'line' }
      },
      legend: {
        top: 0,
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
        textStyle: { color: '#4b5563', fontSize: 12 }
      },
      grid: {
        left: 8,
        right: 8,
        top: 30,
        bottom: 4,
        containLabel: true
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: props.xData,
        axisLine: { lineStyle: { color: '#d1d5db' } },
        axisLabel: { color: '#9ca3af', fontSize: 11 }
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#eef2f7' } },
        axisLabel: {
          color: '#9ca3af',
          formatter: (value) => `${value}${props.yAxisSuffix}`
        }
      },
      series: chartSeries.value
    },
    true
  )
}

const handleResize = () => chart?.resize()

watch(
  () => [props.xData, props.series],
  () => renderChart(),
  { deep: true }
)

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.monitor-card {
  height: 420px;
  border-radius: 16px;
  border: 1px solid #edf1f7;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
}

:deep(.monitor-card .el-card__body) {
  height: calc(100% - 56px);
  display: flex;
  flex-direction: column;
}

.monitor-title {
  font-weight: 600;
  color: #1f2937;
}

.monitor-chart {
  width: 100%;
  height: 210px;
  flex-shrink: 0;
}

.detail-grid {
  margin-top: 10px;
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 16px;
  align-content: start;
  overflow: auto;
}

.detail-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: #f7f9fd;
}

.detail-value {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

@media (max-width: 768px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
