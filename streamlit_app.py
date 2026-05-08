import streamlit as st
import ee
import json
import folium
from streamlit_folium import folium_static

# GEE Initialize
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
    st.sidebar.title("🌊 Suv va Ekin Monitoringi")
    mode = st.sidebar.radio("Indeksni tanlang:", ["EVI (O'simliklar)", "NDWI (Suv zaxirasi)"])
    year = st.sidebar.selectbox("Yil", [2022, 2023, 2024], index=1)
    month = st.sidebar.slider("Oy", 3, 10, 6)

    # Assetni yuklash
    user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")
    roi_centroid = user_roi.geometry().centroid().coordinates().getInfo()

    with st.spinner("Ma'lumotlar qayta ishlanmoqda..."):
        start_date = ee.Date.fromYMD(year, month, 1)
        end_date = start_date.advance(1, 'month')

        # Sentinel-2 Kolleksiyasi
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterBounds(user_roi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
            .median()

        m = folium.Map(location=[roi_centroid[1], roi_centroid[0]], zoom_start=11)

        if mode == "EVI (O'simliklar)":
            st.title("🛰️ Sentinel-2: EVI Indeksi")
            # EVI formulasi
            evi = s2.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                    'NIR': s2.select('B8').divide(10000.0),
                    'RED': s2.select('B4').divide(10000.0),
                    'BLUE': s2.select('B2').divide(10000.0)
                }).clip(user_roi)
            
            vis_params = {'min': 0, 'max': 0.8, 'palette': ['white', 'yellow', 'green', 'darkgreen']}
            m.add_ee_layer(evi, vis_params, 'EVI')
            st.info("Yashil ranglar - o'simlik qatlamining zichligini bildiradi.")

        elif mode == "NDWI (Suv zaxirasi)":
            st.title("💧 Sentinel-2: NDWI Suv Indeksi")
            # NDWI formulasi (Green - NIR) / (Green + NIR)
            # Sentinel-2 da Green=B3, NIR=B8
            ndwi = s2.normalizedDifference(['B3', 'B8']).rename('NDWI').clip(user_roi)
            
            # Suv ko'k rangda, quruqlik oq rangda
            vis_params = {'min': -0.5, 'max': 0.5, 'palette': ['white', 'cyan', 'blue']}
            m.add_ee_layer(ndwi, vis_params, 'NDWI')
            st.info("Ko'k ranglar - ochiq suv havzalari va namlik yuqori hududlarni bildiradi.")

        folium_static(m, width=900)
else:
    st.error("GEE ulanmadi.")
