import streamlit as st
import pandas as pd
import os
from pathlib import Path

# Cấu hình giao diện rộng rãi
st.set_page_config(page_title="Công cụ Gán nhãn - Đồ án 1 UIT", layout="wide", page_icon="🏷️")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path("D:/jd-evidence-matching")
DATASET_DIR = PROJECT_DIR / "dataset"

# 1. Chọn người gán nhãn (Để tách biệt file của Huy và An, không sợ đè dữ liệu)
st.sidebar.title("👤 Người thực hiện")
annotator = st.sidebar.selectbox("Bạn là ai?", ["Quang Huy", "Thu An"])

# Tên file lưu theo người gán nhãn
master_file_name = "ground_truth_huy_raw.csv" if annotator == "Quang Huy" else "ground_truth_an_raw.csv"
local_file_path = BASE_DIR / master_file_name
project_file_path = DATASET_DIR / master_file_name

# Ưu tiên nạp từ local_file_path (đảm bảo chạy mượt cả trên Streamlit Cloud và local)
target_file = None
if local_file_path.exists():
    target_file = str(local_file_path)
elif project_file_path.exists():
    target_file = str(project_file_path)
elif (BASE_DIR / f"pilot_annotation_{annotator.replace(' ', '_').lower()}.csv").exists():
    target_file = str(BASE_DIR / f"pilot_annotation_{annotator.replace(' ', '_').lower()}.csv")

# 2. Khởi tạo/Đọc dữ liệu
if target_file and os.path.exists(target_file):
    df = pd.read_csv(target_file, encoding="utf-8-sig")
else:
    # Fallback tìm kiếm file dữ liệu thô
    raw_source = None
    for candidate in [master_file_name, "ground_truth_master.csv", "pilot_raw.xlsx", "raw_data.xlsx", "data.csv"]:
        if (BASE_DIR / candidate).exists():
            raw_source = str(BASE_DIR / candidate)
            break
        elif (DATASET_DIR / candidate).exists():
            raw_source = str(DATASET_DIR / candidate)
            break

    if raw_source:
        df = pd.read_csv(raw_source, encoding="utf-8-sig") if raw_source.endswith(".csv") else pd.read_excel(raw_source)
    else:
        # Dữ liệu demo
        df = pd.DataFrame([{
            "pair_id": "PAIR_001",
            "jd_title": "Backend Developer (Java / Spring Boot)",
            "jd_mandatory_skills": "Java; Spring Boot; Spring Data JPA",
            "file_path": "src/main/java/com/demo/repository/UserRepository.java",
            "context_header": "Class: UserRepository | Extends: JpaRepository",
            "chunk_content": "@Repository\npublic interface UserRepository extends JpaRepository<User, Long> {\n    Optional<User> findByEmail(String email);\n}",
            "human_label": None,
            "human_note": ""
        }])
    target_file = local_file_name
    df.to_csv(target_file, index=False, encoding="utf-8-sig")

# Tự động ánh xạ tên cột thông minh (Hỗ trợ cả Schema cũ Pilot và Schema mới 250 cặp)
col_id = 'pair_id' if 'pair_id' in df.columns else ('id' if 'id' in df.columns else df.columns[0])
col_title = 'jd_title' if 'jd_title' in df.columns else 'title'
col_skill = 'jd_mandatory_skills' if 'jd_mandatory_skills' in df.columns else ('target_skill' if 'target_skill' in df.columns else 'skill')
col_code = 'chunk_content' if 'chunk_content' in df.columns else ('code_snippet' if 'code_snippet' in df.columns else 'code')
col_file = 'file_path' if 'file_path' in df.columns else 'file'
col_header = 'context_header' if 'context_header' in df.columns else 'header'
col_label = 'human_label' if 'human_label' in df.columns else ('label' if 'label' in df.columns else 'human_label')
col_notes = 'human_note' if 'human_note' in df.columns else ('notes' if 'notes' in df.columns else 'human_note')

# Đảm bảo các cột nhãn & ghi chú tồn tại an toàn
if col_notes not in df.columns:
    df[col_notes] = ""
else:
    df[col_notes] = df[col_notes].fillna("").astype(str)

if col_label not in df.columns:
    df[col_label] = None
else:
    df[col_label] = df[col_label].astype(object)

# 3. Quản lý vị trí đang chấm (Index)
if "current_annotator" not in st.session_state or st.session_state.current_annotator != annotator:
    st.session_state.current_annotator = annotator
    unlabeled = df[df[col_label].isna()].index
    st.session_state.current_idx = int(unlabeled[0]) if len(unlabeled) > 0 else 0

total = len(df)
if total == 0:
    st.warning("⚠️ Không có dữ liệu để gán nhãn!")
    st.stop()

st.session_state.current_idx = max(0, min(st.session_state.current_idx, total - 1))
idx = st.session_state.current_idx
labeled_count = int(df[col_label].notna().sum())

# Thông tin file đang thao tác
st.sidebar.caption(f"📁 Tệp đang mở: `{Path(target_file).name}`")

# Thanh tiến độ trên Sidebar
st.sidebar.markdown(f"**Tiến độ của {annotator}:**")
st.sidebar.progress(labeled_count / total)
st.sidebar.write(f"Đã chấm: **{labeled_count} / {total}** mẫu ({(labeled_count/total)*100:.1f}%)")

# Nút tải file CSV kết quả về máy
st.sidebar.markdown("---")
st.sidebar.markdown("### 💾 Xuất dữ liệu")
csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.sidebar.download_button(
    label=f"📥 Tải file kết quả (`{Path(target_file).name}`)",
    data=csv_bytes,
    file_name=Path(target_file).name,
    mime="text/csv",
    use_container_width=True
)

# Chức năng nạp dữ liệu thu thập mới trực tiếp từ giao diện
with st.sidebar.expander("📤 Nạp file dữ liệu khác (.csv / .xlsx)"):
    st.caption("Upload file CSV mới để gán nhãn:")
    uploaded_file = st.file_uploader("Chọn file", type=["xlsx", "xls", "csv"], key="raw_uploader")
    if uploaded_file is not None:
        st.warning(f"⚠️ Nạp file mới sẽ cập nhật dữ liệu gán nhãn của **{annotator}**.")
        if st.button("🚀 Bắt đầu gán nhãn file này", type="primary", use_container_width=True):
            try:
                new_df = pd.read_csv(uploaded_file, encoding="utf-8-sig") if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
                # Tự chuẩn hóa nhãn nếu thiếu
                target_col_lbl = 'human_label' if 'human_label' in new_df.columns else ('label' if 'label' in new_df.columns else 'human_label')
                target_col_nt = 'human_note' if 'human_note' in new_df.columns else ('notes' if 'notes' in new_df.columns else 'human_note')
                if target_col_lbl not in new_df.columns:
                    new_df[target_col_lbl] = None
                if target_col_nt not in new_df.columns:
                    new_df[target_col_nt] = ""
                new_df.to_csv(target_file, index=False, encoding="utf-8-sig")
                st.session_state.current_idx = 0
                st.success("Nạp dữ liệu thành công! Đang tải lại...")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi khi đọc file: {e}")

# Tóm tắt Guideline ngay góc trái để tiện tra cứu
st.sidebar.markdown("---")
st.sidebar.markdown("### 📖 Tóm tắt Guideline:")
st.sidebar.markdown("""
- **Mức 0**: Không liên quan, code boilerplate/tự sinh, khác ngôn ngữ/nghiệp vụ.
- **Mức 1**: Gián tiếp (chỉ khai báo config, dependency, README, entity/interface đơn giản).
- **Mức 2**: Trực tiếp (có logic xử lý nghiệp vụ tự viết, REST API, Service, Custom Hook).
""")

# 4. Hiển thị nội dung cần gán nhãn
item_id = df.at[idx, col_id] if col_id in df.columns else f"INDEX_{idx+1}"
item_title = df.at[idx, col_title] if col_title in df.columns else "N/A"
item_skill = df.at[idx, col_skill] if col_skill in df.columns else "N/A"
item_repo = df.at[idx, 'repo_name'] if 'repo_name' in df.columns else None
item_level = df.at[idx, 'jd_level'] if 'jd_level' in df.columns else None
item_domain = df.at[idx, 'jd_domain'] if 'jd_domain' in df.columns else None

st.title(f"🏷️ Gán nhãn Mẫu {idx + 1} / {total} (Mã: `{item_id}`)")

extra_info = []
if item_level and pd.notna(item_level): extra_info.append(f"Cấp bậc: **{item_level}**")
if item_domain and pd.notna(item_domain): extra_info.append(f"Lĩnh vực: **{item_domain}**")
if item_repo and pd.notna(item_repo): extra_info.append(f"Repo: `📂 {item_repo}`")
extra_str = (" | " + " | ".join(extra_info)) if extra_info else ""

st.info(f"🎯 **Kỹ năng yêu cầu trong JD:** :red[**{item_skill}**] (Vị trí: *{item_title}*{extra_str})")

col_code, col_action = st.columns([3, 1])

with col_code:
    file_p = df.at[idx, col_file] if col_file in df.columns else "unknown_file"
    ctx_hdr = df.at[idx, col_header] if col_header in df.columns else ""
    st.caption(f"📁 **File:** `{file_p}` | 📌 **Bối cảnh:** `{ctx_hdr}`")
    lang = "java" if str(file_p).endswith(".java") else "typescript"
    code_text = str(df.at[idx, col_code]) if col_code in df.columns else "# No code snippet"
    st.code(code_text, language=lang, line_numbers=True)

    # Mục xem gợi ý AI (Mặc định đóng để đảm bảo nguyên tắc gán nhãn mù độc lập)
    if 'gemini_suggested_label' in df.columns and pd.notna(df.at[idx, 'gemini_suggested_label']):
        with st.expander("🤖 Gợi ý tham khảo từ Gemini AI (Nhấn mở khi phân vân)"):
            ai_lbl = int(float(df.at[idx, 'gemini_suggested_label']))
            ai_rs = df.at[idx, 'gemini_reason'] if 'gemini_reason' in df.columns else ""
            st.markdown(f"- **Đề xuất của AI:** :blue[**Mức {ai_lbl}**]")
            st.markdown(f"- **Lý do chuyên môn:** *{ai_rs}*")

with col_action:
    st.write("### ✍️ Đánh giá của bạn:")
    
    current_label = df.at[idx, col_label]
    if pd.notna(current_label):
        try:
            st.success(f"Đã chấm: **Mức {int(float(current_label))}**")
        except (ValueError, TypeError):
            st.success(f"Đã chấm: **Mức {current_label}**")

    # Ô ghi chú
    current_note = str(df.at[idx, col_notes]) if pd.notna(df.at[idx, col_notes]) else ""
    note_input = st.text_input("Ghi chú (nếu phân vân):", value=current_note, key=f"note_{annotator}_{idx}")

    # Hàm lưu nhãn và sang câu kế tiếp
    def save_and_next(val):
        df.at[idx, col_label] = val
        df.at[idx, col_notes] = note_input
        df.to_csv(target_file, index=False, encoding="utf-8-sig")
        if project_file_path.exists() and str(project_file_path) != str(target_file):
            try:
                df.to_csv(str(project_file_path), index=False, encoding="utf-8-sig")
            except Exception:
                pass
        if st.session_state.current_idx < total - 1:
            st.session_state.current_idx += 1
        st.rerun()

    if st.button("0️⃣ - Không liên quan", use_container_width=True):
        save_and_next(0)

    if st.button("1️⃣ - Gián tiếp / Bối cảnh", use_container_width=True):
        save_and_next(1)

    if st.button("2️⃣ - Minh chứng trực tiếp", use_container_width=True):
        save_and_next(2)

    st.write("---")
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.button("⬅️ Câu trước") and st.session_state.current_idx > 0:
            df.at[idx, col_notes] = note_input
            df.to_csv(target_file, index=False, encoding="utf-8-sig")
            if project_file_path.exists() and str(project_file_path) != str(target_file):
                try:
                    df.to_csv(str(project_file_path), index=False, encoding="utf-8-sig")
                except Exception:
                    pass
            st.session_state.current_idx -= 1
            st.rerun()
    with col_next:
        if st.button("Câu sau ➡️") and st.session_state.current_idx < total - 1:
            df.at[idx, col_notes] = note_input
            df.to_csv(target_file, index=False, encoding="utf-8-sig")
            if project_file_path.exists() and str(project_file_path) != str(target_file):
                try:
                    df.to_csv(str(project_file_path), index=False, encoding="utf-8-sig")
                except Exception:
                    pass
            st.session_state.current_idx += 1
            st.rerun()