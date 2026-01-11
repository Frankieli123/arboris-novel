<template>
  <div class="emotion-curve-section">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-full flex items-center justify-center" style="background-color: var(--md-primary-container);">
          <svg class="w-5 h-5" style="color: var(--md-on-primary-container);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
          </svg>
        </div>
        <div>
          <h3 class="md-title-medium" style="color: var(--md-on-surface);">情感曲线</h3>
          <p class="md-body-small" style="color: var(--md-on-surface-variant);">追踪章节情感变化</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button 
          @click="useAIAnalysis" 
          class="md-btn md-btn-tonal md-ripple"
          :disabled="isLoading"
        >
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          AI深度分析
        </button>
        <button 
          @click="refreshData" 
          class="md-icon-btn md-ripple"
          :disabled="isLoading"
        >
          <svg 
            class="w-5 h-5 transition-transform" 
            :class="{ 'animate-spin': isLoading }"
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center py-12">
      <div class="md-spinner"></div>
      <p class="mt-4 md-body-medium" style="color: var(--md-on-surface-variant);">分析情感数据中...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="flex flex-col items-center justify-center py-12">
      <div class="w-12 h-12 rounded-full flex items-center justify-center mb-4" style="background-color: var(--md-error-container);">
        <svg class="w-6 h-6" style="color: var(--md-error);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p class="md-body-medium" style="color: var(--md-error);">{{ error }}</p>
      <button @click="refreshData" class="md-btn md-btn-text md-ripple mt-4">重试</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="!emotionPoints || emotionPoints.length === 0" class="flex flex-col items-center justify-center py-12">
      <div class="w-16 h-16 rounded-full flex items-center justify-center mb-4" style="background-color: var(--md-surface-container);">
        <svg class="w-8 h-8" style="color: var(--md-on-surface-variant);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      </div>
      <p class="md-body-large" style="color: var(--md-on-surface);">暂无情感数据</p>
      <p class="md-body-medium" style="color: var(--md-on-surface-variant);">生成章节内容后将自动分析情感曲线</p>
    </div>

    <!-- Chart Container -->
    <div v-else>
      <!-- Statistics Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="md-card md-card-outlined p-4 text-center" style="border-radius: var(--md-radius-md);">
          <p class="md-label-medium" style="color: var(--md-on-surface-variant);">总章节</p>
          <p class="md-headline-small" style="color: var(--md-primary);">{{ totalChapters }}</p>
        </div>
        <div class="md-card md-card-outlined p-4 text-center" style="border-radius: var(--md-radius-md);">
          <p class="md-label-medium" style="color: var(--md-on-surface-variant);">平均强度</p>
          <p class="md-headline-small" style="color: var(--md-primary);">{{ averageIntensity }}</p>
        </div>
        <div class="md-card md-card-outlined p-4 text-center" style="border-radius: var(--md-radius-md);">
          <p class="md-label-medium" style="color: var(--md-on-surface-variant);">主导情感</p>
          <p class="md-headline-small" style="color: var(--md-primary);">{{ dominantEmotion }}</p>
        </div>
        <div class="md-card md-card-outlined p-4 text-center" style="border-radius: var(--md-radius-md);">
          <p class="md-label-medium" style="color: var(--md-on-surface-variant);">情感类型</p>
          <p class="md-headline-small" style="color: var(--md-primary);">{{ emotionTypeCount }}</p>
        </div>
      </div>

      <!-- Emotion Type Filter Chips -->
      <div class="flex flex-wrap gap-2 mb-6">
        <button
          v-for="emotion in emotionTypes"
          :key="emotion.key"
          @click="toggleEmotion(emotion.key)"
          class="md-chip md-chip-filter md-ripple"
          :class="{ 'selected': selectedEmotions.includes(emotion.key) }"
          :style="selectedEmotions.includes(emotion.key) ? { backgroundColor: emotion.color + '20', color: emotion.color, borderColor: emotion.color } : {}"
        >
          <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: emotion.color }"></span>
          {{ emotion.label }}
          <span v-if="emotionDistribution[emotion.label]" class="ml-1 opacity-70">({{ emotionDistribution[emotion.label] }})</span>
        </button>
      </div>

      <!-- Chart -->
      <div class="md-card md-card-outlined p-4" style="border-radius: var(--md-radius-md);">
        <canvas ref="chartCanvas" height="300"></canvas>
      </div>

      <!-- Chapter Details List -->
      <div class="mt-6 space-y-3">
        <h4 class="md-title-small" style="color: var(--md-on-surface);">章节情感详情</h4>
        <div 
          v-for="point in emotionPoints" 
          :key="point.chapter_number"
          class="md-card md-card-outlined p-4 flex items-center gap-4"
          style="border-radius: var(--md-radius-md);"
        >
          <div 
            class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
            :style="{ backgroundColor: getEmotionColor(point.emotion_type) + '20' }"
          >
            <span class="md-label-large" :style="{ color: getEmotionColor(point.emotion_type) }">{{ point.chapter_number }}</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="md-body-medium truncate" style="color: var(--md-on-surface);">{{ point.title }}</p>
            <p class="md-body-small" style="color: var(--md-on-surface-variant);">{{ point.description }}</p>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <span 
              class="md-chip md-chip-filter selected px-2 py-1"
              :style="{ backgroundColor: getEmotionColor(point.emotion_type) + '20', color: getEmotionColor(point.emotion_type) }"
            >
              {{ point.emotion_type }}
            </span>
            <span class="md-label-medium" style="color: var(--md-on-surface-variant);">
              强度: {{ point.intensity }}/10
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

interface EmotionPoint {
  chapter_number: number
  title: string
  emotion_type: string
  intensity: number
  narrative_phase?: string
  description: string
}

interface EmotionCurveResponse {
  project_id: string
  project_title: string
  total_chapters: number
  emotion_points: EmotionPoint[]
  average_intensity: number
  emotion_distribution: Record<string, number>
}

const route = useRoute()
const authStore = useAuthStore()
const projectId = route.params.id as string

const chartCanvas = ref<HTMLCanvasElement | null>(null)
const isLoading = ref(false)
const error = ref<string | null>(null)
const emotionPoints = ref<EmotionPoint[]>([])
const totalChapters = ref(0)
const averageIntensity = ref(0)
const emotionDistribution = ref<Record<string, number>>({})
let chartInstance: any = null

const emotionTypes = [
  { key: 'joy', label: '喜悦', color: '#34A853' },
  { key: 'sadness', label: '悲伤', color: '#4285F4' },
  { key: 'anger', label: '愤怒', color: '#EA4335' },
  { key: 'fear', label: '恐惧', color: '#9334E6' },
  { key: 'surprise', label: '惊讶', color: '#FBBC04' },
  { key: 'calm', label: '平静', color: '#5F6368' }
]

const selectedEmotions = ref(['joy', 'sadness', 'anger'])

const dominantEmotion = computed(() => {
  if (Object.keys(emotionDistribution.value).length === 0) return '-'
  const sorted = Object.entries(emotionDistribution.value).sort((a, b) => b[1] - a[1])
  return sorted[0]?.[0] || '-'
})

const emotionTypeCount = computed(() => {
  return Object.keys(emotionDistribution.value).length
})

const getEmotionColor = (emotionType: string) => {
  const emotionMap: Record<string, string> = {
    '喜悦': '#34A853',
    '悲伤': '#4285F4',
    '愤怒': '#EA4335',
    '恐惧': '#9334E6',
    '惊讶': '#FBBC04',
    '平静': '#5F6368'
  }
  return emotionMap[emotionType] || '#5F6368'
}

const toggleEmotion = (key: string) => {
  const index = selectedEmotions.value.indexOf(key)
  if (index > -1) {
    if (selectedEmotions.value.length > 1) {
      selectedEmotions.value.splice(index, 1)
    }
  } else {
    selectedEmotions.value.push(key)
  }
  updateChart()
}

const fetchEmotionData = async (useAI = false) => {
  isLoading.value = true
  error.value = null
  
  try {
    const endpoint = useAI 
      ? `/api/analytics/${projectId}/analyze-emotion-ai`
      : `/api/analytics/${projectId}/emotion-curve`
    
    const method = useAI ? 'POST' : 'GET'
    
    const response = await fetch(endpoint, {
      method,
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      let errorMessage = '获取情感数据失败'
      try {
        const errorData = await response.json()
        errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData)
      } catch (e) {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`
      }
      throw new Error(errorMessage)
    }
    
    const data: EmotionCurveResponse = await response.json()
    emotionPoints.value = data.emotion_points || []
    totalChapters.value = data.total_chapters
    averageIntensity.value = data.average_intensity
    emotionDistribution.value = data.emotion_distribution || {}
    
    await nextTick()
    initChart()
  } catch (e: any) {
    console.error('情感曲线加载错误:', e)
    if (e instanceof Error) {
      error.value = e.message
    } else if (typeof e === 'string') {
      error.value = e
    } else {
      error.value = '加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}

const refreshData = () => {
  fetchEmotionData(false)
}

const useAIAnalysis = () => {
  fetchEmotionData(true)
}

const initChart = async () => {
  if (!chartCanvas.value || emotionPoints.value.length === 0) return
  
  // Dynamically import Chart.js
  const { Chart, registerables } = await import('chart.js')
  Chart.register(...registerables)
  
  if (chartInstance) {
    chartInstance.destroy()
  }
  
  const ctx = chartCanvas.value.getContext('2d')
  if (!ctx) return
  
  const labels = emotionPoints.value.map(p => `第${p.chapter_number}章`)
  const intensityData = emotionPoints.value.map(p => p.intensity)
  const backgroundColors = emotionPoints.value.map(p => getEmotionColor(p.emotion_type) + '80')
  const borderColors = emotionPoints.value.map(p => getEmotionColor(p.emotion_type))
  
  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: '情感强度',
        data: intensityData,
        borderColor: '#4285F4',
        backgroundColor: 'rgba(66, 133, 244, 0.1)',
        tension: 0.4,
        fill: true,
        pointRadius: 6,
        pointHoverRadius: 8,
        pointBackgroundColor: backgroundColors,
        pointBorderColor: borderColors,
        pointBorderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'index'
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          backgroundColor: 'rgba(32, 33, 36, 0.9)',
          titleFont: { family: 'Roboto', size: 14 },
          bodyFont: { family: 'Roboto', size: 12 },
          padding: 12,
          cornerRadius: 8,
          callbacks: {
            label: (context: any) => {
              const point = emotionPoints.value[context.dataIndex]
              return [
                `情感: ${point.emotion_type}`,
                `强度: ${point.intensity}/10`,
                point.narrative_phase ? `阶段: ${point.narrative_phase}` : ''
              ].filter(Boolean)
            }
          }
        }
      },
      scales: {
        x: {
          grid: {
            color: 'rgba(218, 220, 224, 0.5)'
          },
          ticks: {
            font: { family: 'Roboto', size: 12 },
            color: '#5F6368'
          }
        },
        y: {
          min: 0,
          max: 10,
          grid: {
            color: 'rgba(218, 220, 224, 0.5)'
          },
          ticks: {
            font: { family: 'Roboto', size: 12 },
            color: '#5F6368',
            stepSize: 2
          }
        }
      }
    }
  })
}

const updateChart = () => {
  if (chartInstance && emotionPoints.value.length > 0) {
    initChart()
  }
}

onMounted(() => {
  fetchEmotionData()
})

watch(selectedEmotions, () => {
  updateChart()
}, { deep: true })
</script>
