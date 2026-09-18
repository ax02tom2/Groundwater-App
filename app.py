import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re

st.set_page_config(page_title="地下水位與降雨分析工具", page_icon="💧", layout="wide")
st.title("💧 地下水位升降與颱風降雨分析工具")
st.write("上傳水位紀錄器資料，並可選配「降雨量」資料進行疊圖，輕鬆分析颱風事件的洩降與補注反應。")

@st.cache_data
def load_and_clean_data(file):
    # 智慧判斷檔案編碼 (UTF-8 失敗時自動轉為 Big5)
    try:
        df = pd.read_csv(file, encoding='utf-8')
    except UnicodeDecodeError:
        file.seek(0)
        try:
            df = pd.read_csv(file, encoding='big5')
        except UnicodeDecodeError:
            file.seek(0)
            df = pd.read_csv(file, encoding='cp950', errors='ignore')

    time_col, val_col = df.columns[0], df.columns[1]
    
    def clean_time(t):
        t = str(t)
        # 完整對應各類亂碼與中文時間字元
        t = t.replace('®É', ':').replace('¤À', ':').replace('¬í', '')
        t = t.replace('時', ':').replace('分', ':').replace('秒', '')
        cleaned = re.sub(r'[^\d/\-\: ]', ' ', t)
        return re.sub(r'\s+', ' ', cleaned).strip()

    df[time_col] = df[time_col].apply(clean_time)
    # 升級時間解析，支援混合格式與中文時間轉譯
    df[time_col] = pd.to_datetime(df[time_col], errors='coerce', format='mixed')
    df[val_col] = pd.to_numeric(df[val_col], errors='coerce')
    
    return df.dropna(subset=[time_col, val_col]).sort_values(by=time_col).reset_index(drop=True), time_col, val_col

# --- 側邊欄：資料上傳 ---
st.sidebar.header("📁 1. 資料上傳")
uploaded_file = st.sidebar.file_uploader("上傳地下水位 CSV 檔 (必填)", type=["csv"])
uploaded_rain = st.sidebar.file_uploader("上傳降雨量 CSV 檔 (選配)", type=["csv"], help="請確保第一欄為時間，第二欄為降雨量")

if uploaded_file:
    with st.spinner("正在解析水位資料..."):
        df, time_col, water_col = load_and_clean_data(uploaded_file)
    
    if df.empty:
        st.error("⚠️ 水位檔案中的日期或數值無法解析，請檢查 CSV 格式。")
        st.stop()
        
    # 計算全期歷史極值
    max_idx = df[water_col].idxmax()
    min_idx = df[water_col].idxmin()
    max_time, max_val = df.loc[max_idx, time_col], df.loc[max_idx, water_col]
    min_time, min_val = df.loc[min_idx, time_col], df.loc[min_idx, water_col]
    
    st.info(f"🏆 **全期歷史極值紀錄**：\n"
            f"- **最高水位**：{max_val:.3f} (發生於 {max_time.strftime('%Y-%m-%d %H:%M')})\n"
            f"- **最低水位**：{min_val:.3f} (發生於 {min_time.strftime('%Y-%m-%d %H:%M')})")
        
    min_date, max_date = df[time_col].min(), df[time_col].max()
    
    df_rain = None
    if uploaded_rain:
        with st.spinner("正在解析降雨資料..."):
            df_rain, r_time_col, r_val_col = load_and_clean_data(uploaded_rain)
            if not df_rain.empty:
                min_date = min(min_date, df_rain[r_time_col].min())
                max_date = max(max_date, df_rain[r_time_col].max())

    st.sidebar.markdown("---")
    st.sidebar.header("⏱️ 2. 颱風/事件區間設定")
    st.sidebar.write("請設定您想觀察的事件時間範圍：")
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
            st.warning("⚠️ 在您選擇的時間區間內找不到水位資料，請重新調整篩選範圍。")
        else:
            first_record, last_record = df_filtered.iloc[0], df_filtered.iloc[-1]
            level_start, level_end = first_record[water_col], last_record[water_col]
            level_diff = level_end - level_start
            time_diff_hours = (last_record[time_col] - first_record[time_col]).total_seconds() / 3600
            rate = level_diff / time_diff_hours if time_diff_hours > 0 else 0
            
            st.markdown("### 📊 事件區間計算結果")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("事件初始水位", f"{level_start:.3f}")
            col2.metric("事件結束水位", f"{level_end:.3f}")
            col3.metric("🔺 補注幅度" if level_diff > 0 else "🔻 洩降幅度", f"{level_diff:.3f}")
            col4.metric("平均速率 (每小時)", f"{rate:.4f}")

            st.markdown("### 📈 水位與降雨事件歷線圖")
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(
                go.Scatter(x=df_filtered[time_col], y=df_filtered[water_col], 
                           mode='lines', name="地下水位", line=dict(color="#1f77b4", width=2)),
                secondary_y=False
            )
            
            if df_rain is not None and not df_rain.empty:
                df_rain_filtered = df_rain[(df_rain[r_time_col] >= start_dt) & (df_rain[r_time_col] <= end_dt)]
                if not df_rain_filtered.empty:
                    fig.add_trace(
                        go.Bar(x=df_rain_filtered[r_time_col], y=df_rain_filtered[r_val_col], 
                               name="降雨量", marker_color="rgba(0, 191, 255, 0.5)"),
                        secondary_y=True
                    )
            
            fig.update_layout(
                template="plotly_white", 
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig.update_yaxes(title_text="水位 (m)", secondary_y=False)
            fig.update_yaxes(title_text="降雨量 (mm)", autorange="reversed", showgrid=False, secondary_y=True)
            
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("👈 請先由左側面板上傳 CSV 檔案。")
