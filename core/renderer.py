import os
import colorsys
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageColor
from PySide6.QtGui import QImage, QPixmap


def pil_to_pixmap(pil_img):
    data = pil_img.convert("RGBA").tobytes("raw", "RGBA")
    qimg = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


def sort_palette(hex_colors):
    """同步 Java PosterUtils.sortPalette 逻辑"""
    if not hex_colors: return []
    rgb_colors = [ImageColor.getrgb(h) for h in hex_colors]
    hsl_list = []
    for i, rgb in enumerate(rgb_colors):
        # Python colorsys 使用的是 HLS (Hue, Lightness, Saturation)
        h, l, s = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
        hsl_list.append((h, l, s, hex_colors[i]))
    # 按色相排序，同色相按亮度降序
    hsl_list.sort(key=lambda x: (x[0], -x[1]))
    return [item[3] for item in hsl_list]


def get_adaptive_bg(first_hex):
    """同步 Java PosterUtils.getAdaptiveBg 逻辑"""
    if not first_hex: return (232, 230, 225)
    r, g, b = ImageColor.getrgb(first_hex)
    return tuple(int(c * 0.15 + 255 * 0.85) for c in (r, g, b))


def get_safe_info(info, keys, default):
    """多级键值读取，确保兼容 EXIF 原始字段"""
    for key in keys:
        val = info.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return default


def render_poster_engine(img_path, hex_palette, info):
    W, H = 3840, 2160
    # 1. 颜色预处理
    sorted_palette = sort_palette(hex_palette)
    bg_color = get_adaptive_bg(sorted_palette[0] if sorted_palette else "#E8E6E1")

    canvas = Image.new('RGB', (W, H), bg_color)
    draw = ImageDraw.Draw(canvas)

    def load_font(weight, size):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        font_path = os.path.join(base_dir, "assets", "fonts", f"HarmonyOS_Sans_SC_{weight}.ttf")
        try:
            return ImageFont.truetype(font_path, size)
        except:
            return ImageFont.load_default()

    img = Image.open(img_path).convert('RGB')
    is_landscape = img.width >= img.height

    # 准备文本信息
    device_text = get_safe_info(info, ['device'], "ILCE-7CM2").upper()
    lens_text = get_safe_info(info, ['lens'], "LENS INFO").upper()
    f = get_safe_info(info, ['f', 'exif_f'], "f/2.8")
    s = get_safe_info(info, ['s', 'exif_s'], "1/100s")
    iso = get_safe_info(info, ['iso', 'exif_iso'], "ISO 100")
    param_text = f"{s}  {f}  {iso}".upper()

    if is_landscape:
        # ================= 横版布局 (新增 5% 安全边距逻辑) =================
        # 1. 初始目标高度 (61.8% 黄金比例高度)
        target_h = int(H * 0.618)
        target_w = int(img.width * (target_h / img.height))

        # 2. 安全边距计算 (左右各留 5%)
        safe_margin = int(W * 0.05)
        # 预估文字区占据的大致空间 (此处需预留约 15%-20% 的 W 给右侧文字区，否则照片会顶死右侧)
        # 我们设定照片的最大宽度不能超过 75% 的 W，且必须满足 5% 的边距
        max_photo_w = int(W * 0.75)

        # 如果照片太长，超过了最大允许宽度，则按比例缩小高度
        if target_w > max_photo_w:
            target_w = max_photo_w
            target_h = int(img.height * (target_w / img.width))

        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # 文字规格与间距计算
        device_font = load_font("Black", 95)
        max_device_w = int(W * 0.2)  # 文字区宽度约束
        device_w = draw.textlength(device_text, font=device_font)
        if device_w > max_device_w:
            device_font = load_font("Black", int(95 * (max_device_w / device_w)))

        # 获取文字高度作为基准
        bbox = draw.textbbox((0, 0), device_text, font=device_font)
        device_h = bbox[3] - bbox[1]

        v_gap = 20
        lens_font_size = 58
        param_font_size = 50

        img_y = (H - target_h) // 2
        photo_btm = img_y + target_h

        param_y = photo_btm - (param_font_size // 4)
        lens_y = param_y - (param_font_size // 2 + v_gap + lens_font_size // 2)
        device_y = lens_y - (lens_font_size // 2 + v_gap + device_h // 2)

        # 计算装饰线和色块区
        line_y = (device_y - device_h) - device_h
        ball_area_bottom = line_y - device_h

        # 核心：计算动态半径 R
        total_ball_h = ball_area_bottom - img_y
        R = total_ball_h / 7.818
        row_spacing = R * 0.6
        col_spacing = R * 0.8

        d_val = math.sqrt((2 * R) ** 2 - (R + row_spacing / 2) ** 2)
        offset_x = d_val + (R * 0.5)

        # 整体居中布局计算
        info_area_w = max(draw.textlength(device_text, font=device_font), (R * 4 + col_spacing))
        total_content_w = target_w + offset_x + info_area_w

        # 再次检查：如果整体内容宽度超过了 90% W (即左右各 5% 边框)
        if total_content_w > (W - 2 * safe_margin):
            scale_factor = (W - 2 * safe_margin) / total_content_w
            # 整体缩小：照片和文字区的所有关键数值都需要乘这个缩放因子
            # 这里为了性能简单化处理：重新调整照片大小，其他位置随之靠拢
            target_w = int(target_w * scale_factor)
            target_h = int(target_h * scale_factor)
            img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            # 重新计算坐标
            img_y = (H - target_h) // 2
            photo_btm = img_y + target_h
            # ... (其他动态计算的值会基于新的 target_w/target_h 自动缩放)
            total_content_w = int(total_content_w * scale_factor)
            offset_x *= scale_factor
            info_area_w *= scale_factor

        start_x = int((W - total_content_w) / 2)  # 居中对齐
        info_x_start = int(start_x + target_w + offset_x)

        # A. 绘制照片
        canvas.paste(img_resized, (start_x, img_y))

        # B. 绘制色块
        origin_y = img_y + (R * 0.618) + R
        for i, color in enumerate(sorted_palette[:6]):
            row, col = i % 3, i // 3
            cx = info_x_start + R + (col * (R * 2 + col_spacing))
            cy = origin_y + row * (R * 2 + row_spacing)
            draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill=color)

        # C. 绘制装饰线
        draw.line([(info_x_start, line_y), (info_x_start + info_area_w, line_y)], fill=(200, 200, 200), width=3)

        # D. 绘制文字
        draw.text((info_x_start, device_y), device_text, fill=(30, 30, 30), font=device_font, anchor="ls")
        draw.text((info_x_start, lens_y), lens_text, fill=(80, 80, 80), font=load_font("Bold", lens_font_size),
                  anchor="ls")
        draw.text((info_x_start, param_y), param_text, fill=(140, 140, 140), font=load_font("Regular", param_font_size),
                  anchor="ls")

    else:
        # ================= 竖版布局 (同步 Java 黄金比例与切线偏移) =================
        target_h = int(H * 0.62)
        target_w = int(img.width * (target_h / img.height))
        img_resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # 测量视觉高度
        lens_font = load_font("Bold", 85)
        param_font = load_font("Regular", 65)
        l_bbox = draw.textbbox((0, 0), lens_text, font=lens_font)
        p_bbox = draw.textbbox((0, 0), param_text, font=param_font)
        lens_vh = l_bbox[3] - l_bbox[1]
        param_vh = p_bbox[3] - p_bbox[1]

        # 核心：切线偏移量
        offset = param_vh

        # 设备文字测量与缩放
        device_font = load_font("Black", 160)
        device_max_w = (target_w * 0.95) - offset
        d_w = draw.textlength(device_text, font=device_font)
        if d_w > device_max_w:
            device_font = load_font("Black", int(160 * (device_max_w / d_w)))
        d_bbox = draw.textbbox((0, 0), device_text, font=device_font)
        device_vh = d_bbox[3] - d_bbox[1]

        # 布局计算
        gap_to_photo = lens_vh
        right_line_gap = 60
        right_total_h = lens_vh + right_line_gap + param_vh
        text_section_h = max(device_vh, right_total_h)

        total_content_h = target_h + gap_to_photo + text_section_h
        margin_top = (H - total_content_h) / 1.618  # 黄金分割顶部边距

        img_y = int(margin_top)
        px_gap = 150
        start_x = (W - (target_w + px_gap + target_w)) // 2  # 简化调配
        text_center_y = img_y + target_h + gap_to_photo + (text_section_h / 2)

        # A. 绘制图像
        canvas.paste(img_resized, (start_x, img_y))

        # B. 绘制色块 (2x3 矩形分布)
        item_gap = 20
        block_w = (target_w - item_gap) // 2
        block_h = (target_h - 2 * item_gap) // 3
        px_start = start_x + target_w + px_gap

        for i, color in enumerate(hex_palette[:6]):
            row, col = i // 2, i % 2
            bx = px_start + col * (block_w + item_gap)
            by = img_y + row * (block_h + item_gap)
            draw.rectangle([bx, by, bx + block_w, by + block_h], fill=color)

            # HEX 文本
            r, g, b = ImageColor.getrgb(color)
            t_color = (255, 255, 255) if (0.299 * r + 0.587 * g + 0.114 * b) < 150 else (60, 60, 60)
            draw.text((bx + block_w / 2, by + block_h / 2), color.upper(), fill=t_color, font=load_font("Medium", 40),
                      anchor="mm")

        # C. 绘制底部文字 (应用 offset 偏移)
        draw.text((start_x + offset, text_center_y + (device_vh / 2)), device_text, fill=(30, 30, 30), font=device_font,
                  anchor="ls")

        lens_y = text_center_y - (right_total_h / 2) + lens_vh
        param_y = text_center_y + (right_total_h / 2)
        draw.text((px_start + offset, lens_y), lens_text, fill=(80, 80, 80), font=lens_font, anchor="ls")
        draw.text((px_start + offset, param_y), param_text, fill=(120, 120, 120), font=param_font, anchor="ls")

        # D. 装饰竖线
        line_x = start_x + target_w + (px_gap / 2)
        line_half_h = (text_section_h / 2) + 20
        draw.line([(line_x, text_center_y - line_half_h), (line_x, text_center_y + line_half_h)], fill=(200, 200, 200),
                  width=3)

    return canvas
