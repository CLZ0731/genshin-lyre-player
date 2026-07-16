"""
QSS 樣式定義模組

提供深色毛玻璃風格的 PyQt5 樣式表，搭配原神視覺風格的金色/青色色調。
"""

# 色彩定義
COLORS = {
    "bg_primary": "rgba(15, 15, 25, 230)",       # 深色主背景（半透明）
    "bg_secondary": "rgba(25, 25, 45, 200)",      # 次要背景
    "bg_hover": "rgba(45, 45, 75, 200)",          # 懸停背景
    "bg_pressed": "rgba(55, 55, 90, 220)",        # 按下背景
    "border": "rgba(80, 120, 200, 80)",           # 邊框色
    "border_accent": "rgba(180, 160, 100, 120)",  # 金色強調邊框
    "text_primary": "#E8E8F0",                     # 主文字
    "text_secondary": "#9098B0",                   # 次要文字
    "text_accent": "#D4C080",                      # 金色強調文字
    "text_cyan": "#70D0D0",                        # 青色強調
    "btn_bg": "rgba(35, 35, 60, 180)",            # 按鈕背景
    "btn_hover": "rgba(55, 55, 90, 200)",         # 按鈕懸停
    "btn_pressed": "rgba(70, 70, 110, 220)",      # 按鈕按下
    "progress_bg": "rgba(30, 30, 50, 150)",       # 進度條背景
    "progress_fill": "rgba(180, 160, 100, 200)",  # 進度條填充（金色）
    "close_hover": "rgba(200, 60, 60, 200)",      # 關閉按鈕懸停
}

MAIN_STYLESHEET = f"""
/* ═══════════════════ 主視窗 ═══════════════════ */
QWidget#MainWindow {{
    background-color: rgb(15, 15, 25);
    border: 1px solid rgba(80, 120, 200, 80);
    border-radius: 12px;
}}

/* ═══════════════════ 標題列 ═══════════════════ */
QWidget#TitleBar {{
    background-color: transparent;
    border-bottom: 1px solid {COLORS["border"]};
    padding: 4px 8px;
}}

QLabel#TitleLabel {{
    color: {COLORS["text_accent"]};
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
    font-weight: bold;
    background: transparent;
}}

/* ═══════════════════ 曲目資訊 ═══════════════════ */
QLabel#TrackName {{
    color: {COLORS["text_primary"]};
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 13px;
    font-weight: 600;
    padding: 2px 4px;
    background: transparent;
}}

QLabel#BpmLabel {{
    color: {COLORS["text_cyan"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 11px;
    padding: 2px 4px;
    background: transparent;
}}

QLabel#StatusLabel {{
    color: {COLORS["text_secondary"]};
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 10px;
    padding: 1px 4px;
    background: transparent;
}}

QLabel#NoteDisplay {{
    color: {COLORS["text_accent"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 16px;
    font-weight: bold;
    padding: 2px 6px;
    background: {COLORS["bg_secondary"]};
    border-radius: 6px;
    min-width: 40px;
    qproperty-alignment: AlignCenter;
}}

QLabel#ProgressLabel {{
    color: {COLORS["text_secondary"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 10px;
    background: transparent;
}}

/* ═══════════════════ 控制按鈕 ═══════════════════ */
QPushButton#ControlBtn {{
    background-color: {COLORS["btn_bg"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 14px;
    font-family: "Segoe UI Emoji", "Segoe UI Symbol";
    min-width: 36px;
    min-height: 28px;
}}

QPushButton#ControlBtn:hover {{
    background-color: {COLORS["btn_hover"]};
    border-color: {COLORS["border_accent"]};
    color: {COLORS["text_accent"]};
}}

QPushButton#ControlBtn:pressed {{
    background-color: {COLORS["btn_pressed"]};
}}

QPushButton#ControlBtn:disabled {{
    background-color: rgba(25, 25, 40, 100);
    color: rgba(100, 100, 120, 100);
    border-color: rgba(50, 50, 70, 60);
}}

/* 播放按鈕特殊樣式 */
QPushButton#PlayBtn {{
    background-color: rgba(40, 50, 80, 180);
    color: {COLORS["text_accent"]};
    border: 1px solid {COLORS["border_accent"]};
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 15px;
    font-family: "Segoe UI Emoji", "Segoe UI Symbol";
    min-width: 44px;
    min-height: 28px;
}}

QPushButton#PlayBtn:hover {{
    background-color: rgba(55, 65, 100, 210);
    border-color: rgba(210, 190, 120, 160);
}}

QPushButton#PlayBtn:pressed {{
    background-color: rgba(70, 80, 120, 230);
}}

/* ═══════════════════ 視窗按鈕（最小化/關閉） ═══════════════════ */
QPushButton#WinBtn {{
    background-color: transparent;
    color: {COLORS["text_secondary"]};
    border: none;
    border-radius: 4px;
    padding: 2px;
    font-size: 12px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
}}

QPushButton#WinBtn:hover {{
    background-color: {COLORS["bg_hover"]};
    color: {COLORS["text_primary"]};
}}

QPushButton#CloseBtn {{
    background-color: transparent;
    color: {COLORS["text_secondary"]};
    border: none;
    border-radius: 4px;
    padding: 2px;
    font-size: 12px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
}}

QPushButton#CloseBtn:hover {{
    background-color: {COLORS["close_hover"]};
    color: white;
}}

/* ═══════════════════ 進度條 ═══════════════════ */
QProgressBar {{
    background-color: {COLORS["progress_bg"]};
    border: none;
    border-radius: 3px;
    max-height: 4px;
    min-height: 4px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(100, 140, 200, 200),
        stop:1 rgba(180, 160, 100, 200)
    );
    border-radius: 3px;
}}

/* ═══════════════════ 設定對話框 ═══════════════════ */
QDialog {{
    background-color: rgb(20, 20, 35);
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
}}

QDialog QLabel {{
    color: {COLORS["text_primary"]};
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
}}

QDialog QLineEdit {{
    background-color: {COLORS["bg_secondary"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 4px 8px;
    font-family: "Consolas", "Cascadia Code";
    font-size: 12px;
}}

QDialog QLineEdit:focus {{
    border-color: {COLORS["border_accent"]};
}}

QDialog QPushButton {{
    background-color: {COLORS["btn_bg"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
}}

QDialog QPushButton:hover {{
    background-color: {COLORS["btn_hover"]};
    border-color: {COLORS["border_accent"]};
}}

/* ═══════════════════ 工具提示 ═══════════════════ */
QToolTip {{
    background-color: rgb(25, 25, 45);
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}
/* ═══════════════════ 下拉選單 ═══════════════════ */
QComboBox {{
    background-color: rgba(35, 35, 60, 180);
    color: #E8E8F0;
    border: 1px solid rgba(80, 120, 200, 80);
    border-radius: 6px;
    padding: 2px 8px;
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
    min-height: 24px;
}}

QComboBox:hover {{
    background-color: rgba(55, 55, 90, 200);
    border-color: rgba(180, 160, 100, 120);
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: rgb(25, 25, 40);
    color: #E8E8F0;
    selection-background-color: rgba(55, 55, 90, 200);
    selection-color: #D4C080;
    border: 1px solid rgba(80, 120, 200, 80);
    outline: none;
}}
"""
