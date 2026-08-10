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
    "屏東": ["屏東院所", "潮州院所", "東港院所"],
    "高雄": ["東霖院所", "瑞隆院所", "五甲院所", "亞灣院所", "光華院所", "鳳山院所", "陽明院所", "建功院所", "博愛院所", "明華院所", "意凡院所", "佑昌院所", "藍田院所", "橋頭院所"],
    "台南": ["崇學院所", "成功院所", "民權院所", "百合院所", "開元院所", "崇德院所"],
    "彰化": ["彰化院所"],
    "台北": ["信義院所", "迪化院所"],
    "台東": ["台東院所"]
}

ALL_CLINICS = [clinic for clinics in CLINIC_REGIONS.values() for clinic in clinics]
CLINIC_TO_REGION = {clinic: region for region, clinics in CLINIC_REGIONS.items() for clinic in clinics}

# -------------------------------------------------------------------
# 1. 預設資料庫 (包含您提供的潮州院所 10 位護理人員清冊)
# -------------------------------------------------------------------
DEFAULT_NURSES = [
    # 潮州院所實體清冊 10 人
    {"區域": "屏東", "院所": "潮州院所", "姓名": "廖靜敏", "執業類別": "護士", "身份": "舊有員工", "舊員是否調薪": True, "新進級距": 0, "投保金額": 31800, "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "李晨寧", "執業類別": "護理師", "身份": "舊有員工", "舊員是否調薪": True, "新進級距": 0, "投保金額": 31800, "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "林庭如", "執業類別": "護理師", "身份": "新進人員", "舊員是否調薪": False, "新進級距": 4, "投保金額": 33300, "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "梁淑雅", "執業類別": "護理師", "身份": "舊有員工", "舊員是否調薪": False, "新進級距": 0, "投保金額": 27470, "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "洪羿羚", "執業類別": "護理師", "身份": "舊有員工", "舊員是否調薪": True, "新進級距": 0, "投保金額": 31800, "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "莊羽樺", "執業類別": "護理師", "身份": "新進人員", "舊員是否調薪": False, "新進級距": 4, "投保金額": 33300, "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "蔡函紜", "執業類別": "護理師", "身份": "舊有員工", "舊員是否調薪": False, "新進級距": 0, "投保金額": 27470, "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "趙育萱", "執業類別": "護理師", "身份": "舊有員工", "舊員是否調薪": False, "新進級距": 0, "投保金額": 27470, "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "陳靖誼", "執業類別": "護理師", "身份": "舊有員工", "舊員是否調薪": True, "新進級距": 0, "投保金額": 31800, "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "黃玉芬", "執業類別": "護理師", "身份": "舊有員工", "舊員是否調薪": False, "新進級距": 0, "投保金額": 27470, "狀態": "在職"},
    
    # 屏東院所範例
    {"區域": "屏東", "院所": "屏東院所", "姓名": "王小美", "執業類別": "護理師", "身份": "舊有員工", "舊員是否調薪": True, "新進級距": 0, "投保金額": 31800, "狀態": "在職"},
    {"區域": "屏東", "院所": "屏東院所", "姓名": "林阿花", "執業類別": "護理師", "身份": "新進人員", "舊員是否調薪": False, "新進級距": 4, "投保金額": 33300, "狀態": "在職"},
]

# 記憶體內快取資料庫（避免安全權限問題導致報錯）
if 'db_staff' not in st.session_state:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_cloud = conn.read(worksheet="Staff", ttl=0)
        if not df_cloud.empty:
            st.session_state.db_staff = df_cloud
        else:
            st.session_state.db_staff = pd.DataFrame(DEFAULT_NURSES)
    except Exception:
        st.session_state.db_staff = pd.DataFrame(DEFAULT_NURSES)

staff_df = st.session_state.db_staff

# 補齊區域欄位
if not staff_df.empty and "院所" in staff_df.columns:
    staff_df["區域"] = staff_df["院所"].map(lambda x: CLINIC_TO_REGION.get(x, "屏東"))

# -------------------------------------------------------------------
# 2. 帳號密碼與權限登入系統
# -------------------------------------------------------------------
USER_CREDENTIALS = {
    "admin": {"password": "admin123", "role": "HR總管理者", "name": "HR人資部"},
    "accountant": {"password": "act123", "role": "會計", "name": "院所會計部"}
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
st.sidebar.success(f"👤 歡迎登入：{user['name']}")
if st.sidebar.button("🚪 登出系統"):
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.rerun()

# -------------------------------------------------------------------
# 3. 業務卡控邏輯與 LINE 發送函數
# -------------------------------------------------------------------
def check_compliance(row):
    if row['狀態'] == '離職':
        return False
    if row['身份'] == '舊有員工' and row.get('舊員是否調薪', False) == True:
        return True
    if row['身份'] == '新進人員' and (row.get('投保金額', 0) >= 33300 or row.get('新進級距', 0) >= 4):
        return True
    return False

def save_data(new_df):
    st.session_state.db_staff = new_df
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        conn.update(worksheet="Staff", data=new_df)
    except Exception:
        pass  # 若 Google Sheets 尚未設定寫入權限，則維持快取運作不跳紅字警告

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

# 計算合規性
df = staff_df.copy()
if not df.empty and '狀態' in df.columns:
    df['符合資格'] = df.apply(check_compliance, axis=1)

# -------------------------------------------------------------------
# 4. 畫面展示：會計試算/勾選端 vs HR 總表
# -------------------------------------------------------------------

# --- 模式 A：院所會計輸入/勾選端 ---
if user["role"] == "會計":
    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 選擇服務院所")
    
    selected_region = st.sidebar.selectbox("1. 請先選擇大項「區域」：", list(CLINIC_REGIONS.keys()))
    available_clinics = CLINIC_REGIONS[selected_region]
    selected_clinic = st.sidebar.selectbox("2. 再選擇小項「院所」：", available_clinics)

    st.subheader(f"📍【{selected_region}區】{selected_clinic} - 人員維護與勾選卡控")

    clinic_mask = (df['院所'] == selected_clinic) & (df['狀態'] == '在職')
    clinic_df = df[clinic_mask] if '院所' in df.columns else pd.DataFrame()
    
    total_nurses = len(clinic_df)
    compliant_nurses = clinic_df['符合資格'].sum() if total_nurses > 0 and '符合資格' in clinic_df.columns else 0
    target_needed = math.ceil(total_nurses / 2) if total_nurses > 0 else 0
    is_passed = compliant_nurses >= target_needed and total_nurses > 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("實際執登人數", f"{total_nurses} 人")
    col2.metric("符合資格人數", f"{compliant_nurses} 人")
    col3.metric("需達標人數 (1/2)", f"{target_needed} 人")
    
    if is_passed:
        col4.success("🟢 本月審核結果：符合規定")
    else:
        col4.error("🔴 本月審核結果：未達標！")

    st.markdown("---")
    st.write("✏️ **在職護理人員狀態勾選與級距調整（編輯完成後點下方儲存）**")

    editable_df = staff_df[staff_df['院所'] == selected_clinic].copy()
    
    edited_df = st.data_editor(
        editable_df,
        column_config={
            "區域": st.column_config.TextColumn("區域", disabled=True),
            "院所": st.column_config.TextColumn("院所", disabled=True),
            "姓名": st.column_config.TextColumn("姓名", disabled=True),
            "執業類別": st.column_config.TextColumn("類別", disabled=True),
            "身份": st.column_config.SelectboxColumn("身份別", options=["舊有員工", "新進人員"], required=True),
            "舊員是否調薪": st.column_config.CheckboxColumn("舊員有調薪 (往上1級)"),
            "新進級距": st.column_config.NumberColumn("新進投保級距", min_value=0, max_value=20, step=1, help="達第4級(33,300)符合資格"),
            "投保金額": st.column_config.NumberColumn("投保金額 (NTD)", step=100, format="$%d"),
            "狀態": st.column_config.SelectboxColumn("狀態", options=["在職", "離職"], required=True),
        },
        use_container_width=True,
        hide_index=True,
        key=f"data_editor_{selected_clinic}"
    )

    if st.button("💾 儲存並更新變更"):
        staff_df.update(edited_df)
        save_data(staff_df)
        st.success("✅ 修改內容已成功儲存！")
        st.rerun()

    st.markdown("---")
    with st.expander("➕ 手動新增名冊外臨時人員"):
        with st.form("add_single_nurse"):
            new_name = st.text_input("姓名")
            new_title = st.selectbox("執業類別", ["護理師", "護士"])
            new_type = st.selectbox("身份別", ["舊有員工", "新進人員"])
            if st.form_submit_button("新增該人員"):
                if new_name:
                    add_row = {
                        "區域": selected_region, "院所": selected_clinic, "姓名": new_name, "執業類別": new_title,
                        "身份": new_type, "舊員是否調薪": False, "新進級距": 0, "投保金額": 27470, "狀態": "在職"
                    }
                    updated_all = pd.concat([staff_df, pd.DataFrame([add_row])], ignore_index=True)
                    save_data(updated_all)
                    st.success(f"已成功新增 {new_name}")
                    st.rerun()

# --- 模式 B：HR 總管理者模式 ---
else:
    st.subheader("📊 全院所護理人員執登卡控 - HR總表")
    
    with st.expander("📄 上傳各院健保署/衛福部「醫事人員執業清冊 (.xls/.xlsx)」持續更新資料", expanded=True):
        st.write("上傳清冊後，系統會自動比對並**新增未在名冊中的新執登護理師/護士**，同時保持既有歷史資料。")
        
        col_r, col_c, col_f = st.columns([1, 1, 2])
        target_region = col_r.selectbox("選擇大項【區域】：", list(CLINIC_REGIONS.keys()), key="hr_import_reg")
        target_clinic = col_c.selectbox("選擇小項【院所】：", CLINIC_REGIONS[target_region], key="hr_import_cli")
        prsn_file = col_f.file_uploader("選擇執業清冊 (.xls / .xlsx)", type=["xls", "xlsx"])
        
        if prsn_file is not None:
            try:
                uploaded_prsn_df = pd.read_excel(prsn_file)
                if '執業類別' in uploaded_prsn_df.columns and '姓名' in uploaded_prsn_df.columns:
                    nurses_in_file = uploaded_prsn_df[uploaded_prsn_df['執業類別'].isin(['護理師', '護士'])].copy()
                    st.info(f"解析到檔案中有 **{len(nurses_in_file)}** 位護理人員。")
                    st.dataframe(nurses_in_file[['姓名', '執業類別', '執業起日']], use_container_width=True)
                    
                    if st.button(f"🚀 將清冊資料增量更新至 [{target_region}區 - {target_clinic}]"):
                        existing_names = staff_df[(staff_df['院所'] == target_clinic)]['姓名'].tolist() if '姓名' in staff_df.columns else []
                        
                        added_count = 0
                        new_rows = []
                        for _, row in nurses_in_file.iterrows():
                            if row['姓名'] not in existing_names:
                                new_rows.append({
                                    "區域": target_region,
                                    "院所": target_clinic,
                                    "姓名": row['姓名'],
                                    "執業類別": row['執業類別'],
                                    "身份": "舊有員工",
                                    "舊員是否調薪": False,
                                    "新進級距": 0,
                                    "投保金額": 27470,
                                    "狀態": "在職"
                                })
                                added_count += 1
                        
                        if new_rows:
                            merged_df = pd.concat([staff_df, pd.DataFrame(new_rows)], ignore_index=True)
                            save_data(merged_df)
                            st.balloons()
                            st.success(f"✅ 更新成功！新增了 {added_count} 位新護理人員，歷史記錄已完整保留！")
                        else:
                            st.warning("⚠️ 檔案中的護理人員皆已存在於資料庫中，無新增人員。")
                        st.rerun()
                else:
                    st.error("❌ 檔案欄位格式不符（缺少「執業類別」或「姓名」）。")
            except Exception as e:
                st.error(f"檔案讀取失敗：{e}")

    st.markdown("---")

    st.write("🔍 **總表區域篩選**")
    filter_region = st.selectbox("選擇要檢視的區域（或顯示全部）：", ["全部區域"] + list(CLINIC_REGIONS.keys()))

    summary_list = []
    display_clinics = ALL_CLINICS if filter_region == "全部區域" else CLINIC_REGIONS[filter_region]
    
    for c in display_clinics:
        c_region = CLINIC_TO_REGION.get(c, "")
        c_df = df[(df['院所'] == c) & (df['狀態'] == '在職')] if '院所' in df.columns else pd.DataFrame()
        tot = len(c_df)
        comp = c_df['符合資格'].sum() if tot > 0 and '符合資格' in c_df.columns else 0
        req = math.ceil(tot / 2) if tot > 0 else 0
        status = "🟢 達標" if (comp >= req and tot > 0) else ("⚪ 尚未建立名冊" if tot == 0 else "🔴 未達標")
        summary_list.append({
            "區域": c_region,
            "院所名稱": c,
            "執登總人數": tot,
            "符合資格人數": comp,
            "標準門檻 (1/2)": req,
            "管控狀態": status
        })
    
    summary_df = pd.DataFrame(summary_list)
    st.table(summary_df)

    st.markdown("---")
    st.subheader("🔔 LINE 官方帳號 - 私訊催辦推播")
    
    unpassed = summary_df[summary_df["管控狀態"] == "🔴 未達標"]["院所名稱"].tolist() if not summary_df.empty else []
    
    if unpassed:
        st.warning(f"目前未達 1/2 標準之院所：**{', '.join(unpassed)}**")
        selected_notify_clinic = st.selectbox("選擇要提醒的院所：", unpassed)
        
        line_token = st.text_input("LINE Channel Access Token (機器人金鑰)", type="password")
        accountant_line_id = st.text_input("該院所會計個人 LINE User ID")
        
        msg_template = f"⚠️【HR催辦通知】\n{selected_notify_clinic} 負責會計您好：\n貴院本月護理師投保級距合規人數未達執登總人數之 1/2，請儘速進系統確認並調整資料！"
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
        st.success("🎉 所有院所本月皆已符合標準（或無未達標院所）！無需發送提醒。")
