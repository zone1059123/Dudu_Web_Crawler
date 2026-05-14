import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE 管理系統", layout="wide")

# --- 核心邏輯函數 ---
def get_business_date(date_str):
    """處理跨日營業時間：凌晨 5 點前的單算在前一天"""
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    if 0 <= dt.hour < 5:
        return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")

def fetch_data(token, start_date, end_date):
    """從肚肚伺服器抓取並處理數據"""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Access-Token": token,
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
        res = requests.post(url, headers=headers, data=payload)
        if res.status_code != 200:
            return None, f"連線失敗，Token 可能過期或無權限 (錯誤碼：{res.status_code})"
        
        data = res.json().get('data', [])
        if not data:
            return None, "找不到資料，請確認日期範圍是否有帳單。"
        
        # 數據處理
        current_biz_day = get_business_date(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        pr_stats = {}
        total_revenue = 0
        
        for bill in data:
            # 排除作廢 (status 必須為 3)
            if bill.get('status') != 3:
                continue
                
            amount = bill.get('amount', 0)
            total_revenue += amount
            
            bill_time = bill.get('bill_create_time', "")
            biz_day = get_business_date(bill_time)
            desk = bill.get('desk') or "未知/散客"
            
            if desk not in pr_stats:
                pr_stats[desk] = {"今日業績": 0, "本月業績": 0}
            
            pr_stats[desk]["本月業績"] += amount
            if biz_day == current_biz_day:
                pr_stats[desk]["今日業績"] += amount
        
        return {"total": total_revenue, "pr": pr_stats, "biz_day": current_biz_day}, None
        
    except Exception as e:
        return None, f"程式執行錯誤: {str(e)}"

# --- 網頁前端介面 ---
st.title("📊 CUBE LOUNGE 經營數據看板")
st.markdown("---")

# 側邊欄設定
with st.sidebar:
    st.header("🔑 系統狀態")
    
    # 優先從 Secrets 抓，抓不到才給輸入框
    if "DUDOO_TOKEN" in st.secrets:
        token = st.secrets["DUDOO_TOKEN"]
        st.success("✅ 已自動載入授權碼")
    else:
        token = st.text_input("請輸入 Access Token", type="password")
        st.warning("⚠️ 尚未設定雲端授權碼")
    
    st.header("📅 查詢範圍")
    today = datetime.now()
    start_date = st.date_input("開始日期", today.replace(day=1))
    end_date = st.date_input("結束日期", today)
    
    # 確保按鈕被定義
    update_btn = st.button("🚀 更新報表數據", use_container_width=True)

# 執行更新邏輯 (這一段要確保在按鈕定義之後)
if update_btn:
    if not token:
        st.error("請輸入 Token 才能抓取資料！")
    else:
        result, error = fetch_data(token, start_date, end_date)
        
        if error:
            st.error(error)
        else:
            # 1. 頂部關鍵指標
            col1, col2 = st.columns(2)
            with col1:
                st.metric("🏠 全店累計實收 (選擇範圍)", f"${result['total']:,}")
            with col2:
                today_total = sum(p["今日業績"] for p in result["pr"].values())
                st.metric(f"🌙 今日業績 ({result['biz_day']})", f"${today_total:,}")
                
            st.markdown("---")
            
            # 2. 公關業績表格
            st.subheader("👤 公關/桌號業績明細")
            df_data = [{"公關/桌號": k, "本日業績": v["今日業績"], "本月業績": v["本月業績"]} for k, v in result["pr"].items()]
            df = pd.DataFrame(df_data).sort_values(by="本月業績", ascending=False)
            
            st.dataframe(
                df.style.format({"本日業績": "${:,}", "本月業績": "${:,}"}),
                use_container_width=True,
                hide_index=True
            )
            
            st.success(f"數據更新成功！(分析時間: {datetime.now().strftime('%H:%M:%S')})")
else:
    st.info("👋 歡迎回來！點擊左側「更新報表數據」按鈕開始分析。")

st.markdown("---")
st.caption(f"Server Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")