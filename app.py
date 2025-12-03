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
        
        # Sheet 2: Ana Grup Hedefleri (placeholder)
        maingroup_template = pd.DataFrame({
            'Ana Grup': ['Örnek Grup 1', 'Örnek Grup 2'],
            'Hedef (%)': [20.0, 20.0]
        })
        maingroup_template.to_excel(writer, sheet_name='Ana Grup Hedefleri', index=False)
        
        # Sheet 3: Açıklama
        instructions = pd.DataFrame({
            'Talimatlar': [
                '1. "Ay Hedefleri" sekmesini doldurun',
                '2. "Ana Grup Hedefleri" sekmesindeki örnek grupları silin',
                '3. Kendi ana gruplarınızı ekleyin',
                '4. Hedefleri % olarak girin (örn: 20 = %20 büyüme)',
                '5. Sıfırlamak için * yazın',
                '6. Dosyayı kaydedin ve uygulamaya yükleyin'
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
        1. Sol taraftaki **"📂 Veri Yükleme"** bölümünden Excel dosyanızı yükleyin
        2. **"Parametre Ayarları"** sekmesinden hedeflerinizi belirleyin
        3. **"📊 Hesapla"** butonuna basın
        4. Parametreler otomatik kaydedilir
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
st.sidebar.subheader("📉 Enflasyon")

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

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Bütçe Versiyonu")

budget_version = st.sidebar.select_slider(
    "Senaryo",
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
        st.rerun()
    else:
        st.sidebar.error(message)


# Session state
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

# PARAMETRE AYARLARI
with main_tabs[0]:
    st.markdown("## ⚙️ Tahmin Parametrelerini Ayarlayın")
    
    st.markdown("""
    <div class="info-box">
    ⭐ <b>Önemli:</b> Parametreler otomatik kaydedilir<br>
    🔸 <b>Sıfırlama:</b> Bir satırı sıfırlamak için <code>*</code> yazın<br>
    🔸 <b>0 girişi:</b> Geçen yılla aynı kalması anlamına gelir (büyüme yok)<br>
    🔸 <b>Excel:</b> Toplu güncelleme için Excel şablonunu kullanabilirsiniz
    </div>
    """, unsafe_allow_html=True)
    
    param_tabs = st.tabs(["📅 Ay Bazında", "🏪 Ana Grup", "📚 Alınan Dersler", "💵 Fiyat"])
    
    # AY BAZINDA
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
                'Hedef (%)': st.column_config.TextColumn('Hedef (% veya *)', width='medium')
            },
            key='monthly_editor'
        )
    
    # ANA GRUP
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
                'Hedef (%)': st.column_config.TextColumn('Hedef (% veya *)', width='medium')
            },
            key='maingroup_editor'
        )
    
    # ALINAN DERSLER
    with param_tabs[2]:
        st.markdown("### 📚 Alınan Dersler")
        st.caption("💡 `-10` ile `+10` arası puan veya `*` ile sıfırla")
        
        month_names = {1: 'O', 2: 'Ş', 3: 'M', 4: 'N', 5: 'M', 6: 'H',
                       7: 'T', 8: 'A', 9: 'E', 10: 'E', 11: 'K', 12: 'A'}
        
        column_config = {'Ana Grup': st.column_config.TextColumn('Grup', disabled=True, width='small')}
        
        for month in range(1, 13):
            column_config[str(month)] = st.column_config.TextColumn(
                month_names[month], width='small'
            )
        
        edited_lessons = st.data_editor(
            st.session_state.lessons_learned,
            use_container_width=True,
            hide_index=True,
            height=min(len(main_groups) * 35 + 50, 800),
            column_config=column_config,
            key='lessons_editor'
        )
    
    # FİYAT
    with param_tabs[3]:
        st.markdown("### 💵 Birim Fiyat Değişimi")
        st.caption(f"Default: %{inflation_future:.0f}")
        
        column_config = {'Ana Grup': st.column_config.TextColumn('Grup', disabled=True, width='small')}
        
        for month in range(1, 13):
            column_config[str(month)] = st.column_config.TextColumn(month_names[month], width='small')
        
        edited_prices = st.data_editor(
            st.session_state.price_changes,
            use_container_width=True,
            hide_index=True,
            height=min(len(main_groups) * 35 + 50, 800),
            column_config=column_config,
            key='price_editor'
        )
    
    # HESAPLA
    st.markdown("---")
    st.markdown("### 🚀 Tahmini Hesapla")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("📊 Hesapla ve Sonuçları Göster", type='primary', use_container_width=True):
            with st.spinner('Tahmin hesaplanıyor...'):
                # Parametreleri kaydet
                st.session_state.monthly_targets = edited_monthly
                st.session_state.maingroup_targets = edited_maingroup
                st.session_state.lessons_learned = edited_lessons
                st.session_state.price_changes = edited_prices
                
                # Otomatik kaydet
                save_parameters_to_file()
                
                # Sıfırlama
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
                            # Etki oranı uygula (örn: %100 = tam etki, %50 = yarı etki)
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
                
                # Lessons
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
                
                # Fiyat
                price_change_dict = {}
                for _, row in edited_prices.iterrows():
                    main_group = row['Ana Grup']
                    for month in range(1, 13):
                        try:
                            price_change_dict[(main_group, month)] = float(row[str(month)]) / 100
                        except:
                            price_change_dict[(main_group, month)] = inflation_future / 100
                
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
                
                # Sıfırlama
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
                
                st.success("✅ Tahmin hesaplandı! Parametreler kaydedildi.")

# TAHMİN SONUÇLARI
with main_tabs[1]:
    if st.session_state.forecast_result is None:
        st.warning("⚠️ Henüz tahmin hesaplanmadı.")
    else:
        full_data = st.session_state.forecast_result['full_data']
        summary = st.session_state.forecast_result['summary']
        
        st.markdown("## 📈 Özet Metrikler")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            sales_2026 = summary[2026]['Total_Sales']
            sales_2025 = summary[2025]['Total_Sales']
            sales_growth = ((sales_2026 - sales_2025) / sales_2025 * 100) if sales_2025 > 0 else 0
            st.metric("2026 Satış", format_currency(sales_2026), f"%{sales_growth:.1f}")
        
        with col2:
            margin_2026 = summary[2026]['Avg_GrossMargin%']
            st.metric("2026 Marj", f"%{margin_2026:.1f}")
        
        with col3:
            gp_2026 = summary[2026]['Total_GrossProfit']
            st.metric("2026 Kar", format_currency(gp_2026))
        
        with col4:
            stock_2026 = summary[2026]['Avg_Stock_COGS_Weekly']
            st.metric("Stok", f"{stock_2026:.1f} hft")
        
        st.markdown("---")
        
        # Grafikler (basitleştirilmiş)
        st.subheader("📊 Aylık Trend")
        monthly_sales = full_data.groupby(['Year', 'Month'])['Sales'].sum().reset_index()
        
        fig = go.Figure()
        for year in [2024, 2025, 2026]:
            year_data = monthly_sales[monthly_sales['Year'] == year]
            fig.add_trace(go.Scatter(
                x=year_data['Month'], y=year_data['Sales'],
                mode='lines+markers', name=str(year)
            ))
        
        st.plotly_chart(fig, use_container_width=True)

# DETAY VERİLER
with main_tabs[2]:
    if st.session_state.forecast_result is None:
        st.warning("⚠️ Önce tahmini hesaplayın.")
    else:
        full_data = st.session_state.forecast_result['full_data']
        
        st.subheader("Detaylı Veri")
        selected_month = st.selectbox("Ay", list(range(1, 13)))
        
        month_data = full_data[full_data['Month'] == selected_month]
        st.dataframe(month_data, use_container_width=True)
        
        csv = month_data.to_csv(index=False, encoding='utf-8-sig')
        st.download_button("📥 CSV", csv, f"ay_{selected_month}.csv", "text/csv")

st.markdown("---")
st.markdown("<div style='text-align: center; color: #666;'><p>v3.0 - Gelişmiş Parametre Yönetimi</p></div>", unsafe_allow_html=True)
