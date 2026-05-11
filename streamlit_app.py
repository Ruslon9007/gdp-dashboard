import streamlit as st
import ee
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import numpy as np
from datetime import datetime

# --- KONFIGURATSIYA ---
st.set_page_config(
    page_title="Basin3 Monitoring System",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main {background-color: #f5f7fa;}
    .stButton>button {
        width: 100%;
        background-color: #0066cc;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 12px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #0052a3;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,102,204,0.3);
    }
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. GEE ULANISH ---
@st.cache_resource
def initialize_ee():
    """Google Earth Engine ni ishga tushirish"""
    if "gee_key" not in st.secrets:
        st.error("⚠️ Secrets qismida 'gee_key' topilmadi!")
        st.stop()
    
    try:
        key_dict = dict(st.secrets["gee_key"])
        credentials = ee.ServiceAccountCredentials(
            key_dict['client_email'], 
            key_data=json.dumps(key_dict)
        )
        ee.Initialize(credentials)
        return True
    except Exception as e:
        # Agar allaqachon initialize bo'lgan bo'lsa
        try:
            ee.Initialize()
            return True
        except:
            st.error(f"❌ GEE ulanish xatosi: {e}")
            st.stop()

initialize_ee()

# --- 2. YORDAMCHI FUNKSIYALAR ---
def safe_get_value(result_dict, key, default=0, min_val=None, max_val=None):
    """Xavfsiz qiymat olish va validatsiya"""
    value = result_dict.get(key, default)
    
    if value is None or not isinstance(value, (int, float)):
        return default
    
    if min_val is not None and value < min_val:
        return default
    if max_val is not None and value > max_val:
        return default
    
    return value

def calculate_year_metrics(year, user_roi):
    """Bir yil uchun barcha metrikalarni hisoblash"""
    results = {'Yil': year}
    
    try:
        # A. YOĞINGARCHILIK (CHIRPS)
        precip_collection = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY") \
            .filterBounds(user_roi) \
            .filterDate(f'{year}-01-01', f'{year}-12-31')
        
        precip_result = precip_collection.sum() \
            .reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=user_roi,
                scale=5000,
                maxPixels=1e9
            ).getInfo()
        
        results['Yog\'ingarchilik (mm)'] = round(
            safe_get_value(precip_result, 'precipitation', 0, 0, 5000), 1
        )
        
        # B. SENTINEL-2 MA'LUMOTLARI
        s2_collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
            .filterBounds(user_roi) \
            .filterDate(f'{year}-04-01', f'{year}-10-31') \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        
        s2_count = s2_collection.size().getInfo()
        
        if s2_count > 0:
            s2 = s2_collection.median()
            
            # EVI - Enhanced Vegetation Index
            b8 = s2.select('B8').divide(10000)
            b4 = s2.select('B4').divide(10000)
            b2 = s2.select('B2').divide(10000)
            
            evi = b8.subtract(b4).multiply(2.5).divide(
                b8.add(b4.multiply(6)).subtract(b2.multiply(7.5)).add(1)
            )
            
            evi_result = evi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=user_roi,
                scale=100,
                maxPixels=1e9
            ).getInfo()
            
            results['EVI (Yashillik)'] = round(
                safe_get_value(evi_result, 'B8', 0.15, -0.5, 1.0), 3
            )
            
            # NDWI - Normalized Difference Water Index
            ndwi = s2.normalizedDifference(['B3', 'B8'])
            ndwi_result = ndwi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=user_roi,
                scale=100,
                maxPixels=1e9
            ).getInfo()
            
            results['NDWI (Suv)'] = round(
                safe_get_value(ndwi_result, 'nd', 0, -1, 1), 3
            )
            
            # NDMI - Normalized Difference Moisture Index
            ndmi = s2.normalizedDifference(['B8', 'B11'])
            ndmi_result = ndmi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=user_roi,
                scale=100,
                maxPixels=1e9
            ).getInfo()
            
            results['NDMI (Namlik)'] = round(
                safe_get_value(ndmi_result, 'nd', 0, -1, 1), 3
            )
        else:
            results['EVI (Yashillik)'] = None
            results['NDWI (Suv)'] = None
            results['NDMI (Namlik)'] = None
        
        # C. QOR VA MUZLIK
        # MODIS Snow Cover
        snow_collection = ee.ImageCollection("MODIS/006/MOD10A1") \
            .filterBounds(user_roi) \
            .filterDate(f'{year}-01-01', f'{year}-03-31') \
            .select('NDSI_Snow_Cover')
        
        snow_result = snow_collection.mean().reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=user_roi,
            scale=500,
            maxPixels=1e9
        ).getInfo()
        
        results['Qor qoplami (%)'] = round(
            safe_get_value(snow_result, 'NDSI_Snow_Cover', 0, 0, 100), 1
        )
        
        # Muzlik indeksi (Sentinel-2 NDSI)
        if s2_count > 0:
            glacier_collection = s2_collection.filterDate(f'{year}-08-01', f'{year}-09-30')
            if glacier_collection.size().getInfo() > 0:
                glacier_img = glacier_collection.median()
                glacier_ndsi = glacier_img.normalizedDifference(['B3', 'B11'])
                
                glacier_result = glacier_ndsi.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=user_roi,
                    scale=100,
                    maxPixels=1e9
                ).getInfo()
                
                results['Muzlik indeksi'] = round(
                    safe_get_value(glacier_result, 'nd', 0, -1, 1), 3
                )
            else:
                results['Muzlik indeksi'] = None
        else:
            results['Muzlik indeksi'] = None
        
        # D. BUĞ'LANISH (ET)
        et_collection = ee.ImageCollection("MODIS/006/MOD16A2") \
            .filterBounds(user_roi) \
            .filterDate(f'{year}-01-01', f'{year}-12-31')
        
        et_result = et_collection.sum().reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=user_roi,
            scale=500,
            maxPixels=1e9
        ).getInfo()
        
        et_value = safe_get_value(et_result, 'ET', None, 0, 10000)
        results['Bug\'lanish (mm)'] = round(et_value * 0.1, 1) if et_value else None
        
        # E. HARORAT (LST)
        lst_collection = ee.ImageCollection("MODIS/006/MOD11A1") \
            .filterBounds(user_roi) \
            .filterDate(f'{year}-06-01', f'{year}-08-31') \
            .select('LST_Day_1km')
        
        lst_result = lst_collection.mean() \
            .multiply(0.02).subtract(273.15) \
            .reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=user_roi,
                scale=1000,
                maxPixels=1e9
            ).getInfo()
        
        results['Harorat (°C)'] = round(
            safe_get_value(lst_result, 'LST_Day_1km', 25, -50, 60), 1
        )
        
        return results
        
    except Exception as e:
        st.warning(f"⚠️ {year}-yil uchun xato: {str(e)}")
        return None

def create_visualizations(df):
    """Interaktiv grafiklar yaratish"""
    
    # 1. Asosiy metrikalar grafigi
    fig1 = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Yog\'ingarchilik (mm)', 
            'EVI - O\'simlik yashilligi',
            'Harorat (°C)', 
            'Bug\'lanish (mm)'
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    # Yog'ingarchilik
    fig1.add_trace(
        go.Scatter(
            x=df['Yil'], 
            y=df['Yog\'ingarchilik (mm)'],
            mode='lines+markers',
            name='Yog\'ingarchilik',
            line=dict(color='#2E86DE', width=3),
            marker=dict(size=8)
        ),
        row=1, col=1
    )
    
    # EVI
    fig1.add_trace(
        go.Scatter(
            x=df['Yil'], 
            y=df['EVI (Yashillik)'],
            mode='lines+markers',
            name='EVI',
            line=dict(color='#26DE81', width=3),
            marker=dict(size=8)
        ),
        row=1, col=2
    )
    
    # Harorat
    fig1.add_trace(
        go.Scatter(
            x=df['Yil'], 
            y=df['Harorat (°C)'],
            mode='lines+markers',
            name='Harorat',
            line=dict(color='#FC5C65', width=3),
            marker=dict(size=8)
        ),
        row=2, col=1
    )
    
    # Bug'lanish
    if 'Bug\'lanish (mm)' in df.columns:
        fig1.add_trace(
            go.Scatter(
                x=df['Yil'], 
                y=df['Bug\'lanish (mm)'],
                mode='lines+markers',
                name='Bug\'lanish',
                line=dict(color='#FD79A8', width=3),
                marker=dict(size=8)
            ),
            row=2, col=2
        )
    
    fig1.update_layout(
        height=600,
        showlegend=False,
        title_text="<b>Asosiy Ekologik Ko'rsatkichlar Dinamikasi</b>",
        title_font_size=20,
        template='plotly_white'
    )
    
    # 2. Suv va namlik ko'rsatkichlari
    fig2 = go.Figure()
    
    fig2.add_trace(go.Scatter(
        x=df['Yil'],
        y=df['NDWI (Suv)'],
        mode='lines+markers',
        name='NDWI (Suv)',
        line=dict(color='#0984E3', width=3),
        marker=dict(size=10)
    ))
    
    fig2.add_trace(go.Scatter(
        x=df['Yil'],
        y=df['NDMI (Namlik)'],
        mode='lines+markers',
        name='NDMI (Namlik)',
        line=dict(color='#00B894', width=3),
        marker=dict(size=10)
    ))
    
    fig2.update_layout(
        title="<b>Suv va Namlik Indekslari</b>",
        xaxis_title="Yil",
        yaxis_title="Indeks qiymati",
        height=400,
        template='plotly_white',
        hovermode='x unified'
    )
    
    # 3. Qor va muzlik
    fig3 = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Qor qoplami (%)', 'Muzlik indeksi')
    )
    
    fig3.add_trace(
        go.Bar(
            x=df['Yil'],
            y=df['Qor qoplami (%)'],
            name='Qor',
            marker_color='#74B9FF'
        ),
        row=1, col=1
    )
    
    if 'Muzlik indeksi' in df.columns:
        fig3.add_trace(
            go.Bar(
                x=df['Yil'],
                y=df['Muzlik indeksi'],
                name='Muzlik',
                marker_color='#A29BFE'
            ),
            row=1, col=2
        )
    
    fig3.update_layout(
        height=400,
        showlegend=False,
        title_text="<b>Qor va Muzlik Dinamikasi</b>",
        template='plotly_white'
    )
    
    return fig1, fig2, fig3

def calculate_statistics(df):
    """Statistik tahlil va trendlar"""
    stats = {}
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    numeric_cols = [col for col in numeric_cols if col != 'Yil']
    
    for col in numeric_cols:
        if df[col].notna().sum() > 1:
            values = df[col].dropna()
            
            # Asosiy statistika
            stats[col] = {
                'O\'rtacha': round(values.mean(), 2),
                'Min': round(values.min(), 2),
                'Max': round(values.max(), 2),
                'Std': round(values.std(), 2),
            }
            
            # Trend (linear regression)
            if len(values) > 2:
                x = np.arange(len(values))
                y = values.values
                z = np.polyfit(x, y, 1)
                trend = z[0]
                stats[col]['Trend'] = 'Oshmoqda ↗' if trend > 0 else 'Kamaymoqda ↘'
                stats[col]['O\'zgarish/yil'] = round(trend, 3)
    
    return stats

# --- 3. ASOSIY INTERFEYS ---
st.title("🛰️ Basin3: Kompleks Ekologik Monitoring Tizimi")
st.markdown("### 📊 2018-2025 yillar: Sun'iy yo'ldosh ma'lumotlari tahlili")

# Sidebar
with st.sidebar:
    st.header("⚙️ Sozlamalar")
    
    start_year = st.selectbox("Boshlang'ich yil", range(2018, 2026), index=0)
    end_year = st.selectbox("Tugash yili", range(2018, 2026), index=7)
    
    if start_year >= end_year:
        st.error("Tugash yili boshlang'ich yildan katta bo'lishi kerak!")
    
    st.markdown("---")
    st.markdown("""
    **📡 Ma'lumot manbalari:**
    - CHIRPS (Yog'ingarchilik)
    - Sentinel-2 (Optik)
    - MODIS (Qor, ET, LST)
    
    **🔬 Hisoblangan indekslar:**
    - EVI (O'simlik yashilligi)
    - NDWI (Suv)
    - NDMI (Namlik)
    - NDSI (Qor/Muzlik)
    """)

# Asosiy tugma
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    start_button = st.button("🚀 Tahlilni Boshlash", use_container_width=True)

if start_button:
    if start_year >= end_year:
        st.error("❌ Yillar oralig'i noto'g'ri!")
        st.stop()
    
    # Asset yuklash
    try:
        user_roi = ee.FeatureCollection("projects/ee-jumaboyevll/assets/basin3")
    except Exception as e:
        st.error(f"❌ Basin3 asset yuklashda xato: {e}")
        st.stop()
    
    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    years = list(range(start_year, end_year + 1))
    final_results = []
    
    for i, year in enumerate(years):
        status_text.info(f"⏳ {year}-yil ma'lumotlari qayta ishlanmoqda... ({i+1}/{len(years)})")
        progress_bar.progress((i + 1) / len(years))
        
        result = calculate_year_metrics(year, user_roi)
        if result:
            final_results.append(result)
    
    progress_bar.empty()
    status_text.success("✅ Tahlil muvaffaqiyatli yakunlandi!")
    
    # Ma'lumotlarni DataFrame ga o'tkazish
    df = pd.DataFrame(final_results)
    
    # --- NATIJALARNI KO'RSATISH ---
    st.markdown("---")
    st.header("📈 Tahlil Natijalari")
    
    # Metrikalar
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_precip = df['Yog\'ingarchilik (mm)'].mean()
        st.metric(
            "O'rtacha yog'ingarchilik",
            f"{avg_precip:.1f} mm",
            delta=f"{df['Yog\'ingarchilik (mm)'].iloc[-1] - df['Yog\'ingarchilik (mm)'].iloc[0]:.1f} mm"
        )
    
    with col2:
        avg_evi = df['EVI (Yashillik)'].mean()
        st.metric(
            "O'rtacha EVI",
            f"{avg_evi:.3f}",
            delta=f"{df['EVI (Yashillik)'].iloc[-1] - df['EVI (Yashillik)'].iloc[0]:.3f}"
        )
    
    with col3:
        avg_temp = df['Harorat (°C)'].mean()
        st.metric(
            "O'rtacha harorat",
            f"{avg_temp:.1f}°C",
            delta=f"{df['Harorat (°C)'].iloc[-1] - df['Harorat (°C)'].iloc[0]:.1f}°C"
        )
    
    with col4:
        if 'Bug\'lanish (mm)' in df.columns:
            avg_et = df['Bug\'lanish (mm)'].mean()
            st.metric(
                "O'rtacha bug'lanish",
                f"{avg_et:.1f} mm",
                delta=f"{df['Bug\'lanish (mm)'].iloc[-1] - df['Bug\'lanish (mm)'].iloc[0]:.1f} mm"
            )
    
    # Ma'lumotlar jadvali
    st.subheader("📋 To'liq Ma'lumotlar Jadvali")
    # Format the dataframe for display (avoid pandas styler issues on Streamlit Cloud)
    display_df = df.copy()
    for col in display_df.columns:
        if col != 'Yil':
            if 'EVI' in col or 'NDWI' in col or 'NDMI' in col or 'indeksi' in col:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")
            else:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")

    st.dataframe(
        display_df,
        use_container_width=True,
        height=400
    )
    
    # Grafiklar
    st.subheader("📊 Vizual Tahlil")
    
    fig1, fig2, fig3 = create_visualizations(df)
    
    st.plotly_chart(fig1, use_container_width=True)
    st.plotly_chart(fig2, use_container_width=True)
    st.plotly_chart(fig3, use_container_width=True)
    
    # Statistik tahlil
    st.subheader("📉 Statistik Xulosalar")
    
    stats = calculate_statistics(df)
    
    cols = st.columns(2)
    for i, (param, stat_dict) in enumerate(stats.items()):
        with cols[i % 2]:
            with st.expander(f"📊 {param}", expanded=False):
                for key, value in stat_dict.items():
                    st.write(f"**{key}:** {value}")
    
    # Export
    st.markdown("---")
    st.subheader("💾 Ma'lumotlarni Yuklab Olish")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 CSV formatda yuklab olish",
            data=csv,
            file_name=f"basin3_analysis_{start_year}-{end_year}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Excel export
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Natijalar', index=False)
            
            # Statistika sheetini qo'shish
            stats_df = pd.DataFrame(stats).T
            stats_df.to_excel(writer, sheet_name='Statistika')
        
        st.download_button(
            label="📥 Excel formatda yuklab olish",
            data=output.getvalue(),
            file_name=f"basin3_analysis_{start_year}-{end_year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #7f8c8d;'>
        <p>🛰️ <b>Basin3 Monitoring System</b> | Powered by Google Earth Engine & Streamlit</p>
        <p>📅 Oxirgi yangilanish: {}</p>
    </div>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M")), unsafe_allow_html=True)
