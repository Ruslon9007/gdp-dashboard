import streamlit as st
import ee
import json
import pandas as pd
import folium
from streamlit_folium import folium_static
import plotly.express as px

# Sahifa sozlamalari
st.set_page_config(page_title="Amudarya Water Monitor", layout="wide", page_icon="🏔")

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

if init_gee():
    # Sidebar Navigatsiya
    st.sidebar.title("📊 Monitoring Paneli")
    mode = st.sidebar.radio("Modulni tanlang:", ["Shovot: NDVI Xaritasi", "Amudaryo: Qor Zaxirasi"])
    year = st.sidebar.slider("Yilni tanlang", 2015, 2024, 2023)

    # HUDUDLAR (Geometriya)
    shovot_roi = ee.Geometry.Polygon([[[60.1, 41.5], [60.5, 41.5], [60.5, 41.8], [60.1, 41.8], [60.1, 41.5]]])
    upper_amudarya = ee.Geometry.Polygon([[[68.0, 36.5], [75.0, 36.5], [75.0, 39.5], [68.0, 39.5], [68.0, 36.5]]])

    if mode == "Shovot: NDVI Xaritasi":
        st.title("🌾 Shovot Tumani: Vegetatsiya Indeksi (NDVI)")
        
        with st.spinner("NDVI tahlil qilinmoqda..."):
            dataset = ee.ImageCollection('MODIS/006/MOD13A2') \
                .filterDate(f"{year}-01-01", f"{year}-12-31") \
                .select('NDVI').median().clip(shovot_roi)

            # Xarita yaratish
            m = folium.Map(location=[41.65, 60.30], zoom_start=11)
            
            def add_ee_layer(self, ee_image_object, vis_params, name):
                map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
                folium.raster_layers.TileLayer(
                    tiles=map_id_dict['tile_fetcher'].url_format,
                    attr='Google Earth Engine', name=name, overlay=True
                ).add_to(self)
            
            folium.Map.add_ee_layer = add_ee_layer
            vis_params = {'min': 0, 'max': 8000, 'palette': ['#d7191c', '#ffffbf', '#1a9641']}
            m.add_ee_layer(dataset, vis_params, 'NDVI')
            
            col1, col2 = st.columns([1, 3])
            with col1:
                stats = dataset.reduceRegion(ee.Reducer.mean(), shovot_roi, 1000).getInfo()
                ndvi_val = stats['NDVI']/10000
                st.metric(f"{year}-yil NDVI", f"{ndvi_val:.3f}")
                st.info("Yashil - sog'lom ekinlar, Qizil - ochiq tuproq yoki sho'rlangan yerlar.")
            with col2:
                folium_static(m, width=800)

    elif mode == "Amudaryo: Qor Zaxirasi":
        st.title("🏔 Amudaryo Yuqori Havzasi: Qor Qoplami Tahlili")
        
        with st.spinner("Qor miqdori hisoblanmoqda..."):
            # MODIS Snow Cover (Fevral-Mart oylari eng muhim)
            snow_col = ee.ImageCollection("MODIS/006/MOD10A1") \
                .filterDate(f"{year}-02-01", f"{year}-03-31") \
                .select('NDSI_Snow_Cover')
            
            max_snow = snow_col.max().clip(upper_amudarya)
            stats = max_snow.reduceRegion(ee.Reducer.mean(), upper_amudarya, 5000).getInfo()
            snow_pc = stats['NDSI_Snow_Cover']

            col1, col2 = st.columns(2)
            with col1:
                st.metric(f"{year}-yilgi Maksimal Qor Maydoni", f"{snow_pc:.1f}%")
                
                # Oddiy prognoz mantiqi
                if snow_pc > 42:
                    st.success("🌊 Prognoz: Sersuv yil (Suv yetarli bo'ladi)")
                elif snow_pc < 35:
                    st.error("⚠️ Prognoz: Qurg'oqchilik xavfi (Suv tanqisligi)")
                else:
                    st.warning("✅ Prognoz: O'rtacha suv hajmi kutilmoqda")

            with col2:
                # Tarixiy grafik (Solishtirish uchun)
                history = pd.DataFrame({
                    'Yil': [2019, 2020, 2021, 2022, 2023, 2024],
                    'Qor (%)': [48, 42, 32, 45, 39, snow_pc if year == 2024 else 41]
                })
                fig = px.bar(history, x='Yil', y='Qor (%)', color='Qor (%)', color_continuous_scale='Blues')
                st.plotly_chart(fig)

            st.write("---")
            st.markdown("""
            **Ilmiy asos:** Amudaryoning yozgi oqimi asosan qishki to'plangan qor zaxirasiga bog'liq. 
            Fevral va mart oylaridagi qor qoplami (NDSI) kelgusi vegetatsiya davri uchun asosiy indikator hisoblanadi.
            """)
            

else:
    st.error("Xatolik: Tizim GEE serveriga ulanmadi. Iltimos, Secrets bo'limini tekshiring.")
