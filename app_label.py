import streamlit as st
import pandas as pd
import json
import os
import re
from pathlib import Path

# Cấu hình giao diện Streamlit
st.set_page_config(
    page_title="Công cụ Gán nhãn - JD Evidence Matching (IEEE SANER 2027)",
    layout="wide",
    page_icon="🏷️"
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path("D:/jd-evidence-matching")
DATASET_DIR = PROJECT_DIR / "dataset"

# 1. Hỗ trợ query params để mở link riêng cho từng người
# Ví dụ: link?user=an hoặc link?user=huy
default_annotator_idx = 0
try:
    q_user = str(st.query_params.get("user", "") or st.query_params.get("annotator", "")).lower().strip()
    if q_user in ["an", "thuan", "thu_an", "2", "annotator2"]:
        default_annotator_idx = 1
    elif q_user in ["huy", "quanghuy", "quang_huy", "1", "annotator1"]:
        default_annotator_idx = 0
except Exception:
    pass

# 2. Chọn người gán nhãn
st.sidebar.title("👤 Người thực hiện")
annotator_options = ["Quang Huy (Annotator 1)", "Thu An (Annotator 2)"]

if "annotator_selection" not in st.session_state:
    st.session_state.annotator_selection = annotator_options[default_annotator_idx]

annotator_choice = st.sidebar.selectbox(
    "Bạn là ai?",
    annotator_options,
    key="annotator_selection"
)

is_annotator_1 = ("Quang Huy" in annotator_choice or "Annotator 1" in annotator_choice)
annotator_name = "Quang Huy" if is_annotator_1 else "Thu An"
user_key = "huy" if is_annotator_1 else "an"
score_col = "annotator1_score" if is_annotator_1 else "annotator2_score"

# File tương ứng với từng người
primary_file = "annotator1_blank.csv" if is_annotator_1 else "annotator2_blank.csv"
backup_file = "ground_truth_huy_raw.csv" if is_annotator_1 else "ground_truth_an_raw.csv"

# Tìm đường dẫn file mục tiêu
file_to_load = BASE_DIR / primary_file

# Danh sách 10 cột nguyên bản đúng format ban đầu của người dùng
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

# Hàm nạp dữ liệu an toàn, chống triệt để lỗi EmptyDataError
def load_annotator_data(target_path, backup_path, score_col_name):
    paths_to_try = [
        target_path,
        backup_path,
        DATASET_DIR / target_path.name if DATASET_DIR.exists() else None,
        DATASET_DIR / backup_path.name if DATASET_DIR.exists() else None,
        BASE_DIR / ("annotator1_blank.csv" if "annotator2" in str(target_path) else "annotator2_blank.csv")
    ]
    
    df_loaded = None
    for p in paths_to_try:
        if p and os.path.exists(p):
            try:
                # Kiểm tra file không bị 0 byte
                if os.path.getsize(p) > 200:
                    temp_df = pd.read_csv(p, encoding="utf-8-sig")
                    if len(temp_df) > 0 and 'pair_id' in temp_df.columns:
                        df_loaded = temp_df
                        break
            except Exception:
                continue

    if df_loaded is None:
        return None

    # Chuẩn hóa cột score và notes
    if score_col_name not in df_loaded.columns:
        alt_score = 'annotator2_score' if score_col_name == 'annotator1_score' else 'annotator1_score'
        if alt_score in df_loaded.columns:
            df_loaded[score_col_name] = df_loaded[alt_score]
        elif 'human_label' in df_loaded.columns:
            df_loaded[score_col_name] = df_loaded['human_label']
        else:
            df_loaded[score_col_name] = None

    if 'notes' not in df_loaded.columns:
        if 'human_note' in df_loaded.columns:
            df_loaded['notes'] = df_loaded['human_note']
        else:
            df_loaded['notes'] = ""

    # Ép kiểu an toàn tránh LossySetitemError
    df_loaded['notes'] = df_loaded['notes'].fillna("").astype(str)
    df_loaded[score_col_name] = df_loaded[score_col_name].astype(object)
    return df_loaded

# Hàm lưu dữ liệu an toàn Atomic Write (chống race condition và file 0 byte)
def safe_save_csv(df_to_save, target_path):
    try:
        tmp_path = str(target_path) + ".tmp"
        df_to_save.to_csv(tmp_path, index=False, encoding="utf-8-sig")
        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 200:
            os.replace(tmp_path, str(target_path))
    except Exception:
        try:
            df_to_save.to_csv(str(target_path), index=False, encoding="utf-8-sig")
        except Exception:
            pass

# 3. Quản lý dữ liệu qua Session Cache (Tăng tốc & Ngăn ngừa đọc file liên tục)
df_key = f"df_cache_{user_key}"
if df_key not in st.session_state:
    loaded_df = load_annotator_data(file_to_load, BASE_DIR / backup_file, score_col)
    if loaded_df is None or len(loaded_df) == 0:
        st.error(f"⚠️ Không thể nạp dữ liệu cho {annotator_name}! Vui lòng kiểm tra lại file CSV trên máy.")
        st.stop()
    st.session_state[df_key] = loaded_df

df = st.session_state[df_key]

# Tải từ điển gợi ý từ Gemini AI (nếu có)
gemini_sug_file = BASE_DIR / "gemini_suggestions.json"
gemini_map = {}
if gemini_sug_file.exists():
    try:
        with open(gemini_sug_file, "r", encoding="utf-8") as f:
            gemini_map = json.load(f)
    except Exception:
        pass

# 4. Quản lý Index & Trạng thái độc lập cho từng annotator
total = len(df)
if total == 0:
    st.warning("⚠️ Tập dữ liệu rỗng!")
    st.stop()

idx_key = f"current_idx_{user_key}"

# Khởi tạo vị trí câu cho người này (tự động tới câu chưa làm đầu tiên)
if idx_key not in st.session_state:
    unlabeled = df[df[score_col].isna() | (df[score_col].astype(str).str.strip() == "")].index
    st.session_state[idx_key] = int(unlabeled[0]) if len(unlabeled) > 0 else 0

st.session_state[idx_key] = max(0, min(st.session_state[idx_key], total - 1))
idx = st.session_state[idx_key]

# Đếm tiến độ của người này
labeled_mask = df[score_col].notna() & (df[score_col].astype(str).str.strip() != "")
labeled_count = int(labeled_mask.sum())

# Sidebar: Thông tin file & tiến độ
st.sidebar.caption(f"📁 Tệp gán nhãn: `{primary_file}`")
st.sidebar.caption(f"📝 Cột ghi điểm: `{score_col}`")
st.sidebar.markdown(f"**Tiến độ của {annotator_name}:**")
st.sidebar.progress(labeled_count / total)
st.sidebar.write(f"Đã chấm: **{labeled_count} / {total}** mẫu ({(labeled_count/total)*100:.1f}%)")

# Nút chuyển nhanh đến câu chưa làm tiếp theo của người này
if st.sidebar.button("⏭️ Nhảy đến câu chưa làm tiếp theo", use_container_width=True):
    unlabeled = df[df[score_col].isna() | (df[score_col].astype(str).str.strip() == "")].index
    future_unlabeled = [i for i in unlabeled if i > idx]
    if future_unlabeled:
        st.session_state[idx_key] = int(future_unlabeled[0])
    elif len(unlabeled) > 0:
        st.session_state[idx_key] = int(unlabeled[0])
    else:
        st.sidebar.success(f"🎉 {annotator_name} đã hoàn thành tất cả các mẫu!")
    st.rerun()

# Ô nhảy nhanh tới số câu cụ thể (Sử dụng dynamic key sạch để tránh lỗi StreamlitWidgetAlreadyInstantiatedError)
jump_target = st.sidebar.number_input(
    "Nhảy tới mẫu số:",
    min_value=1,
    max_value=total,
    value=idx + 1,
    step=1,
    key=f"jump_val_{user_key}_{idx}"
)
if jump_target - 1 != idx:
    st.session_state[idx_key] = jump_target - 1
    st.rerun()

# Hàm xuất đúng 10 cột nguyên bản
def get_clean_export_df():
    export_df = df.copy()
    for col in ORIGINAL_COLUMNS:
        if col not in export_df.columns:
            export_df[col] = ""
    return export_df[ORIGINAL_COLUMNS]

# Nút tải file CSV kết quả về máy
st.sidebar.markdown("---")
st.sidebar.markdown("### 💾 Xuất dữ liệu")
clean_csv_bytes = get_clean_export_df().to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
download_filename = f"{Path(file_to_load).stem}_labeled.csv"
st.sidebar.download_button(
    label=f"📥 Tải file kết quả (`{download_filename}`)",
    data=clean_csv_bytes,
    file_name=download_filename,
    mime="text/csv",
    use_container_width=True
)

# Nút nạp lại dữ liệu nếu cần
if st.sidebar.button("🔄 Nạp lại dữ liệu từ tệp gốc", use_container_width=True):
    st.session_state.pop(df_key, None)
    st.rerun()

# Link trực tiếp cho từng người
st.sidebar.markdown("---")
st.sidebar.caption("🔗 **Link truy cập nhanh:**")
st.sidebar.caption("• [Dành cho Quang Huy](/?user=huy)")
st.sidebar.caption("• [Dành cho Thu An](/?user=an)")

# Tóm tắt Guideline IEEE SANER 2027
st.sidebar.markdown("---")
st.sidebar.markdown("### 📖 Hướng dẫn Chấm điểm (SANER 2027):")
st.sidebar.markdown("""
- **Mức 0 (Không liên quan / Rác)**: Khác công nghệ, import, class/interface rỗng, UI toast tĩnh, thiếu ngữ cảnh.
- **Mức 1 (Gián tiếp / Ngoại vi)**: Cấu hình cơ bản (Swagger), CRUD chuyển tiếp không có logic, hoặc đoạn code bị cắt dở mất logic cốt lõi.
- **Mức 2 (Trực tiếp / Mạnh mẽ)**: Bằng chứng cốt lõi (Spring Security JWT, custom React hook, REST API có auth & validation).  
  *Lưu ý:* Đoạn code bị cắt dở ở cuối nhưng phần nhìn thấy đã đủ bằng chứng thì **vẫn đạt Mức 2**.
""")

# 5. Hiển thị nội dung mẫu cần gán nhãn
current_row = df.iloc[idx]
pair_id = str(current_row.get('pair_id', f'P{idx+1:04d}'))
query_id = str(current_row.get('query_id', 'N/A'))
jd_raw_text = str(current_row.get('jd_requirement_text', ''))
repo_name = str(current_row.get('repo_name', ''))
file_path = str(current_row.get('file_path', ''))
start_line = current_row.get('start_line', '')
end_line = current_row.get('end_line', '')
raw_code = str(current_row.get('raw_code_without_header', '// Không tìm thấy nội dung mã nguồn'))

# Bóc tách thông tin JD trực quan từ jd_requirement_text
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

    # Gợi ý từ Gemini AI (nếu có)
    ai_item = gemini_map.get(pair_id)
    if ai_item:
        ai_lbl = int(ai_item['label'])
        ai_rs = ai_item['reason']
        lbl_badge = ":red[**Mức 0 (Không liên quan / Rác)**]" if ai_lbl == 0 else (":orange[**Mức 1 (Gián tiếp / Ngoại vi)**]" if ai_lbl == 1 else ":green[**Mức 2 (Minh chứng trực tiếp)**]")
        with st.expander("🤖 Gợi ý tham khảo từ Gemini AI (Nhấn mở khi phân vân)"):
            st.markdown(f"- **Đề xuất của AI:** {lbl_badge}")
            st.markdown(f"- **Lý do chuyên môn:** *{ai_rs}*")

with ui_col_action:
    st.write(f"### ✍️ Đánh giá của {annotator_name}:")

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
    note_input = st.text_input("Ghi chú (nếu phân vân):", value=current_note, key=f"note_{user_key}_{idx}")

    # Hàm lưu nhãn & chuyển câu tiếp theo
    def save_and_next(val):
        df.loc[idx, score_col] = int(val)
        df.loc[idx, 'notes'] = str(note_input or "")

        # Cập nhật cache RAM ngay lập tức
        st.session_state[df_key] = df

        # Lưu an toàn xuống disk
        clean_df = get_clean_export_df()
        safe_save_csv(clean_df, file_to_load)

        # Đồng bộ sang backup_file nếu có
        backup_path = BASE_DIR / backup_file
        if backup_path.exists():
            safe_save_csv(clean_df, backup_path)

        # Chuyển sang câu kế tiếp
        if st.session_state[idx_key] < total - 1:
            st.session_state[idx_key] += 1
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
        if st.button("⬅️ Câu trước", use_container_width=True) and st.session_state[idx_key] > 0:
            df.loc[idx, 'notes'] = str(note_input or "")
            st.session_state[df_key] = df
            safe_save_csv(get_clean_export_df(), file_to_load)
            st.session_state[idx_key] -= 1
            st.rerun()
    with ui_col_next:
        if st.button("Câu sau ➡️", use_container_width=True) and st.session_state[idx_key] < total - 1:
            df.loc[idx, 'notes'] = str(note_input or "")
            st.session_state[df_key] = df
            safe_save_csv(get_clean_export_df(), file_to_load)
            st.session_state[idx_key] += 1
            st.rerun()