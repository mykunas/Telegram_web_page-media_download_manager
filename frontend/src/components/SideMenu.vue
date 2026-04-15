<template>
  <el-menu
    :default-active="activePath"
    class="side-menu"
    router
    :collapse="collapsed"
    background-color="transparent"
    text-color="var(--ds-text-secondary)"
    active-text-color="var(--ds-text-main)"
  >
    <el-menu-item-group title="数据总览">
      <el-menu-item index="/dashboard">仪表盘</el-menu-item>
      <el-menu-item index="/downloads">下载记录</el-menu-item>
      <el-menu-item index="/recommendations">今日推荐</el-menu-item>
      <el-menu-item index="/recap">私人年度</el-menu-item>
    </el-menu-item-group>

    <el-menu-item-group title="内容管理">
      <el-menu-item index="/files">文件管理</el-menu-item>
      <el-menu-item index="/collections">我的收藏</el-menu-item>
    </el-menu-item-group>

    <el-menu-item-group title="系统日志">
      <el-menu-item index="/download-logs">下载日志</el-menu-item>
      <el-menu-item index="/error-logs">错误日志</el-menu-item>
    </el-menu-item-group>

    <el-menu-item-group title="系统设置">
      <el-menu-item index="/settings">电报配置</el-menu-item>
      <el-menu-item index="/sync-status">同步状态</el-menu-item>
      <el-menu-item index="/design-system">设计系统</el-menu-item>
    </el-menu-item-group>
  </el-menu>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

defineProps({
  collapsed: {
    type: Boolean,
    default: false
  }
})

const route = useRoute()
const activePath = computed(() => route.path)
</script>

<style scoped>
.side-menu {
  border-right: none;
  padding: 10px;
  background: transparent;
}

.side-menu :deep(.el-menu-item-group__title) {
  padding: 14px 10px 6px !important;
  color: var(--ds-text-muted);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.35px;
  text-transform: uppercase;
}

.side-menu :deep(.el-menu-item) {
  height: 40px;
  line-height: 40px;
  margin: 4px 0;
  border-radius: var(--ds-radius-md);
  font-size: 14px;
  font-weight: 600;
  color: var(--ds-text-secondary);
  padding: 0 12px !important;
  transition: background-color var(--ds-motion-fast), color var(--ds-motion-fast), transform var(--ds-motion-fast);
}

.side-menu :deep(.el-menu-item.is-active) {
  color: var(--ds-text-main) !important;
  background: color-mix(in srgb, var(--ds-color-primary) 12%, transparent) !important;
}

.side-menu :deep(.el-menu-item:hover) {
  background: color-mix(in srgb, var(--ds-color-primary) 8%, transparent) !important;
  transform: translateX(2px);
}

.side-menu :deep(.el-menu--collapse .el-menu-item-group__title) {
  display: none;
}

.side-menu :deep(.el-menu--collapse .el-menu-item) {
  justify-content: center;
  padding: 0 !important;
  font-size: 12px;
}
</style>
