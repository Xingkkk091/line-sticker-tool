import io
import zipfile
import numpy as np
import streamlit as st
from PIL import Image, ImageFilter
from rembg import remove, new_session

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
    st.subheader("去背模型")
    model_choice = st.radio(
        "選擇模型",
        ["birefnet-general（最佳品質）", "isnet-general-use（次佳）", "u2net（快速）"],
        index=0,
    )
    model_name = model_choice.split("（")[0]

    edge_smooth = st.checkbox("邊緣平滑", value=True)
    st.caption("首次使用會自動下載模型（birefnet 約 200MB）")


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


def smooth_edges(image: Image.Image, radius: int = 1) -> Image.Image:
    """讓 alpha 邊緣更銳利乾淨"""
    r, g, b, a = image.split()
    # 稍微侵蝕 alpha，去掉髒邊
    a_arr = np.array(a, dtype=np.float32)
    # 二值化：半透明的邊界推向完全透明或完全不透明
    a_arr = np.where(a_arr > 200, 255, np.where(a_arr < 50, 0, a_arr))
    a_clean = Image.fromarray(a_arr.astype(np.uint8))
    if radius > 0:
        a_clean = a_clean.filter(ImageFilter.GaussianBlur(radius=radius))
        # 再次二值化避免模糊造成半透明鬼影
        a_arr2 = np.array(a_clean, dtype=np.float32)
        a_arr2 = np.where(a_arr2 > 128, 255, 0)
        a_clean = Image.fromarray(a_arr2.astype(np.uint8))
    return Image.merge("RGBA", (r, g, b, a_clean))


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


@st.cache_resource(show_spinner="載入去背模型中...")
def load_session(name: str):
    return new_session(name)


# ── 主介面 ────────────────────────────────────────────────
uploaded = st.file_uploader(
    "拖曳或選擇排版圖",
    type=["png", "jpg", "jpeg", "webp"],
    label_visibility="collapsed",
)

if uploaded:
    image = Image.open(uploaded).convert("RGBA")
    st.image(image, caption=f"原始圖片 {image.width}×{image.height}", use_container_width=True)

    # 決定格狀
    if grid_mode == "自動偵測":
        cols, rows = detect_grid(image)
        st.info(f"自動偵測：**{cols}×{rows}（{cols * rows} 張）**")
    else:
        cols, rows = map(int, grid_mode.split("（")[0].split("×"))

    total = cols * rows

    if st.button(f"🚀 開始處理（{total} 張貼圖）", type="primary", use_container_width=True):
        cells = slice_grid(image, cols, rows)

        progress = st.progress(0, text="準備中...")
        status = st.empty()

        session = load_session(model_name)
        results: list[Image.Image] = []

        for i, cell in enumerate(cells):
            status.text(f"處理第 {i+1}/{total} 張...")
            raw = to_png_bytes(cell)
            out_bytes = remove(raw, session=session)
            result = Image.open(io.BytesIO(out_bytes)).convert("RGBA")
            if edge_smooth:
                result = smooth_edges(result)
            result = fit_canvas(result, output_size)
            results.append(result)
            progress.progress((i + 1) / total, text=f"{i+1}/{total} 完成")

        status.success(f"✅ 全部完成！共 {total} 張")

        # 預覽（棋盤格背景，更專業）
        st.markdown("### 預覽")
        preview_cols = st.columns(cols)
        for i, img in enumerate(results):
            with preview_cols[i % cols]:
                # 棋盤格背景方便辨識透明度
                checker = Image.new("RGB", (output_size, output_size))
                tile = 20
                arr = np.zeros((output_size, output_size, 3), dtype=np.uint8)
                for ty in range(0, output_size, tile):
                    for tx in range(0, output_size, tile):
                        color = 200 if (tx // tile + ty // tile) % 2 == 0 else 160
                        arr[ty:ty+tile, tx:tx+tile] = color
                checker = Image.fromarray(arr)
                checker.paste(img, mask=img.split()[3])
                st.image(checker, caption=f"#{i+1:02d}", use_container_width=True)

        # 打包 ZIP 下載
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, img in enumerate(results):
                zf.writestr(f"sticker_{i+1:02d}.png", to_png_bytes(img))

        st.download_button(
            label="📦 下載全部貼圖（ZIP）",
            data=zip_buf.getvalue(),
            file_name="line_stickers.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary",
        )
