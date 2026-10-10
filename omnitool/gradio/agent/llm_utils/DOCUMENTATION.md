# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `omnitool/gradio/agent/llm_utils/`

Thư mục [`omnitool/gradio/agent/llm_utils/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils) chứa các lớp Client kết nối qua mạng tới **OmniParser Server** và các nhà cung cấp mô hình ngôn ngữ lớn (**Groq**, **OpenAI**, **DashScope Qwen**).

---

## 1. Cấu Trúc Các Tệp Trong `llm_utils/`

| Tệp | Số dòng | Vai trò cốt lõi |
| :--- | :---: | :--- |
| [`omniparserclient.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/omniparserclient.py) | 46 | Lớp `OmniParserClient`: Chụp màn hình từ cổng `5000`, mã hoá Base64, gửi `POST /parse/` sang OmniParser Server và định dạng danh sách phần tử `ID: 0..N`. |
| [`groqclient.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/groqclient.py) | 82 | Hàm `run_groq_interleaved()`: Giao tiếp với Groq API (`qwen/qwen3.8-27b` / R1), lọc bỏ đường dẫn ảnh khỏi lịch sử hội thoại, gộp các tin nhắn cùng `role` và bóc tách thẻ `</think>`. |
| [`oaiclient.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/oaiclient.py) | 62 | Hàm `run_oai_interleaved()`: Giao tiếp đa phương thức (Multimodal Text + Base64 Image) với OpenAI API (`gpt-4o`, `o1`, `o3-mini`) và Alibaba DashScope (`qwen2.5-vl-72b-instruct`). |
| [`utils.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/utils.py) | 13 | Các hàm tiện ích `is_image_path()` và `encode_image()`. |

---

## 2. Giải Thích Chi Tiết Kèm Mã Nguồn Thực Tế

### 2.1. Tệp [`omniparserclient.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/omniparserclient.py)

Toàn bộ mã nguồn thực tế ([`omniparserclient.py:L9-L46`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/omniparserclient.py#L9-L46)):
```python
class OmniParserClient:
    def __init__(self, 
                 url: str) -> None:
        self.url = url

    def __call__(self,):
        screenshot, screenshot_path = get_screenshot()
        screenshot_path = str(screenshot_path)
        image_base64 = encode_image(screenshot_path)
        response = requests.post(self.url, json={"base64_image": image_base64})
        if response.status_code != 200:
            raise RuntimeError(f"OmniParser Server error ({response.status_code}): {response.text}")
        response_json = response.json()
        print('omniparser latency:', response_json['latency'])

        som_image_data = base64.b64decode(response_json['som_image_base64'])
        screenshot_path_uuid = Path(screenshot_path).stem.replace("screenshot_", "")
        som_screenshot_path = f"{OUTPUT_DIR}/screenshot_som_{screenshot_path_uuid}.png"
        with open(som_screenshot_path, "wb") as f:
            f.write(som_image_data)
        
        response_json['width'] = screenshot.size[0]
        response_json['height'] = screenshot.size[1]
        response_json['original_screenshot_base64'] = image_base64
        response_json['screenshot_uuid'] = screenshot_path_uuid
        response_json = self.reformat_messages(response_json)
        return response_json
    
    def reformat_messages(self, response_json: dict):
        screen_info = ""
        for idx, element in enumerate(response_json["parsed_content_list"]):
            element['idx'] = idx
            if element['type'] == 'text':
                screen_info += f'ID: {idx}, Text: {element["content"]}\n'
            elif element['type'] == 'icon':
                screen_info += f'ID: {idx}, Icon: {element["content"]}\n'
        response_json['screen_info'] = screen_info
        return response_json
```
**Luồng xử lý từng bước:**
1. Gọi `get_screenshot()` để lấy ảnh chụp màn hình gốc từ `http://localhost:5000/screenshot` và lưu vào `./tmp/outputs/screenshot_<uuid>.png`.
2. Mã hoá ảnh gốc sang Base64 và gửi `POST` tới `self.url` (`http://localhost:8000/parse/` hoặc `https://xxxx.trycloudflare.com/parse/`).
3. Lưu ảnh đã vẽ khung số (`som_image_base64`) xuống `./tmp/outputs/screenshot_som_<uuid>.png`.
4. Gọi `reformat_messages()` biến danh sách `parsed_content_list` thành văn bản có cấu trúc:
   ```text
   ID: 0, Text: Google
   ID: 1, Icon: interactive button/input (center-middle)
   ```

---

### 2.2. Tệp [`groqclient.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/groqclient.py)

Toàn bộ mã nguồn thực tế ([`groqclient.py:L5-L82`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/groqclient.py#L5-L82)):
```python
def run_groq_interleaved(messages: list, system: str, model_name: str, api_key: str, max_tokens=256, temperature=0.6):
    api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")
    
    client = Groq(api_key=api_key)
    final_messages = [{"role": "system", "content": system}]

    if isinstance(messages, list):
        for item in messages:
            if isinstance(item, dict):
                role = item.get("role", "user")
                text_contents = []
                for cnt in item.get("content", []):
                    if isinstance(cnt, str):
                        if not is_image_path(cnt) and not cnt.endswith(".png"):
                            text_contents.append(cnt)
                    elif hasattr(cnt, "text") and getattr(cnt, "text", None):
                        text_contents.append(str(cnt.text))
                    elif hasattr(cnt, "input") and getattr(cnt, "input", None):
                        text_contents.append(f"Action: {cnt.input}")
                    else:
                        text_contents.append(str(cnt))
                
                if text_contents:
                    content_str = "\n".join(text_contents)
                    if final_messages and final_messages[-1]["role"] == role:
                        final_messages[-1]["content"] += "\n" + content_str
                    else:
                        final_messages.append({"role": role, "content": content_str})
            else:  # str
                final_messages.append({"role": "user", "content": str(item)})
    
    elif isinstance(messages, str):
        final_messages.append({"role": "user", "content": messages})

    # Ensure the user prompt ends with clear instruction to determine next action
    prompt_suffix = "\nPlease determine the next action for the current screen based on the detected bounding boxes to complete the task."
    if final_messages and final_messages[-1]["role"] == "user":
        final_messages[-1]["content"] += prompt_suffix
    else:
        final_messages.append({"role": "user", "content": prompt_suffix.strip()})

    try:
        target_model = model_name
        if not target_model or "deepseek" in target_model:
            target_model = "qwen/qwen3.8-27b"

        completion = client.chat.completions.create(
            model=target_model,
            messages=final_messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            top_p=0.95,
            stream=False,
        )
        
        msg_obj = completion.choices[0].message
        response = msg_obj.content or getattr(msg_obj, "reasoning", None) or ""
        if "</think>" in response:
            after_think = response.split("</think>")[-1].strip()
            final_answer = after_think if after_think else response
        else:
            final_answer = response

        final_answer = final_answer.replace("<output>", "").replace("</output>", "").strip()
        token_usage = completion.usage.total_tokens if completion.usage else 0
        return final_answer, token_usage
```
**Các kỹ thuật xử lý quan trọng trong `run_groq_interleaved`:**
1. **Lọc sạch đường dẫn ảnh (`not is_image_path(cnt)`):** Vì các mô hình suy luận trên Groq nhận thông tin màn hình qua danh sách `screen_info` trong `system`, các đường dẫn tệp `.png` được lọc bỏ để tránh làm nhiễu văn bản.
2. **Bảo toàn đúng `role` (`user` vs `assistant`) và gộp tin nhắn liên tiếp cùng `role`:** Giúp lịch sử các bước 1, 2, 3... chuẩn cấu trúc ChatML, không bị lỗi trả về chuỗi rỗng ở bước thứ 2.
3. **Bóc tách an toàn thẻ `</think>`:** Với các mô hình Reasoning sinh khối `<think>...</think>`, hàm tự động lấy phần JSON nằm sau `</think>`, nhưng nếu mô hình đặt toàn bộ câu trả lời bên trong `<think>` thì vẫn giữ nguyên `response` thay vì trả về rỗng.

---

### 2.3. Tệp [`oaiclient.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/oaiclient.py)

Đóng gói xen kẽ cả văn bản và ảnh Base64 (`data:image/jpeg;base64,...`) cho các mô hình VLM đa phương thức ([`oaiclient.py:L16-L30`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/oaiclient.py#L16-L30)):
```python
                for cnt in item["content"]:
                    if isinstance(cnt, str):
                        if is_image_path(cnt) and 'o3-mini' not in model_name:
                            # 03 mini does not support images
                            base64_image = encode_image(cnt)
                            content = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        else:
                            content = {"type": "text", "text": cnt}
                    else:
                        # in this case it is a text block from anthropic
                        content = {"type": "text", "text": str(cnt)}
                        
                    contents.append(content)
```

---

### 2.4. Tệp [`utils.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/utils.py)

Toàn bộ mã nguồn ([`utils.py:L1-L13`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/utils.py#L1-L13)):
```python
import base64

def is_image_path(text):
    image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif")
    if text.endswith(image_extensions):
        return True
    else:
        return False

def encode_image(image_path):
    """Encode image file to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
```

---

## 3. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm chứng trực tiếp `is_image_path`, `reformat_messages` của `OmniParserClient` và cuộc gọi thực tế tới Groq API qua `run_groq_interleaved`:

```bash
PYTHONPATH=omnitool/gradio .venv/bin/python -c '
from agent.llm_utils.utils import is_image_path
from agent.llm_utils.omniparserclient import OmniParserClient
from agent.llm_utils.groqclient import run_groq_interleaved

print("1. is_image_path check:", is_image_path("./tmp/outputs/screenshot_som_abc.png"), is_image_path("Click search bar"))

client = OmniParserClient(url="http://localhost:8000/parse/")
dummy_resp = {"parsed_content_list": [{"type": "text", "content": "Google"}, {"type": "icon", "content": "Search button"}]}
formatted = client.reformat_messages(dummy_resp)
print("2. OmniParserClient.reformat_messages:\n" + formatted["screen_info"].strip())

ans, tokens = run_groq_interleaved(
    messages=[{"role": "user", "content": ["Click on Search button"]}],
    system="Screen elements:\nID: 0, Text: Google\nID: 1, Icon: Search button\nOutput JSON with Reasoning, Next Action, Box ID.",
    model_name="qwen/qwen3.8-27b",
    api_key="gsk_your_groq_api_key_here",
    max_tokens=256
)
print("3. Live Groq API response (tokens=" + str(tokens) + "):\n" + ans)
'
```

**Kết quả thực thi thực tế:**
```text
1. is_image_path check: True False
2. OmniParserClient.reformat_messages:
ID: 0, Text: Google
ID: 1, Icon: Search button
3. Live Groq API response (tokens=164):
```json
{
    "Reasoning": "The user wants to click on the Search button, which corresponds to Box ID 1.",
    "Next Action": "left_click",
    "Box ID": 1
}
```
```

