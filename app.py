import re
import numpy as np
import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(
    page_title="地下水位與降雨分析工具", page_icon="💧", layout="wide"
)
st.title("💧 地下水位升降與颱風降雨分析工具")
st.write(
    "支援 CSV 與 Excel 格式上傳，提供圖表「框選」連動時間、動態水位速率換算與對數迴歸相關性分析。"
)

# 檢查 Streamlit 是否支援圖表選取事件 (v1.35.0+)
try:
    from packaging import version
    supports_selection = version.parse(st.__version__) >= version.parse("1.35.0")
except:
    parts = st.__version__.split(".")
    supports_selection = (int(parts[0]) > 1) or (int(parts[0]) == 1 and int(parts[1]) >= 35)


def load_file_flexible(uploaded_file):
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


st.sidebar.header("📁 1. 資料上傳與欄位對應")

if not supports_selection:
    st.sidebar.error("⚠️ 您的 Streamlit 版本過舊 (<1.35.0)，不支援圖表框選功能。請更新環境中的 `streamlit` 套件。")

uploaded_file = st.sidebar.file_uploader("上傳地下水位檔案 (支援 CSV / Excel)", type=["csv", "xlsx", "xls"])
uploaded_rain = st.sidebar.file_uploader("上傳降雨量檔案 (支援 CSV / Excel)", type=["csv", "xlsx", "xls"])

water_df = pd.DataFrame()
rain_df = pd.DataFrame()
time_col, water_col = None, None
r_time_col, selected_rain_cols = None, []

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

    r_time_col = st.sidebar.selectbox("【降雨檔】指定
