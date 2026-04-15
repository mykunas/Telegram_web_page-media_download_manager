<template>
  <div>
    <h1 class="page-title">错误日志</h1>
    <p class="page-desc">查看错误日志，支持筛选、详情查看与标记已处理。</p>

    <el-card class="page-card" shadow="never" style="margin-top: 14px">
      <el-form class="filter-form" label-width="72px" @submit.prevent>
        <el-form-item label="处理状态">
          <el-select v-model="filters.resolved" clearable placeholder="全部" style="width: 140px">
            <el-option label="未处理" :value="false" />
            <el-option label="已处理" :value="true" />
          </el-select>
        </el-form-item>

        <el-form-item label="模块">
          <el-input v-model="filters.module" clearable placeholder="模块名" style="width: 180px" />
        </el-form-item>

        <el-form-item label="频道ID">
          <el-input v-model="filters.chatId" clearable placeholder="频道ID" style="width: 180px" />
        </el-form-item>

        <el-form-item label="关键字">
          <el-input
            v-model="filters.keyword"
            clearable
            placeholder="错误内容关键字"
            style="width: 220px"
            @keyup.enter="handleSearch"
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
        <el-table-column prop="module" label="模块" width="140" sortable />
        <el-table-column prop="chat_id" label="频道ID" width="140" sortable />
        <el-table-column prop="error_type" label="错误类型" width="150" sortable />
        <el-table-column prop="error_message" label="错误信息" min-width="280" show-overflow-tooltip sortable />
        <el-table-column prop="resolved" label="状态" width="100" sortable>
          <template #default="scope">
            <el-tag :type="scope.row.resolved ? 'success' : 'danger'" size="small">
              {{ scope.row.resolved ? '已处理' : '未处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="showDetail(scope.row)">详情</el-button>
            <el-button
              link
              type="success"
              :disabled="scope.row.resolved"
              @click="resolveError(scope.row.id)"
            >
              标记已处理
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

    <el-dialog v-model="detailVisible" title="错误详情" width="760px">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="模块">{{ detail.module }}</el-descriptions-item>
        <el-descriptions-item label="频道ID">{{ detail.chat_id ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="消息ID">{{ detail.message_id ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="文件路径">{{ detail.file_path || '-' }}</el-descriptions-item>
        <el-descriptions-item label="错误类型">{{ detail.error_type }}</el-descriptions-item>
        <el-descriptions-item label="错误信息">{{ detail.error_message }}</el-descriptions-item>
        <el-descriptions-item label="错误堆栈">
          <pre class="trace-box">{{ detail.traceback || '-' }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="状态">{{ detail.resolved ? '已处理' : '未处理' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import http from '@/api/http'

const loading = ref(false)
const rows = ref([])
const detailVisible = ref(false)
const detail = ref(null)

const filters = reactive({
  resolved: undefined,
  module: '',
  chatId: '',
  keyword: ''
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

const buildQuery = () => {
  const params = {
    page: pagination.page,
    page_size: pagination.pageSize
  }

  if (filters.resolved !== undefined) params.resolved = filters.resolved
  if (filters.module) params.module = filters.module
  if (filters.chatId) params.chat_id = filters.chatId
  if (filters.keyword) params.keyword = filters.keyword

  return params
}

const loadErrors = async () => {
  loading.value = true
  try {
    const resp = await http.get('/errors', { params: buildQuery() })
    const data = parseApiData(resp)
    rows.value = Array.isArray(data.list) ? data.list : []
    pagination.total = Number(data.total || 0)
    pagination.page = Number(data.page || pagination.page)
    pagination.pageSize = Number(data.page_size || pagination.pageSize)
  } catch (error) {
    ElMessage.error(error?.message || '加载错误日志失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadErrors()
}

const handleReset = () => {
  filters.resolved = undefined
  filters.module = ''
  filters.chatId = ''
  filters.keyword = ''
  pagination.page = 1
  loadErrors()
}

const handlePageChange = (page) => {
  pagination.page = page
  loadErrors()
}

const handlePageSizeChange = (size) => {
  pagination.pageSize = size
  pagination.page = 1
  loadErrors()
}

const showDetail = (row) => {
  detail.value = row
  detailVisible.value = true
}

const resolveError = async (id) => {
  try {
    await ElMessageBox.confirm('确认将该错误标记为已处理？', '操作确认', { type: 'warning' })
    const resp = await http.post(`/errors/${id}/resolve`)
    parseApiData(resp)
    ElMessage.success('已标记为已处理')
    loadErrors()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error?.message || '操作失败')
    }
  }
}

onMounted(loadErrors)
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

.trace-box {
  margin: 0;
  padding: 10px;
  max-height: 220px;
  overflow: auto;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f8fafc;
  white-space: pre-wrap;
  word-break: break-all;
}

:deep(.el-descriptions__label) {
  width: 120px;
}
</style>
