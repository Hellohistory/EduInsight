// src/utils/pollingService.ts

import { getReportDetails } from '@/api/analysisApi';
import type { IAnalysisReportDetail } from '@/types/dataModels';

interface PollingOptions {
  reportId: number;
  onSuccess: (report: IAnalysisReportDetail) => void;
  onFailure: (error?: any) => void;
  onUpdate?: (report: IAnalysisReportDetail) => void;
  interval?: number;
  timeout?: number;
}

/**
 * 启动一个针对分析报告状态的轮询任务。
 *
 * @param options - 轮询配置
 * @returns 一个可以手动停止轮询的函数
 */
export function startReportPolling(options: PollingOptions): () => void {
  const {
    reportId,
    onSuccess,
    onFailure,
    onUpdate,
    interval = 3000, // 默认3秒轮询一次
    timeout = 120000, // 默认2分钟超时
  } = options;

  let pollingHandle: number | undefined;
  const startTime = Date.now();

  const poll = async () => {
    // 检查是否超时
    if (Date.now() - startTime > timeout) {
      clearInterval(pollingHandle);
      onFailure(new Error(`轮询超时 (超过 ${timeout / 1000} 秒)`));
      return;
    }

    try {
      const report = await getReportDetails(reportId);

      if (onUpdate) {
        onUpdate(report);
      }

      if (report.status === 'completed') {
        clearInterval(pollingHandle);
        onSuccess(report);
      } else if (report.status === 'failed') {
        clearInterval(pollingHandle);
        onFailure(report);
      }
      // 如果状态是 'processing' 或 'submitted'，则继续轮询，不做任何事
    } catch (error) {
      clearInterval(pollingHandle);
      onFailure(error);
    }
  };

  // 立即执行一次，然后开始定时轮询
  poll();
  pollingHandle = window.setInterval(poll, interval);

  // 返回一个停止函数，允许外部手动停止轮询
  return () => {
    if (pollingHandle) {
      clearInterval(pollingHandle);
    }
  };
}