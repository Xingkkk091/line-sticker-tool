#!/usr/bin/env python3
"""
LINE 貼圖自動化工具
功能：自動切割 Gemini 排版圖 → 去背 → 輸出 500x500 PNG
支援：8張（2x4）或 16張（4x4）排版
"""

import os
import sys
import io
from pathlib import Path
from PIL import Image
from rembg import remove, new_session


def detect_grid(image: Image.Image) -> tuple[int, int]:
    """根據圖片比例自動判斷格狀排版"""
    w, h = image.size
    ratio = w / h

    if 0.85 <= ratio <= 1.15:
        # 接近正方形 → 4x4 = 16 張
        return 4, 4
    elif ratio < 0.65:
        # 直式 → 2x4 = 8 張
        return 2, 4
    elif ratio > 1.55:
        # 橫式 → 4x2 = 8 張
        return 4, 2
    else:
        print(f"  [警告] 無法自動判斷排版（比例 {ratio:.2f}），預設使用 4x4")
        return 4, 4


def slice_grid(image: Image.Image, cols: int, rows: int) -> list[Image.Image]:
    """將排版圖切成單格"""
    w, h = image.size
    cell_w = w // cols
    cell_h = h // rows
    cells = []

    for row in range(rows):
        for col in range(cols):
            x1 = col * cell_w
            y1 = row * cell_h
            x2 = x1 + cell_w
            y2 = y1 + cell_h
            cells.append(image.crop((x1, y1, x2, y2)))

    return cells


def remove_bg(image: Image.Image, session) -> Image.Image:
    """用 rembg 去背，回傳 RGBA 圖片"""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    result_bytes = remove(buf.getvalue(), session=session)
    return Image.open(io.BytesIO(result_bytes)).convert("RGBA")


def fit_to_canvas(image: Image.Image, size: int = 500) -> Image.Image:
    """等比縮放至 size，置中貼到透明畫布"""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    image.thumbnail((size, size), Image.LANCZOS)
    x = (size - image.width) // 2
    y = (size - image.height) // 2
    canvas.paste(image, (x, y), image)
    return canvas


def process(input_path: str, output_dir: str = None, grid: str = None):
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"[錯誤] 找不到檔案：{input_path}")
        return

    # 建立輸出資料夾
    if output_dir is None:
        output_dir = input_path.parent / input_path.stem
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n載入圖片：{input_path.name}")
    image = Image.open(input_path).convert("RGBA")
    print(f"  尺寸：{image.width} x {image.height}")

    # 判斷格狀排版
    if grid:
        try:
            cols, rows = map(int, grid.lower().split("x"))
        except Exception:
            print(f"[錯誤] grid 格式錯誤，請用如 4x4 或 2x4")
            return
    else:
        cols, rows = detect_grid(image)

    total = cols * rows
    print(f"  排版：{cols} 欄 x {rows} 列 = {total} 張貼圖")

    # 切割
    print("\n切割中...")
    cells = slice_grid(image, cols, rows)

    # 載入 rembg 模型（只載入一次，加快速度）
    print("載入去背模型（首次需下載，約 200MB）...")
    session = new_session("u2net")

    # 逐張去背
    print(f"\n開始處理 {total} 張貼圖...\n")
    for i, cell in enumerate(cells, 1):
        print(f"  [{i:02d}/{total}] 去背中...", end=" ", flush=True)
        result = remove_bg(cell, session)
        result = fit_to_canvas(result, 500)

        out_file = output_dir / f"sticker_{i:02d}.png"
        result.save(out_file, "PNG")
        print(f"→ {out_file.name}")

    print(f"\n完成！{total} 張貼圖已儲存至：")
    print(f"  {output_dir.resolve()}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("=" * 50)
        print("  LINE 貼圖自動化工具")
        print("=" * 50)
        print()
        print("用法：")
        print("  python sticker_tool.py <圖片路徑>")
        print("  python sticker_tool.py <圖片路徑> <輸出資料夾>")
        print("  python sticker_tool.py <圖片路徑> <輸出資料夾> 4x4")
        print()
        print("範例：")
        print("  python sticker_tool.py stickers.png")
        print("  python sticker_tool.py stickers.png output 2x4")
        print()
        print("  （也可以直接把圖片拖曳到 run.bat 上）")
        sys.exit(0)

    input_file = sys.argv[1]
    out_folder = sys.argv[2] if len(sys.argv) > 2 else None
    grid_arg = sys.argv[3] if len(sys.argv) > 3 else None

    process(input_file, out_folder, grid_arg)
