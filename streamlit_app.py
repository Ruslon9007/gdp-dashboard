import streamlit as st
import ee
import json
import folium
from streamlit_folium import folium_static

# Sahifa sozlamalari
st.set_page_config(page_title="Shovot Map Monitor", layout="wide")

# GEE Initialize (Secrets orqali)
def init_gee():
    if "gee_key" in st.secrets:
        key_dict = dict(st.secrets["gee_key"])
        credentials = ee.ServiceAccountCredentials(key_dict['client_email'], key_data=json.dumps(key_dict))
        ee.Initialize(credentials)
        return True
    return False

if init_gee():
    st.title("🌍 Shovot Tumani: Interaktiv NDVI Xaritasi")
    
    # Sidebar
    year = st.sidebar.slider("Yilni tanlang", 2015, 2024, 2023)
    
    # Shovot ROI (Geometriya)
    shovot_roi = ee.Geometry.Polygon([
        [[60.1, 41.5], [60.5, 41.5], [60.5, 41.8], [60.1, 41.8], [60.1, 41.5]]
    ])

    # Ma'lumotni hisoblash
    dataset = ee.ImageCollection('MODIS/006/MOD13A2') \
        .filterDate(f"{year}-01-01", f"{year}-12-31") \
        .select('NDVI').median().clip(shovot_roi)

    # Xarita yaratish (Markaz: Shovot)
    m = folium.Map(location=[41.65, 60.30], zoom_start=11, tiles="OpenStreetMap")
    
    # GEE qatlamini Foliumga qo'shish uchun yordamchi funksiya
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

    # Ranglar (Qizil - Sariq - Yashil)
    vis_params = {
        'min': 0,
        'max': 8000,
        'palette': ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641']
    }

    # Qatlamni qo'shish
    m.add_ee_layer(dataset, vis_params, 'NDVI Koeffitsiyenti')
    folium.LayerControl().add_to(m)

    # Dashboard interfeysi
    col1, col2 = st.columns([1, 3]) # Xarita kengroq bo'lishi uchun
    
    with col1:
        st.write(f"### {year}-yil hisoboti")
        stats = dataset.reduceRegion(ee.Reducer.mean(), shovot_roi, 1000).getInfo()
        val = stats['NDVI']/10000
        st.metric("O'rtacha NDVI", f"{val:.3f}")
        st.info("Xaritadagi to'q yashil hududlar vegetatsiya yuqori joylarni anglatadi.")

    with col2:
        # Xaritani ekranga chiqarish
        folium_static(m, width=800, height=500)

else:
    st.error("GEE ulanishida xato!")
