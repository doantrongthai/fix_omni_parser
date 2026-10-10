# Hướng Dẫn Vận Hành OmniParser & OmniTool Trên Linux (2 Chế Độ: Colab GPU & Local CPU)

Tài liệu hướng dẫn đầy đủ 2 chế độ vận hành hệ thống điều khiển máy tính tự động (**Host Execution**) trên Ubuntu/Linux:
1. **Kiểu 1 (Google Colab GPU):** Chạy **100% Pipeline gốc** của Microsoft (YOLOv8 + Florence-2 Full Captioning + EasyOCR) trên GPU T4 miễn phí của Colab, truyền kết quả về điều khiển máy Linux của bạn (~1.2s/bước).
2. **Kiểu 2 (Local CPU Tối Ưu):** Chạy **100% trên máy cá nhân** không cần GPU rời, đã được tối ưu Fast Mode (~3.5s/bước).

> 💡 **Tiện ích đã tích hợp sẵn:** Model `omniparser + R1` (Groq) đã được cài làm mặc định trong code. Bạn có thể đặt `export GROQ_API_KEY="your_api_key"` trước khi chạy hoặc nhập trực tiếp trên giao diện web.

---

## ⚖️ So Sánh 2 Chế Độ Chạy

| Đặc điểm | Kiểu 1: Google Colab (GPU) | Kiểu 2: Local Linux (CPU Tối Ưu) |
| :--- | :--- | :--- |
| **Mô hình nhận diện** | **100% Gốc:** YOLOv8 (`0.05`) + Florence-2 sinh mô tả chi tiết cho toàn bộ icon + EasyOCR | **Tối ưu CPU:** YOLOv8 (`0.15`) + EasyOCR + Gán nhãn vị trí không gian thông minh |
| **Tốc độ mỗi bước** | **~1.0 – 1.5 giây** (nhờ GPU T4 16GB) | **~3.5 – 5.0 giây** (chạy trực tiếp trên CPU) |
| **Số Terminal trên máy** | Chỉ cần mở **2 Terminal** (5000 & 7888) | Mở **3 Terminal** (8000, 5000 & 7888) |
| **Điều khiển chuột/phím** | Trực tiếp trên máy Linux thật của bạn | Trực tiếp trên máy Linux thật của bạn |

---

## 🚀 KIỂU 1: Chạy Với Google Colab GPU (100% Pipeline Gốc)

### Bước 1: Khởi chạy Server GPU trên Google Colab
1. Truy cập [Google Colab](https://colab.research.google.com/).
2. Chọn **File $\rightarrow$ Upload notebook** và tải file **[`omniparser_colab_server.ipynb`](file:///home/thai/Downloads/omniparser/omniparser_colab_server.ipynb)** (nằm sẵn trong thư mục `/home/thai/Downloads/omniparser`) lên.
3. Trên menu Colab, chọn **Runtime $\rightarrow$ Change runtime type $\rightarrow$ T4 GPU**.
4. Bấm **Runtime $\rightarrow$ Run all**.
5. Đợi khoảng 2 phút, ở ô cuối cùng sẽ in ra đường link Public dạng:
   ```text
   🌐 LINK PUBLIC COLAB GPU CỦA BẠN: https://xxxx-xxxx.trycloudflare.com
   ```

### Bước 2: Mở 2 Terminal trên máy Linux của bạn

#### Terminal 1 (Trên máy Linux): Khởi chạy Host Control (Cổng 5000)
```bash
cd /home/thai/Downloads/omniparser/omnitool
source ../.venv/bin/activate
python linux_host_server.py
```

#### Terminal 2 (Trên máy Linux): Khởi chạy Gradio kết nối vào Colab GPU (Cổng 7888)
*(Thay đường link `https://xxxx-xxxx.trycloudflare.com` bằng link hiển thị trên Colab của bạn)*:
```bash
cd /home/thai/Downloads/omniparser/omnitool/gradio
source ../../.venv/bin/activate
python app.py --windows_host_url localhost:5000 --omniparser_server_url https://xxxx-xxxx.trycloudflare.com
```

---

## 💻 KIỂU 2: Chạy 100% Trên Máy Local (CPU Tối Ưu)

Nếu không muốn mở Google Colab, bạn chạy toàn bộ trên máy tính bằng 3 cửa sổ Terminal:

### Terminal 1: Khởi chạy OmniParser Server ở chế độ CPU Fast Mode (Cổng 8000)
```bash
cd /home/thai/Downloads/omniparser/omnitool/omniparserserver
source ../../.venv/bin/activate
python -m omniparserserver --device cpu --host 127.0.0.1 --port 8000
```
*(Hệ thống tự động nhận diện `cpu` và kích hoạt Fast Mode: `full_caption=False`, `BOX_TRESHOLD=0.15` giúp chạy nhanh gấp 20 lần).*

### Terminal 2: Khởi chạy Linux Host Control Server (Cổng 5000)
```bash
cd /home/thai/Downloads/omniparser/omnitool
source ../.venv/bin/activate
python linux_host_server.py
```

### Terminal 3: Khởi chạy Gradio Agent Web UI (Cổng 7888)
```bash
cd /home/thai/Downloads/omniparser/omnitool/gradio
source ../../.venv/bin/activate
python app.py --windows_host_url localhost:5000 --omniparser_server_url localhost:8000
```

---

## 🌐 Thao Tác Trên Giao Diện Web UI (`http://127.0.0.1:7888`)

1. Mở trình duyệt vào địa chỉ: **`http://127.0.0.1:7888`**
2. **Model (`omniparser + R1`), Provider (`groq`) và API Key của bạn đã được điền sẵn tự động.**
3. **Quan trọng trước khi bấm Send:**
   - Thu gọn hoặc đặt cửa sổ Web UI sang một nửa màn hình, để nửa màn hình còn lại hiển thị rõ trang web (Google, Bing, YouTube, GitHub...) mà bạn muốn Agent thao tác.
4. Nhập câu lệnh vào ô chat và nhấn **Send**.

---

## 🎯 Bộ Prompt Mẫu Chuẩn Cho Agent

### Nhóm 1: Tìm Kiếm Trên Web (Google / Bing)

- **Mẫu 1.1 (Tìm kiếm từ khóa và nhấn Enter):**
  ```text
  Click vào thanh tìm kiếm trên màn hình, gõ 'DeepMind Robotics' và nhấn Enter.
  ```
- **Mẫu 1.2 (Bằng tiếng Anh):**
  ```text
  Click on the search input box, type 'OmniParser Microsoft GitHub' and press Enter.
  ```
- **Mẫu 1.3 (Mở kết quả đầu tiên sau khi tìm kiếm):**
  ```text
  Nhìn vào danh sách kết quả tìm kiếm, click chuột trái vào tiêu đề kết quả đầu tiên để mở trang web.
  ```

---

### Nhóm 2: Điều Hướng & Tương Tác Trang Web

- **Mẫu 2.1 (Cuộn trang xem nội dung bên dưới):**
  ```text
  Cuộn màn hình xuống dưới (scroll_down) để xem các kết quả tiếp theo.
  ```
- **Mẫu 2.2 (Tương tác trên GitHub):**
  ```text
  Click vào thanh tìm kiếm 'Type / to search' ở góc trên trang GitHub, gõ 'omniparser' và nhấn Enter.
  ```
- **Mẫu 2.3 (Tìm kiếm trên YouTube):**
  ```text
  Click vào ô 'Search' ở phía trên trang YouTube, gõ 'AI Agent Demo' và nhấn Enter.
  ```

---

### Nhóm 3: Điền Biểu Mẫu (Form) Nhiều Bước

- **Mẫu 3.1 (Điền thông tin tuần tự):**
  ```text
  1. Click vào ô nhập 'Username' và gõ 'thai_admin'.
  2. Sau đó click vào nút 'Continue' hoặc 'Submit'.
  ```

---

## 🛡️ Mẹo Xử Lý Sự Cố Nhanh

1. **Muốn dừng Agent ngay lập tức:** Bấm nút **Stop** trên giao diện web `http://127.0.0.1:7888` hoặc nhấn `Ctrl + C` ở Terminal 3.
2. **Nếu muốn bật đầy đủ Florence-2 Captioning ngay trên CPU (chấp nhận đợi ~30s):**
   Chạy Terminal 1 với cờ `--use_local_semantics true`:
   ```bash
   python -m omniparserserver --device cpu --use_local_semantics true --host 127.0.0.1 --port 8000
   ```
