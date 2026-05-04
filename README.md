# 📸 Minimal Photo Poster Generator

这是一个为摄影师设计的自动化海报生成工具，支持根据照片比例自动切换布局。

## ✨ 核心特性

*   **智能布局自适应**：自动识别横竖构图。
    *   **横版**：采用 3x2 大圆几何对称排布，视觉重心极其平衡。
    *   **竖版**：采用侧边长条色块对齐，极简主义风格。
*   **色调提取与排序**：基于 HSL 算法对主色调进行排序，确保色彩过渡自然。
*   **默认适配**：深度适配 **Sony ILCE-7CM2 (A7C2)** 元数据展示。
*   **高精度对齐**：所有文字基于 Baseline (ls) 对齐，边缘严丝合缝。

## 🖼️ 效果预览

| 横版布局 (Landscape) | 竖版布局 (Portrait) |
| :--- | :--- |
| ![Demo 1](docs/landscape_demo.jpg) | ![Demo 2](docs/portrait_demo.jpg) |

## 🚀 快速开始

1. 克隆项目：
`git clone https://github.com/moudou517/Minimal-Photo-Poster.git`

2. 安装依赖：
`pip install -r requirements.txt`

3. 运行：
`python main.py`

---
🎨 **Author**: [moudou517](https://github.com/moudou517)
