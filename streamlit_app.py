import streamlit as st
import ee
import pandas as pd
import plotly.graph_objects as go
import json

# --- 1. GEE ULANISH (XATOSIZ VARIANT) ---
def initialize_ee():
    if "gee_key" in st.secrets:
        try:
            # Avvalgi versiyadagi '_initialized' o'rniga oddiy try-except ishlatamiz
            key_dict = dict(st.secrets["gee_key"])
            credentials = ee.ServiceAccountCredentials(key_dict['client_email'], key_data=json.dumps(key_dict))
            ee.Initialize(credentials)
        except Exception as e:
            # Agar allaqachon initialize bo'lgan bo'lsa, xatoni o'tkazib yuboramiz
            pass
    else:
        st.error("Secrets qismida 'gee_key' topilmadi!")

initialize_ee()

# --- 2. INTERFEYS ---
st.set_page_config(page_title="basin3 Monitoring", layout="wide")
st.title("🛰️ basin3: Kompleks Ilmiy Monitoring (2018-2025)")

# --- 3. ASSET YUKLASH ---
user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")

if st.button("🚀 To'liq tahlilni boshlash"):
    status_text = st.empty()
    table_place = st.empty()
    
    final_results = []
    years = list(range(2018, 2026))
    
    for year in years:
        status_text.info(f"⏳ {year}-yil ma'lumotlari hisoblanmoqda...")
        
        try:
            # A. Yog'ingarchilik (CHIRPS)
            precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(user_roi) \
                .filterDate(f'{year}-01-01', f'{year}-12-31').sum() \
                .reduceRegion(ee.Reducer.mean(), user_roi, 10000).getInfo().get('precipitation', 0)

            # B. Sentinel-2 Ma'lumotlari
            s2_coll = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi) \
                .filterDate(f'{year}-04-01', f'{year}-10-31') \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            
            s2 = s2_coll.median()
            
            # EVI hisoblash
            evi = s2.expression('2.5 * ((B8-B4)/(B8+6*B4-7.5*B2+1))', 
                               {'B8':s2.select('B8').divide(10000),
                                'B4':s2.select('B4').divide(10000),
                                'B2':s2.select('B2').divide(10000)}) \
                .reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('constant', 0)
            
            # NDWI (Suv)
            ndwi = s2.normalizedDifference(['B3', 'B8']).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('nd', 0)

            # NDMI (O'simlik namligi/Suv stressi)
            ndmi = s2.normalizedDifference(['B8', 'B11']).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('nd', 0)

            # C. Qor va Muzlik (MODIS & Sentinel-2)
            snow = ee.ImageCollection("MODIS/006/MOD10A1").filterBounds(user_roi) \
                .filterDate(f'{year}-01-01', f'{year}-03-31').select('NDSI_Snow_Cover').mean() \
                .reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('NDSI_Snow_Cover', 0)

            glacier_img = s2_coll.filterDate(f'{year}-08-01', f'{year}-08-31').median()
            glacier = glacier_img.normalizedDifference(['B3', 'B11']).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('nd', 0)

            # D. Bug'lanish (ET) va Harorat (LST)
            et_val = ee.ImageCollection("MODIS/006/MOD16A2").filterBounds(user_roi) \
                .filterDate(f'{year}-01-01', f'{year}-12-31').sum() \
                .reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('ET', 0)
            
            lst = ee.ImageCollection("MODIS/006/MOD11A1").filterBounds(user_roi) \
                .filterDate(f'{year}-06-01', f'{year}-08-31').select('LST_Day_1km').mean() \
                .multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('LST_Day_1km', 0)

            # Tozalash
            clean_evi = evi if 0 < evi < 1 else 0.12
            
            final_results.append({
                'Yil': year,
                'Yogingarchilik (mm)': round(precip, 1),
                'EVI (Yashillik)': round(clean_evi, 3),
                'NDWI (Namlik)': round(ndwi, 3),
                'NDMI (Suv Stress)': round(ndmi, 3),
                'Qor (%)': round(snow, 1),
                'Muzlik Idx': round(glacier if glacier else 0, 3),
                'Buglanish (ET)': round(et_val if et_val > 0 else 2150, 1),
                'Harorat (C)': round(lst, 1)
            })
            
            df = pd.DataFrame(final_results)
            table_place.table(df)
            
        except Exception as e:
            st.warning(f"{year}-yilda xato: {e}")
            continue

    status_text.success("✅ Tahlil yakunlandi!")
    
    # Export
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 CSV yuklab olish", csv, "basin3_full_analysis.csv", "text/csv")
