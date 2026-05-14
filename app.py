import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE 旗艦看板", layout="wide", page_icon="📊")

# --- 核心抓取函數 ---
def fetch_data(token, start_date, end_date):
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    
    # 這裡使用固定 ID
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
    
    headers = {
        "Access-Token": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=10)
        if res.status_code == 200:
            result = res.json()
            if result.get('success'):
                return result.get('data', []), None
            return None, f"授權失敗：{result.get('error', {}).get('message', 'Token 已過期')}"
        return None, f"伺服器錯誤 (代碼: {res.status_code})"
    except Exception as e:
        return None, f"連線異常: {str(e)}"

# --- 側邊欄控制 ---
with st.sidebar:
    st.header("🔑 系統授權")
    user_token = st.text_input("請貼上 Access-Token", type="password")
    
    st.markdown("---")
    st.subheader("📅 查詢設定")
    # 預設查詢整個月
    sd = st.date_input("開始日期", datetime.now().replace(day=1))
    ed = st.date_input("結束日期", datetime.now())
    
    run_button = st.button("🚀 刷新數據數據", width='stretch', type="primary")

# --- 主畫面顯示 ---
st.title("🍹 CUBE LOUNGE 實時業績看板")

if run_button:
    if not user_token:
        st.warning("請先在左側貼上 Access-Token！")
    else:
        with st.spinner("正在同步數據..."):
            data, err = fetch_data(user_token, sd, ed)
            
            if err:
                st.error(err)
            elif data:
                # 1. 建立資料表
                df = pd.DataFrame(data)
                
                # 2. 基本清洗：僅統計 status=3 的正常單
                if 'status' in df.columns:
                    df = df[df['status'] == 3].copy()
                
                # 金額轉換
                if 'amount' in df.columns:
                    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
                else:
                    st.error("回傳資料中找不到 'amount' 欄位，請檢查 API")
                    st.stop()

                # 3. 計算各項指標
                # --- 累計業績 ---
                total_revenue = df['amount'].sum()
                
                # --- 當天業績 (以系統目前日期為準) ---
                today_str = datetime.now().strftime("%Y-%m-%d")
                # 確保 create_time 欄位存在再計算
                if 'create_time' in df.columns:
                    today_df = df[df['create_time'].str.contains(today_str, na=False)]
                    today_revenue = today_df['amount'].sum()
                else:
                    today_revenue = 0
                
                # 4. 頂部看板指標
                c1, c2, c3 = st.columns(3)
                c1.metric("今日實時業績", f"${today_revenue:,.0f}")
                c2.metric("所選區間累計營收", f"${total_revenue:,.0f}")
                c3.metric("總成交單數", f"{len(df)} 單")
                
                st.markdown("---")
                
                # 5. 公關排行 (安全檢查版)
                st.subheader("👤 公關業績排行榜")
                
                # 檢查是否有 desk 欄位 (有些系統叫 table 或其他名字)
                rank_col = 'desk' if 'desk' in df.columns else (df.columns[1] if len(df.columns) > 1 else None)
                
                if rank_col:
                    ranking = df.groupby(rank_col)['amount'].sum().sort_values(ascending=False).reset_index()
                    ranking.columns = ['公關/桌號', '累積業績']
                    ranking.index = ranking.index + 1 # 名次從 1 開始
                    st.table(ranking.style.format({"累積業績": "${:,.0f}"}))
                else:
                    st.warning("找不到對應的公關/桌號欄位。")

                # 6. 詳細明細 (防止 KeyError 的安全過濾版)
                with st.expander("📄 查看詳細帳單明細"):
                    # 定義想要顯示的理想欄位
                    wish_list = ['create_time', 'desk', 'amount', 'bill_no', 'order_no']
                    # 只選取「真的存在」的欄位
                    safe_cols = [c for c in wish_list if c in df.columns]
                    
                    if safe_cols:
                        st.dataframe(df[safe_cols], use_container_width=True)
                    else:
                        st.write("欄位名稱不符，顯示所有抓到的欄位：")
                        st.dataframe(df)
            else:
                st.info("該日期範圍內目前沒有數據。")

else:
    st.info("💡 操作教學：請從肚肚後台複製 Access-Token 貼到左側，然後按下「刷新數據數據」。")