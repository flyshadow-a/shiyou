from PyQt5.QtWidgets import QApplication, QWidget

# 创建应用实例
app = QApplication([])

# 创建主窗口
window = QWidget()
window.setWindowTitle("我的第一个 PyQt 程序")
window.setGeometry(100, 100, 400, 300)  # (x, y, width, height)

# 显示窗口
window.show()

# 运行应用
app.exec_()