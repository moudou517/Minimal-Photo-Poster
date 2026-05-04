import os
from PIL import Image
from PIL.ExifTags import TAGS
from PySide6.QtWidgets import (QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
                               QWidget, QFileDialog, QLabel, QFrame,
                               QLineEdit, QListWidget, QMessageBox)
from PySide6.QtCore import Qt

from core.extractor import get_hybrid_pro_palette
from core.renderer import render_poster_engine, pil_to_pixmap


class PhotoColorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhotoPalettePro - 摄影海报生成器")
        self.setMinimumSize(1300, 850)
        self.current_path = None
        self.current_palette_hex = []
        self.current_pil_preview = None
        self.init_ui()

    def init_ui(self):
        # 现代感 UI 样式
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; }
            QFrame#ControlPanel { background: white; border-radius: 15px; border: 1px solid #ddd; }
            QLineEdit { border: 1px solid #ccc; border-radius: 4px; padding: 6px; background: #fafafa; }
            QPushButton { background: #34495e; color: white; border-radius: 6px; padding: 10px; font-weight: bold; }
            QPushButton:hover { background: #2c3e50; }
            QPushButton#DelBtn { background: #e74c3c; }
            QPushButton#DelBtn:hover { background: #c0392b; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # --- 左侧：文件管理 ---
        left_panel = QVBoxLayout()
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)  # 支持多选删除
        self.file_list.currentRowChanged.connect(self.handle_image_selection)

        left_panel.addWidget(QLabel("<b>照片队列</b>"))
        left_panel.addWidget(self.file_list)

        btn_box = QHBoxLayout()
        self.btn_add = QPushButton("导入照片")
        self.btn_add.clicked.connect(self.import_files)
        self.btn_del = QPushButton("删除选中")
        self.btn_del.setObjectName("DelBtn")
        self.btn_del.clicked.connect(self.delete_selected_files)
        btn_box.addWidget(self.btn_add)
        btn_box.addWidget(self.btn_del)
        left_panel.addLayout(btn_box)
        main_layout.addLayout(left_panel, 2)

        # --- 中间：海报预览 ---
        self.preview_label = QLabel("请导入照片以预览")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background: #d1d1d1; border-radius: 10px;")
        main_layout.addWidget(self.preview_label, 6)

        # --- 右侧：配置面板 ---
        self.ctrl_panel = QFrame()
        self.ctrl_panel.setObjectName("ControlPanel")
        self.ctrl_panel.setFixedWidth(320)
        c_layout = QVBoxLayout(self.ctrl_panel)

        c_layout.addWidget(QLabel("<h3>文本定制</h3>"))
        self.in_dev = QLineEdit();
        c_layout.addWidget(QLabel("机身型号:"));
        c_layout.addWidget(self.in_dev)
        self.in_lens = QLineEdit();
        c_layout.addWidget(QLabel("镜头型号:"));
        c_layout.addWidget(self.in_lens)

        p_box = QHBoxLayout()
        self.in_shutter = QLineEdit();
        self.in_aperture = QLineEdit();
        self.in_iso = QLineEdit()
        p_box.addLayout(self.make_v_input("快门", self.in_shutter))
        p_box.addLayout(self.make_v_input("光圈", self.in_aperture))
        p_box.addLayout(self.make_v_input("ISO", self.in_iso))
        c_layout.addLayout(p_box)

        self.in_sign = QLineEdit();
        self.in_sign.setText("moudou517")
        c_layout.addWidget(QLabel("水印签名:"));
        c_layout.addWidget(self.in_sign)

        c_layout.addSpacing(20)
        self.btn_refresh = QPushButton("🔄 实时预览")
        self.btn_refresh.clicked.connect(self.refresh_preview)
        c_layout.addWidget(self.btn_refresh)

        c_layout.addStretch()
        self.btn_export = QPushButton("💾 导出成品")
        self.btn_export.clicked.connect(self.export_image)
        c_layout.addWidget(self.btn_export)

        main_layout.addWidget(self.ctrl_panel, 3)

    def make_v_input(self, label, edit):
        v = QVBoxLayout()
        v.addWidget(QLabel(label))
        v.addWidget(edit)
        return v

    def import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择照片", "", "Images (*.jpg *.png)")
        if paths:
            for p in paths: self.file_list.addItem(p)
            self.file_list.setCurrentRow(self.file_list.count() - 1)

    def delete_selected_files(self):
        items = self.file_list.selectedItems()
        if not items: return
        for item in items:
            self.file_list.takeItem(self.file_list.row(item))
        # 列表清空逻辑
        if self.file_list.count() == 0:
            self.preview_label.clear()
            self.preview_label.setText("列表已清空")
            self.current_path = None

    def handle_image_selection(self, row):
        if row < 0: return
        self.current_path = self.file_list.item(row).text()

        # 提取 EXIF 与 默认值恢复[cite: 1]
        model, lens, s, a, i = self.get_exif(self.current_path)
        self.in_dev.setText(model if model else "ILCE-7CM2")  # 恢复默认名称
        self.in_lens.setText(lens if lens else "FE 20-70mm F4 G")
        self.in_shutter.setText(s);
        self.in_aperture.setText(a);
        self.in_iso.setText(i)

        # 预提调色盘
        try:
            with Image.open(self.current_path) as img:
                raw_pal, _ = get_hybrid_pro_palette(img.convert('RGB'))
                self.current_palette_hex = ["#%02x%02x%02x" % tuple(c.astype(int)) for c in raw_pal]
            self.refresh_preview()
        except:
            pass

    def get_exif(self, path):
        try:
            with Image.open(path) as img:
                exif = img._getexif()
                if not exif: return "", "", "", "", ""
                tags = {TAGS.get(t, t): v for t, v in exif.items()}
                m = tags.get('Model', '').strip()
                l = tags.get('LensModel', '').strip()
                et = tags.get('ExposureTime', '')
                f = tags.get('FNumber', '')
                iso = tags.get('ISOSpeedRatings', '')
                shutter = f"1/{int(1 / et)}s" if et and et < 1 else f"{et}s"
                aperture = f"f/{f}" if f else ""
                return m, l, shutter, aperture, str(iso)
        except:
            return "", "", "", "", ""

    def refresh_preview(self):
        if not self.current_path: return
        info = {
            'device': self.in_dev.text(),
            'lens': self.in_lens.text(),
            'param': f"{self.in_shutter.text()}  {self.in_aperture.text()}  ISO{self.in_iso.text()}",
            'sign': f"@{self.in_sign.text()}"
        }
        self.current_pil_preview = render_poster_engine(self.current_path, self.current_palette_hex, info)
        pix = pil_to_pixmap(self.current_pil_preview)
        self.preview_label.setPixmap(pix.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def export_image(self):
        if not self.current_pil_preview: return
        path, _ = QFileDialog.getSaveFileName(self, "保存海报", "", "JPEG (*.jpg)")
        if path: self.current_pil_preview.save(path, quality=95, subsampling=0)