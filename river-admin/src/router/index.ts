import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { registerUnauthorizedHandler } from '@/api/request'

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题 */
    title?: string
    /** 访问所需权限编码 */
    permission?: string | string[]
    /** 无需登录即可访问 */
    public?: boolean
    /** 菜单高亮路径 */
    activeMenu?: string
    /** 是否隐藏于侧边栏 */
    hidden?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/Login.vue'),
    meta: { title: '登录', public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Dashboard.vue'),
        meta: { title: '工作台', permission: 'dashboard:view' },
      },
      {
        path: 'workspace',
        redirect: '/workspace/province',
        children: [
          {
            path: 'province',
            name: 'WorkspaceProvince',
            component: () => import('@/views/workspace/Province.vue'),
            meta: { title: '省级河长工作台', permission: 'workspace:province' },
          },
          {
            path: 'city',
            name: 'WorkspaceCity',
            component: () => import('@/views/workspace/City.vue'),
            meta: { title: '市级河长工作台', permission: 'workspace:city' },
          },
          {
            path: 'county',
            name: 'WorkspaceCounty',
            component: () => import('@/views/workspace/County.vue'),
            meta: { title: '县级河长工作台', permission: 'workspace:county' },
          },
          {
            path: 'town',
            name: 'WorkspaceTown',
            component: () => import('@/views/workspace/Town.vue'),
            meta: { title: '乡镇级河长工作台', permission: 'workspace:town' },
          },
        ],
      },
      {
        path: 'river',
        name: 'RiverList',
        component: () => import('@/views/river/RiverList.vue'),
        meta: { title: '河道档案', permission: 'river:view' },
      },
      {
        path: 'river/:id',
        name: 'RiverDetail',
        component: () => import('@/views/river/RiverDetail.vue'),
        meta: { title: '河道详情', activeMenu: '/river' },
      },
      {
        path: 'chief',
        redirect: '/chief/list',
        children: [
          {
            path: 'list',
            name: 'ChiefList',
            component: () => import('@/views/chief/ChiefList.vue'),
            meta: { title: '河长列表', permission: 'chief:view' },
          },
          {
            path: 'portrait',
            name: 'ChiefPortrait',
            component: () => import('@/views/chief/ChiefPortrait.vue'),
            meta: { title: '数字河长画像', permission: 'chief:view' },
          },
          {
            path: 'portrait/:id',
            name: 'ChiefPortraitDetail',
            component: () => import('@/views/chief/ChiefPortraitDetail.vue'),
            meta: { title: '河长画像详情', activeMenu: '/chief/portrait' },
          },
        ],
      },
      {
        path: 'patrol',
        name: 'PatrolList',
        component: () => import('@/views/patrol/PatrolList.vue'),
        meta: { title: '巡查管理', permission: 'patrol:view' },
      },
      {
        path: 'water-quality',
        name: 'WaterQuality',
        component: () => import('@/views/water/WaterQuality.vue'),
        meta: { title: '水质监测', permission: 'water:view' },
      },
      {
        path: 'event',
        name: 'EventList',
        component: () => import('@/views/event/EventList.vue'),
        meta: { title: '事件中心', permission: 'event:view' },
      },
      {
        path: 'ai',
        redirect: '/ai/diffusion',
        children: [
          {
            path: 'diffusion',
            name: 'AiDiffusion',
            component: () => import('@/views/ai/Diffusion.vue'),
            meta: { title: '污染扩散模拟', permission: 'ai:view' },
          },
          {
            path: 'fingerprint',
            name: 'AiFingerprint',
            component: () => import('@/views/ai/Fingerprint.vue'),
            meta: { title: '排污口指纹识别', permission: 'ai:view' },
          },
          {
            path: 'compare',
            name: 'AiCompare',
            component: () => import('@/views/ai/Compare.vue'),
            meta: { title: '许可数据库比对', permission: 'ai:view' },
          },
          {
            path: 'source',
            name: 'AiSource',
            component: () => import('@/views/ai/Source.vue'),
            meta: { title: '疑似污染源锁定', permission: 'ai:view' },
          },
          {
            path: 'detection',
            name: 'AiDetection',
            component: () => import('@/views/ai/Detection.vue'),
            meta: { title: '目标检测模型', permission: 'ai:view' },
          },
          {
            path: 'prediction',
            name: 'AiPrediction',
            component: () => import('@/views/ai/Prediction.vue'),
            meta: { title: '水质预测模型', permission: 'ai:view' },
          },
          {
            path: 'tracing',
            name: 'AiTracing',
            component: () => import('@/views/ai/Tracing.vue'),
            meta: { title: '污染溯源模型', permission: 'ai:view' },
          },
          {
            path: 'evaluation',
            name: 'AiEvaluation',
            component: () => import('@/views/ai/Evaluation.vue'),
            meta: { title: '履职评估模型', permission: 'ai:view' },
          },
        ],
      },
      {
        path: 'assessment',
        name: 'Assessment',
        component: () => import('@/views/assessment/Assessment.vue'),
        meta: { title: '考核管理', permission: 'assessment:view' },
      },
      {
        path: 'public',
        name: 'PublicService',
        component: () => import('@/views/public/PublicService.vue'),
        meta: { title: '公众服务', permission: 'public:view' },
      },
      {
        path: 'system',
        redirect: '/system/user',
        children: [
          {
            path: 'user',
            name: 'SystemUser',
            component: () => import('@/views/system/UserManage.vue'),
            meta: { title: '用户管理' },
          },
          {
            path: 'org',
            name: 'SystemOrg',
            component: () => import('@/views/system/OrgManage.vue'),
            meta: { title: '组织架构' },
          },
          {
            path: 'role',
            name: 'SystemRole',
            component: () => import('@/views/system/RoleManage.vue'),
            meta: { title: '角色管理' },
          },
          {
            path: 'dict',
            name: 'SystemDict',
            component: () => import('@/views/system/DictManage.vue'),
            meta: { title: '数据字典' },
          },
          {
            path: 'log',
            name: 'SystemLog',
            component: () => import('@/views/system/LogManage.vue'),
            meta: { title: '操作日志' },
          },
          {
            path: 'device',
            name: 'SystemDevice',
            component: () => import('@/views/system/DeviceManage.vue'),
            meta: { title: '设备管理' },
          },
        ],
      },
    ],
  },
  {
    path: '/large-screen',
    name: 'LargeScreen',
    component: () => import('@/views/large-screen/LargeScreen.vue'),
    meta: { title: '数据大屏', permission: 'large-screen:view' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFound.vue'),
    meta: { title: '页面不存在', public: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  // 免登录页面
  if (to.meta.public) {
    if (to.path === '/login' && userStore.isLogin) {
      next({ path: '/dashboard' })
      return
    }
    next()
    return
  }

  // 未登录跳转登录页
  if (!userStore.isLogin) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  // 登录态存在但缺少用户信息时补拉一次
  if (!userStore.userInfo) {
    const profile = await userStore.loadProfile()
    if (!profile) {
      userStore.resetState()
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }
  }

  // 权限校验
  const permission = to.meta.permission
  if (permission && !userStore.hasPermission(permission)) {
    ElMessage.error('暂无访问该页面的权限')
    if (from.fullPath && from.fullPath !== to.fullPath) {
      next(false)
    } else {
      next({ path: '/dashboard' })
    }
    return
  }

  next()
})

router.afterEach((to) => {
  const title = to.meta.title
  document.title = title ? `${title} - 智慧河长协同治理平台` : '智慧河长协同治理平台'
})

// 登录态失效时由请求层触发跳转
registerUnauthorizedHandler(() => {
  router.push({ path: '/login' })
})

export default router
