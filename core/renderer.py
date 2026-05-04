import os
import colorsys
from PIL import Image, ImageDraw, ImageFont, ImageColor
from PySide6.QtGui import QImage, QPixmap


def pil_to_pixmap(pil_img):
    data = pil_img.convert("RGBA").tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


def sort_palette(hex_colors):
    if not hex_colors: return []
    rgb_colors = [ImageColor.getrgb(h) for h in hex_colors]
    hsl_list = []
    for i, rgb in enumerate(rgb_colors):
        h, l, s = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
        hsl_list.append((h, l, s, hex_colors[i]))
    hsl_list.sort(key=lambda x: (x[0], -x[1]))
    return [item[3] for item in hsl_list]


def get_adaptive_bg(sorted_palette):
    if not sorted_palette: return (232, 230, 225)
    brightest_hex = sorted_palette[0]
    r, g, b = ImageColor.getrgb(brightest_hex)
    return tuple(int(c * 0.15 + 255 * 0.85) for c in (r, g, b))


def render_poster_engine(img_path, hex_palette, info):
    """海报生成核心：横版 3x2 几何对称布局"""
    W, H = 3840, 2160
    sorted_palette = sort_palette(hex_palette)
    bg_color = get_adaptive_bg(sorted_palette)

    canvas = Image.new('RGB', (W, H), bg_color)
    draw = ImageDraw.Draw(canvas)

    def load_font(weight, size):
        base_dir = os.path.dirname(os.path.dirname(__file__))
        font_path = os.path.join(base_dir, "assets", "fonts", f"HarmonyOS_Sans_SC_{weight}.ttf")
        return ImageFont.truetype(font_path, size) if os.path.exists(font_path) else ImageFont.load_default()

    img = Image.open(img_path).convert('RGB')
    is_landscape = img.width > img.height

    if is_landscape:
        # ================= 横版布局 (3x2 几何对称) =================
        target_h = int(H * 0.60)
        target_w = int(img.width * (target_h / img.height))
        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # 布局参数计算
        gap_to_img = 180  # 图片与右侧板块的间距
        radius = 100  # 圆半径
        col_spacing = 60  # 列间距
        row_spacing = 50  # 行间距

        # 计算色块矩阵的总宽度 (2列)
        palette_width = (radius * 2 * 2) + col_spacing

        info_area_w = palette_width  # 让文字区域与色块区域宽度一致
        content_w = target_w + gap_to_img + info_area_w
        start_x = (W - content_w) // 2
        img_y = (H - target_h) // 2

        canvas.paste(img_resized, (start_x, img_y))

        # 1. 绘制圆形色块 (靠顶对齐)
        info_x_start = start_x + target_w + gap_to_img
        origin_x = info_x_start + radius
        origin_y = img_y + radius

        last_circle_y = 0
        if sorted_palette:
            for i, h_code in enumerate(sorted_palette[:6]):
                row, col = i % 3, i // 3
                cx = origin_x + col * (radius * 2 + col_spacing)
                cy = origin_y + row * (radius * 2 + row_spacing)
                draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=h_code)
                last_circle_y = cy + radius  # 记录最下方圆形的底部坐标

        # 2. 绘制文字信息 (靠底对齐)
        device_name = (info.get('device') or "ILCE-7CM2").upper()  # 默认机型 ILCE-7CM2

        param_y = img_y + target_h
        lens_y = param_y - 80
        device_y = lens_y - 95

        draw.text((info_x_start, param_y), info.get('param', ''), fill=(140, 140, 140), font=load_font("Regular", 50),
                  anchor="ls")
        draw.text((info_x_start, lens_y), (info.get('lens') or "LENS INFO").upper(), fill=(80, 80, 80),
                  font=load_font("Bold", 58), anchor="ls")
        draw.text((info_x_start, device_y), device_name, fill=(30, 30, 30), font=load_font("Black", 95), anchor="ls")

        # 3. 绘制对称分割线
        # 计算色块底部到文字顶部的中心点
        text_top_y = device_y - 95  # 粗略估算机型文字的顶部位置
        line_y = (last_circle_y + text_top_y) // 2

        # 线条长度与色块矩阵宽度严格对称
        draw.line([(info_x_start, line_y), (info_x_start + palette_width, line_y)],
                  fill=(200, 200, 200), width=3)

    else:
        # ================= 竖版布局 (保持之前优化后的逻辑) =================
        target_h = int(H * 0.62)
        target_w = int(img.width * (target_h / img.height))
        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        gap = 150
        color_block_w = target_w
        total_content_w = target_w + gap + color_block_w
        start_x = (W - total_content_w) // 2
        img_y = (H - target_h) // 2 - 120

        canvas.paste(img_resized, (start_x, img_y))

        if sorted_palette:
            num_colors = len(sorted_palette)
            spacing = 20
            block_h = (target_h - (num_colors - 1) * spacing) / num_colors
            for i, h_code in enumerate(sorted_palette):
                curr_y = img_y + i * (block_h + spacing)
                rect = [start_x + target_w + gap, curr_y, start_x + target_w + gap + color_block_w, curr_y + block_h]
                draw.rectangle(rect, fill=h_code)
                r, g, b = ImageColor.getrgb(h_code)
                t_fill = (255, 255, 255) if (r * 0.299 + g * 0.587 + b * 0.114) < 145 else (60, 60, 60)
                draw.text((rect[0] + color_block_w // 2, rect[1] + block_h // 2), h_code.upper(), fill=t_fill,
                          font=load_font("Medium", 42), anchor="mm")

        baseline_y = img_y + target_h + 120
        device_name = (info.get('device') or "ILCE-7CM2").upper()  # 默认机型 ILCE-7CM2[cite: 4]
        draw.text((start_x, baseline_y + 140), device_name, fill=(30, 30, 30), font=load_font("Black", 160),
                  anchor="ls")
        draw.text((start_x + target_w + gap, baseline_y + 60), (info.get('lens') or "LENS").upper(), fill=(80, 80, 80),
                  font=load_font("Bold", 85), anchor="ls")
        draw.text((start_x + target_w + gap, baseline_y + 140), info.get('param', ''), fill=(120, 120, 120),
                  font=load_font("Regular", 65), anchor="ls")
        draw.line([(start_x, baseline_y + 195), (start_x + total_content_w, baseline_y + 195)], fill=(200, 200, 200),
                  width=3)

    # 公共个人水印
    draw.text((W - 100, H - 100), info.get('sign', '@moudou517'), fill=(160, 160, 160), font=load_font("Light", 45),
              anchor="rb")

    return canvas