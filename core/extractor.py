import numpy as np
from PIL import Image
import colorsys
from sklearn.cluster import KMeans

def get_hybrid_pro_palette(img_pil):
    """
    严格执行 Hybrid Pro 算法逻辑
    """
    # 1. 预处理
    img_small = img_pil.copy()
    img_small.thumbnail((150, 150))
    pixels = np.array(img_small).reshape(-1, 3)

    vibrant_pixels, base_pixels, hsv_all = [], [], []
    for p in pixels:
        h, s, v = colorsys.rgb_to_hsv(p[0] / 255., p[1] / 255., p[2] / 255.)
        hsv_all.append((h, s, v))
        if s > 0.2 and v > 0.2:
            vibrant_pixels.append(p)
        else:
            base_pixels.append(p)

    # 2. 全局氛围感知
    warm_ratio = sum(1 for h, s, v in hsv_all if (h < 0.12 or h > 0.88) and s > 0.15) / len(hsv_all)
    is_warm_scene = warm_ratio > 0.3

    # 3. 混合聚类 (4鲜艳 + 2基础) - 严格不简化
    km_v = KMeans(n_clusters=4, n_init='auto', random_state=42).fit(vibrant_pixels if vibrant_pixels else pixels)
    km_b = KMeans(n_clusters=2, n_init='auto', random_state=42).fit(base_pixels if base_pixels else pixels)
    raw_colors = np.vstack([km_v.cluster_centers_, km_b.cluster_centers_])

    # 4. 艺术化提炼逻辑
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
        refined_palette.append(np.array(colorsys.hsv_to_rgb(h, s, v)) * 255)

    # 5. 排序
    refined_palette.sort(key=lambda c: colorsys.rgb_to_hsv(c[0]/255, c[1]/255, c[2]/255)[2], reverse=True)
    return refined_palette, warm_ratio