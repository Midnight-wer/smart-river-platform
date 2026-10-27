/**
 * 视觉识别 API（阿里云 MaaS · qwen3-vl-plus，OpenAI 兼容接口）
 *
 * 浏览器请求同源 /ai-api/* 路径，由 Vite dev server 代理转发到阿里云端点，
 * Authorization（API Key）在 dev server 端注入，不会进入前端构建产物与浏览器。
 * 代理未配置（缺少 AI_API_KEY）时请求 404，调用方需自行降级。
 *
 * 职责划分：模型只输出目标类别、置信度与 bbox（百分比坐标），
 * 风险值 / 来源预判 / 处置建议由前端按类别映射补齐（与 YOLO 接入方案 §5 一致）。
 *
 * 目标类别唯一：塑料瓶。识别结果统一经本地标签库（./labelDb）过滤，
 * 塑料袋、泡沫、树枝、垃圾等其他物体一律丢弃。
 */
import { isPlasticBottle, PLASTIC_BOTTLE_META, PLASTIC_BOTTLE_TARGET_CN } from './labelDb'

/** 视觉模型输出的原始识别目标 */
export interface VisionItem {
  target: string
  confidence: number
  /** 目标框中心点横坐标（图片宽度百分比 0-100） */
  x: number
  /** 目标框中心点纵坐标（图片高度百分比 0-100） */
  y: number
  /** 目标框宽度（百分比） */
  width: number
  /** 目标框高度（百分比） */
  height: number
}

/** 目标类别的业务字段（风险基数 / 来源预判 / 处置建议）——唯一目标类别为塑料瓶 */
export function targetMeta(): { priorRisk: number; source: string; suggestion: string } {
  return PLASTIC_BOTTLE_META
}

/** 识别提示词：只检测塑料瓶，强制百分比 bbox 的严格 JSON 输出
 *  与 ai-training/config/prompts.json 的 inference_prompt 保持一致（微调后模型已习得该格式） */
const DETECT_PROMPT = [
  '检测图片中的塑料瓶，输出严格 JSON：{"objects":[{"target":"塑料瓶","confidence":0.95,"x":35.5,"y":62.0,"width":18.2,"height":9.4}]}。',
  'x、y 为塑料瓶的**中心点**坐标，width、height 为塑料瓶的**完整外接矩形**尺寸，取值范围均为 0 到 100（按图片宽高百分比换算，不要输出像素坐标）。',
  '框必须完整包含整个瓶体（瓶盖、瓶身、瓶底都要在框内），四周留出约 10% 余量，不要只框瓶身中段或标签部分。',
  '没有塑料瓶时输出 {"objects":[]}。只输出 JSON。',
].join('')

/** Blob 转 data URL（直接作为 image_url 传给模型） */
function blobToDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(file)
  })
}

/** 识别结果的图片尺寸信息，用于坐标单位自适应（部分模型会返回像素坐标） */
export interface VisionImageSize {
  width?: number
  height?: number
}

/** 识别框放大系数（可选补偿）：通过 VITE_AI_BBOX_SCALE 调整，1 表示不放大。
 *  微调后的模型会学到完整框选，届时保持 1 即可。 */
const BBOX_SCALE = Number((import.meta.env.VITE_AI_BBOX_SCALE as string | undefined) ?? '1') || 1

/** 检测模式：local = 本地离线 YOLO 服务（默认，完全不联网）；cloud = 百炼云端视觉模型 */
const DETECT_MODE = (import.meta.env.VITE_DETECT_MODE as string | undefined) === 'cloud' ? 'cloud' : 'local'

/** 当前检测模式 */
export function detectMode(): 'local' | 'cloud' {
  return DETECT_MODE
}

/** 当前使用的模型展示名 */
export function modelLabel(): string {
  if (DETECT_MODE === 'local') return '本地 YOLO（离线）'
  return (import.meta.env.VITE_AI_VISION_MODEL as string | undefined) ?? 'qwen3-vl-plus'
}

/** 从模型输出中稳健解析 objects 数组（容忍 ```json 包裹与前后杂文） */
function parseItems(content: string, size: VisionImageSize = {}): VisionItem[] {
  const start = content.indexOf('{')
  const end = content.lastIndexOf('}')
  if (start === -1 || end <= start) throw new Error('识别结果解析失败')
  let parsed: { objects?: unknown }
  try {
    parsed = JSON.parse(content.slice(start, end + 1))
  } catch {
    throw new Error('识别结果解析失败')
  }
  const objects = Array.isArray(parsed.objects) ? parsed.objects : []
  return objects
    .map((raw): VisionItem | null => {
      if (!raw || typeof raw !== 'object') return null
      const item = raw as Record<string, unknown>
      const target = String(item.target ?? '').trim()
      // 本地标签库过滤：非塑料瓶目标（塑料袋/泡沫/树枝/垃圾等）一律丢弃
      if (!target || !isPlasticBottle(target)) return null
      const num = (value: unknown): number => {
        const parsed = Number(value)
        return Number.isFinite(parsed) ? parsed : 0
      }
      const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value))
      // 坐标单位自适应：模型偶尔返回像素坐标，需按图片尺寸换算成百分比
      let x = num(item.x)
      let y = num(item.y)
      let boxWidth = num(item.width)
      let boxHeight = num(item.height)
      const looksLikePixel = Math.max(x, y) > 100 || Math.max(boxWidth, boxHeight) > 60
      if (looksLikePixel && size.width && size.height) {
        x = (x / size.width) * 100
        y = (y / size.height) * 100
        boxWidth = (boxWidth / size.width) * 100
        boxHeight = (boxHeight / size.height) * 100
      }
      return {
        // 统一业务标签，避免模型输出别名导致展示不一致
        target: PLASTIC_BOTTLE_TARGET_CN,
        confidence: clamp(num(item.confidence), 0, 1),
        x: clamp(x, 0, 100),
        y: clamp(y, 0, 100),
        width: clamp(boxWidth * BBOX_SCALE, 1, 100),
        height: clamp(boxHeight * BBOX_SCALE, 1, 100),
      }
    })
    .filter((item): item is VisionItem => item !== null)
}

/**
 * 调用本地离线检测服务（Ultralytics YOLO，经 Vite 代理同源转发）
 * 服务端已把像素坐标换算为百分比，此处只做标签库过滤与取值约束。
 */
async function detectLocally(file: Blob, conf = 0.3, scene = 'camera'): Promise<VisionItem[]> {
  const dataUrl = await blobToDataUrl(file)
  const response = await fetch('/detect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: dataUrl, conf, scene }),
  })
  if (!response.ok) throw new Error(`本地检测服务异常（${response.status}）`)
  const result = (await response.json()) as {
    error?: string
    items?: Array<{ target?: string; confidence?: number; x?: number; y?: number; width?: number; height?: number }>
  }
  if (result.error) throw new Error(result.error)
  const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value))
  return (result.items ?? [])
    .filter((item) => !!item.target && isPlasticBottle(item.target))
    .map((item) => ({
      target: PLASTIC_BOTTLE_TARGET_CN,
      confidence: clamp(Number(item.confidence ?? 0), 0, 1),
      x: clamp(Number(item.x ?? 0), 0, 100),
      y: clamp(Number(item.y ?? 0), 0, 100),
      width: clamp(Number(item.width ?? 1) * BBOX_SCALE, 1, 100),
      height: clamp(Number(item.height ?? 1) * BBOX_SCALE, 1, 100),
    }))
}

/**
 * 调用视觉大模型识别图片（默认 qwen3-vl-plus）
 * @returns 识别目标列表（含百分比 bbox），空数组表示未检测到目标
 */
export async function recognizeByVision(
  file: Blob,
  size: VisionImageSize = {},
  timeoutMs = 45000,
  scene = 'camera',
): Promise<VisionItem[]> {
  // 本地离线模式：直接走本地 YOLO 服务，不访问任何外网
  if (DETECT_MODE === 'local') return detectLocally(file, 0.35, scene)

  const model = (import.meta.env.VITE_AI_VISION_MODEL as string | undefined) ?? 'qwen3-vl-plus'
  const dataUrl = await blobToDataUrl(file)

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch('/ai-api/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        temperature: 0.1,
        response_format: { type: 'json_object' },
        messages: [
          {
            role: 'user',
            content: [
              { type: 'image_url', image_url: { url: dataUrl } },
              { type: 'text', text: DETECT_PROMPT },
            ],
          },
        ],
      }),
      signal: controller.signal,
    })
    if (!response.ok) {
      throw new Error(`识别服务响应异常（${response.status}）`)
    }
    const result = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>
    }
    const content = result.choices?.[0]?.message?.content
    if (!content) throw new Error('识别服务返回为空')
    return parseItems(content, size)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('识别超时，请稍后重试')
    }
    throw error instanceof Error ? error : new Error('视觉识别失败')
  } finally {
    clearTimeout(timer)
  }
}
