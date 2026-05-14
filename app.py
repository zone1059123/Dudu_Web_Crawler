import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE 營運看板", layout="wide")

def get_auto_token():
    """終極模擬真人登入邏輯"""
    # 切換回最基礎的登入入口，不要加 ?type=reports
    login_url = "https://pos-api.dudooeat.com/users/login"
    
    # 這裡的資料務必對準你的 Secrets
    payload = {
        "code": st.secrets["DUDOO_CODE"],
        "username": st.secrets["DUDOO_USER"],
        "password": st.secrets["DUDOO_PASS"]
    }
    
    # 偽裝成跟你的 Chrome 一模一樣的 Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    try:
        # 使用 Session 維持連線狀態
        session = requests.Session()
        res = session.post(login_url, data=payload, headers=headers, timeout=10)
        
        if res.status_code == 200:
            d = res.json()
            # 優先從 data 裡面找 token
            token = d.get('data', {}).get('access_token') or d.get('access_token')
            
            if token:
                return token, None
            else:
                return None, f"登入成功但回傳內容無 Token: {str(d)[:50]}"
        
        return None, f"登入伺服器拒絕請求 (代碼: {res.status_code})"
        
    except Exception as e:
        return None, f"連線異常: {str(e)}"
def fetch_data(token, start_date, end_date):
    """抓取資料邏輯"""
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    headers = {
        "Access-Token": token,
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    payload = {
        "draw": "1", "start": "0", "length": "5000",
        "hierarchy_id": "17939", "company_id": "13223",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "time_filter": "bill_create_time"
    }
    res = requests.post(url, headers=headers, data=payload, timeout=15)
    if res.status_code == 200:
        return res.json().get('data', []), None
    return None, "Token 已失效"

# --- 側邊欄 ---
with st.sidebar:
    st.header("🔐 授權設定")
    
    # 模式切換：自動登入 或 手動貼 Token
    mode = st.radio("選擇授權方式", ["自動登入 (推薦)", "手動貼上 Token"])
    
    final_token = None
    
    if mode == "自動登入 (推薦)":
        if st.button("🔄 執行自動登入", width='stretch'):
            t, err = get_auto_token()
            if t: 
                st.session_state.token = t
                st.success("自動登入成功！")
            else: st.error(f"自動登入失敗：{err}")
    else:
        st.info("請貼上 F12 看到的 Access-Token")
        manual_token = st.text_input("Token", type="password")
        if manual_token: st.session_state.token = manual_token

    st.markdown("---")
    sd = st.date_input("開始日期", datetime.now().replace(day=1))
    ed = st.date_input("結束日期", datetime.now())
    update_btn = st.button("🚀 更新業績數據", width='stretch')

# --- 主畫面 ---
st.title("📊 CUBE LOUNGE 實時業績")

if update_btn:
    current_token = st.session_state.get('token')
    if not current_token:
        st.warning("請先完成授權（點擊自動登入或輸入 Token）")
    else:
        data, err = fetch_data(current_token, sd, ed)
        if err:
            st.error(f"抓取失敗：{err}")
        else:
            # 計算邏輯...
            df = pd.DataFrame(data)
            if not df.empty:
                # 排除作廢
                df = df[df['status'] == 3]
                total = df['amount'].astype(float).sum()
                st.metric("範圍內總業績", f"${total:,.0f}")
                
                # 桌號排行
                st.subheader("桌號/公關 業績排行")
                res = df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                res.columns = ['桌號/公關', '累積業績']
                st.dataframe(res.style.format({"累積業績": "${:,.0f}"}), width='stretch', hide_index=True)
            else:
                st.info("此日期範圍內無資料。")