<template>
  <div ref="stageRef" class="grid-stage">
    <div class="grid-wrap" :style="gridStyle">
      <VideoPlayerCard
        v-for="(item, idx) in slots"
        :key="`slot_${idx}_${item.video?.id || 0}_${item.status}`"
        :slot="item"
        :slot-index="idx"
        :total="total"
      :collection-name="collectionName"
      :command="command"
      :muted="muted"
      @ended="$emit('ended', $event)"
      @error="$emit('error', $event)"
      @play="$emit('play', $event)"
        @pause="$emit('pause', $event)"
        @next="$emit('next', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import VideoPlayerCard from '@/components/player/VideoPlayerCard.vue'

const GAP = 10
const VIDEO_RATIO = 9 / 16

const props = defineProps({
  slots: {
    type: Array,
    default: () => []
  },
  total: {
    type: Number,
    default: 0
  },
  collectionName: {
    type: String,
    default: ''
  },
  command: {
    type: Object,
    default: () => ({ type: '', token: 0 })
  },
  muted: {
    type: Boolean,
    default: true
  }
})

defineEmits(['ended', 'error', 'play', 'pause', 'next'])

const stageRef = ref(null)
const stageWidth = ref(0)
const stageHeight = ref(0)
let resizeObserver = null

const layout = computed(() => {
  const count = Math.max(1, props.slots.length || 1)
  const width = Math.max(0, stageWidth.value)
  const height = Math.max(0, stageHeight.value)
  if (!width || !height) {
    return { columns: Math.min(4, count), rows: Math.ceil(count / Math.min(4, count)), itemWidth: 180, itemHeight: 320 }
  }

  let best = null
  for (let cols = 1; cols <= count; cols += 1) {
    const rows = Math.ceil(count / cols)
    const cellMaxWidth = (width - (cols - 1) * GAP) / cols
    const cellMaxHeight = (height - (rows - 1) * GAP) / rows
    if (cellMaxWidth <= 0 || cellMaxHeight <= 0) continue

    const itemWidth = Math.min(cellMaxWidth, cellMaxHeight * VIDEO_RATIO)
    const itemHeight = itemWidth / VIDEO_RATIO
    if (itemWidth <= 0 || itemHeight <= 0) continue

    const score = itemWidth * itemHeight
    if (!best || score > best.score) {
      best = { cols, rows, itemWidth, itemHeight, score }
    }
  }

  if (!best) {
    return { columns: Math.min(4, count), rows: Math.ceil(count / Math.min(4, count)), itemWidth: 180, itemHeight: 320 }
  }

  return {
    columns: best.cols,
    rows: best.rows,
    itemWidth: best.itemWidth,
    itemHeight: best.itemHeight
  }
})

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${layout.value.columns}, ${Math.floor(layout.value.itemWidth)}px)`,
  gridAutoRows: `${Math.floor(layout.value.itemHeight)}px`,
  gap: `${GAP}px`
}))

const updateStageSize = () => {
  const el = stageRef.value
  if (!el) return
  stageWidth.value = el.clientWidth
  stageHeight.value = el.clientHeight
}

onMounted(() => {
  updateStageSize()
  resizeObserver = new ResizeObserver(() => updateStageSize())
  if (stageRef.value) resizeObserver.observe(stageRef.value)
})

watch(
  () => props.slots.length,
  () => updateStageSize()
)

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
})
</script>

<style scoped>
.grid-stage {
  width: 100%;
  height: calc(100vh - 258px);
  min-height: 360px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.grid-wrap {
  width: 100%;
  height: 100%;
  display: grid;
  align-content: center;
  justify-content: center;
}

@media (max-width: 900px) {
  .grid-stage {
    height: calc(100vh - 280px);
    min-height: 320px;
  }
}
</style>
