import streamlit as st
import ee
import json
import pandas as pd
import folium
from streamlit_folium import folium_static
import plotly.express as px

# 1. Sahifa sozlamalari
st.set_page_config(page_title="Hydro-Agro Monitor", layout="wide", page_icon="🛰️")

# 2. GEE Initialize (Secrets orqali)
def init_gee():
    try:
        if "gee_key" in st.secrets:
            key_dict = dict(st.secrets["gee_key"])
            credentials = ee.ServiceAccountCredentials(
                key_dict['client_email'], 
                key_data=json.dumps(key_dict)
            )
            ee.Initialize(credentials)
            return True
        return False
    except Exception as e:
        st.error(f"GEE ulanishida xato: {e}")
        return False

# GEE qatlamini Foliumga qo'shish funksiyasi
def add_ee_layer(self, ee_image_object, vis_params, name):
    try:
        map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
        folium.raster_layers.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='Google Earth Engine', name=name, overlay=True
        ).add_to(self)
    except:
        pass
folium.Map.add_ee_layer = add_ee_layer

if init_gee():
    # Sidebar Navigatsiya
    st.sidebar.title("🚀 Monitoring Paneli")
    mode = st.sidebar.radio("Modulni tanlang:", 
                            ["Shovot: Oylik EVI (Sentinel-2)", 
                             "Amudaryo: Qor Zaxirasi (MODIS)", 
                             "Amudaryo: Muzliklar (Sentinel-2)"])
    
    # Umumiy yil tanlovi
    year = st.sidebar.selectbox("Yilni tanlang", [2021, 2022, 2023, 2024], index=2)

    # Hududlar (ROI)
    shovot_roi = ee.Geometry.Polygon([[[60.1, 41.5], [60.5, 41.5], [60.5, 41.8], [60.1, 41.8], [60.1, 41.5]]])
    upper_amudarya = ee.Geometry.Polygon([[[68.0, 36.5], [75.0, 36.5], [75.0, 39.5], [68.0, 39.5], [68.0, 36.5]]])

    # --- MODUL 1: OYLIK EVI ---
    if mode == "Shovot: Oylik EVI (Sentinel-2)":
        st.title("🛰️ Shovot Tumani: Oylik EVI Monitoringi")
        month = st.sidebar.slider("Oy", 3, 10, 6)
        months_uz = {3:"Mart", 4:"Aprel", 5:"May", 6:"Iyun", 7:"Iyul", 8:"Avgust", 9:"Sentyabr", 10:"Oktyabr"}
        st.subheader(f"📅 {year}-yil, {months_uz[month]} oyi")

        with st.spinner("Sentinel-2 ma'lumotlari yuklanmoqda..."):
            start_date = ee.Date.fromYMD(year, month, 1)
            end_date = start_date.advance(1, 'month')
            
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(shovot_roi).filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).median()

            evi = s2.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                    'NIR': s2.select('B8').divide(10000),
                    'RED': s2.select('B4').divide(10000),
                    'BLUE': s2.select('B2').divide(10000)
                }).clip(shovot_roi)

            m1 = folium.Map(location=[41.65, 60.30], zoom_start=11)
            vis_evi = {'min': 0, 'max': 0.8, 'palette': ['white', '#fcd163', '#99b718', '#207401', '#011301']}
            m1.add_ee_layer(evi, vis_evi, 'EVI Index')
            
            c1, c2 = st.columns([1, 3])
            try:
                stats = evi.reduceRegion(ee.Reducer.mean(), shovot_roi, 100).getInfo()
                val = stats['constant']
                c1.metric("O'rtacha EVI", f"{val:.3f}")
            except:
                c1.warning("Ma'lumot topilmadi.")
            folium_static(m1, width=900)

    # --- MODUL 2: QOR ZAXIRASI ---
    elif mode == "Amudaryo: Qor Zaxirasi (MODIS)":
        st.title("🏔 Amudaryo Havzasi: Qor Qoplami")
        with st.spinner("Qor tahlil qilinmoqda..."):
            snow_col = ee.ImageCollection("MODIS/006/MOD10A1") \
                .filterDate(f"{year}-02-01", f"{year}-03-31").select('NDSI_Snow_Cover')
            max_snow = snow_col.max().clip(upper_amudarya)
            stats = max_snow.reduceRegion(ee.Reducer.mean(), upper_amudarya, 5000).getInfo()
            snow_pc = stats['NDSI_Snow_Cover']

            st.metric(f"{year}-yil Fevral-Mart qor maydoni", f"{snow_pc:.1f}%")
            # Simulyatsiya grafigi
            history = pd.DataFrame({'Yil': [2021, 2022, 2023, 2024], 'Qor (%)': [32, 45, 39, snow_pc if year == 2024 else 41]})
            st.plotly_chart(px.line(history, x='Yil', y='Qor (%)', markers=True, title="Qor qoplami dinamikasi"))

    # --- MODUL 3: MUZLIKLAR ---
    elif mode == "Amudaryo: Muzliklar (Sentinel-2)":
        st.title("🏔 Muzliklar Erishi Monitoringi")
        glacier_roi = ee.Geometry.Rectangle([71.8, 38.2, 72.3, 38.8])
        
        with st.spinner("Muzliklar tahlil qilinmoqda..."):
            s2_g = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(glacier_roi).filterDate(f"{year}-08-01", f"{year}-09-30") \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5)).median()
            
            ndsi = s2_g.normalizedDifference(['B3', 'B11']).rename('NDSI')
            glacier_mask = ndsi.gt(0.4).updateMask(ndsi.gt(0.4)).clip(glacier_roi)
            
            m3 = folium.Map(location=[38.5, 72.0], zoom_start=10)
            m3.add_ee_layer(glacier_mask, {'min': 0, 'max': 1, 'palette': ['white', 'cyan', 'blue']}, 'Muzliklar')
            
            try:
                stats = glacier_mask.multiply(ee.Image.pixelArea()).reduceRegion(
                    reducer=ee.Reducer.sum(), geometry=glacier_roi, scale=100, maxPixels=1e9).getInfo()
                area_km2 = stats['NDSI'] / 1000000
                st.metric("Muzlik maydoni", f"{area_km2:.2f} km²")
            except:
                st.warning("Hisoblashda kechikish.")
            folium_static(m3, width=900)
else:
    st.error("GEE ulanish xatosi. Secrets'ni tekshiring.")
