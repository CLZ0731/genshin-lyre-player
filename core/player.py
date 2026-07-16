"""
播放引擎模組

基於 QThread 的多執行緒播放控制器，負責按照解析後的音符序列
精準觸發鍵盤事件，支持播放、暫停、停止與曲目切換。
支援詩琴(Lyre)與圓號(Horn)兩種樂器模式。
"""

import time

from PyQt5.QtCore import QThread, pyqtSignal

from core.key_simulator import (
    press_and_release, press_multiple_keys,
    press_key, release_key, SCAN_CODES
)
from core.midi_parser import ParsedMidi, KeyEvent


class PlaybackState:
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"


class PlayerThread(QThread):
    """
    獨立執行緒的 MIDI 播放引擎。
    """

    state_changed = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)
    note_played = pyqtSignal(str)
    playback_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._midi_data: ParsedMidi | None = None
        self._is_playing = False
        self._is_stopped = True
        self._delay_min = 0.02
        self._delay_max = 0.05
        self._instrument_mode = "lyre"  # 'lyre' 或 'horn'
        self._velocity_dynamics = True   # 力度動態演奏
        self._active_keys: set[str] = set()

    def set_midi_data(self, midi_data: ParsedMidi) -> None:
        self._midi_data = midi_data

    def set_press_delay(self, delay_min: float, delay_max: float) -> None:
        self._delay_min = delay_min
        self._delay_max = delay_max

    def set_instrument_mode(self, mode: str) -> None:
        """設定樂器模式 ('lyre' 詩琴 或 'horn' 圓號)。"""
        self._instrument_mode = mode

    def set_velocity_dynamics(self, enabled: bool) -> None:
        """設定是否啟用力度動態演奏。"""
        self._velocity_dynamics = enabled

    def play(self) -> None:
        self._is_playing = True
        self._is_stopped = False
        if not self.isRunning():
            self.start()

    def pause(self) -> None:
        self._is_playing = False
        self._release_all_active_keys()

    def toggle_play_pause(self) -> None:
        if self._is_stopped and self._midi_data:
            self.play()
        elif self._is_playing:
            self.pause()
            self.state_changed.emit(PlaybackState.PAUSED)
        else:
            self._is_playing = True
            self.state_changed.emit(PlaybackState.PLAYING)

    def stop(self) -> None:
        self._is_stopped = True
        self._is_playing = False
        self._release_all_active_keys()

    def _release_all_active_keys(self) -> None:
        """安全釋放所有目前按下的按鍵，避免卡死。"""
        for key_char in list(self._active_keys):
            scan_code = SCAN_CODES.get(key_char.upper())
            if scan_code is not None:
                release_key(scan_code)
        self._active_keys.clear()

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def is_stopped(self) -> bool:
        return self._is_stopped

    def run(self) -> None:
        if self._midi_data is None or not self._midi_data.events:
            self.error_occurred.emit("沒有可播放的音符資料")
            return

        self.state_changed.emit(PlaybackState.PLAYING)
        events = self._midi_data.events
        
        # 根據樂器模式計算總按鍵數
        if self._instrument_mode == 'horn':
            total_presses = sum(
                len([k for k in e.keys if k.upper() not in ('Z','X','C','V','B','N','M')])
                for e in events if e.action == 'press'
            )
        else:
            total_presses = self._midi_data.total_notes
            
        current_press_count = 0

        try:
            # 播放開始前的初始延遲
            start_delay = 2.0
            wait_start = time.perf_counter()
            while time.perf_counter() - wait_start < start_delay:
                if self._is_stopped:
                    self.state_changed.emit(PlaybackState.STOPPED)
                    self.playback_finished.emit()
                    return
                time.sleep(0.05)

            for event in events:
                if self._is_stopped:
                    break

                while not self._is_playing and not self._is_stopped:
                    time.sleep(0.05)

                if self._is_stopped:
                    break

                # ── 精準延遲等待 ──
                if event.time_seconds > 0:
                    target_time = time.perf_counter() + event.time_seconds
                    while time.perf_counter() < target_time - 0.002:
                        if self._is_stopped:
                            break
                        if not self._is_playing:
                            while not self._is_playing and not self._is_stopped:
                                time.sleep(0.05)
                            remaining = target_time - time.perf_counter()
                            if remaining > 0:
                                target_time = time.perf_counter() + remaining
                        time.sleep(0.001)
                    while time.perf_counter() < target_time:
                        pass

                if self._is_stopped:
                    break

                # ── 音域修正 (圓號無低音區) ──
                # 晚風圓號只有中音與高音，忽略低音(Z~M)
                if self._instrument_mode == 'horn':
                    current_keys = [k.upper() for k in event.keys if k.upper() not in ('Z','X','C','V','B','N','M')]
                else:
                    current_keys = [k.upper() for k in event.keys]

                # ── 執行按鍵邏輯 ──
                if self._instrument_mode == 'horn':
                    # 圓號模式：真實按壓與釋放
                    for key_char in current_keys:
                        scan_code = SCAN_CODES.get(key_char)
                        if scan_code is not None:
                            if event.action == 'press':
                                press_key(scan_code)
                                self._active_keys.add(key_char)
                            elif event.action == 'release':
                                release_key(scan_code)
                                self._active_keys.discard(key_char)
                else:
                    # 詩琴模式：只在按下時觸發一次短點擊
                    if event.action == 'press':
                        # 力度動態演奏：根據 velocity 縮放按壓時長
                        if self._velocity_dynamics and event.velocity > 0:
                            vel_scale = event.velocity / 127.0  # 0.0 ~ 1.0
                            dyn_min = self._delay_min * (0.4 + 0.6 * vel_scale)
                            dyn_max = self._delay_max * (0.4 + 0.6 * vel_scale)
                        else:
                            dyn_min = self._delay_min
                            dyn_max = self._delay_max
                        
                        if len(current_keys) == 1:
                            press_and_release(current_keys[0], dyn_min, dyn_max)
                        else:
                            press_multiple_keys(current_keys, dyn_min, dyn_max)

                # ── 發射信號更新 UI ──
                if event.action == 'press':
                    key_str = "+".join(current_keys)
                    self.note_played.emit(key_str)
                    current_press_count += len(current_keys)
                    self.progress_updated.emit(current_press_count, total_presses)

        except Exception as e:
            self.error_occurred.emit(f"播放時發生錯誤: {str(e)}")

        self._release_all_active_keys()
        self._is_playing = False
        self._is_stopped = True
        self.state_changed.emit(PlaybackState.STOPPED)
        self.playback_finished.emit()
