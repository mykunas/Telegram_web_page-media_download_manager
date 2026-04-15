<template>
  <el-card class="app-card" shadow="never">
    <template v-if="title || $slots.header" #header>
      <slot name="header">
        <div class="app-card__header">
          <div>
            <h3 class="app-card__title">{{ title }}</h3>
            <p v-if="description" class="app-card__desc">{{ description }}</p>
          </div>
          <slot name="actions" />
        </div>
      </slot>
    </template>

    <slot />
  </el-card>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: ''
  },
  description: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.app-card {
  border-radius: var(--ds-radius-lg);
}

.app-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ds-space-2);
}

.app-card__title {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.35;
}

.app-card__desc {
  margin: 4px 0 0;
  color: var(--ds-text-muted);
  font-size: var(--ds-font-meta);
}
</style>
