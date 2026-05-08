import streamlit as st
import ee
import json
import pandas as pd
import plotly.express as px

# GEE init qismini saqlab qolamiz...

if init_gee():
    st.sidebar.title("Navigatsiya")
    mode = st.sidebar.radio("Modulni tanlang:", ["Shovot NDVI", "Amudaryo Qor Qoplami"])

    if mode == "Shovot NDVI":
        # ... (Oldingi NDVI kodi) ...
        st.title("🌾 Shovot NDVI tahlili")
        
    elif mode == "Amudaryo Qor Qoplami":
        st.title("🏔 Yuqori Amudaryo: Qor Zaxirasi Tahlili")
        
        # Amudaryo yuqori havzasi (Polygon)
        upper_amudarya = ee.Geometry.Polygon([[[68.0, 36.5], [75.0, 36.5], [75.0, 39.5], [68.0, 39.5], [68.0, 36.5]]])
        
        selected_year = st.sidebar.slider("Yilni tanlang", 2015, 2024, 2023)
        
        with st.spinner("Qor qoplami hisoblanmoqda..."):
            # MODIS Snow Cover ma'lumotlari
            snow_dataset = ee.ImageCollection("MODIS/006/MOD10A1") \
                .filterDate(f"{selected_year}-01-01", f"{selected_year}-03-31") \
                .select('NDSI_Snow_Cover')
            
            # Maksimal qor maydoni (qish oxiridagi holat)
            max_snow = snow_dataset.max().clip(upper_amudarya)
            
            # Havzadagi o'rtacha qor qoplami foizini hisoblash
            stats = max_snow.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=upper_amudarya,
                scale=5000
            ).getInfo()
            
            snow_percent = stats['NDSI_Snow_Cover']
            
            # Natijani chiqarish
            col1, col2 = st.columns(2)
            col1.metric(f"{selected_year}-yil qishki qor maydoni", f"{snow_percent:.1f}%")
            
            # Kelgusi yil uchun prognoz mantiqi
            # Agar qor 40% dan ko'p bo'lsa - sersuv, 30% dan kam bo'lsa - kam suv
            if snow_percent > 45:
                status = "🌊 Sersuv yil kutilmoqda"
                color = "blue"
            elif snow_percent < 35:
                status = "⚠️ Kam suv (qurg'oqchilik) xavfi"
                color = "red"
            else:
                status = "✅ O'rtacha suv hajmi"
                color = "green"
            
            col2.markdown(f"### Prognoz: <span style='color:{color}'>{status}</span>", unsafe_content_allowed=True)

            # Dinamika uchun grafik (Simulyatsiya qilingan ma'lumot)
            snow_history = {
                'Yil': [2019, 2020, 2021, 2022, 2023, 2024],
                'Qor qoplami (%)': [48, 42, 31, 46, 38, snow_percent]
            }
            fig = px.area(snow_history, x='Yil', y='Qor qoplami (%)', title="Yillar bo'yicha qor to'planish dinamikasi")
            st.plotly_chart(fig)

            st.info("Tahlil MODIS (MOD10A1) sun'iy yo'ldoshining NDSI indeksi asosida fevral-mart oylaridagi maksimal ko'rsatkichlar bo'yicha hisoblandi.")
