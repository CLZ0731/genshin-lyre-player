import socket
import json
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot

def ip_to_code(ip: str) -> str:
    try:
        parts = list(map(int, ip.split('.')))
        if len(parts) != 4:
            return ""
        val = (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        code = ""
        while val > 0:
            code = chars[val % 36] + code
            val //= 36
        return code.zfill(6)
    except Exception:
        return ""

def code_to_ip(code: str) -> str:
    try:
        code = code.upper().strip()
        val = 0
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for char in code:
            val = val * 36 + chars.index(char)
        p1 = (val >> 24) & 0xFF
        p2 = (val >> 16) & 0xFF
        p3 = (val >> 8) & 0xFF
        p4 = val & 0xFF
        return f"{p1}.{p2}.{p3}.{p4}"
    except Exception:
        return ""

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class ServerThread(QThread):
    client_connected = pyqtSignal(socket.socket, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, port=42119, parent=None):
        super().__init__(parent)
        self.port = port
        self.running = True
        self.server_socket = None

    def run(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("0.0.0.0", self.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    self.client_connected.emit(conn, addr[0])
                    break
                except socket.timeout:
                    continue
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except Exception:
                    pass

    def stop(self):
        self.running = False


class ReceiverThread(QThread):
    message_received = pyqtSignal(dict)
    disconnected = pyqtSignal()

    def __init__(self, conn: socket.socket, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.running = True

    def run(self):
        self.conn.settimeout(1.0)
        buffer = ""
        while self.running:
            try:
                data = self.conn.recv(4096).decode('utf-8')
                if not data:
                    self.disconnected.emit()
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            self.message_received.emit(msg)
                        except json.JSONDecodeError:
                            pass
            except socket.timeout:
                continue
            except Exception:
                self.disconnected.emit()
                break
        try:
            self.conn.close()
        except Exception:
            pass

    def stop(self):
        self.running = False


class ClientConnectThread(QThread):
    connected = pyqtSignal(socket.socket, str)
    failed = pyqtSignal(str)

    def __init__(self, ip: str, port=42119, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.port = port

    def run(self):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(5.0)
            conn.connect((self.ip, self.port))
            self.connected.emit(conn, self.ip)
        except Exception as e:
            self.failed.emit(str(e))


class NetworkSyncManager(QObject):
    connection_established = pyqtSignal(str, bool)  # peer_ip, is_master
    disconnected = pyqtSignal()
    command_received = pyqtSignal(dict)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.conn = None
        self.is_connected = False
        self.is_master = False
        
        self.server_thread = None
        self.connect_thread = None
        self.receiver_thread = None

    def start_host_mode(self):
        """啟動被控端模式 (等待主控端連線)"""
        self.disconnect_all()
        self.is_master = False
        self.status_changed.emit("正在等待連線...")
        
        self.server_thread = ServerThread(parent=self)
        self.server_thread.client_connected.connect(self._on_client_connected)
        self.server_thread.error_occurred.connect(self._on_network_error)
        self.server_thread.start()

    def connect_as_master(self, code: str):
        """啟動主控端模式，連接到指定配對碼的被控端"""
        self.disconnect_all()
        self.is_master = True
        
        ip = code_to_ip(code)
        if not ip or ip == "0.0.0.0":
            self.error_occurred.emit("無效的配對碼格式")
            return
            
        self.status_changed.emit("正在連線...")
        self.connect_thread = ClientConnectThread(ip, parent=self)
        self.connect_thread.connected.connect(self._on_master_connected)
        self.connect_thread.failed.connect(self._on_connect_failed)
        self.connect_thread.start()

    @pyqtSlot(socket.socket, str)
    def _on_client_connected(self, conn: socket.socket, ip: str):
        self.conn = conn
        self.is_connected = True
        self.status_changed.emit(f"已連線到主控端 ({ip})")
        self.connection_established.emit(ip, False)
        
        # 啟動接收執行緒
        self.receiver_thread = ReceiverThread(conn, parent=self)
        self.receiver_thread.message_received.connect(self.command_received)
        self.receiver_thread.disconnected.connect(self._on_disconnected)
        self.receiver_thread.start()

    @pyqtSlot(socket.socket, str)
    def _on_master_connected(self, conn: socket.socket, ip: str):
        self.conn = conn
        self.is_connected = True
        self.status_changed.emit(f"已連線到被控端 ({ip})")
        self.connection_established.emit(ip, True)
        
        # 主控端也啟動接收執行緒 (防斷線偵測)
        self.receiver_thread = ReceiverThread(conn, parent=self)
        self.receiver_thread.disconnected.connect(self._on_disconnected)
        self.receiver_thread.start()

    @pyqtSlot(str)
    def _on_connect_failed(self, error_msg: str):
        self.status_changed.emit("連線失敗")
        self.error_occurred.emit(f"無法建立連線: {error_msg}")

    @pyqtSlot(str)
    def _on_network_error(self, error_msg: str):
        self.status_changed.emit("網路錯誤")
        self.error_occurred.emit(error_msg)

    @pyqtSlot()
    def _on_disconnected(self):
        self.disconnect_all()
        self.status_changed.emit("未連線")
        self.disconnected.emit()

    def send_cmd(self, cmd: dict):
        """發送命令給對端"""
        if not self.is_connected or not self.conn:
            return
        try:
            data = (json.dumps(cmd) + "\n").encode('utf-8')
            self.conn.sendall(data)
        except Exception:
            self._on_disconnected()

    def disconnect_all(self):
        self.is_connected = False
        
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread.wait()
            self.server_thread = None
            
        if self.connect_thread:
            self.connect_thread.wait()
            self.connect_thread = None
            
        if self.receiver_thread:
            self.receiver_thread.stop()
            self.receiver_thread.wait()
            self.receiver_thread = None
            
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None
