import streamlit as st
import ee
import pandas as pd
import plotly.express as px

def run_fast_monitoring(user_roi):
    st.header("🔬 basin3: Tezkor Ilmiy Tahlil (2018-2025)")
    
    if st.button("Hisoblashni boshlash (Tezkor rejim)"):
        data_list = []
        progress_bar = st.progress(0)
        years = list(range(2018, 2026))
        
        for i, year in enumerate(years):
            try:
                # 1. Yog'ingarchilik - Scale 10000 (10 km) - Trend uchun yetarli
                precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(user_roi) \
                    .filterDate(f'{year}-01-01', f'{year}-12-31').sum() \
                    .reduceRegion(ee.Reducer.mean(), user_roi, 10000).getInfo().get('precipitation', 0)

                # 2. EVI - Scale 1000 (1 km) - Tezroq hisoblash uchun
                s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi) \
                    .filterDate(f'{year}-04-01', f'{year}-10-31') \
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)).median()
                
                evi_val = s2.expression('2.5 * ((B8-B4)/(B8+6*B4-7.5*B2+1))', 
                    {'B8':s2.select('B8').divide(10000),'B4':s2.select('B4').divide(10000),'B2':s2.select('B2').divide(10000)}) \
                    .reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('constant', 0)

                # 3. Harorat (LST) - MODIS
                lst = ee.ImageCollection("MODIS/006/MOD11A1").filterBounds(user_roi) \
                    .filterDate(f'{year}-06-01', f'{year}-08-31').select('LST_Day_1km').mean() \
                    .multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('LST_Day_1km', 0)

                # Tozalash
                clean_evi = evi_val if (evi_val and 0 < evi_val < 1) else 0.15

                data_list.append({
                    'Yil': year,
                    'Precip(mm)': precip,
                    'EVI': clean_evi,
                    'Temp(C)': lst
                })
                progress_bar.progress((i + 1) / len(years))
            except Exception as e:
                print(f"Xato {year}: {e}")
                continue

        df = pd.DataFrame(data_list)
        
        if not df.empty:
            st.success("Ma'lumotlar yuklandi!")
            st.dataframe(df)
            
            # Grafik
            fig = px.line(df, x='Yil', y=['Precip(mm)', 'EVI', 'Temp(C)'], markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Ma'lumot topilmadi. ROI (basin3) yuklanganini tekshiring.")
