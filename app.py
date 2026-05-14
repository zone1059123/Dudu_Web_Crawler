import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE 全自動看板", layout="wide")

# --- 自動登入函數 ---
def get_auto_token():
    """使用帳密自動獲取最新的 Access-Token"""
    login_url = "https://pos-api.dudooeat.com/reports/login?type=reports"
    
    # 從 Secrets 讀取資料
    payload = {
        "code": st.secrets["DUDOO_CODE"],
        "username": st.secrets["DUDOO_USER"],
        "password": st.secrets["DUDOO_PASS"]
    }
    
    try:
        # 注意：肚肚登入通常使用 Form Data 格式
        res = requests.post(login_url, data=payload)
        if res.status_code == 200:
            token = res.json().get('data', {}).get('access_token')
            return token, None
        else:
            return None, f"登入失敗，請檢查帳密 (錯誤碼: {res.status_code})"
    except Exception as e:
        return None, f"登入過程發生錯誤: {str(e)}"

# --- 營業日判斷 ---
def get_business_date(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    if 0 <= dt.hour < 5:
        return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")

# --- 數據抓取 ---
def fetch_data(token, start_date, end_date):
    headers = {
        "Access-Token": token,
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    payload = {
        "draw": "1", "start": "0", "length": "1000",
        "hierarchy_id": "17939", "company_id": "13223",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "time_filter": "bill_create_time"
    }
    
    res = requests.post(url, headers=headers, data=payload)
    if res.status_code != 200:
        return None, "Token 已失效或無權限。"
    
    data = res.json().get('data', [])
    current_biz_day = get_business_date(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    pr_stats = {}
    total_revenue = 0
    
    for bill in data:
        if bill.get('status') != 3: # 排除作廢
            continue
        
        amount = bill.get('amount', 0)
        total_revenue += amount
        biz_day = get_business_date(bill.get('bill_create_time', ""))
        desk = bill.get('desk') or "未知/散客"
        
        if desk not in pr_stats:
            pr_stats[desk] = {"本日": 0, "本月": 0}
        
        pr_stats[desk]["本月"] += amount
        if biz_day == current_biz_day:
            pr_stats[desk]["本日"] += amount
            
    return {"total": total_revenue, "pr": pr_stats, "biz_day": current_biz_day}, None

# --- 前端畫面 ---
st.title("📊 CUBE LOUNGE 全自動報表系統")

# 自動登入邏輯
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None

with st.sidebar:
    st.header("⚙️ 系統設定")
    if st.button("🔄 重新登入獲取授權", use_container_width=True):
        with st.spinner("正在登入..."):
            token, err = get_auto_token()
            if err:
                st.error(err)
            else:
                st.session_state.auth_token = token
                st.success("登入成功！")

    today = datetime.now()
    start_date = st.date_input("開始日期", today.replace(day=1))
    end_date = st.date_input("結束日期", today)
    update_btn = st.button("🚀 更新數據", use_container_width=True)

# 顯示數據
if update_btn:
    # 如果還沒有 Token，先跑一次自動登入
    if not st.session_state.auth_token:
        token, err = get_auto_token()
        if not err:
            st.session_state.auth_token = token
    
    if st.session_state.auth_token:
        with st.spinner("抓取數據中..."):
            result, error = fetch_data(st.session_state.auth_token, start_date, end_date)
            if error:
                st.error(error)
                st.session_state.auth_token = None # 清除錯誤 Token
            else:
                # 指標面板
                c1, c2 = st.columns(2)
                c1.metric("🏠 全店範圍總實收", f"${result['total']:,}")
                today_total = sum(p["本日"] for p in result["pr"].values())
                c2.metric(f"🌙 今日業績 ({result['biz_day']})", f"${today_total:,}")
                
                # 表格
                st.subheader("👤 公關業績排行")
                df_data = [{"公關/桌號": k, "今日業績": v["本日"], "本月總額": v["本月"]} for k, v in result["pr"].items()]
                df = pd.DataFrame(df_data).sort_values("本月總額", ascending=False)
                st.dataframe(df.style.format({"今日業績": "${:,}", "本月總額": "${:,}"}), use_container_width=True, hide_index=True)
    else:
        st.warning("請先確保 Secrets 中的帳密正確，或點擊「重新登入」。")