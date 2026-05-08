import streamlit as st
import ee
import json
import pandas as pd
import folium
from streamlit_folium import folium_static
import plotly.express as px

# Sahifa sozlamalari
st.set_page_config(page_title="Amudarya & Shovot Monitoring", layout="wide", page_icon="🛰️")

# 1. GEE Initialize (Secrets orqali)
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
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='ESA/Google Earth Engine', name=name, overlay=True
    ).add_to(self)
folium.Map.add_ee_layer = add_ee_layer

if init_gee():
    st.sidebar.title("📊 Monitoring Paneli")
    mode = st.sidebar.radio("Modulni tanlang:", 
                            ["Shovot: EVI Xaritasi (Sentinel-2)", 
                             "Amudaryo: Qor Zaxirasi", 
                             "Amudaryo: Muzliklar Tahlili"])
    
    year = st.sidebar.slider("Yilni tanlang", 2019, 2024, 2023)

    # HUDUDLAR
    shovot_roi = ee.Geometry.Polygon([[[60.1, 41.5], [60.5, 41.5], [60.5, 41.8], [60.1, 41.8], [60.1, 41.5]]])
    upper_amudarya = ee.Geometry.Polygon([[[68.0, 36.5], [75.0, 36.5], [75.0, 39.5], [68.0, 39.5], [68.0, 36.5]]])

    if mode == "Shovot: EVI Xaritasi (Sentinel-2)":
        st.title("🛰️ Sentinel-2: EVI (Enhanced Vegetation Index)")
        with st.spinner("Sentinel-2 ma'lumotlari tahlil qilinmoqda..."):
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(shovot_roi) \
                .filterDate(f"{year}-06-01", f"{year}-08-31") \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)).median()

            evi = s2.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                    'NIR': s2.select('B8').divide(10000),
                    'RED': s2.select('B4').divide(10000),
                    'BLUE': s2.select('B2').divide(10000)
                }).clip(shovot_roi)

            m = folium.Map(location=[41.65, 60.30], zoom_start=11)
            vis_params = {'min': 0, 'max': 1, 'palette': ['white', 'orange', 'yellow', 'green', 'darkgreen']}
            m.add_ee_layer(evi, vis_params, 'EVI Index')
            
            col1, col2 = st.columns([1, 3])
            with col1:
                stats = evi.reduceRegion(ee.Reducer.mean(), shovot_roi, 20).getInfo()
                evi_val = stats['constant']
                st.metric(f"{year}-yilgi EVI", f"{evi_val:.3f}")
            with col2:
                folium_static(m, width=850)

    elif mode == "Amudaryo: Qor Zaxirasi":
        st.title("🏔 Qishki Qor Qoplami Monitoringi")
        with st.spinner("Qor miqdori hisoblanmoqda..."):
            snow_col = ee.ImageCollection("MODIS/006/MOD10A1") \
                .filterDate(f"{year}-02-01", f"{year}-03-31").select('NDSI_Snow_Cover')
            max_snow = snow_col.max().clip(upper_amudarya)
            stats = max_snow.reduceRegion(ee.Reducer.mean(), upper_amudarya, 5000).getInfo()
            snow_pc = stats['NDSI_Snow_Cover']
            
            st.metric(f"{year}-yilgi Maksimal Qor Maydoni", f"{snow_pc:.1f}%")
            history = pd.DataFrame({'Yil': [2021, 2022, 2023, 2024], 'Qor (%)': [32, 45, 39, snow_pc if year == 2024 else 41]})
            st.plotly_chart(px.bar(history, x='Yil', y='Qor (%)', title="Yillik qor dinamikasi"))

    elif mode == "Amudaryo: Muzliklar Tahlili":
        st.title("🏔 Muzliklarning Erish Dinamikasi (Sentinel-2)")
        glacier_roi = ee.Geometry.Rectangle([71.5, 38.0, 72.5, 39.0])
        with st.spinner("Muzliklar tahlil qilinmoqda..."):
            s2_g = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(glacier_roi).filterDate(f"{year}-08-01", f"{year}-09-30") \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5)).median()
            
            ndsi = s2_g.normalizedDifference(['B3', 'B11']).rename('NDSI')
            glacier_mask = ndsi.gt(0.4).clip(glacier_roi)
            
            m_g = folium.Map(location=[38.5, 72.0], zoom_start=9)
            m_g.add_ee_layer(glacier_mask, {'min': 0, 'max': 1, 'palette': ['white', 'blue']}, 'Glaciers')
            
            stats = glacier_mask.multiply(ee.Image.pixelArea()).reduceRegion(ee.Reducer.sum(), glacier_roi, 20).getInfo()
            area_km2 = stats['NDSI'] / 1000000
            st.metric("Muzlik maydoni (taxminan)", f"{area_km2:.2f} km²")
            folium_static(m_g, width=850)
else:
    st.error("GEE ulanishida xatolik yuz berdi.")
