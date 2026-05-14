import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE Dashboard", layout="wide", page_icon="📊")

def fetch_data(token, start_date, end_date):
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    # 擴大搜尋範圍，確保跨夜數據能被抓到
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

# --- 核心邏輯：判斷營業場次 ---
def get_business_date(dt_str):
    """
    自定義營業日邏輯：
    晚上 21:00 ~ 隔天 04:00 算同一個場次
    """
    dt = pd.to_datetime(dt_str)
    # 如果是凌晨 00:00 ~ 03:59，歸類為前一天的場次
    if 0 <= dt.hour < 4:
        return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    # 其他時間（特別是 21:00 以後）算當天
    return dt.strftime("%Y-%m-%d")

# --- UI 介面 ---
st.title("🍹 CUBE LOUNGE 實時看板 (跨夜營業場次版)")

with st.sidebar:
    st.header("🔑 授權設定")
    user_token = st.text_input("Access-Token", type="password")
    st.markdown("---")
    st.subheader("📅 查詢區間")
    sd = st.date_input("開始日期", datetime.now().replace(day=1))
    ed = st.date_input("結束日期", datetime.now())
    run_button = st.button("🚀 刷新數據", width='stretch', type="primary")

if run_button and user_token:
    with st.spinner("計算場次業績中..."):
        raw_data, err = fetch_data(user_token, sd, ed)
        if err:
            st.error(f"連線失敗: {err}")
        elif raw_data:
            df = pd.DataFrame(raw_data)
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
            df = df[df['status'] == 3].copy()
            
            # 應用營業日定義
            df['b_date'] = df['create_time'].apply(get_business_date)
            
            # --- 今日場次業績計算 ---
            # 判斷現在這個時刻屬於哪個營業場次
            now = datetime.now()
            current_b_date = get_business_date(now)
            
            # 篩選出目前這一場的資料
            this_shift_df = df[df['b_date'] == current_b_date]
            today_total = this_shift_df['amount'].sum()
            
            # 篩選出所選範圍內的累計資料
            range_df = df[(df['b_date'] >= sd.strftime("%Y-%m-%d")) & (df['b_date'] <= ed.strftime("%Y-%m-%d"))]
            range_total = range_df['amount'].sum()

            # --- 頂部指標 ---
            c1, c2, c3 = st.columns(3)
            c1.metric("今晚場次業績", f"${today_total:,.0f}", help="定義為今晚 21:00 至明晨 04:00")
            c2.metric("所選區間總營收", f"${range_total:,.0f}")
            c3.metric("本場成交單數", f"{len(this_shift_df)} 單")

            st.markdown("---")

            # --- 公關排行區 ---
            col_rank1, col_rank2 = st.columns(2)
            
            with col_rank1:
                st.subheader("🔥 今晚場次公關排行")
                if not this_shift_df.empty:
                    today_rank = this_shift_df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                    today_rank.columns = ['公關/桌號', '今晚業績']
                    today_rank.index += 1
                    st.table(today_rank.style.format({"今晚業績": "${:,.0f}"}))
                else:
                    st.info("今晚場次暫無數據（21:00 開始計入）")

            with col_rank2:
                st.subheader("🏆 區間累計公關排行")
                if not range_df.empty:
                    range_rank = range_df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                    range_rank.columns = ['公關/桌號', '累計業績']
                    range_rank.index += 1
                    st.table(range_rank.style.format({"累計業績": "${:,.0f}"}))

            # --- 詳細明細 ---
            with st.expander("📄 查看原始帳單明細 (已標註營業場次)"):
                st.dataframe(range_df[['create_time', 'b_date', 'desk', 'amount', 'bill_no']], use_container_width=True)