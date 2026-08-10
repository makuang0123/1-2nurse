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
# 1. 預設資料庫 (包含潮州院所 10 位護理人員清冊)
# -------------------------------------------------------------------
DEFAULT_NURSES = [
    {"區域": "屏東", "院所": "潮州院所", "姓名": "廖靜敏", "執業類別": "護士", "身份": "舊有員工", "符合資格": "🟢 符合", "符合原因": "調薪", "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "李晨寧", "執業類別": "護理師", "身份": "舊有員工", "符合資格": "🟢 符合", "符合原因": "調薪", "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "林庭如", "執業類別": "護理師", "身份": "新進人員", "符合資格": "🟢 符合", "符合原因": "新到職符合級距", "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "梁淑雅", "執業類別": "護理師", "身份": "舊有員工", "符合資格": "🔴 不符合", "符合原因": "無", "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "洪羿羚", "執業類別": "護理師", "身份": "舊有員工", "符合資格": "🟢 符合", "符合原因": "調薪", "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "莊羽樺", "執業類別": "護理師", "身份": "新進人員", "符合資格": "🟢 符合", "符合原因": "新到職符合級距", "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "蔡函紜", "執業類別": "護理師", "身份": "舊有員工", "符合資格": "🔴 不符合", "符合原因": "無", "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "趙育萱", "執業類別": "護理師", "身份": "舊有員工", "符合資格": "🔴 不符合", "符合原因": "無", "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "陳靖誼", "執業類別": "護理師", "身份": "舊有員工", "符合資格": "🟢 符合", "符合原因": "調薪", "狀態": "在職"},
    {"區域": "屏東", "院所": "潮州院所", "姓名": "黃玉芬", "執業類別": "護理師", "身份": "舊有員工", "符合資格": "🔴 不符合", "符合原因": "無", "狀態": "在職"},
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

# 舊版相容修正
if not staff_df.empty and "符合資格" in staff_df.columns:
    staff_df["符合資格"] = staff_df["符合資格"].replace({"符合": "🟢 符合", "不符合": "🔴 不符合"})

required_cols = ["區域", "院所", "姓名", "執業類別", "身份", "符合資格", "符合原因", "狀態"]
for col in required_cols:
    if col not in staff_df.columns:
        if col == "符合資格":
            staff_df[col] = "🔴 不符合"
        elif col == "符合原因":
            staff_df[col] = "無"
        elif col == "身份":
            staff_df[col] = "舊有員工"
        elif col == "狀態":
            staff_df[col] = "在職"
        else:
            staff_df[col] = ""

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
# 3. 資料儲存與 LINE 發送函數
# -------------------------------------------------------------------
def save_data(new_df):
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

# -------------------------------------------------------------------
# 4. 畫面展示：會計試算/勾選端 vs HR 總表
# -------------------------------------------------------------------

# 頂部導覽列備份下載按鈕
st.sidebar.markdown("---")
st.sidebar.subheader("📥 系統資料備份與匯出")
csv_data = staff_df.to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button(
    label="💾 匯出最新完整資料庫 (.csv)",
    data=csv_data,
    file_name="nurse_control_master.csv",
    mime="text/csv"
)

# ===================================================================
# --- 模式 A：院所會計輸入/勾選端 ---
# ===================================================================
if user["role"] == "會計":
    st.sidebar.markdown("---")
    st.sidebar.subheader("📍 選擇服務院所")
    
    selected_region = st.sidebar.selectbox("1. 請先選擇大項「區域」：", list(CLINIC_REGIONS.keys()))
    available_clinics = CLINIC_REGIONS[selected_region]
    selected_clinic = st.sidebar.selectbox("2. 再選擇小項「院所」：", available_clinics)

    st.subheader(f"📍【{selected_region}區】{selected_clinic} - 下個月執登與調薪卡控預測")

    clinic_df_next_month = staff_df[(staff_df['院所'] == selected_clinic) & (staff_df['狀態'] != '離職')]
    
    total_nurses_next_month = len(clinic_df_next_month)
    compliant_nurses_next_month = len(clinic_df_next_month[clinic_df_next_month['符合資格'].str.contains('符合', na=False)])
    target_needed = math.ceil(total_nurses_next_month / 2) if total_nurses_next_month > 0 else 0
    is_passed = compliant_nurses_next_month >= target_needed and total_nurses_next_month > 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📅 下月預估執登數 (扣離職)", f"{total_nurses_next_month} 人")
    col2.metric("符合資格人數", f"{compliant_nurses_next_month} 人")
    col3.metric("需達標人數 (1/2)", f"{target_needed} 人")
    
    if is_passed:
        col4.success("🟢 下個月預估審核：符合規定")
    else:
        col4.error("🔴 下個月預估審核：未達標！")

    st.markdown("---")
    st.write("✏️ **護理人員資格下拉勾選（修改完成後請點下方儲存按鈕）**")

    editable_df = staff_df[staff_df['院所'] == selected_clinic].copy()
    
    edited_df = st.data_editor(
        editable_df,
        column_config={
            "區域": st.column_config.TextColumn("區域", disabled=True),
            "院所": st.column_config.TextColumn("院所", disabled=True),
            "姓名": st.column_config.TextColumn("姓名", disabled=True),
            "執業類別": st.column_config.TextColumn("類別", disabled=True),
            "身份": st.column_config.SelectboxColumn("身份別", options=["舊有員工", "新進人員"], required=True),
            "符合資格": st.column_config.SelectboxColumn("符合資格", options=["🟢 符合", "🔴 不符合"], required=True),
            "符合原因": st.column_config.SelectboxColumn("符合原因", options=["調薪", "新到職符合級距", "無"], required=True),
            "狀態": st.column_config.SelectboxColumn("狀態 (離職下月扣除)", options=["在職", "離職"], required=True),
        },
        use_container_width=True,
        hide_index=True,
        key=f"data_editor_{selected_clinic}"
    )

    if st.button("💾 儲存並更新變更"):
        # 精準對齊索引替換全域資料
        staff_df.loc[staff_df['院所'] == selected_clinic, :] = edited_df.values
        save_data(staff_df)
        st.success("✅ 修改內容已成功儲存！")
        st.rerun()

    st.markdown("---")
    with st.expander("➕ 手動新增名冊外人員"):
        with st.form("add_single_nurse"):
            new_name = st.text_input("姓名")
            new_title = st.selectbox("執業類別", ["護理師", "護士"])
            new_type = st.selectbox("身份別", ["舊有員工", "新進人員"])
            new_qual = st.selectbox("符合資格", ["🟢 符合", "🔴 不符合"])
            new_reason = st.selectbox("符合原因", ["調薪", "新到職符合級距", "無"])
            if st.form_submit_button("新增該人員"):
                if new_name:
                    add_row = {
                        "區域": selected_region, "院所": selected_clinic, "姓名": new_name, "執業類別": new_title,
                        "身份": new_type, "符合資格": new_qual, "符合原因": new_reason, "狀態": "在職"
                    }
                    updated_all = pd.concat([staff_df, pd.DataFrame([add_row])], ignore_index=True)
                    save_data(updated_all)
                    st.success(f"已成功新增 {new_name}")
                    st.rerun()

# ===================================================================
# --- 模式 B：HR 總管理者端 (全權限檢視、匯入與編修) ---
# ===================================================================
else:
    st.subheader("📊 全院所護理人員下月執登卡控 - HR總表")
    
    # ---------------------------------------------------------------
    # 1. 清冊匯入區
    # ---------------------------------------------------------------
    with st.expander("📄 上傳各院健保署/衛福部「醫事人員執業清冊 (.xls/.xlsx)」或「備份資料庫 (.csv)」", expanded=False):
        st.write("可上傳健保局清冊（自動提取護理師/護士）或歷史備份檔：")
        col_r, col_c, col_f = st.columns([1, 1, 2])
        target_region = col_r.selectbox("選擇大項【區域】：", list(CLINIC_REGIONS.keys()), key="hr_import_reg")
        target_clinic = col_c.selectbox("選擇小項【院所】：", CLINIC_REGIONS[target_region], key="hr_import_cli")
        prsn_file = col_f.file_uploader("選擇檔案 (.xls / .xlsx / .csv)", type=["xls", "xlsx", "csv"])
        
        if prsn_file is not None:
            try:
                if prsn_file.name.endswith('.csv'):
                    imported_csv = pd.read_csv(prsn_file)
                    save_data(imported_csv)
                    st.success("✅ 已成功還原並覆蓋最新完整資料庫！")
                    st.rerun()
                else:
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
                                        "區域": target_region, "院所": target_clinic, "姓名": row['姓名'],
                                        "執業類別": row['執業類別'], "身份": "舊有員工", "符合資格": "🔴 不符合",
                                        "符合原因": "無", "狀態": "在職"
                                    })
                                    added_count += 1
                            
                            if new_rows:
                                merged_df = pd.concat([staff_df, pd.DataFrame(new_rows)], ignore_index=True)
                                save_data(merged_df)
                                st.balloons()
                                st.success(f"✅ 更新成功！新增了 {added_count} 位新護理人員！")
                            else:
                                st.warning("⚠️ 檔案中的護理人員皆已存在。")
                            st.rerun()
            except Exception as e:
                st.error(f"檔案讀取失敗：{e}")

    st.markdown("---")

    # ---------------------------------------------------------------
    # 2. 全院卡控總表 (即時連動計算)
    # ---------------------------------------------------------------
    st.write("🔍 **總表區域篩選**")
    filter_region = st.selectbox("選擇要檢視的區域（或顯示全部）：", ["全部區域"] + list(CLINIC_REGIONS.keys()))

    summary_list = []
    display_clinics = ALL_CLINICS if filter_region == "全部區域" else CLINIC_REGIONS[filter_region]
    
    for c in display_clinics:
        c_region = CLINIC_TO_REGION.get(c, "")
        c_df_next_month = staff_df[(staff_df['院所'] == c) & (staff_df['狀態'] != '離職')] if '院所' in staff_df.columns else pd.DataFrame()
        tot = len(c_df_next_month)
        comp = len(c_df_next_month[c_df_next_month['符合資格'].str.contains('符合', na=False)]) if tot > 0 else 0
        req = math.ceil(tot / 2) if tot > 0 else 0
        status = "🟢 達標" if (comp >= req and tot > 0) else ("⚪ 尚未建立名冊" if tot == 0 else "🔴 未達標")
        
        summary_list.append({
            "區域": c_region,
            "院所名稱": c,
            "下月預估執登數 (扣離職)": tot,
            "符合資格人數": comp,
            "標準門檻 (1/2)": req,
            "下月管控預測": status
        })
    
    summary_df = pd.DataFrame(summary_list)
    st.table(summary_df)

    # ---------------------------------------------------------------
    # 3. HR 深入檢視與調整各院所人員明細 (雙向完美同步)
    # ---------------------------------------------------------------
    st.markdown("---")
    st.subheader("📋 HR 深入檢視與調整各院所人員明細")
    st.write("請使用下方連動選單選擇欲查看的院所：")
    
    col_hr_detail_r, col_hr_detail_c = st.columns(2)
    hr_view_region = col_hr_detail_r.selectbox("1. 選擇大項【區域】：", list(CLINIC_REGIONS.keys()), key="hr_view_reg")
    hr_view_clinic = col_hr_detail_c.selectbox("2. 選擇小項【院所】：", CLINIC_REGIONS[hr_view_region], key="hr_view_cli")

    st.markdown(f"#### 📍【{hr_view_region}區】{hr_view_clinic} - 下月預估現況")

    hr_clinic_df_next_month = staff_df[(staff_df['院所'] == hr_view_clinic) & (staff_df['狀態'] != '離職')]
    hr_tot = len(hr_clinic_df_next_month)
    hr_comp = len(hr_clinic_df_next_month[hr_clinic_df_next_month['符合資格'].str.contains('符合', na=False)])
    hr_req = math.ceil(hr_tot / 2) if hr_tot > 0 else 0
    hr_passed = hr_comp >= hr_req and hr_tot > 0

    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("下月預估執登數 (扣離職)", f"{hr_tot} 人")
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
                "符合資格": st.column_config.SelectboxColumn("符合資格", options=["🟢 符合", "🔴 不符合"], required=True),
                "符合原因": st.column_config.SelectboxColumn("符合原因", options=["調薪", "新到職符合級距", "無"], required=True),
                "狀態": st.column_config.SelectboxColumn("狀態 (離職下月扣除)", options=["在職", "離職"], required=True),
            },
            use_container_width=True,
            hide_index=True,
            key=f"hr_data_editor_{hr_view_clinic}"
        )
        
        if st.button(f"💾 儲存 [{hr_view_clinic}] 的人員變更", key="hr_save_btn"):
            # 精準對齊替換全域資料
            staff_df.loc[staff_df['院所'] == hr_view_clinic, :] = hr_edited_df.values
            save_data(staff_df)
            st.success(f"✅ 已成功更新 [{hr_view_clinic}] 的人員資料並同步至全院總表！")
            st.rerun()
            
        with st.expander(f"➕ 手動新增名冊外人員至 [{hr_view_clinic}]"):
            with st.form("hr_add_single_nurse"):
                hr_new_name = st.text_input("姓名")
                hr_new_title = st.selectbox("執業類別", ["護理師", "護士"])
                hr_new_type = st.selectbox("身份別", ["舊有員工", "新進人員"])
                hr_new_qual = st.selectbox("符合資格", ["🟢 符合", "🔴 不符合"])
                hr_new_reason = st.selectbox("符合原因", ["調薪", "新到職符合級距", "無"])
                if st.form_submit_button("新增該人員"):
                    if hr_new_name:
                        add_row = {
                            "區域": hr_view_region, "院所": hr_view_clinic, "姓名": hr_new_name, "執業類別": hr_new_title,
                            "身份": hr_new_type, "符合資格": hr_new_qual, "符合原因": hr_new_reason, "狀態": "在職"
                        }
                        updated_all = pd.concat([staff_df, pd.DataFrame([add_row])], ignore_index=True)
                        save_data(updated_all)
                        st.success(f"已成功新增 {hr_new_name}")
                        st.rerun()
    else:
        st.info(f"💡 目前【{hr_view_clinic}】尚未建立人員名冊，可利用頁面上方方塊上傳該院所的醫事人員執業清冊。")

    # ---------------------------------------------------------------
    # 4. LINE 推播區
    # ---------------------------------------------------------------
    st.markdown("---")
    st.subheader("🔔 LINE 官方帳號 - 私訊催辦推播")
    
    unpassed = summary_df[summary_df["下月管控預測"] == "🔴 未達標"]["院所名稱"].tolist() if not summary_df.empty else []
    
    if unpassed:
        st.warning(f"目前下個月預估未達 1/2 標準之院所：**{', '.join(unpassed)}**")
        selected_notify_clinic = st.selectbox("選擇要提醒的院所：", unpassed)
        
        line_token = st.text_input("LINE Channel Access Token (機器人金鑰)", type="password")
        accountant_line_id = st.text_input("該院所會計個人 LINE User ID")
        
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
        st.success("🎉 所有院所下個月預估皆已符合標準（或無未達標院所）！無需發送提醒。")
