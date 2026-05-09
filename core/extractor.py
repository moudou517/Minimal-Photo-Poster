import numpy as np
from PIL import Image
import colorsys
from sklearn.cluster import KMeans


def color_distance(c1, c2):
    """计算欧氏距离 (对应 Java 的 colorDistance)"""
    return np.linalg.norm(c1 - c2)


def get_vibrance(rgb):
    """计算鲜艳度 (S * V)"""
    _, s, v = colorsys.rgb_to_hsv(rgb[0] / 255., rgb[1] / 255., rgb[2] / 255.)
    return s * v


def get_min_dist_to_palette(color, palette):
    """计算颜色到色板的最小距离 (对应 Java 的 getMinDistToPalette)"""
    if not palette:
        return 0
    return min(color_distance(color, p) for p in palette)


def refine_color(rgb, is_warm_scene):
    """高级感调色逻辑 (对应 Java 的 refineColor)"""
    h, s, v = colorsys.rgb_to_hsv(rgb[0] / 255., rgb[1] / 255., rgb[2] / 255.)

    if v > 0.78:  # 高明度
        s *= 0.4
        v = min(v * 1.1, 0.98)
    elif v < 0.35:  # 低明度
        v *= 0.75
        s = min(s * 1.1, 0.4)
    else:  # 中性色
        s = min(s * 1.2, 0.9) if is_warm_scene else s * 0.9
        v = max(v, 0.4)

    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return np.array([r * 255, g * 255, b * 255])


def check_is_warm_scene(pixels):
    """检测是否为暖色调场景 (对应 Java 的 checkIsWarmScene)"""
    warm_count = 0
    for p in pixels:
        h, s, v = colorsys.rgb_to_hsv(p[0] / 255., p[1] / 255., p[2] / 255.)
        if (h < 0.12 or h > 0.88) and s > 0.15:
            warm_count += 1
    return (warm_count / len(pixels)) > 0.3


def get_palette_by_mode(img_pil, mode="默认渲染"):
    """
    海报取色调度中心：已更新 Java 版精细化反差色逻辑
    """
    img_small = img_pil.copy()
    img_small.thumbnail((150, 150))
    pixels = np.array(img_small).reshape(-1, 3)

    if mode == "取反差色" or mode == "反差色":
        # 1. 获取基础色板 (基于突出原色模式)
        base_palette_hex = get_palette_by_mode(img_pil, mode="突出原色")
        base_palette_rgb = []
        for h in base_palette_hex:
            h = h.lstrip('#')
            base_palette_rgb.append(np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]))

        primary_color = base_palette_rgb[0]
        others = base_palette_rgb[1:]

        # 2. 寻找最接近的三个索引 (对应 Java findThreeClosestIndices)
        # 这里简化处理：取 others 中的前两个待替换位置
        replace_indices = [0, 1]
        has_replaced = False

        # 3. 挖掘“极度差异色”
        filtered_pixels = []
        for p in pixels:
            is_covered = False
            for c in base_palette_rgb:
                if color_distance(p, c) < 65:
                    is_covered = True
                    break

            _, s, v = colorsys.rgb_to_hsv(p[0] / 255., p[1] / 255., p[2] / 255.)
            if not is_covered and v > 0.15 and s > 0.15:
                filtered_pixels.append(p)

        if len(filtered_pixels) > 50:
            # 提取 6 个候选簇
            km = KMeans(n_clusters=min(6, len(filtered_pixels)), n_init='auto', random_state=42).fit(filtered_pixels)
            patches = km.cluster_centers_

            # 按唯一性得分排序：得分 = 鲜艳度 * 到原色板的最小距离
            scored_patches = []
            for patch in patches:
                score = get_vibrance(patch) * get_min_dist_to_palette(patch, base_palette_rgb)
                scored_patches.append((score, patch))

            scored_patches.sort(key=lambda x: x[0], reverse=True)

            replace_count = 0
            for _, patch_color in scored_patches:
                if replace_count >= 2:
                    break

                # 只要反差够大就替换
                if get_min_dist_to_palette(patch_color, base_palette_rgb) > 100:
                    others[replace_count] = patch_color
                    replace_count += 1
                    has_replaced = True

        final_result_rgb = [primary_color] + others

        # 4. 如果发生替换，进行色彩高级感优化
        if has_replaced:
            is_warm = check_is_warm_scene(pixels)
            refined_rgb = [refine_color(c, is_warm) for c in final_result_rgb]
            return ["#%02x%02x%02x" % tuple(c.astype(int)) for c in refined_rgb]

        return ["#%02x%02x%02x" % tuple(c.astype(int)) for c in final_result_rgb]

    elif mode == "突出原色":
        km = KMeans(n_clusters=10, n_init='auto', random_state=42).fit(pixels)
        centers = km.cluster_centers_

        # 寻找最醒目色 (Vibrance)
        best_idx = np.argmax([get_vibrance(c) for c in centers])
        best_color = centers[best_idx]

        others = [c for i, c in enumerate(centers) if i != best_idx]
        # 按与主色距离降序排列
        others.sort(key=lambda c: color_distance(c, best_color), reverse=True)

        raw = [best_color] + others[:5]
        return ["#%02x%02x%02x" % tuple(c.astype(int)) for c in raw]

    else:
        # Default Mode: 混合聚类 (4鲜艳 + 2基础)
        vibrant_pixels = []
        base_pixels = []
        for p in pixels:
            _, s, v = colorsys.rgb_to_hsv(p[0] / 255., p[1] / 255., p[2] / 255.)
            if s > 0.2 and v > 0.2:
                vibrant_pixels.append(p)
            else:
                base_pixels.append(p)

        is_warm = check_is_warm_scene(pixels)

        km_v = KMeans(n_clusters=4, n_init='auto', random_state=42).fit(vibrant_pixels if vibrant_pixels else pixels)
        km_b = KMeans(n_clusters=2, n_init='auto', random_state=42).fit(base_pixels if base_pixels else pixels)

        raw_colors = list(km_v.cluster_centers_) + list(km_b.cluster_centers_)

        # 艺术化提炼并按明度排序
        refined = [refine_color(c, is_warm) for c in raw_colors]
        refined.sort(key=lambda c: colorsys.rgb_to_hsv(c[0] / 255., c[1] / 255., c[2] / 255.)[2], reverse=True)

        return ["#%02x%02x%02x" % tuple(c.astype(int)) for c in refined]
