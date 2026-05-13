"""
🎨 Basin3 Eco-Intelligence | Mukammal Streamlit Monitoring System
=================================================================
Google Earth Engine + Streamlit + Plotly + Geemap
Prettymapp uslubida chiroyli, interaktiv ekologik monitoring
"""

import streamlit as st
import sys
import os
from datetime import datetime
from io import BytesIO

# =============================================================================
# 0. KUTUBXONALAR VA PATCHLAR
# =============================================================================

try:
    import pkg_resources
except ImportError:
    try:
        import pip._vendor.pkg_resources as pkg_resources
    except ImportError:
        from types import ModuleType
        pkg_resources = ModuleType("pkg_resources")
        sys.modules["pkg_resources"] = pkg_resources

import ee
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json

# Geemap import
GEEMAP_AVAILABLE = False
try:
    import geemap.foliumap as geemap
    GEEMAP_AVAILABLE = True
except Exception:
    try:
        import geemap
        GEEMAP_AVAILABLE = True
    except ImportError:
        pass

# =============================================================================
# 1. KONFIGURATSIYA VA STYLING (Prettymapp Inspiration)
# =============================================================================

st.set_page_config(
    page_title="Basin3 | Eco-Intelligence",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Prettymapp uslubidagi CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main { 
        background: linear-gradient(135deg, #fafbfc 0%, #f0f2f5 100%);
    }

    /* Sarlavha */
    h1 {
        font-weight: 800 !important;
        letter-spacing: -0.02em !important;
    }

    h2, h3 {
        font-weight: 700 !important;
        letter-spacing: -0.01em !important;
    }

    /* Metric kartochkalar */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }

    div[data-testid="stMetric"] > div {
        font-size: 0.85rem;
        color: #6c757d;
        font-weight: 500;
    }

    div[data-testid="stMetric"] > div:nth-child(2) {
        font-size: 1.75rem;
        font-weight: 700;
        color: #1a1a1a;
    }

    /* Tugmalar */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        border: none;
        background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
        color: white;
        padding: 14px 28px;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #2d2d2d 0%, #404040 100%);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
    }
    .stButton>button:active {
        transform: translateY(0);
    }
    .stButton>button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
        transform: none;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e9ecef;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }

    /* Selectbox va slider */
    .stSelectbox > div > div {
        border-radius: 10px;
        border-color: #dee2e6;
    }

    /* DataFrame */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e9ecef;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #f8f9fa;
        padding: 8px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
        color: #6c757d;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        background: #ffffff !important;
        color: #1a1a1a !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }

    /* Download button */
    .stDownloadButton > button {
        border-radius: 10px;
        background: #ffffff;
        color: #1a1a1a;
        border: 2px solid #1a1a1a;
        font-weight: 600;
    }
    .stDownloadButton > button:hover {
        background: #1a1a1a;
        color: white;
    }

    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #2ecc71, #27ae60);
        border-radius: 10px;
    }

    /* Alert/Info */
    .stAlert {
        border-radius: 12px;
        border: none;
    }

    /* Expander */
    .streamlit-expanderHeader {
        font-weight: 600;
        border-radius: 12px;
        background: #f8f9fa;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. GOOGLE EARTH ENGINE ULANISH
# =============================================================================

@st.cache_resource(show_spinner=False)
def initialize_ee():
    """GEE ni ishga tushirish va autentifikatsiya"""
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
        st.error(f"❌ GEE ulanish xatosi: {e}")
        return False

GEE_READY = initialize_ee()

# =============================================================================
# 3. YORDAMCHI FUNKSIYALAR
# =============================================================================

def safe_get_value(result_dict, key, default=0, min_val=None, max_val=None):
    """Xavfsiz qiymat olish va validatsiya"""
    if result_dict is None:
        return default
    value = result_dict.get(key, default)
    if value is None or not isinstance(value, (int, float)):
        return default
    if min_val is not None and value < min_val:
        return default
    if max_val is not None and value > max_val:
        return default
    return value


@st.cache_data(ttl=3600, show_spinner=False)
def calculate_year_metrics(year: int, asset_path: str):
    """Bir yil uchun barcha ekologik metrikalarni hisoblash"""
    results = {'Yil': year}

    try:
        user_roi = ee.FeatureCollection(asset_path)

        # ─── A. YO'G'INGARCHILIK (CHIRPS) ───
        precip_col = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
            .filterBounds(user_roi)
            .filterDate(f'{year}-01-01', f'{year}-12-31'))

        if precip_col.size().getInfo() > 0:
            precip_val = (precip_col.sum()
                .reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=5000, maxPixels=1e9)
                .getInfo())
            results["Yog'ingarchilik (mm)"] = round(
                safe_get_value(precip_val, 'precipitation', 0, 0, 5000), 1
            )
        else:
            results["Yog'ingarchilik (mm)"] = None

        # ─── B. SENTINEL-2 (EVI, NDWI, NDMI) ───
        s2_col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(user_roi)
            .filterDate(f'{year}-04-01', f'{year}-10-31')
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)))

        s2_count = s2_col.size().getInfo()

        if s2_count > 0:
            s2 = s2_col.median()

            # EVI
            evi = s2.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                {
                    'NIR': s2.select('B8').multiply(0.0001),
                    'RED': s2.select('B4').multiply(0.0001),
                    'BLUE': s2.select('B2').multiply(0.0001)
                }
            ).rename('EVI')

            evi_val = evi.reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=100, maxPixels=1e9).getInfo()
            results['EVI (Yashillik)'] = round(safe_get_value(evi_val, 'EVI', 0.15, -0.5, 1.0), 3)

            # NDWI
            ndwi = s2.expression(
                '(GREEN - NIR) / (GREEN + NIR)',
                {'GREEN': s2.select('B3').multiply(0.0001), 'NIR': s2.select('B8').multiply(0.0001)}
            ).rename('NDWI')

            ndwi_val = ndwi.reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=100, maxPixels=1e9).getInfo()
            results['NDWI (Suv)'] = round(safe_get_value(ndwi_val, 'NDWI', 0, -1, 1), 3)

            # NDMI
            ndmi = s2.expression(
                '(NIR - SWIR) / (NIR + SWIR)',
                {'NIR': s2.select('B8').multiply(0.0001), 'SWIR': s2.select('B11').multiply(0.0001)}
            ).rename('NDMI')

            ndmi_val = ndmi.reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=100, maxPixels=1e9).getInfo()
            results['NDMI (Namlik)'] = round(safe_get_value(ndmi_val, 'NDMI', 0, -1, 1), 3)
        else:
            results['EVI (Yashillik)'] = None
            results['NDWI (Suv)'] = None
            results['NDMI (Namlik)'] = None

        # ─── C. QOR (MOD10A2) ───
        snow_col = (ee.ImageCollection("MODIS/061/MOD10A2")
            .filterBounds(user_roi)
            .filterDate(f'{year}-01-01', f'{year}-03-31')
            .select('Eight_Day_Snow_Cover'))

        if snow_col.size().getInfo() > 0:
            snow_val = (snow_col.mean()
                .reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=500, maxPixels=1e9)
                .getInfo())
            results['Qor qoplami (%)'] = round(
                safe_get_value(snow_val, 'Eight_Day_Snow_Cover', 0, 0, 100), 1
            )
        else:
            results['Qor qoplami (%)'] = 0

        # ─── D. MUZLIK (Sentinel-2 NDSI) ───
        if s2_count > 0:
            glacier_col = s2_col.filterDate(f'{year}-07-01', f'{year}-09-30')
            if glacier_col.size().getInfo() > 0:
                g = glacier_col.median()
                ndsi = g.expression(
                    '(GREEN - SWIR) / (GREEN + SWIR)',
                    {'GREEN': g.select('B3').multiply(0.0001), 'SWIR': g.select('B11').multiply(0.0001)}
                ).rename('NDSI')

                ndsi_val = ndsi.reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=100, maxPixels=1e9).getInfo()
                results['Muzlik indeksi'] = round(safe_get_value(ndsi_val, 'NDSI', 0, -1, 1), 3)
            else:
                results['Muzlik indeksi'] = None
        else:
            results['Muzlik indeksi'] = None

        # ─── E. BUG'LANISH (MOD16A2) ───
        et_col = (ee.ImageCollection("MODIS/006/MOD16A2")
            .filterBounds(user_roi)
            .filterDate(f'{year}-01-01', f'{year}-12-31'))

        if et_col.size().getInfo() > 0:
            et_img = et_col.select('ET').sum()
            et_val = et_img.reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=500, maxPixels=1e9).getInfo()
            et_raw = safe_get_value(et_val, 'ET', None, 0, 10000)
            results["Bug'lanish (mm)"] = round(et_raw * 0.1, 1) if et_raw else None
        else:
            results["Bug'lanish (mm)"] = None

        # ─── F. HARORAT (MOD11A1) ───
        lst_col = (ee.ImageCollection("MODIS/061/MOD11A1")
            .filterBounds(user_roi)
            .filterDate(f'{year}-06-01', f'{year}-08-31')
            .select('LST_Day_1km'))

        if lst_col.size().getInfo() > 0:
            lst_val = (lst_col.mean().multiply(0.02).subtract(273.15)
                .reduceRegion(reducer=ee.Reducer.mean(), geometry=user_roi, scale=1000, maxPixels=1e9)
                .getInfo())
            results['Harorat (°C)'] = round(safe_get_value(lst_val, 'LST_Day_1km', 25, -50, 60), 1)
        else:
            results['Harorat (°C)'] = None

        return results

    except Exception as e:
        st.warning(f"⚠️ {year}-yil uchun xato: {str(e)}")
        return None


def create_visualizations(df: pd.DataFrame):
    """Plotly grafiklarini yaratish"""
    df = df.copy()
    for col in df.columns:
        if col != 'Yil':
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # ─── 1. Asosiy metrikalar ───
    fig1 = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Yog'ingarchilik (mm)",
            "EVI - O'simlik yashilligi",
            "Harorat (°C)",
            "Bug'lanish (mm)"
        ),
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )

    colors = {'precip': '#3498db', 'evi': '#2ecc71', 'temp': '#e74c3c', 'et': '#9b59b6'}

    if "Yog'ingarchilik (mm)" in df.columns:
        fig1.add_trace(go.Scatter(
            x=df['Yil'], y=df["Yog'ingarchilik (mm)"],
            mode='lines+markers', name="Yog'ingarchilik",
            line=dict(color=colors['precip'], width=3),
            marker=dict(size=10, color=colors['precip'], line=dict(width=2, color='white')),
            fill='tozeroy', fillcolor='rgba(52,152,219,0.1)',
            connectgaps=True
        ), row=1, col=1)

    if 'EVI (Yashillik)' in df.columns:
        fig1.add_trace(go.Scatter(
            x=df['Yil'], y=df['EVI (Yashillik)'],
            mode='lines+markers', name='EVI',
            line=dict(color=colors['evi'], width=3),
            marker=dict(size=10, color=colors['evi'], line=dict(width=2, color='white')),
            fill='tozeroy', fillcolor='rgba(46,204,113,0.1)',
            connectgaps=True
        ), row=1, col=2)

    if 'Harorat (°C)' in df.columns:
        fig1.add_trace(go.Scatter(
            x=df['Yil'], y=df['Harorat (°C)'],
            mode='lines+markers', name='Harorat',
            line=dict(color=colors['temp'], width=3),
            marker=dict(size=10, color=colors['temp'], line=dict(width=2, color='white')),
            connectgaps=True
        ), row=2, col=1)

    if "Bug'lanish (mm)" in df.columns:
        fig1.add_trace(go.Scatter(
            x=df['Yil'], y=df["Bug'lanish (mm)"],
            mode='lines+markers', name="Bug'lanish",
            line=dict(color=colors['et'], width=3),
            marker=dict(size=10, color=colors['et'], line=dict(width=2, color='white')),
            fill='tozeroy', fillcolor='rgba(155,89,182,0.1)',
            connectgaps=True
        ), row=2, col=2)

    fig1.update_layout(
        height=650,
        showlegend=False,
        title_text="<b>Asosiy Ekologik Ko'rsatkichlar</b>",
        title_font_size=18,
        title_font_color='#1a1a1a',
        template='plotly_white',
        margin=dict(t=80, b=40, l=40, r=40)
    )

    # ─── 2. Suv va namlik ───
    fig2 = go.Figure()
    if 'NDWI (Suv)' in df.columns:
        fig2.add_trace(go.Scatter(
            x=df['Yil'], y=df['NDWI (Suv)'],
            mode='lines+markers', name='NDWI (Suv)',
            line=dict(color='#0984E3', width=3),
            marker=dict(size=12, line=dict(width=2, color='white')),
            connectgaps=True
        ))
    if 'NDMI (Namlik)' in df.columns:
        fig2.add_trace(go.Scatter(
            x=df['Yil'], y=df['NDMI (Namlik)'],
            mode='lines+markers', name='NDMI (Namlik)',
            line=dict(color='#00B894', width=3),
            marker=dict(size=12, line=dict(width=2, color='white')),
            connectgaps=True
        ))

    fig2.update_layout(
        title="<b>Suv va Namlik Indekslari</b>",
        xaxis_title="Yil", yaxis_title="Indeks qiymati",
        height=420, template='plotly_white',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    # ─── 3. Qor va muzlik ───
    fig3 = make_subplots(rows=1, cols=2, subplot_titles=('Qor qoplami (%)', 'Muzlik indeksi'))
    if 'Qor qoplami (%)' in df.columns:
        fig3.add_trace(go.Bar(
            x=df['Yil'], y=df['Qor qoplami (%)'],
            name='Qor', marker_color='#74B9FF',
            marker_line_color='#0984E3', marker_line_width=1.5
        ), row=1, col=1)
    if 'Muzlik indeksi' in df.columns:
        fig3.add_trace(go.Bar(
            x=df['Yil'], y=df['Muzlik indeksi'],
            name='Muzlik', marker_color='#A29BFE',
            marker_line_color='#6C5CE7', marker_line_width=1.5
        ), row=1, col=2)

    fig3.update_layout(
        height=400, showlegend=False,
        title_text="<b>Qor va Muzlik Dinamikasi</b>",
        template='plotly_white',
        margin=dict(t=80, b=40, l=40, r=40)
    )

    return fig1, fig2, fig3


def calculate_statistics(df: pd.DataFrame):
    """Statistik tahlil va trendlar"""
    stats = {}
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c != 'Yil']

    for col in numeric_cols:
        values = df[col].dropna()
        if len(values) > 1:
            stats[col] = {
                "O'rtacha": round(values.mean(), 2),
                'Min': round(values.min(), 2),
                'Max': round(values.max(), 2),
                'Std': round(values.std(), 2),
            }
            if len(values) > 2:
                x = np.arange(len(values))
                z = np.polyfit(x, values.values, 1)
                trend = z[0]
                stats[col]['Trend'] = 'Oshmoqda ↗' if trend > 0 else 'Kamaymoqda ↘'
                stats[col]["O'zgarish/yil"] = round(trend, 3)
    return stats


# =============================================================================
# 4. SIDEBAR
# =============================================================================

with st.sidebar:
    st.markdown("""
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="font-size: 3rem; margin-bottom: 8px;">🎨</div>
            <h2 style="margin: 0; font-size: 1.3rem; font-weight: 800;">Basin3</h2>
            <p style="margin: 0; color: #6c757d; font-size: 0.85rem;">Eco-Intelligence</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.header("⚙️ Sozlamalar")

    col1, col2 = st.columns(2)
    with col1:
        start_year = st.selectbox("Boshlang'ich", range(2018, 2026), index=0)
    with col2:
        end_year = st.selectbox("Tugash", range(2018, 2026), index=7)

    if start_year >= end_year:
        st.error("❌ Tugash yili katta bo'lishi kerak!")

    asset_path = st.text_input(
        "GEE Asset yo'li",
        value="projects/ee-jumaboyevll/assets/basin3",
        help="Google Earth Engine'dagi FeatureCollection asset yo'li"
    )

    st.markdown("---")

    st.markdown("""
        <div style="background: #f8f9fa; padding: 16px; border-radius: 12px; margin-top: 10px;">
            <h4 style="margin: 0 0 10px 0; font-size: 0.9rem;">📡 Ma'lumot manbalari</h4>
            <div style="font-size: 0.8rem; color: #6c757d; line-height: 1.6;">
                • <b>CHIRPS</b> — Yog'ingarchilik<br>
                • <b>Sentinel-2</b> — EVI, NDWI, NDMI<br>
                • <b>MODIS</b> — Qor, ET, LST<br>
                • <b>GEE</b> — Sun'iy yo'ldosh tahlili
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    start_btn = st.button(
        "🚀 TAHLILNI BOSHLASH",
        disabled=(start_year >= end_year) or not GEE_READY,
        use_container_width=True
    )

# =============================================================================
# 5. ASOSIY INTERFEYS
# =============================================================================

st.markdown("""
    <div style="margin-bottom: 30px;">
        <h1 style="margin: 0; font-size: 2.2rem;">🎨 Basin3 Eco-Monitoring</h1>
        <p style="margin: 8px 0 0 0; color: #6c757d; font-size: 1.05rem;">
            Google Earth Engine asosidagi kompleks ekologik tahlil platformasi
        </p>
    </div>
""", unsafe_allow_html=True)

if not GEE_READY:
    st.error("⚠️ Google Earth Engine ulanmagan. Iltimos, autentifikatsiyani tekshiring.")
    st.stop()

if start_btn:
    if start_year >= end_year:
        st.error("❌ Yillar oralig'i noto'g'ri!")
        st.stop()

    # ─── Tahlil jarayoni ───
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        user_roi = ee.FeatureCollection(asset_path)
        _ = user_roi.first().getInfo()  # Asset mavjudligini tekshirish
    except Exception as e:
        st.error(f"❌ Asset yuklashda xato: {e}")
        st.stop()

    years = list(range(start_year, end_year + 1))
    final_results = []

    for i, year in enumerate(years):
        status_text.info(f"⏳ {year}-yil ma'lumotlari qayta ishlanmoqda... ({i+1}/{len(years)})")
        progress_bar.progress((i + 1) / len(years))

        result = calculate_year_metrics(year, asset_path)
        if result:
            final_results.append(result)

    progress_bar.empty()
    status_text.success("✅ Tahlil muvaffaqiyatli yakunlandi!")

    df = pd.DataFrame(final_results)

    if df.empty:
        st.error("❌ Hech qanday ma'lumot olinmadi.")
        st.stop()

    # =============================================================================
    # 6. NATIJALAR KO'RSATISH
    # =============================================================================

    st.markdown("---")

    # ─── 6.1 Xarita va Metrikalar ───
    col_map, col_metrics = st.columns([1.5, 1])

    with col_map:
        st.subheader("🗺️ Sun'iy yo'ldosh ko'rinishi")

        if GEEMAP_AVAILABLE:
            m = geemap.Map()
            m.addLayer(user_roi, {'color': '#1a1a1a', 'fillColor': '00000000', 'width': 3}, "Basin3")

            # Sentinel-2 True Color
            s2_vis = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10)).sort('system:time_start', False).first()
            if s2_vis:
                m.addLayer(s2_vis, {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000, 'gamma': 1.2}, "Sentinel-2")

            # EVI visualization
            evi_vis = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(user_roi).filterDate('2024-04-01', '2024-10-31').filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).median()
            evi_img = evi_vis.expression('2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': evi_vis.select('B8').multiply(0.0001),
                'RED': evi_vis.select('B4').multiply(0.0001),
                'BLUE': evi_vis.select('B2').multiply(0.0001)
            }).clamp(-1, 1)
            m.addLayer(evi_img, {'min': -0.2, 'max': 0.8, 'palette': ['#a50026', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']}, "EVI (2024)")

            m.centerObject(user_roi, 11)
            m.to_streamlit(height=480)
        else:
            st.info("📍 Geemap o'rnatilmagan. Xarita ko'rinishi mavjud emas.")

    with col_metrics:
        st.subheader("📊 Asosiy ko'rsatkichlar")

        if not df.empty:
            latest = df.iloc[-1]
            first = df.iloc[0]

            cols = [
                ("Yog'ingarchilik (mm)", "mm", "💧"),
                ('EVI (Yashillik)', "", "🌿"),
                ('Harorat (°C)', "°C", "🌡️"),
                ("Bug'lanish (mm)", "mm", "💨"),
            ]

            for col_name, unit, emoji in cols:
                if col_name in df.columns and df[col_name].notna().any():
                    avg_val = df[col_name].mean()
                    last_val = df[col_name].iloc[-1]
                    first_val = df[col_name].iloc[0]
                    delta = last_val - first_val if pd.notna(last_val) and pd.notna(first_val) else None

                    st.metric(
                        label=f"{emoji} {col_name}",
                        value=f"{last_val:.1f} {unit}" if pd.notna(last_val) else "N/A",
                        delta=f"{delta:+.1f} {unit}" if delta is not None else None,
                        delta_color="inverse" if "Harorat" in col_name else "normal"
                    )

    # ─── 6.2 Tablar ───
    st.markdown("---")
    tab1, tab2, tab3 = st.tabs(["📈 Vizualizatsiya", "📋 Jadval", "📉 Statistika"])

    with tab1:
        fig1, fig2, fig3 = create_visualizations(df)
        st.plotly_chart(fig1, use_container_width=True)
        col_a, col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig2, use_container_width=True)
        with col_b:
            st.plotly_chart(fig3, use_container_width=True)

    with tab2:
        st.subheader("📋 To'liq ma'lumotlar")

        display_df = df.copy()
        for col in display_df.columns:
            if col != 'Yil':
                if any(k in col for k in ['EVI', 'NDWI', 'NDMI', 'indeksi']):
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "—")
                else:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")

        st.dataframe(display_df, use_container_width=True, height=450)

        # Eksport
        col_csv, col_excel = st.columns(2)
        with col_csv:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 CSV yuklash", csv, f"basin3_{start_year}-{end_year}.csv", "text/csv")
        with col_excel:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Natijalar', index=False)
                stats = calculate_statistics(df)
                if stats:
                    pd.DataFrame(stats).T.to_excel(writer, sheet_name='Statistika')
            st.download_button("📥 Excel yuklash", output.getvalue(), f"basin3_{start_year}-{end_year}.xlsx", 
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab3:
        st.subheader("📉 Statistik xulosalar")
        stats = calculate_statistics(df)

        if stats:
            for param, values in stats.items():
                with st.expander(f"📊 {param}", expanded=False):
                    cols = st.columns(len(values))
                    for col, (key, val) in zip(cols, values.items()):
                        st.markdown(f"""
                            <div style="background: #f8f9fa; padding: 12px; border-radius: 10px; text-align: center;">
                                <div style="font-size: 0.75rem; color: #6c757d; margin-bottom: 4px;">{key}</div>
                                <div style="font-size: 1.1rem; font-weight: 700; color: #1a1a1a;">{val}</div>
                            </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("Statistikani hisoblash uchun yetarli ma'lumot yo'q.")

# =============================================================================
# 7. FOOTER
# =============================================================================

st.markdown("""
    <div style='text-align: center; padding: 40px 20px 20px; color: #adb5bd; font-size: 0.85rem;'>
        <div style="font-size: 1.5rem; margin-bottom: 8px;">🎨</div>
        <p style="margin: 0; font-weight: 600; color: #6c757d;">Basin3 Eco-Intelligence</p>
        <p style="margin: 4px 0 0 0;">Google Earth Engine & Streamlit | Dizayn: Prettymapp Inspiration</p>
        <p style="margin: 4px 0 0 0; font-size: 0.75rem;">© 2026 | Oxirgi yangilanish: {date}</p>
    </div>
""".format(date=datetime.now().strftime("%Y-%m-%d %H:%M")), unsafe_allow_html=True)
