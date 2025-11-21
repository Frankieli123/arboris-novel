<template>
  <div class="min-h-screen p-4 relative">
    <div class="absolute top-4 left-4">
      <router-link
        to="/"
        class="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"
      >
        &larr; 返回
      </router-link>
    </div>
    <div class="flex flex-col md:flex-row max-w-6xl mx-auto mt-16">
      <!-- Sidebar -->
      <div class="w-full md:w-64 bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-4 mb-4 md:mb-0 md:mr-8">
        <h2 class="text-xl font-bold text-gray-800 mb-4">设置</h2>
        <nav>
          <ul>
            <li
              :class="[
                'px-4 py-2 rounded-lg cursor-pointer transition-colors',
                activeTab === 'llm' ? 'bg-indigo-100 text-indigo-700' : 'hover:bg-gray-100'
              ]"
              @click="activeTab = 'llm'"
            >
              LLM 配置
            </li>
            <li
              :class="[
                'px-4 py-2 rounded-lg cursor-pointer transition-colors mt-2',
                activeTab === 'plugins' ? 'bg-indigo-100 text-indigo-700' : 'hover:bg-gray-100'
              ]"
              @click="activeTab = 'plugins'"
            >
              MCP 插件
            </li>
          </ul>
        </nav>
      </div>

      <!-- Main Content -->
      <div class="flex-1">
        <LLMSettings v-if="activeTab === 'llm'" />
        <PluginManagement v-else-if="activeTab === 'plugins'" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import LLMSettings from '@/components/LLMSettings.vue'
import PluginManagement from '@/views/PluginManagement.vue'

const activeTab = ref<'llm' | 'plugins'>('llm')
</script>
