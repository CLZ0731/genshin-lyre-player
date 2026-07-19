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
TAG_NAME = "v1.14.0"
MSI_FILE = r"dist\GenshinLyrePlayer-1.14.0-win64.msi"
PORTABLE_DIR = r"build\exe.win-amd64-3.12"
ZIP_FILE = r"dist\GenshinLyrePlayer-1.14.0-portable.zip"

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
        "body": "## 更新內容\n- **新增「精簡迷你模式（可摺疊視窗）」**：\n  - 在標題列新增「精簡模式 / 完整模式」切換按鈕，可一鍵將參數設定摺疊隱藏，縮小為僅 240 像素高的迷你浮動播放器，不再阻擋遊戲畫面！\n  - 修復自訂無邊框縮放臨界值同步 Bug，使手動調整大小更加平滑、反應靈敏。\n- **大幅降低系統資源佔用 (CPU 佔用率趨近 0%)**：\n  - 優化播放引擎的精準延遲控制，引進大區間預先休眠 (Pre-sleep) 機制釋放 CPU 週期，彻底免除 fine-grained 迴圈空轉，大幅降低執行緒資源消耗，提升執行速度！\n- **引進「增量代碼更新 (Code Patch)」機制**：\n  - 自動偵測並下載僅包含 `core/`、`ui/`、`utils/` 的增量更新補丁 (.zip)，下載量從 197 MB 驟降至 100 KB 以下！安裝程序瞬間完成，極大降低空間占用率！",
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
    import zipfile
    
    if not os.path.exists("dist"):
        os.makedirs("dist")
        
    # shutil.make_archive 會自動加上 .zip 副檔名，所以要把 ZIP_FILE 去除 .zip
    zip_base = ZIP_FILE[:-4] if ZIP_FILE.endswith(".zip") else ZIP_FILE
    shutil.make_archive(zip_base, 'zip', PORTABLE_DIR)
    
    # 建立代碼增量更新補丁 PATCH_ZIP
    print("正在打包代碼增量更新補丁 PATCH_ZIP...")
    patch_zip_path = ZIP_FILE.replace("-portable.zip", "-patch.zip")
    with zipfile.ZipFile(patch_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_f:
        # 只打包 lib/core、lib/ui、lib/utils 中的檔案
        for folder in ["core", "ui", "utils"]:
            src_folder = os.path.join(PORTABLE_DIR, "lib", folder)
            if os.path.exists(src_folder):
                for root, dirs, files in os.walk(src_folder):
                    for file in files:
                        full_path = os.path.join(root, file)
                        # 計算相對壓縮路徑，例如 "lib/core/player.pyc"
                        rel_path = os.path.relpath(full_path, PORTABLE_DIR)
                        zip_f.write(full_path, rel_path)
    
    release_id = create_release()
    if release_id:
        upload_asset(release_id, MSI_FILE)
        upload_asset(release_id, ZIP_FILE)
        upload_asset(release_id, patch_zip_path)

if __name__ == "__main__":
    main()
