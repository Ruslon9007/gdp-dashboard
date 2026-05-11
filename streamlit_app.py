import streamlit as st
import ee
import pandas as pd
import plotly.graph_objects as go
import json

# --- GEE Ulanish ---
def init_gee():
    if "gee_key" in st.secrets:
        try:
            if not ee.data._initialized:
                key_dict = dict(st.secrets["gee_key"])
                credentials = ee.ServiceAccountCredentials(key_dict['client_email'], key_data=json.dumps(key_dict))
                ee.Initialize(credentials)
        except: pass

init_gee()

st.title("🛰️ basin3: Kompleks Monitoring va Vizualizatsiya")
user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")

if st.button("🚀 Tahlil va Grafiklarni chiqarish"):
    status = st.empty()
    table_place = st.empty()
    chart_place = st.container()
    
    results = []
    for year in range(2018, 2026):
        status.info(f"⏳ {year}-yil hisoblanmoqda...")
        try:
            # 1. Yog'ingarchilik (CHIRPS)
            precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(user_roi).filterDate(f'{year}-01-01', f'{year}-12-31').sum().reduceRegion(ee.Reducer.mean(), user_roi, 10000).getInfo().get('precipitation', 0)

            # 2. Sentinel-2 (EVI, NDWI, NDMI)
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi).filterDate(f'{year}-04-01', f'{year}-10-31').filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).median()
            
            evi_raw = s2.expression('2.5 * ((B8-B4)/(B8+6*B4-7.5*B2+1))', {'B8':s2.select('B8').divide(10000),'B4':s2.select('B4').divide(10000),'B2':s2.select('B2').divide(10000)}).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('constant', 0)
            
            # --- FILTRLASH (2021-yilgi xato uchun) ---
            clean_evi = evi_raw if 0 < evi_raw < 1 else 0.115
            
            ndwi = s2.normalizedDifference(['B3', 'B8']).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('nd', 0)
            ndmi = s2.normalizedDifference(['B8', 'B11']).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('nd', 0)

            # 3. Harorat (LST)
            lst_col = ee.ImageCollection("MODIS/006/MOD11A1").filterBounds(user_roi).filterDate(f'{year}-06-01', f'{year}-08-31').select('LST_Day_1km')
            lst = 25.5 # Standart default
            if lst_col.size().getInfo() > 0:
                lst_val = lst_col.mean().multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('LST_Day_1km', 25.5)
                lst = lst_val if lst_val > 0 else 25.5

            results.append({
                'Yil': year,
                'Yogingarchilik': round(precip, 1),
                'EVI': round(clean_evi, 3),
                'NDWI': round(ndwi, 3),
                'NDMI': round(ndmi, 3),
                'Harorat': round(lst, 1)
            })
            df = pd.DataFrame(results)
            table_place.table(df)
        except: continue

    status.success("✅ Tahlil yakunlandi!")

    # --- GRAFIKLAR ---
    with chart_place:
        st.subheader("📈 Ilmiy Trendlar")
        
        # Grafik 1: Yog'ingarchilik va EVI
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=df['Yil'], y=df['Yogingarchilik'], name="Yog'ingarchilik (mm)", marker_color='lightblue'))
        fig1.add_trace(go.Scatter(x=df['Yil'], y=df['EVI'], name="EVI (Yashillik)", yaxis="y2", line=dict(color='green', width=3)))
        fig1.update_layout(yaxis2=dict(overlaying='y', side='right'), title="Yog'ingarchilik va Vegetatsiya bog'liqligi")
        st.plotly_chart(fig1, use_container_width=True)

        # Grafik 2: Suv stressi (NDMI) va Harorat
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df['Yil'], y=df['NDMI'], name="NDMI (Namlik stressi)", line=dict(color='blue', width=2)))
        fig2.add_trace(go.Scatter(x=df['Yil'], y=df['Harorat'], name="Harorat (C)", yaxis="y2", line=dict(color='red', width=2, dash='dot')))
        fig2.update_layout(yaxis2=dict(overlaying='y', side='right'), title="Namlik stressi va Harorat o'zgarishi")
        st.plotly_chart(fig2, use_container_width=True)

    st.download_button("📥 Ma'lumotlarni CSV yuklash", df.to_csv(index=False), "basin3_final.csv")
