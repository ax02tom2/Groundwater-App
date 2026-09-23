from plotly.subplots import make_subplots
import plotly.graph_objects as go
import streamlit as st

# 1. 建立具有雙 Y 軸的圖表基底
fig_water = make_subplots(specs=[[{"secondary_y": True}]])

# 2. 加入水位折線圖 (對應主 Y 軸：左側)
fig_water.add_trace(
    go.Scatter(
        x=df['時間'],        # 【注意】請確認 df 內的日期時間欄位名稱是否為 '時間'
        y=df['水位'],        # 【注意】請確認 df 內的水位欄位名稱
        mode='lines',
        name='地下水位',
        line=dict(color='#1f77b4', width=2)
    ),
    secondary_y=False,
)

# 3. 加入降雨量柱狀圖 (對應副 Y 軸：右側)
fig_water.add_trace(
    go.Bar(
        x=df['時間'],        # 【注意】需與上方相同
        y=df['降雨量'],      # 【注意】請確認 df 內的降雨量欄位名稱
        name='降雨量',
        marker_color='#00d2d3',
        opacity=0.6
    ),
    secondary_y=True,
)

# 4. 更新整體版面與 X 軸設定
fig_water.update_layout(
    title="地下水位升降與颱風降雨分析",
    xaxis_title="時間",
    template="plotly_white", # 使用乾淨的主題避免深色模式衝突
    hovermode="x unified",   # 讓滑鼠游標一次顯示水位與降雨量
    legend=dict(
        orientation="h", 
        yanchor="bottom", 
        y=1.02, 
        xanchor="right", 
        x=1
    ),
    margin=dict(l=40, r=40, t=60, b=40)
)

# 5. 分別更新兩個 Y 軸的標籤與翻轉 (降雨量通常由上往下畫)
fig_water.update_yaxes(title_text="水位 (公尺)", secondary_y=False)
fig_water.update_yaxes(title_text="降雨量 (mm)", secondary_y=True, autorange="reversed")

# 6. 輸出至 Streamlit
st.plotly_chart(fig_water, use_container_width=True)
