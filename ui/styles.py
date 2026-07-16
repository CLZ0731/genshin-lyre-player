"""
QSS 樣式定義模組 — Uber Move 設計語彙版

極簡黑白雙色調（Black & White Duet）為主視覺。
膠囊形（Pill Shape）圓角按鈕與控制項，搭配優雅的淡灰面板與無 Emoji 圖標。
"""

# ═══════════════════ 色彩系統 ═══════════════════
COLORS = {
    "canvas":          "#ffffff",  # 白色面板底色
    "canvas_soft":     "#efefef",  # 淺灰按鈕與輸入背景
    "canvas_softer":   "#f3f3f3",  # 主視窗與對話框底色
    "surface_pressed": "#e2e2e2",  # 按下時的灰色
    "primary":         "#000000",  # 純黑主色 (轉換按鈕、重點強調)
    "primary_hover":   "#282828",  # 黑色懸停
    "primary_pressed": "#4b4b4b",  # 黑色按下
    "ink":             "#000000",  # 主文字
    "ink_muted":       "#5e5e5e",  # 次要灰色文字
    "ink_dim":         "#afafaf",  # 佔位與極淡灰色文字
    "border":          "#e2e2e2",  # 細線邊框
    "border_focus":    "#000000",  # 聚焦邊框 (純黑)
}

C = COLORS  # 短別名

MAIN_STYLESHEET = f"""
/* ═══════════════════════════════════════════════
   主視窗 — 透明背景 (由 paintEvent 繪製極簡灰底)
   ═══════════════════════════════════════════════ */
QWidget#MainWindow {{
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   標題列
   ═══════════════════════════════════════════════ */
QWidget#TitleBar {{
    background: transparent;
    border-bottom: 1px solid {C["border"]};
    padding: 4px 4px;
}}

QLabel#TitleLabel {{
    color: {C["ink"]};
    font-family: "UberMove", "Inter", "Helvetica Neue", "Arial", sans-serif;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}}

QLabel#VersionLabel {{
    color: {C["ink_muted"]};
    font-family: "UberMoveText", "Consolas", "Cascadia Code", sans-serif;
    font-size: 11px;
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   面板容器 — 白色圓角卡片 (Uber Style)
   ═══════════════════════════════════════════════ */
QFrame#TrackPanel,
QFrame#ParamsPanel,
QFrame#PlaybackPanel {{
    background-color: {C["canvas"]};
    border: 1px solid {C["border"]};
    border-radius: 16px;
}}

/* ═══════════════════════════════════════════════
   面板內標題標籤
   ═══════════════════════════════════════════════ */
QLabel#PanelTitle {{
    color: {C["ink"]};
    font-family: "UberMove", "Inter", "Helvetica Neue", "Arial", sans-serif;
    font-size: 12px;
    font-weight: 700;
    background: transparent;
    padding: 0px 2px 4px 2px;
}}

/* ═══════════════════════════════════════════════
   曲目資訊標籤
   ═══════════════════════════════════════════════ */
QLabel#TrackName {{
    color: {C["ink"]};
    font-family: "UberMoveText", "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
    font-weight: 500;
    background: transparent;
}}

QLabel#BpmLabel {{
    color: {C["ink"]};
    font-family: "UberMoveText", "Consolas", "Cascadia Code", sans-serif;
    font-size: 11px;
    font-weight: bold;
    background: transparent;
}}

QLabel#StatusLabel {{
    color: {C["ink_muted"]};
    font-family: "UberMoveText", "Inter", "Segoe UI", sans-serif;
    font-size: 11px;
    background: transparent;
}}

QLabel#InfoSep {{
    color: {C["border"]};
    font-size: 11px;
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   音符顯示 — 純黑發光大矩形
   ═══════════════════════════════════════════════ */
QLabel#NoteDisplay {{
    color: {C["canvas"]};
    background-color: {C["primary"]};
    border: 1px solid {C["primary"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 18px;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 12px;
    min-width: 60px;
    min-height: 32px;
    qproperty-alignment: AlignCenter;
}}

QLabel#ProgressLabel {{
    color: {C["ink_muted"]};
    font-family: "Consolas", "Cascadia Code", sans-serif;
    font-size: 10px;
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   一般按鈕 — 膠囊圓角 (Pill Shape)
   ═══════════════════════════════════════════════ */
QPushButton#ControlBtn {{
    background-color: {C["canvas_soft"]};
    color: {C["ink"]};
    border: none;
    border-radius: 15px; /* 高度 30px 的半值，呈現完美膠囊 */
    padding: 6px 12px;
    font-family: "UberMoveText", "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
    font-weight: 500;
    min-width: 48px;
    min-height: 30px;
}}

QPushButton#ControlBtn:hover {{
    background-color: {C["border"]};
}}

QPushButton#ControlBtn:pressed {{
    background-color: {C["surface_pressed"]};
}}

QPushButton#ControlBtn:disabled {{
    background-color: {C["canvas_soft"]};
    color: {C["ink_dim"]};
}}

/* ═══════════════════════════════════════════════
   播放按鈕 — 黑色主膠囊 (Pill Shape)
   ═══════════════════════════════════════════════ */
QPushButton#PlayBtn {{
    background-color: {C["primary"]};
    color: {C["canvas"]};
    border: none;
    border-radius: 17px; /* 高度 34px 的半值 */
    padding: 8px 24px;
    font-family: "UberMoveText", "Inter", "Segoe UI", sans-serif;
    font-size: 14px;
    font-weight: 500;
    min-width: 120px;
    min-height: 34px;
}}

QPushButton#PlayBtn:hover {{
    background-color: {C["primary_hover"]};
}}

QPushButton#PlayBtn:pressed {{
    background-color: {C["primary_pressed"]};
}}

/* ═══════════════════════════════════════════════
   小工具按鈕 (如 ➕, 🎙️, 🗑️) — 迷你膠囊
   ═══════════════════════════════════════════════ */
QPushButton#ToolBtn {{
    background-color: {C["canvas_soft"]};
    color: {C["ink"]};
    border: none;
    border-radius: 14px; /* 高度 28px 的半值 */
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
}}

QPushButton#ToolBtn:hover {{
    background-color: {C["border"]};
}}

QPushButton#ToolBtn:pressed {{
    background-color: {C["surface_pressed"]};
}}

/* ═══════════════════════════════════════════════
   視窗控制按鈕
   ═══════════════════════════════════════════════ */
QPushButton#WinBtn,
QPushButton#CloseBtn {{
    background-color: transparent;
    color: {C["ink_muted"]};
    border: none;
    border-radius: 6px;
    padding: 2px;
    font-size: 13px;
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
}}

QPushButton#WinBtn:hover,
QPushButton#CloseBtn:hover {{
    background-color: {C["canvas_soft"]};
    color: {C["ink"]};
}}

/* ═══════════════════════════════════════════════
   進度條 — 極簡純黑填充
   ═══════════════════════════════════════════════ */
QProgressBar {{
    background-color: {C["canvas_soft"]};
    border: none;
    border-radius: 4px;
    max-height: 8px;
    min-height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {C["primary"]};
    border-radius: 4px;
}}

/* ═══════════════════════════════════════════════
   下拉選單 — 圓角與淡灰
   ═══════════════════════════════════════════════ */
QComboBox {{
    background-color: {C["canvas_soft"]};
    color: {C["ink"]};
    border: 1px solid {C["canvas_soft"]};
    border-radius: 12px;
    padding: 4px 12px;
    font-family: "UberMoveText", "Inter", "Segoe UI", sans-serif;
    font-size: 12px;
    min-height: 26px;
}}

QComboBox:hover {{
    border-color: {C["border"]};
}}

QComboBox:focus {{
    border-color: {C["border_focus"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
}}

QComboBox QAbstractItemView {{
    background-color: {C["canvas"]};
    color: {C["ink"]};
    selection-background-color: {C["canvas_soft"]};
    selection-color: {C["ink"]};
    border: 1px solid {C["border"]};
    border-radius: 12px;
    outline: none;
    padding: 4px;
}}

/* ═══════════════════════════════════════════════
   QSpinBox / QDoubleSpinBox — 膠囊灰底
   ═══════════════════════════════════════════════ */
QSpinBox, QDoubleSpinBox {{
    background-color: {C["canvas_soft"]};
    color: {C["ink"]};
    border: 1px solid {C["canvas_soft"]};
    border-radius: 12px;
    padding: 3px 8px;
    font-family: "Consolas", "Cascadia Code", sans-serif;
    font-size: 12px;
    min-height: 24px;
    min-width: 60px;
}}

QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {C["border"]};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {C["border_focus"]};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 0px;
    border: none;
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   QCheckBox — 簡約黑勾
   ═══════════════════════════════════════════════ */
QCheckBox {{
    color: {C["ink"]};
    font-family: "UberMoveText", "Inter", "Segoe UI", sans-serif;
    font-size: 12px;
    spacing: 6px;
    background: transparent;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 2px solid {C["border"]};
    background-color: {C["canvas"]};
}}

QCheckBox::indicator:hover {{
    border-color: {C["border_focus"]};
}}

QCheckBox::indicator:checked {{
    background-color: {C["primary"]};
    border-color: {C["primary"]};
}}

/* ═══════════════════════════════════════════════
   對話框 (對齊白色 Uber 風格)
   ═══════════════════════════════════════════════ */
QDialog {{
    background-color: {C["canvas"]};
    border: 1px solid {C["border"]};
    border-radius: 16px;
}}

QDialog QLabel {{
    color: {C["ink"]};
    font-family: "UberMoveText", "Inter", "Segoe UI", sans-serif;
    font-size: 12px;
}}

QDialog QLineEdit {{
    background-color: {C["canvas_soft"]};
    color: {C["ink"]};
    border: none;
    border-radius: 12px;
    padding: 5px 10px;
    font-family: "Consolas", "Cascadia Code", sans-serif;
    font-size: 12px;
}}

QDialog QLineEdit:focus {{
    border: 1px solid {C["border_focus"]};
}}

QDialog QPushButton {{
    background-color: {C["canvas_soft"]};
    color: {C["ink"]};
    border: none;
    border-radius: 15px;
    padding: 6px 18px;
    font-size: 12px;
    font-weight: bold;
}}

QDialog QPushButton:hover {{
    background-color: {C["border"]};
}}

QDialog QPushButton:pressed {{
    background-color: {C["surface_pressed"]};
}}

/* ═══════════════════════════════════════════════
   工具提示
   ═══════════════════════════════════════════════ */
QToolTip {{
    background-color: {C["canvas"]};
    color: {C["ink"]};
    border: 1px solid {C["border"]};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
}}

/* ═══════════════════════════════════════════════
   捲軸
   ═══════════════════════════════════════════════ */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: {C["ink_dim"]};
    border-radius: 3px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {C["primary"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   參數標籤
   ═══════════════════════════════════════════════ */
QLabel#ParamLabel {{
    color: {C["ink_muted"]};
    font-family: "UberMoveText", "Inter", "Segoe UI", sans-serif;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}}
"""
