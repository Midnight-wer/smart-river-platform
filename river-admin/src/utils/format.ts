import dayjs from 'dayjs'

/** 格式化日期时间 */
export function formatDateTime(value?: string | number | Date, template = 'YYYY-MM-DD HH:mm'): string {
  if (value === undefined || value === null || value === '') return '-'
  const date = dayjs(value)
  return date.isValid() ? date.format(template) : '-'
}

/** 格式化日期 */
export function formatDate(value?: string | number | Date): string {
  return formatDateTime(value, 'YYYY-MM-DD')
}

/** 相对时间描述 */
export function fromNow(value?: string | number | Date): string {
  if (!value) return '-'
  const date = dayjs(value)
  if (!date.isValid()) return '-'
  const diff = dayjs().diff(date, 'minute')
  if (diff < 1) return '刚刚'
  if (diff < 60) return `${diff} 分钟前`
  if (diff < 60 * 24) return `${Math.floor(diff / 60)} 小时前`
  if (diff < 60 * 24 * 30) return `${Math.floor(diff / (60 * 24))} 天前`
  return date.format('YYYY-MM-DD')
}

/** 保留指定小数位（默认两位） */
export function toFixed(value: number | undefined | null, digits = 2): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '-'
  return value.toFixed(digits)
}

/** 百分比展示 */
export function toPercent(value: number | undefined | null, digits = 1): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '-'
  return `${value.toFixed(digits)}%`
}

/** 数值千分位 */
export function toNumber(value: number | undefined | null): string {
  if (value === undefined || value === null || Number.isNaN(value)) return '-'
  return value.toLocaleString('zh-CN')
}

/** 里程展示（米 → km） */
export function toDistance(meters: number | undefined | null): string {
  if (!meters) return '0 km'
  return `${(meters / 1000).toFixed(1)} km`
}

/** 空值兜底 */
export function defaultText(value: unknown, fallback = '-'): string {
  if (value === undefined || value === null || value === '') return fallback
  return String(value)
}

/** 根据数据量生成序号，如 A-001 */
export function buildCode(prefix: string, index: number, padding = 3): string {
  return `${prefix}-${String(index).padStart(padding, '0')}`
}
