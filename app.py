import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

# --- 參數設定區 ---
TW_TZ = pytz.timezone('Asia/Taipei')
CUTOFF_HOUR = 4  
# 💡 退回只抓 3 (已結帳)。加了 1 會爆表代表後台不算未結單。
STATUS_FILTER = [3]  

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE Dashboard", layout="wide", page_icon="📊")

def fetch_data(token, start_date, end_date):
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    payload = {
        "draw": "1", "start": "0", "length": "5000",
        "hierarchy_id": "17939", "company_id": "13223",
        "start_date": (start_date - timedelta(days=2)).strftime("%Y-%m-%d"), 
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

def get_business_date(dt):
    try:
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
    
    now_tw = datetime.now(TW_TZ)
    sd = st.date_input("開始日期", now_tw.replace(day=1))
    ed = st.date_input("結束日期", now_tw.date())
    run_button = st.button("🚀 刷新數據", width='stretch', type="primary")

if run_button and user_token:
    with st.spinner("正在讀取並比對數據..."):
        raw_data, err = fetch_data(user_token, sd, ed)
        
        if err:
            st.error(f"連線失敗: {err}")
        elif not raw_data:
            st.info("該日期範圍內查無數據。")
        else:
            # === 原始資料預處理 (用於除錯與過濾) ===
            df_raw = pd.DataFrame(raw_data)
            df_raw['amount'] = pd.to_numeric(df_raw['amount'], errors='coerce').fillna(0)
            df_raw['status'] = pd.to_numeric(df_raw['status'], errors='coerce')
            
            time_col = 'bill_create_time'
            if time_col in df_raw.columns:
                df_raw[time_col] = pd.to_datetime(df_raw[time_col])
                df_raw['b_date'] = df_raw[time_col].apply(get_business_date)
            else:
                df_raw['b_date'] = "Unknown"

            # === 正式業績資料過濾 ===
            df = df_raw[df_raw['status'].isin(STATUS_FILTER)].copy()
            
            if 'desk' in df.columns:
                df['desk'] = df['desk'].apply(normalize_name)
            
            current_b_date = get_business_date(datetime.now(TW_TZ))
            this_shift_df = df[df['b_date'] == current_b_date].copy()
            today_total = this_shift_df['amount'].sum()
            
            start_date_str = sd.strftime("%Y-%m-%d")
            end_date_str = ed.strftime("%Y-%m-%d")
            prev_date_str = (sd - timedelta(days=1)).strftime("%Y-%m-%d")

            condition_a = (df['b_date'] >= start_date_str) & (df['b_date'] <= end_date_str)
            condition_b = (df['b_date'] == prev_date_str) & (df[time_col].dt.date == sd) & (df[time_col].dt.hour < CUTOFF_HOUR)

            range_df = df[condition_a | condition_b].copy()
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

            # --- 💡 新增：抓漏透視面板 ---
            st.markdown("---")
            with st.expander("🛠️ 抓漏透視面板 (點此展開比對落差)"):
                st.write("以下數據包含 **API 抓回來的所有原始帳單**（未過濾狀態碼），請比對看看後台是不是偷藏了什麼我們沒算到的項目：")
                
                diag_c1, diag_c2 = st.columns(2)
                with diag_c1:
                    st.markdown("**1. 找出隱藏的狀態碼**")
                    st.write("除了 1(未結) 和 3(已結)，有沒有其他狀態碼（例如 2, 4, 5）帶有金額？")
                    status_summary = df_raw.groupby('status')['amount'].sum().reset_index()
                    st.dataframe(status_summary.style.format({"amount": "${:,.0f}"}), use_container_width=True)
                
                with diag_c2:
                    st.markdown("**2. 單日營業額比對**")
                    st.write("核對下表每天的總額，看是「哪一天」跟後台報表對不上？")
                    # 只看查詢區間內的單日總和 (以防 API 吐太多天的資料)
                    df_raw_range = df_raw[(df_raw['b_date'] >= start_date_str) & (df_raw['b_date'] <= end_date_str)]
                    date_summary = df_raw_range[df_raw_range['status'] == 3].groupby('b_date')['amount'].sum().reset_index()
                    st.dataframe(date_summary.style.format({"amount": "${:,.0f}"}), use_container_width=True)