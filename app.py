import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE Dashboard", layout="wide", page_icon="📊")

def fetch_data(token, start_date, end_date):
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    # 自動擴大抓取範圍，確保跨夜資料能對齊
    payload = {
        "draw": "1", "start": "0", "length": "5000",
        "hierarchy_id": "17939", "company_id": "13223",
        "start_date": (start_date - timedelta(days=1)).strftime("%Y-%m-%d"), 
        "end_date": (end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
        "time_filter": "bill_create_time"
    }
    headers = {
        "Access-Token": str(token).strip(),
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=15)
        if res.status_code == 200:
            return res.json().get('data', []), None
        return None, f"Server Error: {res.status_code}"
    except Exception as e:
        return None, str(e)

def get_business_date(dt_val):
    """自定義營業日：晚上 21:00 ~ 隔天 04:00 算同一場次"""
    try:
        dt = pd.to_datetime(dt_val)
        if 0 <= dt.hour < 4:
            return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except:
        return "Unknown"

# --- UI 介面 ---
st.title("🍹 CUBE LOUNGE 跨夜營業看板")

with st.sidebar:
    st.header("🔑 系統授權")
    user_token = st.text_input("Access-Token", type="password")
    st.markdown("---")
    st.subheader("📅 查詢區間")
    sd = st.date_input("開始日期", datetime.now().replace(day=1))
    ed = st.date_input("結束日期", datetime.now())
    run_button = st.button("🚀 刷新數據", width='stretch', type="primary")

if run_button and user_token:
    with st.spinner("同步跨夜數據中..."):
        raw_data, err = fetch_data(user_token, sd, ed)
        
        if err:
            st.error(f"連線失敗: {err}")
        elif not raw_data:
            st.info("該日期範圍內查無數據。")
        else:
            df = pd.DataFrame(raw_data)
            
            # --- 自動修正欄位名稱 (關鍵修復) ---
            # 肚肚有時候會變動欄位大小寫或名稱，這裡做強行校對
            col_map = {
                'create_time': ['create_time', 'createTime', 'Time', '時間'],
                'amount': ['amount', 'total_amount', 'Amount', '金額'],
                'desk': ['desk', 'table_name', 'desk_name', '桌號', '公關']
            }
            
            for target, options in col_map.items():
                for opt in options:
                    if opt in df.columns and target not in df.columns:
                        df[target] = df[opt]

            # 檢查必要欄位是否存在
            if 'create_time' not in df.columns or 'amount' not in df.columns:
                st.error("找不到必要的資料欄位 (時間或金額)，請檢查 API 回傳內容。")
                st.write("目前抓到的欄位有：", list(df.columns))
                st.stop()

            # 資料清洗
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
            if 'status' in df.columns:
                df = df[pd.to_numeric(df['status'], errors='coerce') == 3].copy()
            
            # 應用營業日定義
            df['b_date'] = df['create_time'].apply(get_business_date)
            
            # --- 場次業績計算 ---
            current_b_date = get_business_date(datetime.now())
            this_shift_df = df[df['b_date'] == current_b_date].copy()
            today_total = this_shift_df['amount'].sum()
            
            range_df = df[(df['b_date'] >= sd.strftime("%Y-%m-%d")) & (df['b_date'] <= ed.strftime("%Y-%m-%d"))].copy()
            range_total = range_df['amount'].sum()

            # --- 頂部指標 ---
            c1, c2, c3 = st.columns(3)
            c1.metric("今晚場次業績", f"${today_total:,.0f}")
            c2.metric("選取區間總營收", f"${range_total:,.0f}")
            c3.metric("本場成交單數", f"{len(this_shift_df)} 單")

            st.markdown("---")

            # --- 公關排行區 ---
            col_rank1, col_rank2 = st.columns(2)
            
            # 確定公關顯示欄位
            display_name = 'desk' if 'desk' in df.columns else '公關/桌號'

            with col_rank1:
                st.subheader("🔥 今晚場次公關排行")
                if not this_shift_df.empty:
                    today_rank = this_shift_df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                    today_rank.columns = [display_name, '今晚業績']
                    today_rank.index += 1
                    st.table(today_rank.style.format({"今晚業績": "${:,.0f}"}))
                else:
                    st.info("今晚場次暫無數據（營業時間：21:00 - 04:00）")

            with col_rank2:
                st.subheader("🏆 區間累計公關排行")
                if not range_df.empty:
                    range_rank = range_df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                    range_rank.columns = [display_name, '累計業績']
                    range_rank.index += 1
                    st.table(range_rank.style.format({"累計業績": "${:,.0f}"}))

            # --- 詳細明細 ---
            with st.expander("📄 查看詳細帳單明細"):
                show_cols = [c for c in ['create_time', 'b_date', 'desk', 'amount'] if c in df.columns]
                st.dataframe(range_df[show_cols], use_container_width=True)