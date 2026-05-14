import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
# 引入最強偽裝庫
from curl_cffi import requests as crequests

st.set_page_config(page_title="CUBE LOUNGE 全自動智慧看板", layout="wide")

def get_auto_token():
    """終極模擬：繞過 400 Access Token 缺失錯誤"""
    # 這是主系統登入點
    login_url = "https://pos-api.dudooeat.com/users/login"
    
    payload = {
        "code": st.secrets["DUDOO_CODE"],
        "username": st.secrets["DUDOO_USER"],
        "password": st.secrets["DUDOO_PASS"]
    }
    
    # 嚴格模擬瀏覽器的 Header 順序與內容
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://admin.dudooeat.com",
        "Referer": "https://admin.dudooeat.com/",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    try:
        # 關鍵：impersonate="chrome120" 會模擬 Chrome 的連線特徵
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
                
                # 去「報表房」換取報表專用 Token (對應你網址中的 reports)
                report_auth_url = "https://pos-api.dudooeat.com/reports/login?type=reports"
                res_r = crequests.post(
                    report_auth_url, 
                    data=payload, 
                    headers={"Access-Token": base_token, **headers},
                    impersonate="chrome120"
                )
                
                # 抓取最終的 Access-Token
                final_token = res_r.json().get('data', {}).get('access_token')
                return final_token or base_token, None
            else:
                return None, f"登入失敗：{result.get('error', {}).get('message')}"
        
        return None, f"伺服器攔截 (HTTP {res.status_code})"
    except Exception as e:
        return None, f"環境執行錯誤: {str(e)}"

# --- 數據抓取 ---
def fetch_data(token, sd, ed):
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    payload = {
        "draw": "1", "start": "0", "length": "5000",
        "hierarchy_id": "17939",
        "company_id": "13223",
        "start_date": sd.strftime("%Y-%m-%d"),
        "end_date": ed.strftime("%Y-%m-%d"),
        "time_filter": "bill_create_time"
    }
    try:
        res = crequests.post(url, headers={"Access-Token": token}, data=payload, impersonate="chrome120")
        return res.json().get('data', []), None
    except Exception as e:
        return None, str(e)

# --- 介面佈局 ---
st.title("📊 CUBE LOUNGE 全自動智慧看板")

if "token" not in st.session_state:
    st.session_state.token = None

with st.sidebar:
    st.header("⚙️ 核心連線")
    if st.button("🚀 啟動全自動授權", width='stretch'):
        with st.spinner("正在破解安全驗證..."):
            t, err = get_auto_token()
            if err:
                st.error(f"自動失敗：{err}")
            else:
                st.session_state.token = t
                st.success("✅ 授權成功！")

    st.markdown("---")
    sd = st.date_input("開始日期", datetime.now().replace(day=1))
    ed = st.date_input("結束日期", datetime.now())
    update = st.button("📈 刷新業績看板", width='stretch')

# --- 主畫面顯示 ---
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
                
                col1, col2 = st.columns(2)
                col1.metric("範圍實收總計", f"${df['amount'].sum():,.0f}")
                
                # 計算今日預估
                today_str = datetime.now().strftime("%Y-%m-%d")
                today_total = df[df['create_time'].str.contains(today_str)]['amount'].sum()
                col2.metric("今日實時業績", f"${today_total:,.0f}")

                st.subheader("👤 公關業績排行")
                res = df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                res.columns = ['公關/桌號', '累積業績']
                st.dataframe(res.style.format({"累積業績": "${:,.0f}"}), width='stretch', hide_index=True)
            else:
                st.info("該日期範圍內無任何帳單。")