import io
import zipfile
import numpy as np
import requests
import streamlit as st
from PIL import Image

st.set_page_config(page_title="LINE 貼圖自動化", page_icon="🐦", layout="wide")

st.title("🐦 LINE 貼圖自動化工具")
st.caption("上傳 Gemini 排版圖 → 自動切割 → 去背 → 下載 500×500 PNG")

# ── 側邊欄設定 ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 設定")
    grid_mode = st.radio(
        "排版格式",
        ["自動偵測", "4×4（16張）", "2×4（8張）", "4×2（8張）"],
        index=0,
    )
    output_size = st.slider("輸出尺寸（px）", 300, 600, 500, step=50)

    st.markdown("---")
    st.subheader("🔑 remove.bg API Key")
    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder="貼上你的 remove.bg API key",
        help="免費申請：https://www.remove.bg/api",
    )
    st.caption("免費帳號每月 50 張，品質極佳")
    if not api_key:
        st.warning("請輸入 API Key 才能使用去背功能")


# ── 工具函數 ──────────────────────────────────────────────
def detect_grid(image: Image.Image) -> tuple[int, int]:
    w, h = image.size
    ratio = w / h
    if 0.85 <= ratio <= 1.15:
        return 4, 4
    elif ratio < 0.65:
        return 2, 4
    elif ratio > 1.55:
        return 4, 2
    return 4, 4


def slice_grid(image: Image.Image, cols: int, rows: int) -> list[Image.Image]:
    w, h = image.size
    cw, ch = w // cols, h // rows
    return [
        image.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
        for r in range(rows)
        for c in range(cols)
    ]


def remove_bg_api(image: Image.Image, key: str) -> Image.Image:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    resp = requests.post(
        "https://api.remove.bg/v1.0/removebg",
        files={"image_file": ("image.png", buf, "image/png")},
        data={"size": "auto"},
        headers={"X-Api-Key": key},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"remove.bg 錯誤：{resp.status_code} {resp.text[:200]}")
    return Image.open(io.BytesIO(resp.content)).convert("RGBA")


def fit_canvas(image: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    image.thumbnail((size, size), Image.LANCZOS)
    x = (size - image.width) // 2
    y = (size - image.height) // 2
    canvas.paste(image, (x, y), image)
    return canvas


def to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def make_checker(size: int) -> Image.Image:
    tile = 20
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    for ty in range(0, size, tile):
        for tx in range(0, size, tile):
            arr[ty:ty+tile, tx:tx+tile] = 200 if (tx // tile + ty // tile) % 2 == 0 else 160
    return Image.fromarray(arr)


# ── 主介面 ────────────────────────────────────────────────
uploaded = st.file_uploader(
    "拖曳或選擇排版圖",
    type=["png", "jpg", "jpeg", "webp"],
    label_visibility="collapsed",
)

if uploaded:
    image = Image.open(uploaded).convert("RGBA")
    st.image(image, caption=f"原始圖片 {image.width}×{image.height}", width="stretch")

    if grid_mode == "自動偵測":
        cols, rows = detect_grid(image)
        st.info(f"自動偵測：**{cols}×{rows}（{cols * rows} 張）**")
    else:
        cols, rows = map(int, grid_mode.split("（")[0].split("×"))

    total = cols * rows

    if st.button(f"🚀 開始處理（{total} 張貼圖）", type="primary", disabled=not api_key):
        cells = slice_grid(image, cols, rows)
        progress = st.progress(0, text="準備中...")
        status = st.empty()
        results: list[Image.Image] = []
        errors = []

        for i, cell in enumerate(cells):
            status.text(f"去背第 {i+1}/{total} 張...")
            try:
                result = remove_bg_api(cell, api_key)
                result = fit_canvas(result, output_size)
                results.append(result)
            except Exception as e:
                errors.append(f"#{i+1}: {e}")
                results.append(fit_canvas(cell, output_size))
            progress.progress((i + 1) / total, text=f"{i+1}/{total} 完成")

        if errors:
            status.error("部分失敗：\n" + "\n".join(errors))
        else:
            status.success(f"✅ 全部完成！共 {total} 張")

        st.markdown("### 預覽")
        preview_cols = st.columns(cols)
        for i, img in enumerate(results):
            with preview_cols[i % cols]:
                checker = make_checker(output_size)
                checker.paste(img, mask=img.split()[3])
                st.image(checker, caption=f"#{i+1:02d}", width="stretch")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, img in enumerate(results):
                zf.writestr(f"sticker_{i+1:02d}.png", to_png_bytes(img))

        st.download_button(
            label="📦 下載全部貼圖（ZIP）",
            data=zip_buf.getvalue(),
            file_name="line_stickers.zip",
            mime="application/zip",
            type="primary",
        )
