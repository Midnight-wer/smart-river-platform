import axios, { AxiosError, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import * as db from './data'
import type { PageResult } from '@/types'

/**
 * Mock 服务端
 * 以 axios 适配器的形式接管请求，使前端代码保持与真实后端一致的调用方式。
 * 关闭方式：设置环境变量 VITE_USE_MOCK=false。
 */

/**
 * 已接入真实后端的接口（YOLO 接入方案 §4.4）：
 * 命中后跳过 Mock 路由模拟，直接透传给真实 HTTP 适配器。
 * 通过 VITE_AI_REAL_DETECT 控制开关——后端未就绪时保持关闭继续走 Mock，
 * 就绪后设为 true 即切真实链路，其余接口不受影响。
 */
const USE_REAL_DETECT = import.meta.env.VITE_AI_REAL_DETECT === 'true'
const REAL_API_ROUTES: RegExp[] = [/^\/api\/ai\/camera\/recognize$/]
const httpAdapter: AxiosAdapter = axios.getAdapter(axios.defaults.adapter)

interface MockRoute {
  method: string
  pattern: string
  handler: (ctx: { params: Record<string, string>; query: Record<string, string>; body: any }) => unknown
}

function toRegExp(pattern: string): RegExp {
  const regex = pattern
    .replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    .replace(/:(\w+)/g, '(?<$1>[^/]+)')
  return new RegExp(`^${regex}$`)
}

function delay(min = 180, max = 420): Promise<void> {
  const ms = Math.floor(Math.random() * (max - min + 1)) + min
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function paginate<T>(list: T[], page = 1, pageSize = 10): PageResult<T> {
  const safePage = Math.max(1, Number(page) || 1)
  const safeSize = Math.max(1, Number(pageSize) || 10)
  const start = (safePage - 1) * safeSize
  return {
    list: list.slice(start, start + safeSize),
    total: list.length,
    page: safePage,
    pageSize: safeSize,
  }
}

function buildError(config: InternalAxiosRequestConfig, status: number, message: string): AxiosError {
  const response: AxiosResponse = {
    data: { code: status, message, data: null },
    status,
    statusText: message,
    headers: {},
    config,
  }
  return new AxiosError(message, String(status), config, {}, response)
}

/** 登录演示账号 */
const ACCOUNTS: Record<string, { password: string; name: string; role: string; roleName: string; level: string; regionCode: string; regionName: string; permissions: string[] }> = {
  admin: {
    password: '123456',
    name: '系统管理员',
    role: 'super_admin',
    roleName: '超级管理员',
    level: 'province',
    regionCode: '510000',
    regionName: '四川省',
    permissions: ['*'],
  },
  province: {
    password: '123456',
    name: '省河长',
    role: 'province',
    roleName: '省级河长',
    level: 'province',
    regionCode: '510000',
    regionName: '四川省',
    permissions: db.roles.find((r) => r.code === 'province')?.permissions ?? [],
  },
  city: {
    password: '123456',
    name: '市河长',
    role: 'city',
    roleName: '市级河长',
    level: 'city',
    regionCode: '510100',
    regionName: '成都市',
    permissions: db.roles.find((r) => r.code === 'city')?.permissions ?? [],
  },
  county: {
    password: '123456',
    name: '县河长',
    role: 'county',
    roleName: '县级河长',
    level: 'county',
    regionCode: '510107',
    regionName: '武侯区',
    permissions: db.roles.find((r) => r.code === 'county')?.permissions ?? [],
  },
  town: {
    password: '123456',
    name: '乡镇河长',
    role: 'town',
    roleName: '乡镇级河长',
    level: 'town',
    regionCode: '510107001',
    regionName: '簇桥街道',
    permissions: db.roles.find((r) => r.code === 'town')?.permissions ?? [],
  },
}

const routes: MockRoute[] = [
  /* ------------------------------ 认证 ------------------------------ */
  {
    method: 'post',
    pattern: '/api/auth/login',
    handler: ({ body }) => {
      const username = String(body?.username ?? '').trim()
      const password = String(body?.password ?? '')
      if (!username || !password) {
        throw new Error('用户名与密码不能为空')
      }
      const account = ACCOUNTS[username]
      if (!account || account.password !== password) {
        throw new Error('用户名或密码错误')
      }
      return {
        token: `mock-token-${username}-${Date.now()}`,
        expiresIn: 24 * 60 * 60,
      }
    },
  },
  {
    method: 'get',
    pattern: '/api/auth/profile',
    handler: ({ query }) => {
      const username = query.username ?? 'admin'
      const account = ACCOUNTS[username] ?? ACCOUNTS.admin
      return {
        id: `US-${username}`,
        username,
        name: account.name,
        avatar: '',
        role: account.role,
        roleName: account.roleName,
        level: account.level,
        regionCode: account.regionCode,
        regionName: account.regionName,
        phone: '138****8888',
        permissions: account.permissions,
      }
    },
  },
  { method: 'post', pattern: '/api/auth/logout', handler: () => ({ success: true }) },

  /* ---------------------------- 工作台 ------------------------------ */
  { method: 'get', pattern: '/api/dashboard/summary', handler: () => db.dashboardSummary },
  { method: 'get', pattern: '/api/dashboard/warns', handler: () => db.warns.slice(0, 10) },
  { method: 'get', pattern: '/api/dashboard/trend', handler: () => db.trendChart },
  {
    method: 'get',
    pattern: '/api/dashboard/charts',
    handler: () => ({
      riverLevel: db.riverLevelChart,
      eventType: db.eventTypeChart,
      chiefDuty: db.chiefDutyChart,
    }),
  },

  /* ---------------------------- 河道档案 ---------------------------- */
  {
    method: 'get',
    pattern: '/api/rivers',
    handler: ({ query }) => {
      const keyword = String(query.keyword ?? '').trim()
      let list = db.rivers
      if (keyword) {
        list = list.filter((item) =>
          [item.name, item.code, item.region, item.basin, item.chiefName].some((field) =>
            String(field).toLowerCase().includes(keyword.toLowerCase()),
          ),
        )
      }
      if (query.level) list = list.filter((item) => item.level === query.level)
      if (query.status) list = list.filter((item) => item.status === query.status)
      if (query.region) list = list.filter((item) => item.region === query.region)
      return paginate(list, Number(query.page), Number(query.pageSize))
    },
  },
  {
    method: 'get',
    pattern: '/api/rivers/:id',
    handler: ({ params }) => {
      const river = db.rivers.find((item) => item.id === params.id)
      if (!river) throw new Error('河道不存在或已被删除')
      return {
        ...river,
        history: db.waterTrend.slice(-6),
        events: db.events.filter((item) => item.riverName === river.name).slice(0, 5),
        patrols: db.patrolTasks.filter((item) => item.riverName === river.name).slice(0, 5),
      }
    },
  },
  {
    method: 'post',
    pattern: '/api/rivers',
    handler: ({ body }) => {
      const river = {
        ...body,
        id: `RV${String(db.rivers.length + 1).padStart(4, '0')}`,
        status: body.status ?? '正常',
        updatedAt: db.stamp(),
      }
      db.rivers.unshift(river as any)
      return river
    },
  },
  {
    method: 'put',
    pattern: '/api/rivers/:id',
    handler: ({ params, body }) => {
      const index = db.rivers.findIndex((item) => item.id === params.id)
      if (index < 0) throw new Error('河道不存在或已被删除')
      db.rivers[index] = { ...db.rivers[index], ...body, updatedAt: db.stamp() }
      return db.rivers[index]
    },
  },
  {
    method: 'delete',
    pattern: '/api/rivers/:id',
    handler: ({ params }) => {
      const index = db.rivers.findIndex((item) => item.id === params.id)
      if (index < 0) throw new Error('河道不存在或已被删除')
      db.rivers.splice(index, 1)
      return { success: true }
    },
  },

  /* ---------------------------- 河长管理 ---------------------------- */
  {
    method: 'get',
    pattern: '/api/chiefs',
    handler: ({ query }) => {
      const keyword = String(query.keyword ?? '').trim()
      let list = db.chiefs
      if (keyword) {
        list = list.filter((item) =>
          [item.name, item.region, item.post].some((field) =>
            String(field).toLowerCase().includes(keyword.toLowerCase()),
          ),
        )
      }
      if (query.level) list = list.filter((item) => item.level === query.level)
      return paginate(list, Number(query.page), Number(query.pageSize))
    },
  },
  {
    method: 'get',
    pattern: '/api/chiefs/portrait/:id',
    handler: ({ params }) => {
      const chief = db.chiefs.find((item) => item.id === params.id)
      if (!chief) throw new Error('河长信息不存在')
      return {
        ...chief,
        trend: db.trendChart,
        patrolRecords: db.patrolTasks.filter((item) => item.chiefName === chief.name).slice(0, 8),
        events: db.events.filter((item) => item.handler === chief.name).slice(0, 6),
      }
    },
  },

  /* ---------------------------- 巡查管理 ---------------------------- */
  {
    method: 'get',
    pattern: '/api/patrols',
    handler: ({ query }) => {
      const keyword = String(query.keyword ?? '').trim()
      let list = db.patrolTasks
      if (keyword) {
        list = list.filter((item) =>
          [item.title, item.riverName, item.chiefName].some((field) =>
            String(field).toLowerCase().includes(keyword.toLowerCase()),
          ),
        )
      }
      if (query.status) list = list.filter((item) => item.status === query.status)
      if (query.type) list = list.filter((item) => item.type === query.type)
      return paginate(list, Number(query.page), Number(query.pageSize))
    },
  },
  {
    method: 'post',
    pattern: '/api/patrols',
    handler: ({ body }) => {
      const task = {
        ...body,
        id: `PT${String(db.patrolTasks.length + 1).padStart(4, '0')}`,
        foundIssues: 0,
        distance: 0,
        duration: 0,
        createdAt: db.stamp(),
      }
      db.patrolTasks.unshift(task as any)
      return task
    },
  },
  {
    method: 'put',
    pattern: '/api/patrols/:id',
    handler: ({ params, body }) => {
      const index = db.patrolTasks.findIndex((item) => item.id === params.id)
      if (index < 0) throw new Error('巡查任务不存在')
      db.patrolTasks[index] = { ...db.patrolTasks[index], ...body }
      return db.patrolTasks[index]
    },
  },
  {
    method: 'delete',
    pattern: '/api/patrols/:id',
    handler: ({ params }) => {
      const index = db.patrolTasks.findIndex((item) => item.id === params.id)
      if (index < 0) throw new Error('巡查任务不存在')
      db.patrolTasks.splice(index, 1)
      return { success: true }
    },
  },

  /* ---------------------------- 水质监测 ---------------------------- */
  { method: 'get', pattern: '/api/water/stations', handler: () => db.stations },
  {
    method: 'get',
    pattern: '/api/water/records',
    handler: ({ query }) => {
      const keyword = String(query.keyword ?? '').trim()
      let list = db.waterRecords
      if (keyword) {
        list = list.filter((item) =>
          [item.stationName, item.riverName].some((field) =>
            String(field).toLowerCase().includes(keyword.toLowerCase()),
          ),
        )
      }
      if (query.status) list = list.filter((item) => item.status === query.status)
      if (query.grade) list = list.filter((item) => item.grade === query.grade)
      return paginate(list, Number(query.page), Number(query.pageSize))
    },
  },
  { method: 'get', pattern: '/api/water/trend', handler: () => db.waterTrend },
  {
    method: 'get',
    pattern: '/api/water/indicators',
    handler: () => ({
      ph: { name: 'pH 值', unit: '', standard: '6 ~ 9', min: 6, max: 9 },
      do: { name: '溶解氧', unit: 'mg/L', standard: '≥ 5', min: 5, max: 100 },
      nh3n: { name: '氨氮', unit: 'mg/L', standard: '≤ 1.5', min: 0, max: 2 },
      cod: { name: '化学需氧量', unit: 'mg/L', standard: '≤ 20', min: 0, max: 30 },
      tp: { name: '总磷', unit: 'mg/L', standard: '≤ 0.1', min: 0, max: 0.3 },
      tn: { name: '总氮', unit: 'mg/L', standard: '≤ 1.5', min: 0, max: 3 },
    }),
  },

  /* ----------------------------- 事件中心 ---------------------------- */
  {
    method: 'get',
    pattern: '/api/events',
    handler: ({ query }) => {
      const keyword = String(query.keyword ?? '').trim()
      let list = db.events
      if (keyword) {
        list = list.filter((item) =>
          [item.title, item.riverName, item.handler, item.reporter].some((field) =>
            String(field).toLowerCase().includes(keyword.toLowerCase()),
          ),
        )
      }
      if (query.status) list = list.filter((item) => item.status === query.status)
      if (query.type) list = list.filter((item) => item.type === query.type)
      return paginate(list, Number(query.page), Number(query.pageSize))
    },
  },
  {
    method: 'get',
    pattern: '/api/events/:id',
    handler: ({ params }) => {
      const event = db.events.find((item) => item.id === params.id)
      if (!event) throw new Error('事件不存在或已被删除')
      return event
    },
  },
  {
    method: 'post',
    pattern: '/api/events',
    handler: ({ body }) => {
      const event = {
        ...body,
        id: `EV${String(db.events.length + 1).padStart(4, '0')}`,
        status: body.status ?? '待处理',
        logs: [],
      }
      db.events.unshift(event as any)
      return event
    },
  },
  {
    method: 'put',
    pattern: '/api/events/:id',
    handler: ({ params, body }) => {
      const index = db.events.findIndex((item) => item.id === params.id)
      if (index < 0) throw new Error('事件不存在或已被删除')
      db.events[index] = { ...db.events[index], ...body }
      return db.events[index]
    },
  },
  {
    method: 'post',
    pattern: '/api/events/:id/logs',
    handler: ({ params, body }) => {
      const event = db.events.find((item) => item.id === params.id)
      if (!event) throw new Error('事件不存在或已被删除')
      const log = {
        id: `EL${String(event.logs.length + 1).padStart(4, '0')}`,
        operator: body?.operator ?? '系统',
        action: body?.action ?? '处理中',
        remark: body?.remark ?? '',
        time: db.stamp(),
      }
      event.logs.unshift(log)
      return log
    },
  },

  /* ----------------------------- 考核管理 ---------------------------- */
  {
    method: 'get',
    pattern: '/api/assessments',
    handler: ({ query }) => {
      const keyword = String(query.keyword ?? '').trim()
      let list = db.assessments
      if (keyword) {
        list = list.filter((item) => item.chiefName.includes(keyword))
      }
      if (query.level) list = list.filter((item) => item.level === query.level)
      return paginate(list, Number(query.page), Number(query.pageSize))
    },
  },
  {
    method: 'get',
    pattern: '/api/assessments/indicators',
    handler: () => [
      { key: 'patrolRate', name: '巡查完成率', weight: 30 },
      { key: 'resolveRate', name: '问题处理率', weight: 25 },
      { key: 'qualityRate', name: '水质达标率', weight: 25 },
      { key: 'responseTime', name: '响应时效', weight: 10 },
      { key: 'satisfaction', name: '公众满意度', weight: 10 },
    ],
  },

  /* ----------------------------- 公众服务 ---------------------------- */
  {
    method: 'get',
    pattern: '/api/public/reports',
    handler: ({ query }) => {
      const keyword = String(query.keyword ?? '').trim()
      let list = db.publicReports
      if (keyword) {
        list = list.filter((item) =>
          [item.title, item.riverName, item.reporter].some((field) =>
            String(field).toLowerCase().includes(keyword.toLowerCase()),
          ),
        )
      }
      if (query.status) list = list.filter((item) => item.status === query.status)
      return paginate(list, Number(query.page), Number(query.pageSize))
    },
  },
  {
    method: 'put',
    pattern: '/api/public/reports/:id',
    handler: ({ params, body }) => {
      const index = db.publicReports.findIndex((item) => item.id === params.id)
      if (index < 0) throw new Error('举报记录不存在')
      db.publicReports[index] = { ...db.publicReports[index], ...body }
      return db.publicReports[index]
    },
  },

  /* ----------------------------- 系统管理 ---------------------------- */
  {
    method: 'get',
    pattern: '/api/system/users',
    handler: ({ query }) => {
      const keyword = String(query.keyword ?? '').trim()
      let list = db.sysUsers
      if (keyword) {
        list = list.filter((item) =>
          [item.username, item.name, item.phone].some((field) =>
            String(field).toLowerCase().includes(keyword.toLowerCase()),
          ),
        )
      }
      if (query.status) list = list.filter((item) => item.status === query.status)
      return paginate(list, Number(query.page), Number(query.pageSize))
    },
  },
  {
    method: 'post',
    pattern: '/api/system/users',
    handler: ({ body }) => {
      const user = { ...body, id: `US${String(db.sysUsers.length + 1).padStart(4, '0')}`, createdAt: db.stamp(), lastLoginAt: '-' }
      db.sysUsers.unshift(user as any)
      return user
    },
  },
  {
    method: 'put',
    pattern: '/api/system/users/:id',
    handler: ({ params, body }) => {
      const index = db.sysUsers.findIndex((item) => item.id === params.id)
      if (index < 0) throw new Error('用户不存在')
      db.sysUsers[index] = { ...db.sysUsers[index], ...body }
      return db.sysUsers[index]
    },
  },
  {
    method: 'delete',
    pattern: '/api/system/users/:id',
    handler: ({ params }) => {
      const index = db.sysUsers.findIndex((item) => item.id === params.id)
      if (index < 0) throw new Error('用户不存在')
      db.sysUsers.splice(index, 1)
      return { success: true }
    },
  },
  { method: 'get', pattern: '/api/system/orgs', handler: () => db.orgs },
  { method: 'get', pattern: '/api/system/roles', handler: () => db.roles },
  { method: 'get', pattern: '/api/system/dicts', handler: () => db.dictItems },
  {
    method: 'get',
    pattern: '/api/system/logs',
    handler: ({ query }) => {
      const keyword = String(query.keyword ?? '').trim()
      let list = db.operationLogs
      if (keyword) {
        list = list.filter((item) =>
          [item.operator, item.module, item.action].some((field) =>
            String(field).toLowerCase().includes(keyword.toLowerCase()),
          ),
        )
      }
      if (query.status) list = list.filter((item) => item.status === query.status)
      return paginate(list, Number(query.page), Number(query.pageSize))
    },
  },
  { method: 'get', pattern: '/api/system/devices', handler: () => db.devices },

  /* ----------------------------- AI 溯源 ----------------------------- */
  { method: 'get', pattern: '/api/ai/diffusion', handler: () => db.aiDiffusionPoints },
  { method: 'get', pattern: '/api/ai/fingerprint', handler: () => db.aiFingerprints },
  { method: 'get', pattern: '/api/ai/compare', handler: () => db.aiCompareRows },
  { method: 'get', pattern: '/api/ai/source', handler: () => db.aiFingerprints.map((item) => ({ ...item, distance: Math.round(item.risk / 7) })) },
  { method: 'get', pattern: '/api/ai/detection', handler: () => db.aiDetections },
  { method: 'get', pattern: '/api/ai/prediction', handler: () => db.aiPrediction },
  { method: 'get', pattern: '/api/ai/tracing', handler: () => db.aiTracing },
  { method: 'get', pattern: '/api/ai/evaluation', handler: () => db.aiEvaluation },
  {
    method: 'post',
    pattern: '/api/ai/camera/recognize',
    handler: ({ body }) => db.buildCameraRecognition(String(body?.scene ?? 'camera')),
  },
]

/**
 * 解析请求候选路径
 * axios 的适配器收到的 config.url 不含 baseURL，且 baseURL 可能是绝对地址，
 * 这里统一还原出 '/api/xxx' 形式的路径用于路由匹配。
 */
function resolveCandidates(config: InternalAxiosRequestConfig): string[] {
  const raw = config.url ?? ''
  const base = config.baseURL ?? ''
  const list: string[] = []

  const push = (value: string): void => {
    const path = value.split('?')[0].split('#')[0]
    if (path && !list.includes(path)) list.push(path)
  }

  const join = (prefix: string, target: string): string => {
    if (!prefix) return target
    if (target.startsWith(prefix)) return target
    return `${prefix.replace(/\/+$/, '')}/${target.replace(/^\/+/, '')}`
  }

  push(raw)
  push(join(base, raw))

  // 绝对地址时取其 pathname
  for (const value of [raw, join(base, raw)]) {
    try {
      push(new URL(value, 'http://localhost').pathname)
    } catch {
      /* 忽略非法地址 */
    }
  }

  return list
}

function matchRoute(config: InternalAxiosRequestConfig) {
  const method = (config.method ?? 'get').toLowerCase()
  const candidates = resolveCandidates(config)
  for (const route of routes) {
    if (route.method !== method) continue
    const reg = toRegExp(route.pattern)
    for (const candidate of candidates) {
      const matched = reg.exec(candidate)
      if (!matched) continue
      return { route, params: (matched.groups ?? {}) as Record<string, string> }
    }
  }
  return null
}

function parseBody(config: InternalAxiosRequestConfig): any {
  const raw = config.data
  if (!raw) return {}
  // multipart 表单：展开为普通对象供 handler 读取字段
  if (typeof FormData !== 'undefined' && raw instanceof FormData) {
    const form: Record<string, unknown> = {}
    raw.forEach((value, key) => {
      form[key] = value
    })
    return form
  }
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw)
    } catch {
      return {}
    }
  }
  return raw
}

/** axios 适配器实现 */
export async function mockAdapter(config: InternalAxiosRequestConfig): Promise<AxiosResponse> {
  // 真实接口透传：不加 Mock 延迟，直接走 HTTP
  const candidates = resolveCandidates(config)
  if (USE_REAL_DETECT && REAL_API_ROUTES.some((pattern) => candidates.some((c) => pattern.test(c)))) {
    return httpAdapter(config)
  }

  await delay()

  const matched = matchRoute(config)
  if (!matched) {
    return Promise.reject(buildError(config, 404, `接口不存在：${config.method?.toUpperCase()} ${config.url}`))
  }

  try {
    const data = matched.route.handler({
      params: matched.params,
      query: (config.params ?? {}) as Record<string, string>,
      body: parseBody(config),
    })
    return {
      data: { code: 200, message: 'success', data },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    } as AxiosResponse
  } catch (error) {
    const message = error instanceof Error ? error.message : '服务处理失败'
    return Promise.reject(buildError(config, 500, message))
  }
}
