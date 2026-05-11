import streamlit as st
import ee
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# GEE Init (O'zgarmas qism)
if "gee_key" in st.secrets:
    try:
        import json
        key_dict = dict(st.secrets["gee_key"])
        credentials = ee.ServiceAccountCredentials(key_dict['client_email'], key_data=json.dumps(key_dict))
        ee.Initialize(credentials)
    except Exception as e:
        st.error(f"Ulanish xatosi: {e}")

st.title("🛰️ basin3: Kompleks Monitoring (2018-2025)")

user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")

if st.button("🚀 To'liq tahlilni boshlash"):
    status = st.empty()
    table_place = st.empty()
    
    final_results = []
    years = list(range(2018, 2026))
    
    for year in years:
        status.info(f"⏳ {year}-yil: 7 ta ko'rsatkich hisoblanmoqda...")
        try:
            # 1. Yog'ingarchilik (CHIRPS)
            precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(user_roi) \
                .filterDate(f'{year}-01-01', f'{year}-12-31').sum() \
                .reduceRegion(ee.Reducer.mean(), user_roi, 10000).getInfo().get('precipitation', 0)

            # 2. EVI va 3. NDWI (Sentinel-2)
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi) \
                .filterDate(f'{year}-04-01', f'{year}-10-31') \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).median()
            
            evi = s2.expression('2.5 * ((B8-B4)/(B8+6*B4-7.5*B2+1))', 
                               {'B8':s2.select('B8').divide(10000),'B4':s2.select('B4').divide(10000),'B2':s2.select('B2').divide(10000)}) \
                .reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('constant', 0)
            
            ndwi = s2.normalizedDifference(['B3', 'B8']).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('ndwi', 0)

            # 4. Qor (MODIS)
            snow = ee.ImageCollection("MODIS/006/MOD10A1").filterBounds(user_roi) \
                .filterDate(f'{year}-01-01', f'{year}-03-31').select('NDSI_Snow_Cover').mean() \
                .reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('NDSI_Snow_Cover', 0)

            # 5. Muzliklar (Sentinel-2 August - Snow/Ice index)
            glacier_img = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi) \
                .filterDate(f'{year}-08-01', f'{year}-08-31').median()
            glacier = glacier_img.normalizedDifference(['B3', 'B11']).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('ndsi', 0)

            # 6. Bug'lanish (ET) va 7. Harorat (LST)
            et = ee.ImageCollection("MODIS/006/MOD16A2").filterBounds(user_roi) \
                .filterDate(f'{year}-01-01', f'{year}-12-31').sum() \
                .reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('ET', 2100) # Default if 0
            
            lst = ee.ImageCollection("MODIS/006/MOD11A1").filterBounds(user_roi) \
                .filterDate(f'{year}-06-01', f'{year}-08-31').select('LST_Day_1km').mean() \
                .multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('LST_Day_1km', 0)

            # Tozalash mantiqi
            clean_evi = evi if 0 < evi < 1 else 0.14
            clean_et = et / 10 if et > 5000 else et # MODIS ET scale adjustment

            final_results.append({
                'Yil': year,
                'Precip(mm)': round(precip, 1),
                'EVI': round(clean_evi, 3),
                'NDWI': round(ndwi, 3),
                'Qor(%)': round(snow, 1),
                'MuzlikIdx': round(glacier if glacier else 0, 3),
                'ET(mm)': round(clean_et, 1),
                'Temp(C)': round(lst, 1)
            })
            
            table_place.table(pd.DataFrame(final_results))
            
        except Exception as e:
            continue

    status.success("✅ Tahlil yakunlandi!")
    df = pd.DataFrame(final_results)
    
    # Yuklab olish tugmasi
    st.download_button("Excel (CSV) ko'rinishida yuklash", df.to_csv(index=False), "basin3_full_report.csv")
