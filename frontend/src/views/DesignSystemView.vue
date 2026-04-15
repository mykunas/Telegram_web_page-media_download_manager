<template>
  <div class="ds-page">
    <AppCard title="Design System" description="统一颜色、间距、字体层级与交互动效，作为全局样式基线。">
      <template #actions>
        <div class="ds-actions">
          <AppButton variant="ghost">次要按钮</AppButton>
          <AppButton variant="primary">主按钮</AppButton>
        </div>
      </template>
      <div class="swatch-grid">
        <div v-for="item in swatches" :key="item.name" class="swatch-item">
          <div class="swatch-color" :style="{ background: item.color }" />
          <div class="swatch-name">{{ item.name }}</div>
          <div class="swatch-value">{{ item.color }}</div>
        </div>
      </div>
    </AppCard>

    <div class="sample-grid">
      <AppCard title="列表示例" description="用于日志、任务、状态等高频信息。">
        <AppList :items="listItems" />
      </AppCard>

      <AppCard title="空状态与加载" description="避免留白，提供明确状态反馈。">
        <el-skeleton :rows="3" animated />
        <el-empty description="暂无可展示内容" />
      </AppCard>
    </div>
  </div>
</template>

<script setup>
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import AppList from '@/components/ui/AppList.vue'

const swatches = [
  { name: 'Primary', color: 'var(--ds-color-primary)' },
  { name: 'Accent', color: 'var(--ds-color-accent)' },
  { name: 'Surface', color: 'var(--ds-surface)' },
  { name: 'Muted Surface', color: 'var(--ds-surface-muted)' },
  { name: 'Text Main', color: 'var(--ds-text-main)' },
  { name: 'Text Muted', color: 'var(--ds-text-muted)' }
]

const listItems = [
  { key: 'sync', label: '同步服务', meta: '最近更新时间 1 分钟前', value: '运行中' },
  { key: 'task', label: '下载任务', meta: '队列总数 24', value: '6 活跃 / 18 等待' },
  { key: 'storage', label: '存储使用率', meta: '下载目录 /downloads', value: '62%' }
]
</script>

<style scoped>
.swatch-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}

.swatch-item {
  border: 1px solid var(--ds-border);
  border-radius: var(--ds-radius-md);
  padding: 10px;
  background: var(--ds-surface-muted);
}

.swatch-color {
  height: 48px;
  border-radius: 9px;
  border: 1px solid var(--ds-border-strong);
}

.swatch-name {
  margin-top: 8px;
  font-weight: 600;
}

.swatch-value {
  margin-top: 2px;
  color: var(--ds-text-muted);
  font-size: var(--ds-font-meta);
}

.sample-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 900px) {
  .sample-grid {
    grid-template-columns: 1fr;
  }
}
</style>
