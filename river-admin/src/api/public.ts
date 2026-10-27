import { get, put } from './request'
import type { PageQuery, PageResult, PublicReport } from '@/types'

/** 公众举报列表 */
export function fetchReports(query: PageQuery): Promise<PageResult<PublicReport>> {
  return get<PageResult<PublicReport>>('/public/reports', query as Record<string, unknown>)
}

/** 审核举报并结算积分 */
export function reviewReport(id: string, data: { status: PublicReport['status']; reward?: number }): Promise<PublicReport> {
  return put<PublicReport>(`/public/reports/${id}`, data)
}
