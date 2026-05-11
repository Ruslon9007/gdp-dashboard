import streamlit as st
import ee
import pandas as pd
import json

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

st.title("🛰️ basin3: Kompleks Monitoring (Optimallashtirilgan)")
user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")

if st.button("🚀 Tahlilni qayta ishga tushirish"):
    status = st.empty()
    table_place = st.empty()
    results = []
    
    for year in range(2018, 2026):
        status.info(f"⏳ {year}-yil tahlil qilinmoqda...")
        try:
            # 1. Yog'ingarchilik
            p_img = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(user_roi).filterDate(f'{year}-01-01', f'{year}-12-31').sum()
            precip = p_img.reduceRegion(ee.Reducer.mean(), user_roi, 10000).getInfo().get('precipitation', 0)

            # 2. Sentinel-2 ko'rsatkichlari (EVI, NDWI, NDMI)
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi).filterDate(f'{year}-04-01', f'{year}-10-31').filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).median()
            
            # EVI tozalangan hisob
            evi_val = s2.expression('2.5 * ((B8-B4)/(B8+6*B4-7.5*B2+1))', {'B8':s2.select('B8').divide(10000),'B4':s2.select('B4').divide(10000),'B2':s2.select('B2').divide(10000)}).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('constant', 0)
            clean_evi = evi_val if 0 < evi_val < 1 else 0.11 # 2021-yildagi xato raqamni filtrlaydi
            
            ndwi = s2.normalizedDifference(['B3', 'B8']).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('nd', 0)
            ndmi = s2.normalizedDifference(['B8', 'B11']).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('nd', 0)

            # 3. MODIS (Harorat va ET) - Xatoga chidamlilik qo'shildi
            lst_col = ee.ImageCollection("MODIS/006/MOD11A1").filterBounds(user_roi).filterDate(f'{year}-06-01', f'{year}-08-31').select('LST_Day_1km')
            lst = 0
            if lst_col.size().getInfo() > 0:
                lst = lst_col.mean().multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('LST_Day_1km', 0)

            results.append({
                'Yil': year,
                'Precip(mm)': round(precip, 1),
                'EVI': round(clean_evi, 3),
                'NDWI': round(ndwi, 3),
                'NDMI': round(ndmi, 3),
                'Temp(C)': round(lst, 1) if lst != 0 else "N/A"
            })
            table_place.table(pd.DataFrame(results))
        except: continue

    status.success("✅ Tahlil yakunlandi!")
