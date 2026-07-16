"""
原神風物之詩琴 — 自動彈琴輔助程式

入口模組：初始化應用程式、建立 GUI、啟動事件迴圈。

使用方式：
    1. 將 MIDI 檔案 (.mid) 放入 midi_files/ 資料夾
    2. 執行 python main.py
    3. 在原神中開啟風物之詩琴
    4. 使用快捷鍵或懸浮視窗按鈕控制播放

預設快捷鍵：
    F8  — 播放/暫停
    F9  — 下一首
    F7  — 上一首
    F12 — 強制停止
"""

import sys
import os
import traceback

# NumPy 2.x 相容性 Monkeypatch (避免 pretty_midi 等舊庫調用已刪除的屬性)
try:
    import numpy as np
    if not hasattr(np, 'float'):
        np.float = float
    if not hasattr(np, 'int'):
        np.int = int
    if not hasattr(np, 'bool'):
        np.bool = bool
except ImportError:
    pass

# 診斷 ONNX Runtime 載入錯誤並寫入檔案
diag_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagnostic.txt")
try:
    with open(diag_file, "w", encoding="utf-8") as f:
        f.write("正在測試導入 onnxruntime...\n")
        try:
            import onnxruntime
            f.write(f"onnxruntime 導入成功！版本: {onnxruntime.__version__}\n")
        except Exception as e:
            f.write("onnxruntime 導入失敗，以下是詳細錯誤：\n")
            traceback.print_exc(file=f)
except Exception:
    pass

# 確保可以從任何位置執行
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from ui.main_window import MainWindow


def main():
    """程式主入口。"""
    print("[啟動] 正在初始化應用程式...")

    # 啟用高 DPI 縮放支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    print("[啟動] 正在建立主視窗...")

    # 建立並顯示懸浮視窗
    window = MainWindow()

    # 將視窗放到螢幕左上方安全位置
    window.move(100, 100)

    screen = app.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        print(f"[啟動] 螢幕可用區域: {geo.x()},{geo.y()} ~ {geo.right()},{geo.bottom()} ({geo.width()}x{geo.height()})")

    print(f"[啟動] 視窗位置: ({window.pos().x()}, {window.pos().y()}), 大小: {window.width()}x{window.height()}")
    print(f"[啟動] 視窗可見: {window.isVisible()}")

    window.show()
    window.activateWindow()
    window.raise_()

    print("[啟動] 視窗已顯示，程式正在運行！")
    print("[提示] 按 F8 播放/暫停 | F9 下一首 | F7 上一首 | F12 停止")

    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[錯誤] {e}")
        traceback.print_exc()
        input("按 Enter 關閉...")
