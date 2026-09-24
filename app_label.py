import streamlit as st
import pandas as pd
import os

# Cấu hình giao diện rộng rãi
st.set_page_config(page_title="Công cụ Gán nhãn - Đồ án 1 UIT", layout="wide")

# 1. Chọn người gán nhãn (Để tách biệt file của Huy và An, không sợ đè dữ liệu)
st.sidebar.title("👤 Người thực hiện")
annotator = st.sidebar.selectbox("Bạn là ai?", ["Quang Huy", "Thu An"])
file_name = f"pilot_annotation_{annotator.replace(' ', '_').lower()}.csv"

# 2. Khởi tạo dữ liệu mẫu nếu chưa có file
if not os.path.exists(file_name):
    # Kiểm tra xem có file dữ liệu gốc nào trong thư mục không
    raw_source = None
    for candidate in ["pilot_raw.xlsx", "raw_data.xlsx", "data.xlsx", "raw_data.csv", "data.csv"]:
        if os.path.exists(candidate):
            raw_source = candidate
            break

    if raw_source:
        if raw_source.endswith(".csv"):
            df = pd.read_csv(raw_source)
        else:
            df = pd.read_excel(raw_source)
    else:
        # Dữ liệu demo để test thử tool
        df = pd.DataFrame([
            {
                "id": "PL_001",
                "jd_title": "Java Fresher Backend",
                "target_skill": "Spring Data JPA",
                "file_path": "src/main/java/com/demo/repository/UserRepository.java",
                "context_header": "Class: UserRepository | Extends: JpaRepository",
                "code_snippet": "@Repository\npublic interface UserRepository extends JpaRepository<User, Long> {\n    @Query(\"SELECT u FROM User u WHERE u.email = :email\")\n    Optional<User> findByEmail(@Param(\"email\") String email);\n}",
                "label": None,
                "notes": ""
            },
            {
                "id": "PL_002",
                "jd_title": "Frontend React Fresher",
                "target_skill": "Redux Toolkit",
                "file_path": "src/store/index.ts",
                "context_header": "File: store/index.ts",
                "code_snippet": "import { configureStore } from '@reduxjs/toolkit';\n\nexport const store = configureStore({\n  reducer: {},\n});",
                "label": None,
                "notes": ""
            }
        ])
    df["label"] = df.get("label", None)
    df["notes"] = df.get("notes", "")
    df.to_csv(file_name, index=False, encoding="utf-8-sig")
else:
    df = pd.read_csv(file_name)

# Đảm bảo kiểu dữ liệu an toàn (tránh lỗi TypeError float64 trên pandas 3.0+)
if "notes" not in df.columns:
    df["notes"] = ""
else:
    df["notes"] = df["notes"].fillna("").astype(str)

if "label" not in df.columns:
    df["label"] = None
else:
    df["label"] = df["label"].astype(object)

# 3. Quản lý vị trí đang chấm (Index)
if "current_annotator" not in st.session_state or st.session_state.current_annotator != annotator:
    st.session_state.current_annotator = annotator
    unlabeled = df[df["label"].isna()].index
    st.session_state.current_idx = int(unlabeled[0]) if len(unlabeled) > 0 else 0

total = len(df)
if total == 0:
    st.warning("⚠️ Không có dữ liệu để gán nhãn!")
    st.stop()

st.session_state.current_idx = max(0, min(st.session_state.current_idx, total - 1))
idx = st.session_state.current_idx
labeled_count = int(df["label"].notna().sum())

# Thanh tiến độ trên Sidebar
st.sidebar.markdown(f"**Tiến độ của {annotator}:**")
st.sidebar.progress(labeled_count / total)
st.sidebar.write(f"Đã chấm: **{labeled_count} / {total}** mẫu ({(labeled_count/total)*100:.1f}%)")

# Nút tải file CSV kết quả về máy
st.sidebar.markdown("---")
st.sidebar.markdown("### 💾 Xuất dữ liệu")
csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.sidebar.download_button(
    label=f"📥 Tải file kết quả (`{file_name}`)",
    data=csv_bytes,
    file_name=file_name,
    mime="text/csv",
    use_container_width=True
)

# Chức năng nạp dữ liệu thu thập mới trực tiếp từ giao diện
with st.sidebar.expander("📤 Nạp dữ liệu mới (.xlsx / .csv)"):
    st.caption("Upload file dữ liệu mới thu thập để bắt đầu gán nhãn:")
    uploaded_file = st.file_uploader("Chọn file dữ liệu", type=["xlsx", "xls", "csv"], key="raw_uploader")
    if uploaded_file is not None:
        st.warning(f"⚠️ Nạp file mới sẽ cập nhật dữ liệu gán nhãn của **{annotator}**.")
        if st.button(" Bắt đầu gán nhãn file này", type="primary", use_container_width=True):
            try:
                if uploaded_file.name.endswith(".csv"):
                    new_df = pd.read_csv(uploaded_file)
                else:
                    new_df = pd.read_excel(uploaded_file)
                
                if "label" not in new_df.columns:
                    new_df["label"] = None
                if "notes" not in new_df.columns:
                    new_df["notes"] = ""
                
                new_df.to_csv(file_name, index=False, encoding="utf-8-sig")
                st.session_state.current_idx = 0
                st.success("Nạp dữ liệu thành công! Đang tải lại...")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi khi đọc file: {e}")

# Tóm tắt Guideline ngay góc trái để tiện tra cứu
st.sidebar.markdown("---")
st.sidebar.markdown("###  Tóm tắt Guideline:")
st.sidebar.markdown("""
- **Mức 0**: Không liên quan, code boilerplate/tự sinh.
- **Mức 1**: Gián tiếp (chỉ khai báo config, dependency, README, interface rỗng).
- **Mức 2**: Trực tiếp (có logic xử lý nghiệp vụ tự viết).
""")

# 4. Hiển thị nội dung cần gán nhãn
st.title(f" Gán nhãn Mẫu {idx + 1} / {total} (Mã: `{df.at[idx, 'id']}`)")
st.info(f" **Kỹ năng cần đối soát:** :red[**{df.at[idx, 'target_skill']}**] (Vị trí: *{df.at[idx, 'jd_title']}*)")

col_code, col_action = st.columns([3, 1])

with col_code:
    st.caption(f"📁 **File:** `{df.at[idx, 'file_path']}` | 📌 **Bối cảnh:** `{df.at[idx, 'context_header']}`")
    lang = "java" if str(df.at[idx, 'file_path']).endswith(".java") else "typescript"
    # Bôi màu code đẹp mắt
    st.code(df.at[idx, 'code_snippet'], language=lang, line_numbers=True)

with col_action:
    st.write("###  Đánh giá:")
    
    current_label = df.at[idx, 'label']
    if pd.notna(current_label):
        try:
            st.success(f"Đã chấm: **Mức {int(float(current_label))}**")
        except (ValueError, TypeError):
            st.success(f"Đã chấm: **Mức {current_label}**")

    # Ô ghi chú đặt TRƯỚC để note_input luôn sẵn sàng khi lưu nhãn
    current_note = str(df.at[idx, 'notes']) if pd.notna(df.at[idx, 'notes']) else ""
    note_input = st.text_input("Ghi chú (nếu phân vân):", value=current_note, key=f"note_{annotator}_{idx}")

    # Hàm lưu nhãn và sang câu kế tiếp
    def save_and_next(val):
        df.at[idx, 'label'] = val
        df.at[idx, 'notes'] = note_input
        df.to_csv(file_name, index=False, encoding="utf-8-sig")
        if st.session_state.current_idx < total - 1:
            st.session_state.current_idx += 1
        st.rerun()

    if st.button("0️⃣  0 - Không liên quan", use_container_width=True):
        save_and_next(0)

    if st.button("1️⃣  1 - Gián tiếp / Bối cảnh", use_container_width=True):
        save_and_next(1)

    if st.button("2️⃣  2 - Minh chứng trực tiếp", use_container_width=True):
        save_and_next(2)

    st.write("---")
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("⬅️ Câu trước") and st.session_state.current_idx > 0:
            df.at[idx, 'notes'] = note_input
            df.to_csv(file_name, index=False, encoding="utf-8-sig")
            st.session_state.current_idx -= 1
            st.rerun()
    with col_next:
        if st.button("Câu sau ➡️") and st.session_state.current_idx < total - 1:
            df.at[idx, 'notes'] = note_input
            df.to_csv(file_name, index=False, encoding="utf-8-sig")
            st.session_state.current_idx += 1
            st.rerun()