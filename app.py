import streamlit as st
import pandas as pd
import math
import requests
from streamlit_gsheets import GSheetsConnection

# 頁面標題與配置
st.set_page_config(page_title="護理人員執登與調薪卡控系統", layout="wide")

st.title("🩺 院所護理人員投保級距與執登管控系統")

# -------------------------------------------------------------------
# 1. Google Sheets 資料庫連線初始化
# -------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet="Staff", ttl=0)
        return df
    except Exception:
        # 預設範例資料結構
        return pd.DataFrame([
            {"院所": "台北院所", "姓名": "王小美", "身份": "舊有員工", "原級距": 2, "現行級距": 3, "投保金額": 31800, "狀態": "在職"},
            {"院所": "台北院所", "姓名": "林阿花", "身份": "新進人員", "原級距": 0, "現行級距": 4, "投保金額": 33300, "狀態": "在職"},
            {"院所": "台中院所", "姓名": "張護士", "身份": "舊有員工", "原級距": 3, "現行級距": 3, "投保金額": 31800, "狀態": "在職"},
            {"院所": "台中院所", "姓名": "陳大明", "身份": "舊有員工", "原級距": 1, "現行級距": 1, "投保金額": 27470, "狀態": "在職"},
        ])

staff_df = load_data()

# -------------------------------------------------------------------
# 2. 帳號密碼與權限登入系統
# -------------------------------------------------------------------
USER_CREDENTIALS = {
    "taipei": {"password": "tp123", "role": "會計", "clinic": "台北院所", "name": "台北會計"},
    "taichung": {"password": "tc123", "role": "會計", "clinic": "台中院所", "name": "台中會計"},
    "admin": {"password": "admin123", "role": "HR總管理者", "clinic": "全部", "name": "HR人資部"}
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

if not st.session_state.logged_in:
    st.sidebar.subheader("🔒 系統登入")
    username_input = st.sidebar.text_input("帳號 (username)")
    password_input = st.sidebar.text_input("密碼 (password)", type="password")
    
    if st.sidebar.button("登入"):
        if username_input in USER_CREDENTIALS and USER_CREDENTIALS[username_input]["password"] == password_input:
            st.session_state.logged_in = True
            st.session_state.user_info = USER_CREDENTIALS[username_input]
            st.rerun()
        else:
            st.sidebar.error("❌ 帳號或密碼錯誤！")
    
    st.info("👈 請先於左側邊欄輸入帳號密碼登入系統。")
    st.stop()

user = st.session_state.user_info
st.sidebar.success(f"👤 歡迎登入：{user['name']}")
if st.sidebar.button("🚪 登出系統"):
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.rerun()

# -------------------------------------------------------------------
# 3. 業務邏輯與 LINE Messaging API 發送函數
# -------------------------------------------------------------------
def check_compliance(row):
    if row['狀態'] == '離職':
        return False
    if row['身份'] == '舊有員工' and row['現行級距'] > row['原級距']:
        return True
    if row['身份'] == '新進人員' and row['投保金額'] >= 33300:
        return True
    return False

def send_line_message(channel_access_token, user_id, message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_access_token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}]
    }
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
# 4. 畫面展示：會計輸入端 vs HR 總表
# -------------------------------------------------------------------

# --- 模式 A：院所會計輸入端 ---
if user["role"] == "會計":
    selected_clinic = user["clinic"]
    st.subheader(f"📍 {selected_clinic} - 人員資料維護與管控")

    clinic_df = df[(df['院所'] == selected_clinic) & (df['狀態'] == '在職')] if '院所' in df.columns else pd.DataFrame()
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

    # 手動單筆新增人員
    with st.expander("➕ 手動新增單筆護理人員"):
        with st.form("add_nurse_form"):
            name = st.text_input("護理師姓名")
            emp_type = st.selectbox("人員身份", ["舊有員工", "新進人員"])
            prev_level = st.number_input("原投保級距 (新進填 0)", min_value=0, max_value=20, value=1)
            curr_level = st.number_input("現行投保級距", min_value=1, max_value=20, value=1)
            salary = st.number_input("投保金額 (NTD)", min_value=0, value=33300, step=100)
            
            if st.form_submit_button("儲存並更新至雲端資料庫"):
                if name:
                    new_row = {
                        "院所": selected_clinic, "姓名": name, "身份": emp_type,
                        "原級距": prev_level, "現行級距": curr_level, 
                        "投保金額": salary, "狀態": "在職"
                    }
                    updated_df = pd.concat([staff_df, pd.DataFrame([new_row])], ignore_index=True)
                    conn.update(worksheet="Staff", data=updated_df)
                    st.success(f"已成功新增 {name} 並同步寫入雲端資料庫！")
                    st.rerun()

    # 顯示目前名單
    st.write("📋 **目前執登人員名單**")
    if not clinic_df.empty:
        st.dataframe(clinic_df[["姓名", "身份", "原級距", "現行級距", "投保金額", "符合資格"]], use_container_width=True)

    # 辦理離職
    with st.expander("🗑️ 辦理護理人員離職"):
        active_names = clinic_df["姓名"].tolist() if not clinic_df.empty else []
        if active_names:
            remove_name = st.selectbox("選擇離職人員", active_names)
            if st.button("確認辦理離職並更新"):
                staff_df.loc[(staff_df['院所'] == selected_clinic) & (staff_df['姓名'] == remove_name), '狀態'] = '離職'
                conn.update(worksheet="Staff", data=staff_df)
                st.warning(f"已將 {remove_name} 標記為離職並同步至雲端。")
                st.rerun()

# --- 模式 B：HR 總管理者模式 ---
else:
    st.subheader("📊 全院所護理人員執登卡控 - HR總表")
    
    # 🌟 核心功能：上傳健保署/衛福部「醫事人員執業清冊」自動擷取護理師母數
    with st.expander("📄 匯入健保署/衛福部「醫事人員執業清冊 (.xls/.xlsx)」", expanded=True):
        st.write("上傳各院所從健保系統下載的名冊檔（系統會自動篩選 **`護理師`** 與 **`護士`** 作為執登母數）。")
        
        col_c, col_f = st.columns([1, 2])
        target_clinic = col_c.selectbox("選擇此檔案所屬的院所：", ["台北院所", "台中院所", "高雄院所"])
        prsn_file = col_f.file_uploader("選擇執業清冊檔案 (.xls / .xlsx)", type=["xls", "xlsx"])
        
        if prsn_file is not None:
            try:
                # 讀取 Excel 檔案
                uploaded_prsn_df = pd.read_excel(prsn_file)
                
                # 檢查是否有健保清冊標準欄位「執業類別」
                if '執業類別' in uploaded_prsn_df.columns and '姓名' in uploaded_prsn_df.columns:
                    # 自動篩選 護理師 與 護士
                    nurse_only_df = uploaded_prsn_df[uploaded_prsn_df['執業類別'].isin(['護理師', '護士'])].copy()
                    
                    st.success(f"解析成功！從檔案中共抓取 **{len(nurse_only_df)}** 位護理人員（已自動排除醫師/藥師）。")
                    st.dataframe(nurse_only_df[['姓名', '執業類別', '執業起日']], use_container_width=True)
                    
                    if st.button(f"🚀 將這 {len(nurse_only_df)} 位護理人員寫入 [{target_clinic}] 執登名單"):
                        # 將原本該院所舊資料清除，換成新匯入的母數名單
                        other_clinics_df = staff_df[staff_df['院所'] != target_clinic] if '院所' in staff_df.columns else pd.DataFrame()
                        
                        new_records = []
                        for idx, row in nurse_only_df.iterrows():
                            new_records.append({
                                "院所": target_clinic,
                                "姓名": row['姓名'],
                                "身份": "舊有員工",  # 預設身份
                                "原級距": 1,
                                "現行級距": 1,
                                "投保金額": 27470,
                                "狀態": "在職"
                            })
                        
                        merged_df = pd.concat([other_clinics_df, pd.DataFrame(new_records)], ignore_index=True)
                        conn.update(worksheet="Staff", data=merged_df)
                        st.balloons()
                        st.success(f"✅ 已成功更新 [{target_clinic}] 的執登母數！會計可登入填寫詳細投保金額。")
                        st.rerun()
                else:
                    st.error("❌ 檔案欄位不符合健保清冊格式（未包含「執業類別」與「姓名」欄位）。")
            except Exception as e:
                st.error(f"檔案解析失敗：{e}")

    st.markdown("---")

    # 總表顯示
    clinics = list(set(df["院所"].tolist())) if not df.empty and '院所' in df.columns else ["台北院所", "台中院所"]
    summary_list = []
    
    for c in clinics:
        c_df = df[(df['院所'] == c) & (df['狀態'] == '在職')] if '院所' in df.columns else pd.DataFrame()
        tot = len(c_df)
        comp = c_df['符合資格'].sum() if tot > 0 and '符合資格' in c_df.columns else 0
        req = math.ceil(tot / 2) if tot > 0 else 0
        status = "🟢 達標" if (comp >= req and tot > 0) else "🔴 未達標"
        summary_list.append({
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
        st.warning(f"目前以下院所合規人數未達 1/2 標準：**{', '.join(unpassed)}**")
        selected_notify_clinic = st.selectbox("選擇要發送 LINE 提醒的院所：", unpassed)
        
        line_token = st.text_input("LINE Channel Access Token (機器人金鑰)", type="password", help="於 LINE Developers 後台取得")
        accountant_line_id = st.text_input("該院所會計的個人 LINE User ID (以 U 開頭)", help="會計加機器人好友後可於後台查看")
        
        msg_template = f"⚠️【HR催辦通知】\n{selected_notify_clinic} 負責會計您好：\n貴院本月護理師投保級距合規人數未達執登總人數之 1/2，請儘速進系統調整或補齊投保資料！"
        st.text_area("推播訊息內容預覽", msg_template, height=120)
        
        if st.button("🚀 即刻私訊發送 LINE 提醒"):
            if line_token and accountant_line_id:
                success = send_line_message(line_token, accountant_line_id, msg_template)
                if success:
                    st.success(f"✅ 已成功私訊發送給 [{selected_notify_clinic}] 負責會計！")
                else:
                    st.error("❌ 發送失敗，請檢查金鑰 (Token) 與會計的 LINE User ID 是否正確。")
            else:
                st.error("請輸入 LINE Token 與會計的 LINE User ID 後再發送。")
    else:
        st.balloons()
        st.success("🎉 所有院所本月皆已符合標準！無需發送提醒。")
