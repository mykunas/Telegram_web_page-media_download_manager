<template>
  <div>
    <h1 class="page-title">下载日志</h1>
    <p class="page-desc">查看系统日志，支持按级别、模块、关键字和时间范围筛选。</p>

    <el-card class="page-card" shadow="never" style="margin-top: 14px">
      <el-form class="filter-form" label-width="72px" @submit.prevent>
        <el-form-item label="级别">
          <el-select v-model="filters.level" clearable placeholder="全部" style="width: 140px">
            <el-option label="信息" value="INFO" />
            <el-option label="警告" value="WARNING" />
            <el-option label="错误" value="ERROR" />
          </el-select>
        </el-form-item>

        <el-form-item label="模块">
          <el-input v-model="filters.module" clearable placeholder="模块名" style="width: 180px" />
        </el-form-item>

        <el-form-item label="关键字">
          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="日志内容"
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>

        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 250px"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="rows" border stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" sortable />
        <el-table-column prop="created_at" label="时间" width="180" sortable />
        <el-table-column prop="level" label="级别" width="100" sortable>
          <template #default="scope">
            <el-tag :type="levelTagType(scope.row.level)" size="small">{{ formatLevel(scope.row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="150" sortable />
        <el-table-column prop="message" label="消息" min-width="360" show-overflow-tooltip sortable />
        <el-table-column label="扩展信息" min-width="220" show-overflow-tooltip>
          <template #default="scope">
            <span>{{ jsonPreview(scope.row.extra_json) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button link type="primary" :disabled="!scope.row.extra_json" @click="showExtra(scope.row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager-wrap">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          background
          layout="total, sizes, prev, pager, next, jumper"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          @size-change="handlePageSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="extraVisible" title="扩展信息" width="600px">
      <pre class="json-box">{{ extraText }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import http from '@/api/http'

const loading = ref(false)
const rows = ref([])
const extraVisible = ref(false)
const extraText = ref('')

const filters = reactive({
  level: '',
  module: '',
  keyword: '',
  dateRange: []
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const parseApiData = (resp) => {
  const payload = resp?.data || {}
  if (payload.code !== 0) throw new Error(payload.message || '接口请求失败')
  return payload.data
}

const levelTagType = (level) => {
  const v = String(level || '').toUpperCase()
  if (v === 'ERROR') return 'danger'
  if (v === 'WARNING') return 'warning'
  return 'info'
}

const formatLevel = (level) => {
  const v = String(level || '').toUpperCase()
  if (v === 'INFO') return '信息'
  if (v === 'WARNING') return '警告'
  if (v === 'ERROR') return '错误'
  return level || '-'
}

const jsonPreview = (obj) => {
  if (!obj) return '-'
  const text = typeof obj === 'string' ? obj : JSON.stringify(obj)
  return text.length > 80 ? `${text.slice(0, 80)}...` : text
}

const buildQuery = () => {
  const params = {
    page: pagination.page,
    page_size: pagination.pageSize
  }

  if (filters.level) params.level = filters.level
  if (filters.module) params.module = filters.module
  if (filters.keyword) params.keyword = filters.keyword

  if (filters.dateRange?.length === 2) {
    params.date_from = filters.dateRange[0]
    params.date_to = filters.dateRange[1]
  }

  return params
}

const loadLogs = async () => {
  loading.value = true
  try {
    const resp = await http.get('/logs', { params: buildQuery() })
    const data = parseApiData(resp)
    rows.value = Array.isArray(data.list) ? data.list : []
    pagination.total = Number(data.total || 0)
    pagination.page = Number(data.page || pagination.page)
    pagination.pageSize = Number(data.page_size || pagination.pageSize)
  } catch (error) {
    ElMessage.error(error?.message || '加载日志失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadLogs()
}

const handleReset = () => {
  filters.level = ''
  filters.module = ''
  filters.keyword = ''
  filters.dateRange = []
  pagination.page = 1
  loadLogs()
}

const handlePageChange = (page) => {
  pagination.page = page
  loadLogs()
}

const handlePageSizeChange = (size) => {
  pagination.pageSize = size
  pagination.page = 1
  loadLogs()
}

const showExtra = (row) => {
  if (!row.extra_json) return
  extraText.value = JSON.stringify(row.extra_json, null, 2)
  extraVisible.value = true
}

onMounted(loadLogs)
</script>

<style scoped>
.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  margin-bottom: 8px;
}

.pager-wrap {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}

.json-box {
  margin: 0;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
  max-height: 360px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
