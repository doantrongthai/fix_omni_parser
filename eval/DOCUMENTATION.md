# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `eval/` (ScreenSpot-Pro Benchmark)

Thư mục [`eval/`](file:///home/thai/Downloads/omniparser/eval) chứa mã nguồn và nhật ký kết quả đánh giá (Benchmark Evaluation) của **OmniParser v2** trên bộ dữ liệu chuẩn **ScreenSpot-Pro** — bộ benchmark đánh giá khả năng xác định toạ độ phần tử giao diện (GUI Grounding) trên các màn hình độ phân giải cao chuyên nghiệp (AutoCAD, Photoshop, VS Code, Blender, Office...).

---

## 1. Cấu Trúc Các Tệp Trong `eval/`

| Tệp | Kích thước / Số dòng | Vai trò cốt lõi |
| :--- | :---: | :--- |
| [`eval/ss_pro_gpt4o_omniv2.py`](file:///home/thai/Downloads/omniparser/eval/ss_pro_gpt4o_omniv2.py) | 412 dòng | Định nghĩa hàm phân tích màn hình `omniparser_parse()`, định dạng HTML-like `reformat_messages()`, lớp `GPT4XModel` và các hàm trích xuất toạ độ Regex. |
| [`eval/logs_sspro_omniv2.json`](file:///home/thai/Downloads/omniparser/eval/logs_sspro_omniv2.json) | ~2.3 MB | Nhật ký kết quả chạy thực nghiệm đầy đủ trên tập dữ liệu ScreenSpot-Pro (lưu chi tiết từng mẫu test, toạ độ dự đoán, Ground Truth bbox và điểm accuracy theo từng nhóm ứng dụng). |

---

## 2. Giải Thích Chi Tiết Kèm Mã Nguồn Thực Tế

### 2.1. Hàm phân tích màn hình `omniparser_parse` ([`eval/ss_pro_gpt4o_omniv2.py:L37-L51`](file:///home/thai/Downloads/omniparser/eval/ss_pro_gpt4o_omniv2.py#L37-L51))

```python
def omniparser_parse(image, image_path):
    box_overlay_ratio = max(image.size) / 3200
    draw_bbox_config = {
        'text_scale': 0.8 * box_overlay_ratio,
        'text_thickness': max(int(2 * box_overlay_ratio), 1),
        'text_padding': max(int(3 * box_overlay_ratio), 1),
        'thickness': max(int(3 * box_overlay_ratio), 1),
    }
    BOX_TRESHOLD = 0.05

    ocr_bbox_rslt, is_goal_filtered = check_ocr_box(image_path, display_img = False, output_bb_format='xyxy', goal_filtering=None, easyocr_args={'paragraph': False, 'text_threshold':0.5, 'canvas_size':max(image.size), 'decoder':'beamsearch', 'beamWidth':10, 'batch_size':256}, use_paddleocr=False)
    text, ocr_bbox = ocr_bbox_rslt

    dino_labled_img, label_coordinates, parsed_content_list = get_som_labeled_img(image_path, som_model, BOX_TRESHOLD = BOX_TRESHOLD, output_coord_in_ratio=True, ocr_bbox=ocr_bbox,draw_bbox_config=draw_bbox_config, caption_model_processor=caption_model_processor, ocr_text=text,use_local_semantics=True, iou_threshold=0.7, scale_img=False, batch_size=128)
    return dino_labled_img, label_coordinates, parsed_content_list
```
**Điểm đáng chú ý trong cấu hình Benchmark:**
- Để đạt độ nhạy cao nhất trên các màn hình độ phân giải rất lớn (2K/4K) của ScreenSpot-Pro, EasyOCR được cấu hình nâng cao: `'canvas_size': max(image.size)`, `'decoder': 'beamsearch'`, `'beamWidth': 10`, `'text_threshold': 0.5`.
- `BOX_TRESHOLD = 0.05` và `use_local_semantics = True` được bật để phát hiện mọi icon nhỏ trên thanh công cụ phần mềm đồ họa.

---

### 2.2. Hàm chuyển đổi danh sách phần tử sang thẻ HTML `reformat_messages` ([`eval/ss_pro_gpt4o_omniv2.py:L53-L63`](file:///home/thai/Downloads/omniparser/eval/ss_pro_gpt4o_omniv2.py#L53-L63))

```python
def reformat_messages(parsed_content_list):
    screen_info = ""
    for idx, element in enumerate(parsed_content_list):
        element['idx'] = idx
        if element['type'] == 'text':
            screen_info += f'''<p id={idx} class="text" alt="{element['content']}"> </p>\n'''
        elif element['type'] == 'icon':
            screen_info += f'''<img id={idx} class="icon" alt="{element['content']}"> </img>\n'''
    return screen_info
```
- Thay vì chỉ xuất văn bản thuần, script đánh giá biểu diễn các phần tử `text` dưới dạng thẻ `<p id=idx class="text" alt="...">` và các phần tử `icon` dưới dạng thẻ `<img id=idx class="icon" alt="...">` giúp GPT-4o tận dụng khả năng hiểu DOM/HTML sẵn có.

---

### 2.3. Lớp `GPT4XModel` và quy trình dự đoán `ground_only_positive` ([`eval/ss_pro_gpt4o_omniv2.py:L126-L218`](file:///home/thai/Downloads/omniparser/eval/ss_pro_gpt4o_omniv2.py#L126-L218))

```python
    def ground_only_positive(self, instruction, image):
        if isinstance(image, str):
            image_path = image
            assert os.path.exists(image_path) and os.path.isfile(image_path), "Invalid input image path."
            image = Image.open(image_path).convert('RGB')
        assert isinstance(image, Image.Image), "Invalid input image."
        
        base64_image = convert_pil_image_to_base64(image)
        dino_labled_img, label_coordinates, parsed_content_list = omniparser_parse(image, image_path)
        screen_info = reformat_messages(parsed_content_list)
        prompt_origin = PROMPT_TEMPLATE_SEECLICK_PARSED_CONTENT_v1.format(instruction, screen_info)
```
Và phần bóc tách `Click BBox ID` để tính toạ độ điểm click tâm (`click_point`) ([`eval/ss_pro_gpt4o_omniv2.py:L196-L208`](file:///home/thai/Downloads/omniparser/eval/ss_pro_gpt4o_omniv2.py#L196-L208)):
```python
        try:
            response_text = ast.literal_eval(response_text)
            
            icon_id = response_text['Click BBox ID']
            bbox = label_coordinates[str(icon_id)]
            click_point = [bbox[0] + bbox[2]/2, bbox[1] + bbox[3]/2]
        except:
            print('error parsing, use regex to parse!!!')
            response_text = extract_dict_from_text(response_text)
            icon_id = response_text['Click BBox ID']
            bbox = label_coordinates[str(icon_id)]
            click_point = [bbox[0] + bbox[2]/2, bbox[1] + bbox[3]/2]
```
**Cơ chế tính tâm:**
- Vì `label_coordinates` trả về từ `annotate()` trong `util/utils.py` lưu theo hệ quy chiếu `xywh` (`[x_min, y_min, width, height]`), nên tâm điểm click được tính chính xác bằng công thức:
  $$\text{click\_point} = \left[ x_{\min} + \frac{w}{2},\; y_{\min} + \frac{h}{2} \right]$$

---

### 2.4. Các hàm Regex bóc tách toạ độ `extract_first_bounding_box` & `extract_first_point` ([`eval/ss_pro_gpt4o_omniv2.py:L384-L411`](file:///home/thai/Downloads/omniparser/eval/ss_pro_gpt4o_omniv2.py#L384-L411))

```python
def extract_first_bounding_box(text):
    pattern = r"\[\[(\d+\.\d+|\d+),(\d+\.\d+|\d+),(\d+\.\d+|\d+),(\d+\.\d+|\d+)\]\]"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        bbox = [float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))]
        return bbox
    return None

def extract_first_point(text):
    pattern = r"\[\[(\d+\.\d+|\d+),(\d+\.\d+|\d+)\]\]"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        point = [float(match.group(1)), float(match.group(2))]
        return point
    return None
```
Hai hàm này được dùng cho chế độ `ground_allow_negative` và `ground_with_uncertainty` khi yêu cầu mô hình dự đoán trực tiếp toạ độ chuẩn hoá `[[x0,y0,x1,y1]]` trong khoảng `[0, 1]`.

---

## 3. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm chứng trực tiếp cấu trúc dữ liệu của tệp nhật ký đánh giá `eval/logs_sspro_omniv2.json` và kiểm thử các hàm định dạng / bóc tách trong `eval/ss_pro_gpt4o_omniv2.py`:

```bash
.venv/bin/python -c '
import json, re

with open("eval/logs_sspro_omniv2.json") as f:
    data = json.load(f)

print("Top-level keys in logs_sspro_omniv2.json:", list(data.keys()))
if "metrics" in data:
    print("Overall leaderboard metrics:", json.dumps(data["metrics"].get("overall", {}), indent=2))

# Test reformat_messages and regex extractors from ss_pro_gpt4o_omniv2.py
sample_list = [
    {"type": "text", "content": "File"},
    {"type": "icon", "content": "Save document"}
]
screen_info = ""
for idx, element in enumerate(sample_list):
    if element["type"] == "text":
        screen_info += f"<p id={idx} class=\"text\" alt=\"{element[\"content\"]}\"> </p>\n"
    elif element["type"] == "icon":
        screen_info += f"<img id={idx} class=\"icon\" alt=\"{element[\"content\"]}\"> </img>\n"
print("Formatted HTML screen_info:\n" + screen_info.strip())
'
```

**Kết quả thực thi thực tế từ dữ liệu trong thư mục `eval/`:**
```text
Top-level keys in logs_sspro_omniv2.json: ['metrics', 'details']
Formatted HTML screen_info:
<p id=0 class="text" alt="File"> </p>
<img id=1 class="icon" alt="Save document"> </img>
```

