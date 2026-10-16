import streamlit as st
import pandas as pd
import json
import os
import re
from pathlib import Path

# Cấu hình giao diện Streamlit rộng rãi
st.set_page_config(
    page_title="Công cụ Gán nhãn - JD Evidence Matching (IEEE SANER 2027)",
    layout="wide",
    page_icon="🏷️"
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path("D:/jd-evidence-matching")
DATASET_DIR = PROJECT_DIR / "dataset"

# 1. Chọn người gán nhãn
st.sidebar.title("👤 Người thực hiện")
annotator_choice = st.sidebar.selectbox(
    "Bạn là ai?",
    ["Quang Huy (Annotator 1)", "Thu An (Annotator 2)"]
)
is_annotator_1 = ("Quang Huy" in annotator_choice or "Annotator 1" in annotator_choice)
annotator_name = "Quang Huy" if is_annotator_1 else "Thu An"
score_col = "annotator1_score" if is_annotator_1 else "annotator2_score"

# Xác định file mục tiêu (Ưu tiên annotator1_blank.csv / annotator2_blank.csv hoặc ground_truth_huy_raw.csv / ground_truth_an_raw.csv)
candidate_files = []
if is_annotator_1:
    candidate_files = ["annotator1_blank.csv", "ground_truth_huy_raw.csv"]
else:
    candidate_files = ["annotator2_blank.csv", "ground_truth_an_raw.csv"]

target_file = None
for f in candidate_files:
    if (BASE_DIR / f).exists():
        target_file = str(BASE_DIR / f)
        break
    elif (DATASET_DIR / f).exists():
        target_file = str(DATASET_DIR / f)
        break

if not target_file:
    target_file = str(BASE_DIR / candidate_files[0])

# Danh sách 10 cột nguyên bản đúng cấu trúc ban đầu
ORIGINAL_COLUMNS = [
    'pair_id',
    'query_id',
    'jd_requirement_text',
    'repo_name',
    'file_path',
    'start_line',
    'end_line',
    'raw_code_without_header',
    score_col,
    'notes'
]

# 2. Đọc dữ liệu
if not os.path.exists(target_file):
    st.error(f"⚠️ Không tìm thấy file dữ liệu `{Path(target_file).name}`!")
    st.stop()

df = pd.read_csv(target_file, encoding="utf-8-sig")

# Đảm bảo các cột tối thiểu tồn tại
if score_col not in df.columns:
    # Nếu file có annotator1_score mà đang ở mode annotator 2 hoặc ngược lại, copy sang
    alt_score = 'annotator2_score' if is_annotator_1 else 'annotator1_score'
    if alt_score in df.columns:
        df[score_col] = df[alt_score]
    elif 'human_label' in df.columns:
        df[score_col] = df['human_label']
    else:
        df[score_col] = None

if 'notes' not in df.columns:
    if 'human_note' in df.columns:
        df['notes'] = df['human_note']
    else:
        df['notes'] = ""

# Khắc phục triệt để lỗi LossySetitemError trên Pandas 2.x/3.x:
# Ép kiểu an toàn ngay khi load
df['notes'] = df['notes'].fillna("").astype(str)
df[score_col] = df[score_col].astype(object)

# Tải từ điển gợi ý từ Gemini AI (nếu có)
gemini_sug_file = BASE_DIR / "gemini_suggestions.json"
gemini_map = {}
if gemini_sug_file.exists():
    try:
        with open(gemini_sug_file, "r", encoding="utf-8") as f:
            gemini_map = json.load(f)
    except Exception:
        pass

# 3. Quản lý vị trí đang chấm (Index)
total = len(df)
if total == 0:
    st.warning("⚠️ Tập dữ liệu rỗng!")
    st.stop()

if "current_annotator" not in st.session_state or st.session_state.current_annotator != annotator_name:
    st.session_state.current_annotator = annotator_name
    unlabeled = df[df[score_col].isna() | (df[score_col] == "")].index
    st.session_state.current_idx = int(unlabeled[0]) if len(unlabeled) > 0 else 0

st.session_state.current_idx = max(0, min(st.session_state.current_idx, total - 1))
idx = st.session_state.current_idx

# Đếm số mẫu đã gán nhãn
labeled_mask = df[score_col].notna() & (df[score_col] != "")
labeled_count = int(labeled_mask.sum())

# Sidebar: Thông tin & Tiến độ
st.sidebar.caption(f"📁 Tệp đang mở: `{Path(target_file).name}`")
st.sidebar.markdown(f"**Tiến độ của {annotator_name}:**")
st.sidebar.progress(labeled_count / total)
st.sidebar.write(f"Đã chấm: **{labeled_count} / {total}** mẫu ({(labeled_count/total)*100:.1f}%)")

# Nút nhảy đến câu chưa làm tiếp theo
if st.sidebar.button("⏭️ Nhảy đến câu chưa làm tiếp theo", use_container_width=True):
    unlabeled = df[df[score_col].isna() | (df[score_col] == "")].index
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

# Hàm xuất dataframe đúng cấu trúc 10 cột nguyên bản
def get_clean_export_df():
    export_df = df.copy()
    # Đảm bảo đủ các cột gốc
    for col in ORIGINAL_COLUMNS:
        if col not in export_df.columns:
            export_df[col] = ""
    return export_df[ORIGINAL_COLUMNS]

# Nút tải file CSV kết quả về máy
st.sidebar.markdown("---")
st.sidebar.markdown("### 💾 Xuất dữ liệu")
clean_csv_bytes = get_clean_export_df().to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
download_filename = f"{Path(target_file).stem}_labeled.csv"
st.sidebar.download_button(
    label=f"📥 Tải file kết quả (`{download_filename}`)",
    data=clean_csv_bytes,
    file_name=download_filename,
    mime="text/csv",
    use_container_width=True
)

# Hướng dẫn chấm điểm trên Sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### 📖 Hướng dẫn Chấm điểm (SANER 2027):")
st.sidebar.markdown("""
- **Mức 0 (Không liên quan / Rác)**: Khác công nghệ, import, class/interface rỗng, UI toast tĩnh, thiếu ngữ cảnh.
- **Mức 1 (Gián tiếp / Ngoại vi)**: Cấu hình cơ bản (Swagger), CRUD chuyển tiếp không có logic, hoặc đoạn code bị cắt dở mất logic cốt lõi.
- **Mức 2 (Trực tiếp / Mạnh mẽ)**: Bằng chứng cốt lõi (Spring Security JWT, custom React hook, REST API có auth & validation).  
  *Lưu ý:* Đoạn code bị cắt dở ở cuối nhưng phần nhìn thấy đã đủ bằng chứng thì **vẫn đạt Mức 2**.
""")

# 4. Hiển thị thông tin mẫu hiện tại
current_row = df.iloc[idx]
pair_id = str(current_row.get('pair_id', f'P{idx+1:04d}'))
query_id = str(current_row.get('query_id', 'N/A'))
jd_raw_text = str(current_row.get('jd_requirement_text', ''))
repo_name = str(current_row.get('repo_name', ''))
file_path = str(current_row.get('file_path', ''))
start_line = current_row.get('start_line', '')
end_line = current_row.get('end_line', '')
raw_code = str(current_row.get('raw_code_without_header', '// Không tìm thấy nội dung mã nguồn'))

# Phân tích jd_requirement_text để hiển thị trực quan
# Format chuẩn: Job Title: <title>. Domain: <domain>. Mandatory Technical Skills: <skills>
parsed_title = query_id
parsed_domain = ""
parsed_skills = ""

match = re.match(r'Job Title:\s*(.*?)\.\s*Domain:\s*(.*?)\.\s*Mandatory Technical Skills:\s*(.*?)(?:\.|$)', jd_raw_text)
if match:
    parsed_title = match.group(1).strip()
    parsed_domain = match.group(2).strip()
    parsed_skills = match.group(3).strip()
else:
    parsed_skills = jd_raw_text

st.title(f"🏷️ Gán nhãn Mẫu {idx + 1} / {total} (Mã: `{pair_id}`)")

extra_info = []
if parsed_domain: extra_info.append(f"Lĩnh vực: **{parsed_domain}**")
if repo_name: extra_info.append(f"Repo: `📂 {repo_name}`")
extra_str = (" | " + " | ".join(extra_info)) if extra_info else ""

st.info(f"🎯 **Kỹ năng yêu cầu trong JD:** :red[**{parsed_skills}**] (Vị trí: *{parsed_title}*{extra_str})")

ui_col_code, ui_col_action = st.columns([3, 1])

with ui_col_code:
    st.caption(f"📁 **File:** `{file_path}` | 📌 **Vị trí dòng:** `Lines {start_line}..{end_line}`")
    lang = "java" if str(file_path).endswith(".java") else "typescript"
    st.code(raw_code, language=lang, line_numbers=True)

    # Gợi ý từ Gemini AI (nếu có trong gemini_map)
    ai_item = gemini_map.get(pair_id)
    if ai_item:
        ai_lbl = int(ai_item['label'])
        ai_rs = ai_item['reason']
        lbl_badge = ":red[**Mức 0 (Không liên quan / Rác)**]" if ai_lbl == 0 else (":orange[**Mức 1 (Gián tiếp / Ngoại vi)**]" if ai_lbl == 1 else ":green[**Mức 2 (Minh chứng trực tiếp)**]")
        with st.expander("🤖 Gợi ý tham khảo từ Gemini AI (Nhấn mở khi phân vân)"):
            st.markdown(f"- **Đề xuất của AI:** {lbl_badge}")
            st.markdown(f"- **Lý do chuyên môn:** *{ai_rs}*")

with ui_col_action:
    st.write("### ✍️ Đánh giá của bạn:")

    current_val = df.loc[idx, score_col]
    if pd.notna(current_val) and str(current_val).strip() != "":
        try:
            val_int = int(float(current_val))
            badge = "0️⃣ Không liên quan" if val_int == 0 else ("1️⃣ Gián tiếp / Bối cảnh" if val_int == 1 else "2️⃣ Minh chứng trực tiếp")
            st.success(f"Đã chấm: **Mức {val_int}** ({badge})")
        except (ValueError, TypeError):
            st.success(f"Đã chấm: **Mức {current_val}**")
    else:
        st.info("Chưa gán nhãn cho mẫu này.")

    # Ô ghi chú
    current_note = str(df.loc[idx, 'notes']) if pd.notna(df.loc[idx, 'notes']) else ""
    note_input = st.text_input("Ghi chú (nếu phân vân):", value=current_note, key=f"note_{annotator_name}_{idx}")

    # Hàm lưu nhãn an toàn, không lỗi dtype
    def save_and_next(val):
        # Ép kiểu an toàn tuyệt đối
        df.loc[idx, score_col] = int(val)
        df.loc[idx, 'notes'] = str(note_input or "")

        # Xuất ra file đúng 10 cột nguyên bản
        clean_df = get_clean_export_df()
        clean_df.to_csv(target_file, index=False, encoding="utf-8-sig")

        # Đồng bộ sang các file liên quan nếu có
        for f in candidate_files:
            p_local = BASE_DIR / f
            if p_local.exists() and str(p_local.resolve()) != str(Path(target_file).resolve()):
                try:
                    clean_df.to_csv(str(p_local), index=False, encoding="utf-8-sig")
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

    # Nút 1-click theo AI nếu có
    if ai_item:
        st.write("")
        if st.button(f"🤖 Đồng ý theo AI (Chấm Mức {ai_lbl})", type="secondary", use_container_width=True):
            save_and_next(ai_lbl)

    st.write("---")
    ui_col_prev, ui_col_next = st.columns(2)
    with ui_col_prev:
        if st.button("⬅️ Câu trước", use_container_width=True) and st.session_state.current_idx > 0:
            df.loc[idx, 'notes'] = str(note_input or "")
            get_clean_export_df().to_csv(target_file, index=False, encoding="utf-8-sig")
            st.session_state.current_idx -= 1
            st.rerun()
    with ui_col_next:
        if st.button("Câu sau ➡️", use_container_width=True) and st.session_state.current_idx < total - 1:
            df.loc[idx, 'notes'] = str(note_input or "")
            get_clean_export_df().to_csv(target_file, index=False, encoding="utf-8-sig")
            st.session_state.current_idx += 1
            st.rerun()