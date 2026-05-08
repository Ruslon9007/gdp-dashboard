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
            attr='ESA/Sentinel-1', name=name, overlay=True
        ).add_to(self)
    except:
        pass
folium.Map.add_ee_layer = add_ee_layer

if init_gee():
    st.title("🛰️ Sentinel-1: Radar asosida Suv Monitoringi")
    
    year = st.sidebar.selectbox("Yil", [2023, 2024], index=1)
    month = st.sidebar.slider("Oy", 1, 12, 5)

    # Assetni yuklash (basin3)
    user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")
    roi_centroid = user_roi.geometry().centroid().coordinates().getInfo()

    with st.spinner("Radar ma'lumotlari yuklanmoqda..."):
        start_date = ee.Date.fromYMD(year, month, 1)
        end_date = start_date.advance(1, 'month')

        # Sentinel-1 SAR GRD Kolleksiyasi
        s1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
            .filterBounds(user_roi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
            .filter(ee.Filter.eq('instrumentMode', 'IW')) \
            .median() \
            .clip(user_roi)

        # Suvni ajratib olish (Thresholding)
        # Odatda -18 dB dan past qiymatlar ochiq suvni bildiradi
        water_mask = s1.select('VV').lt(-18).rename('Water')
        # Faqat suv bo'lgan joylarni qoldirish
        water_only = water_mask.updateMask(water_mask)

        m = folium.Map(location=[roi_centroid[1], roi_centroid[0]], zoom_start=11)

        # 1. Asosiy radar ko'rinishi (Oq-qora)
        s1_vis = {'bands': ['VV'], 'min': -25, 'max': 0}
        m.add_ee_layer(s1.select('VV'), s1_vis, 'Sentinel-1 VV (Radar)')

        # 2. Aniqlangan suv qatlami (Ko'k rangda)
        m.add_ee_layer(water_only, {'palette': ['blue']}, 'Aniqlangan Suv yuzasi')

        folium_static(m, width=900)
        
        st.info("""
        **Sentinel-1 SAR Tahlili:**
        * Xaritadagi **qora hududlar** - radar nurlarini qaytarmaydigan silliq yuzalar (suv havzalari, kanallar).
        * Ko'k qatlam - algoritm tomonidan avtomatik ajratilgan suv maydonlari.
        * Radar bulutlardan o'tib ketgani uchun natija har qanday ob-havoda aniq chiqadi.
        """)
else:
    st.error("GEE ulanmadi.")
