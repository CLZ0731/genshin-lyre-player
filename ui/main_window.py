"""
懸浮視窗 UI 模組

無邊框、永遠置頂的控制面板，支援滑鼠拖曳、播放控制與快捷鍵設定。
"""

import os

from PyQt5.QtCore import Qt, QPoint, pyqtSlot, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QDialog, QLineEdit,
    QFormLayout, QApplication, QComboBox, QFileDialog,
    QCheckBox, QScrollArea, QDialogButtonBox,
    QSpinBox, QDoubleSpinBox, QFrame
)
from PyQt5.QtGui import QColor, QFont, QPainter, QBrush, QPen, QPainterPath
import shutil
import os

from core.midi_parser import parse_midi, scan_midi_folder, ParsedMidi, MidiTrackInfo, analyze_best_pitch_shift
from core.player import PlayerThread, PlaybackState
from core.audio_converter import AudioConverterThread
from utils.config_manager import ConfigManager
from utils.hotkey_manager import HotkeyManager
from utils.online_presets import fetch_online_presets, lookup_preset, export_preset
from ui.styles import MAIN_STYLESHEET

from core.version import __version__ as APP_VERSION

class UpdateCheckerThread(QThread):
    """
    背景執行緒，自動向 GitHub API 查詢最新發布的 Release 版本。
    """
    update_available = pyqtSignal(str, str, str)  # 訊號傳遞：(新版本號, 下載網址, 更新說明)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self) -> None:
        try:
            import urllib.request
            import json
            import re
            url = "https://api.github.com/repos/CLZ0731/genshin-lyre-player/releases/latest"
            req = urllib.request.Request(
                url, 
                headers={
                    "User-Agent": "GenshinLyrePlayer-Updater",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            # 設定 5 秒超時，防止無網路時阻塞
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    tag_name = data.get("tag_name", "").strip()
                    
                    # 使用正則表達式提取純數字版本號 (例如: "GenshinLyrePlayer-1.0.1" -> "1.0.1", "v1.0.2" -> "1.0.2")
                    version_match = re.search(r'\d+(\.\d+)+', tag_name)
                    latest_version = version_match.group(0) if version_match else tag_name
                    
                    release_url = data.get("html_url", "")
                    release_notes = data.get("body", "")
                    
                    if latest_version and self.is_newer(latest_version, self.current_version):
                        self.update_available.emit(latest_version, release_url, release_notes)
        except Exception as e:
            # 靜默處理網路或 API 連線異常
            print(f"[檢查更新] 檢查失敗或網路不可達: {e}")

    def is_newer(self, latest: str, current: str) -> bool:
        """語意化版本比較 (例如 1.0.1 > 1.0.0)"""
        try:
            latest_parts = [int(p) for p in latest.split(".")]
            current_parts = [int(p) for p in current.split(".")]
            max_len = max(len(latest_parts), len(current_parts))
            latest_parts += [0] * (max_len - len(latest_parts))
            current_parts += [0] * (max_len - len(current_parts))
            return latest_parts > current_parts
        except ValueError:
            return latest != current


class TrackSelectionDialog(QDialog):
    """音軌選擇視窗"""
    def __init__(self, tracks_info: list[MidiTrackInfo], enabled_tracks: list[int] | None = None, melody_only: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎛️ 音軌過濾設定")
        self.setFixedSize(420, 480)
        self.setStyleSheet(MAIN_STYLESHEET)
        
        layout = QVBoxLayout(self)
        
        # 標題說明
        header = QLabel("★ = 適配原神程度（越多星越適合）")
        header.setStyleSheet("color: #8f96a3; font-size: 11px; padding: 2px;")
        layout.addWidget(header)

        # Skyline 主旋律提取核取方塊
        self._melody_only_cb = QCheckBox("🎵 啟用 Skyline 主旋律提取（自動過濾伴奏與低音）")
        self._melody_only_cb.setChecked(melody_only)
        self._melody_only_cb.setStyleSheet(
            "color: #35ed7e; font-size: 12px; font-weight: bold; padding: 6px; "
            "border-bottom: 1px solid rgba(88,101,242,40); margin-bottom: 6px;"
        )
        self._melody_only_cb.setToolTip("開啟後，播放器將只挑選音高最高的單一聲部（主旋律），丟棄所有低音伴奏和弦，極適合轉錄琴譜！")
        layout.addWidget(self._melody_only_cb)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        self.content_layout = QVBoxLayout(content)
        
        self.checkboxes = {}
        for track in tracks_info:
            # 計算星級評分 (1~5 星)
            stars = max(1, min(5, track.suitability // 20))
            star_str = "★" * stars + "☆" * (5 - stars)
            
            label = f"{track.name} [{track.instrument}] {star_str} ({track.note_count} 音符)"
            cb = QCheckBox(label)
            cb.setStyleSheet("color: #ffffff; font-size: 12px; padding: 3px;")
            if enabled_tracks is None:
                # 首次載入：自動推薦適配分數 >= 60 的音軌
                cb.setChecked(track.suitability >= 60)
            else:
                cb.setChecked(track.index in enabled_tracks)
            self.checkboxes[track.index] = cb
            self.content_layout.addWidget(cb)
            
        self.content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_enabled_tracks(self) -> list[int]:
        return [idx for idx, cb in self.checkboxes.items() if cb.isChecked()]

    def is_melody_only(self) -> bool:
        return self._melody_only_cb.isChecked()


class SettingsDialog(QDialog):
    """快捷鍵與系統設定對話框。"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self.setWindowTitle("⚙ 系統設定")
        self.setFixedSize(300, 310)
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 標題
        title = QLabel("⚙ 系統設定")
        title.setStyleSheet(
            "color: #5865f2; font-size: 14px; font-weight: 800; "
            "font-family: 'Inter', 'Segoe UI', 'Microsoft YaHei UI'; letter-spacing: 1px;"
        )
        layout.addWidget(title)

        # 表單
        form = QFormLayout()
        form.setSpacing(8)

        hotkeys = self._config.hotkeys
        self._inputs = {}

        labels = {
            "play_pause": "播放/暫停",
            "next_track": "下一首",
            "prev_track": "上一首",
            "force_stop": "強制停止",
        }

        for action, label_text in labels.items():
            edit = QLineEdit(hotkeys.get(action, ""))
            edit.setPlaceholderText("按鍵名稱，如 F8")
            self._inputs[action] = edit
            form.addRow(label_text + "：", edit)

        # AI 轉錄過濾強度設定
        self._sensitivity_combo = QComboBox()
        self._sensitivity_combo.addItems(["高 (極淨旋律)", "中 (推薦格式)", "低 (完整細節)"])
        self._sensitivity_combo.setStyleSheet(
            "background-color: rgba(10,13,58,200); color: #ffffff; border: 1px solid rgba(88,101,242,40); "
            "border-radius: 10px; padding: 3px 8px; font-size: 12px;"
        )
        
        current_sens = self._config.transcribe_sensitivity
        if current_sens == "high":
            self._sensitivity_combo.setCurrentIndex(0)
        elif current_sens == "low":
            self._sensitivity_combo.setCurrentIndex(2)
        else:
            self._sensitivity_combo.setCurrentIndex(1)
            
        form.addRow("AI 轉錄過濾：", self._sensitivity_combo)

        layout.addLayout(form)

        # 按鈕列
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        save_btn = QPushButton("💾 儲存")
        save_btn.clicked.connect(self._save)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _save(self) -> None:
        """儲存設定。"""
        new_hotkeys = {}
        for action, edit in self._inputs.items():
            value = edit.text().strip()
            if value:
                new_hotkeys[action] = value

        if new_hotkeys:
            self._config.hotkeys = new_hotkeys
            
        # 儲存 AI 轉錄過濾靈敏度
        idx = self._sensitivity_combo.currentIndex()
        if idx == 0:
            self._config.transcribe_sensitivity = "high"
        elif idx == 2:
            self._config.transcribe_sensitivity = "low"
        else:
            self._config.transcribe_sensitivity = "medium"
            
        self.accept()


class MainWindow(QWidget):
    """
    主控制面板懸浮視窗。

    功能：
    - 無邊框 + 永遠置頂 + 滑鼠拖曳
    - 顯示曲目名稱、BPM、播放進度
    - 播放/暫停、上一首、下一首、停止按鈕
    - 快捷鍵設定入口
    """

    def __init__(self):
        super().__init__()

        # ── 視窗屬性 ──
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setObjectName("MainWindow")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(420, 500)
        self.resize(480, 540)
        self.setMouseTracking(True)

        # ── 拖曳與縮放狀態 ──
        self._drag_pos: QPoint | None = None
        self._border_width = 8
        self._resize_dir = None
        self._press_global_pos = QPoint()
        self._press_geometry = None

        # ── 初始化元件 ──
        self._config = ConfigManager()
        self._hotkey_manager = HotkeyManager(self)
        self._player = PlayerThread(self)

        # ── 曲目列表 ──
        import sys
        if getattr(sys, 'frozen', False):
            midi_folder = os.path.join(os.path.dirname(sys.executable), "midi_files")
        else:
            midi_folder = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "midi_files"
            )
        self._midi_folder = os.path.normpath(midi_folder)
        self._midi_files: list[str] = []
        self._current_index = 0
        self._current_midi = None
        self._current_enabled_tracks = None
        self._current_wrap_octave = True
        self._current_chord_threshold = 0.005
        self._current_melody_only = False

        # ── 建立 UI ──
        self._init_ui()
        self._apply_styles()
        self._connect_signals()

        # ── 載入曲目 ──
        self._refresh_playlist()

        # ── 註冊快捷鍵 ──
        self._hotkey_manager.register(self._config.hotkeys)

        # ── 檢查更新 ──
        self._update_checker = UpdateCheckerThread(APP_VERSION, self)
        self._update_checker.update_available.connect(self._show_update_dialog)
        self._update_checker.start()

    # ═══════════════════ UI 初始化 ═══════════════════

    def _init_ui(self) -> None:
        """建構介面佈局 — 三大面板分區設計。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 12)
        main_layout.setSpacing(8)

        # ════════════════════════════════════════════
        # 標題列
        # ════════════════════════════════════════════
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(30)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(4, 0, 0, 0)
        title_layout.setSpacing(6)

        self._title_label = QLabel("🎵 原神詩琴助手")
        self._title_label.setObjectName("TitleLabel")
        title_layout.addWidget(self._title_label)

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setObjectName("VersionLabel")
        title_layout.addWidget(version_label)

        title_layout.addStretch()

        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("WinBtn")
        settings_btn.setToolTip("快捷鍵設定")
        settings_btn.clicked.connect(self._open_settings)
        title_layout.addWidget(settings_btn)

        min_btn = QPushButton("─")
        min_btn.setObjectName("WinBtn")
        min_btn.setToolTip("最小化")
        min_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setToolTip("關閉")
        close_btn.clicked.connect(self._on_close)
        title_layout.addWidget(close_btn)

        main_layout.addWidget(title_bar)

        # ════════════════════════════════════════════
        # 面板一：曲目選擇 (Track Panel)
        # ════════════════════════════════════════════
        track_panel = QFrame()
        track_panel.setObjectName("TrackPanel")
        track_panel_layout = QVBoxLayout(track_panel)
        track_panel_layout.setContentsMargins(12, 8, 12, 10)
        track_panel_layout.setSpacing(8)

        # 面板標題
        track_title = QLabel("📂 曲目選擇")
        track_title.setObjectName("PanelTitle")
        track_panel_layout.addWidget(track_title)

        # 曲目下拉 + 操作按鈕
        track_row = QHBoxLayout()
        track_row.setSpacing(6)
        self._track_combo = QComboBox()
        self._track_combo.setObjectName("TrackCombo")
        self._track_combo.setToolTip("選擇曲目")
        self._track_combo.currentIndexChanged.connect(self._on_track_changed)
        track_row.addWidget(self._track_combo, stretch=1)

        self._add_midi_btn = QPushButton("➕")
        self._add_midi_btn.setObjectName("ToolBtn")
        self._add_midi_btn.setToolTip("匯入 MIDI 檔案")
        self._add_midi_btn.clicked.connect(self._import_midi)
        track_row.addWidget(self._add_midi_btn)

        self._audio_transcribe_btn = QPushButton("🎙️")
        self._audio_transcribe_btn.setObjectName("ToolBtn")
        self._audio_transcribe_btn.setToolTip("AI 音訊轉錄 MIDI")
        self._audio_transcribe_btn.clicked.connect(self._transcribe_audio)
        track_row.addWidget(self._audio_transcribe_btn)

        self._delete_midi_btn = QPushButton("🗑️")
        self._delete_midi_btn.setObjectName("ToolBtn")
        self._delete_midi_btn.setToolTip("刪除選取的樂譜")
        self._delete_midi_btn.clicked.connect(self._delete_current_midi)
        track_row.addWidget(self._delete_midi_btn)

        track_panel_layout.addLayout(track_row)

        # 資訊列：BPM + 狀態 + 樂器
        info_row = QHBoxLayout()
        info_row.setSpacing(6)

        self._instrument_combo = QComboBox()
        self._instrument_combo.addItems(["🎵 詩琴 (短音)", "📯 圓號 (長音)"])
        self._instrument_combo.currentIndexChanged.connect(self._on_instrument_changed)
        info_row.addWidget(self._instrument_combo)

        self._track_btn = QPushButton("🎛️ 音軌")
        self._track_btn.setObjectName("ControlBtn")
        self._track_btn.setToolTip("過濾伴奏與雜音")
        self._track_btn.clicked.connect(self._open_track_settings)
        info_row.addWidget(self._track_btn)

        sep1 = QLabel("│")
        sep1.setObjectName("InfoSep")
        info_row.addWidget(sep1)

        self._bpm_label = QLabel("BPM: --")
        self._bpm_label.setObjectName("BpmLabel")
        info_row.addWidget(self._bpm_label)

        sep2 = QLabel("│")
        sep2.setObjectName("InfoSep")
        info_row.addWidget(sep2)

        self._status_label = QLabel("就緒")
        self._status_label.setObjectName("StatusLabel")
        info_row.addWidget(self._status_label)

        info_row.addStretch()
        track_panel_layout.addLayout(info_row)

        main_layout.addWidget(track_panel)

        # ════════════════════════════════════════════
        # 面板二：演奏參數 (Params Panel)
        # ════════════════════════════════════════════
        params_panel = QFrame()
        params_panel.setObjectName("ParamsPanel")
        params_panel_layout = QVBoxLayout(params_panel)
        params_panel_layout.setContentsMargins(12, 8, 12, 10)
        params_panel_layout.setSpacing(8)

        params_title = QLabel("🎛️ 演奏參數")
        params_title.setObjectName("PanelTitle")
        params_panel_layout.addWidget(params_title)

        # 第一列：升降調 + 速度
        params_row1 = QHBoxLayout()
        params_row1.setSpacing(8)

        shift_label = QLabel("升降調")
        shift_label.setObjectName("ParamLabel")
        params_row1.addWidget(shift_label)

        self._pitch_spin = QSpinBox()
        self._pitch_spin.setRange(-12, 12)
        self._pitch_spin.setValue(0)
        self._pitch_spin.setSuffix(" 半音")
        self._pitch_spin.setToolTip("手動調整音高 (半音)")
        self._pitch_spin.valueChanged.connect(self._on_settings_changed)
        params_row1.addWidget(self._pitch_spin)

        params_row1.addSpacing(12)

        speed_label = QLabel("速度")
        speed_label.setObjectName("ParamLabel")
        params_row1.addWidget(speed_label)

        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.5, 2.0)
        self._speed_spin.setSingleStep(0.1)
        self._speed_spin.setValue(1.0)
        self._speed_spin.setSuffix("x")
        self._speed_spin.setToolTip("播放速度倍率")
        self._speed_spin.valueChanged.connect(self._on_settings_changed)
        params_row1.addWidget(self._speed_spin)

        params_row1.addStretch()
        params_panel_layout.addLayout(params_row1)

        # 第二列：核取方塊
        params_row2 = QHBoxLayout()
        params_row2.setSpacing(12)

        self._dynamic_shift_cb = QCheckBox("智能變調")
        self._dynamic_shift_cb.setToolTip("播放中自動偵測變調並平移音階")
        self._dynamic_shift_cb.stateChanged.connect(self._on_settings_changed)
        params_row2.addWidget(self._dynamic_shift_cb)

        self._velocity_cb = QCheckBox("力度演奏")
        self._velocity_cb.setToolTip("根據音符力度動態調整按壓時長")
        self._velocity_cb.setChecked(True)
        self._velocity_cb.stateChanged.connect(self._on_velocity_changed)
        params_row2.addWidget(self._velocity_cb)

        params_row2.addStretch()
        params_panel_layout.addLayout(params_row2)

        main_layout.addWidget(params_panel)

        # ════════════════════════════════════════════
        # 面板三：播放控制 (Playback Panel)
        # ════════════════════════════════════════════
        playback_panel = QFrame()
        playback_panel.setObjectName("PlaybackPanel")
        playback_panel_layout = QVBoxLayout(playback_panel)
        playback_panel_layout.setContentsMargins(12, 8, 12, 12)
        playback_panel_layout.setSpacing(8)

        # 音符顯示 + 狀態 (橫向佈局)
        note_row = QHBoxLayout()
        note_row.setSpacing(12)

        note_row.addStretch()

        self._note_display = QLabel("--")
        self._note_display.setObjectName("NoteDisplay")
        note_row.addWidget(self._note_display)

        note_row.addStretch()

        playback_panel_layout.addLayout(note_row)

        # 進度條
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        playback_panel_layout.addWidget(self._progress_bar)

        # 進度文字
        self._progress_label = QLabel("0 / 0")
        self._progress_label.setObjectName("ProgressLabel")
        self._progress_label.setAlignment(Qt.AlignCenter)
        playback_panel_layout.addWidget(self._progress_label)

        # 控制按鈕列
        control_layout = QHBoxLayout()
        control_layout.setSpacing(8)
        control_layout.setContentsMargins(0, 4, 0, 0)

        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setObjectName("ControlBtn")
        self._prev_btn.setToolTip("上一首 (F7)")
        self._prev_btn.clicked.connect(self._prev_track)
        control_layout.addWidget(self._prev_btn)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setObjectName("ControlBtn")
        self._stop_btn.setToolTip("停止 (F12)")
        self._stop_btn.clicked.connect(self._force_stop)
        control_layout.addWidget(self._stop_btn)

        self._play_btn = QPushButton("▶  播放")
        self._play_btn.setObjectName("PlayBtn")
        self._play_btn.setToolTip("播放/暫停 (F8)")
        self._play_btn.clicked.connect(self._toggle_play_pause)
        control_layout.addWidget(self._play_btn)

        self._next_btn = QPushButton("⏭")
        self._next_btn.setObjectName("ControlBtn")
        self._next_btn.setToolTip("下一首 (F9)")
        self._next_btn.clicked.connect(self._next_track)
        control_layout.addWidget(self._next_btn)

        self._refresh_btn = QPushButton("🔄")
        self._refresh_btn.setObjectName("ControlBtn")
        self._refresh_btn.setToolTip("重新掃描 MIDI 資料夾")
        self._refresh_btn.clicked.connect(self._refresh_playlist)
        control_layout.addWidget(self._refresh_btn)

        playback_panel_layout.addLayout(control_layout)

        main_layout.addWidget(playback_panel)

    def _apply_styles(self) -> None:
        """套用 QSS 樣式表。"""
        self.setStyleSheet(MAIN_STYLESHEET)

    def paintEvent(self, event) -> None:
        """自繪圓角背景，解決 FramelessWindowHint 下 QSS border-radius 無法裁切視窗形狀的問題。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 繪製圓角矩形背景
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(self.width()), float(self.height()), 16.0, 16.0)
        painter.setClipPath(path)

        # 漸層背景
        from PyQt5.QtGui import QLinearGradient
        grad = QLinearGradient(0, 0, self.width() * 0.4, self.height())
        grad.setColorAt(0.0, QColor(10, 13, 58))
        grad.setColorAt(0.5, QColor(16, 20, 64))
        grad.setColorAt(1.0, QColor(10, 13, 58))
        painter.fillPath(path, QBrush(grad))

        # 繪製邊框
        painter.setPen(QPen(QColor(88, 101, 242, 60), 1.0))
        painter.drawPath(path)
        painter.end()

    # ═══════════════════ 信號連接 ═══════════════════

    def _connect_signals(self) -> None:
        """連接所有信號與槽。"""
        # 播放引擎信號
        self._player.state_changed.connect(self._on_state_changed)
        self._player.progress_updated.connect(self._on_progress_updated)
        self._player.note_played.connect(self._on_note_played)
        self._player.playback_finished.connect(self._on_playback_finished)
        self._player.error_occurred.connect(self._on_error)

        # 全域快捷鍵信號
        self._hotkey_manager.play_pause_triggered.connect(self._toggle_play_pause)
        self._hotkey_manager.next_track_triggered.connect(self._next_track)
        self._hotkey_manager.prev_track_triggered.connect(self._prev_track)
        self._hotkey_manager.force_stop_triggered.connect(self._force_stop)

    # ═══════════════════ 曲目管理 ═══════════════════

    def _refresh_playlist(self) -> None:
        """重新掃描 MIDI 資料夾。"""
        self._midi_files = scan_midi_folder(self._midi_folder)
        
        self._track_combo.blockSignals(True)
        self._track_combo.clear()

        if self._midi_files:
            for file in self._midi_files:
                self._track_combo.addItem(os.path.basename(file))
            self._current_index = 0
            self._track_combo.setCurrentIndex(self._current_index)
            self._load_current_track()
            self._status_label.setText(
                f"共 {len(self._midi_files)} 首"
            )
        else:
            self._track_combo.addItem("❌ 未找到 MIDI 檔案")
            self._bpm_label.setText("BPM: --")
            self._status_label.setText(
                f"請匯入 .mid 檔案"
            )
            self._current_midi = None
            
        self._track_combo.blockSignals(False)

    def _load_current_track(self) -> None:
        """載入當前索引的 MIDI 檔案。"""
        if not self._midi_files:
            return

        filepath = self._midi_files[self._current_index]
        try:
            self._current_midi = parse_midi(
                filepath, 
                enabled_tracks=self._current_enabled_tracks,
                pitch_shift=self._pitch_spin.value(),
                speed_multiplier=self._speed_spin.value(),
                dynamic_shift=self._dynamic_shift_cb.isChecked(),
                wrap_octave=self._current_wrap_octave,
                chord_threshold=self._current_chord_threshold,
                melody_only=self._current_melody_only
            )
            self._player.set_midi_data(self._current_midi)
            self._player.set_press_delay(
                self._config.press_delay_min,
                self._config.press_delay_max,
            )
            self._player.set_velocity_dynamics(self._velocity_cb.isChecked())

            # 更新 UI
            self._bpm_label.setText(f"BPM: {self._current_midi.bpm:.0f}")
            self._progress_bar.setValue(0)
            self._progress_label.setText(
                f"0 / {self._current_midi.total_notes}"
            )
            self._note_display.setText("--")
            self._play_btn.setText("▶  播放")

        except Exception as e:
            self._bpm_label.setText("BPM: --")
            self._status_label.setText("載入失敗")
            self._current_midi = None

    @pyqtSlot()
    def _import_midi(self) -> None:
        """匯入外部 MIDI 檔案。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "選擇 MIDI 檔案", "", "MIDI 檔案 (*.mid *.midi)"
        )
        if file_path:
            try:
                os.makedirs(self._midi_folder, exist_ok=True)
                filename = os.path.basename(file_path)
                dest_path = os.path.join(self._midi_folder, filename)
                shutil.copy2(file_path, dest_path)
                self._refresh_playlist()
                
                # 找到剛匯入的檔案並選取
                for i, f in enumerate(self._midi_files):
                    if os.path.basename(f) == filename:
                        self._track_combo.setCurrentIndex(i)
                        break
            except Exception as e:
                self._note_display.setText("匯入失敗")

    @pyqtSlot()
    def _delete_current_midi(self) -> None:
        """刪除當前選取的樂譜檔案。"""
        if not self._midi_files or self._current_index >= len(self._midi_files):
            return

        filepath = self._midi_files[self._current_index]
        filename = os.path.basename(filepath)
        
        # 彈出確認視窗
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "⚠️ 確認刪除",
            f"確定要永久刪除樂譜「{filename}」嗎？\n此動作將無法復原！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 停止播放
            self._force_stop()
            
            try:
                # 刪除實體檔案
                if os.path.exists(filepath):
                    os.remove(filepath)
                    
                # 移除設定檔中的偏好設定
                self._config.clear_track_pref(filename)
                
                # 重新整理曲目
                self._refresh_playlist()
                
                # 彈出提示通知
                self._status_label.setText("已刪除樂譜")
                
            except Exception as e:
                QMessageBox.critical(self, "錯誤", f"刪除檔案失敗: {e}")

    @pyqtSlot()
    def _open_track_settings(self) -> None:
        """開啟音軌選擇視窗。"""
        if not self._current_midi or not self._current_midi.tracks_info:
            return
            
        dialog = TrackSelectionDialog(
            tracks_info=self._current_midi.tracks_info,
            enabled_tracks=self._current_enabled_tracks,
            melody_only=self._current_melody_only,
            parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            self._force_stop()
            self._current_enabled_tracks = dialog.get_enabled_tracks()
            self._current_melody_only = dialog.is_melody_only()
            
            # 儲存偏好
            filename = os.path.basename(self._midi_files[self._current_index])
            self._config.set_track_pref(
                filename, 
                self._pitch_spin.value(), 
                self._speed_spin.value(), 
                self._current_enabled_tracks,
                self._dynamic_shift_cb.isChecked(),
                self._velocity_cb.isChecked(),
                self._current_wrap_octave,
                self._current_chord_threshold,
                self._current_melody_only
            )
            
            self._load_current_track()

    @pyqtSlot()
    def _transcribe_audio(self) -> None:
        """選擇音訊檔案並呼叫 AI 轉錄為 MIDI。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "選擇音訊檔案", "", "音訊檔案 (*.mp3 *.wav *.m4a *.ogg *.flac)"
        )
        if not file_path:
            return

        # 準備輸出路徑
        filename = os.path.splitext(os.path.basename(file_path))[0]
        output_midi_name = f"{filename}_transcribed.mid"
        output_midi_path = os.path.join(self._midi_folder, output_midi_name)

        # 根據設定取得 AI 轉錄靈敏度閾值
        sens = self._config.transcribe_sensitivity
        if sens == "high":
            # 高強度過濾：大幅過濾噪音與背景雜音，只保留最強的主旋律
            onset_threshold = 0.70
            frame_threshold = 0.50
        elif sens == "low":
            # 低強度過濾：保留最多細節（適合極度乾淨的鋼琴獨奏）
            onset_threshold = 0.45
            frame_threshold = 0.25
        else:
            # 預設中等過濾
            onset_threshold = 0.55
            frame_threshold = 0.35

        # 鎖定 UI 避免重複操作或在播放時干擾
        self._force_stop()
        self._set_ui_enabled(False)
        self._status_label.setText("🎙️ AI 轉錄中... (約需10-20秒)")

        # 啟動非同步執行緒
        self._transcribe_thread = AudioConverterThread(
            file_path, 
            output_midi_path, 
            onset_threshold=onset_threshold, 
            frame_threshold=frame_threshold, 
            parent=self
        )
        self._transcribe_thread.finished.connect(self._on_transcribe_success)
        self._transcribe_thread.error.connect(self._on_transcribe_error)
        self._transcribe_thread.start()

    def _set_ui_enabled(self, enabled: bool) -> None:
        """批次設定主要控制元件的啟用狀態。"""
        self._track_combo.setEnabled(enabled)
        self._add_midi_btn.setEnabled(enabled)
        self._audio_transcribe_btn.setEnabled(enabled)
        self._play_btn.setEnabled(enabled)
        self._prev_btn.setEnabled(enabled)
        self._next_btn.setEnabled(enabled)
        self._stop_btn.setEnabled(enabled)
        self._refresh_btn.setEnabled(enabled)
        self._pitch_spin.setEnabled(enabled)
        self._speed_spin.setEnabled(enabled)
        self._dynamic_shift_cb.setEnabled(enabled)
        self._velocity_cb.setEnabled(enabled)
        self._instrument_combo.setEnabled(enabled)
        self._track_btn.setEnabled(enabled)

    @pyqtSlot(str)
    def _on_transcribe_success(self, midi_path: str) -> None:
        """轉錄成功回呼。"""
        self._set_ui_enabled(True)
        self._refresh_playlist()
        
        # 尋找並選取剛生成的 MIDI
        filename = os.path.basename(midi_path)
        for i, f in enumerate(self._midi_files):
            if os.path.basename(f) == filename:
                self._track_combo.setCurrentIndex(i)
                break
                
        self._status_label.setText("🎙️ 轉錄成功！")

    @pyqtSlot(str)
    def _on_transcribe_error(self, err_msg: str) -> None:
        """轉錄失敗回呼。"""
        self._set_ui_enabled(True)
        self._status_label.setText("轉錄失敗")
        self._note_display.setText("語音分析失敗，請使用更清晰的音訊。")
        print(f"[轉錄錯誤] {err_msg}")

    @pyqtSlot()
    def _on_settings_changed(self) -> None:
        """當手動調整升降調或速度時。"""
        if self._midi_files:
            self._force_stop()
            
            # 儲存偏好
            filename = os.path.basename(self._midi_files[self._current_index])
            self._config.set_track_pref(
                filename, 
                self._pitch_spin.value(), 
                self._speed_spin.value(), 
                self._current_enabled_tracks,
                self._dynamic_shift_cb.isChecked(),
                self._velocity_cb.isChecked(),
                self._current_wrap_octave,
                self._current_chord_threshold,
                self._current_melody_only
            )
            
            self._load_current_track()

    @pyqtSlot()
    def _on_velocity_changed(self) -> None:
        """當力度演奏開關變更時。"""
        self._player.set_velocity_dynamics(self._velocity_cb.isChecked())

    @pyqtSlot(int)
    def _on_track_changed(self, index: int) -> None:
        """當下拉選單切換曲目時。"""
        if 0 <= index < len(self._midi_files):
            self._force_stop()
            self._current_index = index
            
            filepath = self._midi_files[self._current_index]
            filename = os.path.basename(filepath)
            prefs = self._config.get_track_pref(filename)
            
            # 若本地無偏好，嘗試從線上預設庫查詢
            if not prefs:
                try:
                    online_data = fetch_online_presets(timeout=3.0)
                    online_preset = lookup_preset(filepath, online_data)
                    if online_preset:
                        prefs = online_preset
                except Exception:
                    pass
            
            self._current_enabled_tracks = prefs.get("enabled_tracks", None)
            
            # 讀取 wrap_octave 與 chord_threshold，若無偏好則根據是否為轉錄檔案自動判斷
            is_transcribed = filename.endswith("_transcribed.mid")
            self._current_wrap_octave = prefs.get("wrap_octave", not is_transcribed)
            self._current_chord_threshold = prefs.get("chord_threshold", 0.020 if is_transcribed else 0.005)
            self._current_melody_only = prefs.get("melody_only", is_transcribed)
            
            # 若無偏好設定，自動計算最佳基礎音高
            best_pitch = prefs.get("pitch_shift", None)
            if best_pitch is None:
                best_pitch = analyze_best_pitch_shift(filepath, self._current_enabled_tracks)
            
            # 靜默重設微調器
            self._pitch_spin.blockSignals(True)
            self._pitch_spin.setValue(best_pitch)
            self._pitch_spin.blockSignals(False)
            
            self._speed_spin.blockSignals(True)
            self._speed_spin.setValue(prefs.get("speed_multiplier", 1.0))
            self._speed_spin.blockSignals(False)
            
            self._dynamic_shift_cb.blockSignals(True)
            self._dynamic_shift_cb.setChecked(prefs.get("dynamic_shift", False))
            self._dynamic_shift_cb.blockSignals(False)
            
            self._velocity_cb.blockSignals(True)
            self._velocity_cb.setChecked(prefs.get("velocity_dynamics", True))
            self._velocity_cb.blockSignals(False)
            
            self._load_current_track()

    @pyqtSlot(int)
    def _on_instrument_changed(self, index: int) -> None:
        """切換樂器模式。"""
        mode = "lyre" if index == 0 else "horn"
        self._player.set_instrument_mode(mode)

    # ═══════════════════ 播放控制 ═══════════════════

    @pyqtSlot()
    def _toggle_play_pause(self) -> None:
        """切換播放/暫停。"""
        if self._current_midi is None:
            return

        if self._player.is_stopped:
            # 重新開始播放
            self._player.set_midi_data(self._current_midi)
            self._player.play()
            self._play_btn.setText("⏸  暫停")
            self._status_label.setText("播放中...")
        elif self._player.is_playing:
            self._player.pause()
            self._play_btn.setText("▶  播放")
            self._status_label.setText("已暫停")
        else:
            self._player.toggle_play_pause()
            self._play_btn.setText("⏸  暫停")
            self._status_label.setText("播放中...")

    @pyqtSlot()
    def _next_track(self) -> None:
        """切換到下一首。"""
        if not self._midi_files:
            return
        new_index = (self._current_index + 1) % len(self._midi_files)
        self._track_combo.setCurrentIndex(new_index)

    @pyqtSlot()
    def _prev_track(self) -> None:
        """切換到上一首。"""
        if not self._midi_files:
            return
        new_index = (self._current_index - 1) % len(self._midi_files)
        self._track_combo.setCurrentIndex(new_index)

    @pyqtSlot()
    def _force_stop(self) -> None:
        """強制停止播放。"""
        self._player.stop()
        if self._player.isRunning():
            self._player.wait(2000)  # 等待執行緒結束，最多 2 秒
        self._play_btn.setText("▶  播放")
        self._status_label.setText("已停止")
        self._note_display.setText("--")
        self._progress_bar.setValue(0)

    # ═══════════════════ 信號槽 ═══════════════════

    @pyqtSlot(str)
    def _on_state_changed(self, state: str) -> None:
        """播放狀態變更回調。"""
        state_text = {
            PlaybackState.PLAYING: "播放中...",
            PlaybackState.PAUSED: "已暫停",
            PlaybackState.STOPPED: "已停止",
            PlaybackState.IDLE: "就緒",
        }
        self._status_label.setText(state_text.get(state, state))

        if state == PlaybackState.PLAYING:
            self._play_btn.setText("⏸  暫停")
        else:
            self._play_btn.setText("▶  播放")

    @pyqtSlot(int, int)
    def _on_progress_updated(self, current: int, total: int) -> None:
        """播放進度更新回調。"""
        if total > 0:
            percent = int((current / total) * 100)
            self._progress_bar.setValue(percent)
            self._progress_label.setText(f"{current} / {total}")

    @pyqtSlot(str)
    def _on_note_played(self, key_str: str) -> None:
        """音符播放回調。"""
        self._note_display.setText(key_str)

    @pyqtSlot()
    def _on_playback_finished(self) -> None:
        """播放結束回調。"""
        self._play_btn.setText("▶  播放")
        self._status_label.setText("播放完畢")
        self._note_display.setText("✓")

    @pyqtSlot(str)
    def _on_error(self, msg: str) -> None:
        """錯誤回調。"""
        self._status_label.setText(f"⚠ {msg[:30]}")

    # ═══════════════════ 設定對話框 ═══════════════════

    def _open_settings(self) -> None:
        """開啟快捷鍵設定對話框。"""
        dialog = SettingsDialog(self._config, self)
        if dialog.exec_() == QDialog.Accepted:
            # 重新註冊快捷鍵
            self._hotkey_manager.register(self._config.hotkeys)
            self._status_label.setText("快捷鍵已更新")

    # ═══════════════════ 視窗拖曳 ═══════════════════

    def _get_resize_direction(self, pos) -> str | None:
        w = self.width()
        h = self.height()
        b = self._border_width
        x = pos.x()
        y = pos.y()
        
        left = x < b
        right = x > w - b
        top = y < b
        bottom = y > h - b
        
        if left and top: return 'TL'
        if right and top: return 'TR'
        if left and bottom: return 'BL'
        if right and bottom: return 'BR'
        if left: return 'L'
        if right: return 'R'
        if top: return 'T'
        if bottom: return 'B'
        return None

    def mousePressEvent(self, event) -> None:
        """記錄滑鼠按下位置，辨識是拖曳視窗還是拉伸縮放。"""
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            dir_ = self._get_resize_direction(pos)
            if dir_:
                self._resize_dir = dir_
                self._press_global_pos = event.globalPos()
                self._press_geometry = self.geometry()
            else:
                self._resize_dir = None
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """處理滑鼠懸停光標更新與拖曳/縮放拉伸。"""
        pos = event.pos()
        
        # 1. 處理滑鼠左鍵按下的拖曳/縮放狀態
        if event.buttons() == Qt.LeftButton:
            if self._resize_dir:
                delta = event.globalPos() - self._press_global_pos
                rect = self.geometry()
                min_w = 420
                min_h = 500
                
                new_left = rect.left()
                new_top = rect.top()
                new_width = rect.width()
                new_height = rect.height()
                
                if 'L' in self._resize_dir:
                    proposed_left = self._press_geometry.left() + delta.x()
                    proposed_width = self._press_geometry.width() - delta.x()
                    if proposed_width >= min_w:
                        new_left = proposed_left
                        new_width = proposed_width
                if 'R' in self._resize_dir:
                    proposed_width = self._press_geometry.width() + delta.x()
                    if proposed_width >= min_w:
                        new_width = proposed_width
                if 'T' in self._resize_dir:
                    proposed_top = self._press_geometry.top() + delta.y()
                    height_diff = self._press_geometry.height() - delta.y()
                    if height_diff >= min_h:
                        new_top = proposed_top
                        new_height = height_diff
                if 'B' in self._resize_dir:
                    proposed_height = self._press_geometry.height() + delta.y()
                    if proposed_height >= min_h:
                        new_height = proposed_height
                        
                self.setGeometry(new_left, new_top, new_width, new_height)
                event.accept()
                return
            elif self._drag_pos is not None:
                self.move(event.globalPos() - self._drag_pos)
                event.accept()
                return
                
        # 2. 未按下按鍵時，根據懸停位置更新滑鼠指標圖示
        dir_ = self._get_resize_direction(pos)
        if dir_ in ('TL', 'BR'):
            self.setCursor(Qt.SizeFDiagCursor)
        elif dir_ in ('TR', 'BL'):
            self.setCursor(Qt.SizeBDiagCursor)
        elif dir_ in ('L', 'R'):
            self.setCursor(Qt.SizeHorCursor)
        elif dir_ in ('T', 'B'):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:
        """釋放拖曳或縮放。"""
        self._drag_pos = None
        self._resize_dir = None
        self.setCursor(Qt.ArrowCursor)
        event.accept()

    # ═══════════════════ 關閉處理 ═══════════════════

    def _on_close(self) -> None:
        """關閉視窗前的清理工作。"""
        self._force_stop()
        self._hotkey_manager.unregister_all()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        """視窗關閉事件。"""
        self._on_close()
        event.accept()

    def _show_update_dialog(self, latest_version: str, release_url: str, release_notes: str) -> None:
        """顯示更新提示對話框。"""
        from PyQt5.QtWidgets import QMessageBox
        import webbrowser
        
        # 建立自定義風格的對話框
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("🔔 發現新版本！")
        msg_box.setText(f"<b>有新版本 {latest_version} 可用！</b><br><br>目前版本: {APP_VERSION}<br><br>更新說明:<br>{release_notes if release_notes else '無詳細說明'}")
        msg_box.setInformativeText("是否前往下載最新安裝包？")
        
        # 自定義按鈕
        yes_btn = msg_box.addButton("💾 前往下載", QMessageBox.YesRole)
        no_btn = msg_box.addButton("下次再說", QMessageBox.NoRole)
        msg_box.setDefaultButton(yes_btn)
        
        # 套用樣式
        msg_box.setStyleSheet(
            "QMessageBox { background-color: #0a0d3a; color: #ffffff; }"
            "QLabel { color: #ffffff; font-size: 12px; }"
            "QPushButton { background-color: #1e2353; color: #ffffff; border: 1px solid rgba(88,101,242,40); border-radius: 12px; padding: 6px 16px; font-size: 12px; font-weight: bold; }"
            "QPushButton:hover { background-color: #5865f2; border-color: #5865f2; }"
        )
        
        msg_box.exec_()
        
        if msg_box.clickedButton() == yes_btn:
            webbrowser.open(release_url)
