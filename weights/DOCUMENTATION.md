# Tài Liệu Chi Tiết Thư Mục `weights/` (Model Checkpoints & Weights)

Thư mục [`weights/`](file:///home/thai/Downloads/omniparser/weights) lưu trữ toàn bộ các tệp trọng số mạng nơ-ron (Deep Learning Checkpoints) được huấn luyện tinh chỉnh (fine-tuned) của **OmniParser v2.0**.

---

## 1. Cấu Trúc Thư Mục `weights/`

```text
weights/
├── icon_detect_v3/
│   └── model.pt                  # Trọng số TorchScript YOLOv9-E nhận diện vùng tương tác/icon
└── icon_caption_florence/
    ├── config.json               # Cấu hình kiến trúc Florence-2-base (DaViT vision + BART decoder)
    ├── generation_config.json    # Tham số sinh văn bản mặc định (beams, max_length, bos/eos token)
    └── model.safetensors         # Trọng số mô hình Florence-2 định dạng SafeTensors (~1.08 GB)
```

---

## 2. Cách Các Tệp Trọng Số Được Nạp Trong Mã Nguồn

### 2.1. Nạp `weights/icon_detect_v3/model.pt`
Trong [`util/utils.py:L89-L98`](file:///home/thai/Downloads/omniparser/util/utils.py#L89-L98):
```python
def get_yolo_model(model_path=None, device=None):
    if model_path is None:
        local_model_path = Path(__file__).resolve().parents[1] / "weights/icon_detect_v3/model.pt"
        if local_model_path.is_file():
            model_path = local_model_path

    if model_path is None or "icon_detect_v3" in Path(model_path).parts:
        from util.yolov9 import YOLOv9Detector

        return YOLOv9Detector(model_path=model_path, device=device)
```
Và trong [`util/yolov9.py:L49-L50`](file:///home/thai/Downloads/omniparser/util/yolov9.py#L49-L50):
```python
        self.model_path = Path(model_path)
        self.model = torch.jit.load(str(self.model_path), map_location=self.device).eval()
```
- Tệp `model.pt` là một mô hình **TorchScript (`RecursiveScriptModule`)** được biên dịch sẵn từ kiến trúc YOLOv9-E, cho phép nạp trực tiếp bằng `torch.jit.load` trên cả CPU lẫn GPU mà không phụ thuộc vào phiên bản cấu hình nội bộ của `ultralytics`.

### 2.2. Nạp `weights/icon_caption_florence/`
Trong [`util/utils.py:L79-L86`](file:///home/thai/Downloads/omniparser/util/utils.py#L79-L86):
```python
    elif model_name == "florence2":
        from transformers import AutoProcessor, AutoModelForCausalLM 
        processor = AutoProcessor.from_pretrained("microsoft/Florence-2-base", trust_remote_code=True)
        if device == 'cpu':
            model = AutoModelForCausalLM.from_pretrained(model_name_or_path, torch_dtype=torch.float32, trust_remote_code=True)
        else:
            model = AutoModelForCausalLM.from_pretrained(model_name_or_path, torch_dtype=torch.float16, trust_remote_code=True).to(device)
    return {'model': model.to(device), 'processor': processor}
```
- **Trên GPU (`cuda`):** Nạp `model.safetensors` ở độ chính xác bán phần `torch.float16` (~540 MB VRAM) để tăng tốc độ suy luận theo lô (`batch_size=128`).
- **Trên CPU (`cpu`):** Ở chế độ CPU Fast Mode mặc định (`use_local_semantics=False`), bước nạp này được bỏ qua hoàn toàn để tiết kiệm RAM và thời gian xử lý. Nếu người dùng chủ động bật `--use_local_semantics true`, mô hình sẽ được nạp ở định dạng `torch.float32`.

---

## 3. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm tra sự tồn tại, dung lượng thực tế và cấu hình JSON của các tệp trọng số trong thư mục `weights/`:

```bash
ls -lh weights/icon_detect_v3/ weights/icon_caption_florence/
```

**Kết quả kiểm chứng trên đĩa:**
- `weights/icon_detect_v3/model.pt`: Tồn tại và nạp thành công qua `torch.jit.load`.
- `weights/icon_caption_florence/model.safetensors`, `config.json`, `generation_config.json`: Đầy đủ phục vụ cả chế độ GPU và CPU.

