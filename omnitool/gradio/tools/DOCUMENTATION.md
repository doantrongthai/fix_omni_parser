# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `omnitool/gradio/tools/` (Hardware & Screen Control Tools)

Thư mục [`omnitool/gradio/tools/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools) chứa lớp thực thi cấp thấp nhất ở phía Agent Client, trực tiếp biến các hành động trừu tượng (`left_click`, `mouse_move`, `type`, `key`, `scroll_down`, `screenshot`...) thành các lời gọi HTTP tới cổng `5000` (`linux_host_server.py` hoặc `omnibox` VM).

---

## 1. Cấu Trúc Các Tệp Trong `omnitool/gradio/tools/`

| Tệp | Số dòng | Vai trò cốt lõi |
| :--- | :---: | :--- |
| [`computer.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/computer.py) | 329 | Lớp `ComputerTool`: Chứa toàn bộ logic điều khiển chuột/bàn phím thông qua hàm `send_to_vm()`, lấy độ phân giải màn hình `get_screen_size()` và co giãn hệ toạ độ `scale_coordinates()`. |
| [`screen_capture.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/screen_capture.py) | 29 | Hàm `get_screenshot()`: Gọi `GET http://localhost:5000/screenshot` để tải ảnh chụp màn hình hiện tại và lưu vào `./tmp/outputs/screenshot_<uuid>.png`. |
| [`base.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/base.py) | 66 | Định nghĩa lớp cơ sở trừu tượng `BaseAnthropicTool`, cấu trúc dữ liệu bất biến `ToolResult`, `ToolFailure` và ngoại lệ `ToolError`. |
| [`collection.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/collection.py) | 35 | Lớp `ToolCollection`: Quản lý danh sách công cụ theo tên (`"computer"`) và bắt lỗi `ToolError` để trả về `ToolFailure` an toàn. |
| [`__init__.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/__init__.py) | 12 | Xuất khẩu các lớp `ComputerTool`, `ToolCollection`, `ToolResult`, `ToolFailure`, `BaseAnthropicTool`. |

---

## 2. Giải Thích Chi Tiết Kèm Mã Nguồn Thực Tế

### 2.1. Tệp [`computer.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/computer.py)

#### A. Tự động phát hiện độ phân giải màn hình khi khởi tạo `get_screen_size` ([`computer.py:L310-L329`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/computer.py#L310-L329)):
```python
    def get_screen_size(self):
        """Return width and height of the screen"""
        try:
            response = requests.post(
                f"http://localhost:5000/execute",
                headers={'Content-Type': 'application/json'},
                json={"command": ["python", "-c", "import pyautogui; print(pyautogui.size())"]},
                timeout=90
            )
            if response.status_code != 200:
                raise ToolError(f"Failed to get screen size. Status code: {response.status_code}")
            
            output = response.json()['output'].strip()
            match = re.search(r'Size\(width=(\d+),\s*height=(\d+)\)', output)
            if not match:
                raise ToolError(f"Could not parse screen size from output: {output}")
            width, height = map(int, match.groups())
            return width, height
        except requests.exceptions.RequestException as e:
            raise ToolError(f"An error occurred while trying to get screen size: {str(e)}")
```
- Ngay khi `ComputerTool()` được khởi tạo, nó gửi lệnh `pyautogui.size()` sang cổng `5000`, dùng biểu thức chính quy `r'Size\(width=(\d+),\s*height=(\d+)\)'` bóc tách chiều rộng và chiều cao thật của màn hình (ví dụ `1920, 1200`).

#### B. Hàm gửi lệnh điều khiển sang Host `send_to_vm` ([`computer.py:L227-L257`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/computer.py#L227-L257)):
```python
    def send_to_vm(self, action: str):
        """
        Executes a python command on the server. Only return tuple of x,y when action is "pyautogui.position()"
        """
        prefix = "import pyautogui; pyautogui.FAILSAFE = False;"
        command_list = ["python", "-c", f"{prefix} {action}"]
        parse = action == "pyautogui.position()"
        if parse:
            command_list[-1] = f"{prefix} print({action})"

        try:
            print(f"sending to vm: {command_list}")
            response = requests.post(
                f"http://localhost:5000/execute", 
                headers={'Content-Type': 'application/json'},
                json={"command": command_list},
                timeout=90
            )
            time.sleep(0.7) # avoid async error as actions take time to complete
            print(f"action executed")
            if response.status_code != 200:
                raise ToolError(f"Failed to execute command. Status code: {response.status_code}")
            if parse:
                output = response.json()['output'].strip()
                match = re.search(r'Point\(x=(\d+),\s*y=(\d+)\)', output)
                if not match:
                    raise ToolError(f"Could not parse coordinates from output: {output}")
                x, y = map(int, match.groups())
                return x, y
        except requests.exceptions.RequestException as e:
            raise ToolError(f"An error occurred while trying to execute the command: {str(e)}")
```
- Mọi thao tác chuột/phím đều được gắn tiền tố `import pyautogui; pyautogui.FAILSAFE = False;` để tránh ngoại lệ `FailSafeException` khi con trỏ chuột di chuyển sát góc màn hình `(0, 0)`.
- Nghỉ `time.sleep(0.7)` sau mỗi thao tác để giao diện ứng dụng kịp phản hồi (mở menu, tải trang, hiển thị con trỏ) trước khi bước tiếp theo chụp màn hình.

#### C. Xử lý các hành động `mouse_move`, `type`, `key`, `left_click`, `scroll` ([`computer.py:L143-L225`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/computer.py#L143-L225)):
```python
            if action == "mouse_move":
                self.send_to_vm(f"pyautogui.moveTo({x}, {y})")
                return ToolResult(output=f"Moved mouse to ({x}, {y})")
...
            if action == "key":
                # Handle key combinations
                keys = text.split('+')
                for key in keys:
                    key = self.key_conversion.get(key.strip(), key.strip())
                    key = key.lower()
                    self.send_to_vm(f"pyautogui.keyDown('{key}')")  # Press down each key
                for key in reversed(keys):
                    key = self.key_conversion.get(key.strip(), key.strip())
                    key = key.lower()
                    self.send_to_vm(f"pyautogui.keyUp('{key}')")    # Release each key in reverse order
                return ToolResult(output=f"Pressed keys: {text}")
            
            elif action == "type":
                # default click before type
                self.send_to_vm("pyautogui.click()")
                self.send_to_vm(f"pyautogui.typewrite({repr(text)}, interval={TYPING_DELAY_MS / 1000})")
                self.send_to_vm("pyautogui.press('enter')")
                screenshot_base64 = (await self.screenshot()).base64_image
                return ToolResult(output=text, base64_image=screenshot_base64)
```
**Lưu ý đặc biệt về hành động `type`:**
- Khi LLM chọn hành động `"Next Action": "type"` (và kèm theo `"Box ID"`), `VLMAgent` sẽ phát lệnh `mouse_move` tới tâm ô tìm kiếm trước, sau đó lệnh `type` trong `ComputerTool` sẽ tự động thực hiện chuỗi **3 thao tác liên hoàn**:
  1. `pyautogui.click()` (click chuột trái để focus vào ô nhập liệu),
  2. `pyautogui.typewrite(..., interval=0.012)` (gõ từng ký tự với độ trễ 12ms),
  3. `pyautogui.press('enter')` (nhấn phím Enter ngay sau khi gõ xong).

---

### 2.2. Tệp [`screen_capture.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/screen_capture.py)

Toàn bộ mã nguồn ([`screen_capture.py:L10-L29`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/screen_capture.py#L10-L29)):
```python
def get_screenshot(resize: bool = False, target_width: int = 1920, target_height: int = 1080):
    """Capture screenshot by requesting from HTTP endpoint - returns native resolution unless resized"""
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"screenshot_{uuid4().hex}.png"
    
    try:
        response = requests.get('http://localhost:5000/screenshot')
        if response.status_code != 200:
            raise ToolError(f"Failed to capture screenshot: HTTP {response.status_code}")
        
        screenshot = Image.open(BytesIO(response.content))
        
        if resize and screenshot.size != (target_width, target_height):
            screenshot = screenshot.resize((target_width, target_height))
        screenshot.save(path)
        return screenshot, path
    except Exception as e:
        raise ToolError(f"Failed to capture screenshot: {str(e)}")
```

---

### 2.3. Tệp [`base.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/base.py) & [`collection.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/collection.py)

Trong [`base.py:L23-L55`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/base.py#L23-L55), lớp `ToolResult` là một `@dataclass(kw_only=True, frozen=True)` hỗ trợ toán tử cộng `__add__` để nối kết quả hai lần chạy công cụ và hàm `.replace(**kwargs)`.

Trong [`collection.py:L27-L34`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/collection.py#L27-L34):
```python
    async def run(self, *, name: str, tool_input: dict[str, Any]) -> ToolResult:
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            return await tool(**tool_input)
        except ToolError as e:
            return ToolFailure(error=e.message)
```
- Bắt mọi ngoại lệ `ToolError` (ví dụ thiếu tham số hoặc toạ độ ngoài màn hình) và chuyển thành đối tượng `ToolFailure(error=e.message)` để chương trình không bị sập giữa chừng.

---

## 3. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm chứng trực tiếp `ComputerTool`, `ToolCollection` và `get_screenshot` với dịch vụ Host đang chạy tại cổng `5000`:

```bash
PYTHONPATH=omnitool/gradio .venv/bin/python -c '
import asyncio
from tools import ComputerTool, ToolCollection
from tools.screen_capture import get_screenshot

# 1. Kiểm chứng get_screenshot()
img, path = get_screenshot()
print("1. get_screenshot(): size=", img.size, "| saved_to=", path)

# 2. Kiểm chứng ComputerTool & ToolCollection với hành động cursor_position
collection = ToolCollection(ComputerTool())
res_pos = asyncio.run(collection.run(name="computer", tool_input={"action": "cursor_position"}))
print("2. cursor_position ToolResult:", res_pos)

# 3. Kiểm chứng bắt lỗi an toàn khi truyền thiếu text cho key
res_err = asyncio.run(collection.run(name="computer", tool_input={"action": "key"}))
print("3. Safe ToolFailure on missing arg:", res_err)
'
```

**Kết quả thực thi thực tế:**
```text
1. get_screenshot(): size= (1920, 1200) | saved_to= tmp/outputs/screenshot_21048b9c18a34c91b5e004f87a96772a.png
screen size: 1920, 1200
action: cursor_position, text: None, coordinate: None, is_scaling: False
sending to vm: ['python', '-c', 'import pyautogui; pyautogui.FAILSAFE = False; print(pyautogui.position())']
action executed
2. cursor_position ToolResult: ToolResult(output='X=1280,Y=800', error=None, base64_image=None, system=None)
action: key, text: None, coordinate: None, is_scaling: False
3. Safe ToolFailure on missing arg: ToolFailure(output=None, error='text is required for key', base64_image=None, system=None)
```

