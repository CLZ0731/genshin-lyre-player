"""
懸浮視窗 UI 模組

無邊框、永遠置頂的控制面板，支援滑鼠拖曳、播放控制與快捷鍵設定。
"""

import os

from PyQt5.QtCore import Qt, QPoint, pyqtSlot
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QDialog, QLineEdit,
    QFormLayout, QApplication, QComboBox, QFileDialog,
    QCheckBox, QScrollArea, QDialogButtonBox,
    QSpinBox, QDoubleSpinBox
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
        header.setStyleSheet("color: #A0A0B0; font-size: 11px; padding: 2px;")
        layout.addWidget(header)

        # Skyline 主旋律提取核取方塊
        self._melody_only_cb = QCheckBox("🎵 啟用 Skyline 主旋律提取（自動過濾伴奏與低音）")
        self._melody_only_cb.setChecked(melody_only)
        self._melody_only_cb.setStyleSheet(
            "color: #D4C080; font-size: 12px; font-weight: bold; padding: 6px; "
            "border-bottom: 1px solid #3E3E48; margin-bottom: 6px;"
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
            cb.setStyleSheet("color: #E8E8F0; font-size: 12px; padding: 3px;")
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
            "color: #D4C080; font-size: 14px; font-weight: bold; "
            "font-family: 'Segoe UI', 'Microsoft YaHei UI';"
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
            "background-color: #2E2E38; color: #E8E8F0; border: 1px solid #4E4E5A; "
            "border-radius: 4px; padding: 2px 4px; font-size: 12px;"
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
        self.setFixedSize(420, 290)

        # ── 拖曳狀態 ──
        self._drag_pos: QPoint | None = None

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

    # ═══════════════════ UI 初始化 ═══════════════════

    def _init_ui(self) -> None:
        """建構介面佈局。"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 10)
        main_layout.setSpacing(6)

        # ── 標題列 ──
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(28)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        self._title_label = QLabel("🎵 原神詩琴助手")
        self._title_label.setObjectName("TitleLabel")
        title_layout.addWidget(self._title_label)

        title_layout.addStretch()

        # 設定按鈕
        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("WinBtn")
        settings_btn.setToolTip("快捷鍵設定")
        settings_btn.clicked.connect(self._open_settings)
        title_layout.addWidget(settings_btn)

        # 最小化按鈕
        min_btn = QPushButton("─")
        min_btn.setObjectName("WinBtn")
        min_btn.setToolTip("最小化")
        min_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_btn)

        # 關閉按鈕
        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.setToolTip("關閉")
        close_btn.clicked.connect(self._on_close)
        title_layout.addWidget(close_btn)

        main_layout.addWidget(title_bar)

        # ── 曲目資訊區 ──
        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)

        track_row = QHBoxLayout()
        self._track_combo = QComboBox()
        self._track_combo.setObjectName("TrackCombo")
        self._track_combo.setToolTip("選擇曲目")
        self._track_combo.currentIndexChanged.connect(self._on_track_changed)
        track_row.addWidget(self._track_combo, stretch=1)

        self._add_midi_btn = QPushButton("➕")
        self._add_midi_btn.setObjectName("WinBtn")
        self._add_midi_btn.setToolTip("匯入 MIDI 檔案")
        self._add_midi_btn.setFixedWidth(28)
        self._add_midi_btn.clicked.connect(self._import_midi)
        track_row.addWidget(self._add_midi_btn)

        self._audio_transcribe_btn = QPushButton("🎙️")
        self._audio_transcribe_btn.setObjectName("WinBtn")
        self._audio_transcribe_btn.setToolTip("AI 音訊轉錄 MIDI")
        self._audio_transcribe_btn.setFixedWidth(28)
        self._audio_transcribe_btn.clicked.connect(self._transcribe_audio)
        track_row.addWidget(self._audio_transcribe_btn)

        info_layout.addLayout(track_row)

        # BPM + 狀態行 + 樂器切換
        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        self._instrument_combo = QComboBox()
        self._instrument_combo.addItems(["樂器: 詩琴 (短音)", "樂器: 圓號 (長音)"])
        self._instrument_combo.currentIndexChanged.connect(self._on_instrument_changed)
        info_row.addWidget(self._instrument_combo)

        self._track_btn = QPushButton("🎛️ 音軌設定")
        self._track_btn.setObjectName("WinBtn")
        self._track_btn.setToolTip("過濾伴奏與雜音")
        self._track_btn.clicked.connect(self._open_track_settings)
        info_row.addWidget(self._track_btn)

        self._bpm_label = QLabel("BPM: --")
        self._bpm_label.setObjectName("BpmLabel")
        info_row.addWidget(self._bpm_label)

        self._status_label = QLabel("就緒")
        self._status_label.setObjectName("StatusLabel")
        info_row.addWidget(self._status_label)

        info_row.addStretch()

        self._note_display = QLabel("--")
        self._note_display.setObjectName("NoteDisplay")
        info_row.addWidget(self._note_display)

        info_layout.addLayout(info_row)

        # ── 播放控制微調區 ──
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        shift_label = QLabel("升降調:")
        shift_label.setStyleSheet("color: #E8E8F0; font-size: 12px;")
        controls_row.addWidget(shift_label)

        self._pitch_spin = QSpinBox()
        self._pitch_spin.setRange(-12, 12)
        self._pitch_spin.setValue(0)
        self._pitch_spin.setToolTip("手動調整音高 (半音)")
        self._pitch_spin.valueChanged.connect(self._on_settings_changed)
        controls_row.addWidget(self._pitch_spin)

        speed_label = QLabel("速度:")
        speed_label.setStyleSheet("color: #E8E8F0; font-size: 12px;")
        controls_row.addWidget(speed_label)

        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.5, 2.0)
        self._speed_spin.setSingleStep(0.1)
        self._speed_spin.setValue(1.0)
        self._speed_spin.setToolTip("播放速度倍率")
        self._speed_spin.valueChanged.connect(self._on_settings_changed)
        controls_row.addWidget(self._speed_spin)

        self._dynamic_shift_cb = QCheckBox("智能變調")
        self._dynamic_shift_cb.setStyleSheet("color: #E8E8F0; font-size: 12px;")
        self._dynamic_shift_cb.setToolTip("播放中自動偵測變調並平移音階")
        self._dynamic_shift_cb.stateChanged.connect(self._on_settings_changed)
        controls_row.addWidget(self._dynamic_shift_cb)

        self._velocity_cb = QCheckBox("力度演奏")
        self._velocity_cb.setStyleSheet("color: #E8E8F0; font-size: 12px;")
        self._velocity_cb.setToolTip("根據音符力度動態調整按壓時長")
        self._velocity_cb.setChecked(True)
        self._velocity_cb.stateChanged.connect(self._on_velocity_changed)
        controls_row.addWidget(self._velocity_cb)

        controls_row.addStretch()
        info_layout.addLayout(controls_row)

        main_layout.addLayout(info_layout)

        # ── 進度條 ──
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        main_layout.addWidget(self._progress_bar)

        # 進度文字
        self._progress_label = QLabel("0 / 0")
        self._progress_label.setObjectName("ProgressLabel")
        self._progress_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self._progress_label)

        # ── 控制按鈕列 ──
        control_layout = QHBoxLayout()
        control_layout.setSpacing(6)
        control_layout.setContentsMargins(0, 4, 0, 0)

        self._prev_btn = QPushButton("⏮")
        self._prev_btn.setObjectName("ControlBtn")
        self._prev_btn.setToolTip("上一首 (F7)")
        self._prev_btn.clicked.connect(self._prev_track)
        control_layout.addWidget(self._prev_btn)

        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("PlayBtn")
        self._play_btn.setToolTip("播放/暫停 (F8)")
        self._play_btn.clicked.connect(self._toggle_play_pause)
        control_layout.addWidget(self._play_btn)

        self._next_btn = QPushButton("⏭")
        self._next_btn.setObjectName("ControlBtn")
        self._next_btn.setToolTip("下一首 (F9)")
        self._next_btn.clicked.connect(self._next_track)
        control_layout.addWidget(self._next_btn)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setObjectName("ControlBtn")
        self._stop_btn.setToolTip("停止 (F12)")
        self._stop_btn.clicked.connect(self._force_stop)
        control_layout.addWidget(self._stop_btn)

        # 重新整理曲目列表
        self._refresh_btn = QPushButton("🔄")
        self._refresh_btn.setObjectName("ControlBtn")
        self._refresh_btn.setToolTip("重新掃描 MIDI 資料夾")
        self._refresh_btn.clicked.connect(self._refresh_playlist)
        control_layout.addWidget(self._refresh_btn)

        main_layout.addLayout(control_layout)

    def _apply_styles(self) -> None:
        """套用 QSS 樣式表。"""
        self.setStyleSheet(MAIN_STYLESHEET)

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
            self._play_btn.setText("▶")

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
            self._play_btn.setText("⏸")
            self._status_label.setText("播放中...")
        elif self._player.is_playing:
            self._player.pause()
            self._play_btn.setText("▶")
            self._status_label.setText("已暫停")
        else:
            self._player.toggle_play_pause()
            self._play_btn.setText("⏸")
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
        self._play_btn.setText("▶")
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
            self._play_btn.setText("⏸")
        else:
            self._play_btn.setText("▶")

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
        self._play_btn.setText("▶")
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

    def mousePressEvent(self, event) -> None:
        """記錄滑鼠按下位置（用於拖曳）。"""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """拖曳移動視窗。"""
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        """釋放拖曳。"""
        self._drag_pos = None

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
