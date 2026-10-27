import type {
  Assessment,
  ChartItem,
  Chief,
  Device,
  DictItem,
  EventLog,
  OperationLog,
  PatrolTask,
  PublicReport,
  River,
  RiverEvent,
  SysOrg,
  SysRole,
  SysUser,
  WarnInfo,
  WaterRecord,
  WaterStation,
  WaterTrendPoint,
} from '@/types'

/**
 * 模拟数据源
 * 使用固定种子的伪随机数，保证每次启动生成的数据保持一致，便于联调与演示。
 */

let seed = 20240501

function random(): number {
  seed = (seed * 9301 + 49297) % 233280
  return seed / 233280
}

function randomInt(min: number, max: number): number {
  return Math.floor(random() * (max - min + 1)) + min
}

function pick<T>(list: readonly T[]): T {
  return list[Math.floor(random() * list.length)]
}

function pad(value: number, length = 2): string {
  return String(value).padStart(length, '0')
}

/** 生成近 n 个月的日期字符串 */
function recentMonths(n: number): string[] {
  const base = new Date()
  const list: string[] = []
  for (let i = n - 1; i >= 0; i--) {
    const date = new Date(base.getFullYear(), base.getMonth() - i, 1)
    list.push(`${date.getFullYear()}-${pad(date.getMonth() + 1)}`)
  }
  return list
}

function recentDays(n: number): string[] {
  const base = new Date()
  const list: string[] = []
  for (let i = n - 1; i >= 0; i--) {
    const date = new Date(base.getFullYear(), base.getMonth(), base.getDate() - i)
    list.push(`${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`)
  }
  return list
}

function stamp(offsetMinutes = 0): string {
  const date = new Date(Date.now() + offsetMinutes * 60_000)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/* -------------------------------------------------------------------------- */
/* 河道档案                                                                    */
/* -------------------------------------------------------------------------- */

const RIVER_NAMES = [
  '岷江', '沱江', '涪江', '嘉陵江', '金沙江', '雅砻江', '大渡河', '青衣江',
  '渠江', '州河', '涪江', '泸水', '安宁河', '西昌河', '文井江', '江安河',
  '釜溪河', '杂谷脑河', '通口河', '武都河', '西河', '东河', '小溪河', '梅江',
]

const BASINS = ['岷江流域', '沱江流域', '嘉陵江流域', '金沙江流域', '雅砻江流域', '长江干流']
const REGIONS = ['成都市', '德阳市', '绵阳市', '乐山市', '宜宾市', '泸州市', '南充市', '眉山市']
const QUALITY_TARGETS = ['Ⅰ类', 'Ⅱ类', 'Ⅲ类', 'Ⅳ类']

export const rivers: River[] = RIVER_NAMES.map((name, index) => {
  const level = (['省级', '市级', '县级', '乡镇级'] as const)[index % 4]
  const qualityRate = randomInt(72, 100)
  return {
    id: `RV${pad(index + 1, 4)}`,
    name: index < RIVER_NAMES.length - 4 ? `${name}干流` : `${name}支流`,
    code: `SC-HD-${pad(index + 1, 4)}`,
    level,
    length: randomInt(15, 320),
    basin: pick(BASINS),
    region: pick(REGIONS),
    startPoint: `${pick(REGIONS)}${pick(['县城', '镇', '乡'])}`,
    endPoint: `${pick(REGIONS)}${pick(['镇', '乡', '街道办'])}`,
    chiefName: `${pick(['张', '王', '李', '赵', '陈', '刘'])}${pick(['建国', '明辉', '志强', '晓东', '文彬', '海燕'])}`,
    qualityTarget: pick(QUALITY_TARGETS),
    qualityRate,
    patrolCount: randomInt(6, 88),
    eventCount: randomInt(0, 12),
    status: qualityRate < 80 ? '预警' : '正常',
    updatedAt: stamp(-randomInt(60, 20000)),
  }
})

/* -------------------------------------------------------------------------- */
/* 河长档案                                                                    */
/* -------------------------------------------------------------------------- */

const LEVEL_NAME: Record<string, string> = {
  province: '省级河长',
  city: '市级河长',
  county: '县级河长',
  town: '乡镇级河长',
}

export const chiefs: Chief[] = Array.from({ length: 18 }, (_, index) => {
  const level = (['province', 'city', 'county', 'town'] as const)[index % 4]
  const patrolRate = randomInt(62, 100)
  const resolveRate = randomInt(58, 100)
  return {
    id: `CH${pad(index + 1, 4)}`,
    name: `${pick(['张', '王', '李', '赵', '陈', '刘', '杨', '黄'])}${pick(['建国', '明辉', '志强', '晓东', '文彬', '海燕', '秀英', '俊杰'])}`,
    phone: `1${pick(['3', '5', '7', '8'])}${randomInt(100000000, 999999999)}`,
    level,
    levelName: LEVEL_NAME[level],
    region: pick(REGIONS),
    post: level === 'province' ? '省河长办公室副主任' : level === 'city' ? '市水务局副局长' : level === 'county' ? '县河长制办公室主任' : '乡镇党委书记',
    riverCount: randomInt(2, 18),
    patrolRate,
    resolveRate,
    score: Number(((patrolRate + resolveRate) / 2).toFixed(1)),
    status: random() > 0.85 ? '离岗' : '在岗',
    lastPatrolAt: stamp(-randomInt(30, 8000)),
  }
})

/* -------------------------------------------------------------------------- */
/* 巡查任务                                                                    */
/* -------------------------------------------------------------------------- */

const PATROL_TYPES = ['日常巡查', '专项巡查', '整改复查', '汛期排查'] as const
const PATROL_STATUS = ['待执行', '进行中', '已完成', '已逾期'] as const

export const patrolTasks: PatrolTask[] = Array.from({ length: 28 }, (_, index) => {
  const river = pick(rivers)
  const chief = pick(chiefs)
  const status = pick(PATROL_STATUS)
  return {
    id: `PT${pad(index + 1, 4)}`,
    title: `${river.name}${pick(['段', '支流', '上游', '下游'])}巡查任务`,
    riverName: river.name,
    chiefName: chief.name,
    level: chief.level,
    type: pick(PATROL_TYPES),
    status,
    duration: randomInt(45, 300),
    distance: randomInt(3000, 42000),
    foundIssues: status === '已完成' ? randomInt(0, 6) : 0,
    assignee: chief.name,
    deadline: stamp(randomInt(1440, 10080)),
    createdAt: stamp(-randomInt(120, 9000)),
  }
})

/* -------------------------------------------------------------------------- */
/* 水质监测                                                                    */
/* -------------------------------------------------------------------------- */

export const stations: WaterStation[] = Array.from({ length: 14 }, (_, index) => {
  const river = pick(rivers)
  const online = random() > 0.15
  return {
    id: `WS${pad(index + 1, 4)}`,
    name: `${river.name}${pick(['断面', '桥头', '入河口', '镇区'])}监测站`,
    code: `SC-WQ-${pad(index + 1, 4)}`,
    riverName: river.name,
    region: river.region,
    deviceType: pick(['自动站', '微型站', '手动采样点']),
    online,
    lastReportAt: online ? stamp(-randomInt(1, 30)) : stamp(-randomInt(600, 5000)),
  }
})

function calcGrade(do_: number, nh3n: number, cod: number): string {
  if (do_ >= 6 && nh3n <= 1 && cod <= 15) return 'Ⅰ类'
  if (do_ >= 5 && nh3n <= 1.5 && cod <= 20) return 'Ⅱ类'
  if (do_ >= 3 && nh3n <= 2 && cod <= 30) return 'Ⅲ类'
  if (do_ >= 2 && nh3n <= 3 && cod <= 40) return 'Ⅳ类'
  return 'Ⅴ类'
}

export const waterRecords: WaterRecord[] = Array.from({ length: 36 }, (_, index) => {
  const station = pick(stations)
  const do_ = Number((randomInt(28, 95) / 10).toFixed(2))
  const nh3n = Number((randomInt(5, 260) / 100).toFixed(2))
  const cod = Number((randomInt(80, 420) / 10).toFixed(2))
  const grade = calcGrade(do_, nh3n, cod)
  const status = grade === 'Ⅳ类' || grade === 'Ⅴ类' ? '超标' : grade === 'Ⅲ类' ? '预警' : '正常'
  return {
    id: `WR${pad(index + 1, 4)}`,
    stationName: station.name,
    riverName: station.riverName,
    ph: Number((randomInt(60, 90) / 10).toFixed(2)),
    do: do_,
    nh3n,
    cod,
    tp: Number((randomInt(5, 60) / 100).toFixed(3)),
    tn: Number((randomInt(80, 450) / 100).toFixed(2)),
    grade,
    status,
    collectAt: stamp(-randomInt(5, 2880)),
  }
})

/** 各等级河道近 12 个月水质趋势 */
export const waterTrend: WaterTrendPoint[] = recentMonths(12).map((date, index) => ({
  date,
  ph: Number((7 + Math.sin(index / 2) * 0.4 + random() * 0.2).toFixed(2)),
  do: Number((6.2 + Math.cos(index / 2.5) * 0.6 + random() * 0.3).toFixed(2)),
  cod: Number((18 + Math.sin(index / 1.8) * 3 + random() * 2).toFixed(2)),
  nh3n: Number((0.9 + Math.cos(index / 2) * 0.2 + random() * 0.1).toFixed(2)),
}))

/* -------------------------------------------------------------------------- */
/* 事件中心                                                                    */
/* -------------------------------------------------------------------------- */

const EVENT_TYPES = ['水质异常', '漂浮物', '违规排污', '堤岸损坏', '其他事件'] as const
const EVENT_STATUS = ['待处理', '处理中', '已完成', '已归档', '已驳回', '已关闭'] as const

export const events: RiverEvent[] = Array.from({ length: 24 }, (_, index) => {
  const river = pick(rivers)
  const type = pick(EVENT_TYPES)
  const status = pick(EVENT_STATUS)
  const handler = pick(chiefs).name
  const logCount = status === '待处理' ? 0 : randomInt(1, 4)
  const logs: EventLog[] = Array.from({ length: logCount }, (_, logIndex) => ({
    id: `EL${pad(index + 1, 4)}-${logIndex + 1}`,
    operator: handler,
    action: ['事件上报', '审核确认', '分派处理', '处理反馈', '审核结案'][logIndex] ?? '处理中',
    remark: pick(['已现场核查并记录', '已通知属地河长核实', '整改已完成，等待复核', '现场已清理，处置留痕']),
    time: stamp(-randomInt(60, 10080) + logIndex * 30),
  }))
  return {
    id: `EV${pad(index + 1, 4)}`,
    title: `${river.name}${type}事件`,
    type,
    status,
    level: pick(['一般', '较大', '重大'] as const),
    riverName: river.name,
    region: river.region,
    reporter: pick(['自动监测告警', '巡查上报', '公众举报', '无人机巡检']),
    handler,
    occurAt: stamp(-randomInt(120, 20000)),
    deadline: stamp(randomInt(60, 7200)),
    description: `${river.name}${river.region}段发现${type}情况，已按流程登记并分派处置。`,
    logs,
  }
})

/* -------------------------------------------------------------------------- */
/* 预警信息                                                                    */
/* -------------------------------------------------------------------------- */

export const warns: WarnInfo[] = Array.from({ length: 12 }, (_, index) => {
  const type = pick(['水质预警', '事件预警', '设备离线', '超期预警'] as const)
  const target = type === '水质预警' ? pick(stations).name : type === '设备离线' ? pick(stations).name : pick(rivers).name
  return {
    id: `WN${pad(index + 1, 4)}`,
    title: `${target}${type}`,
    type,
    level: pick(['提示', '警告', '严重'] as const),
    target,
    time: stamp(-randomInt(5, 1440)),
  }
})

/* -------------------------------------------------------------------------- */
/* 考核管理                                                                    */
/* -------------------------------------------------------------------------- */

export const assessments: Assessment[] = chiefs.map((chief, index) => {
  const patrolRate = chief.patrolRate
  const resolveRate = chief.resolveRate
  const qualityRate = randomInt(70, 100)
  const responseTime = randomInt(1, 12)
  const satisfaction = randomInt(75, 100)
  const totalScore = Number(
    (patrolRate * 0.3 + resolveRate * 0.25 + qualityRate * 0.25 + (100 - responseTime * 4) * 0.1 + satisfaction * 0.1).toFixed(1),
  )
  return {
    id: `AS${pad(index + 1, 4)}`,
    name: `${chief.name}履职考核`,
    chiefName: chief.name,
    level: chief.level,
    levelName: chief.levelName,
    region: chief.region,
    period: '2024年第二季度',
    patrolRate,
    resolveRate,
    qualityRate,
    responseTime,
    satisfaction,
    totalScore,
    rank: 0,
  }
}).sort((a, b) => b.totalScore - a.totalScore)
  .map((item, index) => ({ ...item, rank: index + 1 }))

/* -------------------------------------------------------------------------- */
/* 公众服务                                                                    */
/* -------------------------------------------------------------------------- */

export const publicReports: PublicReport[] = Array.from({ length: 20 }, (_, index) => {
  const river = pick(rivers)
  const status = pick(['待审核', '已受理', '已办结', '已驳回'] as const)
  return {
    id: `PR${pad(index + 1, 4)}`,
    title: `${river.name}${pick(['异味', '漂浮物', '疑似排污', '岸坡垃圾'])}举报`,
    content: `举报人在${river.region}${river.name}段发现异常情况，已拍照上传，请求核实处理。`,
    riverName: river.name,
    region: river.region,
    reporter: `群众${pad(index + 1)}`,
    phone: `13${randomInt(100000000, 999999999)}`,
    status,
    reward: status === '已办结' ? randomInt(5, 50) : 0,
    submitAt: stamp(-randomInt(60, 20000)),
  }
})

/* -------------------------------------------------------------------------- */
/* 系统管理                                                                    */
/* -------------------------------------------------------------------------- */

const ORG_NAMES = [
  ['省河长制办公室', '四川省水利厅'],
  ['成都市河长制办公室', '四川省水利厅'],
  ['德阳市河长制办公室', '成都市河长制办公室'],
  ['绵阳市河长制办公室', '成都市河长制办公室'],
  ['乐山市河长制办公室', '成都市河长制办公室'],
  ['青羊区河长制办公室', '成都市河长制办公室'],
  ['武侯区河长制办公室', '成都市河长制办公室'],
  ['江油市河长制办公室', '绵阳市河长制办公室'],
  ['龙泉驿区河长制办公室', '成都市河长制办公室'],
  ['东坡区河长制办公室', '眉山市河长制办公室'],
]

export const orgs: SysOrg[] = ORG_NAMES.map(([name, parentName], index) => ({
  id: `OG${pad(index + 1, 4)}`,
  name,
  code: `SC-ORG-${pad(index + 1, 4)}`,
  parentName,
  leader: pick(chiefs).name,
  phone: `028-${randomInt(1000000, 9999999)}`,
  sort: index + 1,
  memberCount: randomInt(3, 28),
  status: '正常',
}))

const ROLE_PERMISSIONS: Record<string, string[]> = {
  super_admin: ['*'],
  province: ['dashboard:view', 'workspace:province', 'river:view', 'chief:view', 'patrol:view', 'water:view', 'event:view', 'ai:view', 'assessment:view', 'public:view', 'large-screen:view'],
  city: ['dashboard:view', 'workspace:city', 'river:view', 'chief:view', 'patrol:view', 'water:view', 'event:view', 'ai:view', 'assessment:view', 'large-screen:view'],
  county: ['dashboard:view', 'workspace:county', 'river:view', 'patrol:view', 'water:view', 'event:handle', 'ai:view', 'large-screen:view'],
  town: ['dashboard:view', 'workspace:town', 'patrol:handle', 'event:handle', 'public:view'],
}

export const roles: SysRole[] = (['super_admin', 'province', 'city', 'county', 'town'] as const).map((code, index) => ({
  id: `RL${pad(index + 1, 4)}`,
  name: code === 'super_admin' ? '超级管理员' : LEVEL_NAME[code],
  code,
  level: code as SysRole['level'],
  dataScope: code === 'super_admin' ? '全部数据' : code === 'province' ? '全省数据' : code === 'city' ? '本市数据' : code === 'county' ? '本县数据' : '本乡镇数据',
  memberCount: randomInt(1, 40),
  permissions: ROLE_PERMISSIONS[code],
  status: '启用',
  createdAt: stamp(-randomInt(10000, 100000)),
}))

export const sysUsers: SysUser[] = Array.from({ length: 16 }, (_, index) => {
  const role = roles[index % roles.length]
  const org = pick(orgs)
  return {
    id: `US${pad(index + 1, 4)}`,
    username: `user${pad(index + 1, 3)}`,
    name: `${pick(['张', '王', '李', '赵', '陈'])}${pick(['伟', '芳', '娜', '磊', '静'])}`,
    roleName: role.name,
    orgName: org.name,
    phone: `1${pick(['3', '5', '8'])}${randomInt(100000000, 999999999)}`,
    status: random() > 0.85 ? '禁用' : '启用',
    lastLoginAt: stamp(-randomInt(1, 10080)),
    createdAt: stamp(-randomInt(10000, 200000)),
  }
})

const DICT_TYPES: Array<[string, string, string[]]> = [
  ['river_level', '河道等级', ['省级', '市级', '县级', '乡镇级']],
  ['event_type', '事件类型', ['水质异常', '漂浮物', '违规排污', '堤岸损坏', '其他事件']],
  ['water_grade', '水质类别', ['Ⅰ类', 'Ⅱ类', 'Ⅲ类', 'Ⅳ类', 'Ⅴ类']],
  ['patrol_type', '巡查类型', ['日常巡查', '专项巡查', '整改复查', '汛期排查']],
  ['device_type', '设备类型', ['无人机', '监控设备', '水质监测站', '雨量站', '浮标']],
]

export const dictItems: DictItem[] = DICT_TYPES.flatMap(([type, typeLabel, labels], typeIndex) =>
  labels.map((label, index) => ({
    id: `DI${pad(typeIndex * 10 + index + 1, 4)}`,
    type,
    typeLabel,
    label,
    value: `value_${typeIndex + 1}_${index + 1}`,
    sort: index + 1,
    status: '启用' as const,
  })),
)

export const operationLogs: OperationLog[] = Array.from({ length: 32 }, (_, index) => ({
  id: `LG${pad(index + 1, 4)}`,
  operator: pick(sysUsers).name,
  module: pick(['河道档案', '巡查管理', '事件中心', '水质监测', '系统管理', 'AI溯源']),
  action: pick(['新增', '编辑', '删除', '查询', '导出', '审核']),
  ip: `10.${randomInt(0, 255)}.${randomInt(0, 255)}.${randomInt(1, 254)}`,
  duration: randomInt(20, 3200),
  status: random() > 0.12 ? '成功' : '失败',
  createdAt: stamp(-randomInt(1, 20000)),
}))

export const devices: Device[] = Array.from({ length: 18 }, (_, index) => ({
  id: `DV${pad(index + 1, 4)}`,
  name: `${pick(['巡河', '应急', '取证'])}无人机-${pad(index + 1, 2)}`,
  code: `SC-DEV-${pad(index + 1, 4)}`,
  type: pick(['无人机', '监控设备', '水质监测站', '雨量站', '浮标'] as const),
  region: pick(REGIONS),
  status: pick(['在线', '在线', '在线', '离线', '维护中'] as const),
  battery: randomInt(12, 100),
  lastOnlineAt: stamp(-randomInt(1, 10000)),
}))

/* -------------------------------------------------------------------------- */
/* 统计聚合                                                                    */
/* -------------------------------------------------------------------------- */

export const dashboardSummary = {
  riverTotal: rivers.length,
  riverNormal: rivers.filter((item) => item.status === '正常').length,
  riverWarn: rivers.filter((item) => item.status === '预警').length,
  qualityRate: Number((rivers.reduce((sum, item) => sum + item.qualityRate, 0) / rivers.length).toFixed(1)),
  patrolTotal: patrolTasks.length,
  patrolDone: patrolTasks.filter((item) => item.status === '已完成').length,
  patrolDoing: patrolTasks.filter((item) => item.status === '进行中').length,
  patrolOverdue: patrolTasks.filter((item) => item.status === '已逾期').length,
  eventTotal: events.length,
  eventPending: events.filter((item) => item.status === '待处理').length,
  eventDone: events.filter((item) => item.status === '已完成' || item.status === '已归档').length,
  chiefTotal: chiefs.length,
  stationOnline: stations.filter((item) => item.online).length,
  stationTotal: stations.length,
  reportPending: publicReports.filter((item) => item.status === '待审核').length,
}

export const riverLevelChart: ChartItem[] = (['省级', '市级', '县级', '乡镇级'] as const).map((name) => ({
  name,
  value: rivers.filter((item) => item.level === name).length,
}))

export const eventTypeChart: ChartItem[] = (['水质异常', '漂浮物', '违规排污', '堤岸损坏', '其他事件'] as const).map((name) => ({
  name,
  value: events.filter((item) => item.type === name).length,
}))

export const chiefDutyChart: ChartItem[] = (['省级', '市级', '县级', '乡镇级'] as const).map((name) => ({
  name,
  value: chiefs.filter((item) => item.levelName === `${name}河长`).length,
}))

export const trendChart = {
  qualityRate: recentMonths(6).map((date, index) => ({
    date,
    value: Number((88 + Math.sin(index) * 4 + random() * 2).toFixed(1)),
  })),
  resolveRate: recentMonths(6).map((date, index) => ({
    date,
    value: Number((82 + Math.cos(index) * 5 + random() * 2).toFixed(1)),
  })),
  patrolRate: recentMonths(6).map((date, index) => ({
    date,
    value: Number((90 + Math.sin(index * 0.8) * 3 + random() * 2).toFixed(1)),
  })),
}

/** AI 溯源相关模拟结果 */
export const aiDiffusionPoints = Array.from({ length: 40 }, (_, index) => ({
  x: index,
  y: Number((Math.exp(-index / 9) * 100 + random() * 4).toFixed(2)),
  z: Number((Math.sin(index / 4) * 30 + random() * 8).toFixed(2)),
}))

export const aiFingerprints = Array.from({ length: 12 }, (_, index) => ({
  id: `FP${pad(index + 1, 3)}`,
  x: randomInt(10, 90),
  y: randomInt(10, 90),
  risk: randomInt(30, 98),
  source: pick(['生活污水', '工业废水', '农业面源', '养殖污染']),
  status: random() > 0.6 ? '已锁定' : '待核查',
}))

export const aiCompareRows = Array.from({ length: 10 }, (_, index) => {
  const value = randomInt(20, 200)
  const standard = randomInt(20, 200)
  return {
    id: `CP${pad(index + 1, 3)}`,
    factor: pick(['氨氮', '总磷', 'COD', '总氮', '石油类', '挥发酚']),
    value,
    standard,
    exceed: value > standard,
    permitNo: `川排污字第${randomInt(2018, 2024)}号`,
  }
})

export const aiDetections = Array.from({ length: 14 }, (_, index) => ({
  id: `DT${pad(index + 1, 3)}`,
  target: pick(['水面漂浮物', '疑似排污口', '垃圾堆放', '违规捕捞']),
  confidence: Number((randomInt(70, 99) / 100).toFixed(2)),
  time: stamp(-randomInt(10, 5000)),
  status: pick(['待确认', '已确认', '已派单'] as const),
}))

export const aiPrediction = recentDays(14).map((date, index) => ({
  date,
  actual: Number((7.4 + Math.sin(index / 2) * 0.3).toFixed(2)),
  predict: Number((7.4 + Math.sin(index / 2) * 0.3 + random() * 0.2).toFixed(2)),
  lower: Number((7.1 + Math.sin(index / 2) * 0.3).toFixed(2)),
  upper: Number((7.7 + Math.sin(index / 2) * 0.3).toFixed(2)),
}))

export const aiTracing = [
  { step: 1, node: '疑似排放口', time: '09:20', desc: '监测到氨氮突增 3.2 倍' },
  { step: 2, node: '上游 1.5km 支流汇入点', time: '09:35', desc: '流速与浓度出现明显分层' },
  { step: 3, node: '溯源至污水处理厂排口', time: '09:58', desc: '匹配历史违规排放记录' },
  { step: 4, node: '锁定污染源主体', time: '10:12', desc: '已推送属地河长核查' },
]

/** 摄像头识别模拟：按抓拍场景生成 0-2 个疑似排污口目标（坐标集中在画面下方水域区域） */
export function buildCameraRecognition(scene: string) {
  // 约 1/4 概率未识别到目标，模拟真实模型的"空结果"场景
  const count = randomInt(1, 8) <= 2 ? 0 : randomInt(1, 2)
  const targets = ['疑似排污口', '暗管排放', '水面油污', '岸边渗排'] as const
  const sources = ['生活污水', '工业废水', '农业面源', '养殖污染'] as const
  const suggestions = ['建议现场核查', '建议取样检测', '建议调取排污许可', '建议属地河长复核'] as const
  const items = Array.from({ length: count }, (_, index) => {
    const confidence = Number((randomInt(72, 98) / 100).toFixed(2))
    return {
      id: `CR${pad(index + 1, 3)}`,
      target: pick(targets),
      confidence,
      // 目标集中于画面下方"水面"区域，避免识别框飘在画面上方天空/岸边空白处
      x: Number(randomInt(20, 80).toFixed(1)),
      y: Number(randomInt(50, 82).toFixed(1)),
      width: randomInt(10, 18),
      height: randomInt(8, 14),
      risk: Math.min(99, Math.round(confidence * 60) + randomInt(10, 40)),
      source: pick(sources),
      suggestion: pick(suggestions),
    }
  })
  return {
    taskId: `CT${Date.now().toString().slice(-6)}`,
    scene,
    model: 'YOLOv8-sewer v1.3（模拟）',
    capturedAt: stamp(),
    elapsed: randomInt(120, 480),
    // Mock 服务固定标记，前端据此展示「模拟识别」标签
    mock: true,
    items,
  }
}

export const aiEvaluation = Array.from({ length: 10 }, (_, index) => {
  const score = randomInt(60, 98)
  return {
    id: `EV${pad(index + 1, 3)}`,
    chiefName: pick(chiefs).name,
    score,
    level: score >= 90 ? '优秀' : score >= 80 ? '良好' : score >= 70 ? '合格' : '待提升',
    suggestion: pick(['保持巡查频次，加强问题闭环', '建议提高整改反馈及时性', '事件响应速度有待提升', '水质巡查覆盖不足']),
  }
})

export { recentDays, recentMonths, stamp }
