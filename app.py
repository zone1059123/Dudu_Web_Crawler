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
    
    # 檢查 Secrets 是否存在
    try:
        payload = {
            "code": st.secrets["DUDOO_CODE"],
            "username": st.secrets["DUDOO_USER"],
            "password": st.secrets["DUDOO_PASS"]
        }
    except Exception as e:
        return None, f"Secrets 設定缺失: {str(e)}"
    
    try:
        res = requests.post(login_url, data=payload, timeout=10)
        if res.status_code == 200:
            token = res.json().get('data', {}).get('access_token')
            if token:
                return token, None
            return None, "登入成功但未取得 Token，請檢查帳號權限。"
        else:
            return None, f"登入失敗 (錯誤碼: {res.status_code})，請檢查帳密是否正確。"
    except Exception as e:
        return None, f"連線至肚肚伺服器失敗: {str(e)}"

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
    
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=15)
        if res.status_code != 200:
            return None, f"抓取失敗，Token 可能過期 (Code: {res.status_code})"
        
        data = res.json().get('data', [])
        current_biz_day = get_business_date(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        pr_stats = {}
        total_revenue = 0
        
        for bill in data:
            if bill.get('status') != 3:
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
    except Exception as e:
        return None, f"抓取過程錯誤: {str(e)}"

# --- 前端介面 ---
st.title("📊 CUBE LOUNGE 全自動報表系統")

# 初始化 Session State
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None

with st.sidebar:
    st.header("⚙️ 系統設定")
    # 修正 width='stretch' 符合 2026 新規範
    login_clicked = st.button("🔄 重新登入獲取授權", width='stretch')
    
    if login_clicked:
        with st.spinner("正在登入..."):
            token, err = get_auto_token()
            if err:
                st.error(err)
            else:
                st.session_state.auth_token = token
                st.success("登入成功！")

    st.markdown("---")
    today = datetime.now()
    start_date = st.date_input("開始日期", today.replace(day=1))
    end_date = st.date_input("結束日期", today)
    update_btn = st.button("🚀 更新數據", width='stretch')

# --- 主要內容區 ---
if update_btn:
    # 點擊更新時，若無 Token 則自動試試登入
    if not st.session_state.auth_token:
        with st.spinner("自動登入中..."):
            token, err = get_auto_token()
            if not err:
                st.session_state.auth_token = token
            else:
                st.error(f"自動登入失敗: {err}")

    if st.session_state.auth_token:
        with st.spinner("正在分析數據，請稍後..."):
            result, error = fetch_data(st.session_state.auth_token, start_date, end_date)
            if error:
                st.error(error)
                st.session_state.auth_token = None
            else:
                # 數據看板
                col1, col2 = st.columns(2)
                col1.metric("🏠 選擇範圍實收總計", f"${result['total']:,}")
                today_total = sum(p["本日"] for p in result["pr"].values())
                col2.metric(f"🌙 今日營業額 ({result['biz_day']})", f"${today_total:,}")
                
                st.markdown("---")
                st.subheader("👤 公關業績排行")
                df_data = [{"公關/桌號": k, "今日業績": v["本日"], "累積總額": v["本月"]} for k, v in result["pr"].items()]
                if df_data:
                    df = pd.DataFrame(df_data).sort_values("累積總額", ascending=False)
                    st.dataframe(df.style.format({"今日業績": "${:,}", "累積總額": "${:,}"}), width='stretch', hide_index=True)
                else:
                    st.write("該範圍內無任何營業數據。")
    else:
        st.warning("無法獲取授權，請檢查 Secrets 裡的 DUDOO_CODE, DUDOO_USER, DUDOO_PASS 是否正確。")
else:
    if not st.session_state.auth_token:
        st.info("👋 歡迎！請點擊左側「重新登入」或直接點擊「更新數據」。")
    else:
        st.success("✅ 系統已就緒，請點擊「更新數據」顯示報表。")

st.markdown("---")
st.caption(f"Last sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")