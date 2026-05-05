import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/layouts/AdminLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'downloads', name: 'Downloads', component: () => import('@/views/DownloadsView.vue') },
      { path: 'recommendations', name: 'Recommendations', component: () => import('@/views/RecommendationsView.vue') },
      { path: 'recap', name: 'Recap', component: () => import('@/views/RecapView.vue') },
      { path: 'files', name: 'Files', component: () => import('@/views/FilesView.vue') },
      { path: 'collections', name: 'Collections', component: () => import('@/views/CollectionsView.vue') },
      { path: 'collections/:id/player', name: 'PlaylistPlayer', component: () => import('@/views/PlaylistPlayerPage.vue') },
      { path: 'download-logs', name: 'DownloadLogs', component: () => import('@/views/DownloadLogsView.vue') },
      { path: 'error-logs', name: 'ErrorLogs', component: () => import('@/views/ErrorLogsView.vue') },
      { path: 'settings', name: 'Settings', component: () => import('@/views/SettingsView.vue') },
      { path: 'sync-status', name: 'SyncStatus', component: () => import('@/views/SyncStatusView.vue') },
      { path: 'design-system', name: 'DesignSystem', component: () => import('@/views/DesignSystemView.vue') }
    ]
  }
]

function isDesktopRuntime() {
  if (typeof window === 'undefined') {
    return false
  }

  const hasElectronProcess = Boolean(window.process?.versions?.electron)
  const hasElectronUA = (window.navigator?.userAgent || '').includes('Electron')
  const isFileProtocol = window.location?.protocol === 'file:'
  return hasElectronProcess || hasElectronUA || isFileProtocol
}

const router = createRouter({
  history: isDesktopRuntime() ? createWebHashHistory() : createWebHistory(),
  routes
})

export default router
