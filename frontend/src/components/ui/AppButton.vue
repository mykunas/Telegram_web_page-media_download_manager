<template>
  <el-button
    :type="resolvedType"
    :plain="variant === 'ghost'"
    :text="variant === 'text'"
    :size="size"
    :class="['app-btn', `app-btn--${variant}`]"
    v-bind="$attrs"
  >
    <slot />
  </el-button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  variant: {
    type: String,
    default: 'primary'
  },
  size: {
    type: String,
    default: 'default'
  }
})

const resolvedType = computed(() => {
  if (['primary', 'success', 'warning', 'danger', 'info'].includes(props.variant)) return props.variant
  if (props.variant === 'ghost' || props.variant === 'text') return 'default'
  return 'default'
})
</script>

<style scoped>
.app-btn {
  min-height: 36px;
  border-radius: var(--ds-radius-md);
  font-weight: 600;
}

.app-btn--primary {
  background: linear-gradient(135deg, var(--ds-color-primary), color-mix(in srgb, var(--ds-color-primary) 65%, #fff));
  border-color: color-mix(in srgb, var(--ds-color-primary) 70%, #000);
}

.app-btn--ghost {
  background: color-mix(in srgb, var(--ds-color-primary) 8%, transparent);
  border-color: color-mix(in srgb, var(--ds-color-primary) 26%, var(--ds-border));
  color: var(--ds-color-primary);
}
</style>
