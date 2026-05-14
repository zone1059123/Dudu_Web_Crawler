import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE 旗艦看板", layout="wide")

def fetch_data(token):
    """使用雲端獲取的 Token 抓取業績"""
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    payload = {
        "draw": "1", "start": "0", "length": "5000",
        "hierarchy_id": "17939", # 從你截圖拿到的固定 ID
        "company_id": "13223",
        "start_date": datetime.now().replace(day=1).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "time_filter": "bill_create_time"
    }
    headers = {"Access-Token": token, "User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=10)
        if res.status_code == 200:
            return res.json().get('data', []), None
        return None, "Token 失效"
    except:
        return None, "連線失敗"

# --- 主程式 ---
st.title("📊 CUBE LOUNGE 實時營運看板")

# 這裡我們模擬從雲端獲取 Token (你可以先手動在 Secrets 設定一個 DUDOO_TOKEN)
# 未來你可以改成讀取 Google Sheet
current_token = st.secrets.get("DUDOO_TOKEN")

if not current_token:
    st.error("❌ 雲端找不到授權鑰匙，請聯繫管理員更新 Secrets。")
else:
    data, err = fetch_data(current_token)
    
    if err:
        st.warning(f"⚠️ 自動授權暫時失效：{err}")
        # 提供一個應急輸入框給老闆
        emergency_token = st.text_input("應急 Token 輸入", type="password")
        if emergency_token:
            current_token = emergency_token
            data, err = fetch_data(current_token)

    if data:
        st.success("✅ 數據已透過自動雲端授權同步")
        df = pd.DataFrame(data)
        df = df[df['status'] == 3] # 過濾作廢單
        df['amount'] = df['amount'].astype(float)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("本月累計實收", f"${df['amount'].sum():,.0f}")
        with col2:
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_amt = df[df['create_time'].str.contains(today_str)]['amount'].sum()
            st.metric("今日實時業績", f"${today_amt:,.0f}")
            
        st.markdown("---")
        st.subheader("👤 公關業績排行 (TOP 10)")
        ranking = df.groupby('desk')['amount'].sum().sort_values(ascending=False).head(10).reset_index()
        ranking.columns = ['公關/桌號', '業績總計']
        st.dataframe(ranking.style.format({"業績總計": "${:,.0f}"}), width='stretch', hide_index=True)