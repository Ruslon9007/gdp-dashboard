import streamlit as st
import ee
import pandas as pd
import plotly.express as px

def show_complex_graphs(user_roi):
    st.header("📊 basin3: Ko'p yillik dinamika (2018-2025)")
    
    # 1. Ma'lumotlarni yig'ish (Oylik o'rtacha qiymatlar uchun)
    years = range(2018, 2026)
    
    # Ma'lumotlarni saqlash uchun ro'yxat
    data_list = []

    with st.spinner("GEE serveridan real ma'lumotlar olinmoqda..."):
        # Misol tariqasida EVI va Yog'ingarchilik trendini hisoblash
        # (Barcha 7 ta ko'rsatkichni bir vaqtda hisoblash timeout bermasligi uchun yillik o'rtacha olamiz)
        for year in years:
            # Yog'ingarchilik (CHIRPS)
            precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY") \
                .filterBounds(user_roi) \
                .filterDate(f'{year}-01-01', f'{year}-12-31') \
                .sum().reduceRegion(ee.Reducer.mean(), user_roi, 5000).getInfo()
            
            # EVI (Sentinel-2) - Vegetatsiya davri (Apr-Okt)
            s2_evi = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(user_roi) \
                .filterDate(f'{year}-04-01', f'{year}-10-30') \
                .median()
            
            evi_val = s2_evi.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                    'NIR': s2_evi.select('B8').divide(10000),
                    'RED': s2_evi.select('B4').divide(10000),
                    'BLUE': s2_evi.select('B2').divide(10000)
                }).reduceRegion(ee.Reducer.mean(), user_roi, 250).getInfo()

            # Ma'lumotlarni yig'ish
            data_list.append({
                'Yil': year,
                'Yogingarchilik (mm)': precip.get('precipitation', 0),
                'EVI': evi_val.get('constant', 0)
            })

    # Pandas DataFrame yaratish
    df = pd.DataFrame(data_list)

    # 2. Grafik: Yog'ingarchilik va EVI korrelyatsiyasi
    fig = px.line(df, x='Yil', y=['Yogingarchilik (mm)', 'EVI'], 
                  title="Yog'ingarchilik va Vegetatsiya o'rtasidagi bog'liqlik",
                  markers=True, line_shape='spline')
    
    # Ikkinchi o'qni qo'shish (EVI uchun)
    fig.update_layout(yaxis2=dict(title='EVI', overlaying='y', side='right'))
    st.plotly_chart(fig, use_container_width=True)

    # 3. Ma'lumotlar jadvali
    st.subheader("📋 Raqamli ma'lumotlar (Export uchun)")
    st.dataframe(df)
    
    # CSV yuklab olish tugmasi
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Ma'lumotlarni CSV ko'rinishida yuklash", csv, "basin3_data_2018_2025.csv", "text/csv")
