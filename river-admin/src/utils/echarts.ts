/**
 * ECharts 按需引入统一入口
 *
 * 全站图表统一从该模块导入 echarts，避免 `import * from 'echarts'` 全量打包。
 * 3D 扩展（echarts-gl，依赖 claygl，体积较大）仅在「AI 扩散模拟」页面单独
 * 静态导入，使其落在独立的懒加载 chunk 中，其它页面不会加载。
 */
import * as echarts from 'echarts/core'
import {
  BarChart,
  EffectScatterChart,
  LineChart,
  PieChart,
  ScatterChart,
} from 'echarts/charts'
import {
  AxisPointerComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  EffectScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  AxisPointerComponent,
  CanvasRenderer,
])

export * from 'echarts/core'
// 仅类型透传，运行时无开销
export type { ECharts, EChartsOption } from 'echarts'
