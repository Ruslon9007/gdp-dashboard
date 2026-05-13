import streamlit as st

# Python 3.12+ va geemap muammosini hal qilish uchun patch
try:
    import pkg_resources
except ImportError:
    import pip._vendor.pkg_resources as pkg_resources

import ee
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import numpy as np
from datetime import datetime

# Geemap-ni xavfsiz import qilish
try:
    import geemap.foliumap as geemap
except (ImportError, KeyError, Exception):
    import geemap
# --- 1. KONFIGURATSIYA VA STYLING ---
st.set_page_config(
    page_title="Basin3 | Eco-Intelligence",
    page_icon="🎨",
    layout="wide"
)

# Prettymapp uslubidagi Custom CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main { background-color: #f8f9fa; }
    
    /* Kartochkalar dizayni */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    
    /* Tugmani Prettymapp uslubiga keltirish */
    .stButton>button {
        width: 100%;
        border-radius: 50px;
        border: none;
        background: #1a1a1a;
        color: white;
        padding: 10px 24px;
        font-weight: 600;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background: #404040;
        transform: scale(1.02);
    }
    
    /* Sidebar dizayni */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #eee;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. GEE ULANISH ---
@st.cache_resource
def initialize_ee():
    try:
        if "gee_key" in st.secrets:
            key_dict = dict(st.secrets["gee_key"])
            credentials = ee.ServiceAccountCredentials(
                key_dict['client_email'],
                key_data=json.dumps(key_dict)
            )
            ee.Initialize(credentials)
        else:
            ee.Initialize()
        return True
    except Exception as e:
        st.error(f"GEE Xatosi: {e}")
        return False

initialize_ee()

# --- 3. YORDAMCHI FUNKSIYALAR ---
def safe_get_value(result_dict, key, default=0):
    if result_dict is None or key not in result_dict: return default
    val = result_dict[key]
    return val if isinstance(val, (int, float)) else default

def calculate_year_metrics(year, user_roi):
    """Sizning hisoblash mantiqingiz (qisqartirilgan shaklda saqlandi)"""
    results = {'Yil': year}
    try:
        # CHIRPS - Yog'in
        precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(user_roi).filterDate(f'{year}-01-01', f'{year}-12-31').sum()
        precip_val = precip.reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=5000).getInfo()
        results['Yog\'ingarchilik (mm)'] = round(safe_get_value(precip_val, 'precipitation'), 1)

        # Sentinel-2 EVI va NDWI
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi).filterDate(f'{year}-04-01', f'{year}-10-31').filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).median()
        
        # EVI hisobi
        evi = s2.expression('2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
            'NIR': s2.select('B8').multiply(0.0001),
            'RED': s2.select('B4').multiply(0.0001),
            'BLUE': s2.select('B2').multiply(0.0001)
        }).rename('EVI')
        
        evi_val = evi.reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=100).getInfo()
        results['EVI (Yashillik)'] = round(safe_get_value(evi_val, 'EVI'), 3)

        # LST - Harorat
        temp = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(user_roi).filterDate(f'{year}-06-01', f'{year}-08-31').select('LST_Day_1km').mean()
        temp_val = temp.multiply(0.02).subtract(273.15).reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=1000).getInfo()
        results['Harorat (°C)'] = round(safe_get_value(temp_val, 'LST_Day_1km'), 1)

        return results
    except:
        return None

# --- 4. ASOSIY INTERFEYS ---
st.title("🎨 Basin3 Eco-Monitoring")
st.caption("Google Earth Engine & Streamlit asosidagi badiiy tahlil platformasi")

with st.sidebar:
    st.header("📍 Hudud va Vaqt")
    start_year = st.slider("Boshlang'ich", 2018, 2024, 2018)
    end_year = st.slider("Yakuniy", 2018, 2025, 2025)
    
    st.markdown("---")
    st.markdown("### 🎨 Dizayn mavzusi")
    theme = st.selectbox("Xarita uslubi", ["Sputnik", "Topografik", "Minimal"])
    
    start_btn = st.button("🚀 TAHLILNI BOSHLASH")

if start_btn:
    try:
        user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")
    except:
        st.error("Asset topilmadi!")
        st.stop()

    # Progress
    progress = st.progress(0)
    final_data = []
    
    years = list(range(start_year, end_year + 1))
    for i, year in enumerate(years):
        res = calculate_year_metrics(year, user_roi)
        if res: final_data.append(res)
        progress.progress((i+1)/len(years))
    
    df = pd.DataFrame(final_data)

    # --- VIZUALIZATSIYA QISMI ---
    
    # 1-Qator: Interaktiv Xarita va Asosiy Metrikalar
    col_map, col_metrics = st.columns([2, 1])
    
    with col_map:
        st.subheader("🗺️ Hududning sun'iy yo'ldosh ko'rinishi")
        Map = geemap.Map()
        Map.addLayer(user_roi, {'color': '#1a1a1a', 'fillColor': '00000000'}, "Basin3 Border")
        
        # Sentinel-2 eng yangi tasvirini qo'shish
        latest_s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)).first()
        Map.addLayer(latest_s2, {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000}, "Tabiiy ranglar")
        
        Map.centerObject(user_roi, 12)
        Map.to_streamlit(height=450)

    with col_metrics:
        st.subheader("📊 Oxirgi holat")
        if not df.empty:
            st.metric("O'rtacha EVI", df['EVI (Yashillik)'].iloc[-1], delta=round(df['EVI (Yashillik)'].diff().iloc[-1], 3))
            st.metric("Harorat", f"{df['Harorat (°C)'].iloc[-1]} °C", delta=round(df['Harorat (°C)'].diff().iloc[-1], 1), delta_color="inverse")
            st.metric("Yog'ingarchilik", f"{df['Yog\'ingarchilik (mm)'].iloc[-1]} mm")

    # 2-Qator: Prettymapp uslubidagi Tablar
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📈 Trendlar", "📋 Ma'lumotlar", "📥 Eksport"])

    with tab1:
        fig = make_subplots(rows=1, cols=2, subplot_titles=('EVI Dinamikasi', 'Harorat o\'zgarishi'))
        
        fig.add_trace(go.Scatter(x=df['Yil'], y=df['EVI (Yashillik)'], line=dict(color='#2ecc71', width=4), fill='tozeroy', name="EVI"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Yil'], y=df['Harorat (°C)'], line=dict(color='#e74c3c', width=4), name="LST"), row=1, col=2)
        
        fig.update_layout(template="plotly_white", height=400)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.dataframe(df.style.background_gradient(cmap='Greens', subset=['EVI (Yashillik)']), use_container_width=True)

    with tab3:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Ma'lumotlarni CSV yuklab olish", data=csv, file_name="basin3_data.csv", mime="text/csv")

# Footer
st.markdown("""
    <div style='text-align: center; padding: 20px; color: #95a5a6; font-size: 0.8rem;'>
        Basin3 Intelligence © 2026 | Dizayn: Prettymapp Inspiration
    </div>
""", unsafe_allow_html=True)
