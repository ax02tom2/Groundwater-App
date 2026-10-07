import re
import numpy as np
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(
    page_title="地下水位與降雨分析工具", page_icon="💧", layout="wide"
)
st.title("💧 地下水位升降與颱風降雨分析工具")
st.write(
    "支援 CSV 與 Excel 格式上傳，提供圖表「點擊頭尾」連動選取、動態水位速率換算與對數迴歸相關性分析。"
)

# 檢查 Streamlit 是否支援點擊選取事件 (v1.35.0+)
try:
    from packaging import version
    supports_selection = version.parse(st.__version__) >= version.parse("1.35.0")
except:
    parts = st.__version__.split(".")
    supports_selection = (int(parts[0]) > 1) or (int(parts[0]) == 1 and int(parts[1]) >= 35)


def load_file_flexible(uploaded_file):
  """強固型檔案讀取器：支援 CSV 與 Excel"""
  file_extension = uploaded_file.name.split(".")[-1].lower()
  
  if file_extension in ["xlsx", "xls"]:
    try:
      xls = pd.ExcelFile(uploaded_file)
      df_raw = pd.read_excel(uploaded_file, sheet_name=xls.sheet_names[0], header=None)
      
      best_col_idx = 0
      max_valid_dates = 0
      for col_idx in range(df_raw.shape[1]):
        parsed = pd.to_datetime(df_raw.iloc[:, col_idx], errors='coerce')
        valid_count = parsed.notna().sum()
        if valid_count > max_valid_dates:
          max_valid_dates = valid_count
          best_col_idx = col_idx
      
      header_row = 0
      for idx, row in df_raw.iterrows():
        if pd.notna(row.iloc[best_col_idx]) and (str(row.iloc[best_col_idx]).strip().lower() in ['time', '時間', '日期'] or pd.to_datetime(row.iloc[best_col_idx], errors='coerce') is not pd.NaT):
          if idx > 0 and pd.to_datetime(df_raw.iloc[idx-1, best_col_idx], errors='coerce') is pd.NaT:
            header_row = idx - 1
            break
          elif idx == 0:
            header_row = 0
            break

      df = pd.read_excel(uploaded_file, sheet_name=xls.sheet_names[0], header=header_row)
      if not any('time' in str(c).lower() or '時間' in str(c) or '日期' in str(c) for c in df.columns):
        if df.shape[1] > best_col_idx:
          df.columns = [f"欄位_{i}" if i != best_col_idx else "Time" for i in range(df.shape[1])]
    except ImportError:
      st.error("⚠️ 伺服器缺少 `openpyxl` 套件，無法解析 Excel 檔案。請在 `requirements.txt` 中加入 `openpyxl`！")
      return pd.DataFrame()
    except Exception as e:
      st.error(f"⚠️ 無法讀取 Excel 檔案：{e}")
      return pd.DataFrame()
  else:
    try:
      df = pd.read_csv(uploaded_file, encoding="utf-8")
    except UnicodeDecodeError:
      uploaded_file.seek(0)
      try:
        df = pd.read_csv(uploaded_file, encoding="big5")
      except UnicodeDecodeError:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, encoding="cp950", errors="ignore")

  new_cols = []
  for i, col in enumerate(df.columns):
      col_str = str(col).strip()
      if col_str.upper() == "R1":
          col_str = "R1 (日雨量)"
      if col_str in new_cols or col_str == "" or col_str.lower() == "nan" or "unnamed" in col_str.lower():
          new_cols.append(f"欄位_{i}")
      else:
          new_cols.append(col_str)
  df.columns = new_cols
  return df


# --- 側邊欄：資料上傳與彈性欄位對應 ---
st.sidebar.header("📁 1. 資料上傳與欄位對應")

if not supports_selection:
    st.sidebar.error("⚠️ 您的 Streamlit 版本過舊 (<1.35.0)，不支援圖表點擊功能。請在 `requirements.txt` 更新 `streamlit>=1.35.0`。")

uploaded_file = st.sidebar.file_uploader("上傳地下水位檔案 (支援 CSV / Excel)", type=["csv", "xlsx", "xls"])
uploaded_rain = st.sidebar.file_uploader("上傳降雨量檔案 (支援 CSV / Excel)", type=["csv", "xlsx", "xls"])

water_df = pd.DataFrame()
rain_df = pd.DataFrame()
time_col, water_col = None, None
r_time_col, selected_rain_cols = None, []

# 1. 處理水位資料
if uploaded_file:
  with st.spinner("正在解析水位檔案..."):
    water_df = load_file_flexible(uploaded_file)

  if not water_df.empty:
    st.sidebar.success("✔️ 水位檔案載入成功")
    all_cols = list(water_df.columns)
    
    default_time_idx = 0
    default_water_idx = min(1, len(all_cols) - 1)
    for i, c in enumerate(all_cols):
      if 'time' in c.lower() or '時間' in c or '日期' in c:
        default_time_idx = i
      elif '水位' in c or 'val' in c.lower() or 'r' in c.lower():
        default_water_idx = i

    time_col = st.sidebar.selectbox("【水位檔】指定時間欄位", all_cols, index=default_time_idx)
    water_col = st.sidebar.selectbox("【水位檔】指定水位數值欄位", all_cols, index=default_water_idx)

    def clean_time(t):
      t = str(t)
      if any(w in t for w in ["降雨量", "地下水位", "下田埔", "秀巒", "nan", "None"]):
          return None
      t = t.replace("®É", ":").replace("¤À", ":").replace("¬í", "")
      t = t.replace("時", ":").replace("分", ":").replace("秒", "")
      cleaned = re.sub(r"[^\d/\-\: ]", " ", t)
      return re.sub(r"\s+", " ", cleaned).strip()

    water_df[time_col] = water_df[time_col].apply(clean_time)
    water_df[time_col] = pd.to_datetime(water_df[time_col], errors="coerce", format="mixed")
    water_df[water_col] = pd.to_numeric(water_df[water_col], errors="coerce")
    
    water_df = (
        water_df.dropna(subset=[time_col, water_col])
        .drop_duplicates(subset=[time_col])
        .sort_values(by=time_col)
        .reset_index(drop=True)
    )

# 2. 處理降雨資料
if uploaded_rain:
  with st.spinner("正在解析降雨檔案..."):
    rain_df = load_file_flexible(uploaded_rain)

  if not rain_df.empty:
    st.sidebar.success("✔️ 降雨檔案載入成功")
    r_all_cols = list(rain_df.columns)
    
    default_r_time_idx = 0
    for i, c in enumerate(r_all_cols):
      if 'time' in c.lower() or '時間' in c or '日期' in c:
        default_r_time_idx = i
        break

    r_time_col = st.sidebar.selectbox("【降雨檔】指定時間欄位", r_all_cols, index=default_r_time_idx)
    selected_rain_cols = st.sidebar.multiselect("【降雨檔】選擇要分析的雨量欄位 (可複選)", r_all_cols, default=[])

    def clean_rain_time(t):
      t = str(t)
      if any(w in t for w in ["降雨量", "地下水位", "下田埔", "秀巒", "nan", "None", "Time"]):
          return None
      t = t.replace("®É", ":").replace("¤À", ":").replace("¬í", "")
      t = t.replace("時", ":").replace("分", ":").replace("秒", "")
      cleaned = re.sub(r"[^\d/\-\: ]", " ", t)
      return re.sub(r"\s+", " ", cleaned).strip()

    rain_df[r_time_col] = rain_df[r_time_col].apply(clean_rain_time)
    rain_df[r_time_col] = pd.to_datetime(rain_df[r_time_col], errors="coerce", format="mixed")

    for col in selected_rain_cols:
      rain_df[col] = pd.to_numeric(rain_df[col], errors="coerce")

    rain_df = (
        rain_df.dropna(subset=[r_time_col])
        .drop_duplicates(subset=[r_time_col])
        .sort_values(by=r_time_col)
        .reset_index(drop=True)
    )


# --- 狀態記憶：圖表點擊頭尾機制 ---
if "click_points" not in st.session_state:
    st.session_state.click_points = []


# --- 主畫面邏輯 ---
if not water_df.empty and time_col and water_col:
  max_idx = water_df[water_col].idxmax()
  min_idx = water_df[water_col].idxmin()
  max_time, max_val = water_df.loc[max_idx, time_col], water_df.loc[max_idx, water_col]
  min_time, min_val = water_df.loc[min_idx, time_col], water_df.loc[min_idx, water_col]

  st.info(
      f"🏆 **全期歷史極值紀錄**：\n"
      f"- **最高水位**：{max_val:.2f} m (發生於 {max_time.strftime('%Y-%m-%d %H:%M')})\n"
      f"- **最低水位**：{min_val:.2f} m (發生於 {min_time.strftime('%Y-%m-%d %H:%M')})"
  )

  min_date, max_date = water_df[time_col].min(), water_df[time_col].max()
  if not rain_df.empty and r_time_col and len(selected_rain_cols) > 0:
    min_date = min(min_date, rain_df[r_time_col].min())
    max_date = max(max_date, rain_df[r_time_col].max())

  suggested_start = min_date
  suggested_end = max_date

  # 【強固捕捉點擊事件】解析 Streamlit 1.35+ 回傳的 selection 物件
  pts = []
  water_chart_state = st.session_state.get("water_chart")
  if water_chart_state:
      if hasattr(water_chart_state, "selection"):
          pts = getattr(water_chart_state.selection, "points", [])
      elif isinstance(water_chart_state, dict):
          pts = water_chart_state.get("selection", {}).get("points", [])

  if pts and len(pts) > 0:
      raw_x = pts[0].get("x")
      if raw_x:
          clicked_x = pd.to_datetime(raw_x).tz_localize(None)
          # 如果滿了兩點，就重新覆蓋為第 1 點
          if len(st.session_state.click_points) >= 2:
              st.session_state.click_points = [clicked_x]
          # 否則只要點擊的不是同一個點就加入
          elif len(st.session_state.click_points) == 0 or clicked_x != st.session_state.click_points[-1]:
              st.session_state.click_points.append(clicked_x)

  # 根據收集到的點數，動態決定 suggested_start 與 suggested_end
  points_selected = len(st.session_state.click_points)
  if points_selected == 1:
      suggested_start = st.session_state.click_points[0]
      suggested_end = st.session_state.click_points[0]
  elif points_selected == 2:
      suggested_start = min(st.session_state.click_points)
      suggested_end = max(st.session_state.click_points)

  def clamp_date(d, min_d, max_d):
      return max(min_d, min(d, max_d))
  
  safe_start_date = clamp_date(suggested_start.date(), min_date.date(), max_date.date())
  safe_end_date = clamp_date(suggested_end.date(), min_date.date(), max_date.date())

  st.sidebar.markdown("---")
  st.sidebar.header("⏱️ 2. 颱風/事件區間設定")
  
  # 點擊狀態提示與清除按鈕
  if points_selected == 1:
      st.sidebar.warning("👆 已點擊第 1 個時間點，請在右側圖表上**點擊第 2 個點**作為結束。")
  elif points_selected == 2:
      st.sidebar.success("🎯 **已成功鎖定圖表點擊區間！**")
  
  if points_selected > 0:
      if st.sidebar.button("🧹 清除點擊選取"):
          st.session_state.click_points = []
          st.rerun()

  start_date = st.sidebar.date_input("開始日期", safe_start_date, min_value=min_date.date(), max_value=max_date.date())
  start_time = st.sidebar.time_input("開始時間", suggested_start.time())
  end_date = st.sidebar.date_input("結束日期", safe_end_date, min_value=min_date.date(), max_value=max_date.date())
  end_time = st.sidebar.time_input("結束時間", suggested_end.time())
      
  start_dt = pd.to_datetime(f"{start_date} {start_time}")
  end_dt = pd.to_datetime(f"{end_date} {end_time}")

  st.sidebar.markdown("---")
  st.sidebar.header("📌 3. 颱風事件標註設定")
  if "events_df" not in st.session_state:
    st.session_state.events_df = pd.DataFrame({
        "事件名稱": ["凱米颱風", "康芮颱風"],
        "事件日期": ["2024-07-24", "2024-10-31"],
    })

  edited_events_df = st.sidebar.data_editor(
      st.session_state.events_df,
      num_rows="dynamic",
      key="event_editor_sidebar",
  )
  st.session_state.events_df = edited_events_df

  custom_events = []
  for _, row in edited_events_df.iterrows():
    ev_name = str(row["事件名稱"]).strip()
    ev_date_str = str(row["事件日期"]).strip()
    if ev_name and ev_name != "nan":
      try:
        ev_dt = pd.to_datetime(ev_date_str)
        custom_events.append((ev_name, ev_dt))
      except:
        pass

  st.sidebar.markdown("---")
  st.sidebar.header("⚙️ 4. 圖表縱軸 (Y 軸) 範圍設定")
  use_manual_y = st.sidebar.checkbox("手動固定【水位】縱軸數值", value=False)
  manual_
