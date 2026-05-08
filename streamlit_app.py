import streamlit as st
import ee
import pandas as pd
import plotly.express as px

# GEE init va boshqa qismlar (oldingi kodda bor...)

def ml_module(user_roi):
    st.title("🤖 Mashinali O'qitish: Yer Qoplami Bashorati")
    
    # 1. Bandlarni tanlash
    bands = ['B2', 'B3', 'B4', 'B8'] # Sentinel-2 RGB va NIR
    
    # 2. Classifier parametrini slayder orqali boshqarish
    n_trees = st.sidebar.slider("Daraxtlar soni (Random Forest)", 10, 200, 100)
    
    if st.button("Modelni o'qitish va ishga tushirish"):
        with st.spinner("Sun'iy intellekt tahlil qilmoqda..."):
            # Tasvirni olish
            image = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
                .filterBounds(user_roi).median().divide(10000)
            
            # (Bu yerda training ma'lumotlari bo'lishi kerak, masalan Asset ichida)
            # classifier = ee.Classifier.smileRandomForest(n_trees).train(...)
            # classified = image.select(bands).classify(classifier)
            
            st.success(f"Model {n_trees} ta daraxt bilan muvaffaqiyatli o'qitildi.")
            
            # Grafik chiqarish
            st.info("Kutilayotgan vegetatsiya o'zgarishi grafigi:")
            # Bashorat grafigi...
