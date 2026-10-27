import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import Inspector from 'unplugin-vue-dev-locator/vite'
import traeBadgePlugin from 'vite-plugin-trae-solo-badge'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 读取全部环境变量（含非 VITE_ 前缀的 AI_API_KEY —— 仅 dev server 端使用，不会打进前端包）
  const env = loadEnv(mode, __dirname, '')
  const aiApiKey = env.AI_API_KEY ?? ''
  const aiApiTarget = env.AI_API_TARGET ?? 'https://ws-sam2wv6vqkfzq8rp.cn-beijing.maas.aliyuncs.com'
  // 本地离线检测服务（Ultralytics YOLO），默认模式：前端同源 /detect 转发，避免 CORS
  const localDetectUrl = env.VITE_LOCAL_DETECT_URL ?? 'http://127.0.0.1:8000'

  return {
    build: {
      sourcemap: 'hidden',
      // 按需引入后 echarts 核心仍接近 1MB，均为按需拆分的 vendor chunk，放宽告警阈值
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined
            // echarts-gl 依赖 claygl，体积较大，仅在「AI 扩散模拟」页面加载
            if (/[\\/]node_modules[\\/](echarts-gl|claygl)[\\/]/.test(id)) return 'echarts-gl'
            if (/[\\/]node_modules[\\/](echarts|zrender)[\\/]/.test(id)) return 'echarts'
            if (/[\\/]node_modules[\\/]element-plus[\\/]/.test(id)) return 'element-plus'
            if (/[\\/]node_modules[\\/](vue|vue-router|pinia|pinia-plugin-persistedstate|vue-demi)[\\/]/.test(id)) {
              return 'vue'
            }
            return undefined
          },
        },
      },
    },
    server: {
      host: true, // 允许局域网访问
      port: 5173,
      // 训练产物/数据集目录不参与监听：否则训练每次保存 best.pt 都会触发整页 reload
      watch: {
        ignored: ['**/ai-training/**', '**/runs/**', '**/datasets/**', '**/logs/**', '**/models/**'],
      },
      // 本地离线检测代理：/detect -> 本地 YOLO 推理服务
      proxy: {
        '/detect': {
          target: localDetectUrl,
          changeOrigin: true,
        },
        // 视觉大模型代理（阿里云 MaaS OpenAI 兼容接口，仅 cloud 模式使用）：
        // 浏览器请求同源 /ai-api/*，由 dev server 转发并在服务端注入 Authorization，
        // API Key 不暴露给前端代码与浏览器。未配置 AI_API_KEY 时不启用。
        ...(aiApiKey
          ? {
              '/ai-api': {
                target: aiApiTarget,
                changeOrigin: true,
                rewrite: (url: string) => url.replace(/^\/ai-api/, '/compatible-mode/v1'),
                configure: (proxy: { on: (event: string, cb: (req: { setHeader: (k: string, v: string) => void }) => void) => void }) => {
                  proxy.on('proxyReq', (proxyReq) => {
                    proxyReq.setHeader('Authorization', `Bearer ${aiApiKey}`)
                  })
                },
              },
            }
          : {}),
      },
    },
    plugins: [
      vue(),
      // Element Plus 按需引入：组件、指令（v-loading 等）与样式自动注入
      Components({
        dts: 'src/components.d.ts',
        resolvers: [ElementPlusResolver()],
      }),
      Inspector(),
      traeBadgePlugin({
        variant: 'dark',
        position: 'bottom-right',
        prodOnly: true,
        clickable: true,
        clickUrl: 'https://www.trae.ai/solo?showJoin=1',
        autoTheme: true,
        autoThemeTarget: '#app',
      }),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'), // 定义 @ = src
      },
    },
  }
})
