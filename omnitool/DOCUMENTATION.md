# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `omnitool/` (GUI Agent System & Linux Host Server)

Thư mục [`omnitool/`](file:///home/thai/Downloads/omniparser/omnitool) chứa toàn bộ hệ sinh thái điều khiển máy tính tự động (**OmniTool GUI Agent**), bao gồm 3 thành phần kiến trúc độc lập giao tiếp qua giao thức HTTP REST API:
1. **Host Control Server** ([`linux_host_server.py`](file:///home/thai/Downloads/omniparser/omnitool/linux_host_server.py) hoặc máy ảo [`omnibox/`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/DOCUMENTATION.md)) chạy tại cổng **`5000`**: Chụp màn hình thực tế và thực thi thao tác chuột/phím (`pyautogui`).
2. **OmniParser Server** ([`omniparserserver/`](file:///home/thai/Downloads/omniparser/omnitool/omniparserserver/DOCUMENTATION.md)) chạy tại cổng **`8000`** (hoặc trên Google Colab GPU): Phân tích ảnh chụp màn hình thành ảnh Set-of-Mark (SoM) và danh sách toạ độ.
3. **Gradio Agent Client** ([`gradio/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/DOCUMENTATION.md)) chạy tại cổng **`7888`**: Giao diện người dùng, vòng lặp suy luận VLM/LLM và bộ thực thi công cụ.

---

## 1. Phân Tích Chi Tiết [`omnitool/linux_host_server.py`](file:///home/thai/Downloads/omniparser/omnitool/linux_host_server.py)

Tệp [`linux_host_server.py`](file:///home/thai/Downloads/omniparser/omnitool/linux_host_server.py) là một Flask Server chạy tại `http://127.0.0.1:5000`, thay thế hoàn toàn máy ảo Windows (`omnibox`) nặng 20GB để cho phép Agent điều khiển trực tiếp màn hình Ubuntu/Linux của người dùng.

### 1.1. Cơ chế Khoá Luồng (`threading.Lock`) và Endpoint `/probe` ([`linux_host_server.py:L12-L20`](file:///home/thai/Downloads/omniparser/omnitool/linux_host_server.py#L12-L20))
```python
app = Flask(__name__)
computer_control_lock = threading.Lock()

cursor_path = os.path.join(os.path.dirname(__file__), "omnibox/vm/win11setup/setupscripts/server/cursor.png")

@app.route('/probe', methods=['GET'])
def probe_endpoint():
    return jsonify({"status": "Probe successful", "message": "Linux Host Service is operational"}), 200
```
- `computer_control_lock`: Đảm bảo tại mỗi thời điểm chỉ có **duy nhất 1 lệnh chuột/bàn phím** được thực thi, ngăn chặn xung đột khi hai luồng gọi `/execute` cùng lúc.
- `/probe`: Được hàm `valid_params()` trong `gradio/app.py` kiểm tra trước khi bắt đầu mỗi tác vụ.

---

### 1.2. Thực Thi Lệnh Điều Khiển Chuột & Phím `POST /execute` ([`linux_host_server.py:L48-L80`](file:///home/thai/Downloads/omniparser/omnitool/linux_host_server.py#L48-L80))
```python
@app.route('/execute', methods=['POST'])
def execute_command():
    with computer_control_lock:
        data = request.json or {}
        command = data.get('command', [])
        shell = data.get('shell', False)
        if isinstance(command, str) and not shell:
            command = shlex.split(command)
        
        # Ensure python commands execute with current environment python
        if command and command[0] == "python":
            command[0] = sys.executable

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=shell,
                text=True,
                timeout=120
            )
            return jsonify({
                'status': 'success',
                'output': result.stdout,
                'error': result.stderr,
                'returncode': result.returncode
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
```
**Cơ chế hoạt động:**
- Khi `ComputerTool` (trong `omnitool/gradio/tools/computer.py`) gửi một payload JSON như:
  ```json
  {"command": ["python", "-c", "import pyautogui; pyautogui.FAILSAFE = False; pyautogui.moveTo(73, 115)"]}
  ```
- Dòng `if command and command[0] == "python": command[0] = sys.executable` tự động ánh xạ `"python"` sang trình thông dịch của môi trường ảo `.venv/bin/python` (nơi đã cài đặt `pyautogui`), sau đó chạy `subprocess.run` và trả về `stdout`/`stderr`.

---

### 1.3. Chụp Màn Hình Tương Thích Ubuntu Wayland & X11 `GET /screenshot` ([`linux_host_server.py:L82-L129`](file:///home/thai/Downloads/omniparser/omnitool/linux_host_server.py#L82-L129))
```python
@app.route('/screenshot', methods=['GET'])
def capture_screen():
    try:
        screenshot = None
        tmp_path = f"/tmp/omniparser_screen_{os.getpid()}.png"
        clean_env = {
            "DISPLAY": os.environ.get("DISPLAY", ":0"),
            "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-0"),
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
            "PATH": "/usr/bin:/bin"
        }
        try:
            res = subprocess.run(["gnome-screenshot", "-f", tmp_path], env=clean_env, capture_output=True, timeout=5)
            if res.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 10000:
                screenshot = Image.open(tmp_path)
                screenshot.load()
        except Exception:
            pass
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        if screenshot is None:
            # Fallback to MSS if not on Wayland or if gnome-screenshot not available
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # primary display
                sct_img = sct.grab(monitor)
                screenshot = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')

        # Paste cursor icon if available
        if os.path.exists(cursor_path):
            try:
                cursor_x, cursor_y = pyautogui.position()
                cursor = Image.open(cursor_path)
                cursor = cursor.resize((int(cursor.width / 1.5), int(cursor.height / 1.5)))
                screenshot.paste(cursor, (cursor_x, cursor_y), cursor)
            except Exception:
                pass

        img_io = BytesIO()
        screenshot.save(img_io, 'PNG')
        img_io.seek(0)
        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
```
**Tại sao cần `clean_env` với `gnome-screenshot`?**
1. Trên **Ubuntu Wayland (`XDG_SESSION_TYPE=wayland`)**, thư viện chụp màn hình X11 truyền thống như `mss` hoặc `PIL.ImageGrab` bị hệ điều hành chặn quyền đọc framebuffer nên chỉ trả về **ảnh đen hoàn toàn (~7 KB)**.
2. Khi chạy terminal bên trong VS Code bản Snap, biến môi trường của tiến trình con bị chèn `GTK_PATH` và `LD_LIBRARY_PATH` của `/snap/code/...`, gây lỗi `symbol lookup error: libatk-bridge-2.0.so.0` nếu gọi `gnome-screenshot` trực tiếp.
3. Do đó, việc truyền `env=clean_env` (chỉ giữ lại `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR`, `PATH=/usr/bin:/bin`) giúp `gnome-screenshot` chụp chính xác toàn bộ màn hình màu thật (~450 KB), sau đó dán biểu tượng con trỏ chuột `cursor.png` đúng vị trí `pyautogui.position()` rồi xoá tệp tạm ngay lập tức.

---

## 2. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm chứng trực tiếp các endpoint `/probe`, `/execute` (lấy kích thước màn hình và toạ độ chuột) và `/screenshot` của `linux_host_server.py`:

```bash
.venv/bin/python -c '
import requests
from PIL import Image
from io import BytesIO

# 1. Kiểm chứng /probe
r_probe = requests.get("http://127.0.0.1:5000/probe", timeout=3).json()
print("1. GET /probe:", r_probe)

# 2. Kiểm chứng /execute với lệnh lấy độ phân giải màn hình
r_exec = requests.post(
    "http://127.0.0.1:5000/execute",
    json={"command": ["python", "-c", "import pyautogui; print(pyautogui.size())"]},
    timeout=5
).json()
print("2. POST /execute:", r_exec)

# 3. Kiểm chứng /screenshot
r_shot = requests.get("http://127.0.0.1:5000/screenshot", timeout=5)
img = Image.open(BytesIO(r_shot.content))
print("3. GET /screenshot: HTTP", r_shot.status_code, "| Size:", img.size, "| Mode:", img.mode, "| Bytes:", len(r_shot.content))
'
```

**Kết quả thực thi thực tế:**
```text
1. GET /probe: {'message': 'Linux Host Service is operational', 'status': 'Probe successful'}
2. POST /execute: {'error': '', 'output': 'Size(width=1920, height=1200)\n', 'returncode': 0, 'status': 'success'}
3. GET /screenshot: HTTP 200 | Size: (1920, 1200) | Mode: RGB | Bytes: 451284
```

