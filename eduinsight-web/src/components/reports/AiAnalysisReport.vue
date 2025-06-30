<template>
  <div class="ai-analysis-container">
    <div v-if="isLoading" class="state-container loading-container">
      <el-progress
        type="circle"
        :percentage="100"
        status="success"
        :indeterminate="true"
        :duration="1"
      />
      <p>AI大腦正在高速運轉，為您生成深度分析報告，請稍候...</p>
      <span>這通常需要 15 到 30 秒</span>
    </div>

    <div v-else-if="error" class="state-container error-container">
      <el-alert type="error" :title="error" show-icon :closable="false" />
      <el-button @click="fetchAiAnalysis" type="primary" style="margin-top: 20px;">
        <el-icon><Refresh /></el-icon>
        重试
      </el-button>
    </div>

    <div v-else-if="analysisResult" class="result-container">
      <div v-html="renderedMarkdown" class="markdown-body"></div>
    </div>

    <div v-else class="state-container initial-state">
        <el-button @click="fetchAiAnalysis" type="primary" size="large" round>
            <el-icon style="margin-right: 8px;"><MagicStick /></el-icon>
            开始生成 AI 智能分析报告
        </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElButton, ElAlert, ElProgress, ElIcon } from 'element-plus';
import { MagicStick, Refresh } from '@element-plus/icons-vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import {generateAiAnalysis} from "@/api/analysisApi.ts";


const props = defineProps<{
  reportId: string;
}>();

const isLoading = ref(false);
const error = ref<string | null>(null);
const analysisResult = ref<string | null>(null);

// 将Markdown字符串安全地转换为HTML
const renderedMarkdown = computed(() => {
  if (!analysisResult.value) return '';
  // 先用 marked 解析，再用 DOMPurify 清理，防止XSS攻击
  const rawHtml = marked.parse(analysisResult.value, { async: false }) as string;
  return DOMPurify.sanitize(rawHtml);
});

async function fetchAiAnalysis() {
  isLoading.value = true;
  error.value = null;

  try {
    // 调用我们后端创建的API端点
    const response = await generateAiAnalysis(props.reportId);
    analysisResult.value = response.analysis;
  } catch (err: any) {
    error.value = err.response?.data?.detail || err.message || '生成分析报告时发生未知错误';
    console.error(err);
  } finally {
    isLoading.value = false;
  }
}
</script>

<style scoped>
.ai-analysis-container {
  padding: 1rem 2rem;
  min-height: 50vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #fafcff;
  border-radius: 8px;
  border: 1px dashed #dcdfe6;
}

.state-container {
  text-align: center;
}

.loading-container p {
  margin-top: 1.5rem;
  color: #606266;
  font-size: 1.1rem;
  font-weight: 500;
}
.loading-container span {
  margin-top: 0.5rem;
  color: #909399;
  font-size: 0.9rem;
}

.result-container {
  width: 100%;
  text-align: left;
}

.markdown-body {
  line-height: 1.8;
  font-size: 16px;
  color: #303133;
}
/* 从网上找一份好看的 markdown.css 主题来美化渲染后的HTML */
/* 也可以直接用下面的简单样式 */
:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3) {
  font-weight: 600;
  margin-top: 1.5em;
  margin-bottom: 0.8em;
  border-bottom: 1px solid #e4e7ed;
  padding-bottom: 0.5em;
}
:deep(.markdown-body h1) { font-size: 1.8em; }
:deep(.markdown-body h2) { font-size: 1.5em; }
:deep(.markdown-body h3) { font-size: 1.25em; }

:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  padding-left: 2em;
}
:deep(.markdown-body li) {
  margin-bottom: 0.5em;
}

:deep(.markdown-body code) {
  background-color: rgba(64, 158, 255, 0.1);
  padding: 0.2em 0.4em;
  border-radius: 4px;
  font-size: 90%;
  color: #409eff;
  font-family: 'Courier New', Courier, monospace;
}

:deep(.markdown-body blockquote) {
  border-left: 4px solid #409EFF;
  padding: 0.5em 1rem;
  color: #606266;
  margin-left: 0;
  background-color: #ecf5ff;
}
</style>