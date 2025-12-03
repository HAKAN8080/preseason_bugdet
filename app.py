import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from budget_forecast import BudgetForecaster
import numpy as np
import tempfile
import os
import locale
import json
from io import BytesIO

# Türkçe locale
try:
    locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.1254')
    except:
        pass

# Config
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
    .info-box {
        background-color: #e3f2fd;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #2196f3;
        margin: 10px 0;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">📊 2026 Satış Bütçe Tahmini Sistemi</p>', unsafe_allow_html=True)

# Format fonksiyonları
def format_number(num, decimals=0):
    if pd.isna(num) or num == 0:
        return "-"
    if decimals == 0:
        return f"{num:,.0f}".replace(",", ".")
    else:
        formatted = f"{num:,.{decimals}f}"
        formatted = formatted.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return formatted

def format_currency(num):
    if pd.isna(num) or num == 0:
        return "-"
    return f"₺{format_number(num, 0)}"

def format_percent(num, decimals=1):
    if pd.isna(num):
        return "-"
    return f"%{format_number(num, decimals)}"

# PARAMETRE KAYDETME FONKSİYONLARI
def save_parameters_to_file():
    """Parametreleri JSON dosyasına kaydet"""
    try:
        params = {
            'monthly_targets': st.session_state.monthly_targets.to_dict('records'),
            'maingroup_targets': st.session_state.maingroup_targets.to_dict('records'),
            'lessons_learned': st.session_state.lessons_learned.to_dict('records'),
            'price_changes': st.session_state.price_changes.to_dict('records'),
            'margin_improvement': st.session_state.get('margin_improvement', 2.0),
            'stock_change_pct': st.session_state.get('stock_change_pct', 0.0),
            'inflation_past': st.session_state.get('inflation_past', 35.0),
            'inflation_future': st.session_state.get('inflation_future', 25.0),
            'budget_version': st.session_state.get('budget_version_slider', '🟡 Normal')
        }
        
        with open('saved_parameters.json', 'w', encoding='utf-8') as f:
            json.dump(params, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        st.error(f"Kayıt hatası: {e}")
        return False

def load_parameters_from_file():
    """JSON dosyasından parametreleri yükle"""
    try:
        if os.path.exists('saved_parameters.json'):
            with open('saved_parameters.json', 'r', encoding='utf-8') as f:
                params = json.load(f)
            
            st.session_state.monthly_targets = pd.DataFrame(params['monthly_targets'])
            st.session_state.maingroup_targets = pd.DataFrame(params['maingroup_targets'])
            st.session_state.lessons_learned = pd.DataFrame(params['lessons_learned'])
            st.session_state.price_changes = pd.DataFrame(params['price_changes'])
            
            return True
        return False
    except Exception as e:
        st.error(f"Yükleme hatası: {e}")
        return False

# EXCEL TEMPLATE FONKSİYONLARI
def create_parameter_template():
    """Parametre şablonu Excel oluştur"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Ay Hedefleri
        monthly_template = pd.DataFrame({
            'Ay': list(range(1, 13)),
            'Ay Adı': ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
                       'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'],
            'Hedef (%)': [20.0] * 12
        })
        monthly_template.to_excel(writer, sheet_name='Ay Hedefleri', index=False)
        
        # Sheet 2: Ana Grup Hedefleri - GERÇEK GRUPLARI KULLAN
        if 'maingroup_targets' in st.session_state:
            maingroup_template = st.session_state.maingroup_targets.copy()
        else:
            # Fallback: örnek gruplar
            maingroup_template = pd.DataFrame({
                'Ana Grup': ['Örnek Grup 1', 'Örnek Grup 2'],
                'Hedef (%)': ['20.0', '20.0']
            })
        maingroup_template.to_excel(writer, sheet_name='Ana Grup Hedefleri', index=False)
        
        # Sheet 3: Açıklama
        instructions = pd.DataFrame({
            'Talimatlar': [
                '1. "Ay Hedefleri" sekmesini doldurun',
                '2. "Ana Grup Hedefleri" zaten dolu - sadece hedefleri değiştirin',
                '3. Hedefleri % olarak girin (örn: 20 = %20 büyüme)',
                '4. Sıfırlamak için * yazın',
                '5. Dosyayı kaydedin ve uygulamaya yükleyin',
                '6. ÖNEMLI: Dosyayı yükledikten sonra sayfayı yenilemeyin!'
            ]
        })
        instructions.to_excel(writer, sheet_name='Açıklama', index=False)
    
    output.seek(0)
    return output

def load_parameters_from_excel(uploaded_file):
    """Excel'den parametreleri yükle"""
    try:
        # Ay hedefleri
        monthly_df = pd.read_excel(uploaded_file, sheet_name='Ay Hedefleri')
        monthly_df['Hedef (%)'] = monthly_df['Hedef (%)'].astype(str)
        st.session_state.monthly_targets = monthly_df
        
        # Ana grup hedefleri
        maingroup_df = pd.read_excel(uploaded_file, sheet_name='Ana Grup Hedefleri')
        maingroup_df['Hedef (%)'] = maingroup_df['Hedef (%)'].astype(str)
        st.session_state.maingroup_targets = maingroup_df
        
        # Başarılı yükleme - parametreleri kaydet
        save_parameters_to_file()
        
        return True, "✅ Parametreler başarıyla yüklendi!"
    except Exception as e:
        return False, f"❌ Hata: {e}"

# Sidebar
st.sidebar.header("⚙️ Temel Parametreler")

# INFO BOX
st.sidebar.markdown("""
<div class="info-box">
⭐ <b>İpucu:</b> Bir satırı sıfırlamak için <code>*</code> yazın<br>
💾 Parametreler otomatik kaydedilir<br>
📊 Excel şablonu ile toplu güncelleme yapabilirsiniz
</div>
""", unsafe_allow_html=True)

# FILE UPLOAD
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
    
    current_file_name = uploaded_file.name
    
    if 'last_uploaded_file' not in st.session_state or st.session_state.last_uploaded_file != current_file_name:
        keys_to_clear = [k for k in st.session_state.keys() if k not in ['last_uploaded_file']]
        for key in keys_to_clear:
            del st.session_state[key]
        
        st.session_state.last_uploaded_file = current_file_name
        
        # Kaydedilmiş parametreleri yükle
        if load_parameters_from_file():
            st.sidebar.success("💾 Kaydedilmiş parametreler yüklendi")
        
        st.rerun()


if forecaster is None:
    st.info("👆 Lütfen soldaki menüden Excel dosyanızı yükleyin.")
    
    with st.expander("📖 Kullanım Kılavuzu", expanded=True):
        st.markdown("""
        ### 📋 Nasıl Kullanılır?
        
        1. **Veri Yükleme**
           - Sol menüden Excel dosyanızı yükleyin
           - Dosya 2024-2025 verilerini içermeli
        
        2. **Bütçe Versiyonu Seçin**
           - 🔴 Çekimser: Konservatif tahmin
           - 🟡 Normal: Dengeli yaklaşım (önerilen)
           - 🟢 İyimser: Agresif hedefler
        
        3. **Parametreleri Ayarlayın**
           - Ay Bazında Hedefler
           - Ana Grup Hedefleri
           - Alınan Dersler (-10 ile +10)
           - Fiyat Değişimi
        
        4. **Hesapla**
           - Parametreler otomatik kaydedilir
           - Tahmin Sonuçları sekmesinde sonuçları görün
        
        ### 💡 İpuçları
        - `*` yazarak satırları sıfırlayabilirsiniz
        - Excel şablonu ile toplu parametre güncellemesi yapabilirsiniz
        - Gelişmiş ayarlarla etki oranlarını özelleştirebilirsiniz
        """)
    
    with st.expander("🧮 Nasıl Hesaplar?"):
        st.markdown("""
        ### 🎯 Gelişmiş Tahmin Motoru
        
        **1. Mevsimsellik Analizi**
        - Her ürün grubunun aylara göre satış paternleri tespit edilir
        
        **2. Organik Trend Projeksiyonu**
        - 2024'ten 2025'e doğal büyüme trendi hesaplanır
        - Enflasyon düzeltmesi yapılır
        
        **3. Çoklu Parametre Optimizasyonu**
        - Ay bazında hedefler
        - Ana grup hedefleri
        - Alınan dersler
        - Tümü kombine edilir: `(Ay + Grup) / 2 + Dersler`
        
        **4. Parametrik Etki Oranları**
        - Çekimser: %50 etki
        - Normal: %100 etki
        - İyimser: %120 etki
        
        **5. Stok Sağlığı Faktörü**
        - Yavaş hareket eden ürünler: Hafif azalış
        - Hızlı hareket eden ürünler: Hafif artış
        
        **6. Dinamik Veri Güncellemesi**
        - Gerçekleşen veriler asla ezilmez
        - Sadece gelecek aylar tahmin edilir
        """)
    
    st.stop()


# Ana grupları al
main_groups = sorted(forecaster.data['MainGroup'].unique().tolist())

# Sidebar parametreler
st.sidebar.markdown("---")
st.sidebar.subheader("📈 Karlılık Hedefi")
margin_improvement = st.sidebar.slider(
    "Brüt Marj İyileşme (puan)",
    min_value=-5.0,
    max_value=10.0,
    value=st.session_state.get('margin_improvement', 2.0),
    step=0.5,
    key='margin_improvement'
) / 100

st.sidebar.markdown("---")
st.sidebar.subheader("📦 Stok Hedefi")
stock_change_pct = st.sidebar.slider(
    "Stok Tutar Değişimi (%)",
    min_value=-50.0,
    max_value=100.0,
    value=st.session_state.get('stock_change_pct', 0.0),
    step=5.0,
    key='stock_change_pct'
) / 100

st.sidebar.markdown("---")
st.sidebar.subheader("📉 Enflasyon Düzeltmesi")

col_inf1, col_inf2 = st.sidebar.columns(2)

with col_inf1:
    inflation_past = st.number_input(
        "2024→2025 (%)",
        min_value=0.0,
        max_value=100.0,
        value=st.session_state.get('inflation_past', 35.0),
        step=1.0,
        key="inflation_past"
    )

with col_inf2:
    inflation_future = st.number_input(
        "2025→2026 (%)",
        min_value=0.0,
        max_value=100.0,
        value=st.session_state.get('inflation_future', 25.0),
        step=1.0,
        key="inflation_future"
    )

inflation_adjustment = inflation_future / inflation_past if inflation_past > 0 else 1.0

if inflation_adjustment < 1.0:
    st.sidebar.info(f"📉 Enflasyon düşüyor: ×{inflation_adjustment:.2f}")
elif inflation_adjustment > 1.0:
    st.sidebar.warning(f"📈 Enflasyon artıyor: ×{inflation_adjustment:.2f}")
else:
    st.sidebar.success(f"➡️ Enflasyon sabit")

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Bütçe Versiyonu")

budget_version = st.sidebar.select_slider(
    "Senaryo Seçin",
    options=["🔴 Çekimser", "🟡 Normal", "🟢 İyimser"],
    value=st.session_state.get('budget_version_slider', '🟡 Normal'),
    key="budget_version_slider"
)

# Otomatik etki oranları
if budget_version == "🔴 Çekimser":
    organic_multiplier = 0.0
    monthly_effect = 0.50  # %50 etki
    maingroup_effect = 0.50  # %50 etki
    organic_growth_rate = 0.10  # %10 organik
    st.sidebar.warning("**Çekimser** - Parametreler %50 etki")
elif budget_version == "🟡 Normal":
    organic_multiplier = 0.5
    monthly_effect = 1.00  # %100 etki (tam)
    maingroup_effect = 1.00  # %100 etki (tam)
    organic_growth_rate = 0.15  # %15 organik
    st.sidebar.info("**Normal** - Parametreler %100 etki *(Önerilen)*")
else:
    organic_multiplier = 1.0
    monthly_effect = 1.20  # %120 etki (artırımlı)
    maingroup_effect = 1.20  # %120 etki (artırımlı)
    organic_growth_rate = 0.20  # %20 organik
    st.sidebar.success("**İyimser** - Parametreler %120 etki")

# GELİŞMİŞ AYARLAR (isteğe bağlı)
with st.sidebar.expander("🔧 Gelişmiş Parametre Ayarları"):
    st.markdown("### 📊 Etki Oranları")
    st.caption("Varsayılan değerler bütçe versiyonuna göre ayarlanır")
    
    monthly_effect_custom = st.slider(
        "Ay Hedefi Etkisi (%)",
        min_value=0,
        max_value=150,
        value=int(monthly_effect * 100),
        step=10,
        help="Ay bazında hedeflerin etkisi"
    ) / 100
    
    maingroup_effect_custom = st.slider(
        "Ana Grup Etkisi (%)",
        min_value=0,
        max_value=150,
        value=int(maingroup_effect * 100),
        step=10,
        help="Ana grup hedeflerinin etkisi"
    ) / 100
    
    organic_growth_custom = st.slider(
        "Organik Büyüme Etkisi (%)",
        min_value=0,
        max_value=50,
        value=int(organic_growth_rate * 100),
        step=5,
        help="Geçmiş trendin etkisi"
    ) / 100
    
    # Özel ayar kullanılıyor mu?
    use_custom = st.checkbox("Özel Ayarları Kullan", value=False)
    
    if use_custom:
        monthly_effect = monthly_effect_custom
        maingroup_effect = maingroup_effect_custom
        organic_growth_rate = organic_growth_custom
        st.info("✅ Özel ayarlar aktif")
    else:
        st.info(f"Varsayılan: Ay={int(monthly_effect*100)}%, Grup={int(maingroup_effect*100)}%, Organik={int(organic_growth_rate*100)}%")

# PARAMETRE KAYDET/YÜKLE BUTONLARI
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Parametre Yönetimi")

col_save, col_load = st.sidebar.columns(2)

with col_save:
    if st.button("💾 Kaydet", use_container_width=True):
        if save_parameters_to_file():
            st.sidebar.success("✅ Kaydedildi")

with col_load:
    if st.button("📂 Yükle", use_container_width=True):
        if load_parameters_from_file():
            st.sidebar.success("✅ Yüklendi")
            st.rerun()

# EXCEL TEMPLATE İNDİR/YÜKLE
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Excel İle Parametre Yönetimi")

# Template indir
template_excel = create_parameter_template()
st.sidebar.download_button(
    label="📥 Şablon İndir",
    data=template_excel,
    file_name="parametre_sablonu.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

# Excel yükle
param_upload = st.sidebar.file_uploader(
    "📤 Parametre Yükle (Excel)",
    type=['xlsx'],
    key='param_upload'
)

if param_upload:
    success, message = load_parameters_from_excel(param_upload)
    if success:
        st.sidebar.success(message)
        # Rerun KALDIRILDI - bulanıklaşma sorunu çözüldü
    else:
        st.sidebar.error(message)


# Session state - GÜNCEL ANA GRUPLARI KULLAN
if 'monthly_targets' not in st.session_state:
    st.session_state.monthly_targets = pd.DataFrame({
        'Ay': list(range(1, 13)),
        'Ay Adı': ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
                   'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'],
        'Hedef (%)': ['20.0'] * 12
    })

st.session_state.maingroup_targets = pd.DataFrame({
    'Ana Grup': main_groups,
    'Hedef (%)': ['20.0'] * len(main_groups)
})

lessons_data = {'Ana Grup': main_groups}
for month in range(1, 13):
    lessons_data[str(month)] = ['0'] * len(main_groups)
st.session_state.lessons_learned = pd.DataFrame(lessons_data)

price_data = {'Ana Grup': main_groups}
for month in range(1, 13):
    price_data[str(month)] = [str(inflation_future)] * len(main_groups)
st.session_state.price_changes = pd.DataFrame(price_data)

if 'forecast_result' not in st.session_state:
    st.session_state.forecast_result = None

# ANA SEKMELER
main_tabs = st.tabs(["⚙️ Parametre Ayarları", "📊 Tahmin Sonuçları", "📋 Detay Veriler"])

# ==================== PARAMETRE AYARLARI ====================
with main_tabs[0]:
    st.markdown("## ⚙️ Tahmin Parametrelerini Ayarlayın")
    
    st.markdown("""
    <div class="info-box">
    ⭐ <b>Önemli:</b> Parametreler otomatik kaydedilir<br>
    🔸 <b>Sıfırlama:</b> Bir satırı sıfırlamak için <code>*</code> yazın<br>
    🔸 <b>0 girişi:</b> Geçen yılla aynı kalması anlamına gelir (büyüme yok)<br>
    🔸 <b>Excel:</b> Toplu güncelleme için Excel şablonunu kullanabilirsiniz<br>
    🔸 <b>Etki Oranları:</b> Bütçe versiyonuna göre otomatik ayarlanır
    </div>
    """, unsafe_allow_html=True)
    
    # Mevcut etki oranlarını göster
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("Ay Hedefi Etkisi", f"%{int(monthly_effect*100)}")
    with col_info2:
        st.metric("Ana Grup Etkisi", f"%{int(maingroup_effect*100)}")
    with col_info3:
        st.metric("Organik Büyüme", f"%{int(organic_growth_rate*100)}")
    
    st.markdown("---")
    
    param_tabs = st.tabs(["📅 Ay Bazında", "🏪 Ana Grup", "📚 Alınan Dersler", "💵 Fiyat Değişimi"])
    
    # --- AY BAZINDA HEDEFLER ---
    with param_tabs[0]:
        st.markdown("### 📅 Ay Bazında Büyüme Hedefleri")
        st.caption("💡 Bir ayı sıfırlamak için `*` yazın, 0 = geçen yılla aynı (büyüme yok)")
        
        edited_monthly = st.data_editor(
            st.session_state.monthly_targets,
            use_container_width=True,
            hide_index=True,
            height=500,
            column_config={
                'Ay': st.column_config.NumberColumn('Ay', disabled=True, width='small'),
                'Ay Adı': st.column_config.TextColumn('Ay Adı', disabled=True, width='small'),
                'Hedef (%)': st.column_config.TextColumn(
                    'Hedef (% veya *)',
                    width='medium'
                )
            },
            key='monthly_editor'
        )
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("📊 Ortalama", "Hesapla sonrası")
        col_b.metric("📉 Minimum", "Hesapla sonrası")
        col_c.metric("📈 Maximum", "Hesapla sonrası")
    
    # --- ANA GRUP HEDEFLER ---
    with param_tabs[1]:
        st.markdown("### 🏪 Ana Grup Bazında Büyüme Hedefleri")
        st.caption("💡 Bir grubu sıfırlamak için `*` yazın, 0 = geçen yılla aynı")
        
        num_groups = len(st.session_state.maingroup_targets)
        table_height = min(num_groups * 35 + 50, 800)
        
        edited_maingroup = st.data_editor(
            st.session_state.maingroup_targets,
            use_container_width=True,
            hide_index=True,
            height=table_height,
            column_config={
                'Ana Grup': st.column_config.TextColumn('Ana Grup', disabled=True, width='large'),
                'Hedef (%)': st.column_config.TextColumn(
                    'Hedef (% veya *)',
                    width='medium'
                )
            },
            key='maingroup_editor'
        )
    
    # --- ALINAN DERSLER ---
    with param_tabs[2]:
        st.markdown("### 📚 Alınan Dersler")
        st.caption("💡 `-10` ile `+10` arası puan verin veya `*` ile sıfırlayın")
        
        month_names = {1: 'O', 2: 'Ş', 3: 'M', 4: 'N', 5: 'M', 6: 'H', 
                       7: 'T', 8: 'A', 9: 'E', 10: 'E', 11: 'K', 12: 'A'}
        
        month_full_names = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan',
                           5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos',
                           9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}
        
        column_config = {
            'Ana Grup': st.column_config.TextColumn('Grup', disabled=True, width='small')
        }
        
        for month in range(1, 13):
            column_config[str(month)] = st.column_config.TextColumn(
                month_names[month],
                help=month_full_names[month],
                width='small'
            )
        
        num_lessons = len(st.session_state.lessons_learned)
        lessons_height = min(num_lessons * 35 + 50, 800)
        
        edited_lessons = st.data_editor(
            st.session_state.lessons_learned,
            use_container_width=True,
            hide_index=True,
            height=lessons_height,
            column_config=column_config,
            key='lessons_editor'
        )
    
    # --- FİYAT DEĞİŞİMİ ---
    with param_tabs[3]:
        st.markdown("### 💵 Birim Fiyat Değişimi (% olarak)")
        st.caption(f"Default: %{inflation_future:.0f} (Enflasyon)")
        
        column_config = {
            'Ana Grup': st.column_config.TextColumn('Grup', disabled=True, width='small')
        }
        
        for month in range(1, 13):
            column_config[str(month)] = st.column_config.TextColumn(
                month_names[month],
                help=f"{month_full_names[month]} - Fiyat artış %",
                width='small'
            )
        
        num_price_rows = len(st.session_state.price_changes)
        price_height = min(num_price_rows * 35 + 50, 800)
        
        edited_prices = st.data_editor(
            st.session_state.price_changes,
            use_container_width=True,
            hide_index=True,
            height=price_height,
            column_config=column_config,
            key='price_editor'
        )
    
    # HESAPLA BUTONU
    st.markdown("---")
    st.markdown("### 🚀 Tahmini Hesapla")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("📊 Hesapla ve Sonuçları Göster", type='primary', use_container_width=True):
            with st.spinner('Tahmin hesaplanıyor...'):
                # Session state güncelle
                st.session_state.monthly_targets = edited_monthly
                st.session_state.maingroup_targets = edited_maingroup
                st.session_state.lessons_learned = edited_lessons
                st.session_state.price_changes = edited_prices
                
                # Otomatik kaydet
                save_parameters_to_file()
                
                # *** SIFIRLAMA: Sadece * kontrolü ***
                zero_months = set()
                zero_maingroups = set()
                zero_lessons = set()
                
                # Ay hedefleri - ETKİ ORANI UYGULA
                monthly_growth_targets = {}
                for _, row in edited_monthly.iterrows():
                    month = int(row['Ay'])
                    value = str(row['Hedef (%)']).strip()
                    
                    if value == '*':
                        zero_months.add(month)
                        monthly_growth_targets[month] = -999
                    else:
                        try:
                            # Etki oranı uygula
                            monthly_growth_targets[month] = float(value) / 100 * monthly_effect
                        except:
                            monthly_growth_targets[month] = 0.20 * monthly_effect
                
                # Ana grup - ETKİ ORANI UYGULA
                maingroup_growth_targets = {}
                for _, row in edited_maingroup.iterrows():
                    maingroup = row['Ana Grup']
                    value = str(row['Hedef (%)']).strip()
                    
                    if value == '*':
                        zero_maingroups.add(maingroup)
                        maingroup_growth_targets[maingroup] = -999
                    else:
                        try:
                            # Etki oranı uygula
                            maingroup_growth_targets[maingroup] = float(value) / 100 * maingroup_effect
                        except:
                            maingroup_growth_targets[maingroup] = 0.20 * maingroup_effect
                
                # Alınan dersler
                lessons_learned_dict = {}
                for _, row in edited_lessons.iterrows():
                    main_group = row['Ana Grup']
                    for month in range(1, 13):
                        value = str(row[str(month)]).strip()
                        
                        if value == '*':
                            zero_lessons.add((main_group, month))
                            lessons_learned_dict[(main_group, month)] = -999
                        else:
                            try:
                                lessons_learned_dict[(main_group, month)] = float(value)
                            except:
                                lessons_learned_dict[(main_group, month)] = 0
                
                # Fiyat değişimi
                price_change_dict = {}
                for _, row in edited_prices.iterrows():
                    main_group = row['Ana Grup']
                    for month in range(1, 13):
                        try:
                            price_change_dict[(main_group, month)] = float(row[str(month)]) / 100
                        except:
                            price_change_dict[(main_group, month)] = inflation_future / 100
                
                # Genel büyüme
                general_growth = 0.10  # %10
                
                # Tahmin
                full_data = forecaster.get_full_data_with_forecast(
                    growth_param=general_growth,
                    margin_improvement=margin_improvement,
                    stock_change_pct=stock_change_pct,
                    monthly_growth_targets=monthly_growth_targets,
                    maingroup_growth_targets=maingroup_growth_targets,
                    lessons_learned=lessons_learned_dict,
                    inflation_adjustment=inflation_adjustment,
                    organic_multiplier=organic_multiplier,
                    price_change_matrix=price_change_dict,
                    inflation_rate=inflation_future / 100,
                    organic_growth_rate=organic_growth_rate
                )
                
                # *** SIFIRLAMA UYGULA ***
                for month in zero_months:
                    full_data.loc[(full_data['Year'] == 2026) & (full_data['Month'] == month),
                                 ['Quantity', 'Sales', 'GrossProfit', 'Stock', 'COGS']] = 0
                
                for maingroup in zero_maingroups:
                    full_data.loc[(full_data['Year'] == 2026) & (full_data['MainGroup'] == maingroup),
                                 ['Quantity', 'Sales', 'GrossProfit', 'Stock', 'COGS']] = 0
                
                for (maingroup, month) in zero_lessons:
                    full_data.loc[(full_data['Year'] == 2026) & 
                                 (full_data['MainGroup'] == maingroup) & 
                                 (full_data['Month'] == month),
                                 ['Quantity', 'Sales', 'GrossProfit', 'Stock', 'COGS']] = 0
                
                summary = forecaster.get_summary_stats(full_data)
                quality_metrics = forecaster.get_forecast_quality_metrics(full_data)
                
                st.session_state.forecast_result = {
                    'full_data': full_data,
                    'summary': summary,
                    'quality_metrics': quality_metrics
                }
                
                st.success("✅ Tahmin başarıyla hesaplandı! Parametreler kaydedildi. 'Tahmin Sonuçları' sekmesine geçin.")

# ==================== TAHMİN SONUÇLARI ====================
with main_tabs[1]:
    if st.session_state.forecast_result is None:
        st.warning("⚠️ Henüz tahmin hesaplanmadı. Lütfen 'Parametre Ayarları' sekmesinden parametreleri girin ve 'Hesapla' butonuna basın.")
    else:
        full_data = st.session_state.forecast_result['full_data']
        summary = st.session_state.forecast_result['summary']
        quality_metrics = st.session_state.forecast_result['quality_metrics']
        
        st.markdown("## 📈 Özet Metrikler")
        
        # Ana metrikler
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            sales_2026 = summary[2026]['Total_Sales']
            sales_2025 = summary[2025]['Total_Sales']
            sales_growth = ((sales_2026 - sales_2025) / sales_2025 * 100) if sales_2025 > 0 else 0
            st.metric("2026 Toplam Satış", format_currency(sales_2026), f"%{sales_growth:.1f}")
            
        with col2:
            margin_2026 = summary[2026]['Avg_GrossMargin%']
            margin_2025 = summary[2025]['Avg_GrossMargin%']
            margin_diff = margin_2026 - margin_2025
            st.metric("2026 Brüt Marj", f"%{margin_2026:.1f}", f"{margin_diff:+.1f} puan")
        
        with col3:
            gp_2026 = summary[2026]['Total_GrossProfit']
            gp_2025 = summary[2025]['Total_GrossProfit']
            gp_growth = ((gp_2026 - gp_2025) / gp_2025 * 100) if gp_2025 > 0 else 0
            st.metric("2026 Brüt Kar", format_currency(gp_2026), f"%{gp_growth:.1f}")
            
        with col4:
            stock_2026 = summary[2026]['Avg_Stock_COGS_Weekly']
            stock_2025 = summary[2025]['Avg_Stock_COGS_Weekly']
            stock_diff = stock_2026 - stock_2025
            st.metric("2026 Stok/SMM", f"{stock_2026:.1f} hafta", f"{stock_diff:+.1f} hft")
        
        st.markdown("---")
        
        # Yıllık karşılaştırma tablosu
        st.markdown("### 📊 Yıllık Karşılaştırma")
        
        comparison_data = []
        for year in [2024, 2025, 2026]:
            comparison_data.append({
                'Yıl': year,
                'Satış': format_currency(summary[year]['Total_Sales']),
                'Brüt Kar': format_currency(summary[year]['Total_GrossProfit']),
                'Brüt Marj %': f"{summary[year]['Avg_GrossMargin%']:.1f}%",
                'Ort. Stok': format_currency(summary[year]['Avg_Stock']),
                'Stok/SMM (hafta)': f"{summary[year]['Avg_Stock_COGS_Weekly']:.1f}"
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Alt sekmeler
        result_tabs = st.tabs(["📊 Aylık Trend", "🎯 Ana Grup Performans", "📅 Yıllık Detay", "📈 Kalite Metrikleri"])
        
        # AYLIK TREND
        with result_tabs[0]:
            st.subheader("📊 Aylık Satış Trendi")
            
            monthly_sales = full_data.groupby(['Year', 'Month'])['Sales'].sum().reset_index()
            
            fig = go.Figure()
            
            colors = {'2024': '#1f77b4', '2025': '#ff7f0e', '2026': '#2ca02c'}
            
            for year in [2024, 2025, 2026]:
                year_data = monthly_sales[monthly_sales['Year'] == year]
                fig.add_trace(go.Scatter(
                    x=year_data['Month'],
                    y=year_data['Sales'],
                    mode='lines+markers',
                    name=str(year),
                    line=dict(width=3, dash='solid' if year < 2026 else 'dash', color=colors[str(year)]),
                    marker=dict(size=8)
                ))
            
            fig.update_layout(
                title="Aylık Satış Trendi (2024-2026)",
                xaxis_title="Ay",
                yaxis_title="Satış (₺)",
                hovermode='x unified',
                height=500,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Aylık detay tablo
            st.markdown("#### Aylık Detay")
            pivot_monthly = monthly_sales.pivot(index='Month', columns='Year', values='Sales')
            pivot_monthly['2025 Büyüme %'] = ((pivot_monthly[2025] - pivot_monthly[2024]) / pivot_monthly[2024] * 100).round(1)
            pivot_monthly['2026 Büyüme %'] = ((pivot_monthly[2026] - pivot_monthly[2025]) / pivot_monthly[2025] * 100).round(1)
            
            for year in [2024, 2025, 2026]:
                pivot_monthly[year] = pivot_monthly[year].apply(lambda x: format_currency(x))
            
            st.dataframe(pivot_monthly, use_container_width=True)
        
        # ANA GRUP PERFORMANS
        with result_tabs[1]:
            st.subheader("🎯 Ana Grup Performans Karşılaştırması")
            
            group_sales = full_data.groupby(['Year', 'MainGroup'])['Sales'].sum().reset_index()
            
            # En iyi 10 grubu al (2026 bazında)
            top_groups_2026 = group_sales[group_sales['Year'] == 2026].nlargest(10, 'Sales')['MainGroup']
            filtered_groups = group_sales[group_sales['MainGroup'].isin(top_groups_2026)]
            
            fig = px.bar(
                filtered_groups,
                x='MainGroup',
                y='Sales',
                color='Year',
                barmode='group',
                title=f"Top 10 Ana Grup - Yıllık Karşılaştırma",
                color_discrete_map={'2024': '#1f77b4', '2025': '#ff7f0e', '2026': '#2ca02c'}
            )
            
            fig.update_layout(height=500, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            
            # Büyüme oranları tablosu
            st.markdown("#### Ana Grup Büyüme Oranları")
            
            pivot_groups = group_sales.pivot(index='MainGroup', columns='Year', values='Sales')
            pivot_groups['2025 Büyüme %'] = ((pivot_groups[2025] - pivot_groups[2024]) / pivot_groups[2024] * 100).round(1)
            pivot_groups['2026 Büyüme %'] = ((pivot_groups[2026] - pivot_groups[2025]) / pivot_groups[2025] * 100).round(1)
            pivot_groups = pivot_groups.sort_values('2026 Büyüme %', ascending=False)
            
            for year in [2024, 2025, 2026]:
                pivot_groups[year] = pivot_groups[year].apply(lambda x: format_currency(x))
            
            st.dataframe(pivot_groups, use_container_width=True, height=600)
        
        # YILLIK DETAY
        with result_tabs[2]:
            st.subheader("📅 Yıllık Detaylı Analiz")
            
            # Yıllık satış grafiği
            yearly_sales = full_data.groupby('Year')['Sales'].sum()
            
            fig = go.Figure(data=[
                go.Bar(x=yearly_sales.index, y=yearly_sales.values, 
                       marker_color=['#1f77b4', '#ff7f0e', '#2ca02c'],
                       text=[format_currency(x) for x in yearly_sales.values],
                       textposition='auto')
            ])
            
            fig.update_layout(
                title="Yıllık Toplam Satış",
                xaxis_title="Yıl",
                yaxis_title="Satış (₺)",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Detaylı yıllık metrikler
            st.markdown("#### Detaylı Yıllık Metrikler")
            
            yearly_metrics = []
            for year in [2024, 2025, 2026]:
                yearly_metrics.append({
                    'Yıl': year,
                    'Toplam Satış': format_currency(summary[year]['Total_Sales']),
                    'Toplam Brüt Kar': format_currency(summary[year]['Total_GrossProfit']),
                    'Brüt Marj %': f"{summary[year]['Avg_GrossMargin%']:.2f}%",
                    'Ortalama Stok': format_currency(summary[year]['Avg_Stock']),
                    'Stok/COGS Oranı': f"{summary[year]['Avg_Stock_COGS_Ratio']:.3f}",
                    'Stok/SMM (hafta)': f"{summary[year]['Avg_Stock_COGS_Weekly']:.1f}"
                })
            
            yearly_metrics_df = pd.DataFrame(yearly_metrics)
            st.dataframe(yearly_metrics_df, use_container_width=True, hide_index=True)
        
        # KALİTE METRİKLERİ
        with result_tabs[3]:
            st.subheader("📈 Tahmin Kalite Metrikleri")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if quality_metrics['r2_score'] is not None:
                    st.metric("R² Score", f"{quality_metrics['r2_score']:.3f}", 
                             help="Model uyum kalitesi (0-1 arası, 1 en iyi)")
                else:
                    st.metric("R² Score", "N/A")
            
            with col2:
                if quality_metrics['trend_consistency'] is not None:
                    st.metric("Trend Tutarlılığı", f"{quality_metrics['trend_consistency']:.2f}",
                             help="Büyüme oranlarının tutarlılığı (0-1 arası)")
                else:
                    st.metric("Trend Tutarlılığı", "N/A")
            
            with col3:
                if quality_metrics['avg_growth_2024_2025'] is not None:
                    st.metric("Ort. Büyüme 2024→2025", f"%{quality_metrics['avg_growth_2024_2025']:.1f}",
                             help="2024'ten 2025'e ortalama büyüme oranı")
                else:
                    st.metric("Ort. Büyüme", "N/A")
            
            st.markdown("---")
            
            st.markdown("#### Güven Seviyesi")
            
            confidence = quality_metrics.get('confidence_level', 'Bilinmiyor')
            
            if confidence == 'Yüksek':
                st.success(f"✅ **{confidence}** - Tahmin güvenilirliği yüksek")
            elif confidence == 'Orta':
                st.info(f"ℹ️ **{confidence}** - Tahmin güvenilirliği orta seviye")
            else:
                st.warning(f"⚠️ **{confidence}** - Tahmin güvenilirliği düşük, daha fazla veri gerekebilir")
            
            st.markdown("""
            **Kalite Metrikleri Açıklaması:**
            - **R² Score:** Model ne kadar iyi uyum sağlıyor (1'e yakın = çok iyi)
            - **Trend Tutarlılığı:** Büyüme oranları ne kadar tutarlı (1'e yakın = çok tutarlı)
            - **Güven Seviyesi:** Genel tahmin güvenilirliği
            """)

# ==================== DETAY VERİLER ====================
with main_tabs[2]:
    if st.session_state.forecast_result is None:
        st.warning("⚠️ Önce tahmini hesaplayın.")
    else:
        full_data = st.session_state.forecast_result['full_data']
        
        st.markdown("## 📋 Detaylı Veri İnceleme ve Export")
        
        # Filtreleme seçenekleri
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selected_year = st.selectbox("Yıl Seçin", [2024, 2025, 2026], index=2)
        
        with col2:
            selected_month = st.selectbox("Ay Seçin", list(range(1, 13)))
        
        with col3:
            selected_maingroup = st.selectbox("Ana Grup Seçin (Opsiyonel)", 
                                             ['Tümü'] + sorted(full_data['MainGroup'].unique().tolist()))
        
        # Veriyi filtrele
        filtered_data = full_data[
            (full_data['Year'] == selected_year) & 
            (full_data['Month'] == selected_month)
        ]
        
        if selected_maingroup != 'Tümü':
            filtered_data = filtered_data[filtered_data['MainGroup'] == selected_maingroup]
        
        # Özet metrikler
        st.markdown("### 📊 Seçili Dönem Özeti")
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        with col_m1:
            total_sales = filtered_data['Sales'].sum()
            st.metric("Toplam Satış", format_currency(total_sales))
        
        with col_m2:
            total_gp = filtered_data['GrossProfit'].sum()
            st.metric("Toplam Brüt Kar", format_currency(total_gp))
        
        with col_m3:
            avg_margin = (total_gp / total_sales * 100) if total_sales > 0 else 0
            st.metric("Brüt Marj", f"%{avg_margin:.1f}")
        
        with col_m4:
            total_quantity = filtered_data['Quantity'].sum()
            st.metric("Toplam Adet", format_number(total_quantity, 0))
        
        st.markdown("---")
        
        # Detaylı tablo
        st.markdown("### 📋 Detaylı Veri Tablosu")
        
        # Formatlı veri
        display_data = filtered_data.copy()
        display_data['Sales'] = display_data['Sales'].apply(lambda x: format_currency(x))
        display_data['GrossProfit'] = display_data['GrossProfit'].apply(lambda x: format_currency(x))
        display_data['COGS'] = display_data['COGS'].apply(lambda x: format_currency(x))
        display_data['Stock'] = display_data['Stock'].apply(lambda x: format_currency(x))
        display_data['Quantity'] = display_data['Quantity'].apply(lambda x: format_number(x, 0))
        display_data['UnitPrice'] = display_data['UnitPrice'].apply(lambda x: format_currency(x))
        display_data['GrossMargin%'] = display_data['GrossMargin%'].apply(lambda x: f"%{x*100:.1f}")
        display_data['Stock_COGS_Ratio'] = display_data['Stock_COGS_Ratio'].apply(lambda x: f"{x:.3f}")
        
        st.dataframe(display_data, use_container_width=True, height=600)
        
        # Export seçenekleri
        st.markdown("---")
        st.markdown("### 💾 Export Seçenekleri")
        
        col_exp1, col_exp2, col_exp3 = st.columns(3)
        
        # CSV Export (seçili veri)
        with col_exp1:
            csv_filtered = filtered_data.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Seçili Veriyi İndir (CSV)",
                data=csv_filtered,
                file_name=f"budget_{selected_year}_{selected_month:02d}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        # CSV Export (tüm veri)
        with col_exp2:
            csv_all = full_data.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Tüm Veriyi İndir (CSV)",
                data=csv_all,
                file_name="budget_full_data.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        # Excel Export
        with col_exp3:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Her yıl için ayrı sheet
                for year in [2024, 2025, 2026]:
                    year_data = full_data[full_data['Year'] == year]
                    year_data.to_excel(writer, sheet_name=str(year), index=False)
                
                # Özet sheet
                summary_data = []
                for year in [2024, 2025, 2026]:
                    for month in range(1, 13):
                        month_data = full_data[(full_data['Year'] == year) & (full_data['Month'] == month)]
                        summary_data.append({
                            'Yıl': year,
                            'Ay': month,
                            'Satış': month_data['Sales'].sum(),
                            'Brüt Kar': month_data['GrossProfit'].sum(),
                            'Adet': month_data['Quantity'].sum()
                        })
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Özet', index=False)
            
            output.seek(0)
            
            st.download_button(
                label="📥 Excel Rapor İndir",
                data=output,
                file_name="budget_detay_rapor.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        # ==================== YENİ RAPOR: AY BAZINDA PERFORMANS ====================
        st.markdown("---")
        st.markdown("## 📊 Ay Bazında Performans Raporu")
        st.caption("Her ayın yıl toplamına oranları ve performans metrikleri (2024-2025-2026 karşılaştırmalı)")
        
        # Ay günleri / 7 = hafta
        days_in_month = {
            1: 31/7, 2: 28/7, 3: 31/7, 4: 30/7, 5: 31/7, 6: 30/7,
            7: 31/7, 8: 31/7, 9: 30/7, 10: 31/7, 11: 30/7, 12: 31/7
        }
        
        # Rapor hesaplama
        monthly_performance = []
        
        for month in range(1, 13):
            month_name = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
                         'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'][month-1]
            
            row_data = {
                'Ay': month,
                'Ay Adı': month_name
            }
            
            for year in [2024, 2025, 2026]:
                year_data = full_data[full_data['Year'] == year]
                month_data = year_data[year_data['Month'] == month]
                
                # Yıllık toplamlar
                yearly_sales = year_data['Sales'].sum()
                yearly_quantity = year_data['Quantity'].sum()
                yearly_gp = year_data['GrossProfit'].sum()
                
                if len(month_data) > 0:
                    # Aylık toplamlar
                    monthly_sales = month_data['Sales'].sum()
                    monthly_quantity = month_data['Quantity'].sum()
                    monthly_gp = month_data['GrossProfit'].sum()
                    monthly_cogs = month_data['COGS'].sum()
                    monthly_stock = month_data['Stock'].mean()
                    
                    # Yüzdeler
                    sales_pct = (monthly_sales / yearly_sales * 100) if yearly_sales > 0 else 0
                    quantity_pct = (monthly_quantity / yearly_quantity * 100) if yearly_quantity > 0 else 0
                    gp_pct = (monthly_gp / yearly_gp * 100) if yearly_gp > 0 else 0
                    
                    # Brüt Marj %
                    bm_pct = (monthly_gp / monthly_sales * 100) if monthly_sales > 0 else 0
                    
                    # Stok Hafta = (Stok / Aylık SMM) * Ay'ın hafta sayısı
                    weeks_in_month = days_in_month[month]
                    stock_weeks = (monthly_stock / monthly_cogs * weeks_in_month) if monthly_cogs > 0 else 0
                    
                    # Yıl bazında kolonlar
                    row_data[f'{year} Ciro'] = monthly_sales
                    row_data[f'{year} Ciro %'] = sales_pct
                    row_data[f'{year} Adet'] = monthly_quantity
                    row_data[f'{year} Adet %'] = quantity_pct
                    row_data[f'{year} Kar'] = monthly_gp
                    row_data[f'{year} Kar %'] = gp_pct
                    row_data[f'{year} BM %'] = bm_pct
                    row_data[f'{year} Stok Hft'] = stock_weeks
                else:
                    # Veri yoksa 0
                    row_data[f'{year} Ciro'] = 0
                    row_data[f'{year} Ciro %'] = 0
                    row_data[f'{year} Adet'] = 0
                    row_data[f'{year} Adet %'] = 0
                    row_data[f'{year} Kar'] = 0
                    row_data[f'{year} Kar %'] = 0
                    row_data[f'{year} BM %'] = 0
                    row_data[f'{year} Stok Hft'] = 0
            
            monthly_performance.append(row_data)
        
        performance_df = pd.DataFrame(monthly_performance)
        
        # Formatlama
        display_report = performance_df.copy()
        
        for year in [2024, 2025, 2026]:
            display_report[f'{year} Ciro'] = display_report[f'{year} Ciro'].apply(lambda x: format_currency(x))
            display_report[f'{year} Ciro %'] = display_report[f'{year} Ciro %'].apply(lambda x: f"%{x:.1f}")
            display_report[f'{year} Adet'] = display_report[f'{year} Adet'].apply(lambda x: format_number(x, 0))
            display_report[f'{year} Adet %'] = display_report[f'{year} Adet %'].apply(lambda x: f"%{x:.1f}")
            display_report[f'{year} Kar'] = display_report[f'{year} Kar'].apply(lambda x: format_currency(x))
            display_report[f'{year} Kar %'] = display_report[f'{year} Kar %'].apply(lambda x: f"%{x:.1f}")
            display_report[f'{year} BM %'] = display_report[f'{year} BM %'].apply(lambda x: f"%{x:.1f}")
            display_report[f'{year} Stok Hft'] = display_report[f'{year} Stok Hft'].apply(lambda x: f"{x:.1f}")
        
        # Tabloyu göster - GENİŞ TABLO
        st.dataframe(
            display_report,
            use_container_width=True,
            hide_index=True,
            height=500
        )
        
        # Export rapor
        st.markdown("#### 💾 Performans Raporunu İndir")
        
        col_r1, col_r2 = st.columns(2)
        
        with col_r1:
            # CSV
            report_csv = performance_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Performans Raporu (CSV)",
                data=report_csv,
                file_name="ay_bazinda_performans_2024_2026.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_r2:
            # Excel
            report_output = BytesIO()
            with pd.ExcelWriter(report_output, engine='openpyxl') as writer:
                performance_df.to_excel(writer, sheet_name='Ay Bazında Performans', index=False)
            
            report_output.seek(0)
            
            st.download_button(
                label="📥 Performans Raporu (Excel)",
                data=report_output,
                file_name="ay_bazinda_performans_raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
<p><b>2026 Satış Bütçe Tahmin Sistemi v3.1</b></p>
<p>Parametrik Etki Oranları | Gelişmiş Analiz | Otomatik Kayıt</p>
</div>
""", unsafe_allow_html=True)
