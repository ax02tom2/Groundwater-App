import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="地下水位分析工具", page_icon="💧", layout="wide")
st.title("💧 地下水位升降與洩降速率分析工具")
st.write("請上傳 HOBO 水位紀錄器匯出的 CSV 檔案，設定時間區間，系統將自動計算水位變化並繪製歷線圖。")

@st.cache_data
def load_and_clean_data(file):
    df = pd.read_csv(file)
    time_col, water_col = df.columns[0], df.columns[1]
    
    # 清理 CSV 尾部可能出現的亂碼
    def clean_time(t):
        t = str(t)
        # 關鍵修復：先將代表時、分的亂碼直接替換為冒號，秒數亂碼則消除
        t = t.replace('®É', ':').replace('¤À', ':').replace('¬í', '')
        t = t.replace('時', ':').replace('分', ':').replace('秒', '')
        
        # 移除非時間相關字元
        cleaned = re.sub(r'[^\d/\-\: ]', ' ', t)
        return re.sub(r'\s+', ' ', cleaned).strip()

    df[time_col] = df[time_col].apply(clean_time)
    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    df[water_col] = pd.to_numeric(df[water_col], errors='coerce')
    
    # 移除空值並排序
    return df.dropna(subset=[time_col, water_col]).sort_values(by=time_col).reset_index(drop=True), time_col, water_col

st.sidebar.header("📁 1. 資料上傳")
uploaded_file = st.sidebar.file_uploader("上傳地下水位 CSV 檔", type=["csv"])

if uploaded_file:
    with st.spinner("正在解析與清理資料..."):
        df, time_col, water_col = load_and_clean_data(uploaded_file)
    
    # 增加安全防呆機制：若資料全數無法解析，停止執行並友善提示
    if df.empty:
        st.error("⚠️ 檔案中的日期或水位無法成功解析，請檢查 CSV 內容格式是否正確。")
        st.stop()
        
    min_date, max_date = df[time_col].min(), df[time_col].max()
    
    st.sidebar.markdown("---")
    st.sidebar.header("⏱️ 2. 分析區間設定")
    start_date = st.sidebar.date_input("開始日期", min_date.date(), min_value=min_date.date(), max_value=max_date.date())
    start_time = st.sidebar.time_input("開始時間", min_date.time())
    end_date = st.sidebar.date_input("結束日期", max_date.date(), min_value=min_date.date(), max_value=max_date.date())
    end_time = st.sidebar.time_input("結束時間", max_date.time())
    
    start_dt = pd.to_datetime(f"{start_date} {start_time}")
    end_dt = pd.to_datetime(f"{end_date} {end_time}")
    
    if start_dt >= end_dt:
        st.sidebar.error("開始時間必須早於結束時間！")
    else:
        df_filtered = df[(df[time_col] >= start_dt) & (df[time_col] <= end_dt)]
        
        if df_filtered.empty:
            st.warning("⚠️ 在您選擇的時間區間內找不到資料。")
        else:
            first_record, last_record = df_filtered.iloc[0], df_filtered.iloc[-1]
            level_start, level_end = first_record[water_col], last_record[water_col]
            level_diff = level_end - level_start
            time_diff_hours = (last_record[time_col] - first_record[time_col]).total_seconds() / 3600
            rate = level_diff / time_diff_hours if time_diff_hours > 0 else 0
            
            st.markdown("### 📊 分析結果指標")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("區間初始水位", f"{level_start:.3f}")
            col2.metric("區間結束水位", f"{level_end:.3f}")
            col3.metric("🔺 升降幅度" if level_diff > 0 else "🔻 洩降幅度", f"{level_diff:.3f}")
            col4.metric("平均速率 (每小時)", f"{rate:.4f}")

            st.markdown("### 📈 水位變化歷線圖")
            fig = px.line(df_filtered, x=time_col, y=water_col, template="plotly_white")
            fig.update_traces(line=dict(color="#1f77b4", width=2))
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("👈 請先由左側面板上傳 CSV 檔案。")
