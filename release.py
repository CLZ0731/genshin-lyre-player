import os
import sys
import json
import urllib.request
import urllib.error

# 優先從環境變數讀取 TOKEN，若沒有則讀取本地 gitignored 的 github_token.txt 檔案
TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "github_token.txt")
    if os.path.exists(token_path):
        with open(token_path, "r", encoding="utf-8") as f:
            TOKEN = f.read().strip()
            
if not TOKEN:
    raise ValueError("找不到 GitHub TOKEN！請設定 GITHUB_TOKEN 環境變數或建立 github_token.txt 檔案。")

OWNER = "CLZ0731"
REPO = "genshin-lyre-player"
TAG_NAME = "v1.11.0"
MSI_FILE = r"dist\GenshinLyrePlayer-1.11.0-win64.msi"
PORTABLE_DIR = r"build\exe.win-amd64-3.12"
ZIP_FILE = r"dist\GenshinLyrePlayer-1.11.0-portable.zip"

def make_request(url, headers, method="GET", payload=None, data=None):
    if payload:
        data = json.dumps(payload).encode("utf-8")
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            res_data = json.loads(e.read().decode("utf-8"))
        except Exception:
            res_data = e.reason
        return e.code, res_data
    except Exception as e:
        return -1, str(e)

def create_release():
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    payload = {
        "tag_name": TAG_NAME,
        "name": f"Genshin Lyre Player {TAG_NAME}",
        "body": "## 更新內容\n- **修復模擬器與後台視窗按鍵失效 Bug**：\n  - **增加 WM_ACTIVATE 與 WM_SETFOCUS 注入**：每次發送後台按鍵前，自動向目標視窗的訊息佇列發送視窗啟用與聚焦訊號，解決了部分模擬器在後台或失去焦點時，會主動丟棄 PostMessage 按鍵訊息的問題。\n  - **更廣泛的模擬器渲染子視窗偵測**：針對如 BlueStacks 等基於 Qt5/Qt6 且沒有專門 Render 類名的模擬器，新增了遞迴尋找 Qt 渲染子視窗並對齊對應 HWND 的邏輯，大幅提升對 BlueStacks 等模擬器的背景播放相容性！\n  - 現在，您可以將 PC 版原神保持在前景 (由於 PC 遊戲本身會透過 API 強行檢測 GetForegroundWindow 焦點，故 PC 版必須聚焦)，而將**安卓模擬器丟到背景**，兩者即能同時響應按鍵完美彈奏！",
        "draft": False,
        "prerelease": False
    }
    
    print(f"正在創建 Release {TAG_NAME}...")
    status, result = make_request(url, headers, method="POST", payload=payload)
    if status == 201:
        print(f"成功創建 Release! ID: {result['id']}")
        return result['id']
    elif status == 422 and "already_exists" in str(result):
        print("Release 已存在，將取得現有 Release ID...")
        # 取得已存在的 release
        status, result = make_request(f"https://api.github.com/repos/{OWNER}/{REPO}/releases/tags/{TAG_NAME}", headers)
        if status == 200:
            return result['id']
    
    print(f"創建 Release 失敗: {status} - {result}")
    return None

def upload_asset(release_id, file_path):
    if not os.path.exists(file_path):
        print(f"找不到檔案: {file_path}")
        return False
        
    name = os.path.basename(file_path)
    url = f"https://uploads.github.com/repos/{OWNER}/{REPO}/releases/{release_id}/assets?name={name}"
    
    with open(file_path, "rb") as f:
        data = f.read()
        
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/octet-stream"
    }
    
    print(f"正在上傳安裝包 {name} (大小: {len(data)/1024/1024:.2f} MB)...")
    status, result = make_request(url, headers, method="POST", data=data)
    
    if status == 201:
        print("上傳成功！")
        return True
    else:
        print(f"上傳失敗: {status} - {result}")
        return False

def main():
    # 建立 ZIP 免安裝版
    print(f"正在打包免安裝版 ZIP...")
    import shutil
    import os
    
    if not os.path.exists("dist"):
        os.makedirs("dist")
        
    # shutil.make_archive 會自動加上 .zip 副檔名，所以要把 ZIP_FILE 去除 .zip
    zip_base = ZIP_FILE[:-4] if ZIP_FILE.endswith(".zip") else ZIP_FILE
    shutil.make_archive(zip_base, 'zip', PORTABLE_DIR)
    
    release_id = create_release()
    if release_id:
        upload_asset(release_id, MSI_FILE)
        upload_asset(release_id, ZIP_FILE)

if __name__ == "__main__":
    main()
