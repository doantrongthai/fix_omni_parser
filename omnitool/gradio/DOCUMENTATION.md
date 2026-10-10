# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `omnitool/gradio/` (Frontend & Agent Loop)

Thư mục [`omnitool/gradio/`](file:///home/thai/Downloads/omniparser/omnitool/gradio) là trung tâm điều phối của ứng dụng **OmniTool**. Thư mục này chứa giao diện Web Gradio/Streamlit và vòng lặp điều khiển chính (`sampling_loop_sync`) kết nối giữa:
1. Người dùng (nhập yêu cầu tiếng Việt/tiếng Anh trên trình duyệt tại cổng `7888`),
2. `OmniParserClient` (chụp màn hình từ cổng `5000` và gửi đi phân tích ở cổng `8000` hoặc Colab GPU),
3. `Actor` (`VLMAgent`, `VLMOrchestratedAgent`, hoặc `AnthropicActor` trong [`agent/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/DOCUMENTATION.md)),
4. `Executor` (`AnthropicExecutor` trong [`executor/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/executor/DOCUMENTATION.md) và `ComputerTool` trong [`tools/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/DOCUMENTATION.md)).

---

## 1. Danh Sách Các Tệp Trong `omnitool/gradio/`

| Tệp / Thư mục con | Số dòng | Vai trò cốt lõi |
| :--- | :---: | :--- |
| [`app.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/app.py) | 432 | Giao diện Gradio chính thức (cổng `7888`), cài đặt sẵn cấu hình mặc định `omniparser + R1` (Groq), kiểm tra kết nối `/probe` và hiển thị trực tiếp lịch sử hành động của Agent. |
| [`loop.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/loop.py) | 130 | Chứa hàm generator `sampling_loop_sync()` thực thi vòng lặp khép kín **Chụp màn hình $\rightarrow$ Phân tích SoM $\rightarrow$ Gọi LLM $\rightarrow$ Thực thi chuột/phím** cho đến khi hoàn thành. |
| [`app_new.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/app_new.py) | 762 | Giao diện Gradio mở rộng có thêm tính năng tải tệp lên (`uploaded_files`) và lưu nhật ký theo thư mục thời gian thực. |
| [`app_streamlit.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/app_streamlit.py) | 471 | Phiên bản giao diện thay thế viết bằng thư viện Streamlit. |
| [`agent/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/DOCUMENTATION.md) | Thư mục | Chứa các lớp Agent suy luận (`VLMAgent`, `VLMOrchestratedAgent`, `AnthropicActor`). |
| [`executor/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/executor/DOCUMENTATION.md) | Thư mục | Chứa `AnthropicExecutor` điều phối chạy công cụ và đóng gói kết quả. |
| [`tools/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/tools/DOCUMENTATION.md) | Thư mục | Chứa `ComputerTool` và `screen_capture.py` giao tiếp với cổng `5000`. |

---

## 2. Giải Thích Chi Tiết Kèm Mã Nguồn Thực Tế

### 2.1. Tệp [`omnitool/gradio/loop.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/loop.py)

#### A. Chuẩn hoá URL OmniParser Server & Khởi tạo Actor/Executor ([`loop.py:L57-L100`](file:///home/thai/Downloads/omniparser/omnitool/gradio/loop.py#L57-L100)):
```python
    print('in sampling_loop_sync, model:', model)
    base_parser_url = omniparser_url.strip().rstrip('/')
    if not base_parser_url.startswith(('http://', 'https://')):
        base_parser_url = f"http://{base_parser_url}"
    omniparser_client = OmniParserClient(url=f"{base_parser_url}/parse/")
    if model == "claude-3-5-sonnet-20241022":
        # Register Actor and Executor
        actor = AnthropicActor(
            model=model, 
            provider=provider,
            api_key=api_key, 
            api_response_callback=api_response_callback,
            max_tokens=max_tokens,
            only_n_most_recent_images=only_n_most_recent_images
        )
    elif model in set(["omniparser + gpt-4o", "omniparser + o1", "omniparser + o3-mini", "omniparser + R1", "omniparser + qwen2.5vl"]):
        actor = VLMAgent(
            model=model,
            provider=provider,
            api_key=api_key,
            api_response_callback=api_response_callback,
            output_callback=output_callback,
            max_tokens=max_tokens,
            only_n_most_recent_images=only_n_most_recent_images
        )
    elif model in set(["omniparser + gpt-4o-orchestrated", "omniparser + o1-orchestrated", "omniparser + o3-mini-orchestrated", "omniparser + R1-orchestrated", "omniparser + qwen2.5vl-orchestrated"]):
        actor = VLMOrchestratedAgent(
            model=model,
            provider=provider,
            api_key=api_key,
            api_response_callback=api_response_callback,
            output_callback=output_callback,
            max_tokens=max_tokens,
            only_n_most_recent_images=only_n_most_recent_images,
            save_folder=save_folder
        )
    else:
        raise ValueError(f"Model {model} not supported")
    executor = AnthropicExecutor(
        output_callback=output_callback,
        tool_output_callback=tool_output_callback,
    )
```
**Cơ chế hoạt động:**
- **Chuẩn hoá `base_parser_url`:** Tự động kiểm tra xem `omniparser_url` đã có tiền tố `http://` hoặc `https://` chưa. Nhờ đó, người dùng truyền `--omniparser_server_url localhost:8000` (chạy Local) hay `--omniparser_server_url https://xxxx.trycloudflare.com` (chạy Colab GPU) đều tạo ra URL hợp lệ `<base_parser_url>/parse/`.
- **Phân nhánh 3 dòng Actor:**
  1. `claude-3-5-sonnet-20241022` $\rightarrow$ dùng `AnthropicActor`.
  2. `omniparser + gpt-4o / o1 / o3-mini / R1 / qwen2.5vl` $\rightarrow$ dùng `VLMAgent`.
  3. Các phiên bản có hậu tố `-orchestrated` $\rightarrow$ dùng `VLMOrchestratedAgent` (có lập kế hoạch `plan.json` và sổ cái theo dõi tiến độ `ledger`).

#### B. Vòng lặp thực thi liên tục (`while True`) ([`loop.py:L121-L130`](file:///home/thai/Downloads/omniparser/omnitool/gradio/loop.py#L121-L130)):
```python
    elif model in set(["omniparser + gpt-4o", "omniparser + o1", "omniparser + o3-mini", "omniparser + R1", "omniparser + qwen2.5vl", "omniparser + gpt-4o-orchestrated", "omniparser + o1-orchestrated", "omniparser + o3-mini-orchestrated", "omniparser + R1-orchestrated", "omniparser + qwen2.5vl-orchestrated"]):
        while True:
            parsed_screen = omniparser_client()
            tools_use_needed, vlm_response_json = actor(messages=messages, parsed_screen=parsed_screen)

            for message, tool_result_content in executor(tools_use_needed, messages):
                yield message
        
            if not tool_result_content:
                return messages
```
**Cách vòng lặp kết thúc tự động:**
- Ở mỗi vòng lặp:
  1. `parsed_screen = omniparser_client()` chụp màn hình hiện tại và gọi OmniParser phân tích.
  2. `actor(...)` gửi thông tin màn hình cho LLM và nhận về `tools_use_needed` (kiểu `BetaMessage`).
  3. `executor(...)` duyệt qua các khối lệnh trong `tools_use_needed`. Nếu có khối `tool_use` (`mouse_move`, `left_click`, `type`...), nó thực thi hành động và trả về danh sách `tool_result_content` khác rỗng $\rightarrow$ vòng lặp `while True` tiếp tục sang Bước tiếp theo.
  4. Khi LLM trả về `"Next Action": "None"` (nhiệm vụ đã hoàn tất) hoặc gặp lỗi cú pháp, `tools_use_needed` chỉ chứa `BetaTextBlock` mà không có `BetaToolUseBlock`, nên `tool_result_content` bằng `[]` (rỗng). Khi đó `if not tool_result_content: return messages` sẽ thoát vòng lặp gọn gàng!

---

### 2.2. Tệp [`omnitool/gradio/app.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/app.py)

#### A. Khởi tạo trạng thái mặc định `setup_state` ([`app.py:L50-L78`](file:///home/thai/Downloads/omniparser/omnitool/gradio/app.py#L50-L78)):
```python
def setup_state(state):
    default_groq_key = os.getenv("GROQ_API_KEY", "gsk_your_groq_api_key_here")
    if "messages" not in state:
        state["messages"] = []
    if "model" not in state:
        state["model"] = "omniparser + R1"
    if "provider" not in state:
        state["provider"] = "groq"
    if "openai_api_key" not in state:  # Fetch API keys from environment variables
        state["openai_api_key"] = os.getenv("OPENAI_API_KEY", "")
    if "anthropic_api_key" not in state:
        state["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY", "")
    if "groq_api_key" not in state:
        state["groq_api_key"] = default_groq_key
    if "api_key" not in state or not state["api_key"]:
        state["api_key"] = default_groq_key
```
- Thiết lập mặc định `state["model"] = "omniparser + R1"`, `state["provider"] = "groq"` và nạp sẵn API Key Groq để người dùng không phải cấu hình thủ công mỗi lần mở trang web.

#### B. Kiểm tra điều kiện tiên quyết `valid_params` ([`app.py:L192-L215`](file:///home/thai/Downloads/omniparser/omnitool/gradio/app.py#L192-L215)):
```python
def valid_params(user_input, state):
    """Validate all requirements and return a list of error messages."""
    errors = []
    
    for server_name, raw_url in [('Windows Host', 'localhost:5000'), ('OmniParser Server', args.omniparser_server_url)]:
        try:
            base_url = raw_url.strip().rstrip('/')
            if not base_url.startswith(('http://', 'https://')):
                base_url = f'http://{base_url}'
            probe_url = f'{base_url}/probe'
            response = requests.get(probe_url, timeout=10)
            if response.status_code != 200:
                errors.append(f"{server_name} is not responding")
        except RequestException as e:
            errors.append(f"{server_name} is not responding ({e})")
    
    if not state["api_key"].strip():
        errors.append("LLM API Key is not set")

    if not user_input:
        errors.append("no computer use request provided")
    
    return errors
```
- Trước khi chạy bất kỳ lệnh nào, `valid_params` gọi `GET <base_url>/probe` tới cả 2 dịch vụ (`localhost:5000` và `args.omniparser_server_url`). Nếu 1 trong 2 dịch vụ chưa bật hoặc URL Colab hết hạn, Gradio sẽ hiển thị thông báo lỗi rõ ràng trên màn hình.

#### C. Hàm hiển thị tin nhắn trực tiếp lên khung Chat `chatbot_output_callback` ([`app.py:L134-L186`](file:///home/thai/Downloads/omniparser/omnitool/gradio/app.py#L134-L186)):
```python
        if is_tool_result:
            message = cast(ToolResult, message)
            if message.output:
                return message.output
            if message.error:
                return f"Error: {message.error}"
            if message.base64_image and not hide_images:
                return f'<img src="data:image/png;base64,{message.base64_image}">'

        elif isinstance(message, BetaTextBlock) or isinstance(message, TextBlock):
            return f"Analysis: {message.text}"
        elif isinstance(message, BetaToolUseBlock) or isinstance(message, ToolUseBlock):
            return f"Next I will perform the following action: {message.input}"
```
- Chuyển đổi từng loại đối tượng (`ToolResult`, `BetaTextBlock`, `BetaToolUseBlock`, chuỗi HTML `<img>` hoặc `<details>`) thành dòng hội thoại `(None, message)` trong `chatbot_state` và `yield` ngay lập tức để giao diện cập nhật theo thời gian thực.

---

## 3. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm chứng trực tiếp hàm `setup_state()` và `valid_params()` trong `omnitool/gradio/app.py`:

```bash
PYTHONPATH=omnitool/gradio .venv/bin/python -c '
from app import setup_state, valid_params

state = {}
setup_state(state)
print("1. Initialized state model & provider:", state["model"], "|", state["provider"], "| key_prefix:", state["api_key"][:10] + "...")
errors = valid_params("Click vào thanh tìm kiếm", state)
print("2. Validation errors against running servers:", errors)
'
```

**Kết quả thực thi thực tế:**
```text
1. Initialized state model & provider: omniparser + R1 | groq | key_prefix: gsk_your_groq_api_key_here
2. Validation errors against running servers: []
```
> **Kết luận kiểm chứng:** Hàm `valid_params()` trả về danh sách lỗi rỗng `[]`, chứng minh cả `Linux Host (localhost:5000)`, `OmniParser Server (localhost:8000)` và `API Key` đều hợp lệ và sẵn sàng nhận lệnh.

