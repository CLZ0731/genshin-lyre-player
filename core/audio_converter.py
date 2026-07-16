import os
import tempfile
import numpy as np
import soundfile as sf
import av
from PyQt5.QtCore import QThread, pyqtSignal

class AudioConverterThread(QThread):
    """
    非同步語音轉錄 MIDI 執行緒。
    使用 Spotify basic-pitch 進行 Automatic Music Transcription。
    """
    finished = pyqtSignal(str)  # 成功時傳回輸出的 MIDI 檔案路徑
    error = pyqtSignal(str)     # 失敗時傳回錯誤訊息

    def __init__(self, audio_path: str, output_midi_path: str, onset_threshold: float = 0.55, frame_threshold: float = 0.35, parent=None):
        super().__init__(parent)
        self.audio_path = audio_path
        self.output_midi_path = output_midi_path
        self.onset_threshold = onset_threshold
        self.frame_threshold = frame_threshold

    def run(self) -> None:
        temp_wav_path = None
        try:
            # 延遲導入 basic-pitch，避免程式啟動時載入重量級 AI 庫導致卡頓
            from basic_pitch.inference import predict
            
            if not os.path.exists(self.audio_path):
                self.error.emit("音訊檔案不存在")
                return
            
            # 使用 PyAV 將音訊檔案解碼並轉換為標準單聲道 22050Hz Float32 WAV
            # 這能相容於所有音訊格式（包括 MP3, WAV, M4A, AAC, FLAC 等）且不需額外安裝 FFmpeg
            print(f"[音訊解碼] 正在使用 PyAV 解碼: {self.audio_path}")
            
            container = av.open(self.audio_path)
            if not container.streams.audio:
                raise ValueError("檔案中沒有找到任何音軌。")
                
            stream = container.streams.audio[0]
            
            # 建立重採樣器，強制轉為單聲道、22050Hz、float32 格式
            resampler = av.AudioResampler(
                format='flt', 
                layout='mono', 
                rate=22050
            )
            
            all_chunks = []
            for frame in container.decode(stream):
                resampled = resampler.resample(frame)
                for r_frame in resampled:
                    # 轉為 1D numpy array
                    arr = r_frame.to_ndarray().flatten()
                    all_chunks.append(arr)
            
            container.close()
            
            if not all_chunks:
                raise ValueError("解碼音軌後未獲得任何音訊樣本。")
                
            # 合併為單一 1D float32 array
            audio_data = np.concatenate(all_chunks)
            
            # 建立暫存 WAV 檔案
            temp_fd, temp_wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(temp_fd)  # 關閉檔案描述子，以便 soundfile 寫入
            
            print(f"[音訊解碼] 寫入暫存 PCM WAV: {temp_wav_path}")
            sf.write(temp_wav_path, audio_data, 22050)
            
            # 執行 AI 預測轉錄，加上頻率範圍限制 (原神鋼琴白鍵 C3~B5) 與過濾參數
            # 關閉 multiple_pitch_bends 減少滑音數據
            print(f"[AI 轉錄] 正在分析音軌並轉換為 MIDI: {temp_wav_path} (onset_threshold={self.onset_threshold}, frame_threshold={self.frame_threshold})")
            model_output, midi_data, note_events = predict(
                temp_wav_path,
                onset_threshold=self.onset_threshold,
                frame_threshold=self.frame_threshold,
                minimum_frequency=125.0,  # 忽略 C3 以下的低音（如貝斯、鼓聲）
                maximum_frequency=1050.0, # 忽略 B5 以上的高頻噪音與諧波
                minimum_note_length=150,  # 過濾掉短於 150ms 的短暫雜訊
                multiple_pitch_bends=False
            )
            
            # 清除所有 Pitch Bend（滑音）數據，避免其他播放器或 DAW 播放時發出忽高忽低、走音的怪聲
            for instrument in midi_data.instruments:
                instrument.pitch_bends.clear()
            
            # 寫入 MIDI 檔案
            midi_data.write(self.output_midi_path)
            
            if os.path.exists(self.output_midi_path):
                self.finished.emit(self.output_midi_path)
            else:
                self.error.emit("寫入 MIDI 檔案失敗")
        except Exception as e:
            import traceback
            # 印出錯誤到控制台
            print("[轉錄錯誤] 詳細堆疊資訊如下：")
            traceback.print_exc()
            
            # 寫入 diagnostic.txt
            diag_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diagnostic.txt")
            try:
                with open(diag_file, "a", encoding="utf-8") as f:
                    f.write("\n\n--- 轉錄錯誤 ---\n")
                    traceback.print_exc(file=f)
            except Exception:
                pass
                
            self.error.emit(f"轉錄過程中發生錯誤: {str(e)}")
        finally:
            # 清理暫存檔案
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                    print(f"[音訊解碼] 已清理暫存檔案: {temp_wav_path}")
                except Exception:
                    pass
