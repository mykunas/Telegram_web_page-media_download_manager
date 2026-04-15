<template>
  <div class="settings-page">
    <el-card class="section-card header-card" shadow="never">
      <div class="header-main">
        <div>
          <h1 class="page-title">电报授权配置</h1>
          <p class="page-desc">把授权、下载参数、偏好画像和会话状态分区展示，减少页面横向拥挤和表单压缩问题。</p>
        </div>
        <div class="header-actions">
          <el-button round :loading="statusChecking" @click="checkAuthStatus">检查授权</el-button>
          <el-button round :loading="loading" @click="loadAll">刷新状态</el-button>
          <el-button round type="primary" :loading="savingAll" @click="saveAllConfigs">保存全部配置</el-button>
        </div>
      </div>
    </el-card>

    <div class="summary-grid">
      <el-card class="section-card summary-card" shadow="never">
        <div class="summary-label">授权状态</div>
        <div class="summary-value">{{ authStatusText }}</div>
        <div class="summary-badge summary-badge-green">{{ authStatusSub }}</div>
      </el-card>
      <el-card class="section-card summary-card" shadow="never">
        <div class="summary-label">目标频道</div>
        <div class="summary-value">{{ targetChatCount }}</div>
        <div class="summary-badge summary-badge-cyan">已配置同步源</div>
      </el-card>
      <el-card class="section-card summary-card" shadow="never">
        <div class="summary-label">推荐标签</div>
        <div class="summary-value">{{ preferenceState.tag_weights.length }}</div>
        <div class="summary-badge summary-badge-orange">偏好画像已生成</div>
      </el-card>
      <el-card class="section-card summary-card" shadow="never">
        <div class="summary-label">下载目录</div>
        <div class="summary-value summary-path">{{ downloadForm.DOWNLOAD_DIR || '/downloads' }}</div>
        <div class="summary-badge">当前存储位置</div>
      </el-card>
    </div>

    <div class="content-grid">
      <section class="left-col">
        <el-card class="section-card" shadow="never">
          <div class="block-head">
            <div>
              <div class="block-title">授权配置</div>
              <div class="block-desc">把授权相关字段集中到一张卡片，验证码流程单独一行，避免请求按钮和输入框挤在一起。</div>
            </div>
            <el-tag :type="sessionStatus.authorized ? 'success' : 'info'" effect="plain">{{ sessionStatus.authorized ? '当前已授权' : '当前未授权' }}</el-tag>
          </div>

          <el-form label-position="top" class="form-grid">
            <el-form-item label="接口 ID (API_ID)">
              <el-input v-model.trim="telegramForm.API_ID" placeholder="请输入 API_ID" />
            </el-form-item>
            <el-form-item label="接口密钥 (API_HASH)">
              <el-input v-model.trim="telegramForm.API_HASH" placeholder="请输入 API_HASH" />
            </el-form-item>
            <el-form-item label="手机号 (PHONE_NUMBER)">
              <el-input v-model.trim="telegramForm.PHONE_NUMBER" placeholder="例如 +8613812345678" />
            </el-form-item>
            <el-form-item label="会话名 (SESSION_NAME)">
              <el-input v-model.trim="telegramForm.SESSION_NAME" placeholder="例如 /app/session/telegram_user" />
            </el-form-item>
          </el-form>

          <div class="action-row">
            <el-button type="primary" :loading="authStarting" @click="saveAndStartAuth">保存并开始授权</el-button>
            <el-button :loading="statusChecking" @click="checkAuthStatus">检查授权状态</el-button>
            <el-button type="danger" plain :loading="disconnecting" @click="disconnectSession">断开会话</el-button>
          </div>

          <div class="verify-panel">
            <div class="verify-title">验证码流程</div>
            <div class="verify-row">
              <el-input v-model.trim="verifyCode" placeholder="请输入验证码" clearable />
              <el-button :loading="submittingCode" @click="submitCode">提交验证码</el-button>
              <el-input v-model.trim="twoFactorPassword" placeholder="请输入二步验证码" show-password clearable />
              <el-button :loading="submittingPassword" @click="submitPassword">提交二步验证码</el-button>
            </div>
          </div>
        </el-card>

        <el-card class="section-card" shadow="never">
          <div class="block-head">
            <div>
              <div class="block-title">下载参数配置</div>
              <div class="block-desc">路径、目标频道、扩展名和下载策略按两列展示，便于快速校对。</div>
            </div>
            <el-button round size="small" :loading="loading" @click="loadAll">刷新配置</el-button>
          </div>

          <el-form label-position="top" class="form-grid">
            <el-form-item label="下载目录 (DOWNLOAD_DIR)">
              <el-input v-model.trim="downloadForm.DOWNLOAD_DIR" placeholder="下载目录" />
            </el-form-item>
            <el-form-item label="目标频道 (TARGET_CHATS)">
              <el-input v-model.trim="downloadForm.TARGET_CHATS" placeholder="多个目标用逗号分隔" />
            </el-form-item>
            <el-form-item label="允许扩展名 (ALLOW_EXTS)">
              <el-input v-model.trim="downloadForm.ALLOW_EXTS" placeholder="例如 .mp4,.jpg" />
            </el-form-item>
            <el-form-item label="下载历史">
              <el-switch v-model="downloadForm.DOWNLOAD_HISTORY" />
            </el-form-item>
            <el-form-item label="历史上限 (HISTORY_LIMIT)">
              <el-input-number v-model="downloadForm.HISTORY_LIMIT" :min="0" :step="100" />
            </el-form-item>
            <el-form-item label="最大重试次数">
              <el-input-number v-model="downloadForm.MAX_RETRIES" :min="0" :step="1" />
            </el-form-item>
            <el-form-item label="重试间隔秒数">
              <el-input-number v-model="downloadForm.RETRY_DELAY" :min="0" :step="1" />
            </el-form-item>
            <el-form-item label="最大文件大小 MB">
              <el-input-number v-model="downloadForm.MAX_FILE_SIZE_MB" :min="0" :step="10" />
            </el-form-item>
          </el-form>

          <div class="action-row">
            <el-button type="primary" :loading="savingDownload" @click="saveDownload()">保存下载配置</el-button>
            <el-button @click="loadAll">恢复默认</el-button>
          </div>
        </el-card>
      </section>

      <section class="right-col">
        <el-card class="section-card preference-card" shadow="never">
          <div class="block-head">
            <div>
              <div class="block-title">推荐偏好画像</div>
              <div class="block-desc">原页面三块滑杆区过高，这里收敛为三列卡片，更适合大屏阅读。</div>
            </div>
            <div class="pref-actions">
              <el-button size="small" plain :loading="preferencesLoading" @click="loadPreferences">刷新</el-button>
              <el-button size="small" :loading="preferencesRefreshing" @click="refreshPreferences">重算</el-button>
              <el-button size="small" type="success" :loading="preferencesSaving" @click="saveManualPreferences">保存偏好</el-button>
            </div>
          </div>

          <div class="pref-meta-row">
            <span class="pref-meta">更新时间 {{ preferenceState.updated_at || '-' }}</span>
            <span class="stat-badge">频道 {{ preferenceState.channel_weights.length }}</span>
            <span class="stat-badge">类型 {{ preferenceState.media_type_weights.length }}</span>
            <span class="stat-badge">标签 {{ preferenceState.tag_weights.length }}</span>
          </div>

          <div class="pref-grid">
            <section class="pref-card-col">
              <h4 class="pref-col-title">频道偏好 Top 8</h4>
              <div class="pref-col-body">
                <div v-if="!topChannels.length" class="empty-tip">暂无数据</div>
                <div v-for="item in topChannels" :key="`ch_${item.key}`" class="pref-row">
                  <div class="pref-name" :title="item.key">{{ item.key }}</div>
                  <div class="pref-slider-wrap">
                    <el-slider v-model="manualAdjust.channel[item.key]" :min="-5" :max="5" :step="0.1" size="small" class="pref-slider" />
                  </div>
                  <div class="pref-value">
                    <el-input-number v-model="manualAdjust.channel[item.key]" :min="-5" :max="5" :step="0.1" :controls="false" size="small" class="pref-number" />
                  </div>
                </div>
              </div>
            </section>

            <section class="pref-card-col">
              <h4 class="pref-col-title">媒体类型偏好</h4>
              <div class="pref-col-body">
                <div v-if="!topMediaTypes.length" class="empty-tip">暂无数据</div>
                <div v-for="item in topMediaTypes" :key="`mt_${item.key}`" class="pref-row">
                  <div class="pref-name" :title="item.key">{{ item.key }}</div>
                  <div class="pref-slider-wrap">
                    <el-slider v-model="manualAdjust.media_type[item.key]" :min="-5" :max="5" :step="0.1" size="small" class="pref-slider" />
                  </div>
                  <div class="pref-value">
                    <el-input-number v-model="manualAdjust.media_type[item.key]" :min="-5" :max="5" :step="0.1" :controls="false" size="small" class="pref-number" />
                  </div>
                </div>
              </div>
            </section>

            <section class="pref-card-col">
              <h4 class="pref-col-title">标签偏好 Top 10</h4>
              <div class="pref-col-body">
                <div v-if="!topTags.length" class="empty-tip">暂无数据</div>
                <div v-for="item in topTags" :key="`tag_${item.key}`" class="pref-row">
                  <div class="pref-name" :title="item.key">{{ item.key }}</div>
                  <div class="pref-slider-wrap">
                    <el-slider v-model="manualAdjust.tag[item.key]" :min="-5" :max="5" :step="0.1" size="small" class="pref-slider" />
                  </div>
                  <div class="pref-value">
                    <el-input-number v-model="manualAdjust.tag[item.key]" :min="-5" :max="5" :step="0.1" :controls="false" size="small" class="pref-number" />
                  </div>
                </div>
              </div>
            </section>
          </div>
        </el-card>

        <el-card class="section-card" shadow="never">
          <div class="block-title" style="margin-bottom: 10px">当前会话状态</div>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="授权步骤">{{ sessionStatus.step || '-' }}</el-descriptions-item>
            <el-descriptions-item label="是否已授权">{{ sessionStatus.authorized ? '已授权' : '未授权' }}</el-descriptions-item>
            <el-descriptions-item label="手机号">{{ sessionStatus.phone_number || '-' }}</el-descriptions-item>
            <el-descriptions-item label="会话名">{{ sessionStatus.session_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="用户">{{ sessionStatus.user_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="用户 ID">{{ sessionStatus.user_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态说明" :span="2">{{ sessionStatus.message || '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import http from '@/api/http'

const loading = ref(false)
const authStarting = ref(false)
const submittingCode = ref(false)
const submittingPassword = ref(false)
const statusChecking = ref(false)
const disconnecting = ref(false)
const savingDownload = ref(false)
const savingAll = ref(false)
const preferencesLoading = ref(false)
const preferencesRefreshing = ref(false)
const preferencesSaving = ref(false)

const verifyCode = ref('')
const twoFactorPassword = ref('')

const telegramForm = reactive({
  API_ID: '',
  API_HASH: '',
  PHONE_NUMBER: '',
  SESSION_NAME: '/app/session/telegram_user'
})

const downloadForm = reactive({
  DOWNLOAD_DIR: '/downloads',
  TARGET_CHATS: '',
  ALLOW_EXTS: '.mp4,.mkv,.mov,.avi,.jpg,.jpeg,.png,.webp',
  DOWNLOAD_HISTORY: true,
  HISTORY_LIMIT: 2000,
  MAX_RETRIES: 3,
  RETRY_DELAY: 5,
  MAX_FILE_SIZE_MB: 0
})

const sessionStatus = reactive({
  step: 'idle',
  authorized: false,
  message: '未开始授权',
  phone_number: '',
  session_name: '',
  user_id: '',
  user_name: ''
})

const preferenceState = reactive({
  updated_at: '',
  channel_weights: [],
  media_type_weights: [],
  tag_weights: []
})

const manualAdjust = reactive({
  channel: {},
  media_type: {},
  tag: {}
})

const topChannels = computed(() => preferenceState.channel_weights.slice(0, 8))
const topMediaTypes = computed(() => preferenceState.media_type_weights.slice(0, 6))
const topTags = computed(() => preferenceState.tag_weights.slice(0, 10))
const targetChatCount = computed(() =>
  String(downloadForm.TARGET_CHATS || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean).length
)
const authStatusText = computed(() => (sessionStatus.authorized ? '运行中' : '未授权'))
const authStatusSub = computed(() => (sessionStatus.authorized ? '当前会话可用' : '当前会话不可用'))

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}

const apiErrorMessage = (error, fallback) => error?.response?.data?.message || error?.message || fallback

const assignTelegram = (data = {}) => {
  telegramForm.API_ID = data.API_ID || ''
  telegramForm.API_HASH = data.API_HASH || ''
  telegramForm.PHONE_NUMBER = data.PHONE_NUMBER || ''
  telegramForm.SESSION_NAME = data.SESSION_NAME || '/app/session/telegram_user'
}

const assignDownload = (data = {}) => {
  downloadForm.DOWNLOAD_DIR = data.DOWNLOAD_DIR || '/downloads'
  downloadForm.TARGET_CHATS = data.TARGET_CHATS || ''
  downloadForm.ALLOW_EXTS = data.ALLOW_EXTS || ''
  downloadForm.DOWNLOAD_HISTORY = Boolean(data.DOWNLOAD_HISTORY)
  downloadForm.HISTORY_LIMIT = Number(data.HISTORY_LIMIT || 0)
  downloadForm.MAX_RETRIES = Number(data.MAX_RETRIES || 0)
  downloadForm.RETRY_DELAY = Number(data.RETRY_DELAY || 0)
  downloadForm.MAX_FILE_SIZE_MB = Number(data.MAX_FILE_SIZE_MB || 0)
}

const assignSessionStatus = (data = {}) => {
  sessionStatus.step = data.step || 'idle'
  sessionStatus.authorized = Boolean(data.authorized)
  sessionStatus.message = data.message || ''
  sessionStatus.phone_number = data.phone_number || ''
  sessionStatus.session_name = data.session_name || ''
  sessionStatus.user_id = data.user_id || ''
  sessionStatus.user_name = data.user_name || ''
}

const assignPreferences = (data = {}) => {
  preferenceState.updated_at = data.updated_at ? String(data.updated_at).slice(0, 19).replace('T', ' ') : ''
  preferenceState.channel_weights = Array.isArray(data.channel_weights) ? data.channel_weights : []
  preferenceState.media_type_weights = Array.isArray(data.media_type_weights) ? data.media_type_weights : []
  preferenceState.tag_weights = Array.isArray(data.tag_weights) ? data.tag_weights : []

  manualAdjust.channel = {}
  manualAdjust.media_type = {}
  manualAdjust.tag = {}
  preferenceState.channel_weights.forEach((item) => {
    manualAdjust.channel[item.key] = Number(item.weight || 0)
  })
  preferenceState.media_type_weights.forEach((item) => {
    manualAdjust.media_type[item.key] = Number(item.weight || 0)
  })
  preferenceState.tag_weights.forEach((item) => {
    manualAdjust.tag[item.key] = Number(item.weight || 0)
  })
}

const loadPreferences = async () => {
  preferencesLoading.value = true
  try {
    const data = parseApiData(await http.get('/personal/preferences')) || {}
    assignPreferences(data)
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加载偏好画像失败'))
  } finally {
    preferencesLoading.value = false
  }
}

const refreshPreferences = async () => {
  preferencesRefreshing.value = true
  try {
    await http.post('/personal/preferences/refresh')
    await loadPreferences()
    ElMessage.success('偏好画像已重算')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '重算偏好失败'))
  } finally {
    preferencesRefreshing.value = false
  }
}

const saveManualPreferences = async () => {
  const items = []
  Object.entries(manualAdjust.channel).forEach(([key, weight]) => items.push({ kind: 'channel', key, weight: Number(weight) }))
  Object.entries(manualAdjust.media_type).forEach(([key, weight]) =>
    items.push({ kind: 'media_type', key, weight: Number(weight) })
  )
  Object.entries(manualAdjust.tag).forEach(([key, weight]) => items.push({ kind: 'tag', key, weight: Number(weight) }))

  preferencesSaving.value = true
  try {
    await http.put('/personal/preferences/manual', { items })
    await loadPreferences()
    ElMessage.success('手动偏好已保存')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '保存手动偏好失败'))
  } finally {
    preferencesSaving.value = false
  }
}

const loadAll = async () => {
  loading.value = true
  try {
    const data = parseApiData(await http.get('/telegram-config'))
    assignTelegram(data.telegram || {})
    assignDownload(data.download || {})
    assignSessionStatus(data.session_status || {})
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '加载配置失败'))
  } finally {
    loading.value = false
  }
}

const saveTelegram = async () => {
  const data = parseApiData(await http.put('/telegram-config/telegram', { ...telegramForm }))
  assignTelegram(data)
}

const saveAndStartAuth = async () => {
  authStarting.value = true
  try {
    await saveTelegram()
    const status = parseApiData(await http.post('/telegram-config/auth/start'))
    assignSessionStatus(status)
    ElMessage.success('配置已保存，验证码已发送')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '开始授权失败'))
  } finally {
    authStarting.value = false
  }
}

const submitCode = async () => {
  if (!verifyCode.value) {
    ElMessage.warning('请先输入验证码')
    return
  }
  submittingCode.value = true
  try {
    const status = parseApiData(await http.post('/telegram-config/auth/code', { code: verifyCode.value }))
    assignSessionStatus(status)
    ElMessage.success('验证码已提交')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '提交验证码失败'))
  } finally {
    submittingCode.value = false
  }
}

const submitPassword = async () => {
  if (!twoFactorPassword.value) {
    ElMessage.warning('请先输入二步验证密码')
    return
  }
  submittingPassword.value = true
  try {
    const status = parseApiData(await http.post('/telegram-config/auth/password', { password: twoFactorPassword.value }))
    assignSessionStatus(status)
    ElMessage.success('二步验证密码已提交')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '提交二步验证密码失败'))
  } finally {
    submittingPassword.value = false
  }
}

const checkAuthStatus = async () => {
  statusChecking.value = true
  try {
    const status = parseApiData(await http.get('/telegram-config/auth/status'))
    assignSessionStatus(status)
    ElMessage.success('已更新授权状态')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '检查授权状态失败'))
  } finally {
    statusChecking.value = false
  }
}

const disconnectSession = async () => {
  disconnecting.value = true
  try {
    const status = parseApiData(await http.post('/telegram-config/auth/disconnect'))
    assignSessionStatus(status)
    ElMessage.success('会话已断开')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '断开会话失败'))
  } finally {
    disconnecting.value = false
  }
}

const saveDownload = async (options = {}) => {
  const { silent = false } = options
  savingDownload.value = true
  try {
    const payload = {
      DOWNLOAD_DIR: downloadForm.DOWNLOAD_DIR,
      TARGET_CHATS: downloadForm.TARGET_CHATS,
      ALLOW_EXTS: downloadForm.ALLOW_EXTS,
      DOWNLOAD_HISTORY: downloadForm.DOWNLOAD_HISTORY,
      HISTORY_LIMIT: downloadForm.HISTORY_LIMIT,
      MAX_RETRIES: downloadForm.MAX_RETRIES,
      RETRY_DELAY: downloadForm.RETRY_DELAY,
      MAX_FILE_SIZE_MB: downloadForm.MAX_FILE_SIZE_MB
    }
    const data = parseApiData(await http.put('/telegram-config/download', payload))
    assignDownload(data)
    if (!silent) ElMessage.success('下载配置已保存')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '保存下载配置失败'))
  } finally {
    savingDownload.value = false
  }
}

const saveAllConfigs = async () => {
  savingAll.value = true
  try {
    await saveTelegram()
    await saveDownload({ silent: true })
    ElMessage.success('全部配置已保存')
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, '保存全部配置失败'))
  } finally {
    savingAll.value = false
  }
}

loadAll()
loadPreferences()
</script>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-card {
  border-radius: 18px;
  border: 1px solid #d7dee9;
  background: #fff;
}

.header-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page-title {
  margin: 0;
  color: #0f172a;
  font-size: 32px;
  font-weight: 800;
  line-height: 1.2;
}

.page-desc {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.summary-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.summary-card :deep(.el-card__body) {
  padding: 14px;
}

.summary-label {
  color: #64748b;
  font-size: 13px;
}

.summary-value {
  margin-top: 8px;
  font-size: 40px;
  color: #0f172a;
  font-weight: 700;
  line-height: 1;
}

.summary-path {
  font-size: 44px;
  line-height: 1.1;
}

.summary-badge {
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  color: #334155;
  background: #f1f5f9;
}

.summary-badge-green {
  color: #15803d;
  background: #ecfdf3;
}

.summary-badge-cyan {
  color: #0e7490;
  background: #ecfeff;
}

.summary-badge-orange {
  color: #c2410c;
  background: #fff7ed;
}

.content-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: 1.15fr 1fr;
}

.left-col,
.right-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.block-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.block-title {
  color: #0f172a;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
}

.block-desc {
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
  max-width: 640px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
}

.form-grid :deep(.el-form-item) {
  margin-bottom: 0;
}

.form-grid :deep(.el-form-item__label) {
  color: #64748b;
  font-size: 12px;
  padding-bottom: 6px;
}

.action-row {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.verify-panel {
  margin-top: 12px;
  padding: 12px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #e6edf5;
}

.verify-title {
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
}

.verify-row {
  display: grid;
  gap: 10px;
  grid-template-columns: 1.1fr auto 1.1fr auto;
  align-items: center;
}

.preference-card {
  background: #f6f8fb;
}

.pref-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pref-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.pref-meta {
  color: #64748b;
  font-size: 12px;
}

.stat-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 12px;
  color: #1f2937;
  background: #eef2ff;
  border: 1px solid #dbe4ff;
}

.pref-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.pref-card-col {
  border-radius: 14px;
  background: #fff;
  border: 1px solid #e8edf5;
  min-height: 330px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pref-col-title {
  margin: 0;
  padding: 12px;
  border-bottom: 1px solid #edf2f7;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.pref-col-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px;
}

.pref-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px;
  border-radius: 10px;
}

.pref-row:hover {
  background: #f8fafc;
}

.pref-name {
  flex: 0 0 108px;
  min-width: 84px;
  max-width: 120px;
  font-size: 12px;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pref-slider-wrap {
  flex: 1;
  min-width: 0;
}

.pref-value {
  width: 72px;
  flex: 0 0 72px;
}

.pref-number {
  width: 72px;
}

.pref-slider :deep(.el-slider__runway) {
  height: 4px;
  background-color: #dbeafe;
}

.pref-slider :deep(.el-slider__bar) {
  height: 4px;
  background-color: #06b6d4;
}

.pref-slider :deep(.el-slider__button) {
  width: 12px;
  height: 12px;
  border: 2px solid #06b6d4;
}

.empty-tip {
  padding: 10px;
  color: #94a3b8;
  font-size: 12px;
}

@media (max-width: 1400px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 980px) {
  .header-main,
  .block-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .verify-row {
    grid-template-columns: 1fr;
  }

  .pref-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .summary-value,
  .summary-path,
  .block-title {
    font-size: 30px;
  }
}
</style>
