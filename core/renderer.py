import os
import colorsys
from PIL import Image, ImageDraw, ImageFont, ImageColor
from PySide6.QtGui import QImage, QPixmap

def pil_to_pixmap(pil_img):
    data = pil_img.convert("RGBA").tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)

def sort_palette(hex_colors):
    """严格按照你提供的 HSL 排序逻辑"""
    if not hex_colors: return []
    rgb_colors = [ImageColor.getrgb(h) for h in hex_colors]
    hsl_list = []
    for i, rgb in enumerate(rgb_colors):
        h, l, s = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
        hsl_list.append((h, l, s, hex_colors[i]))
    hsl_list.sort(key=lambda x: (x[0], -x[1]))
    return [item[3] for item in hsl_list]

def get_adaptive_bg(sorted_palette):
    """严格按照你提供的背景加亮逻辑"""
    if not sorted_palette: return (232, 230, 225)
    brightest_hex = sorted_palette[0]
    r, g, b = ImageColor.getrgb(brightest_hex)
    return tuple(int(c * 0.15 + 255 * 0.85) for c in (r, g, b))

def render_poster_engine(img_path, hex_palette, info):
    """
    海报生成核心：严格执行你提供的 3x2 几何对称布局坐标[cite: 3]
    hex_palette 将由 extractor 根据不同模式提供不同的 6 个颜色
    """
    W, H = 3840, 2160
    sorted_palette = sort_palette(hex_palette)
    bg_color = get_adaptive_bg(sorted_palette)

    canvas = Image.new('RGB', (W, H), bg_color)
    draw = ImageDraw.Draw(canvas)

    def load_font(weight, size):
        # 自动定位 assets 目录[cite: 3]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        font_path = os.path.join(base_dir, "assets", "fonts", f"HarmonyOS_Sans_SC_{weight}.ttf")
        return ImageFont.truetype(font_path, size) if os.path.exists(font_path) else ImageFont.load_default()

    img = Image.open(img_path).convert('RGB')
    is_landscape = img.width > img.height

    if is_landscape:
        # ================= 横版布局 (切线偏移逻辑) =================
        target_h = int(H * 0.60)
        target_w = int(img.width * (target_h / img.height))
        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        gap_to_img = 180
        radius = 100
        col_spacing = 60
        row_spacing = 50

        palette_width = (radius * 2 * 2) + col_spacing

        info_area_w = palette_width
        content_w = target_w + gap_to_img + info_area_w
        start_x = (W - content_w) // 2
        img_y = (H - target_h) // 2

        canvas.paste(img_resized, (start_x, img_y))

        # --- 核心修改：切线基础上的下移逻辑 ---
        # 1. 相切状态下的圆心应该是 img_y + radius
        # 2. 在相切基础上向下移动一部分（例如移动半径的 1/3 或 1/4）
        offset_from_tangent = radius // 3  # 你可以根据视觉效果微调这个值，比如 //4 或固定数值

        info_x_start = start_x + target_w + gap_to_img
        origin_x = info_x_start + radius
        # 最终圆心 = 顶边 + 半径 (相切位置) + 额外下移距离
        origin_y = img_y + radius + offset_from_tangent

        last_circle_y = 0
        if sorted_palette:
            for i, h_code in enumerate(sorted_palette[:6]):
                # 严格保持 2x3 排布
                row, col = i % 3, i // 3
                cx = origin_x + col * (radius * 2 + col_spacing)
                cy = origin_y + row * (radius * 2 + row_spacing)
                draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=h_code)
                last_circle_y = cy + radius

        # --- 底部文字信息对齐 ---
        device_name = (info.get('device') or "ILCE-7CM2").upper()
        param_y = img_y + target_h
        lens_y = param_y - 80
        device_y = lens_y - 95

        draw.text((info_x_start, param_y), info.get('param', ''), fill=(140, 140, 140), font=load_font("Regular", 50),
                  anchor="ls")
        draw.text((info_x_start, lens_y), (info.get('lens') or "LENS INFO").upper(), fill=(80, 80, 80),
                  font=load_font("Bold", 58), anchor="ls")
        draw.text((info_x_start, device_y), device_name, fill=(30, 30, 30), font=load_font("Black", 95), anchor="ls")

        # 分割线位置自动适配
        text_top_y = device_y - 95
        line_y = (last_circle_y + text_top_y) // 2
        draw.line([(info_x_start, line_y), (info_x_start + palette_width, line_y)], fill=(200, 200, 200), width=3)



    else:

        # ================= 竖版布局 (空间分布感知版) =================

        target_h = int(H * 0.62)

        target_w = int(img.width * (target_h / img.height))

        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        gap = 150

        palette_area_w = target_w

        total_content_w = target_w + gap + palette_area_w

        start_x = (W - total_content_w) // 2

        img_y = (H - target_h) // 2 - 120

        canvas.paste(img_resized, (start_x, img_y))

        # 此时的 hex_palette 必须是 get_spatial_palette 提取的

        if hex_palette:

            item_gap = 20

            block_w = (palette_area_w - item_gap) / 2

            block_h = (target_h - 2 * item_gap) / 3

            palette_x_start = start_x + target_w + gap

            for i, h_code in enumerate(hex_palette[:6]):
                # 逻辑对应：i=0(左上), i=1(右上), i=2(左中), i=3(右中)...

                row, col = i // 2, i % 2

                bx = palette_x_start + col * (block_w + item_gap)

                by = img_y + row * (block_h + item_gap)

                draw.rectangle([bx, by, bx + block_w, by + block_h], fill=h_code)

                # 绘制 HEX 文本[cite: 8]

                r, g, b = ImageColor.getrgb(h_code)

                t_fill = (255, 255, 255) if (r * 0.299 + g * 0.587 + b * 0.114) < 150 else (60, 60, 60)

                draw.text((bx + block_w // 2, by + block_h // 2), h_code.upper(),

                          fill=t_fill, font=load_font("Medium", 40), anchor="mm")

        # 2. 底部文字信息逻辑 (保持原有的高级感对齐)

        baseline_y = img_y + target_h + 120

        device_name = (info.get('device') or "ILCE-7CM2").upper()

        # 机型名称 (左对齐照片)

        draw.text((start_x, baseline_y + 140), device_name, fill=(30, 30, 30),

                  font=load_font("Black", 160), anchor="ls")

        # 镜头与参数 (左对齐色块区域)

        info_text_x = start_x + target_w + gap

        draw.text((info_text_x, baseline_y + 60), (info.get('lens') or "LENS").upper(),

                  fill=(80, 80, 80), font=load_font("Bold", 85), anchor="ls")

        draw.text((info_text_x, baseline_y + 140), info.get('param', ''),

                  fill=(120, 120, 120), font=load_font("Regular", 65), anchor="ls")

        # 底部横线

        draw.line([(start_x, baseline_y + 195), (start_x + total_content_w, baseline_y + 195)],

                  fill=(200, 200, 200), width=3)
    return canvas
