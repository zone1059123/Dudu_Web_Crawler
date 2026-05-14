import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE 業績看板", layout="wide", page_icon="📊")

# --- 核心抓取函數 ---
def fetch_data(token, start_date, end_date):
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    
    # 這裡使用你提供的固定 ID
    payload = {
        "draw": "1",
        "start": "0",
        "length": "5000",
        "hierarchy_id": "17939",
        "company_id": "13223",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "time_filter": "bill_create_time"
    }
    
    headers = {
        "Access-Token": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=10)
        if res.status_code == 200:
            result = res.json()
            if result.get('success'):
                return result.get('data', []), None
            return None, f"授權失敗：{result.get('error', {}).get('message', 'Token 可能過期')}"
        return None, f"伺服器回應錯誤 (代碼: {res.status_code})"
    except Exception as e:
        return None, f"連線異常: {str(e)}"

# --- 側邊欄控制 ---
with st.sidebar:
    st.header("🔑 授權與設定")
    # 使用 password 模式隱藏 token
    user_token = st.text_input("請貼上 Access-Token", type="password", help="從 F12 > Network > getBillInvoicesList 獲取")
    
    st.markdown("---")
    st.subheader("📅 查詢區間")
    col_s, col_e = st.columns(2)
    sd = col_s.date_input("開始日期", datetime.now().replace(day=1))
    ed = col_e.date_input("結束日期", datetime.now())
    
    run_button = st.button("📈 刷新業績數據", width='stretch', type="primary")

# --- 主畫面顯示 ---
st.title("🍹 CUBE LOUNGE 實時業績看板")

if run_button:
    if not user_token:
        st.warning("請先在左側選單貼上有效的 Access-Token！")
    else:
        with st.spinner("正在讀取肚肚系統數據..."):
            data, err = fetch_data(user_token, sd, ed)
            
            if err:
                st.error(err)
            elif data:
                # 1. 建立資料表
                df = pd.DataFrame(data)
                
                # 2. 資料清洗：僅統計「已完成(status=3)」的帳單，並轉換金額
                df = df[df['status'] == 3].copy()
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
                
                # 3. 關鍵指標
                total_rev = df['amount'].sum()
                bill_count = len(df)
                avg_bill = total_rev / bill_count if bill_count > 0 else 0
                
                m1, m2, m3 = st.columns(3)
                m1.metric("選取區間總營收", f"${total_rev:,.0f}")
                m2.metric("總成交單數", f"{bill_count} 單")
                m3.metric("平均單筆金額", f"${avg_bill:,.0f}")
                
                st.markdown("---")
                
                # 4. 公關/桌號排行榜
                st.subheader("👤 公關業績排行榜")
                # 依照 desk 分組計算總額
                ranking = df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                ranking.columns = ['公關/桌號', '累積業績']
                
                # 加入名次
                ranking.index = ranking.index + 1
                
                st.table(ranking.style.format({"累積業績": "${:,.0f}"}))
                
                # 5. 今日明細 (可選)
                with st.expander("📄 查看所有帳單明細"):
                    st.dataframe(df[['create_time', 'desk', 'amount', 'bill_no']], use_container_width=True)
            else:
                st.info("該日期範圍內沒有任何營業數據。")

else:
    st.info("💡 操作教學：登入肚肚後台 -> 按 F12 -> 點擊任何報表 -> 找到 getBillInvoicesList -> 複製 Request Headers 中的 Access-Token 並貼到左側。")