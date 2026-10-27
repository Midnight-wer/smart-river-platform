/**
 * 全局类型定义
 * 项目：智河通 —— 智慧河长协同治理平台
 */

/** 统一响应结构 */
export interface ApiResult<T = unknown> {
  code: number
  message: string
  data: T
}

/** 分页请求参数 */
export interface PageQuery {
  page: number
  pageSize: number
  keyword?: string
  [key: string]: unknown
}

/** 分页响应结构 */
export interface PageResult<T> {
  list: T[]
  total: number
  page: number
  pageSize: number
}

/** 登录参数 */
export interface LoginParams {
  username: string
  password: string
  remember?: boolean
}

/** 登录结果 */
export interface LoginResult {
  token: string
  expiresIn: number
}

/** 用户信息 */
export interface UserInfo {
  id: string
  username: string
  name: string
  avatar: string
  role: RoleCode
  roleName: string
  /** 行政层级 */
  level: AdminLevel
  /** 所属区域编码 */
  regionCode: string
  regionName: string
  phone: string
  permissions: string[]
}

/** 角色编码 */
export type RoleCode = 'super_admin' | 'province' | 'city' | 'county' | 'town'

/** 行政层级 */
export type AdminLevel = 'province' | 'city' | 'county' | 'town'

/** 河道等级 */
export type RiverLevel = '省级' | '市级' | '县级' | '乡镇级'

/** 事件状态 */
export type EventStatus = '待处理' | '处理中' | '已完成' | '已归档' | '已驳回' | '已关闭'

/** 事件类型 */
export type EventType = '水质异常' | '漂浮物' | '违规排污' | '堤岸损坏' | '其他事件'

/** 河道档案 */
export interface River {
  id: string
  name: string
  code: string
  level: RiverLevel
  length: number
  basin: string
  region: string
  startPoint: string
  endPoint: string
  chiefName: string
  qualityTarget: string
  qualityRate: number
  patrolCount: number
  eventCount: number
  status: '正常' | '预警' | '停用'
  updatedAt: string
}

/** 河长档案 */
export interface Chief {
  id: string
  name: string
  phone: string
  level: AdminLevel
  levelName: string
  region: string
  post: string
  riverCount: number
  patrolRate: number
  resolveRate: number
  score: number
  status: '在岗' | '离岗'
  lastPatrolAt: string
}

/** 巡查任务 */
export interface PatrolTask {
  id: string
  title: string
  riverName: string
  chiefName: string
  level: AdminLevel
  type: '日常巡查' | '专项巡查' | '整改复查' | '汛期排查'
  status: '待执行' | '进行中' | '已完成' | '已逾期'
  duration: number
  distance: number
  foundIssues: number
  assignee: string
  deadline: string
  createdAt: string
}

/** 水质监测站点 */
export interface WaterStation {
  id: string
  name: string
  code: string
  riverName: string
  region: string
  deviceType: string
  online: boolean
  lastReportAt: string
}

/** 水质实时数据 */
export interface WaterRecord {
  id: string
  stationName: string
  riverName: string
  ph: number
  do: number
  nh3n: number
  cod: number
  tp: number
  tn: number
  /** 水质类别 Ⅰ ~ Ⅴ */
  grade: string
  status: '正常' | '预警' | '超标'
  collectAt: string
}

/** 水质历史趋势点 */
export interface WaterTrendPoint {
  date: string
  ph: number
  do: number
  cod: number
  nh3n: number
}

/** 事件 */
export interface RiverEvent {
  id: string
  title: string
  type: EventType
  status: EventStatus
  level: '一般' | '较大' | '重大'
  riverName: string
  region: string
  reporter: string
  handler: string
  occurAt: string
  deadline: string
  description: string
  logs: EventLog[]
}

/** 事件处理记录 */
export interface EventLog {
  id: string
  operator: string
  action: string
  remark: string
  time: string
}

/** 预警信息 */
export interface WarnInfo {
  id: string
  title: string
  type: '水质预警' | '事件预警' | '设备离线' | '超期预警'
  level: '提示' | '警告' | '严重'
  target: string
  time: string
}

/** 考核记录 */
export interface Assessment {
  id: string
  name: string
  chiefName: string
  level: AdminLevel
  levelName: string
  region: string
  period: string
  patrolRate: number
  resolveRate: number
  qualityRate: number
  responseTime: number
  satisfaction: number
  totalScore: number
  rank: number
}

/** 公众举报 */
export interface PublicReport {
  id: string
  title: string
  content: string
  riverName: string
  region: string
  reporter: string
  phone: string
  status: '待审核' | '已受理' | '已办结' | '已驳回'
  reward: number
  submitAt: string
}

/** 系统用户 */
export interface SysUser {
  id: string
  username: string
  name: string
  roleName: string
  orgName: string
  phone: string
  status: '启用' | '禁用'
  lastLoginAt: string
  createdAt: string
}

/** 组织架构 */
export interface SysOrg {
  id: string
  name: string
  code: string
  parentName: string
  leader: string
  phone: string
  sort: number
  memberCount: number
  status: '正常' | '停用'
}

/** 角色 */
export interface SysRole {
  id: string
  name: string
  code: string
  level: AdminLevel
  dataScope: string
  memberCount: number
  permissions: string[]
  status: '启用' | '停用'
  createdAt: string
}

/** 数据字典 */
export interface DictItem {
  id: string
  type: string
  typeLabel: string
  label: string
  value: string
  sort: number
  status: '启用' | '停用'
}

/** 操作日志 */
export interface OperationLog {
  id: string
  operator: string
  module: string
  action: string
  ip: string
  duration: number
  status: '成功' | '失败'
  createdAt: string
}

/** 设备 */
export interface Device {
  id: string
  name: string
  code: string
  type: '无人机' | '监控设备' | '水质监测站' | '雨量站' | '浮标'
  region: string
  status: '在线' | '离线' | '维护中'
  battery: number
  lastOnlineAt: string
}

/** 菜单项 */
export interface MenuItem {
  index: string
  title: string
  icon?: unknown
  permission?: string | string[]
  children?: MenuItem[]
}

/** 图表通用项 */
export interface ChartItem {
  name: string
  value: number
}
