import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
# 注意：這裡引入的是偽裝能力最強的庫
from curl_cffi import requests as crequests

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE 旗艦看板", layout="wide")

def get_auto_token():
    """使用 Chrome 120 指紋偽裝登入"""
    login_url = "https://pos-api.dudooeat.com/users/login"
    
    payload = {
        "code": st.secrets["DUDOO_CODE"],
        "username": st.secrets["DUDOO_USER"],
        "password": st.secrets["DUDOO_PASS"]
    }
    
    try:
        # impersonate="chrome120" 是為了讓伺服器以為你是真的瀏覽器
        res = crequests.post(
            login_url, 
            data=payload, 
            impersonate="chrome120", 
            timeout=15
        )
        
        if res.status_code == 200:
            d = res.json()
            # 嘗試抓取 Token
            base_token = d.get('data', {}).get('access_token')
            
            if base_token:
                # 帶著基礎 Token 換取報表權限
                report_url = "https://pos-api.dudooeat.com/reports/login?type=reports"
                res_r = crequests.post(
                    report_url, 
                    data=payload, 
                    headers={"Access-Token": base_token},
                    impersonate="chrome120"
                )
                final_token = res_r.json().get('data', {}).get('access_token')
                return final_token or base_token, None
            else:
                return None, f"登入成功但找不到密鑰: {str(d)[:50]}"
        
        return None, f"登入被攔截 (代碼: {res.status_code})"
    except Exception as e:
        return None, f"模擬器執行失敗: {str(e)}"

def fetch_data(token, sd, ed):
    """抓取業績數據"""
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    payload = {
        "draw": "1", "start": "0", "length": "5000",
        "hierarchy_id": "17939", "company_id": "13223",
        "start_date": sd.strftime("%Y-%m-%d"),
        "end_date": ed.strftime("%Y-%m-%d"),
        "time_filter": "bill_create_time"
    }
    try:
        res = crequests.post(url, headers={"Access-Token": token}, data=payload, impersonate="chrome120")
        if res.status_code == 200:
            return res.json().get('data', []), None
        return None, "數據抓取失敗"
    except Exception as e:
        return None, str(e)

# --- 介面 ---
st.title("📊 CUBE LOUNGE 全自動智慧看板")

if "token" not in st.session_state:
    st.session_state.token = None

with st.sidebar:
    st.header("⚙️ 系統核心")
    # 如果偏要自動登入，就點這個按鈕
    if st.button("🚀 執行全自動授權", width='stretch'):
        with st.spinner("正在模擬真人操作中..."):
            t, err = get_auto_token()
            if err:
                st.error(f"自動登入失敗：{err}")
            else:
                st.session_state.token = t
                st.success("✅ 自動授權成功！")

    st.markdown("---")
    sd = st.date_input("開始日期", datetime.now().replace(day=1))
    ed = st.date_input("結束日期", datetime.now())
    update_btn = st.button("📈 刷新業績數據", width='stretch')

# --- 內容區 ---
if update_btn:
    if not st.session_state.token:
        st.warning("請先執行全自動授權。")
    else:
        with st.spinner("同步數據中..."):
            data, err = fetch_data(st.session_state.token, sd, ed)
            if err:
                st.error(f"抓取失敗：{err}")
            elif data:
                df = pd.DataFrame(data)
                df = df[df['status'] == 3]
                df['amount'] = df['amount'].astype(float)
                
                st.metric("範圍實收總計", f"${df['amount'].sum():,.0f}")
                st.subheader("👤 公關業績排行")
                res = df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                res.columns = ['公關/桌號', '累積業績']
                st.dataframe(res.style.format({"累積業績": "${:,.0f}"}), width='stretch', hide_index=True)
            else:
                st.info("查無資料。")