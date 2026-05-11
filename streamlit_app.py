import streamlit as st
import ee
import pandas as pd
import plotly.express as px
import json

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
            st.error(f"GEE ulanish xatosi: {e}")
    return False

if init_gee():
    st.title("📊 basin3: Gidro-Agro Monitoring (2018-2025)")
    
    # Assetni yuklash
    user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")
    
    # Tugma bosilganda hisoblashni boshlash
    if st.button("Grafik ma'lumotlarini hisoblash"):
        data_list = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        years = list(range(2018, 2026))
        
        for i, year in enumerate(years):
            try:
                status_text.text(f"Hisoblanmoqda: {year}-yil...")
                
                # 1. Yog'ingarchilik (CHIRPS) - Yillik jami
                precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY") \
                    .filterBounds(user_roi).filterDate(f'{year}-01-01', f'{year}-12-31') \
                    .sum().reduceRegion(ee.Reducer.mean(), user_roi, 5000).getInfo()

                # 2. EVI (Sentinel-2) - Vegetatsiya davri (Apr-Okt)
                s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                    .filterBounds(user_roi).filterDate(f'{year}-04-01', f'{year}-10-31') \
                    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)).median()
                
                evi = s2.expression(
                    '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                        'NIR': s2.select('B8').divide(10000.0),
                        'RED': s2.select('B4').divide(10000.0),
                        'BLUE': s2.select('B2').divide(10000.0)
                    }).reduceRegion(ee.Reducer.mean(), user_roi, 500).getInfo()

                # 3. Bug'lanish (ET - MODIS)
                et = ee.ImageCollection("MODIS/006/MOD16A2") \
                    .filterBounds(user_roi).filterDate(f'{year}-01-01', f'{year}-12-31') \
                    .sum().reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo()

                # Ma'lumotlarni lug'atga yig'ish
                data_list.append({
                    'Yil': year,
                    'Yogingarchilik (mm)': precip.get('precipitation', 0),
                    'EVI (Vegetatsiya)': evi.get('constant', 0),
                    'Buglanish (ET)': et.get('ET', 0)
                })
                
                progress_bar.progress((i + 1) / len(years))
            except Exception as e:
                st.warning(f"{year}-yil uchun ma'lumot yetarli emas.")

        # DataFrame yaratish
        df = pd.DataFrame(data_list)

        if not df.empty:
            # GRAFIK 1: Yog'ingarchilik va ET
            st.subheader("⛈ Yog'ingarchilik va Bug'lanish trendi")
            fig1 = px.bar(df, x='Yil', y=['Yogingarchilik (mm)', 'Buglanish (ET)'], barmode='group')
            st.plotly_chart(fig1, use_container_width=True)

            # GRAFIK 2: EVI dinamikasi
            st.subheader("🌿 Vegetatsiya (EVI) ko'p yillik o'zgarishi")
            fig2 = px.line(df, x='Yil', y='EVI (Vegetatsiya)', markers=True, line_shape='spline')
            fig2.update_traces(line_color='green')
            st.plotly_chart(fig2, use_container_width=True)

            # JADVAL
            st.subheader("📋 Raqamli ma'lumotlar jadvali")
            st.dataframe(df.style.format(precision=3))
            
            # CSV yuklab olish
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Ma'lumotlarni CSV yuklash", csv, "basin3_data.csv", "text/csv")
        
        status_text.text("Hisoblash yakunlandi!")
else:
    st.error("Secrets qismida 'gee_key' topilmadi!")
