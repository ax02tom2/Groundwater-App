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
    "上傳水位與降雨資料，支援多時段雨量疊加比較、動態速率換算、雙"
    " Y 軸範圍固定功能，以及針對「突出事件」的對數迴歸分析。"
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

  new_cols = []
  for i, col in enumerate(df.columns):
      col_str = str(col).strip()
      if col_str in new_cols:
          new_cols.append(f"{col_str}_{i}")
      else:
          new_cols.append(col_str)
  df.columns = new_cols

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

  new_cols = []
  for i, col in enumerate(df.columns):
      col_str = str(col).strip()
      if col_str in new_cols:
          new_cols.append(f"{col_str}_{i}")
      else:
          new_cols.append(col_str)
  df.columns = new_cols

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
      f"- **最高水位**：{max_val:.2f} (發生於"
      f" {max_time.strftime('%Y-%m-%d %H:%M')})\n"
      f"- **最低水位**：{min_val:.2f} (發生於"
      f" {min_time.strftime('%Y-%m-%d %H:%M')})"
  )

  min_date, max_date = df[time_col].min(), df[time_col].max()

  df_rain = None
  r_time_col = None
  r_val_cols = []
  selected_rain_cols = []

  if uploaded_rain:
    with st.spinner("正在解析降雨資料..."):
      df_rain, r_time_col, r_val_cols = load_and_clean_rain(uploaded_rain)
      if not df_rain.empty:
        min_date = min(min_date, df_rain[r_time_col].min())
        max_date = max(max_date, df_rain[r_time_col].max())

  st.sidebar.markdown("---")
  st.sidebar.header("⏱️ 2. 颱風/事件區間設定")
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

  if df_rain is not None and not df_rain.empty and r_val_cols:
    st.sidebar.markdown("---")
    st.sidebar.header("🌧️ 4. 降雨欄位對應選擇 (可複選)")
    default_names = []
    for name_pref in ["1小時", "降雨量", "rain", "Rain"]:
      if name_pref in r_val_cols:
        default_names = [name_pref]
        break
    selected_rain_cols = st.sidebar.multiselect(
        "選擇要繪圖與分析的雨量欄位", r_val_cols, default=default_names
    )

  st.sidebar.markdown("---")
  st.sidebar.header("⚙️ 5. 圖表縱軸 (Y 軸) 範圍設定")

  use_manual_y = st.sidebar.checkbox("手動固定【水位】縱軸數值", value=False)
  manual_y_min, manual_y_max = 0.0, 0.0
  if use_manual_y:
    suggest_min = float(df[water_col].min() - 1)
    suggest_max = float(df[water_col].max() + 1)
    manual_y_min = st.sidebar.number_input(
        "水位最小值 (Y min)", value=suggest_min, format="%.2f"
    )
    manual_y_max = st.sidebar.number_input(
        "水位最大值 (Y max)", value=suggest_max, format="%.2f"
    )

  use_manual_rain_y = False
  manual_rain_max = 500.0
  if (
      df_rain is not None
      and not df_rain.empty
      and len(selected_rain_cols) > 0
  ):
    use_manual_rain_y = st.sidebar.checkbox(
        "手動固定【雨量】縱軸數值", value=False
    )
    if use_manual_rain_y:
      try:
          max_val = df_rain[selected_rain_cols].max().max()
          suggest_rain_max = float(np.ravel(max_val)[0]) * 1.2 if pd.notna(max_val) else 500.0
      except:
          suggest_rain_max = 500.0
      manual_rain_max = st.sidebar.number_input(
          "雨量最大值 (Rain Y max)", value=suggest_rain_max, format="%.2f"
      )

  # --- 主畫面區塊 ---
  if start_dt >= end_dt:
    st.error("開始時間必須早於結束時間！")
  else:
    df_filtered = df[
        (df[time_col] >= start_dt) & (df[time_col] <= end_dt)
    ].copy()

    has_rain = df_rain is not None and not df_rain.empty
    df_rain_filtered = pd.DataFrame()
    if has_rain:
        df_rain_filtered = df_rain[
            (df_rain[r_time_col] >= start_dt)
            & (df_rain[r_time_col] <= end_dt)
        ].copy()

    if df_filtered.empty:
      st.warning(
          "⚠️ 在您選擇的時間區間內找不到水位資料，請重新調整篩選範圍。"
      )
    else:
      first_record = df_filtered.iloc[0]
      last_record = df_filtered.iloc[-1]
      
      level_start = float(np.ravel(first_record[water_col])[0])
      level_end = float(np.ravel(last_record[water_col])[0])
      level_diff = level_end - level_start

      t_start = pd.to_datetime(np.ravel(first_record[time_col])[0])
      t_end = pd.to_datetime(np.ravel(last_record[time_col])[0])
      time_diff_days = (t_end - t_start).total_seconds() / (24 * 3600)
      
      rate_day = level_diff / time_diff_days if time_diff_days > 0 else 0
      trend_word = "上升" if level_diff > 0 else ("洩降" if level_diff < 0 else "變化")

      st.markdown("### 📊 選擇區間之整體計算結果")
      
      col1, col2, col3, col4 = st.columns(4)
      col1.metric("初始水位", f"{level_start:.2f} m")
      col2.metric("結束水位", f"{level_end:.2f} m")
      col3.metric(
          f"🔺 水位{trend_word}幅度",
          f"{abs(level_diff):.2f} m",
      )
      col4.metric(f"區間平均{trend_word}速率 (m/day)", f"{abs(rate_day):.2f}")

      if has_rain and len(selected_rain_cols) > 0 and not df_rain_filtered.empty:
          st.markdown(f"#### 🌧️ 對應降雨時段之平均{trend_word}速率與極值")
          r_cols = st.columns(len(selected_rain_cols))
          
          for idx, r_col in enumerate(selected_rain_cols):
              hours = 1
              match = re.search(r'(\d+)', r_col)
              if match:
                  hours = int(match.group(1))
              elif "日" in r_col or "day" in r_col.lower():
                  hours = 24
                  
              specific_rate = abs(rate_day) * (hours / 24)
              
              try:
                  max_r = df_rain_filtered[r_col].max()
                  max_r_val = float(np.ravel(max_r)[0]) if pd.notna(np.ravel(max_r)[0]) else 0.0
              except:
                  max_r_val = 0.0
              
              r_cols[idx].metric(
                  label=f"【{r_col}】{trend_word}速率", 
                  value=f"{specific_rate:.2f} m/{r_col}",
                  delta=f"區間內最大雨量: {max_r_val:.2f} mm",
                  delta_color="off"
              )

      st.markdown("---")
      st.markdown("### 📈 水位與降雨事件歷線圖")

      rows_count = 2 if has_rain and len(selected_rain_cols) > 0 else 1

      fig = make_subplots(
          rows=rows_count,
          cols=1,
          shared_xaxes=True,
          vertical_spacing=0.1,
          row_heights=[0.7, 0.3] if rows_count == 2 else [1.0],
      )

      fig.add_trace(
          go.Scatter(
              x=df_filtered[time_col],
              y=df_filtered[water_col],
              mode="lines",
              name="地下水位",
              line=dict(color="#1f77b4", width=2),
              hovertemplate="水位: %{y:.2f} m<extra></extra>"
          ),
          row=1,
          col=1,
      )

      if rows_count == 2:
        bar_colors = ["#1A237E", "#B71C1C", "#1B5E20", "#4A148C", "#E65100", "#004D40"]
        
        for idx, r_col in enumerate(selected_rain_cols):
            c = bar_colors[idx % len(bar_colors)]
            fig.add_trace(
                go.Bar(
                    x=df_rain_filtered[r_time_col],
                    y=df_rain_filtered[r_col],
                    name=r_col,
                    marker=dict(color=c, line=dict(width=0)), 
                    hovertemplate=f"{r_col}: %{{y:.2f}} mm<extra></extra>"
                ),
                row=2,
                col=1,
            )
            
        fig.update_layout(barmode='group')
        
        if use_manual_rain_y:
          fig.update_yaxes(
              title_text="雨量 (mm)",
              range=[0, manual_rain_max],
              row=2,
              col=1,
          )
        else:
          fig.update_yaxes(
              title_text="雨量 (mm)",
              autorange=True,
              row=2,
              col=1,
          )

      for ev_name, ev_dt in custom_events:
        if start_dt <= ev_dt <= end_dt:
          water_val_str = "N/A"
          if not df.empty:
            closest_w_idx = (df[time_col] - ev_dt).abs().idxmin()
            try:
                w_val = float(np.ravel(df.loc[closest_w_idx, water_col])[0])
                water_val_str = f"{w_val:.2f} m"
            except:
                pass

          rain_strs = []
          if has_rain and not df_rain.empty and selected_rain_cols:
            closest_r_idx = (df_rain[r_time_col] - ev_dt).abs().idxmin()
            for r_col in selected_rain_cols:
                try:
                    r_val = float(np.ravel(df_rain.loc[closest_r_idx, r_col])[0])
                    if pd.notna(r_val):
                        rain_strs.append(f"{r_val:.2f} mm ({r_col})")
                except:
                    pass
                    
          rain_val_str = "<br>      ".join(rain_strs) if rain_strs else "N/A"

          label_text = (
              f"<b>{ev_name}</b><br>水位: {water_val_str}<br>雨量: {rain_val_str}"
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

      fig.update_xaxes(
          hoverformat="%Y-%m-%d %H:%M",
          tickformatstops=[
              dict(dtickrange=[None, 3600000], value="%m-%d %H:%M"),
              dict(dtickrange=[3600000, 86400000], value="%m-%d %H:%M"),
              dict(dtickrange=[86400000, 604800000], value="%Y-%m-%d"),
              dict(dtickrange=[604800000, "M1"], value="%Y-%m-%d"),
              dict(dtickrange=["M1", "M12"], value="%Y-%m"),
              dict(dtickrange=["M12", None], value="%Y")
          ]
      )

      fig.update_layout(
          template="plotly_white",
          hovermode="x unified",
          height=650 if rows_count == 2 else 450,
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
      
      # =========================================================
      # 降雨與水位相關性分析 (對數迴歸散佈圖) - 突出事件特化版
      # =========================================================
      if has_rain and len(selected_rain_cols) > 0 and not df_rain_filtered.empty:
          st.markdown("---")
          
          with st.expander("🔗 點擊展開：降雨與水位相關性分析 (對數迴歸)", expanded=False):
              st.markdown("""
              擷取選定區間內的**每日極值**進行配對。為避免日常微弱降雨干擾回歸曲線，您可以設定**最低降雨門檻**，專注分析**突出降雨事件**。
              此外，您在側邊欄標註的「颱風/事件」將會在圖上被**紅色星星**標記凸顯，讓您秒懂這些重大事件的極值位置！
              """)
              
              col_a, col_b = st.columns([1, 2])
              with col_a:
                  # 讓使用者設定門檻濾除雜訊
                  min_rain_threshold = st.number_input("設定有效降雨門檻 (mm/日)：", min_value=0.0, value=30.0, step=10.0, help="只將降雨量大於此數值的日子納入迴歸分析。")
              
              try:
                  # 抓取日極值
                  df_w_daily = df_filtered.set_index(time_col)[[water_col]].resample('D').max().reset_index()
                  df_r_daily = df_rain_filtered.set_index(r_time_col)[selected_rain_cols].resample('D').max().reset_index()
                  
                  df_w_daily['Date'] = df_w_daily[time_col].dt.date
                  df_r_daily['Date'] = df_r_daily[r_time_col].dt.date
                  
                  df_scatter = pd.merge(df_w_daily, df_r_daily, on='Date', how='inner')
                  
                  # 建立事件對照表，用於標註星星
                  event_dict = {}
                  for ev_name, ev_dt in custom_events:
                      event_dict[ev_dt.date()] = ev_name
                  
                  tabs = st.tabs([f"📊 {col} 相關性" for col in selected_rain_cols])
                  
                  for idx, r_col in enumerate(selected_rain_cols):
                      with tabs[idx]:
                          try:
                              r_arr = pd.to_numeric(df_scatter[r_col], errors='coerce').fillna(0).values
                              w_arr = pd.to_numeric(df_scatter[water_col], errors='coerce').values
                              date_arr = df_scatter['Date'].values
                              
                              # 關鍵邏輯：過濾掉小於 threshold 降雨量 以及缺失水位的資料
                              valid_mask = (r_arr >= min_rain_threshold) & (~np.isnan(w_arr))
                              
                              if np.sum(valid_mask) > 2:
                                  # 將資料掛回 DataFrame 以方便篩選標記
                                  df_valid = pd.DataFrame({
                                      'Date': date_arr[valid_mask],
                                      'Rain': r_arr[valid_mask],
                                      'Water': w_arr[valid_mask]
                                  })
                                  
                                  # 對應事件名稱
                                  df_valid['EventName'] = df_valid['Date'].map(event_dict)
                                  
                                  # 分為一般點與事件點
                                  df_normal = df_valid[df_valid['EventName'].isna()]
                                  df_event = df_valid[df_valid['EventName'].notna()]
                                  
                                  x_val = df_valid['Rain'].values
                                  y_val = df_valid['Water'].values
                                  
                                  # 1. 執行對數迴歸擬合 y = a * ln(x) + b (避免 log(0) 錯誤)
                                  x_val_safe = np.where(x_val == 0, 1e-5, x_val)
                                  log_x = np.log(x_val_safe)
                                  a, b = np.polyfit(log_x, y_val, 1)
                                  
                                  y_pred = a * log_x + b
                                  ss_res = np.sum((y_val - y_pred)**2)
                                  ss_tot = np.sum((y_val - np.mean(y_val))**2)
                                  r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
                                  
                                  fig_scatter = go.Figure()
                                  
                                  # 畫出一般觀測點 (藍色)
                                  fig_scatter.add_trace(
                                      go.Scatter(
                                          x=df_normal['Rain'], 
                                          y=df_normal['Water'],
                                          mode='markers',
                                          name='一般突出降雨日',
                                          marker=dict(color='#3399FF', size=8, line=dict(color='white', width=1), opacity=0.7),
                                          customdata=df_normal['Date'],
                                          hovertemplate="日期: %{customdata}<br>雨量: %{x:.2f} mm<br>水位: %{y:.2f} m<extra></extra>"
                                      )
                                  )
                                  
                                  # 畫出使用者標註的事件點 (紅色大星星)
                                  if not df_event.empty:
                                      fig_scatter.add_trace(
                                          go.Scatter(
                                              x=df_event['Rain'], 
                                              y=df_event['Water'],
                                              mode='markers+text',
                                              name='🔥 您的標註事件',
                                              text=df_event['EventName'],
                                              textposition="top center",
                                              marker=dict(color='#FF3333', size=14, symbol='star', line=dict(color='black', width=1)),
                                              customdata=df_event['Date'],
                                              hovertemplate="<b>%{text}</b><br>日期: %{customdata}<br>雨量: %{x:.2f} mm<br>水位: %{y:.2f} m<extra></extra>"
                                          )
                                      )
                                  
                                  # 加入對數趨勢線
                                  x_trend = np.linspace(min(x_val), max(x_val), 100)
                                  x_trend_safe = np.where(x_trend == 0, 1e-5, x_trend)
                                  y_trend = a * np.log(x_trend_safe) + b
                                  
                                  fig_scatter.add_trace(
                                      go.Scatter(
                                          x=x_trend, 
                                          y=y_trend,
                                          mode='lines',
                                          name=f'對數趨勢線 (R² = {r2:.4f})',
                                          line=dict(color='#0033CC', width=3, dash='dash')
                                      )
                                  )
                                  
                                  fig_scatter.update_layout(
                                      template='plotly_white',
                                      title=dict(text=f"{r_col} vs 地下水位 (相似度 R² = {r2:.4f})", x=0.5, font=dict(size=18)),
                                      xaxis_title=f"{r_col} (mm)",
                                      yaxis_title="地下水位 (m)",
                                      height=500,
                                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                                  )
                                  
                                  fig_scatter.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                  fig_scatter.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                                  
                                  st.plotly_chart(fig_scatter, use_container_width=True)
                                  
                                  st.info(f"💡 **分析結果**：排除小於 {min_rain_threshold} mm 的無效降雨後，共擷取 **{len(df_valid)}** 個突出事件點。對數方程式為 `y = {a:.4f} * ln(x) + {b:.4f}`，決定係數 $R^2$ 為 **{r2:.4f}**。")
                              else:
                                  st.warning(f"⚠️ {r_col} 在大於等於 {min_rain_threshold} mm 的有效事件點不足，無法繪製對數趨勢。請嘗試調降門檻數值。")
                          except Exception as inner_e:
                              st.warning(f"⚠️ 該欄位運算發生錯誤：{inner_e}")
              except Exception as e:
                  st.warning(f"⚠️ 相關性分析運算發生異常，暫無法顯示圖表。錯誤提示：{type(e).__name__} - {e}")
else:
  st.info("👈 請先由左側面板上傳 CSV 檔案。")
