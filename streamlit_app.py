import streamlit as st
import ee
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# GEE Ulanish
def init_gee():
    if "gee_key" in st.secrets:
        try:
            if not ee.data._initialized:
                key_dict = dict(st.secrets["gee_key"])
                credentials = ee.ServiceAccountCredentials(key_dict['client_email'], key_data=json.dumps(key_dict))
                ee.Initialize(credentials)
        except: pass

init_gee()

st.title("🛰️ basin3: Monitoring va Vizualizatsiya")
user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")

if st.button("🚀 Tahlil va Grafiklarni chiqarish"):
    status = st.empty()
    table_place = st.empty()
    chart_place = st.container() # Grafiklar uchun joy
    
    results = []
    for year in range(2018, 2026):
        status.info(f"⏳ {year}-yil hisoblanmoqda...")
        try:
            # Ma'lumotlarni yig'ish (Oldingi mantiq asosida)
            # ... (Bu yerda yuqoridagi barcha indekslarni hisoblash kodi bor) ...
            
            # 2021-yilgi EVI kabi xatolarni filtrlash (Logical Filter)
            # clean_evi = evi if 0 < evi < 1 else 0.11
            
            # Namuna sifatida natijani qo'shish
            results.append({
                'Yil': year,
                'Yogingarchilik': precip, # Hisoblangan qiymat
                'EVI': clean_evi,
                'NDMI': ndmi_val,
                'Harorat': lst_val
            })
            df = pd.DataFrame(results)
            table_place.table(df)
        except: continue

    status.success("✅ Tahlil yakunlandi! Grafiklar tayyorlanmoqda...")

    # --- TASVIRLARNI (GRAFIKLARNI) QO'SHISH ---
    with chart_place:
        st.subheader("📈 Ilmiy Trendlar Vizualizatsiyasi")
        
        # 1. Yog'ingarchilik va Harorat (Dual Axis)
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=df['Yil'], y=df['Yogingarchilik'], name="Yog'ingarchilik (mm)", marker_color='lightblue'))
        fig1.add_trace(go.Scatter(x=df['Yil'], y=df['Harorat'], name="Harorat (C)", yaxis="y2", line=dict(color='orange', width=3)))
        
        fig1.update_layout(
            title="Yog'ingarchilik va Harorat dinamikasi",
            yaxis=dict(title="Yog'ingarchilik (mm)"),
            yaxis2=dict(title="Harorat (C)", overlaying='y', side='right'),
            legend=dict(x=0, y=1.1, orientation="h")
        )
        st.plotly_chart(fig1, use_container_width=True)

        # 2. Vegetatsiya Indekslari (EVI vs NDMI)
        fig2 = px.line(df, x='Yil', y=['EVI', 'NDMI'], markers=True,
                       title="EVI (Yashillik) va NDMI (Namlik stressi) solishtirmasi",
                       color_discrete_map={"EVI": "green", "NDMI": "blue"})
        st.plotly_chart(fig2, use_container_width=True)

    # Ma'lumotlarni saqlash (CSV)
    st.download_button("📥 Ma'lumotlarni (CSV) yuklab olish", df.to_csv(index=False), "basin3_data.csv")
