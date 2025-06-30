/**
 * @file src/api/analysisApi.ts
 * @description 提供分析报告相关的 API 调用，包括列表查询、详情获取、提交任务、删除与重试操作
 * @author Hellohistory
 */

/**
 * @module api/analysisApi
 * 高内聚：仅负责分析报告的网络请求
 * 低耦合：依赖通用 apiClient，与业务逻辑及 UI 分离
 */

import apiClient from './apiClient';
import type {
  IAnalysisReport,
  IAnalysisReportDetail,
  IAnalysisSubmissionRequest,
  IComparisonReportRequest,
  IFullReport,
  IClassReportData,
  IStudentReportData,
} from '@/types/dataModels';

/**
 * 获取报告列表的请求参数类型
 */
export interface IGetReportsParams {
  /** 当前页码，默认 1 */
  page?: number;
  /** 每页条数，默认 10 */
  pageSize?: number;
  /** 按报告名称或关键字搜索 */
  query?: string;
  /** 按状态过滤，例如 'completed'、'processing' */
  status?: string;
  /** 按报告类型过滤，例如 'single', 'comparison' */
  report_type?: string;
}

/**
 * 后端返回的分页数据结构类型
 * @template T - 列表项类型
 */
export interface IPaginatedResponse<T> {
  /** 列表数据 */
  items: T[];
  /** 总条数 */
  total: number;
  /** 当前页码 */
  page: number;
  /** 每页条数 */
  pageSize: number;
}

/**
 * 提交分析任务的响应类型
 */
export interface ISubmitResponse {
  /** 返回消息 */
  message: string;
  /** 新建报告的 ID */
  report_id: number;
}


// --- API 实现 ---

const BASE_PATH = '/analysis';

/**
 * 获取分析报告列表（支持分页、搜索、筛选）
 * @param params - 分页与筛选参数
 * @returns Promise<IPaginatedResponse<IAnalysisReport>>
 */
export const getReports = async (
  params: IGetReportsParams,
): Promise<IPaginatedResponse<IAnalysisReport>> => {
  const response = await apiClient.get<IPaginatedResponse<IAnalysisReport>>(
    `${BASE_PATH}/reports`,
    { params },
  );
  return response.data;
};

/**
 * 根据报告 ID 获取单个分析报告的元数据和完整结果
 * @param id - 报告 ID
 * @returns Promise<IAnalysisReportDetail>
 */
export const getReportDetails = async (
  id: number,
): Promise<IAnalysisReportDetail> => {
  const response = await apiClient.get<IAnalysisReportDetail>(
    `${BASE_PATH}/reports/${id}`,
  );
  return response.data;
};

/**
 * 提交一个新的单场考试分析任务
 * @param submissionData - 包含考试 ID、报告名称与分析范围的请求体
 * @returns Promise<ISubmitResponse>
 */
export const submitAnalysisJob = async (
  submissionData: IAnalysisSubmissionRequest,
): Promise<ISubmitResponse> => {
  const response = await apiClient.post<ISubmitResponse>(
    `${BASE_PATH}/submit`,
    submissionData,
  );
  return response.data;
};

/**
 * 提交一个新的对比分析任务
 * @param submissionData - 包含报告名称与源报告ID列表
 * @returns Promise<ISubmitResponse>
 */
export const submitComparisonJob = async (
  submissionData: IComparisonReportRequest,
): Promise<ISubmitResponse> => {
  const response = await apiClient.post<ISubmitResponse>(
    `${BASE_PATH}/compare`,
    submissionData,
  );
  return response.data;
};

/**
 * 删除一个分析报告
 * @param id - 要删除的报告 ID
 * @returns Promise<void>
 */
export const deleteReport = async (id: number): Promise<void> => {
  await apiClient.delete(`${BASE_PATH}/reports/${id}`);
};

/**
 * 重试一个失败的分析任务
 * @param id - 要重试的报告 ID
 * @returns Promise<ISubmitResponse>
 */
export const retryAnalysis = async (id: number): Promise<ISubmitResponse> => {
  const response = await apiClient.post<ISubmitResponse>(`${BASE_PATH}/reports/${id}/retry`);
  return response.data;
};

/**
 * 为报告生成或获取AI分析摘要
 * @param reportId - 报告 ID
 * @returns Promise<{ analysis: string; source: string }>
 */
export const generateAiAnalysis = async (reportId: number): Promise<{ analysis: string; source: string }> => {
  const response = await apiClient.post(`${BASE_PATH}/reports/${reportId}/ai-analysis`);
  return response.data;
};


// --- 新增的细粒度数据获取 API ---

/**
 * 从指定报告中获取顶层（年级）的统计数据
 * @param reportId - 报告 ID
 * @returns Promise<IFullReport['groupStats']>
 */
export const getGroupStatsFromReport = async (reportId: number): Promise<IFullReport['groupStats']> => {
    const response = await apiClient.get(`${BASE_PATH}/reports/${reportId}/group-stats`);
    return response.data;
};

/**
 * 从指定报告中获取某个班级的详细数据
 * @param reportId - 报告 ID
 * @param className - 班级名称
 * @returns Promise<IClassReportData>
 */
export const getClassReportFromReport = async (reportId: number, className: string): Promise<IClassReportData> => {
    const response = await apiClient.get(`${BASE_PATH}/reports/${reportId}/class/${className}`);
    return response.data;
};

/**
 * 从指定报告中获取某个学生的详细数据
 * @param reportId - 报告 ID
 * @param studentName - 学生名称
 * @returns Promise<IStudentReportData>
 */
export const getStudentReportFromReport = async (reportId: number, studentName: string): Promise<IStudentReportData> => {
    const response = await apiClient.get(`${BASE_PATH}/reports/${reportId}/student/${studentName}`);
    return response.data;
};

/**
 * 为指定报告实时获取用于渲染的图表数据
 * @param reportId - 报告 ID
 * @returns Promise<any>
 */
export const getChartDataForReport = async (reportId: number): Promise<any> => {
    const response = await apiClient.get(`${BASE_PATH}/reports/${reportId}/charts`);
    return response.data;
};