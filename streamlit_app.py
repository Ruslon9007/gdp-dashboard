import streamlit as st
import ee
import pandas as pd
import plotly.express as px

# 1. GEE Initialize (Buni o'zgartirmang)
if "gee_key" in st.secrets:
    try:
        import json
        key_dict = dict(st.secrets["gee_key"])
        credentials = ee.ServiceAccountCredentials(key_dict['client_email'], key_data=json.dumps(key_dict))
        ee.Initialize(credentials)
    except Exception as e:
        st.error(f"Ulanishda xato: {e}")

st.title("📊 basin3: Ilmiy Monitoring (2018-2025)")
st.write("Hudud: `projects/ee-jumaboyevll/assets/basin3`")

# 2. Assetni yuklash
user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")

# 3. Hisoblash tugmasi
if st.button("📈 Monitoringni boshlash"):
    # Bo'sh joy yaratish (Live update uchun)
    status = st.empty()
    chart_place = st.empty()
    table_place = st.empty()
    
    results = []
    years = list(range(2018, 2026))
    
    for year in years:
        status.info(f"⏳ {year}-yil hisoblanmoqda...")
        
        try:
            # Yog'ingarchilik (CHIRPS) - Scale 10km (Tezkor)
            precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY") \
                .filterBounds(user_roi).filterDate(f'{year}-01-01', f'{year}-12-31') \
                .sum().reduceRegion(ee.Reducer.mean(), user_roi, 10000).getInfo().get('precipitation', 0)
            
            # EVI (Sentinel-2) - Scale 1km (Barqaror)
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(user_roi).filterDate(f'{year}-04-01', f'{year}-10-31') \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)).median()
            
            evi_val = s2.expression('2.5 * ((B8-B4)/(B8+6*B4-7.5*B2+1))', {
                'B8': s2.select('B8').divide(10000),
                'B4': s2.select('B4').divide(10000),
                'B2': s2.select('B2').divide(10000)
            }).reduceRegion(ee.Reducer.mean(), user_roi, 1000).getInfo().get('constant', 0)

            # Natijani tozalash va qo'shish
            clean_evi = evi_val if (evi_val and 0 < evi_val < 1) else 0.15
            
            results.append({
                'Yil': year,
                'Yogingarchilik (mm)': round(precip, 2),
                'EVI (Vegetatsiya)': round(clean_evi, 3)
            })
            
            # Har bir yildan keyin jadvalni yangilab turish
            df = pd.DataFrame(results)
            table_place.table(df) # Natija chiqayotganini ko'rib turasiz
            
        except Exception as e:
            st.error(f"{year}-yilda xato: {e}")
            continue

    status.success("✅ Hisoblash yakunlandi!")
    
    # Yakuniy Grafik
    fig = px.line(df, x='Yil', y=['Yogingarchilik (mm)', 'EVI (Vegetatsiya)'], 
                  markers=True, title="Ko'p yillik o'zgarish trendi")
    st.plotly_chart(fig, use_container_width=True)
