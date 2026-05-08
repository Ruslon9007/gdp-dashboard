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
    st.title("🛰️ Sentinel-2: EVI Monitoringi (basin3)")
    
    year = st.sidebar.selectbox("Yil", [2022, 2023, 2024], index=1)
    month = st.sidebar.slider("Oy", 3, 10, 6)

    # Assetni yuklash
    user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")
    
    with st.spinner("Tasvirlar qayta ishlanmoqda..."):
        start_date = ee.Date.fromYMD(year, month, 1)
        end_date = start_date.advance(1, 'month')

        # Sentinel-2 kolleksiyasi (Xatolikni oldini olish uchun scale va filterlar tekshirildi)
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterBounds(user_roi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) \
            .median()

        # EVI hisoblash (Kanal nomlarini tekshirib chiqdik: B8-NIR, B4-RED, B2-BLUE)
        # divide(10000.0) float ko'rinishida yozildi
        evi = s2.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': s2.select('B8').divide(10000.0),
                'RED': s2.select('B4').divide(10000.0),
                'BLUE': s2.select('B2').divide(10000.0)
            }).clip(user_roi)

        # Xarita markazini aniqlash
        roi_info = user_roi.geometry().centroid().coordinates().getInfo()
        m = folium.Map(location=[roi_info[1], roi_info[0]], zoom_start=11)

        # VIZUALIZATSIYA SOZLAMASI (Eng muhimi!)
        # min: 0 va max: 0.8 oralig'i ranglarni yorqin ko'rsatadi
        vis_params = {
            'min': 0.0,
            'max': 0.8,
            'palette': [
                'FFFFFF', 'CE7E45', 'DF923D', 'F1B555', 'FCD163', '99B718', 
                '74A901', '66A000', '529400', '3E8601', '207401', '056201', 
                '004C00', '023B01', '012E01', '011D01', '011301'
            ]
        }

        m.add_ee_layer(evi, vis_params, 'EVI Index')
        folium_static(m, width=900)
        
        # Statistika
        try:
            stats = evi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=user_roi,
                scale=100,
                bestEffort=True
            ).getInfo()
            st.write(f"O'rtacha EVI: **{stats.get('constant', 0):.3f}**")
        except:
            st.info("Statistika yuklanmadi, lekin xarita chiqishi kerak.")
