"""手持瓶人工标注小工具（tkinter，双击标注）。

用法：
    python scripts/annotate_gui.py                # 标注所有缺标签的手持瓶图
    python scripts/annotate_gui.py --all          # 重标全部（含已有标签）

操作：
    左键点一下 = 瓶子左上角；再点一下 = 瓶子右下角，自动保存并下一张
    「无瓶」按钮 = 存空标签（负样本）
    「撤销」按钮 = 重画当前这张
    「跳过」按钮 = 稍后再标
"""
from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "datasets" / "handheld-bottles" / "images"
LBL_DIR = ROOT / "datasets" / "handheld-bottles" / "labels"
MAX_W, MAX_H = 1100, 620


def save_label(stem: str, box_norm: tuple[float, float, float, float] | None) -> None:
    LBL_DIR.mkdir(parents=True, exist_ok=True)
    path = LBL_DIR / f"{stem}.txt"
    if box_norm is None:
        path.write_text("", encoding="utf-8")
    else:
        cx, cy, bw, bh = box_norm
        path.write_text(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n", encoding="utf-8")


def has_label(stem: str) -> bool:
    path = LBL_DIR / f"{stem}.txt"
    return path.exists()


class App:
    def __init__(self, todo: list[Path]):
        self.todo = todo
        self.index = 0
        self.points: list[tuple[int, int]] = []
        self.photo = None
        self.scale = 1.0
        self.size = (0, 0)

        self.win = tk.Tk()
        self.win.title("手持瓶标注")
        self.canvas = tk.Canvas(self.win, bg="#111", width=MAX_W, height=MAX_H)
        self.canvas.pack()
        bar = tk.Frame(self.win)
        bar.pack(fill="x")
        self.info = tk.Label(bar, text="", font=("Arial", 12))
        self.info.pack(side="left", padx=8)
        for text, cmd in (("无瓶", self.mark_none), ("撤销", self.undo),
                          ("跳过", self.skip)):
            tk.Button(bar, text=text, command=cmd, width=8).pack(side="left", padx=4)
        self.canvas.bind("<Button-1>", self.on_click)

    def load(self) -> None:
        self.points = []
        if self.index >= len(self.todo):
            self.win.quit()
            return
        path = self.todo[self.index]
        self.stem = path.stem
        img = Image.open(path).convert("RGB")
        self.size = img.size
        scale = min(MAX_W / img.width, MAX_H / img.height, 1.0)
        self.scale = scale
        img = img.resize((int(img.width * scale), int(img.height * scale)))
        draw = ImageDraw.Draw(img)
        draw.text((10, 8), path.name, fill=(255, 255, 0))
        self.photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.info.config(text=f"{self.index + 1}/{len(self.todo)}  {path.name}"
                         "   左键点瓶左上角 → 再点右下角")

    def on_click(self, event) -> None:
        # 画布是缩放显示，换算回原图坐标
        ox, oy = event.x / self.scale, event.y / self.scale
        self.points.append((ox, oy))
        r = 5
        self.canvas.create_oval(event.x - r, event.y - r, event.x + r, event.y + r,
                                fill="#00ff00", outline="")
        if len(self.points) == 2:
            xs = sorted(p[0] for p in self.points)
            ys = sorted(p[1] for p in self.points)
            x1, x2, y1, y2 = xs[0], xs[1], ys[0], ys[1]
            W, H = self.size
            if abs(x2 - x1) < 8 or abs(y2 - y1) < 8:
                self.info.config(text="框太小，请重新点（撤销）")
                self.undo()
                return
            self.canvas.create_rectangle(x1 * self.scale, y1 * self.scale,
                                         x2 * self.scale, y2 * self.scale,
                                         outline="#ff3030", width=3)
            cx, cy = (x1 + x2) / 2 / W, (y1 + y2) / 2 / H
            bw, bh = (x2 - x1) / W, (y2 - y1) / H
            save_label(self.stem, (cx, cy, bw, bh))
            self.win.after(180, self.next_image)
        elif len(self.points) > 2:
            self.undo()
            self.on_click(event)

    def mark_none(self) -> None:
        save_label(self.stem, None)
        self.next_image()

    def undo(self) -> None:
        self.index -= 0  # 重画当前
        self.load()

    def skip(self) -> None:
        self.todo.append(self.todo[self.index])
        self.next_image()

    def next_image(self) -> None:
        self.index += 1
        self.load()

    def run(self) -> None:
        self.load()
        self.win.mainloop()
        print(f"标注会话结束，进度 {min(self.index, len(self.todo))}/{len(self.todo)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="手持瓶双击标注")
    parser.add_argument("--all", action="store_true", help="重标全部图片")
    args = parser.parse_args()

    images = sorted(IMG_DIR.glob("raw_*.jpg"))
    todo = images if args.all else [p for p in images if not has_label(p.stem)]
    if not todo:
        print("全部图片已有标签，无需标注（--all 可强制重标）")
        return 0
    print(f"待标注 {len(todo)} 张")
    App(todo).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
