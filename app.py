import streamlit as st
import pandas as pd
import math
import requests
from streamlit_gsheets import GSheetsConnection

# 頁面標題與配置
st.set_page_config(page_title="醫療網護理人員執登與調薪卡控系統", layout="wide")

st.title("🩺 醫療網護理人員投保級距與執登管控系統")

# -------------------------------------------------------------------
# 區域與院所兩階層字典對照表
# -------------------------------------------------------------------
CLINIC_REGIONS = {
    "屏東": ["屏東院", "潮州院", "東港院"],
    "高雄": ["東霖院", "瑞隆院", "五甲院", "亞灣院", "光華院", "鳳山院", "陽明院", "建功院", "博愛院", "明華院", "意凡院", "佑昌院", "藍田院", "橋頭院"],
    "台南": ["崇學院", "成功院", "民權院", "百合院", "開元院", "崇德院"],
    "彰化": ["彰化院"],
    "台北": ["信義院", "迪化院"],
    "台東": ["台東院"]
}

ALL_CLINICS = [clinic for clinics in CLINIC_REGIONS.values() for clinic in clinics]
CLINIC_TO_REGION = {clinic: region for region, clinics in CLINIC_REGIONS.items() for clinic in clinics}

REASON_OPTIONS = ["調薪", "新到職符合級距", "無調薪", "新到職不符合級距"]

def get_compliance_status(reason):
    if reason in ["調薪", "新到職符合級距"]:
        return "🟢 符合"
    return "🔴 不符合"

def normalize_clinic_name(location_str):
    if not isinstance(location_str, str):
        return "博愛院"
    loc = location_str.strip()
    for clinic in ALL_CLINICS:
        short_name = clinic.replace("院", "").replace("所", "")
        if short_name in loc:
            return clinic
    return "博愛院"

# -------------------------------------------------------------------
# 1. 預設資料庫
# -------------------------------------------------------------------
DEFAULT_NURSES = [
    {"區域": "屏東", "院所": "潮州院", "姓名": "黃玉芬", "執業類別": "護理人員", "身份": "舊有員工", "到職日": "2002/08/03", "符合原因": "調薪", "符合資格": "🟢 符合", "本月離職": False, "備註": ""},
    {"區域": "屏東", "院所": "潮州院", "姓名": "林庭如", "執業類別": "護理人員", "身份": "舊有員工", "到職日": "2021/01/04", "符合原因": "調薪", "符合資格": "🟢 符合", "本月離職": False, "備註": ""},
    {"區域": "屏東", "院所": "潮州院", "姓名": "李晨寧", "執業類別": "護理人員", "身份": "舊有員工", "到職日": "2022/11/02", "符合原因": "調薪", "符合資格": "🟢 符合", "本月離職": False, "備註": ""},
    {"區域": "屏東", "院所": "潮州院", "姓名": "趙育萱", "執業類別": "兼職護理人員", "身份": "舊有員工", "到職日": "2024/04/08", "符合原因": "無調薪", "符合資格": "🔴 不符合", "本月離職": False, "備註": ""},
    {"區域": "屏東", "院所": "潮州院", "姓名": "陳靖誼", "執業類別": "護理人員", "身份": "舊有員工", "到職日": "2024/07/15", "符合原因": "調薪", "符合資格": "🟢 符合", "本月離職": False, "備註": ""},
    {"區域": "屏東", "院所": "潮州院", "姓名": "蔡函紜", "執業類別": "護理人員", "身份": "舊有員工", "到職日": "2025/02/17", "符合原因": "調薪", "符合資格": "🟢 符合", "本月離職": False, "備註": ""},
    {"區域": "屏東", "院所": "潮州院", "姓名": "梁淑雅", "執業類別": "護理人員", "身份": "舊有員工", "到職日": "2025/06/02", "符合原因": "無調薪", "符合資格": "🔴 不符合", "本月離職": False, "備註": ""},
    {"區域": "屏東", "院所": "潮州院", "姓名": "莊羽樺", "執業類別": "護理人員", "身份": "舊有員工", "到職日": "2026/05/18", "符合原因": "新到職不符合級距", "符合資格": "🔴 不符合", "本月離職": False, "備註": ""},
    {"區域": "屏東", "院所": "潮州院", "姓名": "莊慈慈", "執業類別": "儲備護理人員", "身份": "舊有員工", "到職日": "2026/08/10", "符合原因": "新到職符合級距", "符合資格": "🟢 符合", "本月離職": False, "備註": ""},
    {"區域": "屏東", "院所": "潮州院", "姓名": "廖靜敏", "執業類別": "護士", "身份": "舊有員工", "到職日": "2008/01/01", "符合原因": "無調薪", "符合資格": "🔴 不符合", "本月離職": False, "備註": ""},
]

if 'db_staff' not in st.session_state:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_cloud = conn.read(worksheet="Staff", ttl=0)
        if not df_cloud.empty and len(df_cloud) > 0:
            st.session_state.db_staff = df_cloud
        else:
            st.session_state.db_staff = pd.DataFrame(DEFAULT_NURSES)
    except Exception:
        st.session_state.db_staff = pd.DataFrame(DEFAULT_NURSES)

staff_df = st.session_state.db_staff

if not staff_df.empty and "院所" in staff_df.columns:
    staff_df["院所"] = staff_df["院所"].apply(normalize_clinic_name)

required_cols = ["區域", "院所", "姓名", "執業類別", "身份", "到職日", "符合原因", "符合資格", "本月離職", "備註"]
for col in required_cols:
    if col not in staff_df.columns:
        if col == "符合原因":
            staff_df[col] = "無調薪"
        elif col == "符合資格":
            staff_df[col] = "🔴 不符合"
        elif col == "身份":
            staff_df[col] = "舊有員工"
        elif col == "本月離職":
            staff_df[col] = False
        elif col in ["到職日", "備註"]:
            staff_df[col] = ""
        else:
            staff_df[col] = ""

staff_df["本月離職"] = staff_df["本月離職"].fillna(False).astype(bool)
staff_df["到職日"] = staff_df["到職日"].fillna("").astype(str)
staff_df["備註"] = staff_df["備註"].fillna("").astype(str)
staff_df["符合資格"] = staff_df["符合原因"].map(get_compliance_status)

if not staff_df.empty and "院所" in staff_df.columns:
    staff_df["區域"] = staff_df["院所"].map(lambda x: CLINIC_TO_REGION.get(x, "屏東"))

# -------------------------------------------------------------------
# 2. 帳號密碼與權限地圖 (定義一人管單院/多院)
# -------------------------------------------------------------------
USER_CREDENTIALS = {
    "admin": {"password": "admin123", "role": "HR總管理者", "clinics": ALL_CLINICS, "name": "HR人資部"},
    
    # 27 家院會計專屬帳號與可看院所
    "KYW-MK": {"password": "KSY00298", "role": "會計", "clinics": ["亞灣院"], "name": "吳淑婷"},
    "NCM-MK": {"password": "NCK00035", "role": "會計", "clinics": ["民權院"], "name": "李依婷"},
    "NCS-MK": {"password": "NCK00035", "role": "會計", "clinics": ["崇學院"], "name": "李依婷"},
    "KFS-MK": {"password": "KRL00162", "role": "會計", "clinics": ["鳳山院"], "name": "李宛純"},
    "KKH-MK": {"password": "KRL00162", "role": "會計", "clinics": ["光華院"], "name": "李宛純"},
    "TDH-MK": {"password": "KQT01345", "role": "會計", "clinics": ["迪化院"], "name": "周詩涵"},
    "TXY-MK": {"password": "KQT01345", "role": "會計", "clinics": ["信義院"], "name": "周詩涵"},
    "NCD-MK": {"password": "NCM01400", "role": "會計", "clinics": ["崇德院"], "name": "林君豫"},
    "NKY-MK": {"password": "NCM01400", "role": "會計", "clinics": ["開元院"], "name": "林君豫"},
    "PPT-MK": {"password": "PPT00004", "role": "會計", "clinics": ["屏東院"], "name": "邱麗梅"},
    "KRL-MK": {"password": "KRL00371", "role": "會計", "clinics": ["瑞隆院"], "name": "范育甄"},
    "KBI-MK": {"password": "KRL00371", "role": "會計", "clinics": ["博愛院"], "name": "范育甄"},
    "KYC-MK": {"password": "KYF02146", "role": "會計", "clinics": ["佑昌院"], "name": "張于婕"},
    "KQT-MK": {"password": "KYF02146", "role": "會計", "clinics": ["橋頭院"], "name": "張于婕"},
    "NCK-MK": {"password": "NBH00223", "role": "會計", "clinics": ["成功院"], "name": "張惠萍"},
    "NBH-MK": {"password": "NBH00223", "role": "會計", "clinics": ["百合院"], "name": "張惠萍"},
    "ZZH-MK": {"password": "ZZH01735", "role": "會計", "clinics": ["彰化院"], "name": "莊雅惠"},
    "KLT-MK": {"password": "KYF00075", "role": "會計", "clinics": ["藍田院"], "name": "郭玉輝"},
    "KYF-MK": {"password": "KYF00075", "role": "會計", "clinics": ["意凡院"], "name": "郭玉輝"},
    "KDL-MK": {"password": "KDL00024", "role": "會計", "clinics": ["東霖院"], "name": "曾美雲"},
    "KWJ-MK": {"password": "KSY00327", "role": "會計", "clinics": ["五甲院"], "name": "黃湘蓉"},
    "KYM-MK": {"password": "KSY00327", "role": "會計", "clinics": ["陽明院"], "name": "黃湘蓉"},
    "DTT-MK": {"password": "DTT02078", "role": "會計", "clinics": ["台東院"], "name": "塗婉瑜"},
    "PDG-MK": {"password": "PHK00041", "role": "會計", "clinics": ["東港院"], "name": "廖靜敏"},
    "PHK-MK": {"password": "PHK00041", "role": "會計", "clinics": ["潮州院"], "name": "廖靜敏"},
    "KMH-MK": {"password": "KJG0018",  "role": "會計", "clinics": ["明華院"], "name": "賴秀如"},
    "KJG-MK": {"password": "KJG0018",  "role": "會計", "clinics": ["建功院"], "name": "賴秀如"},
    
    "accountant": {"password": "act123", "role": "會計", "clinics": ["潮州院"], "name": "測試會計"}
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

if not st.session_state.logged_in:
    st.sidebar.subheader("🔒 系統登入")
    
    with st.sidebar.form("login_form"):
        username_input = st.text_input("帳號 (username)").strip()
        password_input = st.text_input("密碼 (password)", type="password").strip()
        submit_button = st.form_submit_button("登入系統")
        
        if submit_button:
            if username_input in USER_CREDENTIALS and USER_CREDENTIALS[username_input]["password"] == password_input:
                st.session_state.logged_in = True
                st.session_state.user_info = USER_CREDENTIALS[username_input]
                st.rerun()
            else:
                st.error("❌ 帳號或密碼錯誤！")
    
    st.info("👈 請於左側邊欄輸入管理帳號密碼登入系統。")
    st.stop()

user = st.session_state.user_info
allowed_clinics = user.get("clinics", [])

st.sidebar.success(f"👤 歡迎登入：{user['name']}\n權限：{', '.join(allowed_clinics)}")
if st.sidebar.button("🚪 登出系統"):
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.rerun()

# -------------------------------------------------------------------
# 3. 資料儲存與 LINE 發送函數
# -------------------------------------------------------------------
def save_data(new_df):
    new_df["符合資格"] = new_df["符合原因"].map(get_compliance_status)
    st.session_state.db_staff = new_df.copy()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(worksheet="Staff", data=new_df)
    except Exception:
        pass

def send_line_message(channel_access_token, user_id, message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {channel_access_token}"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    try:
        response = requests.post(url, headers=headers, json=payload)
        return response.status_code == 200
    except Exception as e:
        st.error(f"連線失敗：{e}")
        return False

# ===================================================================
# --- 模式 A：院所會計端 (僅顯示權限內允許的院) ---
# ===================================================================
if user["role"] == "會計":
    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 服務院所 (已鎖定權限)")
    
    # 根據該會計允許看到的院，反推允許的區域
    allowed_regions = list(set([CLINIC_TO_REGION.get(c, "屏東") for c in allowed_clinics]))
    
    selected_region = st.sidebar.selectbox("1. 大項「區域」：", allowed_regions)
    
    # 該區域內，且屬於該會計權限允許的院
    region_clinics = CLINIC_REGIONS[selected_region]
    user_available_clinics = [c for c in region_clinics if c in allowed_clinics]
    
    selected_clinic = st.sidebar.selectbox("2. 小項「院」：", user_available_clinics)

    st.subheader(f"📍【{selected_region}區】{selected_clinic} - 下個月執登與調薪卡控預測")

    clinic_df_next_month = staff_df[(staff_df['院所'] == selected_clinic) & (staff_df['本月離職'] == False)]
    
    total_nurses_next_month = len(clinic_df_next_month)
    compliant_nurses_next_month = len(clinic_df_next_month[clinic_df_next_month['符合資格'] == '🟢 符合'])
    target_needed = math.ceil(total_nurses_next_month / 2) if total_nurses_next_month > 0 else 0
    is_passed = compliant_nurses_next_month >= target_needed and total_nurses_next_month > 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📅 下月預估執登數 (已扣離職)", f"{total_nurses_next_month} 人")
    col2.metric("符合資格人數", f"{compliant_nurses_next_month} 人")
    col3.metric("需達標人數 (1/2)", f"{target_needed} 人")
    
    if is_passed:
        col4.success("🟢 下個月預估審核：符合規定")
    else:
        col4.error("🔴 下個月預估審核：未達標！")

    st.markdown("---")
    st.write("✏️ **選擇「符合原因」自動連動資格，可直接填寫「備註」資訊：**")

    editable_df = staff_df[staff_df['院所'] == selected_clinic].copy()
    
    edited_df = st.data_editor(
        editable_df,
        column_config={
            "區域": st.column_config.TextColumn("區域", disabled=True),
            "院所": st.column_config.TextColumn("院所", disabled=True),
            "姓名": st.column_config.TextColumn("姓名", disabled=True),
            "執業類別": st.column_config.TextColumn("類別", disabled=True),
            "身份": st.column_config.SelectboxColumn("身份別", options=["舊有員工", "新進人員"], required=True),
            "到職日": st.column_config.TextColumn("到職日"),
            "符合原因": st.column_config.SelectboxColumn("符合原因", options=REASON_OPTIONS, required=True),
            "符合資格": st.column_config.TextColumn("符合資格 (自動判定)", disabled=True),
            "本月離職": st.column_config.CheckboxColumn("本月離職 (勾選則下月扣除)", default=False),
            "備註": st.column_config.TextColumn("備註"),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key=f"data_editor_{selected_clinic}"
    )

    if st.button("💾 儲存並更新變更"):
        other_clinics_df = staff_df[staff_df['院所'] != selected_clinic]
        edited_df["符合資格"] = edited_df["符合原因"].map(get_compliance_status)
        edited_df["區域"] = selected_region
        edited_df["院所"] = selected_clinic
        new_staff_df = pd.concat([other_clinics_df, edited_df], ignore_index=True)
        save_data(new_staff_df)
        st.success("✅ 修改內容已成功儲存！")
        st.rerun()

    st.markdown("---")
    with st.expander("🗑️ 批量移除/刪除已離職人員名單"):
        current_names = editable_df["姓名"].tolist() if not editable_df.empty else []
        if current_names:
            remove_names = st.multiselect("選擇要從系統永久移除的人員：", current_names)
            if st.button("❌ 確認移除選取的人員"):
                if remove_names:
                    new_staff_df = staff_df[~((staff_df['院所'] == selected_clinic) & (staff_df['姓名'].isin(remove_names)))]
                    save_data(new_staff_df)
                    st.success(f"已成功移除 {', '.join(remove_names)}")
                    st.rerun()

    with st.expander("➕ 手動新增名冊外人員"):
        with st.form("add_single_nurse"):
            new_name = st.text_input("姓名")
            new_title = st.selectbox("執業類別", ["護理師", "護士", "護理人員", "兼職護理人員", "儲備護理人員"])
            new_type = st.selectbox("身份別", ["舊有員工", "新進人員"])
            new_date = st.text_input("到職日 (例: 2025/05/01)")
            new_reason = st.selectbox("符合原因", REASON_OPTIONS)
            new_memo = st.text_input("備註")
            if st.form_submit_button("新增該人員"):
                if new_name:
                    add_row = {
                        "區域": selected_region, "院所": selected_clinic, "姓名": new_name, "執業類別": new_title,
                        "身份": new_type, "到職日": new_date, "符合原因": new_reason, "符合資格": get_compliance_status(new_reason), "本月離職": False, "備註": new_memo
                    }
                    updated_all = pd.concat([staff_df, pd.DataFrame([add_row])], ignore_index=True)
                    save_data(updated_all)
                    st.success(f"已成功新增 {new_name}")
                    st.rerun()

# ===================================================================
# --- 模式 B：HR 總管理者端 (全權限觀看與匯入) ---
# ===================================================================
else:
    st.subheader("📊 全院護理人員下月執登卡控 - HR總表")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 系統資料備份與匯出")
    csv_data = staff_df.to_csv(index=False).encode('utf-8-sig')
    st.sidebar.download_button(
        label="💾 匯出最新完整資料庫 (.csv)",
        data=csv_data,
        file_name="nurse_control_master.csv",
        mime="text/csv"
    )

    with st.expander("📄 上傳全醫療網「護理人員母數清冊 (.xlsx / .xls / .csv)」全自動分類與預審", expanded=True):
        st.write("上傳包含欄位：`員工編號`、`中文姓名`、`職稱`、`上班地點`、`到職日` 的總表：")
        
        prsn_file = st.file_uploader("選擇全網護理人員 Excel 檔案 (.xlsx / .xls / .csv)", type=["xlsx", "xls", "csv"])
        
        if prsn_file is not None:
            try:
                if prsn_file.name.endswith('.csv'):
                    imported_df = pd.read_csv(prsn_file)
                else:
                    imported_df = pd.read_excel(prsn_file)
                
                if '中文姓名' in imported_df.columns and '上班地點' in imported_df.columns:
                    st.success("✅ 解析完成！您可直接在下方表格修正【歸類院】或單筆刪除錯誤資料：")
                    
                    imported_df['歸類院'] = imported_df['上班地點'].apply(normalize_clinic_name)
                    imported_df['歸類區域'] = imported_df['歸類院'].map(lambda x: CLINIC_TO_REGION.get(x, "高雄"))
                    
                    if '職稱' not in imported_df.columns:
                        imported_df['職稱'] = '護理人員'
                    if '到職日' not in imported_df.columns:
                        imported_df['到職日'] = ''
                    else:
                        imported_df['到職日'] = imported_df['到職日'].fillna("").astype(str).apply(lambda x: x.split(" ")[0] if " " in x else x)
                    if '備註' not in imported_df.columns:
                        imported_df['備註'] = ''

                    preview_df = imported_df[['中文姓名', '職稱', '到職日', '上班地點', '歸類院', '歸類區域', '備註']].copy()
                    
                    edited_preview_df = st.data_editor(
                        preview_df,
                        column_config={
                            "中文姓名": st.column_config.TextColumn("姓名"),
                            "職稱": st.column_config.TextColumn("職稱"),
                            "到職日": st.column_config.TextColumn("到職日"),
                            "上班地點": st.column_config.TextColumn("原始上班地點", disabled=True),
                            "歸類院": st.column_config.SelectboxColumn("歸類院 (可手動修正)", options=ALL_CLINICS, required=True),
                            "歸類區域": st.column_config.TextColumn("歸類區域 (自動對應)", disabled=True),
                            "備註": st.column_config.TextColumn("備註"),
                        },
                        use_container_width=True,
                        num_rows="dynamic",
                        key="import_preview_editor"
                    )
                    
                    edited_preview_df['歸類區域'] = edited_preview_df['歸類院'].map(lambda x: CLINIC_TO_REGION.get(x, "高雄"))
                    
                    import_mode = st.radio("選擇匯入方式：", ["增量比對更新（保留既有勾選資料，僅新增新到職人員）", "完全覆蓋資料庫（以新檔案為準重新建立全網母數）"])
                    
                    if st.button("🚀 確認匯入此預審名單"):
                        new_records = []
                        for _, row in edited_preview_df.iterrows():
                            c_name = row['中文姓名']
                            clinic_name = row['歸類院']
                            region_name = CLINIC_TO_REGION.get(clinic_name, "高雄")
                            title = row.get('職稱', '護理人員')
                            arr_date = str(row.get('到職日', ''))
                            memo_val = str(row.get('備註', ''))
                            
                            new_records.append({
                                "區域": region_name,
                                "院所": clinic_name,
                                "姓名": c_name,
                                "執業類別": title,
                                "身份": "舊有員工",
                                "到職日": arr_date,
                                "符合原因": "無調薪",
                                "符合資格": "🔴 不符合",
                                "本月離職": False,
                                "備註": memo_val
                            })
                        
                        parsed_new_df = pd.DataFrame(new_records)
                        
                        if import_mode.startswith("完全覆蓋"):
                            save_data(parsed_new_df)
                            st.balloons()
                            st.success(f"🎉 成功覆蓋資料庫！已將 **{len(parsed_new_df)}** 位護理人員匯入！")
                        else:
                            existing_pairs = set(zip(staff_df['院所'], staff_df['姓名'])) if not staff_df.empty else set()
                            added_rows = []
                            for _, r in parsed_new_df.iterrows():
                                if (r['院所'], r['姓名']) not in existing_pairs:
                                    added_rows.append(r)
                            
                            if added_rows:
                                merged_df = pd.concat([staff_df, pd.DataFrame(added_rows)], ignore_index=True)
                                save_data(merged_df)
                                st.balloons()
                                st.success(f"🎉 增量更新成功！自動新增了 **{len(added_rows)}** 位護理人員！")
                            else:
                                st.warning("⚠️ 檔案中的護理人員皆已存在於資料庫中。")
                        st.rerun()
                else:
                    st.error("❌ 檔案欄位格式不符，請確認包含「中文姓名」與「上班地點」欄位。")
            except Exception as e:
                st.error(f"檔案讀取失敗：{e}")

    st.markdown("---")

    # 全院總表
    st.write("🔍 **總表區域篩選**")
    filter_region = st.selectbox("選擇要檢視的區域（或顯示全部）：", ["全部區域"] + list(CLINIC_REGIONS.keys()))

    summary_list = []
    display_clinics = ALL_CLINICS if filter_region == "全部區域" else CLINIC_REGIONS[filter_region]
    
    for c in display_clinics:
        c_region = CLINIC_TO_REGION.get(c, "")
        c_df_next_month = staff_df[(staff_df['院所'] == c) & (staff_df['本月離職'] == False)] if '院所' in staff_df.columns else pd.DataFrame()
        tot = len(c_df_next_month)
        comp = len(c_df_next_month[c_df_next_month['符合資格'] == '🟢 符合']) if tot > 0 else 0
        req = math.ceil(tot / 2) if tot > 0 else 0
        status = "🟢 達標" if (comp >= req and tot > 0) else ("⚪ 尚未建立名冊" if tot == 0 else "🔴 未達標")
        
        summary_list.append({
            "區域": c_region,
            "院所名稱": c,
            "下月預估執登數 (已扣離職)": tot,
            "符合資格人數": comp,
            "標準門檻 (1/2)": req,
            "下月管控預測": status
        })
    
    summary_df = pd.DataFrame(summary_list)
    st.table(summary_df)

    # HR 明細調整
    st.markdown("---")
    st.subheader("📋 HR 深入檢視與調整各院人員明細")
    st.write("請使用下方連動選單選擇欲查看的院：")
    
    col_hr_detail_r, col_hr_detail_c = st.columns(2)
    hr_view_region = col_hr_detail_r.selectbox("1. 選擇大項【區域】：", list(CLINIC_REGIONS.keys()), key="hr_view_reg")
    hr_view_clinic = col_hr_detail_c.selectbox("2. 選擇小項【院】：", CLINIC_REGIONS[hr_view_region], key="hr_view_cli")

    st.markdown(f"#### 📍【{hr_view_region}區】{hr_view_clinic} - 下月預估現況")

    hr_clinic_df_next_month = staff_df[(staff_df['院所'] == hr_view_clinic) & (staff_df['本月離職'] == False)]
    hr_tot = len(hr_clinic_df_next_month)
    hr_comp = len(hr_clinic_df_next_month[hr_clinic_df_next_month['符合資格'] == '🟢 符合'])
    hr_req = math.ceil(hr_tot / 2) if hr_tot > 0 else 0
    hr_passed = hr_comp >= hr_req and hr_tot > 0

    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("下月預估執登數 (已扣離職)", f"{hr_tot} 人")
    col_k2.metric("符合資格人數", f"{hr_comp} 人")
    col_k3.metric("需達標人數 (1/2)", f"{hr_req} 人")
    
    if hr_passed:
        col_k4.success("🟢 預估審核結果：符合規定")
    else:
        col_k4.error("🔴 預估審核結果：未達標！")

    hr_editable_df = staff_df[staff_df['院所'] == hr_view_clinic].copy()
    
    if not hr_editable_df.empty:
        st.write("✏️ **人資同仁可直接在下方表格修改資料（修改後點擊儲存）：**")
        hr_edited_df = st.data_editor(
            hr_editable_df,
            column_config={
                "區域": st.column_config.TextColumn("區域", disabled=True),
                "院所": st.column_config.TextColumn("院所", disabled=True),
                "姓名": st.column_config.TextColumn("姓名"),
                "執業類別": st.column_config.TextColumn("類別"),
                "身份": st.column_config.SelectboxColumn("身份別", options=["舊有員工", "新進人員"], required=True),
                "到職日": st.column_config.TextColumn("到職日"),
                "符合原因": st.column_config.SelectboxColumn("符合原因", options=REASON_OPTIONS, required=True),
                "符合資格": st.column_config.TextColumn("符合資格 (自動判定)", disabled=True),
                "本月離職": st.column_config.CheckboxColumn("本月離職 (勾選則下月扣除)", default=False),
                "備註": st.column_config.TextColumn("備註"),
            },
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key=f"hr_data_editor_{hr_view_clinic}"
        )
        
        if st.button(f"💾 儲存 [{hr_view_clinic}] 的人員變更", key="hr_save_btn"):
            other_clinics_df = staff_df[staff_df['院所'] != hr_view_clinic]
            hr_edited_df["符合資格"] = hr_edited_df["符合原因"].map(get_compliance_status)
            hr_edited_df["區域"] = hr_view_region
            hr_edited_df["院所"] = hr_view_clinic
            new_staff_df = pd.concat([other_clinics_df, hr_edited_df], ignore_index=True)
            save_data(new_staff_df)
            st.success(f"✅ 已成功更新 [{hr_view_clinic}] 的人員資料並同步至全院總表！")
            st.rerun()

        with st.expander(f"🗑️ 批量移除/刪除 [{hr_view_clinic}] 已離職人員名單"):
            hr_current_names = hr_editable_df["姓名"].tolist() if not hr_editable_df.empty else []
            if hr_current_names:
                hr_remove_names = st.multiselect("選擇要從系統永久移除的人員：", hr_current_names, key="hr_multiselect_del")
                if st.button("❌ 確認移除選取的人員", key="hr_btn_del"):
                    if hr_remove_names:
                        new_staff_df = staff_df[~((staff_df['院所'] == hr_view_clinic) & (staff_df['姓名'].isin(hr_remove_names)))]
                        save_data(new_staff_df)
                        st.success(f"已成功移除 {', '.join(hr_remove_names)}")
                        st.rerun()

        with st.expander(f"➕ 手動新增名冊外人員至 [{hr_view_clinic}]"):
            with st.form("hr_add_single_nurse"):
                hr_new_name = st.text_input("姓名")
                hr_new_title = st.selectbox("執業類別", ["護理師", "護士", "護理人員", "兼職護理人員", "儲備護理人員"])
                hr_new_type = st.selectbox("身份別", ["舊有員工", "新進人員"])
                hr_new_date = st.text_input("到職日 (例: 2025/05/01)")
                hr_new_reason = st.selectbox("符合原因", REASON_OPTIONS)
                hr_new_memo = st.text_input("備註")
                if st.form_submit_button("新增該人員"):
                    if hr_new_name:
                        add_row = {
                            "區域": hr_view_region, "院所": hr_view_clinic, "姓名": hr_new_name, "執業類別": hr_new_title,
                            "身份": hr_new_type, "到職日": hr_new_date, "符合原因": hr_new_reason, "符合資格": get_compliance_status(hr_new_reason), "本月離職": False, "備註": hr_new_memo
                        }
                        updated_all = pd.concat([staff_df, pd.DataFrame([add_row])], ignore_index=True)
                        save_data(updated_all)
                        st.success(f"已成功新增 {hr_new_name}")
                        st.rerun()
    else:
        st.info(f"💡 目前【{hr_view_clinic}】尚未建立人員名冊，可利用頁面上方方塊上傳全醫療網護理人員 Excel 母數總表。")

    # 4. LINE 推播區
    st.markdown("---")
    st.subheader("🔔 LINE 官方帳號 - 私訊催辦推播")
    
    unpassed = summary_df[summary_df["下月管控預測"] == "🔴 未達標"]["院所名稱"].tolist() if not summary_df.empty else []
    
    if unpassed:
        st.warning(f"目前下個月預估未達 1/2 標準之院：**{', '.join(unpassed)}**")
        selected_notify_clinic = st.selectbox("選擇要提醒的院：", unpassed)
        
        line_token = st.text_input("LINE Channel Access Token (機器人金鑰)", type="password")
        accountant_line_id = st.text_input("該院會計個人 LINE User ID")
        
        msg_template = f"⚠️【HR催辦通知】\n{selected_notify_clinic} 負責會計您好：\n貴院下個月預估護理師投保級距合規人數未達執登總人數之 1/2，請儘速進系統調整資料！"
        st.text_area("推播訊息預覽", msg_template, height=120)
        
        if st.button("🚀 私訊發送 LINE 提醒"):
            if line_token and accountant_line_id:
                success = send_line_message(line_token, accountant_line_id, msg_template)
                if success:
                    st.success(f"✅ 已成功私訊發送給 [{selected_notify_clinic}] 負責會計！")
                else:
                    st.error("❌ 發送失敗，請確認 LINE Token 與 User ID。")
            else:
                st.error("請填寫 LINE Token 與會計 User ID。")
    else:
        st.balloons()
        st.success("🎉 所有院下個月預估皆已符合標準（或無未達標院）！無需發送提醒。")
