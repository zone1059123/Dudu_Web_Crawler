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
            return None, f"連線失敗，錯誤碼：{res.status_code}"
        
        data = res.json().get('data', [])
        if not data:
            return None, "找不到資料，請確認 Token 或日期是否正確。"
        
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
        return None, str(e)

# --- 網頁前端介面 ---
st.title("📊 CUBE LOUNGE 經營數據看板")
st.markdown("---")

# 側邊欄設定
with st.sidebar:
    st.header("🔑 系統狀態")

    # 自動從 Secrets 讀取 Token，如果讀不到才讓使用者手動輸入
    if "DUDOO_TOKEN" in st.secrets:
        token = st.secrets["DUDOO_TOKEN"]
        st.success("✅ 已自動載入授權碼")
    else:
        token = st.text_input("請輸入 Access Token", type="password")
        st.warning("⚠️ 尚未設定雲端授權碼")

# 執行更新
if update_btn:
    result, error = fetch_data(token, start_date, end_date)
    
    if error:
        st.error(error)
    else:
        # 1. 頂部關鍵指標
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🏠 全店累計實收 (本月)", f"${result['total']:,}")
        with col2:
            # 計算今日全店總額
            today_total = sum(p["今日業績"] for p in result["pr"].values())
            st.metric(f"🌙 今日業績 ({result['biz_day']})", f"${today_total:,}")
            
        st.markdown("---")
        
        # 2. 公關業績表格
        st.subheader("👤 公關/桌號業績明細")
        
        # 轉換數據格式給表格
        df_data = []
        for name, s in result["pr"].items():
            df_data.append({
                "公關/桌號": name,
                "本日業績": s["今日業績"],
                "本月業績": s["本月業績"]
            })
        
        df = pd.DataFrame(df_data).sort_values(by="本月業績", ascending=False)
        
        # 設定表格樣式
        st.dataframe(
            df.style.format({"本日業績": "${:,}", "本月業績": "${:,}"}),
            use_container_width=True,
            hide_index=True
        )
        
        # 3. 簡單圖表分析
        st.markdown("---")
        st.subheader("📈 業績佔比分析")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.write("公關業績分佈 (本月)")
            st.bar_chart(df.set_index("公關/桌號")["本月業績"])
        with chart_col2:
            st.info("""
            **報表說明：**
            1. 數據已自動**排除作廢單**。
            2. 時間邏輯：晚上 21:00 至隔日凌晨 04:59 之帳單統一歸類為同一營業日。
            3. 若數據未更新，請檢查 Token 是否過期。
            """)
else:
    st.info("👋 歡迎回來！請確認左側設定並點擊「更新報表數據」按鈕開始分析。")

# 頁尾
st.markdown("---")
st.caption(f"最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")