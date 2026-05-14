import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- 頁面設定 ---
st.set_page_config(page_title="CUBE LOUNGE 終極看板", layout="wide")

def get_auto_token():
    """模擬完整登入流程"""
    # 嘗試報表專用登入入口
    login_url = "https://pos-api.dudooeat.com/reports/login?type=reports"
    payload = {
        "code": st.secrets["DUDOO_CODE"],
        "username": st.secrets["DUDOO_USER"],
        "password": st.secrets["DUDOO_PASS"]
    }
    
    try:
        # 使用 Session 並模擬瀏覽器 Header
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
            "Origin": "https://admin.dudooeat.com",
            "Referer": "https://admin.dudooeat.com/"
        }
        res = session.post(login_url, data=payload, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            token = data.get('data', {}).get('access_token') or data.get('access_token')
            if token:
                return token, None
        return None, "登入成功但找不到通行證，請確認 Secrets 中的店號/帳密是否完全正確。"
    except Exception as e:
        return None, f"連線失敗: {str(e)}"

def fetch_data(token, start_date, end_date):
    """根據截圖提供的精準參數抓取資料"""
    url = "https://pos-api.dudooeat.com/reports/getBillInvoicesList?type=reports"
    headers = {
        "Access-Token": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    # 完全模擬你截圖中的 Payload
    payload = {
        "draw": "1",
        "start": "0",
        "length": "5000", # 加大長度一次抓完
        "hierarchy_id": "17939",
        "company_id": "13223",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "time_filter": "bill_create_time"
    }
    
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=15)
        if res.status_code != 200:
            return None, "連線報表伺服器失敗。"
        
        raw_data = res.json().get('data', [])
        if not raw_data:
            return None, "此日期範圍內沒有帳單資料。"

        # 處理業績邏輯
        pr_stats = {}
        total_rev = 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 營業日判定 (凌晨5點)
        def is_today(time_str):
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            biz_now = datetime.now()
            if biz_now.hour < 5: biz_now -= timedelta(days=1)
            target_date = dt
            if dt.hour < 5: target_date -= timedelta(days=1)
            return biz_now.date() == target_date.date()

        for bill in raw_data:
            # 狀態 3 通常是已完成/正常帳單
            if bill.get('status') != 3: continue
            
            val = float(bill.get('amount', 0))
            total_rev += val
            
            # 抓取桌號/公關名稱
            name = bill.get('desk') or "其他"
            if name not in pr_stats: pr_stats[name] = {"today": 0, "month": 0}
            
            pr_stats[name]["month"] += val
            if is_today(bill.get('create_time', now_str)):
                pr_stats[name]["today"] += val
                
        return {"total": total_rev, "pr": pr_stats}, None
    except Exception as e:
        return None, f"處理資料時出錯: {str(e)}"

# --- 介面 ---
st.title("📊 CUBE LOUNGE 營運報表系統")

if "token" not in st.session_state: st.session_state.token = None

with st.sidebar:
    st.header("🔑 系統登入")
    if st.button("🔄 重新取得授權", width='stretch'):
        t, err = get_auto_token()
        if err: st.error(err)
        else:
            st.session_state.token = t
            st.success("授權成功！")
    
    st.markdown("---")
    sd = st.date_input("開始日期", datetime.now().replace(day=1))
    ed = st.date_input("結束日期", datetime.now())
    btn = st.button("🚀 更新報表", width='stretch')

if btn:
    if not st.session_state.token:
        t, err = get_auto_token()
        if not err: st.session_state.token = t
    
    if st.session_state.token:
        with st.spinner("讀取中..."):
            res, err = fetch_data(st.session_state.token, sd, ed)
            if err: st.error(err)
            else:
                c1, c2 = st.columns(2)
                c1.metric("範圍實收總計", f"${res['total']:,}")
                today_sum = sum(v['today'] for v in res['pr'].values())
                c2.metric("今日預估業績", f"${today_sum:,}")
                
                st.subheader("👤 各桌/公關 業績排行")
                df = pd.DataFrame([{"對象": k, "今日": v["today"], "本月累積": v["month"]} for k, v in res["pr"].items()])
                if not df.empty:
                    df = df.sort_values("本月累積", ascending=False)
                    st.dataframe(df.style.format({"今日": "${:,}", "本月累積": "${:,}"}), width='stretch', hide_index=True)
    else:
        st.warning("請先完成授權。")