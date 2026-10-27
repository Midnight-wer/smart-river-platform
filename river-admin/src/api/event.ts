import { get, post, put } from './request'
import type { EventLog, PageQuery, PageResult, RiverEvent } from '@/types'

/** 事件列表 */
export function fetchEvents(query: PageQuery): Promise<PageResult<RiverEvent>> {
  return get<PageResult<RiverEvent>>('/events', query as Record<string, unknown>)
}

/** 事件详情 */
export function fetchEventDetail(id: string): Promise<RiverEvent> {
  return get<RiverEvent>(`/events/${id}`)
}

/** 上报事件 */
export function createEvent(data: Partial<RiverEvent>): Promise<RiverEvent> {
  return post<RiverEvent>('/events', data)
}

/** 更新事件（分派、状态流转等） */
export function updateEvent(id: string, data: Partial<RiverEvent>): Promise<RiverEvent> {
  return put<RiverEvent>(`/events/${id}`, data)
}

/** 追加事件处理记录 */
export function createEventLog(id: string, data: Partial<EventLog>): Promise<EventLog> {
  return post<EventLog>(`/events/${id}/logs`, data)
}
