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
      <p>AI大脑正在高速运转，为您生成深度分析报告，请稍后...</p>
      <span>这通常需要1-3分钟，您可以先处理其他事务</span>
    </div>

    <div v-else-if="error" class="state-container error-container">
      <el-alert type="error" :title="error" show-icon :closable="false" />
      <el-button @click="startAnalysis" type="primary" style="margin-top: 20px;">
        <el-icon><Refresh /></el-icon>
        重试
      </el-button>
    </div>

    <div v-else-if="analysisResult" class="result-container">
      <div v-html="renderedMarkdown" class="markdown-body"></div>
    </div>

    <div v-else class="state-container initial-state">
        <el-button @click="startAnalysis" type="primary" size="large" round>
            <el-icon style="margin-right: 8px;"><MagicStick /></el-icon>
            开始生成 AI 智能分析报告
        </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { ElButton, ElAlert, ElProgress, ElIcon } from 'element-plus';
import { MagicStick, Refresh } from '@element-plus/icons-vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
// 【修改】引入新的API和轮询服务
import { submitAiAnalysisTask, getReportDetails } from "@/api/analysisApi";
import { startAiAnalysisPolling } from '@/utils/pollingService';
import type { IAnalysisReportDetail } from '@/types/dataModels';

const props = defineProps<{
  reportId: number; // ID通常是number类型
}>();

const isLoading = ref(false);
const error = ref<string | null>(null);
const analysisResult = ref<string | null>(null);
let stopPolling: (() => void) | null = null; // 用于存储停止轮询的函数

const renderedMarkdown = computed(() => {
  if (!analysisResult.value) return '';
  const rawHtml = marked.parse(analysisResult.value, { async: false }) as string;
  return DOMPurify.sanitize(rawHtml);
});

// 统一处理轮询成功和失败的逻辑
const handlePollingSuccess = (report: IAnalysisReportDetail) => {
  isLoading.value = false;
  analysisResult.value = report.ai_analysis_cache;
};

const handlePollingFailure = (err?: any) => {
  isLoading.value = false;
  // 如果err是report对象，说明是分析失败；否则是网络等其他错误
  if (err && err.ai_analysis_status === 'failed') {
    error.value = 'AI分析任务执行失败，请检查报告或重试。';
  } else {
    error.value = err?.message || '获取AI分析结果时发生未知错误';
  }
};

async function startAnalysis() {
  isLoading.value = true;
  error.value = null;

  try {
    // 1. 提交任务
    await submitAiAnalysisTask(props.reportId);

    // 2. 启动轮询
    stopPolling = startAiAnalysisPolling({
      reportId: props.reportId,
      onSuccess: handlePollingSuccess,
      onFailure: handlePollingFailure,
    });
  } catch (err: any) {
    isLoading.value = false;
    error.value = err.response?.data?.detail || '提交分析任务失败';
  }
}

onMounted(async () => {
  // 组件加载时，检查初始状态
  try {
    const report = await getReportDetails(props.reportId);
    if (report.ai_analysis_status === 'processing') {
      isLoading.value = true;
      stopPolling = startAiAnalysisPolling({
        reportId: props.reportId,
        onSuccess: handlePollingSuccess,
        onFailure: handlePollingFailure,
      });
    } else if (report.ai_analysis_status === 'completed') {
      analysisResult.value = report.ai_analysis_cache;
    } else if (report.ai_analysis_status === 'failed') {
      error.value = '此前的AI分析任务已失败，请重试。';
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail || '加载报告状态失败';
  }
});

onUnmounted(() => {
  // 组件卸载时，确保停止轮询
  if (stopPolling) {
    stopPolling();
  }
});
</script>

<style scoped>
/* 样式部分无需修改 */
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