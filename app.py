import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
# 使用能模擬瀏覽器 TLS 指紋的庫
from curl_cffi import requests as crequests

st.set_page_config(page_title="CUBE LOUNGE 全自動看板", layout="wide")

def get_auto_token():
    """強行突破：模擬 Chrome 120 的連線指紋"""
    # 注意：我們直接進攻最核心的登入 API
    login_url = "https://pos-api.dudooeat.com/users/login"
    
    payload = {
        "code": st.secrets["DUDOO_CODE"],
        "username": st.secrets["DUDOO_USER"],
        "password": st.secrets["DUDOO_PASS"]
    }
    
    # 這些 Header 必須跟瀏覽器一模一樣，且順序不能亂
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://admin.dudooeat.com",
        "Referer": "https://admin.dudooeat.com/",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    try:
        # impersonate="chrome120" 是為了繞過 400 錯誤的核心
        res = crequests.post(
            login_url, 
            data=payload, 
            headers=headers,
            impersonate="chrome120", 
            timeout=20
        )
        
        if res.status_code == 200:
            result = res.json()
            if result.get('success'):
                # 拿到了第一層通行證
                base_token = result.get('data', {}).get('access_token')
                
                # 帶著它去激活「報表權限」，這是你網址中 /reports/ 的由來
                report_auth_url = "https://pos-api.dudooeat.com/reports/login?type=reports"
                res_r = crequests.post(
                    report_auth_url, 
                    data=payload, 
                    headers={"Access-Token": base_token, **headers},
                    impersonate="chrome120"
                )
                
                final_token = res_r.json().get('data', {}).get('access_token')
                return final_token or base_token, None
            else:
                return None, f"登入被拒：{result.get('error', {}).get('message')}"
        
        return None, f"連線被防火牆攔截 (代碼: {res.status_code})"
    except Exception as e:
        return None, f"執行環境錯誤: {str(e)}"

# --- 數據抓取 ---
def fetch_data(token, sd, ed):
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
        return res.json().get('data', []), None
    except Exception as e:
        return None, str(e)

# --- 網頁配置 ---
st.title("📊 CUBE LOUNGE 實時業績看板 (自動化版)")

if "token" not in st.session_state:
    st.session_state.token = None

with st.sidebar:
    st.header("⚙️ 核心控制器")
    if st.button("🔄 全自動獲取最新授權", width='stretch'):
        with st.spinner("正在破解安全驗證..."):
            t, err = get_auto_token()
            if err:
                st.error(f"自動失敗：{err}")
            else:
                st.session_state.token = t
                st.success("✅ 授權已就緒！")

    st.markdown("---")
    sd = st.date_input("開始", datetime.now().replace(day=1))
    ed = st.date_input("結束", datetime.now())
    update = st.button("📈 刷新業績", width='stretch')

if update:
    if not st.session_state.token:
        st.warning("請先點擊上方「自動獲取授權」")
    else:
        with st.spinner("同步數據中..."):
            data, err = fetch_data(st.session_state.token, sd, ed)
            if err: st.error(err)
            elif data:
                df = pd.DataFrame(data)
                df = df[df['status'] == 3]
                df['amount'] = df['amount'].astype(float)
                st.metric("範圍實收總計", f"${df['amount'].sum():,.0f}")
                
                res = df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                res.columns = ['公關/桌號', '業績']
                st.dataframe(res.style.format({"業績": "${:,.0f}"}), width='stretch', hide_index=True)