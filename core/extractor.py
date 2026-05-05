import numpy as np
from PIL import Image
import colorsys
from sklearn.cluster import KMeans


def get_spatial_palette(img_pil):
    """
    空间感知取色：将照片分为上中下三段，每段提取2个颜色
    """
    w, h = img_pil.size
    # 定义三个区域：顶部(0-33%)，中部(33-66%)，底部(66-100%)[cite: 7]
    zones = [
        (0, 0, w, h // 3),  # Top
        (0, h // 3, w, 2 * h // 3),  # Middle
        (0, 2 * h // 3, w, h)  # Bottom
    ]

    spatial_hex = []
    for zone in zones:
        # 裁剪区域并缩小以提高 KMeans 效率[cite: 7]
        region = img_pil.crop(zone)
        region.thumbnail((100, 100))
        pixels = np.array(region).reshape(-1, 3)

        # 提取 2 个聚类中心[cite: 7]
        km = KMeans(n_clusters=2, n_init='auto', random_state=42).fit(pixels)
        centers = km.cluster_centers_

        # 排序：让更鲜艳或更重的颜色靠左（第一列）[cite: 7]
        c1, c2 = centers[0], centers[1]
        _, s1, v1 = colorsys.rgb_to_hsv(c1[0] / 255, c1[1] / 255, c1[2] / 255)
        _, s2, v2 = colorsys.rgb_to_hsv(c2[0] / 255, c2[1] / 255, c2[2] / 255)

        if (s2 * v2) > (s1 * v1):
            c1, c2 = c2, c1

        spatial_hex.append("#%02x%02x%02x" % tuple(c1.astype(int)))  # 左侧位置
        spatial_hex.append("#%02x%02x%02x" % tuple(c2.astype(int)))  # 右侧位置

    return spatial_hex  # 返回长度为 6 的列表，顺序为 [左上, 右上, 左中, 右中, 左下, 右下][cite: 7]

def get_palette_by_mode(img_pil, mode="默认渲染"):
    """
    海报取色调度中心：严格执行用户提供的算法逻辑
    """
    img_small = img_pil.copy()
    img_small.thumbnail((150, 150))
    pixels = np.array(img_small).reshape(-1, 3)

    if mode == "反差色":
        # 严格执行红色拦截与偏移算法，修复 NumPy 2.0 兼容性
        km = KMeans(n_clusters=15, n_init='auto', random_state=42).fit(pixels)
        centers = km.cluster_centers_
        counts = np.bincount(km.labels_)  # 修复 NumPy 2.0 移除 get_array_wrap 的问题

        processed = []
        for i, color in enumerate(centers):
            h, s, v = colorsys.rgb_to_hsv(color[0] / 255., color[1] / 255., color[2] / 255.)
            if (h < 0.08 or h > 0.9) and s > 0.3:
                h, s, v = 0.55, min(s, 0.5), max(v, 0.4)
                color = np.array(colorsys.hsv_to_rgb(h, s, v)) * 255
                vibrance = s * v * 2.0
            else:
                vibrance = s * v
            weight = (counts[i] / len(pixels)) * 0.5 + vibrance * 0.5
            processed.append((weight, color))

        processed.sort(key=lambda x: x[0], reverse=True)

        final_hex = []
        final_rgb = []
        for _, c in processed:
            if len(final_hex) < 6:
                # 修复 UFuncNoLoopError：使用数字数组进行距离对比[cite: 7]
                if not final_rgb or all(np.linalg.norm(c - f_rgb) > 40 for f_rgb in final_rgb):
                    final_rgb.append(c)
                    final_hex.append("#%02x%02x%02x" % tuple(c.astype(int)))
        return final_hex

    elif mode == "突出原色":
        # --- 严格执行你提供的“突出原色”算法 ---[cite: 7]
        km = KMeans(n_clusters=10, n_init='auto').fit(pixels)
        centers = km.cluster_centers_

        # 目标：寻找最醒目色（S*V最大）
        scores = [colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)[1] *
                  colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)[2] for c in centers]
        best_idx = np.argmax(scores)
        best_color = centers[best_idx]

        # 剔除过于接近的颜色，确保 6 个颜色分布均匀
        others = [c for i, c in enumerate(centers) if i != best_idx]
        others.sort(key=lambda c: np.linalg.norm(c - best_color), reverse=True)

        raw = [best_color] + others[:5]
        return ["#%02x%02x%02x" % tuple(c.astype(int)) for c in raw]

    else:
        # --- 严格执行你提供的“Hybrid Pro”默认算法 ---[cite: 7]
        vibrant_pixels, base_pixels, hsv_all = [], [], []
        for p in pixels:
            h, s, v = colorsys.rgb_to_hsv(p[0] / 255., p[1] / 255., p[2] / 255.)
            hsv_all.append((h, s, v))
            if s > 0.2 and v > 0.2:
                vibrant_pixels.append(p)
            else:
                base_pixels.append(p)

        # 全局氛围感知
        warm_ratio = sum(1 for h, s, v in hsv_all if (h < 0.12 or h > 0.88) and s > 0.15) / len(hsv_all)
        is_warm_scene = warm_ratio > 0.3

        # 混合聚类 (4鲜艳 + 2基础)
        km_v = KMeans(n_clusters=4, n_init='auto', random_state=42).fit(vibrant_pixels if vibrant_pixels else pixels)
        km_b = KMeans(n_clusters=2, n_init='auto', random_state=42).fit(base_pixels if base_pixels else pixels)
        raw_colors = np.vstack([km_v.cluster_centers_, km_b.cluster_centers_])

        # 艺术化提炼逻辑
        refined_palette = []
        for c in raw_colors:
            h, s, v = colorsys.rgb_to_hsv(c[0] / 255., c[1] / 255., c[2] / 255.)
            if v > 0.78:
                s, v = s * 0.4, min(v * 1.1, 0.98)
            elif v < 0.35:
                v, s = v * 0.75, min(s * 1.1, 0.4)
            else:
                s = min(s * 1.2, 0.9) if is_warm_scene else s * 0.9
                v = max(v, 0.4)
            # 存入 RGB 数组以供后续排序
            refined_palette.append(np.array(colorsys.hsv_to_rgb(h, s, v)) * 255)

        # 排序：按明度 V 降序排列
        refined_palette.sort(key=lambda c: colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)[2], reverse=True)

        return ["#%02x%02x%02x" % tuple(c.astype(int)) for c in refined_palette]
