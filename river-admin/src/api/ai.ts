import { get, postForm } from './request'

/* ---------------------------- 污染扩散模拟 ---------------------------- */
export interface DiffusionPoint {
  x: number
  y: number
  z: number
}

export function fetchDiffusion(): Promise<DiffusionPoint[]> {
  return get<DiffusionPoint[]>('/ai/diffusion')
}

/* ---------------------------- 排污口指纹 ------------------------------ */
export interface Fingerprint {
  id: string
  x: number
  y: number
  risk: number
  source: string
  status: string
}

export function fetchFingerprints(): Promise<Fingerprint[]> {
  return get<Fingerprint[]>('/ai/fingerprint')
}

/* ---------------------------- 许可数据比对 ---------------------------- */
export interface CompareRow {
  id: string
  factor: string
  value: number
  standard: number
  exceed: boolean
  permitNo: string
}

export function fetchCompareRows(): Promise<CompareRow[]> {
  return get<CompareRow[]>('/ai/compare')
}

/* ---------------------------- 污染源锁定 ------------------------------ */
export interface SourceItem extends Fingerprint {
  distance: number
}

export function fetchSources(): Promise<SourceItem[]> {
  return get<SourceItem[]>('/ai/source')
}

/* ---------------------------- 目标检测模型 ---------------------------- */
export interface DetectionItem {
  id: string
  target: string
  confidence: number
  time: string
  status: string
}

export function fetchDetections(): Promise<DetectionItem[]> {
  return get<DetectionItem[]>('/ai/detection')
}

/* ---------------------------- 水质预测模型 ---------------------------- */
export interface PredictionPoint {
  date: string
  actual: number
  predict: number
  lower: number
  upper: number
}

export function fetchPrediction(): Promise<PredictionPoint[]> {
  return get<PredictionPoint[]>('/ai/prediction')
}

/* ---------------------------- 污染溯源模型 ---------------------------- */
export interface TracingStep {
  step: number
  node: string
  time: string
  desc: string
}

export function fetchTracing(): Promise<TracingStep[]> {
  return get<TracingStep[]>('/ai/tracing')
}

/* ---------------------------- 履职评估模型 ---------------------------- */
export interface EvaluationItem {
  id: string
  chiefName: string
  score: number
  level: string
  suggestion: string
}

export function fetchEvaluation(): Promise<EvaluationItem[]> {
  return get<EvaluationItem[]>('/ai/evaluation')
}

/* ---------------------------- 摄像头识别 ------------------------------ */
export interface CameraRecognitionItem {
  id: string
  target: string
  confidence: number
  /** 目标中心点横坐标（相对画面百分比） */
  x: number
  /** 目标中心点纵坐标（相对画面百分比） */
  y: number
  /** 识别框宽度（百分比） */
  width: number
  /** 识别框高度（百分比） */
  height: number
  risk: number
  source: string
  suggestion: string
}

export interface CameraRecognitionResult {
  taskId: string
  scene: string
  model: string
  capturedAt: string
  elapsed: number
  /** 是否为模拟识别结果（Mock 服务返回 true，真实推理服务返回 false） */
  mock: boolean
  items: CameraRecognitionItem[]
}

/** 摄像头/图片识别（multipart 上传，scene 区分实时抓拍与上传图片） */
export function recognizeCamera(payload: {
  file: Blob
  scene: string
  width?: number
  height?: number
}): Promise<CameraRecognitionResult> {
  const form = new FormData()
  form.append('image', payload.file, `capture-${payload.scene}.jpg`)
  form.append('scene', payload.scene)
  if (payload.width) form.append('width', String(Math.round(payload.width)))
  if (payload.height) form.append('height', String(Math.round(payload.height)))
  // VITE_AI_DETECT_BASE 可选：将识别接口指向独立推理网关（默认复用 /api 实例 baseURL）
  const detectBase = (import.meta.env.VITE_AI_DETECT_BASE as string | undefined) ?? ''
  return postForm<CameraRecognitionResult>('/ai/camera/recognize', form, detectBase ? { baseURL: detectBase } : undefined)
}
