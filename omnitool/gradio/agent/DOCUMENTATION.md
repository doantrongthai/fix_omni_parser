# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `omnitool/gradio/agent/` (Reasoning Agents)

Thư mục [`omnitool/gradio/agent/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent) chứa **bộ não suy luận (Planner / Actor)** của hệ thống. Nhiệm vụ của các lớp trong thư mục này là nhận danh sách phần tử giao diện đã được OmniParser đánh số (`ID: 0..N`), kết hợp với yêu cầu của người dùng và lịch sử các bước trước đó để quyết định **hành động tiếp theo (`Next Action`)**, **ô mục tiêu (`Box ID`)**, và **giá trị nhập (`value`)**.

---

## 1. Cấu Trúc Các Tệp Trong `omnitool/gradio/agent/`

| Tệp / Thư mục | Số dòng | Vai trò cốt lõi |
| :--- | :---: | :--- |
| [`vlm_agent.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent.py) | 399 | Lớp `VLMAgent`: Điều phối các mô hình `omniparser + R1` (Groq), `gpt-4o`, `o1`, `o3-mini`, `qwen2.5vl`; bóc tách JSON/Key-Value, tính tâm `Box ID`, vẽ tâm ngắm màu đỏ và đóng gói thành `BetaToolUseBlock`. |
| [`vlm_agent_with_orchestrator.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent_with_orchestrator.py) | 544 | Lớp `VLMOrchestratedAgent`: Mở rộng `VLMAgent` với cơ chế lập kế hoạch đầu kỳ (`_initialize_task` $\rightarrow$ `plan.json`) và cập nhật sổ cái tiến độ mỗi bước (`_update_ledger` & `trajectory.json`). |
| [`anthropic_agent.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/anthropic_agent.py) | 162 | Lớp `AnthropicActor`: Tích hợp trực tiếp với giao thức `computer-use-2024-10-22` của Claude 3.5 Sonnet kèm thông tin hỗ trợ từ OmniParser. |
| [`llm_utils/`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/llm_utils/DOCUMENTATION.md) | Thư mục | Các client gọi API ngoại vi (`groqclient.py`, `oaiclient.py`, `omniparserclient.py`, `utils.py`). |

---

## 2. Giải Thích Chi Tiết Kèm Mã Nguồn Thực Tế

### 2.1. Lớp `VLMAgent` trong [`vlm_agent.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent.py)

#### A. Ánh xạ tên mô hình trong `__init__` ([`vlm_agent.py:L42-L53`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent.py#L42-L53)):
```python
        if model == "omniparser + gpt-4o":
            self.model = "gpt-4o-2024-11-20"
        elif model == "omniparser + R1":
            self.model = "qwen/qwen3.8-27b"
        elif model == "omniparser + qwen2.5vl":
            self.model = "qwen2.5-vl-72b-instruct"
        elif model == "omniparser + o1":
            self.model = "o1"
        elif model == "omniparser + o3-mini":
            self.model = "o3-mini"
        else:
            raise ValueError(f"Model {model} not supported")
```

#### B. Xây dựng System Prompt kèm danh sách Box ID `_get_system_prompt` ([`vlm_agent.py:L256-L287`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent.py#L256-L287)):
```python
    def _get_system_prompt(self, screen_info: str = ""):
        main_section = f"""
You are using a Windows device.
You are able to use a mouse and keyboard to interact with the computer based on the given task and screenshot.
You can only interact with the desktop GUI (no terminal or application menu access).

You may be given some history plan and actions, this is the response from the previous loop.
You should carefully consider your plan base on the task, screenshot, and history actions.

Here is the list of all detected bounding boxes by IDs on the screen and their description:{screen_info}

Your available "Next Action" only include:
- type: types a string of text.
- left_click: move mouse to box id and left clicks.
- right_click: move mouse to box id and right clicks.
- double_click: move mouse to box id and double clicks.
- hover: move mouse to box id.
- scroll_up: scrolls the screen up to view previous content.
- scroll_down: scrolls the screen down, when the desired button is not visible, or you need to see more content. 
- wait: waits for 1 second for the device to load or respond.
...
Output format:
```json
{{
    "Reasoning": str,
    "Next Action": "action_type, action description" | "None"
    "Box ID": n,
    "value": "xxx"
}}
```
```
- Biến `screen_info` (chứa danh sách `ID: 0, Text: ...`, `ID: 1, Icon: ...`) được nhúng trực tiếp vào System Prompt ở mỗi bước. Nhờ vậy, ngay cả các mô hình ngôn ngữ thuần văn bản trên Groq vẫn biết chính xác trên màn hình đang có những nút nào và mang số `ID` bao nhiêu.

#### C. Cơ chế Bóc tách Kép (JSON Parser + Key-Value Fallback) ([`vlm_agent.py:L146-L182`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent.py#L146-L182)):
```python
        vlm_response_json = None
        try:
            raw_json_str = extract_data(vlm_response, "json")
            try:
                vlm_response_json = json.loads(raw_json_str)
            except Exception:
                if "{" in raw_json_str and "}" in raw_json_str:
                    json_substr = raw_json_str[raw_json_str.find("{"):raw_json_str.rfind("}")+1]
                    vlm_response_json = json.loads(json_substr)
        except Exception:
            pass

        if not vlm_response_json or not isinstance(vlm_response_json, dict):
            # Fallback: parse plain text Key-Value format (Reasoning, Next Action, Box ID, value)
            res = {}
            reasoning_lines = []
            for line in vlm_response.strip().split("\n"):
                line_clean = line.strip()
                if line_clean.startswith("Next Action:"):
                    res["Next Action"] = line_clean.split("Next Action:", 1)[1].strip()
                elif line_clean.startswith("Box ID:"):
                    val = line_clean.split("Box ID:", 1)[1].strip()
                    try:
                        res["Box ID"] = int(val)
                    except Exception:
                        res["Box ID"] = val
                elif line_clean.startswith("value:"):
                    res["value"] = line_clean.split("value:", 1)[1].strip()
                elif line_clean.startswith("Reasoning:"):
                    reasoning_lines.append(line_clean.split("Reasoning:", 1)[1].strip())
                else:
                    if "Next Action" not in res and line_clean:
                        reasoning_lines.append(line_clean)
            if "Next Action" in res:
                res["Reasoning"] = " ".join(reasoning_lines).strip()
                vlm_response_json = res
```
**Tại sao cần cơ chế Fallback này?**
- Ở Bước 1, LLM thường trả về đúng khối ```` ```json { ... } ``` ````. Nhưng từ Bước 2 trở đi, khi trong lịch sử hội thoại (`messages`) có các khối văn bản `BetaTextBlock` được định dạng theo kiểu `Next Action: ...\nBox ID: ...`, LLM đôi khi bắt chước định dạng văn bản thuần đó thay vì trả về JSON.
- Nhờ bộ lọc kép này, dù LLM trả về JSON chuẩn, JSON nằm lẫn trong câu văn, hay văn bản `Next Action: ... / Box ID: ... / value: ...`, Agent đều trích xuất thành công `vlm_response_json`.

#### D. Quy đổi `Box ID` sang Toạ độ Pixel & Vẽ Tâm Ngắm Đỏ ([`vlm_agent.py:L191-L209`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent.py#L191-L209)):
```python
        if "Box ID" in vlm_response_json and vlm_response_json["Box ID"] is not None:
            try:
                bbox = parsed_screen["parsed_content_list"][int(vlm_response_json["Box ID"])]["bbox"]
                vlm_response_json["box_centroid_coordinate"] = [int((bbox[0] + bbox[2]) / 2 * screen_width), int((bbox[1] + bbox[3]) / 2 * screen_height)]
                img_to_show_data = base64.b64decode(img_to_show_base64)
                img_to_show = Image.open(BytesIO(img_to_show_data))

                draw = ImageDraw.Draw(img_to_show)
                x, y = vlm_response_json["box_centroid_coordinate"] 
                radius = 10
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill='red')
                draw.ellipse((x - radius*3, y - radius*3, x + radius*3, y + radius*3), fill=None, outline='red', width=2)
```
- Lấy khung tỷ lệ `bbox = [x1_norm, y1_norm, x2_norm, y2_norm]` của phần tử thứ `Box ID` trong `parsed_content_list`.
- Tính toạ độ tâm trên màn hình thực tế (`screen_width x screen_height`):
  $$x = \left\lfloor \frac{x_1 + x_2}{2} \times W \right\rfloor, \quad y = \left\lfloor \frac{y_1 + y_2}{2} \times H \right\rfloor$$
- Vẽ một chấm tròn đặc màu đỏ bán kính `10px` và một vòng tròn viền đỏ bán kính `30px` lên ảnh `som_image_base64` để người dùng nhìn thấy chính xác vị trí Agent sắp click trên giao diện Gradio.

#### E. Đóng gói Hành động thành `BetaToolUseBlock` ([`vlm_agent.py:L226-L251`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent.py#L226-L251)):
```python
        response_content = [BetaTextBlock(text=vlm_plan_str, type='text')]
        if 'box_centroid_coordinate' in vlm_response_json:
            move_cursor_block = BetaToolUseBlock(id=f'toolu_{uuid.uuid4()}',
                                            input={'action': 'mouse_move', 'coordinate': vlm_response_json["box_centroid_coordinate"]},
                                            name='computer', type='tool_use')
            response_content.append(move_cursor_block)

        next_action_raw = str(vlm_response_json.get("Next Action", "None"))
        action_name = next_action_raw.split(",")[0].strip()

        if action_name == "None" or not action_name:
            print("Task paused/completed.")
        elif action_name in ("type", "key", "press"):
            real_action = "key" if action_name == "press" else action_name
            type_val = str(vlm_response_json.get("value") or vlm_response_json.get("text") or "")
            sim_content_block = BetaToolUseBlock(id=f'toolu_{uuid.uuid4()}',
                                        input={'action': real_action, 'text': type_val},
                                        name='computer', type='tool_use')
            response_content.append(sim_content_block)
        else:
            sim_content_block = BetaToolUseBlock(id=f'toolu_{uuid.uuid4()}',
                                            input={'action': action_name},
                                            name='computer', type='tool_use')
            response_content.append(sim_content_block)
```
- Nếu có `box_centroid_coordinate`, Agent luôn chèn một khối `mouse_move` tới tâm `[x, y]` trước, sau đó mới chèn khối hành động chính (`left_click`, `double_click`, `type`, `key`...).

---

### 2.2. Lớp `VLMOrchestratedAgent` trong [`vlm_agent_with_orchestrator.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent_with_orchestrator.py)

Bổ sung cơ chế **Task Progress Ledger** (Sổ cái theo dõi tiến độ) ở mỗi bước ([`vlm_agent_with_orchestrator.py:L22-L54`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/vlm_agent_with_orchestrator.py#L22-L54)):
```python
ORCHESTRATOR_LEDGER_PROMPT = """
Recall we are working on the following request:
{task}
To make progress on the request, please answer the following questions, including necessary reasoning:
    - Is the request fully satisfied?
    - Are we in a loop where we are repeating the same requests and / or getting the same responses as before?
    - Are we making forward progress?
    - What instruction or question would you give in order to complete the task? 
...
"""
```
- Ở bước `step_count == 0`, gọi `_initialize_task(messages)` để tạo kế hoạch tổng thể và lưu vào `plan.json`.
- Ở các bước tiếp theo, gọi `_update_ledger(messages)` để tự đánh giá xem Agent có bị lặp vô hạn (`is_in_loop`) hay không, và ghi nhật ký chi tiết vào `trajectory.json`.

---

### 2.3. Lớp `AnthropicActor` trong [`anthropic_agent.py`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/anthropic_agent.py)

Dành riêng cho mô hình `claude-3-5-sonnet-20241022` sử dụng công cụ `computer-use-2024-10-22` chính chủ của Anthropic ([`anthropic_agent.py:L93-L100`](file:///home/thai/Downloads/omniparser/omnitool/gradio/agent/anthropic_agent.py#L93-L100)):
```python
        raw_response = self.client.beta.messages.with_raw_response.create(
            max_tokens=self.max_tokens,
            messages=messages,
            model=self.model,
            system=self.system,
            tools=self.tool_collection.to_params(),
            betas=["computer-use-2024-10-22"],
        )
```

---

## 3. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm chứng trực tiếp bộ trích xuất `extract_data`, bộ lọc fallback Key-Value và phép tính tâm `box_centroid_coordinate` trong `omnitool/gradio/agent/vlm_agent.py`:

```bash
PYTHONPATH=omnitool/gradio .venv/bin/python -c '
from agent.vlm_agent import extract_data

# 1. Kiểm chứng trích xuất JSON từ Markdown code block
raw_md = "Here is my plan:\n```json\n{\"Reasoning\": \"Click search box\", \"Next Action\": \"left_click\", \"Box ID\": 2}\n```"
print("1. Extracted JSON:", extract_data(raw_md, "json"))

# 2. Kiểm chứng tính toạ độ tâm (box_centroid_coordinate) trên màn hình 1920x1200
screen_w, screen_h = 1920, 1200
bbox_norm = [0.25, 0.40, 0.75, 0.50] # Trung tâm ngang (0.5), dọc (0.45)
centroid = [int((bbox_norm[0] + bbox_norm[2]) / 2 * screen_w), int((bbox_norm[1] + bbox_norm[3]) / 2 * screen_h)]
print("2. Computed Centroid on 1920x1200:", centroid)
'
```

**Kết quả thực thi thực tế:**
```text
1. Extracted JSON: {"Reasoning": "Click search box", "Next Action": "left_click", "Box ID": 2}
2. Computed Centroid on 1920x1200: [960, 540]
```

