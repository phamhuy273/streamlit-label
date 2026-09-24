# Streamlit Labeling Tool - Đồ án 1 UIT

Công cụ hỗ trợ gán nhãn dữ liệu đánh giá kỹ năng từ mã nguồn (code snippet) và tin tuyển dụng (JD).

## 🚀 Cài đặt & Khởi chạy

1. Cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt
```

2. Khởi chạy ứng dụng Streamlit:
```bash
python -m streamlit run app_label.py
```

Trình duyệt sẽ tự động mở ứng dụng tại `http://localhost:8501`.

## 📌 Tính năng chính
- **Tách biệt người gán nhãn**: Chọn người thực hiện (Quang Huy / Thu An) để lưu file độc lập, không sợ đè dữ liệu.
- **Tự động lưu**: Kết quả được tự động lưu liên tục vào file CSV trên máy và có nút tải file trực tiếp trên web (`utf-8-sig` hỗ trợ tiếng Việt trên Excel).
- **Nạp dữ liệu mới**: Hỗ trợ upload trực tiếp file `.xlsx` hoặc `.csv` từ giao diện để bắt đầu phiên gán nhãn mới.
- **Thanh tiến độ & Tóm tắt Guideline**: Theo dõi tiến độ trực quan ngay trên sidebar.
