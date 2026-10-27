# 智河通 —— 智慧河长协同治理平台（后台管理端）

基于 Vue 3 + TypeScript + Vite 的河道治理数字化管理后台，为各级河长、水务部门提供河道档案、巡查管理、水质监测、事件闭环、AI 溯源、履职考核等一体化工具。

> 📘 **接手/续做请先看**：[docs/项目工作文档.md](docs/项目工作文档.md) —— 含离线识别链路、数据与训练流程、踩坑记录、后续任务建议。
> 🤖 AI 工程细节见 [ai-training/README.md](ai-training/README.md)。

## 快速开始

```bash
npm install     # 安装依赖
npm run dev     # 本地开发，默认 http://localhost:5173
npm run build   # 类型检查 + 生产构建
npm run preview # 预览构建产物
npm run check   # 仅执行 vue-tsc 类型检查
npm run lint    # ESLint 检查
```

## 演示账号

密码统一为 `123456`，登录页提供快捷填充按钮。

| 账号 | 角色 | 可见范围 |
|------|------|----------|
| `admin` | 超级管理员 | 全部功能 |
| `province` | 省级河长 | 省级工作台、全省数据 |
| `city` | 市级河长 | 市级工作台、本市数据 |
| `county` | 县级河长 | 县级工作台、辖区数据 |
| `town` | 乡镇级河长 | 乡镇级工作台、日常巡查与上报 |

## 技术栈

| 层面 | 选型 |
|------|------|
| 框架 | Vue 3.4（`<script setup>`） |
| 语言 | TypeScript 5.3 |
| 构建 | Vite 5 |
| 状态管理 | Pinia + pinia-plugin-persistedstate |
| 路由 | Vue Router 4（history 模式 + 全局守卫） |
| UI | Element Plus + TailwindCSS + @element-plus/icons-vue |
| 图表 | ECharts 6 + echarts-gl（3D 散点） |
| 请求 | Axios（统一拦截 + 内置 Mock 适配器） |

## 目录结构

```
src/
├── api/            # 接口层，按业务域拆分（auth/dashboard/river/chief/patrol/water/event/assessment/public/system/ai）
├── components/     # 通用组件（PageHeader、StatCard、StatusTag、EChart）
├── composables/    # 组合式函数（useTable 统一列表分页逻辑）
├── layouts/        # 后台主布局（侧边导航 + 顶部工具栏）
├── mock/           # 内置模拟数据与 axios 适配器
├── router/         # 路由表、菜单配置与权限守卫
├── stores/         # Pinia 状态（user 鉴权、app 应用状态）
├── styles/         # 全局样式与设计变量
├── types/          # 全局 TypeScript 类型定义
├── utils/          # 工具函数（存储、格式化）
└── views/          # 业务页面
```

## 功能模块

- **工作台** `/dashboard`：河道、水质、巡查、事件核心指标与趋势
- **河长工作台** `/workspace/{province,city,county,town}`：省/市/县/乡镇四级分级视图
- **河道档案** `/river`：河道台账、详情、增删改查
- **河长管理** `/chief/list`、`/chief/portrait`：河长台账与数字河长画像
- **巡查管理** `/patrol`：任务分配、执行、轨迹与问题上报
- **水质监测** `/water-quality`：站点、实时数据、趋势、指标标准与预警
- **事件中心** `/event`：事件上报、分派、处理、归档全流程
- **AI 智能溯源** `/ai/*`：扩散模拟、排污口指纹、许可比对、污染源锁定、目标检测、水质预测、溯源、履职评估
- **考核管理** `/assessment`：五维指标加权考核与排名
- **公众服务** `/public`：举报受理、审核与积分激励
- **系统管理** `/system/*`：用户、组织架构、角色权限、数据字典、操作日志、设备管理
- **数据大屏** `/large-screen`：四川省河道治理监控中心（1920×1080 自适应）

## 数据说明

当前版本内置 Mock 服务（`src/mock/`），以 axios 适配器形式接管请求，前端调用方式与真实后端保持一致。接入真实后端时设置环境变量 `VITE_USE_MOCK=false` 并配置 `VITE_API_BASE` 即可，无需改动业务代码。

## 权限模型

基于角色的权限控制（RBAC），路由 `meta.permission` 声明访问所需权限编码，由 `useUserStore().hasPermission()` 统一校验，菜单亦按权限过滤。
