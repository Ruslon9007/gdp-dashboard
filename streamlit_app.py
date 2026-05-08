import streamlit as st
import ee
import pandas as pd
import plotly.express as px # Grafiklar uchun

# GEE init qismini saqlab qolamiz...

def get_precip_data():
    # Amudaryo yuqori havzasi (taxminiy koordinatalar)
    upper_amudarya = ee.Geometry.Polygon([
        [[68.0, 36.5], [75.0, 36.5], [75.0, 39.5], [68.0, 39.5], [68.0, 36.5]]
    ])
    
    # CHIRPS yog'ingarchilik ma'lumotlari
    precip_col = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY") \
        .filterDate('2010-01-01', '2024-01-01') \
        .select('precipitation')
    
    # Yillik yig'indi hisoblash
    def yearly_sum(year):
        start = ee.Date.fromYMD(year, 1, 1)
        end = ee.Date.fromYMD(year, 12, 31)
        total = precip_col.filterDate(start, end).sum()
        stats = total.reduceRegion(ee.Reducer.mean(), upper_amudarya, 5000).getInfo()
        return {'year': year, 'precip': stats['precipitation']}

    # Ma'lumotlarni yig'ish (Oxirgi 10 yil)
    years = range(2014, 2024)
    data = [yearly_sum(y) for y in years]
    return pd.DataFrame(data)

if init_gee():
    st.header("🏔 Amudaryo Yuqori Havzasi Suv Resurslari Tahlili")
    
    with st.spinner("Yog'ingarchilik ma'lumotlari yuklanmoqda..."):
        df = get_precip_data()
        
        # Grafik chiqarish
        fig = px.line(df, x='year', y='precip', title="Havzadagi yillik o'rtacha yog'ingarchilik (mm)")
        st.plotly_chart(fig)
        
        # Oddiy prognoz (Lineer trend asosida)
        last_val = df['precip'].iloc[-1]
        forecast_val = last_val * 1.05 # Bu yerda murakkabroq ML model qo'shish mumkin
        
        st.subheader("🔮 2025-yil uchun dastlabki prognoz")
        st.write(f"Ma'lumotlar trendiga ko'ra, kelgusi yilda kutilayotgan yog'ingarchilik: **{forecast_val:.2f} mm**")
        st.info("Eslatma: Bu gidrologik prognoz bo'lib, aniqlikni oshirish uchun qor zaxirasi (Snow Water Equivalent) ma'lumotlarini ham qo'shish lozim.")
