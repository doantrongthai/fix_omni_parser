# Tài Liệu Chi Tiết Thư Mục `imgs/` (Demo Images & UI Assets)

Thư mục [`imgs/`](file:///home/thai/Downloads/omniparser/imgs) chứa hai nhóm tài nguyên hình ảnh được sử dụng trực tiếp bởi mã nguồn trong dự án:

---

## 1. Tài Nguyên Giao Diện Web (UI Assets)
- [`imgs/header_bar_thin.png`](file:///home/thai/Downloads/omniparser/imgs/header_bar_thin.png) & [`imgs/header_bar.png`](file:///home/thai/Downloads/omniparser/imgs/header_bar.png): Ảnh banner đầu trang được nạp trực tiếp bởi hàm `get_header_image_base64()` trong [`omnitool/gradio/app.py:L264-L275`](file:///home/thai/Downloads/omniparser/omnitool/gradio/app.py#L264-L275):
  ```python
  def get_header_image_base64():
      try:
          script_dir = Path(__file__).parent
          image_path = script_dir.parent.parent / "imgs" / "header_bar_thin.png"
          
          with open(image_path, "rb") as image_file:
              encoded_string = base64.b64encode(image_file.read()).decode()
              return f'data:image/png;base64,{encoded_string}'
      except Exception as e:
          print(f"Failed to load header image: {e}")
          return None
  ```
- [`imgs/logo.png`](file:///home/thai/Downloads/omniparser/imgs/logo.png), [`imgs/omniparsericon.png`](file:///home/thai/Downloads/omniparser/imgs/omniparsericon.png), [`imgs/omniboxicon.png`](file:///home/thai/Downloads/omniparser/imgs/omniboxicon.png), [`imgs/gradioicon.png`](file:///home/thai/Downloads/omniparser/imgs/gradioicon.png): Các biểu tượng minh hoạ trong `README.md` và `omnitool/readme.md`.

---

## 2. Bộ Ảnh Mẫu Kiểm Thử (Sample GUI Screenshots)
Được sử dụng trong [`demo.ipynb`](file:///home/thai/Downloads/omniparser/demo.ipynb) và [`gradio_demo.py`](file:///home/thai/Downloads/omniparser/gradio_demo.py) để kiểm thử khả năng nhận diện chữ + icon trên nhiều nền tảng hệ điều hành:
- **Desktop Windows & Office:** `windows_home.png`, `word.png`, `excel.png`, `onenote.png`, `teams.png`, `windows_multitab.png`.
- **Trình duyệt Web:** `google_page.png`.
- **Thiết bị di động (iOS / Android):** `ios.png`, `mobile.png`.
- **Ảnh minh hoạ kết quả Set-of-Mark (SoM):** `demo_image.jpg` $\rightarrow$ `demo_image_som.jpg`, `som_overlaid_omni.png`.

