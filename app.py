import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz

# --- 參數設定區 ---
TW_TZ = pytz.timezone('Asia/Taipei')
STATUS_FILTER = [3]  

# 💡 破案關鍵：請在這裡填寫代表「銷售金額」的 API 欄位名稱！
# 常見的名稱可能是 'sales_amount', 'actual_price', 'total_price', 'subtotal'
TARGET_AMOUNT_COL = 'sale_amount'  # <--- 如果名稱不同，請修改這行

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

def get_business_date(dt, cutoff):
    try:
        if 0 <= dt.hour < cutoff:
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
    st.subheader("⚙️ 營業設定")
    cutoff_hour = st.number_input("營業日切換時間 (凌晨幾點)", min_value=0, max_value=12, value=4)
    
    st.markdown("---")
    st.subheader("📅 查詢區間")
    now_tw = datetime.now(TW_TZ)
    sd = st.date_input("開始日期", now_tw.replace(day=1))
    ed = st.date_input("結束日期", now_tw.date() - timedelta(days=1)) 
    run_button = st.button("🚀 刷新數據", width='stretch', type="primary")

if run_button and user_token:
    with st.spinner(f"正在以 {TARGET_AMOUNT_COL} 重新計算業績..."):
        raw_data, err = fetch_data(user_token, sd, ed)
        
        if err:
            st.error(f"連線失敗: {err}")
        elif not raw_data:
            st.info("該日期範圍內查無數據。")
        else:
            df_raw = pd.DataFrame(raw_data)
            
            # 💡 抽換業績欄位核心邏輯
            if TARGET_AMOUNT_COL in df_raw.columns:
                df_raw['calc_amount'] = pd.to_numeric(df_raw[TARGET_AMOUNT_COL], errors='coerce').fillna(0)
            else:
                st.warning(f"⚠️ 找不到您指定的 '{TARGET_AMOUNT_COL}' 欄位，系統暫時退回使用 'amount' 計算。請去最下方的面板檢查正確的欄位名稱！")
                df_raw['calc_amount'] = pd.to_numeric(df_raw['amount'], errors='coerce').fillna(0)
                
            df_raw['status'] = pd.to_numeric(df_raw['status'], errors='coerce')
            
            time_col = 'bill_create_time'
            if time_col in df_raw.columns:
                df_raw[time_col] = pd.to_datetime(df_raw[time_col])
                df_raw['b_date'] = df_raw[time_col].apply(lambda x: get_business_date(x, cutoff_hour))
            else:
                df_raw['b_date'] = "Unknown"

            # 過濾狀態碼
            df = df_raw[df_raw['status'].isin(STATUS_FILTER)].copy()
            if 'desk' in df.columns:
                df['desk'] = df['desk'].apply(normalize_name)
            
            current_b_date = get_business_date(datetime.now(TW_TZ), cutoff_hour)
            this_shift_df = df[df['b_date'] == current_b_date].copy()
            # 改用 calc_amount 加總
            today_total = this_shift_df['calc_amount'].sum()
            
            start_date_str = sd.strftime("%Y-%m-%d")
            end_date_str = ed.strftime("%Y-%m-%d")
            range_df = df[(df['b_date'] >= start_date_str) & (df['b_date'] <= end_date_str)].copy()
            # 改用 calc_amount 加總
            range_total = range_df['calc_amount'].sum()

            # --- 頂部指標 ---
            c1, c2, c3 = st.columns(3)
            c1.metric("今晚場次業績", f"${today_total:,.0f}")
            c2.metric("所選區間總營收", f"${range_total:,.0f}")
            c3.metric("本場成交單數", f"{len(this_shift_df)} 單")
            st.markdown("---")

            col_rank1, col_rank2 = st.columns(2)
            with col_rank1:
                st.subheader("🔥 今晚場次公關排行")
                if not this_shift_df.empty:
                    today_rank = this_shift_df.groupby('desk')['calc_amount'].sum().sort_values(ascending=False).reset_index()
                    today_rank.columns = ['公關/桌號', '今晚業績']
                    today_rank.index += 1
                    st.table(today_rank.style.format({"今晚業績": "${:,.0f}"}))
                else:
                    st.info("今晚場次暫無數據。")

            with col_rank2:
                st.subheader("🏆 區間累計公關排行")
                if not range_df.empty:
                    range_rank = range_df.groupby('desk')['calc_amount'].sum().sort_values(ascending=False).reset_index()
                    range_rank.columns = ['公關/桌號', '累計業績']
                    range_rank.index += 1
                    st.table(range_rank.style.format({"累計業績": "${:,.0f}"}))

            # --- 💡 抓漏面板 ---
            st.markdown("---")
            with st.expander("🛠️ API 原始資料檢查 (用來尋找正確的銷售金額欄位)"):
                st.write("如果您不確定「銷售金額」在 API 裡的英文是什麼，請看下方這張表：")
                if not df_raw.empty:
                    sample_data = df_raw.iloc[0:1].T
                    sample_data.columns = ['第一筆訂單的數值']
                    st.dataframe(sample_data, height=400)