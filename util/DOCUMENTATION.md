# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `util/` (Core Vision Engine)

Thư mục [`util/`](file:///home/thai/Downloads/omniparser/util) là **trái tim thị giác máy tính (Computer Vision Core)** của toàn bộ hệ thống OmniParser. Mọi tác vụ từ nhận diện biểu tượng (Icon Detection), nhận diện chữ viết (OCR), khử khung hình chồng lấp (Non-Maximum Suppression & IoU Deduplication), mô tả ngữ nghĩa biểu tượng bằng VLM (Florence-2 / BLIP-2 / Phi-3V), cho đến vẽ nhãn số **Set-of-Mark (SoM)** không bị đè chữ đều nằm trong thư mục này.

---

## 1. Cấu Trúc Các Tệp Trong `util/`

| Tệp | Số dòng | Vai trò cốt lõi |
| :--- | :---: | :--- |
| [`util/omniparser.py`](file:///home/thai/Downloads/omniparser/util/omniparser.py) | 55 | Lớp vỏ bọc cấp cao `Omniparser`: tự động phân nhánh cấu hình **GPU (Colab - 100% gốc)** và **CPU (Local - Fast Mode)**, điều phối luồng `parse()` từ ảnh Base64 sang ảnh SoM và danh sách phần tử. |
| [`util/utils.py`](file:///home/thai/Downloads/omniparser/util/utils.py) | 584 | Chứa toàn bộ thuật toán lõi: `check_ocr_box()`, `get_yolo_model()`, `get_caption_model_processor()`, `remove_overlap_new()`, `get_parsed_content_icon()`, `get_som_labeled_img()` và `annotate()`. |
| [`util/yolov9.py`](file:///home/thai/Downloads/omniparser/util/yolov9.py) | 137 | Bộ suy luận `YOLOv9Detector` chạy mô hình TorchScript (`icon_detect_v3/model.pt`) với tiền xử lý Letterbox, giải mã Anchor-free multi-stride `(8, 16, 32)` và `batched_nms`. |
| [`util/box_annotator.py`](file:///home/thai/Downloads/omniparser/util/box_annotator.py) | 263 | Lớp `BoxAnnotator` và thuật toán `get_optimal_label_pos()` tìm vị trí đặt nhãn ID tối ưu quanh khung bao để các con số ID không đè lên nhau. |

---

## 2. Giải Thích Chi Tiết Kèm Mã Nguồn Thực Tế

### 2.1. Tệp [`util/omniparser.py`](file:///home/thai/Downloads/omniparser/util/omniparser.py)

Tệp này định nghĩa lớp [`Omniparser`](file:///home/thai/Downloads/omniparser/util/omniparser.py#L7-L55) được gọi trực tiếp bởi `omniparserserver.py`.

#### Mã nguồn thực tế ([`util/omniparser.py:L7-L55`](file:///home/thai/Downloads/omniparser/util/omniparser.py#L7-L55)):
```python
class Omniparser(object):
    def __init__(self, config: Dict):
        self.config = config
        req_device = config.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')
        self.device = 'cuda' if (req_device == 'cuda' and torch.cuda.is_available()) else 'cpu'

        self.som_model = get_yolo_model(model_path=config.get('som_model_path'), device=self.device)
        
        if config.get('use_local_semantics') is not None:
            self.use_semantics = bool(config['use_local_semantics'])
        else:
            # GPU (Colab): 100% original pipeline (True); CPU (Local): Fast mode (False)
            self.use_semantics = (self.device == 'cuda')

        if self.use_semantics:
            self.caption_model_processor = get_caption_model_processor(
                model_name=config['caption_model_name'], 
                model_name_or_path=config['caption_model_path'], 
                device=self.device
            )
        else:
            self.caption_model_processor = None
        print(f'Omniparser initialized on {self.device.upper()} (full_caption={self.use_semantics})!!!')

    def parse(self, image_base64: str):
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        print('image size:', image.size)
        
        box_overlay_ratio = max(image.size) / 3200
        draw_bbox_config = {
            'text_scale': 0.8 * box_overlay_ratio,
            'text_thickness': max(int(2 * box_overlay_ratio), 1),
            'text_padding': max(int(3 * box_overlay_ratio), 1),
            'thickness': max(int(3 * box_overlay_ratio), 1),
        }

        default_thresh = 0.05 if self.device == 'cuda' else 0.15
        box_thresh = self.config.get('BOX_TRESHOLD') or default_thresh

        (text, ocr_bbox), _ = check_ocr_box(image, display_img=False, output_bb_format='xyxy', easyocr_args={'text_threshold': 0.8}, use_paddleocr=False)
        dino_labled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
            image, self.som_model, BOX_TRESHOLD=box_thresh, 
            output_coord_in_ratio=True, ocr_bbox=ocr_bbox, draw_bbox_config=draw_bbox_config, 
            caption_model_processor=self.caption_model_processor, ocr_text=text, 
            use_local_semantics=self.use_semantics, iou_threshold=0.7, scale_img=False, batch_size=128
        )

        return dino_labled_img, parsed_content_list
```

**Phân tích cơ chế:**
1. **Tự động tách 2 chế độ (`__init__`):**
   - Nếu chạy trên **GPU (`self.device == 'cuda'`)**: tự động bật `self.use_semantics = True`, nạp mô hình Florence-2 vào VRAM với kiểu `float16`, và đặt ngưỡng `default_thresh = 0.05` (giữ nguyên 100% pipeline gốc).
   - Nếu chạy trên **CPU (`self.device == 'cpu'`)**: mặc định `self.use_semantics = False` (không nạp Florence-2 vào RAM để tiết kiệm ~1.5 GB RAM và tránh nghẽn CPU 90 giây), đồng thời đặt `default_thresh = 0.15` để lọc bỏ các khung nhiễu độ tin cậy thấp.
2. **Hàm `parse(image_base64)`:**
   - Giải mã chuỗi Base64 thành ảnh `PIL.Image`.
   - Chạy `check_ocr_box` với EasyOCR (`text_threshold=0.8`) để lấy danh sách chuỗi văn bản `text` và toạ độ `ocr_bbox`.
   - Gọi `get_som_labeled_img` để hợp nhất kết quả OCR + YOLO + Captioning và trả về bộ đôi `(dino_labled_img, parsed_content_list)`.

---

### 2.2. Tệp [`util/yolov9.py`](file:///home/thai/Downloads/omniparser/util/yolov9.py)

Tệp này triển khai lớp [`YOLOv9Detector`](file:///home/thai/Downloads/omniparser/util/yolov9.py#L27-L137) để chạy tệp trọng số TorchScript `weights/icon_detect_v3/model.pt` với giao diện hàm `.predict()` tương thích hoàn toàn với Ultralytics YOLO.

#### Tiền xử lý ảnh Letterbox ([`util/yolov9.py:L73-L87`](file:///home/thai/Downloads/omniparser/util/yolov9.py#L73-L87)):
```python
    def _preprocess(self, image, image_size):
        target_width, target_height = self._normalize_image_size(image_size)
        image_width, image_height = image.size
        scale = min(target_width / image_width, target_height / image_height)
        resized_width = int(image_width * scale)
        resized_height = int(image_height * scale)
        pad_left = (target_width - resized_width) // 2
        pad_top = (target_height - resized_height) // 2

        resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
        padded = Image.new("RGB", (target_width, target_height), (114, 114, 114))
        padded.paste(resized, (pad_left, pad_top))
        image_array = np.asarray(padded, dtype=np.float32).transpose(2, 0, 1) / 255.0
        image_tensor = torch.from_numpy(image_array).unsqueeze(0).to(self.device)
        return image_tensor, scale, pad_left, pad_top
```
- Làm tròn kích thước mục tiêu lên bội số của `32` (`_normalize_image_size`), giữ nguyên tỷ lệ khung hình gốc bằng hệ số `scale`, chèn viền xám `(114, 114, 114)` ở hai bên (`pad_left`, `pad_top`) và chuẩn hóa giá trị điểm ảnh về `[0.0, 1.0]`.

#### Giải mã đầu ra đa tỷ lệ `_decode` & suy luận `predict` ([`util/yolov9.py:L89-L136`](file:///home/thai/Downloads/omniparser/util/yolov9.py#L89-L136)):
```python
    def _decode(self, outputs):
        class_logits = []
        decoded_boxes = []
        for output_index, stride in zip(range(0, len(outputs), 2), self.strides):
            layer_logits, layer_distances = outputs[output_index : output_index + 2]
            batch_size, _, height, width = layer_logits.shape
            layer_logits = layer_logits.permute(0, 2, 3, 1).reshape(batch_size, -1, layer_logits.shape[1])
            layer_distances = layer_distances.permute(0, 2, 3, 1).reshape(batch_size, -1, 4) * stride

            grid_y, grid_x = torch.meshgrid(
                torch.arange(height, device=self.device),
                torch.arange(width, device=self.device),
                indexing="ij",
            )
            anchors = (torch.stack((grid_x, grid_y), dim=-1).reshape(-1, 2) + 0.5) * stride
            left_top, right_bottom = layer_distances.chunk(2, dim=-1)
            decoded_boxes.append(torch.cat((anchors - left_top, anchors + right_bottom), dim=-1))
            class_logits.append(layer_logits)

        return torch.cat(class_logits, dim=1).sigmoid(), torch.cat(decoded_boxes, dim=1)
```
```python
    @torch.inference_mode()
    def predict(self, source, conf=0.25, imgsz=640, iou=0.7, max_det=300):
        image = self._load_image(source)
        image_tensor, scale, pad_left, pad_top = self._preprocess(image, imgsz)

        with self._inference_context(), torch.jit.optimized_execution(False):
            class_scores, boxes = self._decode(self.model(image_tensor))

        scores, class_ids = class_scores[0].max(dim=-1)
        valid = scores > conf
        scores = scores[valid]
        class_ids = class_ids[valid]
        boxes = boxes[0][valid]
        boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_left) / scale
        boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_top) / scale

        keep = batched_nms(boxes, scores, class_ids, iou)[:max_det]
        boxes = boxes[keep]
        scores = scores[keep]
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clamp(0, image.width)
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clamp(0, image.height)
        return [Result(Boxes(boxes, scores))]
```
- **Giải mã Anchor-free:** Trên 3 tầng đặc trưng có bước nhảy `strides = (8, 16, 32)`, mỗi tâm lưới `(grid_x + 0.5, grid_y + 0.5) * stride` cộng/trừ khoảng cách `left_top` và `right_bottom` để tạo thành toạ độ `[x1, y1, x2, y2]`.
- **Khôi phục toạ độ gốc & NMS:** Trừ đi phần đệm `pad_left`, `pad_top`, chia cho `scale`, sau đó dùng `torchvision.ops.batched_nms` để loại bỏ các khung trùng lặp và giới hạn tối đa `max_det=300` khung.

---

### 2.3. Tệp [`util/utils.py`](file:///home/thai/Downloads/omniparser/util/utils.py)

Đây là tệp trung tâm kết nối OCR, YOLO và Captioning.

#### A. Thuật toán khử trùng lặp và gộp nhãn `remove_overlap_new` ([`util/utils.py:L259-L337`](file:///home/thai/Downloads/omniparser/util/utils.py#L259-L337)):
```python
    for i, box1_elem in enumerate(boxes):
        box1 = box1_elem['bbox']
        is_valid_box = True
        for j, box2_elem in enumerate(boxes):
            # keep the smaller box
            box2 = box2_elem['bbox']
            if i != j and IoU(box1, box2) > iou_threshold and box_area(box1) > box_area(box2):
                is_valid_box = False
                break
        if is_valid_box:
            if ocr_bbox:
                # keep yolo boxes + prioritize ocr label
                box_added = False
                ocr_labels = ''
                for box3_elem in ocr_bbox:
                    if not box_added:
                        box3 = box3_elem['bbox']
                        if is_inside(box3, box1): # ocr inside icon
                            try:
                                # gather all ocr labels
                                ocr_labels += box3_elem['content'] + ' '
                                filtered_boxes.remove(box3_elem)
                            except:
                                continue
                        elif is_inside(box1, box3): # icon inside ocr, don't added this icon box
                            box_added = True
                            break
                        else:
                            continue
                if not box_added:
                    if ocr_labels:
                        filtered_boxes.append({'type': 'icon', 'bbox': box1_elem['bbox'], 'interactivity': True, 'content': ocr_labels, 'source':'box_yolo_content_ocr'})
                    else:
                        filtered_boxes.append({'type': 'icon', 'bbox': box1_elem['bbox'], 'interactivity': True, 'content': None, 'source':'box_yolo_content_yolo'})
```
**Điểm thông minh của thuật toán này:**
1. **Giữ khung nhỏ hơn khi hai khung YOLO chồng nhau:** Nếu `IoU(box1, box2) > iou_threshold` và `box_area(box1) > box_area(box2)`, khung to bao ngoài bị loại bỏ để giữ lại nút bấm chi tiết bên trong.
2. **Hợp nhất chữ OCR nằm trong nút bấm YOLO (`is_inside(box3, box1)`):** Ví dụ một nút bấm `Submit` được YOLO phát hiện là một `icon` và EasyOCR phát hiện chữ `"Submit"` nằm bên trong (>80% diện tích). Thuật toán sẽ **gộp chữ `"Submit"` làm nội dung (`content`) của khung YOLO đó** (`source: 'box_yolo_content_ocr'`) và xóa khung OCR rời khỏi danh sách! Nhờ vậy, khung đó không cần phải chạy qua Florence-2 để đoán chữ nữa mà có ngay nhãn chính xác tuyệt đối.
3. **Những khung YOLO không chứa chữ bên trong** sẽ có `content: None` (`source: 'box_yolo_content_yolo'`), chờ bước tiếp theo xử lý.

#### B. Sinh mô tả ngữ nghĩa cho các Icon không chữ `get_parsed_content_icon` ([`util/utils.py:L105-L150`](file:///home/thai/Downloads/omniparser/util/utils.py#L105-L150)):
```python
@torch.inference_mode()
def get_parsed_content_icon(filtered_boxes, starting_idx, image_source, caption_model_processor, prompt=None, batch_size=128):
    to_pil = ToPILImage()
    if starting_idx:
        non_ocr_boxes = filtered_boxes[starting_idx:]
    else:
        non_ocr_boxes = filtered_boxes
    model, processor = caption_model_processor['model'], caption_model_processor['processor']
    if model.device.type == 'cpu' and len(non_ocr_boxes) > 25:
        non_ocr_boxes = non_ocr_boxes[:25]
    croped_pil_image = []
    for i, coord in enumerate(non_ocr_boxes):
        try:
            xmin, xmax = int(coord[0]*image_source.shape[1]), int(coord[2]*image_source.shape[1])
            ymin, ymax = int(coord[1]*image_source.shape[0]), int(coord[3]*image_source.shape[0])
            cropped_image = image_source[ymin:ymax, xmin:xmax, :]
            cropped_image = cv2.resize(cropped_image, (64, 64))
            croped_pil_image.append(to_pil(cropped_image))
        except:
            continue
    if not prompt:
        if 'florence' in model.config.name_or_path:
            prompt = "<CAPTION>"
        else:
            prompt = "The image shows"
    
    generated_texts = []
    device = model.device
    for i in range(0, len(croped_pil_image), batch_size):
        batch = croped_pil_image[i:i+batch_size]
        if model.device.type == 'cuda':
            inputs = processor(images=batch, text=[prompt]*len(batch), return_tensors="pt", do_resize=False).to(device=device, dtype=torch.float16)
        else:
            inputs = processor(images=batch, text=[prompt]*len(batch), return_tensors="pt").to(device=device)
        if 'florence' in model.config.name_or_path:
            generated_ids = model.generate(input_ids=inputs["input_ids"],pixel_values=inputs["pixel_values"],max_new_tokens=20,num_beams=1, do_sample=False)
        else:
            generated_ids = model.generate(**inputs, max_length=100, num_beams=5, no_repeat_ngram_size=2, early_stopping=True, num_return_sequences=1)
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)
        generated_text = [gen.strip() for gen in generated_text]
        generated_texts.extend(generated_text)
    
    return generated_texts
```
- Cắt từng vùng ảnh con (`cropped_image`) ứng với mỗi icon chưa có nhãn, đưa về kích thước chuẩn `64x64`, gom thành từng lô (`batch_size=128`) và đưa vào mô hình Florence-2 với prompt `<CAPTION>` (`max_new_tokens=20, num_beams=1`).

#### C. Điều phối tổng thể trong `get_som_labeled_img` ([`util/utils.py:L468-L522`](file:///home/thai/Downloads/omniparser/util/utils.py#L468-L522)):
```python
    # sort the filtered_boxes so that the one with 'content': None is at the end, and get the index of the first 'content': None
    filtered_boxes_elem = sorted(filtered_boxes, key=lambda x: x['content'] is None)
    starting_idx = next((i for i, box in enumerate(filtered_boxes_elem) if box['content'] is None), -1)
    filtered_boxes = torch.tensor([box['bbox'] for box in filtered_boxes_elem])

    # get parsed icon local semantics
    time1 = time.time()
    if use_local_semantics:
        caption_model = caption_model_processor['model']
        if 'phi3_v' in caption_model.config.model_type: 
            parsed_content_icon = get_parsed_content_icon_phi3v(filtered_boxes, ocr_bbox, image_source, caption_model_processor)
        else:
            parsed_content_icon = get_parsed_content_icon(filtered_boxes, starting_idx, image_source, caption_model_processor, prompt=prompt,batch_size=batch_size)
        ocr_text = [f"Text Box ID {i}: {txt}" for i, txt in enumerate(ocr_text)]
        icon_start = len(ocr_text)
        parsed_content_icon_ls = []
        # fill the filtered_boxes_elem None content with parsed_content_icon in order
        for i, box in enumerate(filtered_boxes_elem):
            if box['content'] is None:
                box['content'] = parsed_content_icon.pop(0) if parsed_content_icon else "icon"
        for i, txt in enumerate(parsed_content_icon):
            parsed_content_icon_ls.append(f"Icon Box ID {str(i+icon_start)}: {txt}")
        parsed_content_merged = ocr_text + parsed_content_icon_ls
    else:
        for i, box in enumerate(filtered_boxes_elem):
            if box['content'] is None:
                bx = box['bbox']
                cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
                pos_y = "top" if cy < 0.25 else ("bottom" if cy > 0.75 else "center")
                pos_x = "left" if cx < 0.33 else ("right" if cx > 0.67 else "middle")
                box['content'] = f"interactive button/input ({pos_y}-{pos_x})"
        ocr_text = [f"Text Box ID {i}: {txt}" for i, txt in enumerate(ocr_text)]
        parsed_content_merged = ocr_text
```
- Khi `use_local_semantics=True` (GPU Colab): điền mô tả sinh bởi Florence-2 vào từng phần tử `box['content']`.
- Khi `use_local_semantics=False` (CPU Fast Mode): tự động tính tâm `(cx, cy)` của khung để gán nhãn định vị không gian như `interactive button/input (center-middle)`, `interactive button/input (top-right)` trong `0.001` giây!

---

### 2.4. Tệp [`util/box_annotator.py`](file:///home/thai/Downloads/omniparser/util/box_annotator.py)

Khi một màn hình có hàng chục nút bấm sát nhau, nếu luôn vẽ nhãn số `ID` ở góc trên bên trái (`top-left`) thì nhãn của nút dưới sẽ đè lên nút trên. Tệp `box_annotator.py` giải quyết bài toán này.

#### Tự động chọn màu chữ Đen/Trắng theo độ sáng nền ([`util/box_annotator.py:L148-L161`](file:///home/thai/Downloads/omniparser/util/box_annotator.py#L148-L161)):
```python
            box_color = color.as_rgb()
            luminance = 0.299 * box_color[0] + 0.587 * box_color[1] + 0.114 * box_color[2]
            text_color = (0,0,0) if luminance > 160 else (255,255,255)
            cv2.putText(
                img=scene,
                text=text,
                org=(text_x, text_y),
                fontFace=font,
                fontScale=self.text_scale,
                color=text_color,
                thickness=self.text_thickness,
                lineType=cv2.LINE_AA,
            )
```
- Dùng công thức độ chói chuẩn ITU-R BT.601 ($Y = 0.299R + 0.587G + 0.114B$): nếu màu nền khung sáng ($Y > 160$) thì in chữ màu đen `(0,0,0)`, ngược lại in chữ màu trắng `(255,255,255)` để VLM đọc số rõ nhất.

#### Tìm vị trí đặt nhãn không chồng lấp `get_optimal_label_pos` ([`util/box_annotator.py:L189-L262`](file:///home/thai/Downloads/omniparser/util/box_annotator.py#L189-L262)):
```python
def get_optimal_label_pos(text_padding, text_width, text_height, x1, y1, x2, y2, detections, image_size):
    def get_is_overlap(detections, text_background_x1, text_background_y1, text_background_x2, text_background_y2, image_size):
        is_overlap = False
        for i in range(len(detections)):
            detection = detections.xyxy[i].astype(int)
            if IoU([text_background_x1, text_background_y1, text_background_x2, text_background_y2], detection) > 0.3:
                is_overlap = True
                break
        if text_background_x1 < 0 or text_background_x2 > image_size[0] or text_background_y1 < 0 or text_background_y2 > image_size[1]:
            is_overlap = True
        return is_overlap
```
- Lần lượt thử 4 vị trí quanh khung:
  1. `top left` (phía trên bên trái)
  2. `outer left` (mép ngoài bên trái)
  3. `outer right` (mép ngoài bên phải)
  4. `top right` (phía trên bên phải)
- Vị trí đầu tiên không đè lên bất kỳ khung phát hiện nào khác (`IoU <= 0.3`) và không tràn khỏi mép ảnh sẽ được chọn ngay lập tức.

---

## 3. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Chạy kiểm chứng trực tiếp các hàm tính toán hình học (`box_area`, `intersection_area`, `IoU`) và bộ khử trùng lặp `remove_overlap_new` trong thư mục `util/`:

```bash
.venv/bin/python -c '
from util.box_annotator import box_area, intersection_area, IoU
from util.utils import remove_overlap_new

b1 = [10, 10, 110, 60]
b2 = [60, 10, 160, 60]
print("1. Box Area & IoU:", "area=", box_area(b1), "inter=", intersection_area(b1, b2), "iou_std=", round(IoU(b1, b2, return_max=False), 4), "iou_max=", round(IoU(b1, b2, return_max=True), 4))

ocr_boxes = [{"type": "text", "bbox": [0.12, 0.12, 0.28, 0.18], "interactivity": False, "content": "Search"}]
yolo_boxes = [
    {"type": "icon", "bbox": [0.10, 0.10, 0.30, 0.20], "interactivity": True, "content": None},
    {"type": "icon", "bbox": [0.80, 0.10, 0.85, 0.15], "interactivity": True, "content": None}
]
merged = remove_overlap_new(yolo_boxes, iou_threshold=0.7, ocr_bbox=ocr_boxes)
print("2. Merged OCR+YOLO boxes:", merged)
'
```

**Kết quả thực thi thực tế:**
```text
1. Box Area & IoU: area= 5000 inter= 2500 iou_std= 0.3333 iou_max= 0.5
2. Merged OCR+YOLO boxes: [
  {'type': 'icon', 'bbox': [0.1, 0.1, 0.3, 0.2], 'interactivity': True, 'content': 'Search ', 'source': 'box_yolo_content_ocr'},
  {'type': 'icon', 'bbox': [0.8, 0.1, 0.85, 0.15], 'interactivity': True, 'content': None, 'source': 'box_yolo_content_yolo'}
]
```
> **Kết luận kiểm chứng:** Khung chữ OCR `"Search"` nằm bên trong khung nút bấm YOLO `[0.1, 0.1, 0.3, 0.2]` đã được gộp chính xác thành một phần tử duy nhất có `interactivity: True`, `content: 'Search '` và `source: 'box_yolo_content_ocr'`.

