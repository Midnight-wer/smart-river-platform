import {
  Bell,
  ChatDotRound,
  Compass,
  DataLine,
  Document,
  Histogram,
  MagicStick,
  Monitor,
  OfficeBuilding,
  Odometer,
  Setting,
  Share,
  TrendCharts,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import type { MenuItem } from '@/types'

/**
 * 侧边栏菜单配置
 * permission 为空表示所有已登录用户可见；配置后仅具备对应权限的角色可见。
 */
export const menus: MenuItem[] = [
  {
    index: '/dashboard',
    title: '工作台',
    icon: Odometer,
    permission: 'dashboard:view',
  },
  {
    index: '/workspace',
    title: '河长工作台',
    icon: OfficeBuilding,
    children: [
      { index: '/workspace/province', title: '省级河长工作台', icon: OfficeBuilding, permission: 'workspace:province' },
      { index: '/workspace/city', title: '市级河长工作台', icon: OfficeBuilding, permission: 'workspace:city' },
      { index: '/workspace/county', title: '县级河长工作台', icon: OfficeBuilding, permission: 'workspace:county' },
      { index: '/workspace/town', title: '乡镇级河长工作台', icon: OfficeBuilding, permission: 'workspace:town' },
    ],
  },
  {
    index: '/river',
    title: '河道档案',
    icon: Share,
    permission: 'river:view',
  },
  {
    index: '/chief',
    title: '河长管理',
    icon: User,
    children: [
      { index: '/chief/list', title: '河长列表', icon: User, permission: 'chief:view' },
      { index: '/chief/portrait', title: '数字河长画像', icon: UserFilled, permission: 'chief:view' },
    ],
  },
  {
    index: '/patrol',
    title: '巡查管理',
    icon: Compass,
    permission: 'patrol:view',
  },
  {
    index: '/water-quality',
    title: '水质监测',
    icon: DataLine,
    permission: 'water:view',
  },
  {
    index: '/event',
    title: '事件中心',
    icon: Bell,
    permission: 'event:view',
  },
  {
    index: '/ai',
    title: 'AI 智能溯源',
    icon: MagicStick,
    children: [
      { index: '/ai/diffusion', title: '污染扩散模拟', icon: MagicStick, permission: 'ai:view' },
      { index: '/ai/fingerprint', title: '排污口指纹识别', icon: MagicStick, permission: 'ai:view' },
      { index: '/ai/compare', title: '许可数据库比对', icon: MagicStick, permission: 'ai:view' },
      { index: '/ai/source', title: '疑似污染源锁定', icon: MagicStick, permission: 'ai:view' },
      { index: '/ai/detection', title: '目标检测模型', icon: MagicStick, permission: 'ai:view' },
      { index: '/ai/prediction', title: '水质预测模型', icon: MagicStick, permission: 'ai:view' },
      { index: '/ai/tracing', title: '污染溯源模型', icon: MagicStick, permission: 'ai:view' },
      { index: '/ai/evaluation', title: '履职评估模型', icon: MagicStick, permission: 'ai:view' },
    ],
  },
  {
    index: '/assessment',
    title: '考核管理',
    icon: TrendCharts,
    permission: 'assessment:view',
  },
  {
    index: '/public',
    title: '公众服务',
    icon: ChatDotRound,
    permission: 'public:view',
  },
  {
    index: '/system',
    title: '系统管理',
    icon: Setting,
    children: [
      { index: '/system/user', title: '用户管理', icon: User },
      { index: '/system/org', title: '组织架构', icon: OfficeBuilding },
      { index: '/system/role', title: '角色管理', icon: UserFilled },
      { index: '/system/dict', title: '数据字典', icon: Document },
      { index: '/system/log', title: '操作日志', icon: Histogram },
      { index: '/system/device', title: '设备管理', icon: Monitor },
    ],
  },
  {
    index: '/large-screen',
    title: '数据大屏',
    icon: Monitor,
    permission: 'large-screen:view',
  },
]
