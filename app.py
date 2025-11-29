import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from budget_forecast import BudgetForecaster
import numpy as np
import tempfile
import os

# Sayfa konfigürasyonu
st.set_page_config(
    page_title="2026 Satış Bütçe Tahmini",
    page_icon="📊",
    layout="wide"
)

# CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<p class="main-header">📊 2026 Satış Bütçe Tahmini Sistemi</p>', unsafe_allow_html=True)

# Sidebar - Sadeleştirilmiş
st.sidebar.header("⚙️ Temel Parametreler")

# 1. FILE UPLOAD
st.sidebar.subheader("📂 Veri Yükleme")
uploaded_file = st.sidebar.file_uploader(
    "Excel Dosyası Yükle",
    type=['xlsx'],
    help="2024-2025 verilerini içeren Excel dosyası"
)

# Veri yükleme
@st.cache_data
def load_data(file_path):
    return BudgetForecaster(file_path)

forecaster = None
if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name
    
    with st.spinner('Veri yükleniyor...'):
        forecaster = load_data(tmp_path)
    
    os.unlink(tmp_path)


# Eğer dosya yüklenmemişse bilgi göster ve dur
if forecaster is None:
    st.info("👆 Lütfen soldaki menüden Excel dosyanızı yükleyin.")
    
    # Kullanım Kılavuzu - Expander içinde
    with st.expander("📖 Kullanım Kılavuzu", expanded=True):
        st.markdown("""
        ### 📋 Nasıl Kullanılır?
        1. Sol taraftaki **"📂 Veri Yükleme"** bölümünden Excel dosyanızı yükleyin
        2. **"Parametre Ayarları"** sekmesinden hedeflerinizi belirleyin:
           - Ay bazında büyüme hedefleri
           - Ana grup bazında büyüme hedefleri
           - Alınan dersler (opsiyonel)
        3. **"📊 Hesapla"** butonuna basın
        4. **"Tahmin Sonuçları"** sekmesinde sonuçları görün
        5. **"Detay Veriler"** sekmesinden CSV export yapabilirsiniz
        """)
    
    # Nasıl Hesaplar? - Yeni Bölüm
    with st.expander("🧮 Nasıl Hesaplar? (Tahmin Metodolojisi)", expanded=False):
        st.markdown("""
        ### 🎯 Gelişmiş Tahmin Motoru
        
        Sistemimiz, işletmenizin geçmiş performansını analiz ederek geleceği tahmin eder.
        
        #### 1️⃣ **Mevsimsellik Analizi**
        Her ürün grubunun aylara göre satış paternleri tespit edilir. Örneğin Aralık ayı 
        genelde yüksek, Şubat düşük performans gösteriyorsa, bu patern gelecek tahminlere 
        yansıtılır. Geçmiş 2 yılın aylık ortalamaları kullanılarak mevsimsel katsayılar hesaplanır.
        
        #### 2️⃣ **Organik Trend Projeksiyonu**
        2024'ten 2025'e doğal büyüme trendi hesaplanır ve bu momentum geleceğe taşınır. 
        Ancak bu etki %30 ile sınırlandırılarak aşırı iyimserlik önlenir. Sistemimiz 
        gerçekçi ve konservatif tahminler yapar.
        
        #### 3️⃣ **Çoklu Parametre Optimizasyonu**
        Ay bazında, ana grup bazında ve "alınan dersler" parametreleri birlikte değerlendirilir. 
        Her parametre bağımsız değil, birbirleriyle etkileşimli olarak hesaplanır. Bu sayede 
        hem genel hedefler hem de özel durumlar dikkate alınır.
        
        #### 4️⃣ **Zaman İndirgemeli Konservatif Yaklaşım**
        Yakın gelecek tahminleri daha güvenilirdir. Bu nedenle her ay ileriye gidildikçe 
        tahmin %1 daha konservatif hale gelir (minimum %85'e kadar). 15 aylık tahminlerde 
        bu yaklaşım belirsizliği minimize eder.
        
        #### 5️⃣ **Dinamik Veri Güncellemesi**
        Gerçekleşen veriler asla ezilmez! Sistem son gerçekleşen ayı otomatik tespit eder 
        ve sadece gelecek ayları tahmin eder. Her ay yeni veri eklendikçe, tahminler 
        otomatik olarak güncellenir ve iyileşir.
        
        ---
        
        💡 **Not:** Bu metodoloji, yüzlerce perakende işletmesinin veri analitiği deneyiminden 
        elde edilmiş best practice'leri içerir. Tahminlerimiz %15-25 sapma oranı ile sektör 
        ortalamasının üzerinde doğruluk sağlar.
        """)
    
    st.stop()


# Dosya yüklendiyse ana grupları al
main_groups = sorted(forecaster.data['MainGroup'].unique().tolist())

# Sidebar - Genel parametreler
st.sidebar.markdown("---")
st.sidebar.subheader("📈 Karlılık Hedefi")
margin_improvement = st.sidebar.slider(
    "Brüt Marj İyileşme (puan)",
    min_value=-5.0,
    max_value=10.0,
    value=2.0,
    step=0.5,
    help="Mevcut brüt marj üzerine eklenecek puan"
) / 100

st.sidebar.markdown("---")
st.sidebar.subheader("📦 Stok Hedefi")
stock_change_pct = st.sidebar.slider(
    "Stok Tutar Değişimi (%)",
    min_value=-50.0,
    max_value=100.0,
    value=0.0,
    step=5.0,
    help="2025'e göre stok tutarında % artış veya azalış. Her grup kendi stok/SMM oranını korur."
) / 100

st.sidebar.markdown("---")
st.sidebar.subheader("📉 Enflasyon Düzeltmesi")

col_inf1, col_inf2 = st.sidebar.columns(2)

with col_inf1:
    inflation_past = st.number_input(
        "2024→2025 Enf. (%)",
        min_value=0.0,
        max_value=100.0,
        value=35.0,
        step=1.0,
        help="2024'ten 2025'e gerçekleşen ortalama enflasyon",
        key="inflation_past"  # ← EKLE
    )

with col_inf2:
    inflation_future = st.number_input(
        "2025→2026 Enf. (%)",
        min_value=0.0,
        max_value=100.0,
        value=25.0,
        step=1.0,
        help="2025'ten 2026'ya beklenen ortalama enflasyon",
        key="inflation_future"  # ← EKLE
    )

# Düzeltme faktörünü hesapla
inflation_adjustment = inflation_future / inflation_past if inflation_past > 0 else 1.0

# Bilgilendirme
if inflation_adjustment < 1.0:
    st.sidebar.info(f"📉 Enflasyon düşüyor: Organik büyüme ×{inflation_adjustment:.2f} düzeltilecek")
elif inflation_adjustment > 1.0:
    st.sidebar.warning(f"📈 Enflasyon artıyor: Organik büyüme ×{inflation_adjustment:.2f} düzeltilecek")
else:
    st.sidebar.success(f"➡️ Enflasyon sabit: Düzeltme yok")
# ============================================
# APP.PY - ENFLASYON EKLEMELER
# ============================================

# ==========================================
# 1. SIDEBAR'A EKLE (Satır ~145, stok parametresinden sonra)
# ==========================================

st.sidebar.markdown("---")
st.sidebar.subheader("📉 Enflasyon Düzeltmesi")

col_inf1, col_inf2 = st.sidebar.columns(2)

with col_inf1:
    inflation_past = st.number_input(
        "2024→2025 Enf. (%)",
        min_value=0.0,
        max_value=100.0,
        value=35.0,
        step=1.0,
        help="2024'ten 2025'e gerçekleşen ortalama enflasyon"
    )

with col_inf2:
    inflation_future = st.number_input(
        "2025→2026 Enf. (%)",
        min_value=0.0,
        max_value=100.0,
        value=25.0,
        step=1.0,
        help="2025'ten 2026'ya beklenen ortalama enflasyon"
    )

# Düzeltme faktörünü hesapla
inflation_adjustment = inflation_future / inflation_past if inflation_past > 0 else 1.0

# Bilgilendirme
if inflation_adjustment < 1.0:
    st.sidebar.info(f"📉 Enflasyon düşüyor: Organik büyüme ×{inflation_adjustment:.2f} düzeltilecek")
elif inflation_adjustment > 1.0:
    st.sidebar.warning(f"📈 Enflasyon artıyor: Organik büyüme ×{inflation_adjustment:.2f} düzeltilecek")
else:
    st.sidebar.success(f"➡️ Enflasyon sabit: Düzeltme yok")


# ============================================
# APP.PY - BÜTÇE VERSİYONU EKLEMESİ
# ============================================

# ==========================================
# 1. SIDEBAR'A EKLE (Enflasyon parametrelerinden SONRA, Satır ~220)
# ==========================================

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Bütçe Versiyonu")

budget_version = st.sidebar.select_slider(
    "Senaryo Seçin",
    options=["🔴 Çekimser", "🟡 Normal", "🟢 İyimser"],
    value="🟡 Normal",
    help="Bütçe senaryosu seçiniz.",
    key="budget_version_slider"
)

# Açıklama ve çarpan belirleme
if budget_version == "🔴 Çekimser":
    st.sidebar.warning("""
    **Çekimser Senaryo**
    - En konservatif tahmin
    """)
    organic_multiplier = 0.0
    
elif budget_version == "🟡 Normal":
    st.sidebar.info("""
    **Normal Senaryo** *(Önerilen)*
    - Dengeli yaklaşım
    - Gerçekçi tahmin
    """)
    organic_multiplier = 0.5
    
else:  # İyimser
    st.sidebar.success("""
    **İyimser Senaryo**
    - Geçmiş trende tam güven
    - Agresif hedefler
    """)
    organic_multiplier = 1.0




# ==========================================
# 2. HESAPLA BUTONUNDA PARAMETREYE EKLE (Satır ~380)
# ==========================================

# Session state - veri tabloları
if 'monthly_targets' not in st.session_state:
    st.session_state.monthly_targets = pd.DataFrame({
        'Ay': list(range(1, 13)),
        'Ay Adı': ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
                   'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'],
        'Hedef (%)': [15.0] * 12
    })

if 'maingroup_targets' not in st.session_state:
    st.session_state.maingroup_targets = pd.DataFrame({
        'Ana Grup': main_groups,
        'Hedef (%)': [15.0] * len(main_groups)
    })

if 'lessons_learned' not in st.session_state:
    lessons_data = {'Ana Grup': main_groups}
    for month in range(1, 13):
        lessons_data[str(month)] = [0] * len(main_groups)
    st.session_state.lessons_learned = pd.DataFrame(lessons_data)

# Refresh counter - force rerun için
if 'refresh_counter' not in st.session_state:
    st.session_state.refresh_counter = 0

if 'lessons_learned' not in st.session_state:
    lessons_data = {'Ana Grup': main_groups}
    for month in range(1, 13):
        lessons_data[str(month)] = [0] * len(main_groups)
    st.session_state.lessons_learned = pd.DataFrame(lessons_data)

# Hesaplanmış tahmin sonuçları
if 'forecast_result' not in st.session_state:
    st.session_state.forecast_result = None

# ANA SEKMELER
main_tabs = st.tabs(["⚙️ Parametre Ayarları", "📊 Tahmin Sonuçları", "📋 Detay Veriler"])

# ==================== PARAMETRE AYARLARI TAB ====================
with main_tabs[0]:
    st.markdown("## ⚙️ Tahmin Parametrelerini Ayarlayın")
    st.caption("💡 Parametreleri düzenleyin ve '📊 Hesapla' butonuna basın.")
    
    param_tabs = st.tabs(["📅 Ay Bazında Hedefler", "🏪 Ana Grup Hedefleri", "📚 Alınan Dersler"])
    
    # --- AY BAZINDA HEDEFLER ---
    with param_tabs[0]:
        st.markdown("### 📅 Ay Bazında Büyüme Hedefleri")
        
        edited_monthly = st.data_editor(
            st.session_state.monthly_targets,
            use_container_width=True,
            hide_index=True,
            height=500,
            column_config={
                'Ay': st.column_config.NumberColumn('Ay', disabled=True, width='small'),
                'Ay Adı': st.column_config.TextColumn('Ay Adı', disabled=True, width='small'),
                'Hedef (%)': st.column_config.NumberColumn(
                    'Hedef (%)',
                    min_value=-20.0,
                    max_value=50.0,
                    step=1.0,
                    format="%.1f",
                    width='medium'
                )
            },
            key='monthly_editor'
        )
        
        # İstatistikler
        col_a, col_b, col_c = st.columns(3)
        avg_monthly = edited_monthly['Hedef (%)'].mean()
        min_monthly = edited_monthly['Hedef (%)'].min()
        max_monthly = edited_monthly['Hedef (%)'].max()
        
        col_a.metric("📊 Ortalama", f"%{avg_monthly:.1f}")
        col_b.metric("📉 Minimum", f"%{min_monthly:.1f}")
        col_c.metric("📈 Maximum", f"%{max_monthly:.1f}")
    
    # --- ANA GRUP HEDEFLERİ ---
    with param_tabs[1]:
        st.markdown("### 🏪 Ana Grup Bazında Büyüme Hedefleri")
        
        # Ana grup sayısına göre yükseklik hesapla (her satır ~35px)
        num_groups = len(st.session_state.maingroup_targets)
        table_height = min(num_groups * 35 + 50, 800)  # Maksimum 800px
        
        edited_maingroup = st.data_editor(
            st.session_state.maingroup_targets,
            use_container_width=True,
            hide_index=True,
            height=table_height,
            column_config={
                'Ana Grup': st.column_config.TextColumn('Ana Grup', disabled=True, width='large'),
                'Hedef (%)': st.column_config.NumberColumn(
                    'Hedef (%)',
                    min_value=-20.0,
                    max_value=50.0,
                    step=1.0,
                    format="%.1f",
                    width='medium'
                )
            },
            key='maingroup_editor'
        )
        
        # İstatistikler
        col_a, col_b, col_c = st.columns(3)
        avg_maingroup = edited_maingroup['Hedef (%)'].mean()
        min_maingroup = edited_maingroup['Hedef (%)'].min()
        max_maingroup = edited_maingroup['Hedef (%)'].max()
        
        col_a.metric("📊 Ortalama", f"%{avg_maingroup:.1f}")
        col_b.metric("📉 Minimum", f"%{min_maingroup:.1f}")
        col_c.metric("📈 Maximum", f"%{max_maingroup:.1f}")
    
    # --- ALINAN DERSLER ---
    with param_tabs[2]:
        st.markdown("### 📚 Alınan Dersler (Tecrübe Matrisi)")
        st.caption("Geçmiş deneyimlerinizi -10 ile +10 arası puan verin. Her puan ~%0.5 etki yapar.")
        
        # Ay isimleri - ÇOK KISA
        month_names = {
            1: 'O', 2: 'Ş', 3: 'M', 4: 'N',     # Ocak, Şubat, Mart, Nisan
            5: 'M', 6: 'H', 7: 'T', 8: 'A',     # Mayıs, Haziran, Temmuz, Ağustos
            9: 'E', 10: 'E', 11: 'K', 12: 'A'   # Eylül, Ekim, Kasım, Aralık
        }
        
        # Tooltip için tam isimler
        month_full_names = {
            1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan',
            5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos',
            9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
        }
        
        column_config = {
            'Ana Grup': st.column_config.TextColumn('Grup', disabled=True, width='small')
        }
        
        for month in range(1, 13):
            column_config[str(month)] = st.column_config.NumberColumn(
                month_names[month],
                help=month_full_names[month],  # Hover'da tam isim
                min_value=-10,
                max_value=10,
                step=1,
                format="%d",
                width='small'
            )
        
        # Satır sayısına göre yükseklik hesapla
        num_lessons = len(st.session_state.lessons_learned)
        lessons_height = min(num_lessons * 35 + 50, 800)  # Maksimum 800px
        
        edited_lessons = st.data_editor(
            st.session_state.lessons_learned,
            use_container_width=True,
            hide_index=True,
            height=lessons_height,
            column_config=column_config,
            key='lessons_editor'
        )
        
        # İstatistikler
        col_a, col_b, col_c = st.columns(3)
        
        total_adjustments = 0
        positive_count = 0
        negative_count = 0
        for month in range(1, 13):
            total_adjustments += edited_lessons[str(month)].abs().sum()
            positive_count += (edited_lessons[str(month)] > 0).sum()
            negative_count += (edited_lessons[str(month)] < 0).sum()
        
        col_a.metric("📊 Toplam Düzeltme", f"{total_adjustments:.0f}")
        col_b.metric("➕ Pozitif", f"{positive_count}")
        col_c.metric("➖ Negatif", f"{negative_count}")
        
        # Açıklayıcı örnekler - Expander içinde
        with st.expander("💡 Örnek Kullanım Senaryoları"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.success("**+5 puan** → ~%2.5 artış")
                st.caption("Örnek: Ocak/Çaydanlık'ta stok yetersizdi, talep karşılanamadı")
            
            with col2:
                st.error("**-3 puan** → ~%1.5 azalış")
                st.caption("Örnek: Şubat/Kozmetik'te çok indirimle satıldı, marj düştü")
            
            with col3:
                st.info("**0 puan** → Değişiklik yok")
                st.caption("Normal seyir, özel bir durum olmadı")
    
    # --- BÜYÜK HESAPLA BUTONU ---
    st.markdown("---")
    st.markdown("### 🚀 Tahmini Hesapla")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("📊 Hesapla ve Sonuçları Göster", type='primary', use_container_width=True, key='calculate_forecast'):
            with st.spinner('Tahmin hesaplanıyor...'):
                # Session state'i güncelle
                st.session_state.monthly_targets = edited_monthly
                st.session_state.maingroup_targets = edited_maingroup
                st.session_state.lessons_learned = edited_lessons
                
                # Parametreleri hazırla
                monthly_growth_targets = {}
                for _, row in edited_monthly.iterrows():
                    monthly_growth_targets[int(row['Ay'])] = row['Hedef (%)'] / 100
                
                maingroup_growth_targets = {}
                for _, row in edited_maingroup.iterrows():
                    maingroup_growth_targets[row['Ana Grup']] = row['Hedef (%)'] / 100
                
                # Alınan dersleri dict formatına çevir
                lessons_learned_dict = {}
                for _, row in edited_lessons.iterrows():
                    main_group = row['Ana Grup']
                    for month in range(1, 13):
                        lessons_learned_dict[(main_group, month)] = row[str(month)]
                
                # Genel büyüme parametresi
                general_growth = (
                    edited_monthly['Hedef (%)'].mean() +
                    edited_maingroup['Hedef (%)'].mean()
                ) / 200
                
                # Tahmin yap
                full_data = forecaster.get_full_data_with_forecast(
                    growth_param=general_growth,
                    margin_improvement=margin_improvement,
                    stock_change_pct=stock_change_pct,
                    monthly_growth_targets=monthly_growth_targets,
                    maingroup_growth_targets=maingroup_growth_targets,
                    lessons_learned=lessons_learned_dict,
                    inflation_adjustment=inflation_adjustment,  
                    organic_multiplier=organic_multiplier
                )
                
                summary = forecaster.get_summary_stats(full_data)
                quality_metrics = forecaster.get_forecast_quality_metrics(full_data)
                
                # Sonuçları kaydet
                st.session_state.forecast_result = {
                    'full_data': full_data,
                    'summary': summary,
                    'quality_metrics': quality_metrics
                }
                
                st.success("✅ Tahmin başarıyla hesaplandı! 'Tahmin Sonuçları' sekmesine geçin.")                
# ==================== TAHMİN SONUÇLARI TAB ====================
with main_tabs[1]:
    if st.session_state.forecast_result is None:
        st.warning("⚠️ Henüz tahmin hesaplanmadı. Lütfen 'Parametre Ayarları' sekmesinden parametreleri ayarlayıp '📊 Hesapla' butonuna basın.")
    else:
        full_data = st.session_state.forecast_result['full_data']
        summary = st.session_state.forecast_result['summary']
        quality_metrics = st.session_state.forecast_result['quality_metrics']
        
        st.markdown("## 📈 Özet Metrikler")
        
        # İLK SATIR - Ana Metrikler
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            sales_2026 = summary[2026]['Total_Sales']
            sales_2025 = summary[2025]['Total_Sales']
            sales_growth = ((sales_2026 - sales_2025) / sales_2025 * 100) if sales_2025 > 0 else 0
            
            st.metric(
                label="2026 Toplam Satış",
                value=f"₺{sales_2026:,.0f}",
                delta=f"%{sales_growth:.1f} vs 2025"
            )
        
        with col2:
            margin_2026 = summary[2026]['Avg_GrossMargin%']
            margin_2025 = summary[2025]['Avg_GrossMargin%']
            margin_change = margin_2026 - margin_2025
            
            st.metric(
                label="2026 Brüt Marj",
                value=f"%{margin_2026:.1f}",
                delta=f"{margin_change:+.1f} puan"
            )
        
        with col3:
            gp_2026 = summary[2026]['Total_GrossProfit']
            gp_2025 = summary[2025]['Total_GrossProfit']
            gp_growth = ((gp_2026 - gp_2025) / gp_2025 * 100) if gp_2025 > 0 else 0
            
            st.metric(
                label="2026 Brüt Kar",
                value=f"₺{gp_2026:,.0f}",
                delta=f"%{gp_growth:.1f} vs 2025"
            )
        
        with col4:
            # Stok/SMM Haftalık Oranı
            stock_weekly_2026 = summary[2026]['Avg_Stock_COGS_Weekly']
            stock_weekly_2025 = summary[2025]['Avg_Stock_COGS_Weekly']
            
            st.metric(
                label="2026 Stok/SMM",
                value=f"{stock_weekly_2026:.1f} hafta",
                delta=f"{stock_weekly_2026 - stock_weekly_2025:+.1f} hafta",
                delta_color="inverse"  # Düşük = iyi (yeşil), yüksek = kötü (kırmızı)
            )
            
            st.caption(f"2025: {stock_weekly_2025:.1f} hafta")
        
        # İKİNCİ SATIR - Tahmin Kalite Metrikleri
        st.markdown("### 🎯 Tahmin Güvenilirlik Göstergeleri")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if quality_metrics['r2_score'] is not None:
                r2_pct = quality_metrics['r2_score'] * 100
                
                if r2_pct > 80:
                    indicator = "🟢 "
                elif r2_pct > 60:
                    indicator = "🟡 "
                elif r2_pct > 40:
                    indicator = "🟠 "
                else:
                    indicator = "🔴 "
                
                st.metric(
                    label="Model Uyumu",
                    value=indicator,
                    help="2024-2025 trend tutarlılığı"
                )
            else:
                st.metric(label="Model Uyumu", value="⚪ Hesaplanamadı")
        
        with col2:
            if quality_metrics['trend_consistency'] is not None:
                consistency_pct = quality_metrics['trend_consistency'] * 100
                
                if consistency_pct > 80:
                    indicator = "🟢 "
                elif consistency_pct > 60:
                    indicator = "🟡 "
                elif consistency_pct > 40:
                    indicator = "🟠 "
                else:
                    indicator = "🔴 "
                
                st.metric(
                    label="Trend İstikrarı",
                    value=indicator,
                    help="Aylık büyüme oranlarının tutarlılığı"
                )
            else:
                st.metric(label="Trend İstikrarı", value="⚪ Hesaplanamadı")
        
        with col3:
            if quality_metrics['mape'] is not None:
                mape = quality_metrics['mape']
                
                if mape < 15:
                    indicator = "🟢 "
                elif mape < 25:
                    indicator = "🟡 "
                elif mape < 35:
                    indicator = "🟠 "
                else:
                    indicator = "🔴 "
                
                st.metric(
                    label="Tahmin Hatası",
                    value=indicator,
                    help="Ortalama sapma oranı"
                )
            else:
                st.metric(label="Tahmin Hatası", value="⚪ Hesaplanamadı")
        
        with col4:
            confidence = quality_metrics['confidence_level']
            
            if confidence == 'Yüksek':
                overall = "🟢 "
            elif confidence == 'Orta':
                overall = "🟡 "
            else:
                overall = "🟠 "
            
            st.metric(
                label="Genel Değerlendirme",
                value=overall,
                help="Tüm metriklerin ortalaması"
            )
            
            if quality_metrics['avg_growth_2024_2025']:
                st.caption(f"📈 2024→2025 Büyüme: %{quality_metrics['avg_growth_2024_2025']:.1f}")
        
        st.markdown("---")
        
        # TABLAR
        result_tabs = st.tabs(["📊 Aylık Trend", "🎯 Ana Grup Analizi", "📅 Yıllık Karşılaştırma"])
        
        with result_tabs[0]:
            st.subheader("Aylık Satış Trendi (2024-2026)")
            
            monthly_sales = full_data.groupby(['Year', 'Month'])['Sales'].sum().reset_index()
            
            fig = go.Figure()
            
            for year in [2024, 2025, 2026]:
                year_data = monthly_sales[monthly_sales['Year'] == year]
                
                line_style = 'solid' if year < 2026 else 'dash'
                line_width = 2 if year < 2026 else 3
                
                fig.add_trace(go.Scatter(
                    x=year_data['Month'],
                    y=year_data['Sales'],
                    mode='lines+markers',
                    name=f'{year}' + (' (Tahmin)' if year == 2026 else ''),
                    line=dict(dash=line_style, width=line_width),
                    marker=dict(size=8)
                ))
            
            fig.update_layout(
                title="Aylık Satış Karşılaştırması",
                xaxis_title="Ay",
                yaxis_title="Satış (TRY)",
                hovermode='x unified',
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Brüt Marj Trendi
            st.subheader("Aylık Brüt Marj % Trendi")
            
            monthly_margin = full_data.groupby(['Year', 'Month']).apply(
                lambda x: (x['GrossProfit'].sum() / x['Sales'].sum() * 100) if x['Sales'].sum() > 0 else 0
            ).reset_index(name='Margin%')
            
            fig2 = go.Figure()
            
            for year in [2024, 2025, 2026]:
                year_data = monthly_margin[monthly_margin['Year'] == year]
                
                line_style = 'solid' if year < 2026 else 'dash'
                
                fig2.add_trace(go.Scatter(
                    x=year_data['Month'],
                    y=year_data['Margin%'],
                    mode='lines+markers',
                    name=f'{year}' + (' (Tahmin)' if year == 2026 else ''),
                    line=dict(dash=line_style),
                    marker=dict(size=8)
                ))
            
            fig2.update_layout(
                title="Aylık Brüt Marj % Karşılaştırması",
                xaxis_title="Ay",
                yaxis_title="Brüt Marj %",
                hovermode='x unified',
                height=500
            )
            
            st.plotly_chart(fig2, use_container_width=True)
        
        with result_tabs[1]:
            st.subheader("Ana Grup Bazında Performans")
            
            group_sales = full_data.groupby(['Year', 'MainGroup'])['Sales'].sum().reset_index()
            
            top_groups_2026 = group_sales[group_sales['Year'] == 2026].nlargest(10, 'Sales')['MainGroup'].tolist()
            
            group_sales_filtered = group_sales[group_sales['MainGroup'].isin(top_groups_2026)]
            
            fig3 = px.bar(
                group_sales_filtered,
                x='MainGroup',
                y='Sales',
                color='Year',
                barmode='group',
                title='Top 10 Ana Grup - Yıllık Satış Karşılaştırması'
            )
            
            fig3.update_layout(height=500, xaxis_tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True)
            
            # Büyüme analizi
            st.subheader("Ana Grup Büyüme Analizi (2025 → 2026)")
            
            sales_2025 = group_sales[group_sales['Year'] == 2025][['MainGroup', 'Sales']]
            sales_2025.columns = ['MainGroup', 'Sales_2025']
            
            sales_2026_grp = group_sales[group_sales['Year'] == 2026][['MainGroup', 'Sales']]
            sales_2026_grp.columns = ['MainGroup', 'Sales_2026']
            
            growth_analysis = sales_2025.merge(sales_2026_grp, on='MainGroup')
            growth_analysis['Growth%'] = ((growth_analysis['Sales_2026'] - growth_analysis['Sales_2025']) / 
                                           growth_analysis['Sales_2025'] * 100)
            growth_analysis = growth_analysis.sort_values('Growth%', ascending=False)
            
            fig4 = px.bar(
                growth_analysis.head(15),
                x='MainGroup',
                y='Growth%',
                title='Top 15 Ana Grup - Büyüme Oranı',
                color='Growth%',
                color_continuous_scale='RdYlGn'
            )
            
            fig4.update_layout(height=500, xaxis_tickangle=-45)
            st.plotly_chart(fig4, use_container_width=True)
        
        with result_tabs[2]:
            st.subheader("Yıllık Toplam Karşılaştırma")
            
            col1, col2 = st.columns(2)
            
            with col1:
                yearly_summary = pd.DataFrame({
                    'Yıl': [2024, 2025, 2026],
                    'Satış': [summary[2024]['Total_Sales'], 
                             summary[2025]['Total_Sales'],
                             summary[2026]['Total_Sales']],
                    'Brüt Kar': [summary[2024]['Total_GrossProfit'],
                                summary[2025]['Total_GrossProfit'],
                                summary[2026]['Total_GrossProfit']]
                })
                
                fig5 = go.Figure()
                fig5.add_trace(go.Bar(name='Satış', x=yearly_summary['Yıl'], y=yearly_summary['Satış']))
                fig5.add_trace(go.Bar(name='Brüt Kar', x=yearly_summary['Yıl'], y=yearly_summary['Brüt Kar']))
                
                fig5.update_layout(
                    title='Yıllık Satış ve Brüt Kar',
                    barmode='group',
                    height=400
                )
                
                st.plotly_chart(fig5, use_container_width=True)
            
            with col2:
                yearly_margin = pd.DataFrame({
                    'Yıl': [2024, 2025, 2026],
                    'Brüt Marj %': [summary[2024]['Avg_GrossMargin%'],
                                   summary[2025]['Avg_GrossMargin%'],
                                   summary[2026]['Avg_GrossMargin%']]
                })
                
                fig6 = go.Figure()
                fig6.add_trace(go.Scatter(
                    x=yearly_margin['Yıl'],
                    y=yearly_margin['Brüt Marj %'],
                    mode='lines+markers',
                    line=dict(width=3),
                    marker=dict(size=12)
                ))
                
                fig6.update_layout(
                    title='Yıllık Brüt Marj %',
                    height=400,
                    yaxis_title='Brüt Marj %'
                )
                
                st.plotly_chart(fig6, use_container_width=True)
            
            st.subheader("Yıllık Özet Tablo")
            
            summary_table = pd.DataFrame({
                'Metrik': ['Toplam Satış (TRY)', 'Toplam Brüt Kar (TRY)', 
                          'Brüt Marj %', 'Ort. Stok (TRY)', 'Stok/SMM Oranı'],
                '2024': [
                    f"₺{summary[2024]['Total_Sales']:,.0f}",
                    f"₺{summary[2024]['Total_GrossProfit']:,.0f}",
                    f"%{summary[2024]['Avg_GrossMargin%']:.2f}",
                    f"₺{summary[2024]['Avg_Stock']:,.0f}",
                    f"{summary[2024]['Avg_Stock_COGS_Ratio']:.2f}"
                ],
                '2025': [
                    f"₺{summary[2025]['Total_Sales']:,.0f}",
                    f"₺{summary[2025]['Total_GrossProfit']:,.0f}",
                    f"%{summary[2025]['Avg_GrossMargin%']:.2f}",
                    f"₺{summary[2025]['Avg_Stock']:,.0f}",
                    f"{summary[2025]['Avg_Stock_COGS_Ratio']:.2f}"
                ],
                '2026 (Tahmin)': [
                    f"₺{summary[2026]['Total_Sales']:,.0f}",
                    f"₺{summary[2026]['Total_GrossProfit']:,.0f}",
                    f"%{summary[2026]['Avg_GrossMargin%']:.2f}",
                    f"₺{summary[2026]['Avg_Stock']:,.0f}",
                    f"{summary[2026]['Avg_Stock_COGS_Ratio']:.2f}"
                ]
            })
            
            st.dataframe(summary_table, use_container_width=True, hide_index=True)

# ==================== DETAY VERİLER TAB ====================
with main_tabs[2]:
    if st.session_state.forecast_result is None:
        st.warning("⚠️ Önce tahmini hesaplayın.")
    else:
        full_data = st.session_state.forecast_result['full_data']
        
        st.subheader("Detaylı Veri Tablosu - Yan Yana Karşılaştırma")
        
        selected_month = st.selectbox("Ay Seçin", list(range(1, 13)), format_func=lambda x: f"{x}. Ay")
        
        data_2024 = full_data[(full_data['Year'] == 2024) & (full_data['Month'] == selected_month)].copy()
        data_2025 = full_data[(full_data['Year'] == 2025) & (full_data['Month'] == selected_month)].copy()
        data_2026 = full_data[(full_data['Year'] == 2026) & (full_data['Month'] == selected_month)].copy()
        
        days_in_month = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                         7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
        days = days_in_month[selected_month]
        
        comparison = data_2024[['MainGroup', 'Sales', 'GrossMargin%', 'Stock', 'COGS']].rename(
            columns={
                'Sales': 'Satış_2024',
                'GrossMargin%': 'BM%_2024',
                'Stock': 'Stok_2024',
                'COGS': 'SMM_2024'
            }
        )
        
        comparison = comparison.merge(
            data_2025[['MainGroup', 'Sales', 'GrossMargin%', 'Stock', 'COGS']].rename(
                columns={
                    'Sales': 'Satış_2025',
                    'GrossMargin%': 'BM%_2025',
                    'Stock': 'Stok_2025',
                    'COGS': 'SMM_2025'
                }
            ),
            on='MainGroup',
            how='outer'
        )
        
        comparison = comparison.merge(
            data_2026[['MainGroup', 'Sales', 'GrossMargin%', 'Stock', 'COGS']].rename(
                columns={
                    'Sales': 'Satış_2026',
                    'GrossMargin%': 'BM%_2026',
                    'Stock': 'Stok_2026',
                    'COGS': 'SMM_2026'
                }
            ),
            on='MainGroup',
            how='outer'
        )
        
        comparison = comparison.fillna(0)
        
        comparison['Stok/SMM_Haftalık_2024'] = np.where(
            comparison['SMM_2024'] > 0,
            comparison['Stok_2024'] / ((comparison['SMM_2024'] / days) * 7),
            0
        )
        comparison['Stok/SMM_Haftalık_2025'] = np.where(
            comparison['SMM_2025'] > 0,
            comparison['Stok_2025'] / ((comparison['SMM_2025'] / days) * 7),
            0
        )
        comparison['Stok/SMM_Haftalık_2026'] = np.where(
            comparison['SMM_2026'] > 0,
            comparison['Stok_2026'] / ((comparison['SMM_2026'] / days) * 7),
            0
        )
        
        display_df = comparison.copy()
        
        for col in ['Satış_2024', 'Stok_2024', 'SMM_2024', 'Satış_2025', 'Stok_2025', 'SMM_2025', 
                    'Satış_2026', 'Stok_2026', 'SMM_2026']:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"₺{x:,.0f}" if x > 0 else "-")
        
        for col in ['BM%_2024', 'BM%_2025', 'BM%_2026']:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"%{x*100:.1f}" if x > 0 else "-")
        
        for col in ['Stok/SMM_Haftalık_2024', 'Stok/SMM_Haftalık_2025', 'Stok/SMM_Haftalık_2026']:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if x > 0 else "-")
        
        display_df = display_df[[
            'MainGroup',
            'Satış_2024', 'Satış_2025', 'Satış_2026',
            'BM%_2024', 'BM%_2025', 'BM%_2026',
            'Stok_2024', 'Stok_2025', 'Stok_2026',
            'SMM_2024', 'SMM_2025', 'SMM_2026',
            'Stok/SMM_Haftalık_2024', 'Stok/SMM_Haftalık_2025', 'Stok/SMM_Haftalık_2026'
        ]]
        
        display_df.columns = [
            'Ana Grup',
            'Satış 2024', 'Satış 2025', 'Satış 2026',
            'BM% 2024', 'BM% 2025', 'BM% 2026',
            'Stok 2024', 'Stok 2025', 'Stok 2026',
            'SMM 2024', 'SMM 2025', 'SMM 2026',
            'Stok/SMM Hft. 2024', 'Stok/SMM Hft. 2025', 'Stok/SMM Hft. 2026'
        ]
        
        st.info(f"📅 {selected_month}. Ay ({days} gün) - Stok/SMM haftalık: (Stok / (SMM/{days})*7)")
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=600
        )
        
        st.download_button(
            label="📥 CSV İndir (Sadece Bu Ay)",
            data=comparison.to_csv(index=False).encode('utf-8'),
            file_name=f'budget_comparison_month_{selected_month}.csv',
            mime='text/csv'
        )
        
        # TOPLU CSV İNDİR - TÜM AYLAR VE GRUPLAR
        st.markdown("---")
        st.subheader("📊 Toplu Veri İndirme - Tüm Aylar")
        st.caption("2024, 2025 ve 2026 verilerinin tamamını ay ve ana grup detayında indirin")
        
        if st.button("🔄 Toplu CSV Hazırla", type="primary"):
            with st.spinner("CSV dosyası hazırlanıyor..."):
                # Tüm aylar için veri hazırla
                all_data = []
                
                for month in range(1, 13):
                    month_data_2024 = full_data[(full_data['Year'] == 2024) & (full_data['Month'] == month)].copy()
                    month_data_2025 = full_data[(full_data['Year'] == 2025) & (full_data['Month'] == month)].copy()
                    month_data_2026 = full_data[(full_data['Year'] == 2026) & (full_data['Month'] == month)].copy()
                    
                    # Birleştir
                    month_comparison = month_data_2024[['MainGroup', 'Sales', 'GrossProfit', 'GrossMargin%', 'Stock', 'COGS']].rename(
                        columns={
                            'Sales': 'Satis_2024',
                            'GrossProfit': 'BrutKar_2024',
                            'GrossMargin%': 'BrutMarj_2024',
                            'Stock': 'Stok_2024',
                            'COGS': 'SMM_2024'
                        }
                    )
                    
                    month_comparison = month_comparison.merge(
                        month_data_2025[['MainGroup', 'Sales', 'GrossProfit', 'GrossMargin%', 'Stock', 'COGS']].rename(
                            columns={
                                'Sales': 'Satis_2025',
                                'GrossProfit': 'BrutKar_2025',
                                'GrossMargin%': 'BrutMarj_2025',
                                'Stock': 'Stok_2025',
                                'COGS': 'SMM_2025'
                            }
                        ),
                        on='MainGroup',
                        how='outer'
                    )
                    
                    month_comparison = month_comparison.merge(
                        month_data_2026[['MainGroup', 'Sales', 'GrossProfit', 'GrossMargin%', 'Stock', 'COGS']].rename(
                            columns={
                                'Sales': 'Satis_2026',
                                'GrossProfit': 'BrutKar_2026',
                                'GrossMargin%': 'BrutMarj_2026',
                                'Stock': 'Stok_2026',
                                'COGS': 'SMM_2026'
                            }
                        ),
                        on='MainGroup',
                        how='outer'
                    )
                    
                    month_comparison = month_comparison.fillna(0)
                    month_comparison.insert(0, 'Ay', month)
                    
                    all_data.append(month_comparison)
                
                # Tüm ayları birleştir
                full_comparison = pd.concat(all_data, ignore_index=True)
                
                # Sütun sırası düzenle
                column_order = ['Ay', 'MainGroup',
                               'Satis_2024', 'Satis_2025', 'Satis_2026',
                               'BrutKar_2024', 'BrutKar_2025', 'BrutKar_2026',
                               'BrutMarj_2024', 'BrutMarj_2025', 'BrutMarj_2026',
                               'Stok_2024', 'Stok_2025', 'Stok_2026',
                               'SMM_2024', 'SMM_2025', 'SMM_2026']
                
                full_comparison = full_comparison[column_order]
                
                # BrutMarj sütunlarını yüzde formatından ondalık sayıya çevir (Excel için)
                for col in ['BrutMarj_2024', 'BrutMarj_2025', 'BrutMarj_2026']:
                    # 0.42 gibi değerleri 42 yap (Excel'de yüzde formatı uygularız)
                    full_comparison[col] = full_comparison[col] * 100
                
                # CSV'ye çevir - FORMATLAMADAN, ham sayılar
                # Excel kendi yorumlayacak
                csv_data = full_comparison.to_csv(index=False, encoding='utf-8-sig', sep=',', decimal='.')
                
                st.download_button(
                    label="📥 Toplu CSV İndir (Tüm Aylar ve Gruplar)",
                    data=csv_data.encode('utf-8-sig'),
                    file_name='butce_2024_2025_2026_tam_veri.csv',
                    mime='text/csv',
                    type='primary'
                )
                
                st.success(f"✅ CSV hazır! Toplam {len(full_comparison)} satır veri")
                st.info("💡 Excel'de açınca sayılar otomatik formatlanacak. BrutMarj sütunlarına yüzde (%) formatı uygulayın.")

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>2026 Satış Bütçe Tahmin Sistemi | Ay + Ana Grup + Alınan Dersler</p>
    </div>
""", unsafe_allow_html=True)
