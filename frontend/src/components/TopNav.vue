<template>
  <header class="top-nav">
    <div class="left-group">
      <el-button text class="menu-btn" @click="$emit('toggle-menu')">
        <el-icon><Expand /></el-icon>
      </el-button>
      <div>
        <h2 class="title">电报媒体下载管理系统</h2>
        <p class="subtitle">统一设计系统 · 更清晰的信息层级</p>
      </div>
    </div>
    <div class="right-group">
      <el-tag effect="plain" type="success" round>
        <span class="status-dot" /> 运行中
      </el-tag>
      <el-button text class="theme-btn" @click="toggleTheme">{{ isDark ? '浅色' : '深色' }}</el-button>
      <el-avatar size="small" class="avatar">A</el-avatar>
    </div>
  </header>
</template>

<script setup>
import { Expand } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'

defineEmits(['toggle-menu'])

const isDark = ref(false)

const applyTheme = (theme) => {
  const root = document.documentElement
  if (theme === 'dark') {
    root.dataset.theme = 'dark'
    isDark.value = true
  } else {
    root.dataset.theme = 'light'
    isDark.value = false
  }
}

const toggleTheme = () => {
  const next = isDark.value ? 'light' : 'dark'
  localStorage.setItem('tg_theme', next)
  applyTheme(next)
}

onMounted(() => {
  const saved = localStorage.getItem('tg_theme')
  if (saved === 'dark' || saved === 'light') {
    applyTheme(saved)
    return
  }
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
  applyTheme(prefersDark ? 'dark' : 'light')
})
</script>

<style scoped>
.top-nav {
  min-height: 62px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--ds-border);
  border-radius: var(--ds-radius-lg);
  background: color-mix(in srgb, var(--ds-surface) 86%, transparent);
  backdrop-filter: blur(10px);
  position: sticky;
  top: 0;
  z-index: 6;
}

.left-group {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.menu-btn {
  display: inline-flex;
  width: 36px;
  height: 36px;
  border-radius: 10px;
}

.title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--ds-text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.subtitle {
  margin: 2px 0 0;
  color: var(--ds-text-muted);
  font-size: 12px;
}

.right-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  display: inline-block;
  margin-right: 5px;
}

.theme-btn {
  color: var(--ds-text-secondary);
}

.avatar {
  background: linear-gradient(145deg, var(--ds-color-primary), var(--ds-color-accent));
  color: #fff;
  font-weight: 700;
}

@media (max-width: 900px) {
  .subtitle {
    display: none;
  }

  .theme-btn {
    padding: 0 8px;
  }
}
</style>
