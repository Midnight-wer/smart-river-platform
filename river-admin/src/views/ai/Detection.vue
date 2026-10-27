<script setup lang="ts">
/**
 * 目标检测模型：视频/影像中的漂浮物、排污口等目标识别与置信度分析
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Camera, Refresh, SwitchButton, Upload, VideoCamera } from '@element-plus/icons-vue'
import * as echarts from '@/utils/echarts'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import EChart from '@/components/EChart.vue'
import { fetchDetections, recognizeCamera } from '@/api/ai'
import { recognizeByVision, targetMeta, modelLabel, detectMode } from '@/api/vision'
import { formatDateTime } from '@/utils/format'
import type { CameraRecognitionItem, CameraRecognitionResult, DetectionItem } from '@/api/ai'

/** 置信度分档 */
const CONFIDENCE_BUCKETS = [
  { label: '70%-80%', min: 0.7, max: 0.8 },
  { label: '80%-85%', min: 0.8, max: 0.85 },
  { label: '85%-90%', min: 0.85, max: 0.9 },
  { label: '90%-95%', min: 0.9, max: 0.95 },
  { label: '95%-100%', min: 0.95, max: 1.01 },
]

const detections = ref<DetectionItem[]>([])
const loading = ref(false)

const totalCount = computed(() => detections.value.length)
const confirmedCount = computed(() => detections.value.filter((item) => item.status === '已确认').length)
const pendingCount = computed(() => detections.value.filter((item) => item.status === '待确认').length)
const dispatchedCount = computed(() => detections.value.filter((item) => item.status === '已派单').length)

const averageConfidence = computed(() => {
  if (!detections.value.length) return 0
  const total = detections.value.reduce((sum, item) => sum + item.confidence, 0)
  return Number(((total / detections.value.length) * 100).toFixed(1))
})

/** 置信度分档统计 */
const confidenceBuckets = computed(() =>
  CONFIDENCE_BUCKETS.map((bucket) => ({
    label: bucket.label,
    count: detections.value.filter(
      (item) => item.confidence >= bucket.min && item.confidence < bucket.max,
    ).length,
  })),
)

/** 目标类型分布 */
const targetStatistics = computed(() => {
  const counter: Record<string, number> = {}
  detections.value.forEach((item) => {
    counter[item.target] = (counter[item.target] ?? 0) + 1
  })
  return Object.entries(counter)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
})

/** 置信度分布直方图 */
const histogramOption = computed<echarts.EChartsOption>(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 50, right: 24, top: 30, bottom: 44 },
  xAxis: {
    type: 'category',
    name: '置信度区间',
    data: confidenceBuckets.value.map((item) => item.label),
    axisLabel: { color: '#64748b' },
  },
  yAxis: { type: 'value', name: '目标数', minInterval: 1, axisLabel: { color: '#64748b' } },
  series: [
    {
      name: '目标数量',
      type: 'bar',
      barMaxWidth: 44,
      itemStyle: { color: '#2563eb', borderRadius: [4, 4, 0, 0] },
      label: { show: true, position: 'top' },
      data: confidenceBuckets.value.map((item) => item.count),
    },
  ],
}))

/** 目标类型占比图 */
const targetOption = computed<echarts.EChartsOption>(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 个 ({d}%)' },
  legend: { bottom: 0, itemWidth: 12, itemHeight: 8 },
  color: ['#2563eb', '#16a34a', '#f59e0b', '#7c3aed', '#0891b2'],
  series: [
    {
      name: '目标类型',
      type: 'pie',
      radius: '62%',
      center: ['50%', '44%'],
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c} 个' },
      data: targetStatistics.value,
    },
  ],
}))

/** 置信度进度条颜色 */
function confidenceColor(confidence: number): string {
  if (confidence >= 0.9) return '#16a34a'
  if (confidence >= 0.8) return '#2563eb'
  return '#f59e0b'
}

/** 加载检测数据 */
async function load(): Promise<void> {
  loading.value = true
  try {
    detections.value = await fetchDetections()
  } catch (error) {
    console.error('[目标检测模型] 检测数据加载失败', error)
    ElMessage.error('目标检测数据加载失败')
    detections.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)

/* ---------------------------- 摄像头实时识别 ---------------------------- */
const videoRef = ref<HTMLVideoElement | null>(null)
const fileRef = ref<HTMLInputElement | null>(null)
const devices = ref<MediaDeviceInfo[]>([])
const deviceId = ref('')
const cameraActive = ref(false)
const cameraLoading = ref(false)
const recognizing = ref(false)
/** 抓拍/上传画面的预览地址（压缩后的 objectURL） */
const snapshot = ref('')
const recognitionItems = ref<CameraRecognitionItem[]>([])
const recognitionMeta = ref<CameraRecognitionResult | null>(null)
let stream: MediaStream | null = null

/** 读取可用摄像头列表 */
async function loadDevices(): Promise<void> {
  if (!navigator.mediaDevices?.enumerateDevices) return
  const list = await navigator.mediaDevices.enumerateDevices()
  devices.value = list.filter((item) => item.kind === 'videoinput')
  if (!deviceId.value && devices.value.length) {
    deviceId.value = devices.value[0].deviceId
  }
}

/** 校验当前环境是否允许访问摄像头 */
function ensureMediaSupport(): boolean {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    ElMessage.warning('当前环境无法访问摄像头，请通过 localhost 或 HTTPS 打开页面')
    return false
  }
  return true
}

/** 开启摄像头 */
async function startCamera(): Promise<void> {
  if (!ensureMediaSupport()) return
  stopCamera()
  cameraLoading.value = true
  try {
    // 请求 720p 理想分辨率，避免默认低清流导致画面模糊
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        ...(deviceId.value ? { deviceId: { exact: deviceId.value } } : { facingMode: 'environment' }),
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    })
    cameraActive.value = true
    await nextTick()
    if (videoRef.value) {
      videoRef.value.srcObject = stream
      await videoRef.value.play().catch(() => undefined)
    }
    await loadDevices()
  } catch (error) {
    console.error('[目标检测模型] 摄像头开启失败', error)
    const name = (error as DOMException)?.name
    if (name === 'NotAllowedError') {
      ElMessage.error('摄像头权限被拒绝，请在浏览器设置中允许访问')
    } else if (name === 'NotFoundError') {
      ElMessage.error('未检测到可用摄像头')
    } else if (name === 'NotReadableError') {
      ElMessage.error('摄像头被其他程序占用')
    } else {
      ElMessage.error('摄像头开启失败，请检查设备与权限')
    }
    cameraActive.value = false
  } finally {
    cameraLoading.value = false
  }
}

/** 关闭摄像头并释放媒体流，同时清空快照与识别结果 */
function stopCamera(): void {
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
  cameraActive.value = false
  if (videoRef.value) videoRef.value.srcObject = null
  if (snapshot.value) URL.revokeObjectURL(snapshot.value)
  snapshot.value = ''
  recognitionItems.value = []
  recognitionMeta.value = null
}

/** 切换摄像头后重启画面 */
async function handleDeviceChange(): Promise<void> {
  if (cameraActive.value) await startCamera()
}

/** 画面压缩为 Blob（最长边 1280、JPEG 0.85），控制上行体积与推理耗时 */
async function compressToBlob(source: HTMLVideoElement | HTMLImageElement, maxEdge = 1280): Promise<Blob> {
  const width = source instanceof HTMLVideoElement ? source.videoWidth : source.naturalWidth
  const height = source instanceof HTMLVideoElement ? source.videoHeight : source.naturalHeight
  if (!width || !height) throw new Error('画面尚未就绪，请稍后再试')
  const scale = Math.min(1, maxEdge / Math.max(width, height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(width * scale)
  canvas.height = Math.round(height * scale)
  const context = canvas.getContext('2d')
  if (!context) throw new Error('画面处理失败，请重试')
  context.drawImage(source, 0, 0, canvas.width, canvas.height)
  return new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('画面压缩失败，请重试'))), 'image/jpeg', 0.85),
  )
}

/** 抓拍当前画面并识别 */
async function captureAndRecognize(): Promise<void> {
  const video = videoRef.value
  if (!video || !cameraActive.value) {
    ElMessage.warning('请先开启摄像头')
    return
  }
  try {
    const blob = await compressToBlob(video)
    if (snapshot.value) URL.revokeObjectURL(snapshot.value)
    snapshot.value = URL.createObjectURL(blob)
    await recognize(blob, 'camera', video.videoWidth, video.videoHeight)
  } catch (error) {
    console.error('[目标检测模型] 抓拍识别失败', error)
    ElMessage.error(error instanceof Error ? error.message : '抓拍失败，请重试')
  }
}

/** 选择本地图片 */
function pickImage(): void {
  fileRef.value?.click()
}

/** 上传图片并识别（超大图先压缩） */
async function handleFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  const sourceUrl = URL.createObjectURL(file)
  try {
    const image = new Image()
    image.src = sourceUrl
    await image.decode()
    const blob = await compressToBlob(image)
    if (snapshot.value) URL.revokeObjectURL(snapshot.value)
    snapshot.value = URL.createObjectURL(blob)
    await recognize(blob, 'upload', image.naturalWidth, image.naturalHeight)
  } catch (error) {
    console.error('[目标检测模型] 图片识别失败', error)
    ElMessage.error('图片识别失败，请稍后重试')
  } finally {
    URL.revokeObjectURL(sourceUrl)
  }
}

/** 调用识别接口：优先视觉大模型真实识别，不可用时降级 Mock 模拟识别 */
async function recognize(file: Blob, scene: string, width: number, height: number): Promise<void> {
  recognizing.value = true
  const startedAt = performance.now()
  try {
    // 1. 视觉大模型（qwen3-vl-plus）：识别框与画面内容真实对应
    const visionItems = await recognizeByVision(file, { width, height }, 45000, scene)
    const model = modelLabel()
    const taskId = `VL${Date.now().toString().slice(-6)}`
    const items: CameraRecognitionItem[] = visionItems.map((item, index) => {
      const meta = targetMeta()
      return {
        id: `${taskId}-${index + 1}`,
        target: item.target,
        confidence: item.confidence,
        x: item.x,
        y: item.y,
        width: item.width,
        height: item.height,
        risk: Math.min(99, Math.round(item.confidence * 60 + meta.priorRisk)),
        source: meta.source,
        suggestion: meta.suggestion,
      }
    })
    recognitionMeta.value = {
      taskId,
      scene,
      model,
      capturedAt: formatDateTime(new Date()),
      elapsed: Math.round(performance.now() - startedAt),
      mock: false,
      items,
    }
    recognitionItems.value = items
    if (visionItems.length) {
      ElMessage.success(`识别完成，发现 ${visionItems.length} 个目标`)
    } else {
      ElMessage.info('本次未识别到相关违规目标')
    }
  } catch (visionError) {
    // 2. 视觉模型不可用（代理未配置 / 超时 / 解析失败）：降级 Mock，保持演示可用
    console.warn('[目标检测模型] 视觉模型识别失败，降级为模拟识别', visionError)
    try {
      const result = await recognizeCamera({ file, scene, width, height })
      recognitionMeta.value = result
      recognitionItems.value = result.items.map((item, index) => ({ ...item, id: `${result.taskId}-${index + 1}` }))
      if (result.items.length) {
        const reason = visionError instanceof Error ? visionError.message : '服务异常'
        ElMessage.warning(`视觉模型暂不可用（${reason}），已降级为模拟识别`)
      } else {
        ElMessage.info('本次未识别到目标，请调整角度后重试')
      }
    } catch (error) {
      console.error('[目标检测模型] 摄像头识别失败', error)
      ElMessage.error('识别失败，请稍后重试')
      recognitionItems.value = []
      recognitionMeta.value = null
    }
  } finally {
    recognizing.value = false
  }
}

/** 识别结果写入检测结果明细（统计卡片与图表随之刷新） */
function addToDetections(item: CameraRecognitionItem): void {
  if (detections.value.some((row) => row.id === item.id)) {
    ElMessage.info('该目标已在检测结果明细中')
    return
  }
  detections.value = [
    {
      id: item.id,
      target: item.target,
      confidence: item.confidence,
      time: recognitionMeta.value?.capturedAt ?? new Date().toISOString(),
      status: '待确认',
    },
    ...detections.value,
  ]
  ElMessage.success(`已将 ${item.target} 写入检测结果明细`)
}

/** 清空快照，返回实时画面 */
function clearSnapshot(): void {
  if (snapshot.value) URL.revokeObjectURL(snapshot.value)
  snapshot.value = ''
}

/** 识别框定位样式 */
function boxStyle(item: CameraRecognitionItem): Record<string, string> {
  return {
    left: `${Math.max(0, item.x - item.width / 2)}%`,
    top: `${Math.max(0, item.y - item.height / 2)}%`,
    width: `${item.width}%`,
    height: `${item.height}%`,
  }
}

onMounted(() => {
  loadDevices().catch(() => undefined)
})

onBeforeUnmount(stopCamera)
</script>

<template>
  <div class="rv-page">
    <PageHeader title="目标检测模型" description="河道视频与巡河影像中的违规目标智能识别、置信度评估与派单处置">
      <template #extra>
        <el-button :icon="Refresh" @click="load">刷新数据</el-button>
        <el-button
          type="primary"
          :icon="VideoCamera"
          :loading="cameraLoading"
          :disabled="cameraActive"
          @click="startCamera"
        >
          {{ cameraActive ? '检测中' : '启动检测' }}
        </el-button>
      </template>
    </PageHeader>

    <el-alert
      class="mb-4"
      type="info"
      :closable="false"
      show-icon
      title="模型说明"
      description="目标检测采用深度学习目标检测模型对巡河视频与无人机影像进行实时识别，置信度低于 80% 的结果建议人工复核后处置。"
    />

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-4">
      <StatCard label="检测目标总数" :value="totalCount" suffix="个" color="blue" :icon="Camera" />
      <StatCard label="已确认" :value="confirmedCount" suffix="个" color="green" />
      <StatCard label="待确认" :value="pendingCount" suffix="个" color="orange" />
      <StatCard label="已派单" :value="dispatchedCount" suffix="个" color="purple" />
    </div>

    <!-- 摄像头实时识别 -->
    <div class="rv-card mb-4">
      <div class="rv-card-header">
        <span class="rv-card-title">
          摄像头实时识别
          <el-tag v-if="recognitionMeta?.mock" size="small" type="warning" effect="light" round class="ml-2">
            模拟识别
          </el-tag>
        </span>
        <span class="rv-text-secondary">
          {{ recognitionMeta
            ? `模型 ${recognitionMeta.model} · 用时 ${recognitionMeta.elapsed}ms · 任务 ${recognitionMeta.taskId}`
            : '现场抓拍或上传图片，自动识别漂浮物、排污口等违规目标' }}
        </span>
      </div>
      <div class="rv-card-body">
        <div class="grid grid-cols-1 gap-4 xl:grid-cols-12">
          <!-- 摄像头画面 -->
          <div class="xl:col-span-7">
            <div class="fp-camera">
              <div class="fp-camera-frame">
                <video
                  v-show="cameraActive && !snapshot"
                  ref="videoRef"
                  class="fp-camera-media"
                  autoplay
                  muted
                  playsinline
                />
                <img v-if="snapshot" :src="snapshot" class="fp-camera-media" alt="抓拍画面" />
                <div
                  v-for="item in recognitionItems"
                  :key="`box-${item.id}`"
                  class="fp-box"
                  :style="{ ...boxStyle(item), borderColor: confidenceColor(item.confidence) }"
                >
                  <span class="fp-box__label" :style="{ background: confidenceColor(item.confidence) }">
                    {{ item.target }} {{ Math.round(item.confidence * 100) }}%
                  </span>
                </div>
                <span v-if="cameraActive && !snapshot" class="fp-camera-live">LIVE</span>
                <el-button
                  v-if="snapshot && cameraActive"
                  class="fp-camera-back"
                  size="small"
                  text
                  @click="clearSnapshot"
                >
                  返回实时画面
                </el-button>
              </div>

              <div v-if="!cameraActive && !snapshot" class="fp-camera-empty">
                <el-empty description="摄像头未开启，可开启实时画面或上传图片识别" :image-size="70" />
              </div>
            </div>

            <div class="fp-camera-actions">
              <el-select
                v-model="deviceId"
                class="!w-44"
                placeholder="选择摄像头"
                :disabled="!devices.length"
                @change="handleDeviceChange"
              >
                <el-option
                  v-for="(item, index) in devices"
                  :key="item.deviceId || index"
                  :label="item.label || `摄像头 ${index + 1}`"
                  :value="item.deviceId"
                />
              </el-select>
              <el-button
                v-if="!cameraActive"
                type="primary"
                :icon="VideoCamera"
                :loading="cameraLoading"
                @click="startCamera"
              >
                开启摄像头
              </el-button>
              <el-button v-else type="danger" plain :icon="SwitchButton" @click="stopCamera">关闭摄像头</el-button>
              <el-button
                type="primary"
                :icon="Camera"
                :disabled="!cameraActive"
                :loading="recognizing"
                @click="captureAndRecognize"
              >
                抓拍识别
              </el-button>
              <el-button :icon="Upload" :loading="recognizing" @click="pickImage">上传图片识别</el-button>
              <input ref="fileRef" type="file" accept="image/*" class="hidden" @change="handleFile" />
            </div>
            <p class="fp-camera-tip">
              {{ detectMode() === 'local'
                ? '当前为本地离线识别：模型权重与推理服务均在本机运行，画面与数据不离开本机、不访问外网。'
                : '当前为云端模型识别（画面将上传至云端推理）；如需完全离线部署，请在 .env.local 中设置 VITE_DETECT_MODE=local。' }}
              摄像头需在 localhost 或 HTTPS 环境下使用，首次开启时浏览器会请求摄像头权限。
            </p>
          </div>

          <!-- 识别结果 -->
          <div class="xl:col-span-5">
            <div class="fp-result-head">
              <span class="rv-card-title">识别结果</span>
              <span class="rv-text-secondary">
                {{ recognitionItems.length ? `共 ${recognitionItems.length} 个目标` : '暂无识别结果' }}
              </span>
            </div>
            <el-empty
              v-if="!recognitionItems.length"
              description="抓拍或上传图片后展示识别结果"
              :image-size="70"
            />
            <ul v-else class="fp-result-list">
              <li v-for="item in recognitionItems" :key="item.id" class="fp-result">
                <div class="fp-result__head">
                  <span class="fp-result__title">{{ item.target }}</span>
                  <el-tag
                    :type="item.confidence >= 0.9 ? 'danger' : 'warning'"
                    size="small"
                    effect="light"
                    round
                  >
                    置信 {{ Math.round(item.confidence * 100) }}%
                  </el-tag>
                </div>
                <div class="fp-result__row">
                  <span class="rv-text-secondary">风险值</span>
                  <span class="rv-num">{{ item.risk }}</span>
                  <span class="rv-text-secondary">来源预判</span>
                  <span>{{ item.source }}</span>
                </div>
                <div class="fp-result__meta">
                  {{ item.suggestion }} · 坐标 {{ item.x.toFixed(1) }}% / {{ item.y.toFixed(1) }}%
                </div>
                <el-button size="small" type="primary" plain @click="addToDetections(item)">
                  加入检测结果明细
                </el-button>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-12 mb-4">
      <!-- 目标类型分布 -->
      <div class="rv-card xl:col-span-4">
        <div class="rv-card-header">
          <span class="rv-card-title">识别目标类型分布</span>
          <span class="rv-text-secondary">平均置信度 {{ averageConfidence }}%</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="targetOption" height="320px" :loading="loading" />
        </div>
      </div>

      <!-- 置信度直方图 -->
      <div class="rv-card xl:col-span-8">
        <div class="rv-card-header">
          <span class="rv-card-title">置信度分布直方图</span>
          <span class="rv-text-secondary">按 5% 区间统计目标数量</span>
        </div>
        <div class="rv-card-body">
          <EChart :option="histogramOption" height="320px" :loading="loading" />
        </div>
      </div>
    </div>

    <!-- 检测结果明细 -->
    <div class="rv-card">
      <div class="rv-card-header">
        <span class="rv-card-title">检测结果明细</span>
        <span class="rv-text-secondary">共 {{ totalCount }} 条记录</span>
      </div>
      <div class="rv-card-body">
        <el-table v-loading="loading" :data="detections" size="small" border max-height="420">
          <el-table-column prop="id" label="记录编号" width="110" />
          <el-table-column prop="target" label="目标类型" min-width="130" show-overflow-tooltip />
          <el-table-column label="置信度" min-width="200">
            <template #default="{ row }">
              <div class="flex items-center gap-2">
                <el-progress
                  :percentage="Math.round(row.confidence * 100)"
                  :color="confidenceColor(row.confidence)"
                  :stroke-width="12"
                />
                <span class="rv-num text-xs text-slate-500">{{ (row.confidence * 100).toFixed(1) }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="检测时间" min-width="150">
            <template #default="{ row }">
              <span class="rv-num">{{ row.time }}</span>
            </template>
          </el-table-column>
          <el-table-column label="处置状态" width="110" align="center">
            <template #default="{ row }">
              <StatusTag :status="row.status" />
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无检测结果" :image-size="70" />
          </template>
        </el-table>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---------------------------- 摄像头实时识别 ---------------------------- */
.fp-camera {
  position: relative;
  width: 100%;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--rv-border);
  border-radius: var(--rv-radius);
  background: #0f172a;
  overflow: hidden;
}

/* 画面容器按图片/视频真实比例自适应，完整显示不裁切，
   保证识别框（按整图百分比绘制）与画面严格对齐 */
.fp-camera-frame {
  position: relative;
  display: inline-block;
  max-width: 100%;
  line-height: 0;
}

.fp-camera-media {
  display: block;
  max-width: 100%;
  max-height: 58vh;
  width: auto;
  height: auto;
  object-fit: contain;
}

.fp-camera-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
}

.fp-box {
  position: absolute;
  border: 2px solid #dc2626;
  border-radius: 4px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.55);
}

.fp-box__label {
  position: absolute;
  left: -2px;
  top: -20px;
  padding: 0 6px;
  height: 18px;
  line-height: 18px;
  font-size: 11px;
  color: #fff;
  border-radius: 3px;
  white-space: nowrap;
}

.fp-camera-live {
  position: absolute;
  left: 10px;
  top: 10px;
  padding: 0 8px;
  height: 20px;
  line-height: 20px;
  font-size: 11px;
  color: #fff;
  background: #dc2626;
  border-radius: 10px;
  letter-spacing: 1px;
}

.fp-camera-back {
  position: absolute;
  right: 8px;
  top: 8px;
  background: rgba(255, 255, 255, 0.92);
}

.fp-camera-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.fp-camera-tip {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--rv-text-secondary);
}

.fp-result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.fp-result-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  overflow: auto;
}

.fp-result {
  border: 1px solid var(--rv-border);
  border-radius: var(--rv-radius);
  padding: 10px;
}

.fp-result__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.fp-result__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--rv-text);
}

.fp-result__row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 12px;
}

.fp-result__meta {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--rv-text-secondary);
}
</style>
