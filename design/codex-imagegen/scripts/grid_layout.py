#!/usr/bin/env python3
"""grid_layout.py — 计算 NxM 网格布局 + 生成给 ChatGPT/Codex 的参考模板图。

背景：ChatGPT/Codex 的 image_gen 每次固定输出 1024x1024，单张只画一个资源很浪费。
把多个小资源打包进一张网格图，一次生成、事后按坐标切片。

输出：
  - layout.json : 每个格子的像素矩形（供 grid_slice.py 切片）
  - template.png: 带编号/标签的网格参考图（作为 image_gen 的 reference 引导排版，即“样例图片”）

用法：
  python grid_layout.py --labels "carrot,clover,coin,star" \
    --canvas 1024 --gutter 28 --margin 28 --bg "#00ff00" \
    --out-template template.png --out-layout layout.json
"""
import argparse, json, math, os
from PIL import Image, ImageDraw, ImageFont


def near_square(n):
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    return cols, rows


def load_font(size):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=None, help="资源数量（与 --labels 二选一）")
    ap.add_argument("--labels", type=str, default=None, help="逗号分隔的每格标签，数量即格数")
    ap.add_argument("--cols", type=int, default=None)
    ap.add_argument("--rows", type=int, default=None)
    ap.add_argument("--canvas", type=int, default=1024)
    ap.add_argument("--gutter", type=int, default=28, help="格子间距（留白防主体溢出到邻格）")
    ap.add_argument("--margin", type=int, default=28, help="画布外边距")
    ap.add_argument("--bg", type=str, default="#00ff00", help="模板背景色（默认绿幕，便于抠透明）")
    ap.add_argument("--grid-color", type=str, default="#111111")
    ap.add_argument("--no-annot", action="store_true", help="不画编号/标签（密集网格用，只留格线）")
    ap.add_argument("--out-template", type=str, default="template.png")
    ap.add_argument("--out-layout", type=str, default="layout.json")
    args = ap.parse_args()

    labels = None
    if args.labels:
        labels = [s.strip() for s in args.labels.split(",") if s.strip()]
        n = len(labels)
    elif args.count:
        n = args.count
    else:
        ap.error("需要 --count 或 --labels")

    if args.cols and args.rows:
        cols, rows = args.cols, args.rows
    elif args.cols:
        cols, rows = args.cols, math.ceil(n / args.cols)
    elif args.rows:
        rows, cols = args.rows, math.ceil(n / args.rows)
    else:
        cols, rows = near_square(n)
    if cols * rows < n:
        ap.error(f"网格 {cols}x{rows} 放不下 {n} 个")

    C, m, g = args.canvas, args.margin, args.gutter
    cell_w = (C - 2 * m - (cols - 1) * g) / cols
    cell_h = (C - 2 * m - (rows - 1) * g) / rows
    if cell_w < 1 or cell_h < 1:
        ap.error("格子太小：调小 margin/gutter 或减少格数")

    cells = []
    for i in range(n):
        r, c = i // cols, i % cols
        cells.append({
            "index": i + 1,
            "label": labels[i] if labels else str(i + 1),
            "x": round(m + c * (cell_w + g)),
            "y": round(m + r * (cell_h + g)),
            "w": round(cell_w),
            "h": round(cell_h),
        })

    layout = {"canvas": C, "cols": cols, "rows": rows, "gutter": g,
              "margin": m, "bg": args.bg, "cells": cells}
    with open(args.out_layout, "w", encoding="utf-8") as f:
        json.dump(layout, f, ensure_ascii=False, indent=2)

    # 参考模板：背景 + 每格描边 + 大号编号(左上) + 标签(底部居中)
    img = Image.new("RGB", (C, C), args.bg)
    d = ImageDraw.Draw(img)
    line_w = max(1, int(min(cell_w, cell_h) / 18))
    num_font = load_font(max(10, int(min(cell_w, cell_h) * 0.26)))
    lbl_font = load_font(max(10, int(min(cell_w, cell_h) * 0.11)))
    for cell in cells:
        x, y, w, h = cell["x"], cell["y"], cell["w"], cell["h"]
        d.rectangle([x, y, x + w, y + h], outline=args.grid_color, width=line_w)
        if not args.no_annot:
            d.text((x + 8, y + 6), str(cell["index"]), fill=args.grid_color, font=num_font)
            lbl = cell["label"]
            tb = d.textbbox((0, 0), lbl, font=lbl_font)
            tw = tb[2] - tb[0]
            d.text((x + (w - tw) / 2, y + h - (tb[3] - tb[1]) - 12),
                   lbl, fill=args.grid_color, font=lbl_font)
    img.save(args.out_template)

    print(json.dumps({"ok": True, "cols": cols, "rows": rows, "n": n,
                      "cell_w": round(cell_w), "cell_h": round(cell_h),
                      "template": os.path.abspath(args.out_template),
                      "layout": os.path.abspath(args.out_layout)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
