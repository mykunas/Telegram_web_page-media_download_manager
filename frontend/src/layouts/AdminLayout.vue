<template>
  <div class="admin-layout">
    <aside class="sidebar" :class="{ collapsed: isDesktopCollapsed, mobile: isMobile }">
      <div class="brand-wrap">
        <div class="brand-mark">TG</div>
        <div v-if="!isDesktopCollapsed" class="brand-meta">
          <div class="brand">电报管理</div>
          <div class="brand-sub">Telegram Media Admin</div>
        </div>
      </div>
      <SideMenu :collapsed="isDesktopCollapsed" />
    </aside>

    <main class="main-panel">
      <TopNav @toggle-menu="handleToggleMenu" />
      <section class="content-area">
        <router-view />
      </section>
    </main>

    <el-drawer v-model="mobileMenuVisible" direction="ltr" size="272px" :with-header="false" class="mobile-drawer">
      <div class="brand-wrap mobile-brand-wrap">
        <div class="brand-mark">TG</div>
        <div class="brand-meta">
          <div class="brand">电报管理</div>
          <div class="brand-sub">Telegram Media Admin</div>
        </div>
      </div>
      <SideMenu :collapsed="false" @click="mobileMenuVisible = false" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

import SideMenu from '@/components/SideMenu.vue'
import TopNav from '@/components/TopNav.vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const mobileMenuVisible = ref(false)
const isMobile = ref(false)

const onResize = () => {
  isMobile.value = window.innerWidth <= 960
}

const handleToggleMenu = () => {
  if (isMobile.value) {
    mobileMenuVisible.value = true
    return
  }
  appStore.toggleSidebar()
}

onMounted(() => {
  onResize()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
})

const isDesktopCollapsed = computed(() => !isMobile.value && appStore.sidebarCollapsed)
</script>

<style scoped>
.admin-layout {
  width: 100%;
  height: 100%;
  display: flex;
  gap: 10px;
  overflow: hidden;
  padding: 10px;
}

.sidebar {
  width: 260px;
  min-width: 260px;
  background: var(--ds-bg-elevated);
  border: 1px solid var(--ds-border);
  border-radius: var(--ds-radius-lg);
  box-shadow: var(--ds-shadow-soft);
  transition: width var(--ds-motion-base), min-width var(--ds-motion-base);
  overflow: hidden;
}

.sidebar.collapsed {
  width: 88px;
  min-width: 88px;
}

.sidebar.mobile {
  display: none;
}

.brand-wrap,
.mobile-brand-wrap {
  min-height: 72px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--ds-border);
}

.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(145deg, var(--ds-color-primary), var(--ds-color-accent));
}

.brand-meta {
  min-width: 0;
}

.brand {
  color: var(--ds-text-main);
  font-weight: 700;
  font-size: 16px;
  white-space: nowrap;
}

.brand-sub {
  color: var(--ds-text-muted);
  font-size: 11px;
  line-height: 1.2;
}

.main-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-radius: var(--ds-radius-lg);
  background: transparent;
}

.content-area {
  flex: 1;
  overflow: auto;
  padding: 14px;
}

:deep(.mobile-drawer .el-drawer) {
  background: var(--ds-bg-elevated);
}

@media (max-width: 960px) {
  .admin-layout {
    gap: 0;
    padding: 0;
  }

  .sidebar {
    display: none;
  }

  .content-area {
    padding: 12px;
  }
}
</style>
