"""生成本地标签库（前端过滤白名单）。

从 config/label_db.json 生成 src/api/labelDb.ts：
推理结果中只保留命中塑料瓶别名集合的目标，其余（塑料袋/泡沫/树枝/垃圾等）一律丢弃，
实现「识别结果只可能是一种：塑料瓶」。

用法：
    python scripts/build_label_db.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_label_db  # noqa: E402

TARGET_TS = ROOT.parent / "src" / "api" / "labelDb.ts"

TEMPLATE = '''/**
 * 本地标签库：河道巡检唯一目标类别（塑料瓶）白名单
 *
 * 由 ai-training/scripts/build_label_db.py 依据 ai-training/config/label_db.json 生成，请勿手改。
 * 作用：推理结果过滤 —— 命中白名单的目标才保留，塑料袋/泡沫/树枝等其他物体一律丢弃。
 */

/** 塑料瓶类别名（含中英文与常见写法别名） */
export const PLASTIC_BOTTLE_ALIASES: readonly string[] = {aliases}

/** 塑料瓶业务标签（统一展示名） */
export const PLASTIC_BOTTLE_TARGET_CN = '{target_cn}'

/** 塑料瓶目标业务字段 */
export const PLASTIC_BOTTLE_META = {meta} as const

/**
 * 判断识别目标是否属于塑料瓶
 * @param target 模型输出的目标类别名
 */
export function isPlasticBottle(target: string): boolean {{
  const key = target.trim().toLowerCase().replace(/[-\\s]+/g, '_')
  return PLASTIC_BOTTLE_ALIASES.includes(key)
}}
'''


def main() -> int:
    label_db = load_label_db()
    aliases = [a.strip().lower().replace("-", "_").replace(" ", "_") for a in label_db["aliases"]]
    aliases = sorted(set(aliases))
    meta = label_db["meta"]
    meta_text = "{\n  priorRisk: %d,\n  source: '%s',\n  suggestion: '%s',\n}" % (
        meta["priorRisk"], meta["source"], meta["suggestion"]
    )
    alias_text = json.dumps(aliases, ensure_ascii=False, indent=2)
    TARGET_TS.write_text(
        TEMPLATE.format(
            aliases=alias_text,
            target_cn=label_db["target_cn"],
            meta=meta_text,
        ),
        encoding="utf-8",
    )
    print(f"已生成 {TARGET_TS}（别名 {len(aliases)} 个）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
