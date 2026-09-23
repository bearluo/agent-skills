#!/usr/bin/env python3
"""grid_slice.py — 按 layout.json 把 ChatGPT 生成的网格图切回单张小图。

用法：
  python grid_slice.py --input filled.png --layout layout.json --out-dir tiles \
    [--inset 8] [--resize 256] [--transparent --key "#00ff00" --key-thresh 100]

要点：
  - --inset 每格四边内缩像素，避开网格线/邻格溢出（网格背景是均匀绿幕，切松一点没关系）。
  - --transparent 用简单 key 距离阈值把绿底转 alpha（自足、可移植）。
    需要更干净的抗锯齿边缘时，改为对每张 tile 跑 Codex 自带的
    remove_chroma_key.py（--soft-matte --despill），见 codex-imagegen SKILL。
"""
import argparse, json, os
from PIL import Image


def hex2rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def key_to_alpha(im, key_rgb, thresh):
    im = im.convert("RGBA")
    px = im.load()
    kr, kg, kb = key_rgb
    t2 = thresh * thresh
    W, H = im.size
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if (r - kr) ** 2 + (g - kg) ** 2 + (b - kb) ** 2 <= t2:
                px[x, y] = (r, g, b, 0)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--layout", required=True)
    ap.add_argument("--out-dir", default="tiles")
    ap.add_argument("--inset", type=int, default=8, help="每格四边内缩像素")
    ap.add_argument("--resize", type=int, default=None, help="每张统一缩放到 NxN")
    ap.add_argument("--transparent", action="store_true", help="按 key 色抠透明")
    ap.add_argument("--key", default="#00ff00")
    ap.add_argument("--key-thresh", type=int, default=100)
    args = ap.parse_args()

    with open(args.layout, encoding="utf-8") as f:
        layout = json.load(f)
    src = Image.open(args.input).convert("RGBA")

    # 生成图尺寸若 != 模板画布，按比例换算坐标
    C = layout["canvas"]
    sx = src.size[0] / C
    sy = src.size[1] / C

    os.makedirs(args.out_dir, exist_ok=True)
    key = hex2rgb(args.key)
    out = []
    for cell in layout["cells"]:
        x = round((cell["x"] + args.inset) * sx)
        y = round((cell["y"] + args.inset) * sy)
        w = round((cell["w"] - 2 * args.inset) * sx)
        h = round((cell["h"] - 2 * args.inset) * sy)
        tile = src.crop((x, y, x + w, y + h))
        if args.transparent:
            tile = key_to_alpha(tile, key, args.key_thresh)
        if args.resize:
            tile = tile.resize((args.resize, args.resize), Image.LANCZOS)
        name = f"{cell['index']:02d}_{cell['label']}.png".replace("/", "_").replace("\\", "_")
        p = os.path.join(args.out_dir, name)
        tile.save(p)
        out.append(os.path.abspath(p))

    print(json.dumps({"ok": True, "tiles": out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
