import re
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
    "上傳水位與降雨資料，支援大數據降採樣流暢顯示、動態選取雨量欄位、表格化事件標註與雙"
    " Y 軸範圍固定功能。"
)


@st.cache_data
def load_and_clean_water(file):
  try:
    df = pd.read_csv(file, encoding="utf-8")
  except UnicodeDecodeError:
    file.seek(0)
    try:
      df = pd.read_csv(file, encoding="big5")
    except UnicodeDecodeError:
      file.seek(0)
      df = pd.read_csv(file, encoding="cp950", errors="ignore")

  time_col, val_col = df.columns[0], df.columns[1]

  def clean_time(t):
    t = str(t)
    t = t.replace("®É", ":").replace("¤À", ":").replace("¬í", "")
    t = t.replace("時", ":").replace("分", ":").replace("秒", "")
    cleaned = re.sub(r"[^\d/\-\: ]", " ", t)
    return re.sub(r"\s+", " ", cleaned).strip()

  df[time_col] = df[time_col].apply(clean_time)
  df[time_col] = pd.to_datetime(df[time_col], errors="coerce", format="mixed")
  df[val_col] = pd.to_numeric(df[val_col], errors="coerce")

  return (
      df.dropna(subset=[time_col, val_col])
      .drop_duplicates(subset=[time_col])
      .sort_values(by=time_col)
      .reset_index(drop=True),
      time_col,
      val_col,
  )


@st.cache_data
def load_and_clean_rain(file):
  try:
    df = pd.read_csv(file, encoding="utf-8")
  except UnicodeDecodeError:
    file.seek(0)
    try:
      df = pd.read_csv(file, encoding="big5")
    except UnicodeDecodeError:
      file.seek(0)
      df = pd.read_csv(file, encoding="cp950", errors="ignore")

  time_col = df.columns[0]

  def clean_time(t):
    t = str(t)
    t = t.replace("®É", ":").replace("¤À", ":").replace("¬í", "")
    t = t.replace("時", ":").replace("分", ":").replace("秒", "")
    cleaned = re.sub(r"[^\d/\-\: ]", " ", t)
    return re.sub(r"\s+", " ", cleaned).strip()

  df[time_col] = df[time_col].apply(clean_time)
  df[time_col] = pd.to_datetime(df[time_col], errors="coerce", format="mixed")

  rain_cols = list(df.columns[1:])
  for col in rain_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

  return (
      df.dropna(subset=[time_col])
      .drop_duplicates(subset=[time_col])
      .sort_values(by=time_col)
      .reset_index(drop=True),
      time_col,
      rain_cols,
  )


# --- 側邊欄：資料上傳 ---
st.sidebar.header("📁 1. 資料上傳")
uploaded_file = st.sidebar.file_uploader(
    "上傳地下水位 CSV 檔 (必填)", type=["csv"]
)
uploaded_rain = st.sidebar.file_uploader(
    "上傳降雨量 CSV 檔 (選配)",
    type=["csv"],
    help="請確保第一欄為時間，後續欄位為各項雨量數據",
)

if uploaded_file:
  with st.spinner("正在解析水位資料..."):
    df, time_col, water_col = load_and_clean_water(uploaded_file)

  if df.empty:
    st.error("⚠️ 水位檔案中的日期或數值無法解析，請檢查 CSV 格式。")
    st.stop()

  max_idx = df[water_col].idxmax()
  min_idx = df[water_col].idxmin()
  max_time, max_val = df.loc[max_idx, time_col], df.loc[max_idx, water_col]
  min_time, min_val = df.loc[min_idx, time_col], df.loc[min_idx, water_col]

  st.info(
      f"🏆 **全期歷史極值紀錄**：\n"
      f"- **最高水位**：{max_val:.3f} (發生於"
      f" {max_time.strftime('%Y-%m-%d %H:%M')})\n"
      f"- **最低水位**：{min_val:.3f} (發生於"
      f" {min_time.strftime('%Y-%m-%d %H:%M')})"
  )

  min_date, max_date = df[time_col].min(), df[time_col].max()

  df_rain = None
  r_time_col = None
  r_val_cols = []
  selected_rain_col = None

  if uploaded_rain:
    with st.spinner("正在解析降雨資料..."):
      df_rain, r_time_col, r_val_cols = load_and_clean_rain(uploaded_rain)
      if not df_rain.empty:
        min_date = min(min_date, df_rain[r_time_col].min())
        max_date = max(max_date, df_rain[r_time_col].max())

  # --- 效能優化：大數據降採樣設定 ---
  st.sidebar.markdown("---")
  st.sidebar.header("⚡ 2. 效能與圖表優化")
  total_rows = len(df)
  enable_downsample = False
  resample_freq = "1H"

  if total_rows > 5000:
    st.sidebar.warning(
        f"⚠️ 偵測到水位資料筆數較多 ({total_rows:,} 筆)，建議啟用降採樣以保持流暢。"
    )
    enable_downsample = st.sidebar.checkbox(
        "啟用資料降採樣（加速繪圖）", value=True
    )
  else:
    enable_downsample = st.sidebar.checkbox(
        "啟用資料降採樣（平均取樣）", value=False
    )

  if enable_downsample:
    freq_option = st.sidebar.selectbox(
        "降採樣頻率", ["15分鐘 (15T)", "1小時 (1H)", "6小時 (6H)", "每日 (1D)"], index=1
    )
    freq_map = {
        "15分鐘 (15T)": "15min",
        "1小時 (1H)": "H",
        "6小時 (6H)": "6H",
        "每日 (1D)": "D",
    }
    resample_freq = freq_map[freq_option]

  st.sidebar.markdown("---")
  st.sidebar.header("⏱️ 3. 颱風/事件區間設定")
  start_date = st.sidebar.date_input(
      "開始日期",
      min_date.date(),
      min_value=min_date.date(),
      max_value=max_date.date(),
  )
  start_time = st.sidebar.time_input("開始時間", min_date.time())
  end_date = st.sidebar.date_input(
      "結束日期",
      max_date.date(),
      min_value=min_date.date(),
      max_value=max_date.date(),
  )
  end_time = st.sidebar.time_input("結束時間", max_date.time())

  start_dt = pd.to_datetime(f"{start_date} {start_time}")
  end_dt = pd.to_datetime(f"{end_date} {end_time}")

  # 4. 颱風事件標註設定
  st.sidebar.markdown("---")
  st.sidebar.header("📌 4. 颱風事件標註設定")
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

  # 雨量欄位選擇
  if df_rain is not None and not df_rain.empty and r_val_cols:
    st.sidebar.markdown("---")
    st.sidebar.header("🌧️ 5. 降雨欄位對應選擇")
    default_idx = 0
    for name_pref in ["1小時", "降雨量", "rain", "Rain"]:
      if name_pref in r_val_cols:
        default_idx = r_val_cols.index(name_pref)
        break
    selected_rain_col = st.sidebar.selectbox(
        "選擇要分析的雨量欄位", r_val_cols, index=default_idx
    )

  # --- 縱軸範圍設定 ---
  st.sidebar.markdown("---")
  st.sidebar.header("⚙️ 6. 圖表縱軸 (Y 軸) 範圍設定")

  use_manual_y = st.sidebar.checkbox("手動固定【水位】縱軸數值", value=False)
  manual_y_min, manual_y_max = 0.0, 0.0
  if use_manual_y:
    suggest_min = float(df[water_col].min() - 1)
    suggest_max = float(df[water_col].max() + 1)
    manual_y_min = st.sidebar.number_input(
        "水位最小值 (Y min)", value=suggest_min, format="%.3f"
    )
    manual_y_max = st.sidebar.number_input(
        "水位最大值 (Y max)", value=suggest_max, format="%.3f"
    )

  use_manual_rain_y = False
  manual_rain_max = 500.0
  if (
      df_rain is not None
      and not df_rain.empty
      and selected_rain_col is not None
  ):
    use_manual_rain_y = st.sidebar.checkbox(
        f"手動固定【{selected_rain_col}】縱軸數值", value=False
    )
    if use_manual_rain_y:
      max_val_series = df_rain[selected_rain_col]
      suggest_rain_max = (
          float(max_val_series.max() * 1.2)
          if not max_val_series.empty
          and not pd.isna(max_val_series.max())
          else 500.0
      )
      manual_rain_max = st.sidebar.number_input(
          "雨量最大值 (Rain Y max)", value=suggest_rain_max, format="%.1f"
      )

  if start_dt >= end_dt:
    st.sidebar.error("開始時間必須早於結束時間！")
  else:
    # 進行資料區間篩選
    df_filtered = df[
        (df[time_col] >= start_dt) & (df[time_col] <= end_dt)
    ].copy()

    # 套用降採樣以優化效能
    if enable_downsample and not df_filtered.empty:
      df_filtered.set_index(time_col, inplace=True)
      df_filtered = (
          df_filtered.resample(resample_freq)
          .mean()
          .reset_index()
          .dropna(subset=[water_col])
      )

    if df_filtered.empty:
      st.warning(
          "⚠️ 在您選擇的時間區間內找不到水位資料，請重新調整篩選範圍。"
      )
    else:
      first_record, last_record = df_filtered.iloc[0], df_filtered.iloc[-1]
      level_start, level_end = first_record[water_col], last_record[water_col]
      level_diff = level_end - level_start

      time_diff_days = (
          last_record[time_col] - first_record[time_col]
      ).total_seconds() / (24 * 3600)
      rate = level_diff / time_diff_days if time_diff_days > 0 else 0

      st.markdown("### 📊 事件區間計算結果")
      col1, col2, col3, col4 = st.columns(4)
      col1.metric("事件初始水位", f"{level_start:.3f}")
      col2.metric("事件結束水位", f"{level_end:.3f}")
      col3.metric(
          "🔺 水位上升幅度" if level_diff > 0 else "🔻 洩降幅度",
          f"{level_diff:.3f}",
      )
      col4.metric("平均速率 (m/day)", f"{rate:.4f}")

      st.markdown("### 📈 水位與降雨事件歷線圖")

      has_rain = (
          df_rain is not None and not df_rain.empty and selected_rain_col
      )
      rows_count = 2 if has_rain else 1

      fig = make_subplots(
          rows=rows_count,
          cols=1,
          shared_xaxes=True,
          vertical_spacing=0.1,
          row_heights=[0.7, 0.3] if has_rain else [1.0],
      )

      # 建立安全且快速的雨量對照
      rain_hover_vals = []
      if has_rain:
        rain_dict = dict(zip(df_rain[r_time_col], df_rain[selected_rain_col]))
        for t in df_filtered[time_col]:
          match_val = rain_dict.get(t, 0.0)
          rain_hover_vals.append(
              match_val if pd.notna(match_val) else 0.0
          )
      else:
        rain_hover_vals = [0.0] * len(df_filtered)

      # 上圖：地下水位折線圖（回復使用原本的 datetime 格式 x 軸）
      fig.add_trace(
          go.Scatter(
              x=df_filtered[time_col],
              y=df_filtered[water_col],
              mode="lines",
              name="地下水位"
              + (" (已降採樣)" if enable_downsample else ""),
              line=dict(color="#1f77b4", width=2),
              customdata=rain_hover_vals,
              hovertemplate=(
                  f"水位: %{{y:.3f}} m<br>{selected_rain_col}:"
                  " %{customdata:.1f} mm<extra></extra>"
                  if has_rain
                  else "水位: %{y:.3f} m<extra></extra>"
              ),
          ),
          row=1,
          col=1,
      )

      # 下圖：降雨量長條圖
      if has_rain:
        df_rain_filtered = df_rain[
            (df_rain[r_time_col] >= start_dt)
            & (df_rain[r_time_col] <= end_dt)
        ].copy()
        if not df_rain_filtered.empty:
          fig.add_trace(
              go.Bar(
                  x=df_rain_filtered[r_time_col],
                  y=df_rain_filtered[selected_rain_col],
                  name=selected_rain_col,
                  marker_color="#0044cc",
                  hovertemplate=(
                      f"{selected_rain_col}: %{{y:.1f}} mm<extra></extra>"
                  ),
              ),
              row=2,
              col=1,
          )
          if use_manual_rain_y:
            fig.update_yaxes(
                title_text=f"{selected_rain_col} (mm)",
                range=[0, manual_rain_max],
                row=2,
                col=1,
            )
          else:
            fig.update_yaxes(
                title_text=f"{selected_rain_col} (mm)",
                autorange=True,
                row=2,
                col=1,
            )

      # 自動計算並在圖面上標註事件數值
      for ev_name, ev_dt in custom_events:
        if start_dt <= ev_dt <= end_dt:
          water_val_str = "N/A"
          if not df.empty:
            closest_w_idx = (df[time_col] - ev_dt).abs().idxmin()
            water_val_str = f"{df.loc[closest_w_idx, water_col]:.3f} m"

          rain_val_str = "N/A"
          if has_rain and not df_rain.empty:
            closest_r_idx = (df_rain[r_time_col] - ev_dt).abs().idxmin()
            r_val = df_rain.loc[closest_r_idx, selected_rain_col]
            if pd.notna(r_val):
              rain_val_str = f"{r_val:.1f} mm"

          label_text = (
              f"<b>{ev_name}</b><br>水位: {water_val_str}<br>雨量:"
              f" {rain_val_str}"
          )

          fig.add_vline(
              x=ev_dt,
              line_width=1.5,
              line_dash="dash",
              line_color="red",
              row="all",
              col=1,
          )
          fig.add_annotation(
              x=ev_dt,
              y=1.0,
              yref="paper",
              text=label_text,
              showarrow=False,
              textangle=-90,
              font=dict(size=11, color="red"),
              xanchor="left",
              yanchor="top",
          )

      # 這裡是最關鍵的修正！利用 hoverformat 控制左上角標題的數字格式
      fig.update_xaxes(hoverformat="%Y-%m-%d %H:%M")

      fig.update_layout(
          template="plotly_white",
          hovermode="x unified",
          height=650 if has_rain else 450,
          legend=dict(
              orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
          ),
      )

      if use_manual_y:
        fig.update_yaxes(
            title_text="水位 (m)",
            range=[manual_y_min, manual_y_max],
            row=1,
            col=1,
        )
      else:
        fig.update_yaxes(title_text="水位 (m)", autorange=True, row=1, col=1)

      st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
else:
  st.info("👈 請先由左側面板上傳 CSV 檔案。")
