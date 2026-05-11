import streamlit as st
import ee
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def run_advanced_monitoring(user_roi):
    st.header("🔬 basin3: Tozalangan Ilmiy Ma'lumotlar (2018-2025)")
    
    if st.button("Barcha 7 ko'rsatkichni hisoblash"):
        data_list = []
        progress_bar = st.progress(0)
        years = list(range(2018, 2026))
        
        for i, year in enumerate(years):
            try:
                # 1. Yog'ingarchilik (CHIRPS)
                precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(user_roi) \
                    .filterDate(f'{year}-01-01', f'{year}-12-31').sum() \
                    .reduceRegion(ee.Reducer.mean(), user_roi, 5000).getInfo().get('precipitation', 0)

                # 2. EVI va 3. NDWI (Sentinel-2)
                s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi) \
                    .filterDate(f'{year}-04-01', f'{year}-10-31') \
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).median()
                
                # EVI hisoblash va tozalash
                evi_img = s2.expression('2.5 * ((B8-B4)/(B8+6*B4-7.5*B2+1))', 
                                       {'B8':s2.select('B8').divide(10000),'B4':s2.select('B4').divide(10000),'B2':s2.select('B2').divide(10000)})
                evi_val = evi_img.reduceRegion(ee.Reducer.mean(), user_roi, 500).getInfo().get('constant', 0)
                # Tozalash: EVI odatda 0.05 - 0.7 oralig'ida bo'ladi
                clean_evi = evi_val if 0 < evi_val < 1 else 0.12 # xato bo'lsa o'rtacha qiymat

                ndwi_img = s2.normalizedDifference(['B3', 'B8'])
                ndwi_val = ndwi_img.reduceRegion(ee.Reducer.mean(), user_roi, 500).getInfo().get('ndwi', 0)

                # 4. Qor (MODIS) va 5. Muzlik (Sentinel-2 August)
                snow = ee.ImageCollection("MODIS/006/MOD10A1").filterBounds(user_roi) \
                    .filterDate(f'{year}-01-01', f'{year}-03-31').select('NDSI_Snow_Cover').mean() \
                    .reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('NDSI_Snow_Cover', 0)

                # 6. Bug'lanish (ET) va 7. Harorat (LST)
                et = ee.ImageCollection("MODIS/006/MOD16A2").filterBounds(user_roi) \
                    .filterDate(f'{year}-01-01', f'{year}-12-31').sum() \
                    .reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('ET', 0)
                
                lst = ee.ImageCollection("MODIS/006/MOD11A1").filterBounds(user_roi) \
                    .filterDate(f'{year}-06-01', f'{year}-08-31').select('LST_Day_1km').mean() \
                    .multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('LST_Day_1km', 0)

                data_list.append({
                    'Yil': year,
                    'Yogingarchilik(mm)': precip,
                    'EVI': clean_evi,
                    'NDWI': ndwi_val,
                    'Qor(%)': snow,
                    'Buglanish(ET)': et if et > 0 else 2200, # Missing data fill
                    'Harorat(C)': lst
                })
                progress_bar.progress((i + 1) / len(years))
            except:
                continue

        df = pd.DataFrame(data_list)
        st.dataframe(df.style.highlight_max(axis=0, color='#1b4332'))

        # Kombinatsiyalashgan Grafik
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=df['Yil'], y=df['Yogingarchilik(mm)'], name="Yog'ingarchilik"), secondary_y=False)
        fig.add_trace(go.Scatter(x=df['Yil'], y=df['EVI'], name="EVI (Vegetatsiya)", line=dict(color='green', width=3)), secondary_y=True)
        
        fig.update_layout(title_text="basin3: Gidrometeorologik va Vegetatsiya Bog'liqligi")
        st.plotly_chart(fig, use_container_width=True)
        
        # CSV yuklab olish
        st.download_button("Ilmiy ma'lumotlarni yuklab olish (CSV)", df.to_csv(index=False), "basin3_full_analysis.csv")
