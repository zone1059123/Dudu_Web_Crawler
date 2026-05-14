import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --- 頁面設定 (確保標題為純英文，避免編碼問題) ---
st.set_page_config(page_title="CUBE LOUNGE Dashboard", layout="wide", page_icon="📊")

# --- 核心抓取函數 ---
def fetch_data(token, start_date, end_date):
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    
    # 確保 payload 資料格式正確
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
    
    # 重要：Header 嚴禁出現中文字，解決 'latin-1' 編碼報錯
    headers = {
        "Access-Token": str(token).strip(),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json"
    }
    
    try:
        # 發送請求
        res = requests.post(url, headers=headers, data=payload, timeout=15)
        
        if res.status_code == 200:
            result = res.json()
            if result.get('success'):
                return result.get('data', []), None
            return None, f"Auth Failed: {result.get('error', {}).get('message', 'Invalid Token')}"
        return None, f"Server Error: {res.status_code}"
    except Exception as e:
        # 如果是編碼錯誤，這裡會捕獲並提示
        return None, f"Connection Error: {str(e)}"

# --- 側邊欄控制 ---
with st.sidebar:
    st.header("🔑 Auth Settings")
    # 提示使用者貼上 Token
    user_token = st.text_input("Paste Access-Token Here", type="password")
    
    st.markdown("---")
    st.subheader("📅 Date Range")
    # 預設顯示當月
    sd = st.date_input("Start Date", datetime.now().replace(day=1))
    ed = st.date_input("End Date", datetime.now())
    
    run_button = st.button("🚀 Refresh Data", width='stretch', type="primary")

# --- 主畫面顯示 ---
st.title("🍹 CUBE LOUNGE 實時業績看板")

if run_button:
    if not user_token:
        st.warning("請在左側貼上 Access-Token 才能開始！")
    else:
        with st.spinner("正在讀取數據..."):
            data, err = fetch_data(user_token, sd, ed)
            
            if err:
                st.error(f"發生錯誤：{err}")
                if "latin-1" in str(err):
                    st.info("💡 提示：Token 中可能包含特殊字元或空格，請重新複製貼上。")
            elif data:
                # 1. 建立 DataFrame
                df = pd.DataFrame(data)
                
                # 2. 資料清洗 (過濾 status=3 正常單)
                if 'status' in df.columns:
                    # 確保 status 是數字類型再過濾
                    df['status'] = pd.to_numeric(df['status'], errors='coerce')
                    df = df[df['status'] == 3].copy()
                
                # 金額轉換
                if 'amount' in df.columns:
                    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
                else:
                    st.error("找不到業績欄位 'amount'")
                    st.stop()

                # 3. 指標計算
                # --- 區間累計 ---
                total_revenue = df['amount'].sum()
                
                # --- 今日業績 ---
                today_str = datetime.now().strftime("%Y-%m-%d")
                if 'create_time' in df.columns:
                    today_df = df[df['create_time'].str.contains(today_str, na=False)]
                    today_revenue = today_df['amount'].sum()
                else:
                    today_revenue = 0
                
                # 4. 頂部看板指標展示
                col1, col2, col3 = st.columns(3)
                col1.metric("今日實時業績", f"${today_revenue:,.0f}")
                col2.metric("選取區間總營收", f"${total_revenue:,.0f}")
                col3.metric("總成交單數", f"{len(df)} 單")
                
                st.markdown("---")
                
                # 5. 公關排行 (加入安全檢查)
                st.subheader("👤 公關業績排行")
                
                # 判斷公關欄位名稱 (優先找 desk)
                potential_cols = ['desk', 'table_name', 'desk_name']
                rank_col = next((c for c in potential_cols if c in df.columns), None)
                
                if rank_col:
                    ranking = df.groupby(rank_col)['amount'].sum().sort_values(ascending=False).reset_index()
                    ranking.columns = ['公關/桌號', '累積業績']
                    ranking.index = ranking.index + 1
                    st.table(ranking.style.format({"累積業績": "${:,.0f}"}))
                else:
                    st.warning("找不到公關名稱欄位，顯示原始資料。")

                # 6. 詳細明細 (防止 KeyError)
                with st.expander("📄 查看詳細帳單明細"):
                    wish_list = ['create_time', 'desk', 'amount', 'bill_no', 'order_no']
                    safe_cols = [c for c in wish_list if c in df.columns]
                    
                    if safe_cols:
                        st.dataframe(df[safe_cols], use_container_width=True)
                    else:
                        st.write("顯示所有可用欄位：")
                        st.dataframe(df)
            else:
                st.info("該區間內查無數據，請確認日期或 Token 是否正確。")

else:
    st.info("💡 操作教學：登入肚肚後台 -> F12 -> 找到 getBillInvoicesList -> 複製 Access-Token 貼到左側。")