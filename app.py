import streamlit as st
import pandas as pd
from datetime import datetime
from curl_cffi import requests as crequests

st.set_page_config(page_title="CUBE LOUNGE 旗艦看板", layout="wide")

def get_ultra_token():
    """終極破解：Session 追蹤 + 指紋偽裝"""
    # 這是入口大門
    login_url = "https://pos-api.dudooeat.com/users/login"
    # 這是換票櫃檯
    report_url = "https://pos-api.dudooeat.com/reports/login?type=reports"
    
    payload = {
        "code": st.secrets["DUDOO_CODE"],
        "username": st.secrets["DUDOO_USER"],
        "password": st.secrets["DUDOO_PASS"]
    }
    
    headers = {
        "Origin": "https://admin.dudooeat.com",
        "Referer": "https://admin.dudooeat.com/",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # 1. 建立一個 Session 物件，它會自動幫我們收好 Cookie
        session = crequests.Session()
        
        # 2. 第一次衝刺：主系統登入
        # impersonate="chrome120" 繞過 TLS 檢測
        res1 = session.post(login_url, data=payload, headers=headers, impersonate="chrome120", timeout=15)
        
        if res1.status_code != 200 or not res1.json().get('success'):
            err = res1.json().get('error', {}).get('message', '未知錯誤')
            return None, f"第一階段失敗: {err}"
        
        # 拿到第一張臨時票
        base_token = res1.json().get('data', {}).get('access_token')
        
        # 3. 關鍵動作：帶著臨時票和 Session(Cookie) 去換報表票
        # 這是你之前失敗的地方，現在我們帶著 Cookie 過去
        headers["Access-Token"] = base_token
        res2 = session.post(report_url, data=payload, headers=headers, impersonate="chrome120", timeout=15)
        
        if res2.status_code == 200:
            final_token = res2.json().get('data', {}).get('access_token')
            if final_token:
                return final_token, None
        
        # 如果二階段沒給，就賭賭看一階段的能不能用
        return base_token, "⚠️ 使用基礎授權（報表授權換領失敗）"

    except Exception as e:
        return None, f"系統崩潰: {str(e)}"

# --- 主程式介面 ---
st.title("🚀 CUBE LOUNGE 全自動運作中")

# 進入網頁就自動嘗試授權
if "token" not in st.session_state or st.session_state.token is None:
    with st.spinner("正在執行全自動安全破防..."):
        t, err = get_ultra_token()
        if not err or "⚠️" in str(err):
            st.session_state.token = t
            st.toast("✅ 全自動授權成功！")
        else:
            st.error(f"全自動登入卡關：{err}")

# ... (其餘 fetch_data 和排行統計代碼保持不變)