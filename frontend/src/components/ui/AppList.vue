<template>
  <div class="app-list">
    <div v-if="title" class="app-list__title">{{ title }}</div>
    <div v-if="!items.length" class="app-list__empty">{{ emptyText }}</div>
    <ul v-else>
      <li v-for="item in items" :key="item.key || item.id || item.label" class="app-list__item">
        <div>
          <div class="app-list__label">{{ item.label || '-' }}</div>
          <div v-if="item.meta" class="app-list__meta">{{ item.meta }}</div>
        </div>
        <div class="app-list__value">{{ item.value ?? '-' }}</div>
      </li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: ''
  },
  items: {
    type: Array,
    default: () => []
  },
  emptyText: {
    type: String,
    default: '暂无数据'
  }
})
</script>

<style scoped>
.app-list {
  display: grid;
  gap: var(--ds-space-2);
}

.app-list__title {
  font-size: 0.95rem;
  font-weight: 600;
}

.app-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: var(--ds-space-1);
}

.app-list__item {
  border: 1px solid var(--ds-border);
  border-radius: var(--ds-radius-md);
  padding: 10px 12px;
  background: var(--ds-surface-muted);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.app-list__item:hover {
  border-color: color-mix(in srgb, var(--ds-color-primary) 36%, var(--ds-border));
}

.app-list__label {
  font-weight: 600;
}

.app-list__meta {
  color: var(--ds-text-muted);
  font-size: var(--ds-font-meta);
}

.app-list__value {
  color: var(--ds-text-secondary);
  font-size: 0.9rem;
  font-weight: 600;
}

.app-list__empty {
  color: var(--ds-text-muted);
  font-size: var(--ds-font-meta);
}
</style>
