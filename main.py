import sys
from PySide6.QtWidgets import QApplication
# 这里的导入路径要根据你具体在哪个文件里定义的类来决定
# 如果类在 ui/main_window.py 里，就用下面的导入：
from ui.main_window import PhotoColorApp

if __name__ == "__main__":
    # 1. 创建应用程序实例
    app = QApplication(sys.argv)

    # 2. 实例化你的主窗口
    window = PhotoColorApp()

    # 3. 显示窗口
    window.show()

    # 4. 开启 Qt 事件循环，这会阻塞进程直到你关闭窗口
    sys.exit(app.exec())