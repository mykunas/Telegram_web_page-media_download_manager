import axios from 'axios'

const DESKTOP_DEFAULT_API_BASE = 'http://127.0.0.1:18000/api'

function isDesktopRuntime() {
  if (typeof window === 'undefined') {
    return false
  }

  const ua = window.navigator?.userAgent || ''
  const hasElectronUA = ua.includes('Electron')
  const hasElectronProcess = Boolean(window.process?.versions?.electron)
  const hasDesktopFlag = Boolean(window.__APP_CONFIG__?.isDesktop)

  return hasElectronUA || hasElectronProcess || hasDesktopFlag
}

function resolveApiBase() {
  const fromWindow = window.__APP_CONFIG__?.apiBase
  if (typeof fromWindow === 'string' && fromWindow.trim()) {
    return fromWindow.trim()
  }

  const fromEnv = import.meta.env.VITE_API_BASE
  if (typeof fromEnv === 'string' && fromEnv.trim()) {
    return fromEnv.trim()
  }

  if (isDesktopRuntime()) {
    return DESKTOP_DEFAULT_API_BASE
  }

  return '/api'
}

const http = axios.create({
  baseURL: resolveApiBase(),
  timeout: 10000
})

// Intentionally memory-only. Never persist an admin token in browser storage.
let adminToken = ''

export function setAdminToken(value) {
  adminToken = typeof value === 'string' ? value.trim() : ''
}

http.interceptors.request.use((config) => {
  if (adminToken && !['get', 'head', 'options'].includes(String(config.method || 'get').toLowerCase())) {
    config.headers.Authorization = `Bearer ${adminToken}`
  }
  return config
})

export default http
