"""
QSS 樣式定義模組 - Discord 視覺設計語彙版本

使用 deep-indigo 畫布作為背景，輔以經典的 Blurple、活力洋紅與電光綠，打造電競感十足的介面。
"""

# 色彩定義 (相容 Discord 設計規範)
COLORS = {
    "canvas": "#0a0d3a",          # 深靛藍畫布底色
    "surface_indigo": "#1e2353",   # Raised Indigo 面板色
    "surface_onyx": "#23272a",     # Onyx 次要面板/邊框色
    "blurple": "#5865f2",          # 經典品牌 Blurple
    "blurple_hover": "#3e49b8",    # 懸停 Blurple
    "green": "#35ed7e",            # 電光綠 (高亮行動按鈕)
    "green_hover": "#2ec96b",      # 電光綠懸停
    "magenta": "#ec48bd",          # 活力洋紅 (強調/發光/警告)
    "link_cyan": "#00b0f4",        # 連結青色
    "ink_white": "#ffffff",        # 主文字 (純白)
    "ink_muted": "#8f96a3",        # 次要文字 (暗灰藍)
}

MAIN_STYLESHEET = f"""
/* ═══════════════════ 主視窗 ═══════════════════ */
QWidget#MainWindow {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 {COLORS["canvas"]},
        stop:0.6 {COLORS["surface_indigo"]},
        stop:1 {COLORS["canvas"]}
    );
    border: 1px solid rgba(88, 101, 242, 100);
    border-radius: 16px;
}}

/* ═══════════════════ 標題列 ═══════════════════ */
QWidget#TitleBar {{
    background-color: transparent;
    border-bottom: 1px solid {COLORS["surface_indigo"]};
    padding: 4px 8px;
}}

QLabel#TitleLabel {{
    color: {COLORS["ink_white"]};
    font-family: "Inter", "Plus Jakarta Sans", "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
    font-weight: 800;
    text-transform: uppercase;
    background: transparent;
}}

/* ═══════════════════ 曲目資訊 ═══════════════════ */
QLabel#TrackName {{
    color: {COLORS["ink_white"]};
    font-family: "Inter", "Plus Jakarta Sans", "Segoe UI", "Microsoft YaHei UI";
    font-size: 13px;
    font-weight: 600;
    padding: 2px 4px;
    background: transparent;
}}

QLabel#BpmLabel {{
    color: {COLORS["link_cyan"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 11px;
    font-weight: bold;
    padding: 2px 4px;
    background: transparent;
}}

QLabel#StatusLabel {{
    color: {COLORS["ink_muted"]};
    font-family: "Inter", "Plus Jakarta Sans", "Segoe UI", "Microsoft YaHei UI";
    font-size: 10px;
    padding: 1px 4px;
    background: transparent;
}}

QLabel#NoteDisplay {{
    color: {COLORS["ink_white"]};
    background-color: {COLORS["magenta"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 15px;
    font-weight: 900;
    padding: 3px 6px;
    border-radius: 8px;
    min-width: 44px;
    qproperty-alignment: AlignCenter;
}}

QLabel#ProgressLabel {{
    color: {COLORS["ink_muted"]};
    font-family: "Consolas", "Cascadia Code";
    font-size: 10px;
    background: transparent;
}}

/* ═══════════════════ 控制按鈕 ═══════════════════ */
QPushButton#ControlBtn {{
    background-color: {COLORS["surface_indigo"]};
    color: {COLORS["ink_white"]};
    border: 1px solid {COLORS["surface_onyx"]};
    border-radius: 12px;
    padding: 6px 10px;
    font-size: 14px;
    font-family: "Segoe UI Emoji", "Segoe UI Symbol";
    min-width: 36px;
    min-height: 28px;
}}

QPushButton#ControlBtn:hover {{
    background-color: {COLORS["blurple"]};
    border-color: {COLORS["green"]};
    color: {COLORS["ink_white"]};
}}

QPushButton#ControlBtn:pressed {{
    background-color: {COLORS["blurple_hover"]};
}}

QPushButton#ControlBtn:disabled {{
    background-color: rgba(30, 35, 83, 100);
    color: rgba(143, 150, 163, 80);
    border-color: rgba(35, 39, 42, 60);
}}

/* 播放按鈕特殊樣式 (電光綠背景配黑字) */
QPushButton#PlayBtn {{
    background-color: {COLORS["green"]};
    color: #000000;
    border: none;
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 15px;
    font-family: "Segoe UI Emoji", "Segoe UI Symbol";
    font-weight: bold;
    min-width: 44px;
    min-height: 28px;
}}

QPushButton#PlayBtn:hover {{
    background-color: {COLORS["green_hover"]};
}}

QPushButton#PlayBtn:pressed {{
    background-color: {COLORS["surface_indigo"]};
    color: {COLORS["green"]};
    border: 1px solid {COLORS["green"]};
}}

/* ═══════════════════ 視窗按鈕 (最小化/關閉) ═══════════════════ */
QPushButton#WinBtn {{
    background-color: transparent;
    color: {COLORS["ink_muted"]};
    border: none;
    border-radius: 6px;
    padding: 2px;
    font-size: 12px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
}}

QPushButton#WinBtn:hover {{
    background-color: {COLORS["surface_indigo"]};
    color: {COLORS["ink_white"]};
}}

QPushButton#CloseBtn {{
    background-color: transparent;
    color: {COLORS["ink_muted"]};
    border: none;
    border-radius: 6px;
    padding: 2px;
    font-size: 12px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
}}

QPushButton#CloseBtn:hover {{
    background-color: {COLORS["magenta"]};
    color: {COLORS["ink_white"]};
}}

/* ═══════════════════ 進度條 ═══════════════════ */
QProgressBar {{
    background-color: {COLORS["surface_onyx"]};
    border: none;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS["blurple"]},
        stop:1 {COLORS["magenta"]}
    );
    border-radius: 3px;
}}

/* ═══════════════════ 設定對話框 ═══════════════════ */
QDialog {{
    background-color: {COLORS["canvas"]};
    border: 1px solid {COLORS["blurple"]};
    border-radius: 16px;
}}

QDialog QLabel {{
    color: {COLORS["ink_white"]};
    font-family: "Inter", "Plus Jakarta Sans", "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
}}

QDialog QLineEdit {{
    background-color: {COLORS["surface_onyx"]};
    color: {COLORS["ink_white"]};
    border: 1px solid {COLORS["surface_indigo"]};
    border-radius: 12px;
    padding: 5px 10px;
    font-family: "Consolas", "Cascadia Code";
    font-size: 12px;
}}

QDialog QLineEdit:focus {{
    border-color: {COLORS["blurple"]};
}}

QDialog QPushButton {{
    background-color: {COLORS["surface_indigo"]};
    color: {COLORS["ink_white"]};
    border: 1px solid {COLORS["surface_onyx"]};
    border-radius: 12px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: bold;
}}

QDialog QPushButton:hover {{
    background-color: {COLORS["blurple"]};
    border-color: {COLORS["green"]};
}}

/* ═══════════════════ 工具提示 ═══════════════════ */
QToolTip {{
    background-color: {COLORS["surface_indigo"]};
    color: {COLORS["ink_white"]};
    border: 1px solid {COLORS["surface_onyx"]};
    border-radius: 12px;
    padding: 5px 10px;
    font-size: 11px;
}}

/* ═══════════════════ 下拉選單 ═══════════════════ */
QComboBox {{
    background-color: {COLORS["surface_indigo"]};
    color: {COLORS["ink_white"]};
    border: 1px solid {COLORS["surface_onyx"]};
    border-radius: 12px;
    padding: 2px 10px;
    font-family: "Inter", "Plus Jakarta Sans", "Segoe UI", "Microsoft YaHei UI";
    font-size: 12px;
    min-height: 26px;
}}

QComboBox:hover {{
    background-color: {COLORS["surface_indigo"]};
    border-color: {COLORS["blurple"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["surface_indigo"]};
    color: {COLORS["ink_white"]};
    selection-background-color: {COLORS["blurple"]};
    selection-color: {COLORS["ink_white"]};
    border: 1px solid {COLORS["blurple"]};
    border-radius: 12px;
    outline: none;
}}
"""
