import streamlit as st
import ee
import json
import pandas as pd
import folium
from streamlit_folium import folium_static
import plotly.express as px

# 1. Sahifa sozlamalari
st.set_page_config(page_title="Amudarya & Shovot Monitoring", layout="wide", page_icon="🛰️")

# 2. GEE Initialize
def init_gee():
    if "gee_key" in st.secrets:
        try:
            key_dict = dict(st.secrets["gee_key"])
            credentials = ee.ServiceAccountCredentials(
                key_dict['client_email'], 
                key_data=json.dumps(key_dict)
            )
            ee.Initialize(credentials)
            return True
        except Exception as e:
            st.error(f"Ulanishda xato: {e}")
    return False

# GEE qatlamini Foliumga qo'shish funksiyasi
def add_ee_layer(self, ee_image_object, vis_params, name):
    try:
        map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
        folium.raster_layers.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='ESA/Google Earth Engine', name=name, overlay=True
        ).add_to(self)
    except:
        pass
folium.Map.add_ee_layer = add_ee_layer

if init_gee():
    # Sidebar Navigatsiya
    st.sidebar.title("🚀 Monitoring Paneli")
    mode = st.sidebar.radio("Modulni tanlang:", 
                            ["Shovot: Oylik EVI (Sentinel-2)", 
                             "Havza: Qor va Muzliklar"])
    
    year = st.sidebar.selectbox("Yilni tanlang", [2022, 2023, 2024], index=1)

    # --- SIZNING HUDUDINGIZNI YUKLASH ---
    # Asset orqali hududni yuklaymiz
    try:
        user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")
        # Xaritani markazlashtirish uchun kordinatalarni olamiz
        roi_centroid = user_roi.geometry().centroid().coordinates().getInfo()
        center_lat, center_lon = roi_centroid[1], roi_centroid[0]
    except Exception as e:
        st.error(f"Asset yuklanmadi: {e}. Iltimos, GEE Asset'ingizda 'Share' tugmasini bosib, hamma uchun (Public) yoki Service Account uchun ruxsat berganingizni tekshiring.")
        user_roi = ee.Geometry.Point([60.3, 41.6]) # Xato bersa zaxira nuqta

    # --- MODUL 1: OYLIK EVI ---
    if mode == "Shovot: Oylik EVI (Sentinel-2)":
        st.title("🛰️ Shovot Tumani (basin3): Oylik EVI Monitoringi")
        month = st.sidebar.slider("Oy", 3, 10, 6)
        months_uz = {3:"Mart", 4:"Aprel", 5:"May", 6:"Iyun", 7:"Iyul", 8:"Avgust", 9:"Sentyabr", 10:"Oktyabr"}
        
        with st.spinner("Sentinel-2 ma'lumotlari tahlil qilinmoqda..."):
            start_date = ee.Date.fromYMD(year, month, 1)
            end_date = start_date.advance(1, 'month')
            
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(user_roi).filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).median()

            evi = s2.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                    'NIR': s2.select('B8').divide(10000),
                    'RED': s2.select('B4').divide(10000),
                    'BLUE': s2.select('B2').divide(10000)
                }).clip(user_roi)

            m1 = folium.Map(location=[center_lat, center_lon], zoom_start=11)
            vis_evi = {'min': 0, 'max': 0.8, 'palette': ['white', '#fcd163', '#99b718', '#207401', '#011301']}
            m1.add_ee_layer(evi, vis_evi, 'EVI Index')
            
            c1, c2 = st.columns([1, 3])
            try:
                stats = evi.reduceRegion(ee.Reducer.mean(), user_roi, 100).getInfo()
                # Sentinel-2 EVI odatda 'constant' nomi bilan chiqadi
                val = stats.get('constant', 0)
                c1.metric(f"{months_uz[month]} EVI", f"{val:.3f}")
            except:
                c1.warning("Raqamli tahlil imkonsiz.")
            with c2:
                folium_static(m1, width=850)

    # --- MODUL 2: QOR VA MUZLIKLAR ---
    elif mode == "Havza: Qor va Muzliklar":
        st.title("🏔 Havza: Qor va Muzliklar Dinamikasi")
        
        tab1, tab2 = st.tabs(["Qor Qoplami (MODIS)", "Muzliklar (Sentinel-2)"])
        
        with tab1:
            with st.spinner("Qor tahlili..."):
                snow_col = ee.ImageCollection("MODIS/006/MOD10A1") \
                    .filterDate(f"{year}-02-01", f"{year}-03-31").select('NDSI_Snow_Cover')
                max_snow = snow_col.max().clip(user_roi)
                stats = max_snow.reduceRegion(ee.Reducer.mean(), user_roi, 5000).getInfo()
                snow_pc = stats.get('NDSI_Snow_Cover', 0)
                
                st.metric(f"{year}-yilgi Qor Maydoni", f"{snow_pc:.1f}%")
                st.plotly_chart(px.bar(x=[year], y=[snow_pc], labels={'x':'Yil', 'y':'Qor %'}, title="Qishki qor ko'rsatkichi"))

        with tab2:
            with st.spinner("Muzliklar tahlili..."):
                s2_g = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                    .filterBounds(user_roi).filterDate(f"{year}-08-01", f"{year}-09-30") \
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5)).median()
                
                ndsi = s2_g.normalizedDifference(['B3', 'B11']).rename('NDSI')
                glacier_mask = ndsi.gt(0.4).updateMask(ndsi.gt(0.4)).clip(user_roi)
                
                m2 = folium.Map(location=[center_lat, center_lon], zoom_start=10)
                m2.add_ee_layer(glacier_mask, {'min': 0, 'max': 1, 'palette': ['cyan', 'blue']}, 'Muzlik')
                folium_static(m2, width=850)
else:
    st.error("Ulanish amalga oshmadi.")
