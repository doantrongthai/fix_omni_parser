# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `omnitool/gradio/executor/` (Action Executor)

Thư mục [`omnitool/gradio/executor/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/executor) chứa lớp [`AnthropicExecutor`](file:///home/thai/Downloads/omniparser/omnitool/gradio/executor/anthropic_executor.py#L18-L72) — bộ phận đứng giữa `Actor` (`VLMAgent` / `AnthropicActor`) và `ComputerTool`. Khi `Actor` quyết định cần thực hiện hành động nào (ví dụ: di chuyển chuột tới tâm Box ID rồi click trái), `AnthropicExecutor` sẽ duyệt qua từng khối lệnh, kích hoạt `ComputerTool` chạy thực tế và đóng gói kết quả trả về cho vòng lặp tiếp theo.

---

## 1. Phân Tích Chi Tiết [`anthropic_executor.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/executor/anthropic_executor.py)

### 1.1. Khởi tạo `AnthropicExecutor` & Thực thi `tool_use` ([`anthropic_executor.py:L18-L72`](file:///home/thai/Downloads/omniparser/omnitool/gradio/executor/anthropic_executor.py#L18-L72))

```python
class AnthropicExecutor:
    def __init__(
        self, 
        output_callback: Callable[[BetaContentBlockParam], None], 
        tool_output_callback: Callable[[Any, str], None],
    ):
        self.tool_collection = ToolCollection(
            ComputerTool()
        )
        self.output_callback = output_callback
        self.tool_output_callback = tool_output_callback

    def __call__(self, response: BetaMessage, messages: list[BetaMessageParam]):
        new_message = {
            "role": "assistant",
            "content": cast(list[BetaContentBlockParam], response.content),
        }
        if new_message not in messages:
            messages.append(new_message)
        else:
            print("new_message already in messages, there are duplicates.")
        
        tool_result_content: list[BetaToolResultBlockParam] = []
        for content_block in cast(list[BetaContentBlock], response.content):
            self.output_callback(content_block, sender="bot")
            # Execute the tool
            if content_block.type == "tool_use":
                # Run the asynchronous tool execution in a synchronous context
                result = asyncio.run(self.tool_collection.run(
                    name=content_block.name,
                    tool_input=cast(dict[str, Any], content_block.input),
                ))
                
                self.output_callback(result, sender="bot")
                
                tool_result_content.append(
                    _make_api_tool_result(result, content_block.id)
                )

            display_messages = _message_display_callback(messages)
            
            # Send the messages to the gradio
            for user_msg, bot_msg in display_messages:
                yield [None, None], tool_result_content

        if not tool_result_content:
            return messages
        
        return tool_result_content
```

**Cơ chế hoạt động từng bước:**
1. **Ghi nhận phản hồi của Assistant vào lịch sử (`messages.append(new_message)`):** Lưu toàn bộ kế hoạch và các khối `BetaToolUseBlock` mà Agent vừa sinh ra vào mảng `messages` với `role: "assistant"`.
2. **Duyệt tuần tự từng `content_block` trong `response.content`:**
   - Khối thứ nhất thường là `BetaTextBlock` chứa phân tích (`Reasoning`, `Next Action`, `Box ID`, `box_centroid_coordinate`) $\rightarrow$ gửi qua `self.output_callback` để in lên giao diện Gradio.
   - Khối thứ hai (nếu có `Box ID`) là `BetaToolUseBlock(name='computer', input={'action': 'mouse_move', 'coordinate': [x, y]})` $\rightarrow$ gọi `asyncio.run(self.tool_collection.run(...))` để di chuyển con trỏ chuột thật tới `[x, y]`.
   - Khối thứ ba là `BetaToolUseBlock` cho hành động chính (`left_click`, `type`, `key`...) $\rightarrow$ gọi `asyncio.run(self.tool_collection.run(...))` để thực hiện thao tác.
3. **Cập nhật giao diện tức thì (`yield`):** Sau mỗi khối lệnh, `yield [None, None], tool_result_content` trả quyền điều khiển tạm thời về cho `app.py` để trình duyệt vẽ ngay dòng trạng thái mới (`Moved mouse to (x, y)`, `Performed left_click`).

---

### 1.2. Đóng gói kết quả công cụ `_make_api_tool_result` ([`anthropic_executor.py:L93-L126`](file:///home/thai/Downloads/omniparser/omnitool/gradio/executor/anthropic_executor.py#L93-L126))

```python
def _make_api_tool_result(
    result: ToolResult, tool_use_id: str
) -> BetaToolResultBlockParam:
    """Convert an agent ToolResult to an API ToolResultBlockParam."""
    tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
    is_error = False
    if result.error:
        is_error = True
        tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
    else:
        if result.output:
            tool_result_content.append(
                {
                    "type": "text",
                    "text": _maybe_prepend_system_tool_result(result, result.output),
                }
            )
        if result.base64_image:
            tool_result_content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": result.base64_image,
                    },
                }
            )
    return {
        "type": "tool_result",
        "content": tool_result_content,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
    }
```
- Chuyển đối tượng nội bộ `ToolResult(output=..., error=..., base64_image=...)` thành cấu trúc chuẩn `{"type": "tool_result", "tool_use_id": ..., "is_error": ...}` để lưu trữ thống nhất cho cả VLM và Anthropic Claude.

---

## 2. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm chứng trực tiếp hàm `_make_api_tool_result` và luồng thực thi lệnh `wait` thông qua `AnthropicExecutor`:

```bash
PYTHONPATH=omnitool/gradio .venv/bin/python -c '
import uuid
from anthropic.types.beta import BetaMessage, BetaTextBlock, BetaToolUseBlock, BetaUsage
from executor.anthropic_executor import AnthropicExecutor, _make_api_tool_result
from tools.base import ToolResult

# 1. Kiểm chứng _make_api_tool_result
tr = ToolResult(output="Performed left_click")
api_res = _make_api_tool_result(tr, "toolu_test123")
print("1. _make_api_tool_result:", api_res)

# 2. Kiểm chứng AnthropicExecutor chạy lệnh "wait" thực tế
logs = []
executor = AnthropicExecutor(
    output_callback=lambda msg, sender="bot": logs.append(str(msg)),
    tool_output_callback=lambda out, tid: None
)
msg = BetaMessage(
    id="msg_1",
    content=[
        BetaTextBlock(text="Waiting 1s", type="text"),
        BetaToolUseBlock(id="toolu_wait", name="computer", input={"action": "wait"}, type="tool_use")
    ],
    model="",
    role="assistant",
    type="message",
    stop_reason="tool_use",
    usage=BetaUsage(input_tokens=0, output_tokens=0)
)
history = []
for _, tool_results in executor(msg, history):
    pass
print("2. Callback logs:", logs)
print("3. Final tool_results:", tool_results)
'
```

**Kết quả thực thi thực tế:**
```text
screen size: 1920, 1200
1. _make_api_tool_result: {'type': 'tool_result', 'content': [{'type': 'text', 'text': 'Performed left_click'}], 'tool_use_id': 'toolu_test123', 'is_error': False}
action: wait, text: None, coordinate: None, is_scaling: False
2. Callback logs: ["BetaTextBlock(citations=None, text='Waiting 1s', type='text')", "BetaToolUseBlock(id='toolu_wait', input={'action': 'wait'}, name='computer', type='tool_use')", "ToolResult(output='Performed wait', error=None, base64_image=None, system=None)"]
3. Final tool_results: [{'type': 'tool_result', 'content': [{'type': 'text', 'text': 'Performed wait'}], 'tool_use_id': 'toolu_wait', 'is_error': False}]
```

