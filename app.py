import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

# --- 參數設定區 (請依據杜督益後台實際邏輯微調) ---
TW_TZ = pytz.timezone('Asia/Taipei')
CUTOFF_HOUR = 4  # 跨夜營業切換點 (0-23)，目前預設為清晨 4 點前算前一天
STATUS_FILTER = [3]  # 欲計算的帳單狀態碼 (3通常為已結帳。若後台包含未結帳請改為 [1, 3])

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE Dashboard", layout="wide", page_icon="📊")

def fetch_data(token, start_date, end_date):
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    payload = {
        "draw": "1", "start": "0", "length": "5000",
        "hierarchy_id": "17939", "company_id": "13223",
        "start_date": (start_date - timedelta(days=1)).strftime("%Y-%m-%d"), 
        "end_date": (end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
        "time_filter": "bill_create_time" # 若發現後台是用結帳時間算業績，請改為 "checkout_time"
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
    try:
        dt = pd.to_datetime(dt_val)
        # 依據設定的跨夜切換點判定營業日
        if 0 <= dt.hour < CUTOFF_HOUR:
            return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except:
        return "Unknown"

def normalize_name(name):
    if not isinstance(name, str): return name
    name = name.strip()
    
    merge_map = {
        "Lynn洪": "洪Lynn",
        "洪lynn": "洪Lynn", 
        "lynn洪": "洪Lynn",
    }
    
    return merge_map.get(name, name)

# --- UI 介面 ---
st.title("🍹 SUNSETCUBE")

with st.sidebar:
    st.header("🔑 系統授權")
    user_token = st.text_input("Access-Token", type="password")
    st.markdown("---")
    st.subheader("📅 查詢區間")
    
    # 修正：確保預設日期也是使用台灣時區
    now_tw = datetime.now(TW_TZ)
    sd = st.date_input("開始日期", now_tw.replace(day=1))
    ed = st.date_input("結束日期", now_tw.date())
    run_button = st.button("🚀 刷新數據", width='stretch', type="primary")

if run_button and user_token:
    with st.spinner("正在套用台灣時區並計算數據..."):
        raw_data, err = fetch_data(user_token, sd, ed)
        
        if err:
            st.error(f"連線失敗: {err}")
        elif not raw_data:
            st.info("該日期範圍內查無數據。")
        else:
            df = pd.DataFrame(raw_data)
            
            # 安全轉換與狀態碼彈性過濾
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
            df['status'] = pd.to_numeric(df['status'], errors='coerce')
            df = df[df['status'].isin(STATUS_FILTER)].copy()
            
            if 'desk' in df.columns:
                df['desk'] = df['desk'].apply(normalize_name)
            
            # 使用正確的時間欄位判定營業日
            time_col = 'bill_create_time'
            if time_col in df.columns:
                df['b_date'] = df[time_col].apply(get_business_date)
            else:
                df['b_date'] = "Unknown"
            
            # --- 場次業績計算 (修正：採用台灣時間獲取當前營業日) ---
            current_b_date = get_business_date(datetime.now(TW_TZ))
            this_shift_df = df[df['b_date'] == current_b_date].copy()
            today_total = this_shift_df['amount'].sum()
            
            range_df = df[(df['b_date'] >= sd.strftime("%Y-%m-%d")) & (df['b_date'] <= ed.strftime("%Y-%m-%d"))].copy()
            range_total = range_df['amount'].sum()

            # --- 頂部指標 ---
            c1, c2, c3 = st.columns(3)
            c1.metric("今晚場次業績", f"${today_total:,.0f}")
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
                    st.info("今晚場次暫無數據。")

            with col_rank2:
                st.subheader("🏆 區間累計公關排行")
                if not range_df.empty:
                    range_rank = range_df.groupby('desk')['amount'].sum().sort_values(ascending=False).reset_index()
                    range_rank.columns = ['公關/桌號', '累計業績']
                    range_rank.index += 1
                    st.table(range_rank.style.format({"累計業績": "${:,.0f}"}))

            with st.expander("📄 查看詳細帳單明細 (已套用時區校正)"):
                show_cols = ['bill_create_time', 'b_date', 'desk', 'amount', 'status']
                final_show = [c for c in show_cols if c in df.columns]
                st.dataframe(range_df[final_show], use_container_width=True)