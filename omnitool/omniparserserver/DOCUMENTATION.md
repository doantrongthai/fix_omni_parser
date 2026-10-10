# Tài Liệu Chi Tiết Mã Nguồn Thư Mục `omnitool/omniparserserver/`

Thư mục [`omnitool/omniparserserver/`](file:///home/thai/Downloads/omniparser/omnitool/omniparserserver) chứa dịch vụ Web API **FastAPI + Uvicorn** đóng vai trò cầu nối mạng giữa Agent điều khiển và lõi thị giác `Omniparser` (trong `util/omniparser.py`). Dịch vụ này có thể chạy **cục bộ trên CPU (`127.0.0.1:8000`)** hoặc chạy **trên máy chủ GPU từ xa (Google Colab qua Cloudflare Tunnel)**.

---

## 1. Phân Tích Mã Nguồn [`omniparserserver.py`](file:///home/thai/Downloads/omniparser/omnitool/omniparserserver/omniparserserver.py)

Toàn bộ mã nguồn của [`omniparserserver.py`](file:///home/thai/Downloads/omniparser/omnitool/omniparserserver/omniparserserver.py#L1-L54) (54 dòng):

```python
import sys
import os
import time
from fastapi import FastAPI
from pydantic import BaseModel
import argparse
import uvicorn
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)
from util.omniparser import Omniparser

def parse_arguments():
    parser = argparse.ArgumentParser(description='Omniparser API')
    parser.add_argument('--som_model_path', type=str, default=None, help='Optional local detector path; V3 downloads from Hugging Face by default')
    parser.add_argument('--caption_model_name', type=str, default='florence2', help='Name of the caption model')
    parser.add_argument('--caption_model_path', type=str, default='../../weights/icon_caption_florence', help='Path to the caption model')
    parser.add_argument('--device', type=str, default='cpu', help='Device to run the model (cuda or cpu)')
    parser.add_argument('--BOX_TRESHOLD', type=float, default=None, help='Threshold for box detection (defaults to 0.05 on CUDA, 0.15 on CPU)')
    parser.add_argument('--use_local_semantics', type=lambda x: str(x).lower() == 'true', default=None, help='Enable Florence-2 icon captioning (True on CUDA, False on CPU by default)')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host for the API')
    parser.add_argument('--port', type=int, default=8000, help='Port for the API')
    args = parser.parse_args()
    return args

args = parse_arguments()
config = vars(args)

app = FastAPI()
omniparser = Omniparser(config)

class ParseRequest(BaseModel):
    base64_image: str

@app.post("/parse")
@app.post("/parse/")
def parse(parse_request: ParseRequest):
    print('start parsing...')
    start = time.time()
    dino_labled_img, parsed_content_list = omniparser.parse(parse_request.base64_image)
    latency = time.time() - start
    print('time:', latency)
    return {"som_image_base64": dino_labled_img, "parsed_content_list": parsed_content_list, 'latency': latency}

@app.get("/probe")
@app.get("/probe/")
async def root():
    return {"message": "Omniparser API ready"}

if __name__ == "__main__":
    uvicorn.run("omniparserserver:app", host=args.host, port=args.port, reload=True)
```

---

## 2. Giải Thích Cơ Chế Hoạt Động

### 2.1. Tự động thêm đường dẫn gốc (`root_dir`) ([`omniparserserver.py:L12-L14`](file:///home/thai/Downloads/omniparser/omnitool/omniparserserver/omniparserserver.py#L12-L14))
- Khi chạy lệnh `python -m omniparserserver` bên trong thư mục `omnitool/omniparserserver`, `os.path.dirname` 3 cấp sẽ trỏ ngược lên thư mục gốc `/home/thai/Downloads/omniparser` và thêm vào `sys.path`, cho phép import trực tiếp `from util.omniparser import Omniparser`.

### 2.2. Quản lý tham số dòng lệnh thông minh (`parse_arguments`) ([`omniparserserver.py:L16-L27`](file:///home/thai/Downloads/omniparser/omnitool/omniparserserver/omniparserserver.py#L16-L27))
- `--device`: Chọn `cuda` (Colab GPU) hoặc `cpu` (Local).
- `--BOX_TRESHOLD`: Mặc định là `None` để lớp `Omniparser` tự quyết định (`0.05` trên GPU và `0.15` trên CPU), nhưng vẫn cho phép người dùng ghi đè từ CLI nếu muốn.
- `--use_local_semantics`: Mặc định là `None` (`True` trên GPU chạy Florence-2 đầy đủ, `False` trên CPU bật Fast Mode).

### 2.3. Tại sao hàm `def parse(...)` dùng hàm đồng bộ (`def`) còn `async def root()` dùng bất đồng bộ? ([`omniparserserver.py:L38-L51`](file:///home/thai/Downloads/omniparser/omnitool/omniparserserver/omniparserserver.py#L38-L51))
- Trong **FastAPI**, nếu một route thực hiện tính toán nặng trên CPU/GPU (`omniparser.parse(...)` mất 1–5 giây) mà khai báo là `async def`, nó sẽ chạy trực tiếp trên **Main Event Loop** và làm treo toàn bộ server (khiến các lệnh kiểm tra sức khoẻ `GET /probe` từ Gradio bị timeout).
- Khi khai báo là **`def parse(parse_request: ParseRequest):`** (không có `async`), FastAPI tự động đẩy tác vụ `omniparser.parse()` sang một **Worker Threadpool riêng biệt**, giữ cho Event Loop chính luôn rảnh để phản hồi `GET /probe` ngay lập tức (dưới 2ms) ngay cả khi đang phân tích ảnh!
- Hỗ trợ đồng thời cả 2 đường dẫn có và không có dấu gạch chéo cuối (`/parse` và `/parse/`, `/probe` và `/probe/`).

---

## 3. Minh Chứng & Kiểm Chứng Thực Tế (Verification)

Kiểm chứng phản hồi trực tiếp của `omniparserserver` đang chạy tại cổng `8000` và kiểm tra cấu trúc JSON trả về từ `POST /parse/`:

```bash
.venv/bin/python -c '
import requests, base64
from io import BytesIO
from PIL import Image, ImageDraw

# 1. Kiểm tra GET /probe
probe_resp = requests.get("http://127.0.0.1:8000/probe", timeout=3).json()
print("1. GET /probe:", probe_resp)

# 2. Tạo ảnh test nhỏ có chữ rõ ràng và gửi tới POST /parse/
img = Image.new("RGB", (400, 120), color=(255, 255, 255))
d = ImageDraw.Draw(img)
d.rectangle([20, 20, 180, 80], outline=(0, 0, 0), width=2)
d.text((50, 45), "SEARCH", fill=(0, 0, 0))
buf = BytesIO()
img.save(buf, format="PNG")
b64_str = base64.b64encode(buf.getvalue()).decode()

parse_resp = requests.post("http://127.0.0.1:8000/parse/", json={"base64_image": b64_str}, timeout=30).json()
print("2. POST /parse/ keys:", list(parse_resp.keys()))
print("3. Latency:", round(parse_resp["latency"], 3), "s")
print("4. Parsed elements:", parse_resp["parsed_content_list"])
'
```

**Kết quả thực thi thực tế:**
```text
1. GET /probe: {'message': 'Omniparser API ready'}
2. POST /parse/ keys: ['som_image_base64', 'parsed_content_list', 'latency']
3. Latency: 0.412 s
4. Parsed elements: [{'type': 'text', 'bbox': [0.115, 0.35, 0.255, 0.491], 'interactivity': False, 'content': 'SEARCH', 'source': 'box_ocr_content_ocr'}]
```

