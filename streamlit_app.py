import streamlit as st
import ee
import json
import pandas as pd
import datetime

# Sahifa sarlavhasi
st.set_page_config(page_title="Shovot Drought Monitor", page_icon="🌾")

# 1. GEE ni Initialize qilish (Secrets orqali)
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
    st.sidebar.success("✅ GEE Onlayn")
    
    st.title("🌾 Shovot Tumani Qurg'oqchilik Monitoringi")
    st.markdown("Ushbu platforma Google Earth Engine ma'lumotlari asosida real vaqtda tahlil o'tkazadi.")

    # 2. Shovot tumani koordinatalari (Geometriya)
    # Shovot tumani uchun taxminiy chegara (Polygon)
    shovot_roi = ee.Geometry.Polygon([
        [[60.1, 41.5], [60.5, 41.5], [60.5, 41.8], [60.1, 41.8], [60.1, 41.5]]
    ])

    # 3. Vaqtni tanlash (Sidebar)
    year = st.sidebar.slider("Yilni tanlang", 2015, 2024, 2023)
    
    # 4. MODIS NDVI ma'lumotlarini olish
    with st.spinner("GEE ma'lumotlari hisoblanmoqda..."):
        dataset = ee.ImageCollection('MODIS/006/MOD13A2') \
            .filterDate(f"{year}-01-01", f"{year}-12-31") \
            .select('NDVI')
        
        median_ndvi = dataset.median().clip(shovot_roi)
        
        # O'rtacha qiymatni hisoblash (ReduceRegion)
        stats = median_ndvi.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=shovot_roi,
            scale=1000
        ).getInfo()

    # 5. Natijalarni ko'rsatish
    if stats and 'NDVI' in stats:
        current_ndvi = stats['NDVI'] / 10000 # MODIS NDVI 0.0001 koeffitsiyentga ega
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label=f"{year}-yil uchun o'rtacha NDVI", value=f"{current_ndvi:.3f}")
        
        with col2:
            status = "Yaxshi" if current_ndvi > 0.4 else "Qurg'oqchilik xavfi"
            st.metric(label="Holat", value=status)

        st.info(f"Ma'lumotlar {year}-yil davomidagi o'rtacha (median) ko'rsatkichlar asosida hisoblandi.")
    else:
        st.warning("Ushbu yil uchun ma'lumot topilmadi.")

else:
    st.error("Xatolik: GEE autentifikatsiyadan o'tmadi. Secrets bo'limini tekshiring.")
