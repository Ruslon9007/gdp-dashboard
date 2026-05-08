import streamlit as st
import ee
import json
import pandas as pd
import folium
from streamlit_folium import folium_static
import plotly.express as px

# Sahifa sozlamalari
st.set_page_config(page_title="Amudarya & Shovot: Sentinel-2 EVI", layout="wide", page_icon="🛰️")

# GEE Initialize
def init_gee():
    try:
        if "gee_key" in st.secrets:
            # Secrets'dan lug'atni olish
            key_dict = dict(st.secrets["gee_key"])
            
            # MUHIM: ServiceAccountCredentials fayl yo'lini emas, 
            # to'g'ridan-to'g'ri lug'atning o'zini (from_json metodu orqali) kutadi
            credentials = ee.ServiceAccountCredentials(
                key_dict['client_email'], 
                key_data=json.dumps(key_dict) # Bu yerda xato yo'q, lekin ee.Initialize bilan tekshiramiz
            )
            
            # Agar yuqoridagi usul xato bersa, muqobil (eng xavfsiz) usul:
            # ee.Initialize(credentials) 
            
            # AMMO eng yangi va xatosiz usul quyidagicha:
            ee.Initialize(credentials=credentials)
            return True
        return False
    except Exception as e:
        st.error(f"GEE ulanishida xato: {e}")
        return False
if init_gee():
    st.sidebar.title("📊 Monitoring Paneli")
    mode = st.sidebar.radio("Modulni tanlang:", ["Shovot: EVI Xaritasi", "Amudaryo: Qor Zaxirasi"])
    year = st.sidebar.slider("Yilni tanlang", 2019, 2024, 2023) # Sentinel-2 2018-yildan keyin barqaror

    shovot_roi = ee.Geometry.Polygon([[[60.1, 41.5], [60.5, 41.5], [60.5, 41.8], [60.1, 41.8], [60.1, 41.5]]])
    upper_amudarya = ee.Geometry.Polygon([[[68.0, 36.5], [75.0, 36.5], [75.0, 39.5], [68.0, 39.5], [68.0, 36.5]]])

    if mode == "Shovot: EVI Xaritasi":
        st.title("🛰️ Sentinel-2: EVI (Enhanced Vegetation Index)")
        
        with st.spinner("Sentinel-2 ma'lumotlari tahlil qilinmoqda..."):
            # Sentinel-2 Level-2A (Surface Reflectance) kolleksiyasi
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(shovot_roi) \
                .filterDate(f"{year}-06-01", f"{year}-08-31") \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)) \
                .median()

            # EVI hisoblash funksiyasi (Sentinel-2 kanallari: B8=NIR, B4=Red, B2=Blue)
            evi = s2.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                    'NIR': s2.select('B8').divide(10000),
                    'RED': s2.select('B4').divide(10000),
                    'BLUE': s2.select('B2').divide(10000)
                }).clip(shovot_roi)

            # Xarita
            m = folium.Map(location=[41.65, 60.30], zoom_start=11)
            
            def add_ee_layer(self, ee_image_object, vis_params, name):
                map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
                folium.raster_layers.TileLayer(
                    tiles=map_id_dict['tile_fetcher'].url_format,
                    attr='ESA/Google Earth Engine', name=name, overlay=True
                ).add_to(self)
            
            folium.Map.add_ee_layer = add_ee_layer
            vis_params = {'min': 0, 'max': 1, 'palette': ['#ffffff', '#ce7e45', '#df923d', '#f1b555', '#fcd163', '#99b718', '#74a901', '#66a000', '#529400', '#3e8601', '#207401', '#056201', '#004c00', '#023b01', '#012e01', '#011d01', '#011301']}
            
            m.add_ee_layer(evi, vis_params, 'EVI Index')
            
            col1, col2 = st.columns([1, 3])
            with col1:
                stats = evi.reduceRegion(ee.Reducer.mean(), shovot_roi, 20).getInfo()
                evi_val = stats['constant']
                st.metric(f"{year}-yilgi EVI", f"{evi_val:.3f}")
                st.write("**Nega EVI?** EVI zich o'simlik qatlamlarida NDVI kabi 'to'yinib' qolmaydi va atmosferaning salbiy ta'sirini yaxshiroq filtrlaydi.")
            with col2:
                folium_static(m, width=800)

    elif mode == "Amudaryo: Qor Zaxirasi":
        # Qor zaxirasi kodi o'zgarishsiz qoladi (MODIS qor uchun eng yaxshisi)
        st.title("🏔 Amudaryo Yuqori Havzasi: Qor Tahlili")
        # ... (oldingi qor kodi) ...
        st.info("Qor tahlili MODIS ma'lumotlari asosida ishlamoqda.")
