import { get } from './request'
import type { Assessment, PageQuery, PageResult } from '@/types'

export interface AssessmentIndicator {
  key: string
  name: string
  weight: number
}

/** 考核结果列表 */
export function fetchAssessments(query: PageQuery): Promise<PageResult<Assessment>> {
  return get<PageResult<Assessment>>('/assessments', query as Record<string, unknown>)
}

/** 考核指标与权重 */
export function fetchIndicators(): Promise<AssessmentIndicator[]> {
  return get<AssessmentIndicator[]>('/assessments/indicators')
}
