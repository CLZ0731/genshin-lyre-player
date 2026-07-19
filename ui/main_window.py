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
    QSpinBox, QDoubleSpinBox, QFrame, QGroupBox, QRadioButton, QGridLayout
)
from PyQt5.QtGui import QColor, QFont, QPainter, QBrush, QPen, QPainterPath, QIcon
import shutil
import os

from core.midi_parser import parse_midi, scan_midi_folder, ParsedMidi, MidiTrackInfo, analyze_best_pitch_shift
from core.player import PlayerThread, PlaybackState
from core.audio_converter import AudioConverterThread
from utils.config_manager import ConfigManager
from utils.hotkey_manager import HotkeyManager
from utils.online_presets import fetch_online_presets, lookup_preset, export_preset
from ui.styles import MAIN_STYLESHEET
from ui.icons import IconFactory

from core.version import __version__ as APP_VERSION

class UpdateCheckerThread(QThread):
    """
    背景執行緒，自動向 GitHub API 查詢最新發布的 Release 版本。
    """
    update_available = pyqtSignal(str, str, str, str)  # 訊號傳遞：(新版本號, 下載網址, 更新說明, MSI直鏈)

    def __init__(self, current_version: str, parent=None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self) -> None:
        try:
            import urllib.request
            import json
            import re
            import ssl
            
            url = "https://api.github.com/repos/CLZ0731/genshin-lyre-player/releases/latest"
            req = urllib.request.Request(
                url, 
                headers={
                    "User-Agent": "GenshinLyrePlayer-Updater",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            
            # 忽略虛擬機可能缺乏最新根憑證導致的 SSL 錯誤
            ssl_context = ssl._create_unverified_context()
            
            # 設定 5 秒超時，防止無網路時阻塞
            with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    tag_name = data.get("tag_name", "").strip()
                    
                    # 使用正則表達式提取純數字版本號 (例如: "GenshinLyrePlayer-1.0.1" -> "1.0.1", "v1.0.2" -> "1.0.2")
                    version_match = re.search(r'\d+(\.\d+)+', tag_name)
                    latest_version = version_match.group(0) if version_match else tag_name
                    
                    release_url = data.get("html_url", "")
                    release_notes = data.get("body", "")
                    
                    # 尋找 ZIP 下載連結
                    download_url = ""
                    for asset in data.get("assets", []):
                        if asset.get("name", "").endswith(".zip"):
                            download_url = asset.get("browser_download_url", "")
                            break
                    
                    if latest_version and self.is_newer(latest_version, self.current_version):
                        self.update_available.emit(latest_version, release_url, release_notes, download_url)
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


class UpdateDownloaderThread(QThread):
    """背景下載更新檔的執行緒"""
    progress = pyqtSignal(int, int)  # (已下載, 總大小)
    finished_download = pyqtSignal(str) # 下載完成的檔案路徑
    error = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self) -> None:
        try:
            import urllib.request
            import tempfile
            import os
            import ssl
            
            ssl_context = ssl._create_unverified_context()
            req = urllib.request.Request(self.url, headers={"User-Agent": "GenshinLyrePlayer-Updater"})
            
            with urllib.request.urlopen(req, context=ssl_context) as response:
                total_size = int(response.info().get("Content-Length", 0))
                
                # 建立暫存檔
                fd, temp_path = tempfile.mkstemp(suffix=".zip", prefix="GenshinLyrePlayer_Update_")
                
                with os.fdopen(fd, 'wb') as out_file:
                    downloaded = 0
                    chunk_size = 8192
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total_size)
                
                self.finished_download.emit(temp_path)
        except Exception as e:
            self.error.emit(str(e))


class UpdateProgressDialog(QDialog):
    """顯示下載進度的對話框"""
    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下載更新中...")
        self.setFixedSize(350, 120)
        self.setStyleSheet(
            "QDialog { background-color: #0a0d3a; color: #ffffff; }"
            "QLabel { color: #ffffff; font-size: 13px; font-weight: bold; }"
            "QProgressBar { border: 1px solid rgba(88,101,242,40); border-radius: 6px; background-color: #1e2353; text-align: center; color: white; }"
            "QProgressBar::chunk { background-color: #5865f2; border-radius: 6px; }"
        )
        
        layout = QVBoxLayout(self)
        self.status_label = QLabel("正在連線...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        self.downloader = UpdateDownloaderThread(url, self)
        self.downloader.progress.connect(self._on_progress)
        self.downloader.finished_download.connect(self._on_finished)
        self.downloader.error.connect(self._on_error)
        self.downloader.start()
        
    @pyqtSlot(int, int)
    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.progress_bar.setValue(percent)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.status_label.setText(f"下載中... {mb_downloaded:.1f} MB / {mb_total:.1f} MB")
        else:
            self.status_label.setText(f"下載中... {downloaded / (1024 * 1024):.1f} MB")
            
    @pyqtSlot(str)
    def _on_finished(self, temp_path: str) -> None:
        self.status_label.setText("下載完成！準備安裝...")
        import os
        import sys
        import tempfile
        import zipfile
        import subprocess
        from PyQt5.QtWidgets import QApplication
        
        # 解壓縮到暫存資料夾
        extract_dir = tempfile.mkdtemp(prefix="GenshinLyrePlayer_Update_Extract_")
        try:
            with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except Exception as e:
            self._on_error(f"解壓縮失敗: {e}")
            return
            
        current_app_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 產生更新用的暫存批次檔
        bat_content = f"""@echo off
echo 正在等待主程式關閉...
:wait_loop
tasklist /FI "IMAGENAME eq GenshinLyrePlayer.exe" 2>NUL | find /I /N "GenshinLyrePlayer.exe" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

echo 正在替換新版本檔案...
xcopy /E /Y /Q /R /H "{extract_dir}\\*" "{current_app_dir}\\"
echo 正在重新啟動應用程式...
start "" "{current_app_dir}\\GenshinLyrePlayer.exe"
echo 清理暫存檔案...
rmdir /S /Q "{extract_dir}"
del "{temp_path}"
del "%~f0"
"""
        bat_path = os.path.join(tempfile.gettempdir(), "genshin_lyre_update.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
            
        # 在背景無痕執行批次檔
        # CREATE_NO_WINDOW (0x08000000) 用來隱藏 cmd 視窗
        subprocess.Popen([bat_path], creationflags=0x08000000)
        
        # 關閉主程式
        QApplication.quit()
        
    @pyqtSlot(str)
    def _on_error(self, err_msg: str) -> None:
        self.status_label.setText("下載失敗！")
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.critical(self, "錯誤", f"下載更新時發生錯誤:\n{err_msg}")
        self.reject()


class TrackSelectionDialog(QDialog):
    """音軌選擇視窗"""
    def __init__(self, tracks_info: list[MidiTrackInfo], enabled_tracks: list[int] | None = None, melody_only: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("音軌過濾設定")
        self.setFixedSize(420, 480)
        self.setStyleSheet(MAIN_STYLESHEET)
        
        layout = QVBoxLayout(self)
        
        # 標題說明
        header = QLabel("★ = 適配原神程度（越多星越適合）")
        header.setStyleSheet("color: #5e5e5e; font-size: 11px; padding: 2px;")
        layout.addWidget(header)

        # Skyline 主旋律提取核取方塊
        self._melody_only_cb = QCheckBox("啟用 Skyline 主旋律提取（自動過濾伴奏與低音）")
        self._melody_only_cb.setChecked(melody_only)
        self._melody_only_cb.setStyleSheet(
            "color: #000000; font-size: 12px; font-weight: bold; padding: 6px; "
            "border-bottom: 1px solid #e2e2e2; margin-bottom: 6px;"
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
            cb.setStyleSheet("color: #000000; font-size: 12px; padding: 3px;")
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


class NetworkDuetDialog(QDialog):
    """網路雙人聯彈設定對話框"""
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("網路雙人聯彈設定")
        self.setFixedSize(400, 415)
        self.setStyleSheet(MAIN_STYLESHEET)
        
        # 保存主視窗參考以更新播放音域
        self.main_window = parent

        layout = QVBoxLayout(self)

        # 角色選擇 (主控端 / 被控端)
        mode_group = QGroupBox("選擇連線角色")
        mode_group.setStyleSheet("QGroupBox { color: #000000; font-weight: bold; }")
        mode_layout = QHBoxLayout(mode_group)
        
        self.slave_radio = QRadioButton("我是被控端 (播放琴音)")
        self.master_radio = QRadioButton("我是主控端 (載入樂譜)")
        
        mode_layout.addWidget(self.slave_radio)
        mode_layout.addWidget(self.master_radio)
        layout.addWidget(mode_group)

        # 動態內容區域
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 5, 0, 5)
        layout.addWidget(self.content_widget)

        # 底部按鈕
        self.btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        self.btn_box.rejected.connect(self.reject)
        layout.addWidget(self.btn_box)

        # 信號綁定
        self.slave_radio.toggled.connect(self._on_mode_changed)
        self.master_radio.toggled.connect(self._on_mode_changed)

        # 綁定網路管理器信號，即時更新連線狀態
        self.manager.status_changed.connect(self._update_status)
        self.manager.error_occurred.connect(self._show_error)

        # 初始化連線狀態
        if self.manager.is_connected:
            if self.manager.is_master:
                self.master_radio.setChecked(True)
            else:
                self.slave_radio.setChecked(True)
        else:
            self.slave_radio.setChecked(True)

    def _clear_content_layout(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _on_mode_changed(self):
        self._clear_content_layout()
        if self.slave_radio.isChecked():
            self._setup_slave_ui()
        else:
            self._setup_master_ui()

    def _setup_slave_ui(self):
        from core.network_sync import get_local_ip, ip_to_code
        local_ip = get_local_ip()
        pairing_code = ip_to_code(local_ip)
        
        code_label = QLabel("您的被控配對碼：")
        code_label.setStyleSheet("color: #555555; font-size: 13px; font-weight: bold;")
        self.content_layout.addWidget(code_label)
        
        self.code_display = QLineEdit(pairing_code)
        self.code_display.setReadOnly(True)
        self.code_display.setAlignment(Qt.AlignCenter)
        self.code_display.setStyleSheet(
            "QLineEdit { font-size: 22px; font-weight: bold; color: #5865f2; "
            "background-color: #f3f3f3; border: 2px solid #5865f2; border-radius: 8px; padding: 4px; }"
        )
        self.content_layout.addWidget(self.code_display)
        
        self.status_label = QLabel("等待主控端連線...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #222222; font-size: 13px; font-weight: bold; margin-top: 10px;")
        self.content_layout.addWidget(self.status_label)
        
        self.action_btn = QPushButton("開始等待連線")
        self.action_btn.setStyleSheet(
            "QPushButton { background-color: #5865f2; color: white; border-radius: 8px; padding: 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #4752c4; }"
        )
        self.action_btn.clicked.connect(self._start_slave_server)
        self.content_layout.addWidget(self.action_btn)
        
        # 若已連線，顯示已連線狀態
        if self.manager.is_connected and not self.manager.is_master:
            self.action_btn.setText("斷開連線")
            self.action_btn.clicked.disconnect()
            self.action_btn.clicked.connect(self._disconnect_network)
            self.status_label.setText("已連線至主控端")

    def _start_slave_server(self):
        self.manager.start_host_mode()
        self.action_btn.setText("斷開連線")
        self.action_btn.clicked.disconnect()
        self.action_btn.clicked.connect(self._disconnect_network)

    def _setup_master_ui(self):
        code_label = QLabel("請輸入被控端的配對碼：")
        code_label.setStyleSheet("color: #555555; font-size: 13px; font-weight: bold;")
        self.content_layout.addWidget(code_label)
        
        self.code_input = QLineEdit()
        self.code_input.setAlignment(Qt.AlignCenter)
        self.code_input.setPlaceholderText("請輸入 6 ~ 7 碼英文數字配對碼")
        self.code_input.setStyleSheet(
            "QLineEdit { font-size: 16px; color: #000000; "
            "border: 1px solid #cccccc; border-radius: 8px; padding: 4px; }"
        )
        self.content_layout.addWidget(self.code_input)
        
        self.status_label = QLabel("請輸入配對碼並點選連線")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #222222; font-size: 13px; font-weight: bold; margin-top: 5px;")
        self.content_layout.addWidget(self.status_label)
        
        self.action_btn = QPushButton("連線")
        self.action_btn.setStyleSheet(
            "QPushButton { background-color: #5865f2; color: white; border-radius: 8px; padding: 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #4752c4; }"
        )
        self.action_btn.clicked.connect(self._connect_to_slave)
        self.content_layout.addWidget(self.action_btn)
        
        # 音域配置群組
        config_group = QGroupBox("雙人合奏音域分配")
        config_group.setStyleSheet("QGroupBox { color: #000000; font-weight: bold; }")
        config_layout = QGridLayout(config_group)
        
        config_layout.addWidget(QLabel("主控本地彈奏:"), 0, 0)
        self.local_low = QCheckBox("低音")
        self.local_mid = QCheckBox("中音")
        self.local_high = QCheckBox("高音")
        config_layout.addWidget(self.local_low, 0, 1)
        config_layout.addWidget(self.local_mid, 0, 2)
        config_layout.addWidget(self.local_high, 0, 3)
        
        config_layout.addWidget(QLabel("被控遠端彈奏:"), 1, 0)
        self.remote_low = QCheckBox("低音")
        self.remote_mid = QCheckBox("中音")
        self.remote_high = QCheckBox("高音")
        config_layout.addWidget(self.remote_low, 1, 1)
        config_layout.addWidget(self.remote_mid, 1, 2)
        config_layout.addWidget(self.remote_high, 1, 3)

        config_layout.addWidget(QLabel("被控端樂器:"), 2, 0)
        self.remote_inst_combo = QComboBox()
        self.remote_inst_combo.addItems(["跟隨被控端設定", "強制詩琴 (短音)", "強制圓號 (長音)"])
        override_map = {"follow": 0, "lyre": 1, "horn": 2}
        self.remote_inst_combo.setCurrentIndex(override_map.get(self.main_window._remote_instrument_override, 0))
        self.remote_inst_combo.currentIndexChanged.connect(self._on_remote_inst_changed)
        config_layout.addWidget(self.remote_inst_combo, 2, 1, 1, 3)
        
        # 載入目前的音域配置
        self.local_low.setChecked('low' in self.main_window._local_play_ranges)
        self.local_mid.setChecked('mid' in self.main_window._local_play_ranges)
        self.local_high.setChecked('high' in self.main_window._local_play_ranges)
        
        self.remote_low.setChecked('low' in self.main_window._remote_play_ranges)
        self.remote_mid.setChecked('mid' in self.main_window._remote_play_ranges)
        self.remote_high.setChecked('high' in self.main_window._remote_play_ranges)
        
        # 綁定狀態改變
        self.local_low.toggled.connect(self._update_ranges)
        self.local_mid.toggled.connect(self._update_ranges)
        self.local_high.toggled.connect(self._update_ranges)
        self.remote_low.toggled.connect(self._update_ranges)
        self.remote_mid.toggled.connect(self._update_ranges)
        self.remote_high.toggled.connect(self._update_ranges)

        self.content_layout.addWidget(config_group)
        
        # 若已連線，顯示已連線狀態
        if self.manager.is_connected and self.manager.is_master:
            self.action_btn.setText("斷開連線")
            self.action_btn.clicked.disconnect()
            self.action_btn.clicked.connect(self._disconnect_network)
            self.status_label.setText("已連線至被控端")

    def _connect_to_slave(self):
        code = self.code_input.text().strip()
        if not code:
            return
        self.manager.connect_as_master(code)
        
    def _disconnect_network(self):
        self.manager.disconnect_all()
        self._on_mode_changed()

    def _update_status(self, text: str):
        if hasattr(self, 'status_label'):
            self.status_label.setText(text)
        if "已連線" in text or "已連接" in text:
            self.action_btn.setText("斷開連線")
            try:
                self.action_btn.clicked.disconnect()
            except Exception:
                pass
            self.action_btn.clicked.connect(self._disconnect_network)
            
    def _show_error(self, err: str):
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(self, "聯彈錯誤", err)
        self._on_mode_changed()

    def _update_ranges(self):
        local = set()
        if self.local_low.isChecked(): local.add('low')
        if self.local_mid.isChecked(): local.add('mid')
        if self.local_high.isChecked(): local.add('high')
        
        remote = set()
        if self.remote_low.isChecked(): remote.add('low')
        if self.remote_mid.isChecked(): remote.add('mid')
        if self.remote_high.isChecked(): remote.add('high')
        
        self.main_window._local_play_ranges = local
        self.main_window._remote_play_ranges = remote
        
        # 若播放器執行中，即時同步音域
        if self.main_window._player.isRunning():
            self.main_window._player.set_playback_ranges(local, remote)

    def _on_remote_inst_changed(self, index: int):
        override_map = {0: "follow", 1: "lyre", 2: "horn"}
        val = override_map.get(index, "follow")
        self.main_window._remote_instrument_override = val
        self.main_window._player.set_remote_instrument_mode(val)


class SettingsDialog(QDialog):
    """快捷鍵與系統設定對話框。"""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self.setWindowTitle("系統設定")
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
        title = QLabel("系統設定")
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


        layout.addLayout(form)

        # 按鈕列
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        save_btn = QPushButton("儲存")
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
        self.setMinimumSize(440, 595)
        self.resize(480, 615)
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

        # ── 網路聯彈 ──
        from core.network_sync import NetworkSyncManager
        from core.player import SlaveKeyExecutor
        self._network_manager = NetworkSyncManager(self)
        self._slave_executor = SlaveKeyExecutor(self)
        self._slave_executor.start()
        
        # 預設演奏範圍：本地彈奏中高音，被控端彈奏低音
        self._local_play_ranges = {'mid', 'high'}
        self._remote_play_ranges = {'low'}
        self._remote_instrument_override = "follow"  # 預設被控端樂器跟隨被控端自己的設定

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

        # ── 重新整理目標視窗 ──
        self._refresh_genshin_windows()

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

        self._title_label = QLabel("風物之詩琴助手")
        self._title_label.setObjectName("TitleLabel")
        title_layout.addWidget(self._title_label)

        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setObjectName("VersionLabel")
        title_layout.addWidget(version_label)

        title_layout.addStretch()

        self._network_btn = QPushButton()
        self._network_btn.setObjectName("WinBtn")
        self._network_btn.setToolTip("網路雙人聯彈")
        self._network_btn.setIcon(IconFactory.create_icon("network", QColor(94, 94, 94)))
        self._network_btn.clicked.connect(self._open_network_duet)
        title_layout.addWidget(self._network_btn)

        settings_btn = QPushButton()
        settings_btn.setObjectName("WinBtn")
        settings_btn.setToolTip("快捷鍵設定")
        settings_btn.setIcon(IconFactory.create_icon("gear", QColor(94, 94, 94)))
        settings_btn.clicked.connect(self._open_settings)
        title_layout.addWidget(settings_btn)

        min_btn = QPushButton()
        min_btn.setObjectName("WinBtn")
        min_btn.setToolTip("最小化")
        min_btn.setIcon(IconFactory.create_icon("minimize", QColor(94, 94, 94)))
        min_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_btn)

        close_btn = QPushButton()
        close_btn.setObjectName("CloseBtn")
        close_btn.setToolTip("關閉")
        close_btn.setIcon(IconFactory.create_icon("close", QColor(94, 94, 94)))
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
        track_title = QLabel("曲目選擇")
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

        self._add_midi_btn = QPushButton()
        self._add_midi_btn.setObjectName("ToolBtn")
        self._add_midi_btn.setToolTip("匯入 MIDI 檔案")
        self._add_midi_btn.setIcon(IconFactory.create_icon("plus", QColor(0, 0, 0)))
        self._add_midi_btn.clicked.connect(self._import_midi)
        track_row.addWidget(self._add_midi_btn)

        self._audio_transcribe_btn = QPushButton()
        self._audio_transcribe_btn.setObjectName("ToolBtn")
        self._audio_transcribe_btn.setToolTip("AI 音訊轉錄 MIDI")
        self._audio_transcribe_btn.setIcon(IconFactory.create_icon("transcribe", QColor(0, 0, 0)))
        self._audio_transcribe_btn.clicked.connect(self._transcribe_audio)
        track_row.addWidget(self._audio_transcribe_btn)

        self._delete_midi_btn = QPushButton()
        self._delete_midi_btn.setObjectName("ToolBtn")
        self._delete_midi_btn.setToolTip("刪除選取的樂譜")
        self._delete_midi_btn.setIcon(IconFactory.create_icon("delete", QColor(0, 0, 0)))
        self._delete_midi_btn.clicked.connect(self._delete_current_midi)
        track_row.addWidget(self._delete_midi_btn)

        track_panel_layout.addLayout(track_row)

        # 資訊列：BPM + 狀態 + 樂器
        info_row = QHBoxLayout()
        info_row.setSpacing(6)

        self._instrument_combo = QComboBox()
        self._instrument_combo.addItems(["詩琴 (短音)", "圓號 (長音)"])
        self._instrument_combo.currentIndexChanged.connect(self._on_instrument_changed)
        info_row.addWidget(self._instrument_combo)

        self._track_btn = QPushButton("音軌設定")
        self._track_btn.setObjectName("ControlBtn")
        self._track_btn.setToolTip("過濾伴奏與雜音")
        self._track_btn.clicked.connect(self._open_track_settings)
        info_row.addWidget(self._track_btn)

        self._export_sheet_btn = QPushButton("匯出鍵盤譜")
        self._export_sheet_btn.setObjectName("ControlBtn")
        self._export_sheet_btn.setToolTip("將此曲轉換為易讀的鍵盤譜文字檔")
        self._export_sheet_btn.clicked.connect(self._export_keyboard_sheet)
        info_row.addWidget(self._export_sheet_btn)

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

        params_title = QLabel("演奏參數")
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

        self._auto_export_cb = QCheckBox("自動匯出鍵盤譜")
        self._auto_export_cb.setToolTip("播放完畢後，自動將本曲匯出為文字檔鍵盤譜 (.txt) 並開啟")
        self._auto_export_cb.setChecked(self._config.auto_export_sheet)
        self._auto_export_cb.stateChanged.connect(self._on_auto_export_changed)
        params_row2.addWidget(self._auto_export_cb)

        params_row2.addStretch()
        params_panel_layout.addLayout(params_row2)

        # 第三列：目標視窗 1
        params_row3 = QHBoxLayout()
        params_row3.setSpacing(8)

        target_label = QLabel("主控視窗")
        target_label.setObjectName("ParamLabel")
        target_label.setToolTip("第一目標遊戲視窗，通常是前景的 PC 版原神")
        params_row3.addWidget(target_label)

        self._target_hwnd_combo = QComboBox()
        self._target_hwnd_combo.setMinimumWidth(180)
        self._target_hwnd_combo.setToolTip("第一個遊戲視窗的控制代碼")
        self._target_hwnd_combo.currentIndexChanged.connect(self._on_target_hwnd_changed)
        params_row3.addWidget(self._target_hwnd_combo)

        # 重新整理按鈕
        self._refresh_windows_btn = QPushButton()
        self._refresh_windows_btn.setObjectName("ToolBtn")
        self._refresh_windows_btn.setToolTip("重新掃描原神與模擬器視窗")
        self._refresh_windows_btn.setIcon(IconFactory.create_icon("refresh", QColor(0, 0, 0)))
        self._refresh_windows_btn.clicked.connect(self._refresh_genshin_windows)
        params_row3.addWidget(self._refresh_windows_btn)

        params_row3.addSpacing(6)

        # 視窗 1 音域選擇
        self._w1_low_cb = QCheckBox("低")
        self._w1_low_cb.setChecked(True)
        self._w1_low_cb.setToolTip("主控視窗演奏低音區")
        self._w1_low_cb.stateChanged.connect(self._update_playback_ranges)
        params_row3.addWidget(self._w1_low_cb)

        self._w1_mid_cb = QCheckBox("中")
        self._w1_mid_cb.setChecked(True)
        self._w1_mid_cb.setToolTip("主控視窗演奏中音區")
        self._w1_mid_cb.stateChanged.connect(self._update_playback_ranges)
        params_row3.addWidget(self._w1_mid_cb)

        self._w1_high_cb = QCheckBox("高")
        self._w1_high_cb.setChecked(True)
        self._w1_high_cb.setToolTip("主控視窗演奏高音區")
        self._w1_high_cb.stateChanged.connect(self._update_playback_ranges)
        params_row3.addWidget(self._w1_high_cb)

        params_row3.addStretch()
        params_panel_layout.addLayout(params_row3)

        # 第四列：目標視窗 2 (協同/雙開伴奏)
        params_row4 = QHBoxLayout()
        params_row4.setSpacing(8)

        target2_label = QLabel("協同視窗")
        target2_label.setObjectName("ParamLabel")
        target2_label.setToolTip("第二目標遊戲視窗，通常是背景的手機版模擬器")
        params_row4.addWidget(target2_label)

        self._target_hwnd_combo2 = QComboBox()
        self._target_hwnd_combo2.setMinimumWidth(180)
        self._target_hwnd_combo2.setToolTip("第二個遊戲視窗的控制代碼，設為未設定則停用雙開同步模式")
        self._target_hwnd_combo2.currentIndexChanged.connect(self._on_target_hwnd2_changed)
        params_row4.addWidget(self._target_hwnd_combo2)

        # 為了排版對齊，放一個空白占位 spacer
        params_row4.addSpacing(34)

        # 視窗 2 音域選擇
        self._w2_low_cb = QCheckBox("低")
        self._w2_low_cb.setChecked(False)
        self._w2_low_cb.setToolTip("協同視窗演奏低音區")
        self._w2_low_cb.stateChanged.connect(self._update_playback_ranges)
        params_row4.addWidget(self._w2_low_cb)

        self._w2_mid_cb = QCheckBox("中")
        self._w2_mid_cb.setChecked(False)
        self._w2_mid_cb.setToolTip("協同視窗演奏中音區")
        self._w2_mid_cb.stateChanged.connect(self._update_playback_ranges)
        params_row4.addWidget(self._w2_mid_cb)

        self._w2_high_cb = QCheckBox("高")
        self._w2_high_cb.setChecked(False)
        self._w2_high_cb.setToolTip("協同視窗演奏高音區")
        self._w2_high_cb.stateChanged.connect(self._update_playback_ranges)
        params_row4.addWidget(self._w2_high_cb)

        params_row4.addStretch()
        params_panel_layout.addLayout(params_row4)

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

        self._prev_btn = QPushButton()
        self._prev_btn.setObjectName("IconBtn")
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setToolTip("上一首 (F7)")
        self._prev_btn.setIcon(IconFactory.create_icon("prev", QColor(0, 0, 0)))
        self._prev_btn.clicked.connect(self._prev_track)
        control_layout.addWidget(self._prev_btn)

        self._stop_btn = QPushButton()
        self._stop_btn.setObjectName("IconBtn")
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setToolTip("停止 (F12)")
        self._stop_btn.setIcon(IconFactory.create_icon("stop", QColor(0, 0, 0)))
        self._stop_btn.clicked.connect(self._force_stop)
        control_layout.addWidget(self._stop_btn)

        self._play_btn = QPushButton("  播放")
        self._play_btn.setObjectName("PlayBtn")
        self._play_btn.setToolTip("播放/暫停 (F8)")
        self._play_btn.setIcon(IconFactory.create_icon("play", QColor(255, 255, 255)))
        self._play_btn.clicked.connect(self._toggle_play_pause)
        control_layout.addWidget(self._play_btn)

        self._next_btn = QPushButton()
        self._next_btn.setObjectName("IconBtn")
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setToolTip("下一首 (F9)")
        self._next_btn.setIcon(IconFactory.create_icon("next", QColor(0, 0, 0)))
        self._next_btn.clicked.connect(self._next_track)
        control_layout.addWidget(self._next_btn)

        self._refresh_btn = QPushButton()
        self._refresh_btn.setObjectName("IconBtn")
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setToolTip("重新掃描 MIDI 資料夾")
        self._refresh_btn.setIcon(IconFactory.create_icon("refresh", QColor(0, 0, 0)))
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

        # Uber Move 淺灰色單色背景
        painter.fillPath(path, QBrush(QColor(243, 243, 243)))

        # 繪製 Uber Move 極細灰色外邊框
        painter.setPen(QPen(QColor(226, 226, 226), 1.0))
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

        # 網路聯彈信號
        self._network_manager.command_received.connect(self._slave_executor.queue_cmd)
        self._network_manager.command_received.connect(self._on_network_command_received)
        self._network_manager.connection_established.connect(self._on_connection_established)
        self._network_manager.disconnected.connect(self._on_disconnected)

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
            self._play_btn.setText("  播放")
            self._play_btn.setIcon(IconFactory.create_icon("play", QColor(255, 255, 255)))

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

    @pyqtSlot(int)
    def _on_auto_export_changed(self, state: int) -> None:
        """切換自動匯出狀態。"""
        self._config.auto_export_sheet = (state == Qt.Checked)

    @pyqtSlot()
    def _export_keyboard_sheet(self) -> None:
        """匯出當前歌曲的文字檔鍵盤譜。"""
        if not self._current_midi:
            self._status_label.setText("無可匯出的歌曲")
            return

        try:
            # 建立 exports 目錄
            import_dir = os.path.dirname(os.path.abspath(__file__))
            export_dir = os.path.abspath(os.path.join(import_dir, "..", "exports"))
            os.makedirs(export_dir, exist_ok=True)

            # 去除檔名中不合法的字元
            title = self._current_midi.title
            for c in r'\/:*?"<>|':
                title = title.replace(c, "_")

            filepath = os.path.join(export_dir, f"{title}_鍵盤譜.txt")

            # 生成鍵盤譜
            from core.midi_parser import export_keyboard_sheet_text
            sheet_content = export_keyboard_sheet_text(self._current_midi)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(sheet_content)

            print(f"[鍵盤譜匯出] 已成功匯出至 {filepath}")

            # 自動開啟檔案
            if os.path.exists(filepath):
                os.startfile(filepath)

            self._status_label.setText("鍵盤譜已匯出並開啟")
        except Exception as e:
            print(f"[鍵盤譜匯出] 失敗: {e}")
            self._status_label.setText("鍵盤譜匯出失敗")

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

        # 使用預設的中等 AI 轉錄過濾靈敏度
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
        self._auto_export_cb.setEnabled(enabled)
        self._instrument_combo.setEnabled(enabled)
        self._track_btn.setEnabled(enabled)
        self._export_sheet_btn.setEnabled(enabled)
        self._target_hwnd_combo.setEnabled(enabled)
        self._target_hwnd_combo2.setEnabled(enabled)
        self._refresh_windows_btn.setEnabled(enabled)
        self._w1_low_cb.setEnabled(enabled)
        self._w1_mid_cb.setEnabled(enabled)
        self._w1_high_cb.setEnabled(enabled)
        self._w2_low_cb.setEnabled(enabled)
        self._w2_mid_cb.setEnabled(enabled)
        self._w2_high_cb.setEnabled(enabled)

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

    def _refresh_genshin_windows(self) -> None:
        """掃描系統中的原神與模擬器視窗並填入下拉選單。"""
        from core.key_simulator import get_genshin_windows
        
        self._target_hwnd_combo.blockSignals(True)
        self._target_hwnd_combo.clear()
        self._target_hwnd_combo.addItem("活動視窗 (前景 / SendInput)", None)
        
        self._target_hwnd_combo2.blockSignals(True)
        self._target_hwnd_combo2.clear()
        self._target_hwnd_combo2.addItem("未設定 (停用雙開)", None)
        
        # 掃描視窗
        windows = get_genshin_windows()
        for hwnd, title in windows:
            self._target_hwnd_combo.addItem(title, hwnd)
            self._target_hwnd_combo2.addItem(title, hwnd)
            
        self._target_hwnd_combo.blockSignals(False)
        self._target_hwnd_combo2.blockSignals(False)
        
        self._target_hwnd_combo.setCurrentIndex(0)
        self._target_hwnd_combo2.setCurrentIndex(0)
        self._on_target_hwnd_changed(0)
        self._on_target_hwnd2_changed(0)

    @pyqtSlot(int)
    def _on_target_hwnd_changed(self, index: int) -> None:
        """當選取的主控遊戲視窗改變時。"""
        hwnd = self._target_hwnd_combo.currentData()
        if hwnd:
            # 獲取實際輸入視窗（若為模擬器會自動轉換為內部子視窗）
            from core.key_simulator import get_input_target_hwnd
            actual_hwnd = get_input_target_hwnd(hwnd)
            self._player.set_target_hwnd(actual_hwnd)
            self._slave_executor.set_target_hwnd(actual_hwnd)
            print(f"[主控視窗] 已切換至特定視窗 (HWND: {hwnd} -> 實際輸入 HWND: {actual_hwnd})，啟用背景模擬模式")
        else:
            self._player.set_target_hwnd(None)
            self._slave_executor.set_target_hwnd(None)
            print("[主控視窗] 已切換至活動視窗，使用傳統前景 SendInput 模式")
        self._update_playback_ranges()

    @pyqtSlot(int)
    def _on_target_hwnd2_changed(self, index: int) -> None:
        """當選取的協同遊戲視窗改變時。"""
        hwnd2 = self._target_hwnd_combo2.currentData()
        if hwnd2:
            # 獲取實際輸入視窗（若為模擬器會自動轉換為內部子視窗）
            from core.key_simulator import get_input_target_hwnd
            actual_hwnd2 = get_input_target_hwnd(hwnd2)
            self._player.set_target_hwnd2(actual_hwnd2)
            print(f"[協同視窗] 已切換至特定視窗 (HWND: {hwnd2} -> 實際輸入 HWND: {actual_hwnd2})，啟用雙開同步演奏")
        else:
            self._player.set_target_hwnd2(None)
            print("[協同視窗] 已設為未指定，關閉雙開同步演奏")
        self._update_playback_ranges()

    def _update_playback_ranges(self) -> None:
        """根據介面勾選的音域，更新播放器主/協同視窗的播放音域。"""
        # 由於這是一個防爆保護，未初始化時直接回傳
        if not hasattr(self, "_w1_low_cb"):
            return
            
        w1_ranges = set()
        if self._w1_low_cb.isChecked(): w1_ranges.add('low')
        if self._w1_mid_cb.isChecked(): w1_ranges.add('mid')
        if self._w1_high_cb.isChecked(): w1_ranges.add('high')
        
        w2_ranges = set()
        if self._w2_low_cb.isChecked(): w2_ranges.add('low')
        if self._w2_mid_cb.isChecked(): w2_ranges.add('mid')
        if self._w2_high_cb.isChecked(): w2_ranges.add('high')
        
        self._player.set_playback_ranges(w1_ranges, w2_ranges)

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
        self._slave_executor.set_instrument_mode(mode)

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
            self._play_btn.setText("  暫停")
            self._play_btn.setIcon(IconFactory.create_icon("pause", QColor(255, 255, 255)))
            self._status_label.setText("播放中...")
        elif self._player.is_playing:
            self._player.pause()
            self._play_btn.setText("  播放")
            self._play_btn.setIcon(IconFactory.create_icon("play", QColor(255, 255, 255)))
            self._status_label.setText("已暫停")
        else:
            self._player.toggle_play_pause()
            self._play_btn.setText("  暫停")
            self._play_btn.setIcon(IconFactory.create_icon("pause", QColor(255, 255, 255)))
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
        self._play_btn.setText("  播放")
        self._play_btn.setIcon(IconFactory.create_icon("play", QColor(255, 255, 255)))
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
            self._play_btn.setText("  暫停")
            self._play_btn.setIcon(IconFactory.create_icon("pause", QColor(255, 255, 255)))
            self._target_hwnd_combo.setEnabled(False)
            self._target_hwnd_combo2.setEnabled(False)
            self._refresh_windows_btn.setEnabled(False)
            self._w1_low_cb.setEnabled(False)
            self._w1_mid_cb.setEnabled(False)
            self._w1_high_cb.setEnabled(False)
            self._w2_low_cb.setEnabled(False)
            self._w2_mid_cb.setEnabled(False)
            self._w2_high_cb.setEnabled(False)
            self._export_sheet_btn.setEnabled(False)
            self._auto_export_cb.setEnabled(False)
        else:
            self._play_btn.setText("  播放")
            self._play_btn.setIcon(IconFactory.create_icon("play", QColor(255, 255, 255)))
            self._target_hwnd_combo.setEnabled(True)
            self._target_hwnd_combo2.setEnabled(True)
            self._refresh_windows_btn.setEnabled(True)
            self._w1_low_cb.setEnabled(True)
            self._w1_mid_cb.setEnabled(True)
            self._w1_high_cb.setEnabled(True)
            self._w2_low_cb.setEnabled(True)
            self._w2_mid_cb.setEnabled(True)
            self._w2_high_cb.setEnabled(True)
            self._export_sheet_btn.setEnabled(True)
            self._auto_export_cb.setEnabled(True)

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
        self._play_btn.setText("  播放")
        self._play_btn.setIcon(IconFactory.create_icon("play", QColor(255, 255, 255)))
        self._status_label.setText("播放完畢")
        self._note_display.setText("✓")
        
        # 自動匯出鍵盤譜
        if self._auto_export_cb.isChecked() and self._current_midi:
            self._export_keyboard_sheet()

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
        # ── 網路清理 ──
        self._network_manager.disconnect_all()
        self._slave_executor.stop()
        self._slave_executor.wait()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        """視窗關閉事件。"""
        self._on_close()
        event.accept()

    def _show_update_dialog(self, latest_version: str, release_url: str, release_notes: str, download_url: str = "") -> None:
        """顯示更新提示對話框。"""
        from PyQt5.QtWidgets import QMessageBox
        import webbrowser
        
        # 建立自定義風格的對話框
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("發現新版本！")
        msg_box.setText(f"<b>有新版本 {latest_version} 可用！</b><br><br>目前版本: {APP_VERSION}<br><br>更新說明:<br>{release_notes if release_notes else '無詳細說明'}")
        msg_box.setInformativeText("是否要立即下載並自動安裝最新版本？")
        
        # 自定義按鈕
        if download_url:
            yes_btn = msg_box.addButton("🚀 立即下載並安裝", QMessageBox.YesRole)
        else:
            yes_btn = msg_box.addButton("💾 前往下載頁面", QMessageBox.YesRole)
            
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
            if download_url:
                # 啟動應用內下載對話框
                self._update_dlg = UpdateProgressDialog(download_url, self)
                self._update_dlg.exec_()
            else:
                webbrowser.open(release_url)

    def _open_network_duet(self) -> None:
        """開啟網路聯彈對話框。"""
        dialog = NetworkDuetDialog(self._network_manager, self)
        dialog.exec_()

    @pyqtSlot(str, bool)
    def _on_connection_established(self, peer_ip: str, is_master: bool) -> None:
        """網路連線建立後的設定。"""
        if is_master:
            self._player.set_network_send_callback(self._network_manager.send_cmd)
            self._player.set_playback_ranges(self._local_play_ranges, self._remote_play_ranges)
            self._player.set_remote_instrument_mode(self._remote_instrument_override)
        else:
            self._player.set_network_send_callback(None)
            self._player.set_playback_ranges(set(), {'low', 'mid', 'high'})
            self._status_label.setText("連線成功 (被控端模式)")

    @pyqtSlot()
    def _on_disconnected(self) -> None:
        """斷開連線後的還原設定。"""
        self._player.set_network_send_callback(None)
        self._player.set_playback_ranges({'low', 'mid', 'high'}, set())
        self._note_display.setText("--")
        self._status_label.setText("就緒")

    @pyqtSlot(dict)
    def _on_network_command_received(self, cmd: dict) -> None:
        """被控端接收到遠端播放命令時，更新本機 UI 顯示。"""
        action = cmd.get("action")
        keys = cmd.get("keys", [])
        if action == "press" and keys:
            key_str = "+".join(keys)
            self._note_display.setText(key_str)
            self._status_label.setText("同步演奏中...")
        elif action == "release_all":
            self._note_display.setText("--")
            self._status_label.setText("連線成功 (被控模式)")
