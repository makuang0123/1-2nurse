import streamlit as st
import pandas as pd
import math
import requests
from streamlit_gsheets import GSheetsConnection

# 頁面標題與配置
st.set_page_config(page_title="護理人員執登與調薪卡控系統", layout="wide")

st.title("🩺 院所護理人員投保級距與執登管控系統 (正式版)")

# -------------------------------------------------------------------
# 1. Google Sheets 資料庫連線初始化
# -------------------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # 讀取名為 "Staff" 的工作表，若讀不到則回傳預設資料
        df = conn.read(worksheet="Staff", ttl=0)
        return df
    except Exception:
        # 預設資料結構
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
# 預設帳號密碼庫 (實際生產環境可儲存於 secrets)
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

# 登入後的側邊欄資訊
user = st.session_state.user_info
st.sidebar.success(f"👤 歡迎登入：{user['name']}")
if st.sidebar.button("🚪 登出系統"):
    st.session_state.logged_in = False
    st.session_state.user_info = None
    st.rerun()

# -------------------------------------------------------------------
# 3. 業務邏輯與 LINE 推播函數
# -------------------------------------------------------------------
def check_compliance(row):
    if row['狀態'] == '離職':
        return False
    if row['身份'] == '舊有員工' and row['現行級距'] > row['原級距']:
        return True
    if row['身份'] == '新進人員' and row['投保金額'] >= 33300:
        return True
    return False

def send_line_notify(token, message):
    url = "https://notify-api.line.me/api/notify"
    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": message}
    response = requests.post(url, headers=headers, data=data)
    return response.status_code == 200

# 計算合規性
df = staff_df.copy()
df['符合資格'] = df.apply(check_compliance, axis=1)

# -------------------------------------------------------------------
# 4. 畫面展示：會計輸入端 vs HR 總表
# -------------------------------------------------------------------

# --- 會計模式 ---
if user["role"] == "會計":
    selected_clinic = user["clinic"]
    st.subheader(f"📍 {selected_clinic} - 人員資料維護與管控")

    clinic_df = df[(df['院所'] == selected_clinic) & (df['狀態'] == '在職')]
    total_nurses = len(clinic_df)
    compliant_nurses = clinic_df['符合資格'].sum() if total_nurses > 0 else 0
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

    # 新增人員表單
    with st.expander("➕ 新增護理人員"):
        with st.form("add_nurse_form"):
            name = st.text_input("護理師姓名")
            emp_type = st.selectbox("人員身份", ["舊有員工", "新進人員"])
            prev_level = st.number_input("原投保級距 (新進填 0)", min_value=0, max_value=20, value=1)
            curr_level = st.number_input("現行投保級距", min_value=1, max_value=20, value=1)
            salary = st.number_input("投保金額 (NTD)", min_value=0, value=33300, step=100)
            
            if st.form_submit_button("儲存並更新至 Google Sheets"):
                if name:
                    new_row = {
                        "院所": selected_clinic, "姓名": name, "身份": emp_type,
                        "原級距": prev_level, "現行級距": curr_level, 
                        "投保金額": salary, "狀態": "在職"
                    }
                    updated_df = pd.concat([staff_df, pd.DataFrame([new_row])], ignore_index=True)
                    # 同步回寫 Google Sheets
                    conn.update(worksheet="Staff", data=updated_df)
                    st.success(f"已成功新增 {name} 並同步寫入雲端資料庫！")
                    st.rerun()

    # 顯示目前名單
    st.write("📋 **目前執登人員名單**")
    st.dataframe(clinic_df[["姓名", "身份", "原級距", "現行級距", "投保金額", "符合資格"]], use_container_width=True)

    # 辦理離職
    with st.expander("🗑️ 辦理護理人員離職"):
        active_names = clinic_df["姓名"].tolist()
        if active_names:
            remove_name = st.selectbox("選擇離職人員", active_names)
            if st.button("確認辦理離職並更新"):
                staff_df.loc[(staff_df['院所'] == selected_clinic) & (staff_df['姓名'] == remove_name), '狀態'] = '離職'
                conn.update(worksheet="Staff", data=staff_df)
                st.warning(f"已將 {remove_name} 標記為離職並同步至雲端。")
                st.rerun()

# --- HR 總管理者模式 ---
else:
    st.subheader("📊 全院所護理人員執登卡控 - HR總表")
    
    clinics = list(set(df["院所"].tolist()))
    summary_list = []
    
    for c in clinics:
        c_df = df[(df['院所'] == c) & (df['狀態'] == '在職')]
        tot = len(c_df)
        comp = c_df['符合資格'].sum() if tot > 0 else 0
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
    st.subheader("🔔 LINE Notify 自動催辦推播")
    
    unpassed = summary_df[summary_df["管控狀態"] == "🔴 未達標"]["院所名稱"].tolist()
    
    if unpassed:
        st.warning(f"目前以下院所合規人數未達 1/2 標準：**{', '.join(unpassed)}**")
        selected_notify_clinic = st.selectbox("選擇要發送 LINE 提醒的院所：", unpassed)
        
        # 讀取 Secrets 中的 LINE Token (若無設定可手動輸入測試)
        line_token = st.text_input("LINE Notify Token (發送權限金鑰)", type="password", help="可在 LINE Notify 官網免費申請")
        
        msg_template = f"\n⚠️【HR催辦通知】\n{selected_notify_clinic} 負責會計您好：\n貴院本月護理師投保級距合規人數未達執登總人數之 1/2，請儘速進系統調整或補齊投保資料！"
        st.text_area("推播訊息內容預覽", msg_template, height=120)
        
        if st.button("🚀 即刻發送 LINE 推播訊息"):
            if line_token:
                success = send_line_notify(line_token, msg_template)
                if success:
                    st.success(f"✅ 已成功將提醒訊息推播至 [{selected_notify_clinic}] 的 LINE！")
                else:
                    st.error("❌ 發送失敗，請檢查 LINE Notify Token 是否正確。")
            else:
                st.error("請輸入 LINE Notify Token 後再嘗試發送。")
    else:
        st.balloons()
        st.success("🎉 所有院所本月皆已符合標準！無需發送提醒。")
