import streamlit as st
import pandas as pd
import os
from pathlib import Path

# Cấu hình giao diện rộng rãi
st.set_page_config(page_title="Công cụ Gán nhãn - JD Evidence Matching (IEEE SANER 2027)", layout="wide", page_icon="🏷️")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path("D:/jd-evidence-matching")
DATASET_DIR = PROJECT_DIR / "dataset"

# 1. Chọn người gán nhãn
st.sidebar.title("👤 Người thực hiện")
annotator_choice = st.sidebar.selectbox(
    "Bạn là ai?",
    ["Quang Huy (Annotator 1)", "Thu An (Annotator 2)"]
)
annotator = "Quang Huy" if "Quang Huy" in annotator_choice else "Thu An"
is_annotator_1 = (annotator == "Quang Huy")

# Tên file chính và file phụ tương ứng với người gán nhãn
primary_file = "ground_truth_huy_raw.csv" if is_annotator_1 else "ground_truth_an_raw.csv"
fallback_file = "annotator1_blank.csv" if is_annotator_1 else "annotator2_blank.csv"

# Tìm file phù hợp trên máy
candidate_files = []
for f in [primary_file, fallback_file]:
    if (BASE_DIR / f).exists():
        candidate_files.append(str(BASE_DIR / f))
    elif (DATASET_DIR / f).exists():
        candidate_files.append(str(DATASET_DIR / f))

# Loại bỏ trùng lặp nếu có
candidate_files = list(dict.fromkeys(candidate_files))

target_file = None
if candidate_files:
    target_file = candidate_files[0]
else:
    target_file = str(BASE_DIR / primary_file)

# 2. Khởi tạo/Đọc dữ liệu
if target_file and os.path.exists(target_file):
    df = pd.read_csv(target_file, encoding="utf-8-sig")
else:
    st.error(f"⚠️ Không tìm thấy file dữ liệu `{primary_file}` hoặc `{fallback_file}`!")
    st.stop()

# Tự động ánh xạ tên cột thông minh (Hỗ trợ đa dạng schema)
col_name_id = 'pair_id' if 'pair_id' in df.columns else ('id' if 'id' in df.columns else df.columns[0])
col_name_title = 'jd_title' if 'jd_title' in df.columns else 'title'
col_name_skill = 'jd_mandatory_skills' if 'jd_mandatory_skills' in df.columns else ('target_skill' if 'target_skill' in df.columns else 'skill')
col_name_code = 'chunk_content' if 'chunk_content' in df.columns else ('raw_code_without_header' if 'raw_code_without_header' in df.columns else ('code_snippet' if 'code_snippet' in df.columns else 'code'))
col_name_file = 'file_path' if 'file_path' in df.columns else 'file'
col_name_header = 'context_header' if 'context_header' in df.columns else 'header'

# Xác định cột nhãn người dùng
score_col = 'annotator1_score' if is_annotator_1 else 'annotator2_score'
col_name_label = 'human_label' if 'human_label' in df.columns else (score_col if score_col in df.columns else ('label' if 'label' in df.columns else 'human_label'))
col_name_notes = 'human_note' if 'human_note' in df.columns else ('notes' if 'notes' in df.columns else 'human_note')

# Đảm bảo các cột nhãn & ghi chú tồn tại an toàn
if col_name_notes not in df.columns:
    df[col_name_notes] = ""
else:
    df[col_name_notes] = df[col_name_notes].fillna("").astype(str)

if col_name_label not in df.columns:
    df[col_name_label] = None
else:
    df[col_name_label] = df[col_name_label].astype(object)

if score_col not in df.columns:
    df[score_col] = df[col_name_label]

# Đảm bảo cột chunk_content tồn tại nếu chỉ có raw_code_without_header
if 'chunk_content' not in df.columns and 'raw_code_without_header' in df.columns:
    df['chunk_content'] = df['raw_code_without_header']

# 3. Quản lý vị trí đang chấm (Index)
if "current_annotator" not in st.session_state or st.session_state.current_annotator != annotator:
    st.session_state.current_annotator = annotator
    unlabeled = df[df[col_name_label].isna()].index
    st.session_state.current_idx = int(unlabeled[0]) if len(unlabeled) > 0 else 0

total = len(df)
if total == 0:
    st.warning("⚠️ Không có dữ liệu để gán nhãn!")
    st.stop()

st.session_state.current_idx = max(0, min(st.session_state.current_idx, total - 1))
idx = st.session_state.current_idx
labeled_count = int(df[col_name_label].notna().sum())

# Thông tin file đang thao tác
st.sidebar.caption(f"📁 Tệp đang mở: `{Path(target_file).name}`")

# Thanh tiến độ trên Sidebar
st.sidebar.markdown(f"**Tiến độ của {annotator}:**")
st.sidebar.progress(labeled_count / total)
st.sidebar.write(f"Đã chấm: **{labeled_count} / {total}** mẫu ({(labeled_count/total)*100:.1f}%)")

# Nút chuyển nhanh đến câu chưa chấm
if st.sidebar.button("⏭️ Nhảy đến câu chưa làm tiếp theo", use_container_width=True):
    unlabeled = df[df[col_name_label].isna()].index
    future_unlabeled = [i for i in unlabeled if i > idx]
    if future_unlabeled:
        st.session_state.current_idx = int(future_unlabeled[0])
    elif len(unlabeled) > 0:
        st.session_state.current_idx = int(unlabeled[0])
    else:
        st.sidebar.success("🎉 Bạn đã hoàn thành tất cả các mẫu!")
    st.rerun()

# Ô nhảy nhanh tới số câu cụ thể
jump_idx = st.sidebar.number_input(
    "Nhảy tới mẫu số:",
    min_value=1,
    max_value=total,
    value=idx + 1,
    step=1,
    key="jump_box"
)
if jump_idx - 1 != idx:
    st.session_state.current_idx = jump_idx - 1
    st.rerun()

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
st.sidebar.markdown("### 📖 Hướng dẫn Chấm điểm (SANER 2027):")
st.sidebar.markdown("""
- **Mức 0 (Không liên quan / Rác)**: Khác công nghệ, import, class/interface rỗng, UI toast tĩnh, thiếu ngữ cảnh.
- **Mức 1 (Gián tiếp / Ngoại vi)**: Cấu hình cơ bản (Swagger), CRUD chuyển tiếp không có logic, hoặc đoạn code bị cắt dở mất logic cốt lõi.
- **Mức 2 (Trực tiếp / Mạnh mẽ)**: Bằng chứng cốt lõi (Spring Security JWT, custom React hook, REST API có auth & validation).  
  *Lưu ý:* Đoạn code bị cắt dở ở cuối nhưng phần nhìn thấy đã đủ bằng chứng thì **vẫn đạt Mức 2**.
""")

# 4. Hiển thị nội dung cần gán nhãn
item_id = df.at[idx, col_name_id] if col_name_id in df.columns else f"INDEX_{idx+1}"
item_title = df.at[idx, col_name_title] if col_name_title in df.columns else "N/A"
item_skill = df.at[idx, col_name_skill] if col_name_skill in df.columns else "N/A"
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

ui_col_code, ui_col_action = st.columns([3, 1])

with ui_col_code:
    file_p = df.at[idx, col_name_file] if col_name_file in df.columns else "unknown_file"
    ctx_hdr = df.at[idx, col_name_header] if col_name_header in df.columns else ""
    st.caption(f"📁 **File:** `{file_p}` | 📌 **Bối cảnh:** `{ctx_hdr}`")
    lang = "java" if str(file_p).endswith(".java") else "typescript"
    raw_code = df.at[idx, col_name_code] if col_name_code in df.columns else None
    if pd.notna(raw_code) and str(raw_code).strip():
        code_text = str(raw_code)
    else:
        code_text = "// Không tìm thấy nội dung mã nguồn"
    st.code(code_text, language=lang, line_numbers=True)

    # Mục xem gợi ý AI (Mặc định đóng để đảm bảo nguyên tắc gán nhãn mù độc lập)
    has_ai_suggest = 'gemini_suggested_label' in df.columns and pd.notna(df.at[idx, 'gemini_suggested_label'])
    ai_lbl = None
    ai_rs = ""
    if has_ai_suggest:
        ai_lbl = int(float(df.at[idx, 'gemini_suggested_label']))
        ai_rs = df.at[idx, 'gemini_reason'] if 'gemini_reason' in df.columns else ""
        lbl_badge = ":red[**Mức 0 (Không liên quan)**]" if ai_lbl == 0 else (":orange[**Mức 1 (Gián tiếp / Ngoại vi)**]" if ai_lbl == 1 else ":green[**Mức 2 (Minh chứng trực tiếp)**]")
        with st.expander("🤖 Gợi ý tham khảo từ Gemini AI (Nhấn mở khi phân vân)"):
            st.markdown(f"- **Đề xuất của AI:** {lbl_badge}")
            st.markdown(f"- **Lý do chuyên môn:** *{ai_rs}*")

with ui_col_action:
    st.write("### ✍️ Đánh giá của bạn:")
    
    current_label = df.at[idx, col_name_label]
    if pd.notna(current_label):
        try:
            cur_lbl_int = int(float(current_label))
            badge = "0️⃣ Không liên quan" if cur_lbl_int == 0 else ("1️⃣ Gián tiếp / Bối cảnh" if cur_lbl_int == 1 else "2️⃣ Minh chứng trực tiếp")
            st.success(f"Đã chấm: **Mức {cur_lbl_int}** ({badge})")
        except (ValueError, TypeError):
            st.success(f"Đã chấm: **Mức {current_label}**")
    else:
        st.info("Chưa gán nhãn cho mẫu này.")

    # Ô ghi chú
    current_note = str(df.at[idx, col_name_notes]) if pd.notna(df.at[idx, col_name_notes]) else ""
    note_input = st.text_input("Ghi chú (nếu phân vân):", value=current_note, key=f"note_{annotator}_{idx}")

    # Hàm lưu nhãn và sang câu kế tiếp
    def save_and_next(val):
        df.at[idx, col_name_label] = val
        if score_col in df.columns:
            df.at[idx, score_col] = val
        df.at[idx, col_name_notes] = note_input
        if 'notes' in df.columns:
            df.at[idx, 'notes'] = note_input

        # Lưu file đích
        df.to_csv(target_file, index=False, encoding="utf-8-sig")

        # Đồng bộ sang các file liên quan nếu tồn tại
        sync_files = [
            BASE_DIR / primary_file,
            BASE_DIR / fallback_file,
            DATASET_DIR / primary_file
        ]
        for sf in sync_files:
            if sf.exists() and str(sf.resolve()) != str(Path(target_file).resolve()):
                try:
                    df.to_csv(str(sf), index=False, encoding="utf-8-sig")
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

    # Nút bấm 1-click áp dụng gợi ý AI nếu có
    if has_ai_suggest and ai_lbl is not None:
        st.write("")
        if st.button(f"🤖 Đồng ý theo AI (Chấm Mức {ai_lbl})", type="secondary", use_container_width=True):
            save_and_next(ai_lbl)

    st.write("---")
    ui_col_prev, ui_col_next = st.columns(2)
    with ui_col_prev:
        if st.button("⬅️ Câu trước", use_container_width=True) and st.session_state.current_idx > 0:
            df.at[idx, col_name_notes] = note_input
            df.to_csv(target_file, index=False, encoding="utf-8-sig")
            st.session_state.current_idx -= 1
            st.rerun()
    with ui_col_next:
        if st.button("Câu sau ➡️", use_container_width=True) and st.session_state.current_idx < total - 1:
            df.at[idx, col_name_notes] = note_input
            df.to_csv(target_file, index=False, encoding="utf-8-sig")
            st.session_state.current_idx += 1
            st.rerun()