<template>
  <div v-if="show" class="task-progress-modal-overlay" @click.self="onCancel">
    <div class="task-progress-modal">
      <div class="modal-header">
        <h3 class="modal-title">{{ title }}</h3>
        <button v-if="cancellable" @click="onCancel" class="close-button" aria-label="关闭">
          ×
        </button>
      </div>

      <div class="modal-body">
        <div class="progress-bar-container">
          <div class="progress-bar">
            <div 
              class="progress-fill" 
              :style="{ width: `${progress}%` }"
              :class="statusClass"
            ></div>
          </div>
          <div class="progress-text">{{ progress }}%</div>
        </div>

        <p class="progress-message">{{ progressMessage || '正在处理...' }}</p>
        
        <div v-if="status" class="status-indicator" :class="statusClass">
          <span class="status-text">{{ statusText }}</span>
        </div>

        <div v-if="error" class="error-message">
          <p>{{ error }}</p>
          <button v-if="onRetry" @click="onRetry" class="retry-button">
            重试
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  show: boolean
  title?: string
  status: 'idle' | 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  progressMessage?: string
  error?: string | null
  cancellable?: boolean
  onRetry?: () => void
  onCancel?: () => void
}

const props = withDefaults(defineProps<Props>(), {
  title: '任务进度',
  progressMessage: '',
  error: null,
  cancellable: false,
  onRetry: undefined,
  onCancel: undefined
})

const statusText = computed(() => {
  switch (props.status) {
    case 'idle':
      return '等待中'
    case 'pending':
      return '排队中'
    case 'processing':
      return '处理中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
    default:
      return ''
  }
})

const statusClass = computed(() => {
  return `status-${props.status}`
})
</script>

<style scoped>
.task-progress-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.task-progress-modal {
  background: white;
  border-radius: 8px;
  padding: 24px;
  min-width: 400px;
  max-width: 500px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.modal-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

.close-button {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  padding: 0;
  width: 24px;
  height: 24px;
  line-height: 1;
}

.close-button:hover {
  color: #333;
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.progress-bar-container {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background-color: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  transition: width 0.3s ease;
  border-radius: 4px;
}

.progress-fill.status-pending,
.progress-fill.status-processing {
  background-color: #3b82f6;
}

.progress-fill.status-completed {
  background-color: #10b981;
}

.progress-fill.status-failed {
  background-color: #ef4444;
}

.progress-text {
  font-size: 14px;
  font-weight: 500;
  color: #666;
  min-width: 45px;
  text-align: right;
}

.progress-message {
  font-size: 14px;
  color: #666;
  margin: 0;
  text-align: center;
}

.status-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  border-radius: 4px;
}

.status-indicator.status-pending {
  background-color: #dbeafe;
  color: #1e40af;
}

.status-indicator.status-processing {
  background-color: #dbeafe;
  color: #1e40af;
}

.status-indicator.status-completed {
  background-color: #d1fae5;
  color: #065f46;
}

.status-indicator.status-failed {
  background-color: #fee2e2;
  color: #991b1b;
}

.status-text {
  font-size: 14px;
  font-weight: 500;
}

.error-message {
  background-color: #fee2e2;
  border: 1px solid #fecaca;
  border-radius: 4px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.error-message p {
  margin: 0;
  color: #991b1b;
  font-size: 14px;
}

.retry-button {
  align-self: flex-start;
  background-color: #ef4444;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
}

.retry-button:hover {
  background-color: #dc2626;
}
</style>
