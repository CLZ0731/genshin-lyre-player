"""
QSS 樣式定義模組 — Discord 設計語彙完整版

深靛藍畫布 + Blurple/洋紅/電光綠三色體系，搭配三大面板分區佈局。
"""

# ═══════════════════ 色彩系統 ═══════════════════
COLORS = {
    "canvas":          "#0a0d3a",
    "surface_indigo":  "#1e2353",
    "surface_onyx":    "#23272a",
    "surface_black":   "#000000",
    "blurple":         "#5865f2",
    "blurple_dark":    "#4752c4",
    "blurple_glow":    "rgba(88, 101, 242, 60)",
    "green":           "#35ed7e",
    "green_dark":      "#2ec96b",
    "magenta":         "#ec48bd",
    "magenta_glow":    "rgba(236, 72, 189, 40)",
    "link_cyan":       "#00b0f4",
    "ink":             "#ffffff",
    "ink_muted":       "#8f96a3",
    "ink_dim":         "#5c6370",
    "hairline":        "rgba(88, 101, 242, 40)",
}

C = COLORS  # 短別名

MAIN_STYLESHEET = f"""
/* ═══════════════════════════════════════════════
   主視窗 — 背景由 paintEvent 自繪圓角漸層
   ═══════════════════════════════════════════════ */
QWidget#MainWindow {{
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   標題列
   ═══════════════════════════════════════════════ */
QWidget#TitleBar {{
    background: transparent;
    border-bottom: 1px solid {C["hairline"]};
    padding: 4px 4px;
}}

QLabel#TitleLabel {{
    color: {C["ink"]};
    font-family: "Inter", "Segoe UI", "Microsoft YaHei UI";
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 1px;
    background: transparent;
}}

QLabel#VersionLabel {{
    color: {C["ink_dim"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 10px;
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   面板容器 — Raised Indigo 卡片
   ═══════════════════════════════════════════════ */
QWidget#TrackPanel,
QWidget#ParamsPanel,
QWidget#PlaybackPanel {{
    background-color: {C["surface_indigo"]};
    border: 1px solid {C["blurple_glow"]};
    border-radius: 16px;
    padding: 10px 12px;
}}

/* 播放面板特殊處理：用更深的底色強調 */
QWidget#PlaybackPanel {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 {C["surface_indigo"]},
        stop:1 #161a42
    );
}}

/* ═══════════════════════════════════════════════
   面板內標題標籤
   ═══════════════════════════════════════════════ */
QLabel#PanelTitle {{
    color: {C["ink_muted"]};
    font-family: "Inter", "Segoe UI", "Microsoft YaHei UI";
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    background: transparent;
    padding: 0px 2px 4px 2px;
}}

/* ═══════════════════════════════════════════════
   曲目資訊標籤
   ═══════════════════════════════════════════════ */
QLabel#TrackName {{
    color: {C["ink"]};
    font-family: "Inter", "Segoe UI", "Microsoft YaHei UI";
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}}

QLabel#BpmLabel {{
    color: {C["link_cyan"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 11px;
    font-weight: bold;
    background: transparent;
}}

QLabel#StatusLabel {{
    color: {C["ink_muted"]};
    font-family: "Inter", "Segoe UI", "Microsoft YaHei UI";
    font-size: 11px;
    background: transparent;
}}

QLabel#InfoSep {{
    color: {C["ink_dim"]};
    font-size: 11px;
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   音符顯示 — 洋紅發光大矩形
   ═══════════════════════════════════════════════ */
QLabel#NoteDisplay {{
    color: {C["ink"]};
    background-color: {C["magenta"]};
    border: 2px solid {C["magenta_glow"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 18px;
    font-weight: 900;
    padding: 6px 12px;
    border-radius: 12px;
    min-width: 60px;
    min-height: 32px;
    qproperty-alignment: AlignCenter;
}}

QLabel#ProgressLabel {{
    color: {C["ink_dim"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 10px;
    background: transparent;
}}

/* ═══════════════════════════════════════════════
   控制按鈕 — Raised Indigo 圓角
   ═══════════════════════════════════════════════ */
QPushButton#ControlBtn {{
    background-color: rgba(30, 35, 83, 200);
    color: {C["ink"]};
    border: 1px solid {C["hairline"]};
    border-radius: 12px;
    padding: 7px 12px;
    font-size: 14px;
    font-family: "Segoe UI Emoji", "Segoe UI Symbol";
    min-width: 38px;
    min-height: 30px;
}}

QPushButton#ControlBtn:hover {{
    background-color: {C["blurple"]};
    border-color: {C["blurple"]};
    color: {C["ink"]};
}}

QPushButton#ControlBtn:pressed {{
    background-color: {C["blurple_dark"]};
}}

QPushButton#ControlBtn:disabled {{
    background-color: rgba(30, 35, 83, 80);
    color: rgba(143, 150, 163, 60);
    border-color: rgba(30, 35, 83, 40);
}}

/* ═══════════════════════════════════════════════
   播放按鈕 — 電光綠寬按鈕
   ═══════════════════════════════════════════════ */
QPushButton#PlayBtn {{
    background-color: {C["green"]};
    color: #000000;
    border: none;
    border-radius: 14px;
    padding: 8px 20px;
    font-size: 15px;
    font-family: "Inter", "Segoe UI", "Segoe UI Emoji";
    font-weight: 800;
    min-width: 120px;
    min-height: 34px;
}}

QPushButton#PlayBtn:hover {{
    background-color: {C["green_dark"]};
}}

QPushButton#PlayBtn:pressed {{
    background-color: {C["surface_indigo"]};
    color: {C["green"]};
    border: 2px solid {C["green"]};
}}

/* ═══════════════════════════════════════════════
   視窗操控按鈕（最小化 / 設定 / 關閉）
   ═══════════════════════════════════════════════ */
QPushButton#WinBtn {{
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

QPushButton#WinBtn:hover {{
    background-color: {C["surface_indigo"]};
    color: {C["ink"]};
}}

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

QPushButton#CloseBtn:hover {{
    background-color: {C["magenta"]};
    color: {C["ink"]};
}}

/* ═══════════════════════════════════════════════
   進度條 — 加粗 Blurple→洋紅漸層
   ═══════════════════════════════════════════════ */
QProgressBar {{
    background-color: rgba(10, 13, 58, 180);
    border: none;
    border-radius: 4px;
    max-height: 8px;
    min-height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {C["blurple"]},
        stop:1 {C["magenta"]}
    );
    border-radius: 4px;
}}

/* ═══════════════════════════════════════════════
   下拉選單
   ═══════════════════════════════════════════════ */
QComboBox {{
    background-color: rgba(10, 13, 58, 200);
    color: {C["ink"]};
    border: 1px solid {C["hairline"]};
    border-radius: 12px;
    padding: 4px 12px;
    font-family: "Inter", "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
    min-height: 26px;
}}

QComboBox:hover {{
    border-color: {C["blurple"]};
}}

QComboBox:focus {{
    border-color: {C["blurple"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
}}

QComboBox::down-arrow {{
    image: none;
    width: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: {C["surface_indigo"]};
    color: {C["ink"]};
    selection-background-color: {C["blurple"]};
    selection-color: {C["ink"]};
    border: 1px solid {C["blurple"]};
    border-radius: 8px;
    outline: none;
    padding: 4px;
}}

/* ═══════════════════════════════════════════════
   QSpinBox / QDoubleSpinBox — 深色風格
   ═══════════════════════════════════════════════ */
QSpinBox, QDoubleSpinBox {{
    background-color: rgba(10, 13, 58, 200);
    color: {C["ink"]};
    border: 1px solid {C["hairline"]};
    border-radius: 10px;
    padding: 3px 8px;
    font-family: "Consolas", "Cascadia Code";
    font-size: 12px;
    min-height: 24px;
    min-width: 60px;
}}

QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {C["blurple"]};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {C["blurple"]};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border: none;
    border-top-right-radius: 10px;
    background-color: transparent;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
    background-color: {C["blurple"]};
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border: none;
    border-bottom-right-radius: 10px;
    background-color: transparent;
}}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {C["blurple"]};
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    width: 0px;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    width: 0px;
}}

/* ═══════════════════════════════════════════════
   QCheckBox — Blurple 打勾底色
   ═══════════════════════════════════════════════ */
QCheckBox {{
    color: {C["ink"]};
    font-family: "Inter", "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
    spacing: 6px;
    background: transparent;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 2px solid {C["ink_dim"]};
    background-color: rgba(10, 13, 58, 200);
}}

QCheckBox::indicator:hover {{
    border-color: {C["blurple"]};
}}

QCheckBox::indicator:checked {{
    background-color: {C["blurple"]};
    border-color: {C["blurple"]};
}}

/* ═══════════════════════════════════════════════
   對話框（設定視窗、音軌選擇等）
   ═══════════════════════════════════════════════ */
QDialog {{
    background-color: {C["canvas"]};
    border: 1px solid {C["blurple_glow"]};
    border-radius: 16px;
}}

QDialog QLabel {{
    color: {C["ink"]};
    font-family: "Inter", "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
}}

QDialog QLineEdit {{
    background-color: rgba(10, 13, 58, 200);
    color: {C["ink"]};
    border: 1px solid {C["hairline"]};
    border-radius: 10px;
    padding: 5px 10px;
    font-family: "Consolas", "Cascadia Code";
    font-size: 12px;
}}

QDialog QLineEdit:focus {{
    border-color: {C["blurple"]};
}}

QDialog QPushButton {{
    background-color: {C["surface_indigo"]};
    color: {C["ink"]};
    border: 1px solid {C["hairline"]};
    border-radius: 12px;
    padding: 6px 18px;
    font-size: 12px;
    font-weight: bold;
}}

QDialog QPushButton:hover {{
    background-color: {C["blurple"]};
    border-color: {C["blurple"]};
}}

QDialog QPushButton:pressed {{
    background-color: {C["blurple_dark"]};
}}

/* ═══════════════════════════════════════════════
   工具提示
   ═══════════════════════════════════════════════ */
QToolTip {{
    background-color: {C["surface_indigo"]};
    color: {C["ink"]};
    border: 1px solid {C["blurple_glow"]};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
}}

/* ═══════════════════════════════════════════════
   捲軸 — 極細深色
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
    background-color: {C["blurple"]};
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
    font-family: "Inter", "Segoe UI", "Microsoft YaHei UI";
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}}
"""
