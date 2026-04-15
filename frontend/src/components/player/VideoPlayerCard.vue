<template>
  <article class="player-card">
    <video
      v-if="slot.video && slot.status !== 'finished'"
      ref="videoRef"
      :key="videoKey"
      :src="slot.video.play_url"
      :poster="slot.video.cover || ''"
      class="video-el"
      controls
      :muted="muted"
      autoplay
      playsinline
      preload="metadata"
      @ended="onEnded"
      @play="onPlay"
      @pause="onPause"
      @error="onError"
    />
    <div v-else class="empty-state">{{ emptyText }}</div>
  </article>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  slot: {
    type: Object,
    required: true
  },
  slotIndex: {
    type: Number,
    required: true
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

const emit = defineEmits(['ended', 'error', 'play', 'pause', 'next'])

const videoRef = ref(null)
const videoKey = computed(() => `${props.slotIndex}_${props.slot?.video?.id || 0}_${props.slot?.status || ''}`)

const emptyText = computed(() => {
  const s = props.slot?.status || 'waiting'
  if (s === 'finished') return '播放完成'
  if (s === 'error') return '加载失败，等待下一个'
  return '等待分配'
})

const tryPlay = async () => {
  const el = videoRef.value
  if (!el) return
  try {
    await el.play()
  } catch {
    // ignore autoplay restrictions
  }
}

watch(
  () => props.slot?.video?.id,
  async () => {
    await nextTick()
    if ((props.slot?.status || '') === 'playing') {
      await tryPlay()
    }
  }
)

watch(
  () => props.command?.token,
  async () => {
    const cmd = props.command?.type
    const el = videoRef.value
    if (!el) return
    if (cmd === 'pause') {
      el.pause()
    } else if (cmd === 'resume') {
      await tryPlay()
    } else if (cmd === 'stop') {
      el.pause()
      el.currentTime = 0
    } else if (cmd === 'restart') {
      el.currentTime = 0
      await tryPlay()
    }
  }
)

watch(
  () => props.muted,
  (value) => {
    const el = videoRef.value
    if (!el) return
    el.muted = Boolean(value)
  }
)

const onEnded = () => emit('ended', props.slotIndex)
const onError = () => emit('error', props.slotIndex)
const onPlay = () => emit('play', props.slotIndex)
const onPause = () => emit('pause', props.slotIndex)
</script>

<style scoped>
.player-card {
  width: 100%;
  height: 100%;
  border-radius: 10px;
  overflow: hidden;
  background: #0b1220;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.video-el {
  width: 100%;
  height: 100%;
  object-fit: contain;
  object-position: center center;
  background: #000;
}

.empty-state {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #cbd5e1;
  font-size: 13px;
  background: #111827;
}
</style>
