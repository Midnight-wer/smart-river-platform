/**
 * 本地标签库：河道巡检唯一目标类别（塑料瓶）白名单
 *
 * 由 ai-training/scripts/build_label_db.py 依据 ai-training/config/label_db.json 生成，请勿手改。
 * 作用：推理结果过滤 —— 命中白名单的目标才保留，塑料袋/泡沫/树枝等其他物体一律丢弃。
 */

/** 塑料瓶类别名（含中英文与常见写法别名） */
export const PLASTIC_BOTTLE_ALIASES: readonly string[] = [
  "bottle",
  "bottles",
  "pet_bottle",
  "pet_bottle_garbage",
  "petbottle",
  "plastic_bottle",
  "plastic_bottle_garbage",
  "plasticbottle",
  "塑料瓶",
  "塑料瓶子",
  "矿泉水瓶",
  "饮料瓶"
]

/** 塑料瓶业务标签（统一展示名） */
export const PLASTIC_BOTTLE_TARGET_CN = '塑料瓶'

/** 塑料瓶目标业务字段 */
export const PLASTIC_BOTTLE_META = {
  priorRisk: 20,
  source: '生活垃圾倾倒',
  suggestion: '建议现场核查并清理',
} as const

/**
 * 判断识别目标是否属于塑料瓶
 * @param target 模型输出的目标类别名
 */
export function isPlasticBottle(target: string): boolean {
  const key = target.trim().toLowerCase().replace(/[-\s]+/g, '_')
  return PLASTIC_BOTTLE_ALIASES.includes(key)
}
