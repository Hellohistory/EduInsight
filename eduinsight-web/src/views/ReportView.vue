<template>
  <div class="report-view" v-loading="reportStore.isLoading">
    <template v-if="reportStore.fullReport && reportStore.chartData">
      <div class="report-header">
        <h1>{{ reportStore.fullReport.groupName }} - 学情分析报告</h1>
        <p>报告生成时间: {{ formatDateTime(reportStore.reportDetail?.created_at) }}</p>
      </div>

      <el-tabs v-model="activeTab" class="report-tabs">
        <el-tab-pane label="年级总览" name="grade-overview">
          <GradeOverviewTab />
        </el-tab-pane>

        <el-tab-pane label="班级对比" name="class-comparison">
          <ClassComparison
            :report="reportStore.fullReport"
            :chartData="reportStore.chartData"
          />
        </el-tab-pane>

        <el-tab-pane label="学生详情" name="student-details">
          <StudentDetailListTab />
        </el-tab-pane>

        <el-tab-pane label="AI 智能分析" name="ai-analysis">
          <AiAnalysisReport :report-id="props.id" />
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-result
      v-else-if="reportStore.error"
      status="error"
      title="报告加载失败"
      :sub-title="reportStore.error"
    >
      <template #extra>
        <el-button type="primary" @click="fetchData">重试</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { ElTabs, ElTabPane, ElResult, ElButton, vLoading } from 'element-plus';
import { useAnalysisReportStore } from '@/stores/analysisReportStore';

import GradeOverviewTab from '@/components/reports/tabs/GradeOverviewTab.vue';
import ClassComparison from '@/components/reports/ClassComparison.vue'; // 可保持原样或继续拆分
import StudentDetailListTab from '@/components/reports/tabs/StudentDetailListTab.vue';
import AiAnalysisReport from '@/components/reports/AiAnalysisReport.vue';

const props = defineProps<{ id: string }>();

const reportStore = useAnalysisReportStore();
const activeTab = ref('grade-overview');

const fetchData = () => {
  const reportId = parseInt(props.id, 10);
  if (!isNaN(reportId)) {
    reportStore.fetchReport(reportId);
  }
};

onMounted(fetchData);

// 在组件卸载时清理 Store 中的数据，避免数据污染
onUnmounted(() => {
  reportStore.clearReport();
});

const formatDateTime = (dateString?: string) => {
  if (!dateString) return 'N/A';
  return new Date(dateString).toLocaleString('zh-CN');
};
</script>

<style scoped>
.report-view {
  padding: 1rem 2rem;
  background-color: #f9fafc;
}
.report-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e4e7ed;
}
.report-header h1 {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
}
.report-header p {
  color: #888;
  font-size: 0.9rem;
}
.chart-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
    gap: 1.5rem;
    margin-top: 1.5rem;
}
.chart-card {
    border-radius: 8px;
    box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}
.student-table {
    margin-top: 1rem;
    width: 100%;
}
.student-link {
    color: #409EFF;
    text-decoration: none;
    font-weight: 500;
}
.student-link:hover {
    text-decoration: underline;
}
.report-tabs {
    background-color: #fff;
    padding: 1.5rem;
    border-radius: 8px;
    box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}
</style>