import os
from PIL import Image
from PIL.ExifTags import TAGS
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt

from core.extractor import get_palette_by_mode
from core.renderer import render_poster_engine, pil_to_pixmap


class PhotoColorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhotoPalettePro - 摄影海报生成器")
        self.setMinimumSize(1300, 850)

        # 业务状态变量
        self.current_path = None
        self.last_open_dir = ""
        self.last_save_dir = ""
        self.poster_counter = 1
        self.current_palette_hex = []
        self.current_pil_preview = None

        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; }
            QFrame#ControlPanel { background: white; border-radius: 15px; border: 1px solid #ddd; }
            QLineEdit, QComboBox { border: 1px solid #ccc; border-radius: 4px; padding: 6px; background: #fafafa; }
            QPushButton { background: #34495e; color: white; border-radius: 6px; padding: 10px; font-weight: bold; }
            QPushButton#DelBtn { background: #e74c3c; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # --- 左侧：文件管理 ---
        left_panel = QVBoxLayout()
        self.file_list = QListWidget()
        self.file_list.currentRowChanged.connect(self.handle_image_selection)
        left_panel.addWidget(QLabel("<b>照片队列</b>"))
        left_panel.addWidget(self.file_list)

        btn_box = QHBoxLayout()
        self.btn_add = QPushButton("导入照片")
        self.btn_add.clicked.connect(self.import_files)
        self.btn_del = QPushButton("删除选中")
        self.btn_del.setObjectName("DelBtn")
        self.btn_del.clicked.connect(self.delete_selected_files)
        btn_box.addWidget(self.btn_add);
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

        # 新增算法切换
        c_layout.addWidget(QLabel("<h3>模式选择</h3>"))
        self.mode_select = QComboBox()
        self.mode_select.addItems(["默认渲染", "突出原色", "反差色"])
        self.mode_select.currentIndexChanged.connect(self.refresh_preview)
        c_layout.addWidget(self.mode_select)

        c_layout.addWidget(QLabel("<h3>文本定制</h3>"))
        self.in_dev = QLineEdit();
        c_layout.addWidget(QLabel("机身:"));
        c_layout.addWidget(self.in_dev)
        self.in_lens = QLineEdit();
        c_layout.addWidget(QLabel("镜头:"));
        c_layout.addWidget(self.in_lens)

        p_box = QHBoxLayout()
        self.in_shutter = QLineEdit();
        self.in_aperture = QLineEdit();
        self.in_iso = QLineEdit()
        p_box.addLayout(self.make_v_layout("快门", self.in_shutter))
        p_box.addLayout(self.make_v_layout("光圈", self.in_aperture))
        p_box.addLayout(self.make_v_layout("ISO", self.in_iso))
        c_layout.addLayout(p_box)

        self.in_sign = QLineEdit();
        self.in_sign.setText("moudou517")
        c_layout.addWidget(QLabel("签名:"));
        c_layout.addWidget(self.in_sign)

        c_layout.addSpacing(20)
        self.btn_refresh = QPushButton("🔄 实时预览")
        self.btn_refresh.clicked.connect(self.refresh_preview)
        c_layout.addWidget(self.btn_refresh)

        c_layout.addStretch()
        self.btn_export = QPushButton("💾 导出并自动移除")
        self.btn_export.clicked.connect(self.export_image)
        c_layout.addWidget(self.btn_export)

        main_layout.addWidget(self.ctrl_panel, 3)

    def make_v_layout(self, label, edit):
        v = QVBoxLayout();
        v.addWidget(QLabel(label));
        v.addWidget(edit);
        return v

    def import_files(self):
        # 默认上次打开路径[cite: 1]
        paths, _ = QFileDialog.getOpenFileNames(self, "选择照片", self.last_open_dir, "Images (*.jpg *.png)")
        if paths:
            self.last_open_dir = os.path.dirname(paths[0])
            for p in paths: self.file_list.addItem(p)
            self.file_list.setCurrentRow(0)

    def handle_image_selection(self, row):
        if row < 0: return
        self.current_path = self.file_list.item(row).text()
        # EXIF 提取[cite: 1]
        model, lens, s, a, i = self.get_exif(self.current_path)
        self.in_dev.setText(model if model else "ILCE-7CM2")
        self.in_lens.setText(lens if lens else "FE 20-70mm F4 G")
        self.in_shutter.setText(s);
        self.in_aperture.setText(a);
        self.in_iso.setText(i)
        self.refresh_preview()

    def get_exif(self, path):
        try:
            with Image.open(path) as img:
                exif = img._getexif()
                if not exif: return "", "", "", "", ""
                tags = {TAGS.get(t, t): v for t, v in exif.items()}
                m = tags.get('Model', '').strip()
                l = tags.get('LensModel', '').strip()
                et, f, iso = tags.get('ExposureTime', ''), tags.get('FNumber', ''), tags.get('ISOSpeedRatings', '')
                shutter = f"1/{int(1 / et)}s" if et and et < 1 else f"{et}s"
                return m, l, shutter, f"f/{f}" if f else "", str(iso)
        except:
            return "", "", "", "", ""

    def refresh_preview(self):
        if not self.current_path: return
        mode = self.mode_select.currentText()
        with Image.open(self.current_path) as img:
            # 直接赋值，因为 extractor 现在稳定返回字符串列表[cite: 6]
            self.current_palette_hex = get_palette_by_mode(img.convert('RGB'), mode)

        # 封装渲染信息[cite: 6]
        info = {
            'device': self.in_dev.text(),
            'lens': self.in_lens.text(),
            'param': f"{self.in_shutter.text()}  {self.in_aperture.text()}  ISO{self.in_iso.text()}",
            'sign': f"@{self.in_sign.text()}"
        }

        # 渲染海报（此时 hex_palette 是长度为 6 的 HEX 列表，布局将严格保持 3x2）
        self.current_pil_preview = render_poster_engine(self.current_path, self.current_palette_hex, info)

        # 更新 UI 预览[cite: 6]
        pix = pil_to_pixmap(self.current_pil_preview)
        self.preview_label.setPixmap(pix.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def export_image(self):
        if not self.current_pil_preview: return
        # 保存逻辑：优先上次保存路径，其次当前打开路径[cite: 1]
        save_dir = self.last_save_dir if self.last_save_dir else self.last_open_dir
        default_name = f"Poster{self.poster_counter}.jpg"
        path, _ = QFileDialog.getSaveFileName(self, "保存海报", os.path.join(save_dir, default_name), "JPEG (*.jpg)")

        if path:
            self.current_pil_preview.save(path, quality=95, subsampling=0)
            self.last_save_dir = os.path.dirname(path)
            self.poster_counter += 1
            # 自动从列表中移除[cite: 1]
            row = self.file_list.currentRow()
            self.file_list.takeItem(row)
            if self.file_list.count() > 0:
                self.file_list.setCurrentRow(0)
            else:
                self.preview_label.setText("处理完毕")

    def delete_selected_files(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
