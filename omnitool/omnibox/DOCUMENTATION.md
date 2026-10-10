# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `omnitool/omnibox/` (Windows 11 KVM Docker VM)

Thư mục [`omnitool/omnibox/`](file:///home/thai/Downloads/omniparser/omnitool/omnibox) chứa hệ thống đóng gói máy ảo **Windows 11 Enterprise Evaluation** bên trong Docker container (sử dụng QEMU/KVM) cùng với Flask Server điều khiển bên trong máy ảo Windows đó.

> [!NOTE]
> Trên máy Ubuntu/Linux của bạn hiện tại, tệp [`omnitool/linux_host_server.py`](file:///home/thai/Downloads/omniparser/omnitool/linux_host_server.py) đã được thiết kế để thay thế hoàn toàn `omnibox` (chạy trực tiếp trên máy thật ở cổng `5000`, tốn 0GB dung lượng máy ảo). Tuy nhiên, tài liệu này giải thích chi tiết cách `omnibox` hoạt động trong thiết kế gốc và cách hai hệ thống chia sẻ chung giao thức API.

---

## 1. Cấu Trúc Các Tệp Trong `omnitool/omnibox/`

| Tệp / Thư mục | Vai trò cốt lõi |
| :--- | :--- |
| [`compose.yml`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/compose.yml) | Cấu hình Docker Compose khởi tạo container `omni-windows` (8GB RAM, 4 CPU cores, 20GB Disk, quyền `/dev/kvm`, mở cổng `8006` cho NoVNC Web Viewer). |
| [`Dockerfile`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/Dockerfile) | Xây dựng image dựa trên `qemux/qemu-docker:6.08`, cài đặt driver VirtIO, Samba, `wimtools`, `genisoimage` và nạp các script khởi động KVM vào `/run/`. |
| [`scripts/manage_vm.sh`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/scripts/manage_vm.sh) | Script Bash quản lý vòng đời máy ảo (`create`, `start`, `stop`, `delete`) và vòng lặp chờ `localhost:5000/probe` trả về HTTP `200`. |
| [`vm/win11setup/setupscripts/server/main.py`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/vm/win11setup/setupscripts/server/main.py) | Flask Control Server chạy ngầm bên trong Windows 11 tại cổng `5000` (cung cấp `/probe`, `/execute`, `/screenshot`). |
| [`vm/win11setup/setupscripts/server/cursor.png`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/vm/win11setup/setupscripts/server/cursor.png) | Ảnh biểu tượng con trỏ chuột (được cả Windows VM và `linux_host_server.py` dùng để dán lên ảnh chụp màn hình). |

---

## 2. Giải Thích Chi Tiết Kèm Mã Nguồn Thực Tế

### 2.1. Cấu hình Docker KVM trong [`compose.yml`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/compose.yml)

Toàn bộ nội dung [`compose.yml:L1-L22`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/compose.yml#L1-L22):
```yaml
services:
  windows:
    image: windows-local
    container_name: omni-windows
    privileged: true
    environment:
      RAM_SIZE: "8G"
      CPU_CORES: "4"
      DISK_SIZE: "20G"
    devices:
      - /dev/kvm
      - /dev/net/tun
    cap_add:
      - NET_ADMIN
    ports:
      - 8006:8006                 # Web Viewer access
    volumes:
      - ./vm/win11iso/custom.iso:/custom.iso
      - ./vm/win11setup/firstboot:/oem
      - ./vm/win11setup/setupscripts:/data
      - ./vm/win11storage:/storage
```
- Gắn trực tiếp bộ tăng tốc ảo hoá phần cứng `/dev/kvm` của nhân Linux vào container để chạy Windows 11 qua QEMU.
- Thư mục `./vm/win11setup/setupscripts` được mount vào `/data` (chia sẻ qua Samba tới máy ảo Windows) để khi Windows khởi động lần đầu (`firstboot/install.bat` và `on-logon.ps1`), nó tự động cài Python và chạy `server/main.py`.

---

### 2.2. Máy chủ điều khiển bên trong Windows VM [`vm/win11setup/setupscripts/server/main.py`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/vm/win11setup/setupscripts/server/main.py)

Trích dẫn mã nguồn [`server/main.py:L14-L95`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/vm/win11setup/setupscripts/server/main.py#L14-L95):
```python
def execute_anything(data):
    """Execute any command received in the JSON request.
    WARNING: This function executes commands without any safety checks."""
    shell = data.get('shell', False)
    command = data.get('command', "" if shell else [])

    if isinstance(command, str) and not shell:
        command = shlex.split(command)

    # Expand user directory
    for i, arg in enumerate(command):
        if arg.startswith("~/"):
            command[i] = os.path.expanduser(arg)

    # Execute the command without any safety checks.
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell, text=True, timeout=120)
        return jsonify({
            'status': 'success',
            'output': result.stdout,
            'error': result.stderr,
            'returncode': result.returncode
        })
    except Exception as e:
        logger.error("\n" + traceback.format_exc() + "\n")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    

def execute(data):
    """Action space aware implementation. Should not use arbitrary code execution."""
    return jsonify({
        'status': 'error',
        'message': 'Not implemented. Please add your implementation to omnitool/omnibox/vm/win11setup/setupscripts/server/main.py.'
    }), 500


execute_impl = execute   # switch to execute_anything to allow any command. Please use with caution only for testing purposes.
```
Và hàm chụp màn hình kèm con trỏ chuột ([`server/main.py:L81-L95`](file:///home/thai/Downloads/omniparser/omnitool/omnibox/vm/win11setup/setupscripts/server/main.py#L81-L95)):
```python
@app.route('/screenshot', methods=['GET'])
def capture_screen_with_cursor():    
    cursor_path = os.path.join(os.path.dirname(__file__), "cursor.png")
    screenshot = pyautogui.screenshot()
    cursor_x, cursor_y = pyautogui.position()
    cursor = Image.open(cursor_path)
    # make the cursor smaller
    cursor = cursor.resize((int(cursor.width / 1.5), int(cursor.height / 1.5)))
    screenshot.paste(cursor, (cursor_x, cursor_y), cursor)

    # Convert PIL Image to bytes and send
    img_io = BytesIO()
    screenshot.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')
```

**Điểm quan trọng cần biết trong mã gốc `server/main.py`:**
- Ở dòng 54 của mã gốc Microsoft: `execute_impl = execute` mặc định trả về lỗi HTTP `500 Not implemented` vì lý do bảo mật mẫu, buộc người dùng phải tự sửa dòng 54 thành `execute_impl = execute_anything` nếu dùng máy ảo Windows.
- Ngược lại, trong tệp [`omnitool/linux_host_server.py`](file:///home/thai/Downloads/omniparser/omnitool/linux_host_server.py) mà chúng ta đã xây dựng cho máy Linux của bạn, endpoint `/execute` đã được triển khai hoàn chỉnh và hoạt động ngay lập tức, đồng thời tái sử dụng trực tiếp tệp ảnh `cursor.png` từ thư mục `omnibox/vm/win11setup/setupscripts/server/cursor.png`.

---

## 3. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm chứng tệp tài nguyên `cursor.png` trong `omnibox` được nạp và xử lý thu nhỏ `1.5x` chính xác bởi `PIL.Image`:

```bash
.venv/bin/python -c '
from PIL import Image
cursor = Image.open("omnitool/omnibox/vm/win11setup/setupscripts/server/cursor.png")
resized = cursor.resize((int(cursor.width / 1.5), int(cursor.height / 1.5)))
print("Original cursor.png:", cursor.size, cursor.mode, "| Resized (1/1.5):", resized.size)
'
```

**Kết quả thực thi thực tế:**
```text
Original cursor.png: (27, 40) RGBA | Resized (1/1.5): (18, 26)
```

