import streamlit as st
import ee
import json
import folium
from streamlit_folium import folium_static

# GEE ulanish (boyagi funksiya)
def init_gee():
    if "gee_key" in st.secrets:
        key_dict = dict(st.secrets["gee_key"])
        credentials = ee.ServiceAccountCredentials(key_dict['client_email'], key_data=json.dumps(key_dict))
        ee.Initialize(credentials)
        return True
    return False

if init_gee():
    st.title("🌍 Shovot Tumani: NDVI Xaritasi")
    
    year = st.sidebar.slider("Yilni tanlang", 2015, 2024, 2023)
    
    # Shovot tumani koordinatalari
    shovot_roi = ee.Geometry.Polygon([
        [[60.1, 41.5], [60.5, 41.5], [60.5, 41.8], [60.1, 41.8], [60.1, 41.5]]
    ])

    # Ma'lumotlarni olish
    dataset = ee.ImageCollection('MODIS/006/MOD13A2') \
        .filterDate(f'{year}-01-01', f'{year}-12-31') \
        .select('NDVI').median().clip(shovot_roi)

    # Xarita yaratish
    m = folium.Map(location=[41.65, 60.30], zoom_start=11)
    
    # GEE qatlamini Foliumga qo'shish funksiyasi
    def add_ee_layer(self, ee_image_object, vis_params, name):
        map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
        folium.raster_layers.TileLayer(
            tiles=map_id_dict['tile_fetcher'].url_format,
            attr='Google Earth Engine',
            name=name,
            overlay=True,
            control=True
        ).add_to(self)

    folium.Map.add_ee_layer = add_ee_layer

    # Ranglar palitrasi (Qizil - sariq - yashil)
    vis_params = {
        'min': 0,
        'max': 8000,
        'palette': ['#e5f5f9', '#99d8c9', '#2ca25f'] # Qurg'oqchildan serhosilgacha
    }

    m.add_ee_layer(dataset, vis_params, 'NDVI')
    
    # Xaritani ko'rsatish
    folium_static(m)
    
    st.write(f"Yuqoridagi xaritada {year}-yilgi o'simlik qoplami ko'rsatilgan. To'q yashil hududlar serhosil yerlarni anglatadi.")
