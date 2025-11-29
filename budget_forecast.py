import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

class BudgetForecaster:
    def __init__(self, excel_path):
        """Excel'den veriyi yükle ve temizle"""
        # Raw olarak oku, header belirtme
        df_raw = pd.read_excel(excel_path, sheet_name='Sayfa1', header=None)
        
        # Header 1. satır (index 1)
        self.df = pd.read_excel(excel_path, sheet_name='Sayfa1', header=1)
        
        self.process_data()
        
    def process_data(self):
        """Veriyi yıl bazında ayrıştır ve temizle"""
        
        # 2024 verileri - DOĞRU KOLONLAR
        df_2024 = self.df[['Month', 'MainGroupDesc', 
                           'TY Sales Unit',                # Kolon C - Adet
                           'TY Sales Value TRY2',          # Kolon J - Gerçek satış
                           'TY Gross Profit TRY2',         # Kolon H - Brüt kar  
                           'TY Gross Marjin TRY%',         # Kolon K - Brüt marj %
                           'TY Avg Store Stock Cost TRY2']].copy()  # Kolon I - Stok
        df_2024.columns = ['Month', 'MainGroup', 'Quantity', 'Sales', 'GrossProfit', 'GrossMargin%', 'Stock']
        df_2024['Year'] = 2024
        
        # 2025 verileri - DOĞRU KOLONLAR
        df_2025 = self.df[['Month', 'MainGroupDesc',
                           'TY Sales Unit',                 # Kolon L - Adet
                           'TY Sales Value TRY2.1',         # Kolon S - Gerçek satış
                           'TY Gross Profit TRY2.1',        # Kolon Q - Brüt kar
                           'TY Gross Marjin TRY%.1',        # Kolon T - Brüt marj %
                           'TY Avg Store Stock Cost TRY2.1']].copy()  # Kolon R - Stok
        df_2025.columns = ['Month', 'MainGroup', 'Quantity', 'Sales', 'GrossProfit', 'GrossMargin%', 'Stock']
        df_2025['Year'] = 2025
        
        # Birleştir
        self.data = pd.concat([df_2024, df_2025], ignore_index=True)
        
        # Toplam satırlarını çıkar
        self.data = self.data[~self.data['Month'].astype(str).str.contains('Toplam', na=False)]
        
        # Month'u integer'a çevir
        self.data['Month'] = pd.to_numeric(self.data['Month'], errors='coerce')
        
        # MainGroup boş olanları çıkar
        self.data = self.data.dropna(subset=['MainGroup'])
        
        # NaN değerleri 0 yap
        self.data = self.data.fillna(0)
        
        # SMM hesapla (COGS = Sales - GrossProfit)
        self.data['COGS'] = self.data['Sales'] - self.data['GrossProfit']
        
        # Birim Fiyat hesapla
        self.data['UnitPrice'] = np.where(
            self.data['Quantity'] > 0,
            self.data['Sales'] / self.data['Quantity'],
            0
        )
        
        # Stok/COGS oranı hesapla (hız)
        self.data['Stock_COGS_Ratio'] = np.where(
            self.data['COGS'] > 0,
            self.data['Stock'] / self.data['COGS'],
            0
        )
        
        # Son gerçekleşen yıl-ay'ı bul
        self._find_last_actual_period()
        
        # *** 2025 Kasım-Aralık için özel tahmin YAPMA ***
        # forecast_future_months bu işi yapacak
        # Sadece 2024'teki eksik ayları doldur
        self._fill_missing_months()
    
    def _find_last_actual_period(self):
        """Son gerçekleşen veriyi bul (Sales > 0 olan son ay)"""
        # Her yıl-ay için toplam satışı kontrol et
        period_sales = self.data.groupby(['Year', 'Month'])['Sales'].sum().reset_index()
        period_sales = period_sales[period_sales['Sales'] > 100000]  # Anlamlı veri kontrolü
        
        if len(period_sales) > 0:
            # Son gerçekleşen ay
            last_period = period_sales.sort_values(['Year', 'Month'], ascending=True).iloc[-1]
            self.last_actual_year = int(last_period['Year'])
            self.last_actual_month = int(last_period['Month'])
            
            print(f"✅ Son gerçekleşen veri: {self.last_actual_year}/{self.last_actual_month}")
        else:
            # Varsayılan
            self.last_actual_year = 2025
            self.last_actual_month = 10
            print(f"⚠️ Gerçekleşen veri bulunamadı, varsayılan: 2025/10")
    
    def _fill_missing_months(self):
        """SADECE 2024'teki eksik ayları tahmin et - 2025 için YAPMA"""
        
        # SADECE 2024'ü kontrol et
        for month in range(1, 13):
            # Bu ay verisi var mı?
            month_data = self.data[(self.data['Year'] == 2024) & (self.data['Month'] == month)]
            
            if len(month_data) == 0 or month_data['Sales'].sum() < 100000:
                # Eksik veya yetersiz veri - tahmin et
                self._estimate_month(2024, month)
    
    def _estimate_month(self, year, month):
        """Belirli bir ayı tahmin et - SADECE 2024 İÇİN"""
        
        # Önceki ayı al
        prev_month = month - 1
        prev_year = year
        
        if prev_month == 0:
            prev_month = 12
            prev_year = year - 1
        
        prev_data = self.data[(self.data['Year'] == prev_year) & (self.data['Month'] == prev_month)].copy()
        
        if len(prev_data) == 0:
            return  # Önceki ay da yoksa tahmin yapma
        
        estimate = prev_data.copy()
        estimate['Month'] = month
        estimate['Year'] = year
        
        # Konservatif: × 0.98
        estimate['Quantity'] = estimate['Quantity'] * 0.98 if 'Quantity' in estimate.columns else 0
        estimate['Sales'] = estimate['Sales'] * 0.98
        estimate['GrossProfit'] = estimate['GrossProfit'] * 0.98
        estimate['COGS'] = estimate['COGS'] * 0.98
        estimate['Stock'] = estimate['Stock'] * 1.0
        
        # Birim fiyat hesapla
        estimate['UnitPrice'] = np.where(
            estimate['Quantity'] > 0,
            estimate['Sales'] / estimate['Quantity'],
            0
        ) if 'Quantity' in estimate.columns else 0
        
        # Stok oranını yeniden hesapla
        estimate['Stock_COGS_Ratio'] = np.where(
            estimate['COGS'] > 0,
            estimate['Stock'] / estimate['COGS'],
            0
        )
        
        # Mevcut tahmini çıkar ve yenisini ekle
        self.data = self.data[~((self.data['Year'] == year) & (self.data['Month'] == month))]
        self.data = pd.concat([self.data, estimate], ignore_index=True)
        self.data = self.data.sort_values(['Year', 'Month', 'MainGroup']).reset_index(drop=True)
        
        print(f"📅 {year}/{month} ayı tahmini eklendi (Önceki ay × 0.98)")
    
    def calculate_seasonality(self):
        """Her ay için mevsimsellik indeksi hesapla"""
        
        # Grup ve ay bazında ortalama satış
        monthly_avg = self.data.groupby(['MainGroup', 'Month'])['Sales'].mean().reset_index()
        monthly_avg.columns = ['MainGroup', 'Month', 'AvgSales']
        
        # Her grup için yıllık ortalama
        yearly_avg = self.data.groupby('MainGroup')['Sales'].mean().reset_index()
        yearly_avg.columns = ['MainGroup', 'YearlyAvg']
        
        # Merge
        seasonality = monthly_avg.merge(yearly_avg, on='MainGroup')
        
        # Mevsimsellik indeksi = Aylık Ort / Yıllık Ort
        seasonality['SeasonalityIndex'] = np.where(
            seasonality['YearlyAvg'] > 0,
            seasonality['AvgSales'] / seasonality['YearlyAvg'],
            1
        )
        
        return seasonality[['MainGroup', 'Month', 'SeasonalityIndex']]
    
    def forecast_future_months(self, num_months=15, growth_param=0.1, margin_improvement=0.0, 
                              stock_change_pct=0.0, monthly_growth_targets=None, 
                              maingroup_growth_targets=None, lessons_learned=None,
                              inflation_adjustment=1.0, organic_multiplier=0.5,
                              price_change_matrix=None, inflation_rate=0.25):
        """
        Son gerçekleşen aydan itibaren belirtilen sayıda ay tahmin et
        
        Parameters:
        -----------
        num_months: Kaç ay ileriye tahmin yapılacak (varsayılan 15)
        growth_param: Genel büyüme hedefi
        margin_improvement: Brüt marj iyileşme hedefi
        stock_change_pct: Stok tutar değişim yüzdesi
        monthly_growth_targets: Dict {month: growth_rate} - Her ay için özel hedef
        maingroup_growth_targets: Dict {maingroup: growth_rate} - Her ana grup için özel hedef
        lessons_learned: Dict {(maingroup, month): score} - Alınan dersler (-10 ile +10 arası)
        inflation_adjustment: Enflasyon düzeltme faktörü (örn: 25/35 = 0.71)
        organic_multiplier: Organik büyüme çarpanı (0.0=Çekimser, 0.5=Normal, 1.0=İyimser)
        price_change_matrix: Dict {(maingroup, month): price_change_pct} - Fiyat değişim matrisi
        inflation_rate: Enflasyon oranı (default fiyat artışı için, örn: 0.25 = %25)
        """
        
        # Mevsimsellik hesapla
        seasonality = self.calculate_seasonality()
        
        # Son gerçekleşen ayın verisini base al
        base_data = self.data[
            (self.data['Year'] == self.last_actual_year) & 
            (self.data['Month'] == self.last_actual_month)
        ].copy()
        
        # Organik trend (2024->2025) - SADECE AYNI AYLARI KARŞILAŞTIR
        # Son gerçekleşen aya kadar olan ayları al
        common_months_2024 = self.data[
            (self.data['Year'] == 2024) & 
            (self.data['Month'] <= self.last_actual_month)
        ]['Sales'].sum()
        
        common_months_2025 = self.data[
            (self.data['Year'] == 2025) & 
            (self.data['Month'] <= self.last_actual_month)
        ]['Sales'].sum()
        
        organic_growth_raw = (common_months_2025 - common_months_2024) / common_months_2024 if common_months_2024 > 0 else 0
        
        # ENFLASYON DÜZELTMESİ UYGULA
        organic_growth = organic_growth_raw * inflation_adjustment
        
        # BÜTÇE VERSİYONU ÇARPANI UYGULA
        # 0.0 = Çekimser (organik yok), 0.5 = Normal (yarım), 1.0 = İyimser (tam)
        organic_growth = organic_growth * organic_multiplier
        
        # ========================================
        # *** STOK SAĞLIK FAKTÖRLERİNİ HESAPLA ***
        # ========================================
        
        # Ortalama Stok/COGS oranı (benchmark)
        avg_stock_ratio = base_data['Stock_COGS_Ratio'].mean()
        
        # Her ana grup için stok sağlık faktörü hesapla
        stock_health_factors = {}
        
        for _, row in base_data.iterrows():
            main_group = row['MainGroup']
            group_ratio = row['Stock_COGS_Ratio']
            
            # Benchmark'a göre sapma
            if avg_stock_ratio > 0:
                ratio_deviation = (group_ratio - avg_stock_ratio) / avg_stock_ratio
                
                # ÇOK KONSERVATIF AYARLAMA - Max %2.5
                if ratio_deviation > 0.5:  # %50'den fazla yüksekse (yavaş hareket)
                    # Hafif azalt: max %2.5 azalış
                    adjustment = -0.01 - (min(ratio_deviation - 0.5, 0.5) * 0.03)
                    adjustment = max(adjustment, -0.025)  # Max -%2.5
                elif ratio_deviation < -0.3:  # %30'dan fazla düşükse (hızlı hareket)
                    # Hafif artır: max %2.5 artış
                    adjustment = 0.01 + (min(abs(ratio_deviation) - 0.3, 0.5) * 0.03)
                    adjustment = min(adjustment, 0.025)  # Max +%2.5
                else:
                    # Normal aralıkta, ayarlama yok
                    adjustment = 0
                
                stock_health_factors[main_group] = 1 + adjustment
            else:
                stock_health_factors[main_group] = 1.0
        
        # ========================================
        # *** STOK FAKTÖRÜ HESAPLANDI ***
        # ========================================
        
        # Tahmin aylarını oluştur
        forecast_data = []
        
        for i in range(1, num_months + 1):
            # Hedef yıl-ay hesapla
            target_month = self.last_actual_month + i
            target_year = self.last_actual_year
            
            while target_month > 12:
                target_month -= 12
                target_year += 1
            
            # *** İLK 2 AY İÇİN ÖZEL YAKLAŞIM (SADECE 2025 Kasım-Aralık) ***
            if target_year == 2025 and target_month in [11, 12]:
                # Geçen yılın aynı ayını baz al
                same_month_last_year = self.data[
                    (self.data['Year'] == 2024) & 
                    (self.data['Month'] == target_month)
                ].copy()
                
                if len(same_month_last_year) > 0:
                    month_forecast = same_month_last_year.copy()
                    month_forecast['Year'] = 2025
                    month_forecast['Month'] = target_month
                    
                    # Fiyat artışını hesapla
                    month_forecast['PriceChange'] = month_forecast.apply(
                        lambda row: price_change_matrix.get((row['MainGroup'], target_month), inflation_rate) 
                        if price_change_matrix else inflation_rate,
                        axis=1
                    )
                    
                    # Fiyat artış çarpanı (örn: %25 artış = 1.25)
                    month_forecast['PriceMultiplier'] = 1 + month_forecast['PriceChange']
                    
                    # 2025 Birim Fiyat = 2024 Fiyat × Fiyat Çarpanı
                    month_forecast['UnitPrice'] = month_forecast['UnitPrice'] * month_forecast['PriceMultiplier']
                    
                    # 2025 Adet = 2024 Adet × 1.15
                    month_forecast['Quantity'] = month_forecast['Quantity'] * 1.15
                    
                    # 2025 Ciro = Adet × Fiyat
                    month_forecast['Sales'] = month_forecast['Quantity'] * month_forecast['UnitPrice']
                    
                    # *** ÖNEMLİ: Ciro artış oranını hesapla ***
                    # Ciro = Adet × Fiyat = 1.15 × Fiyat Çarpanı
                    month_forecast['SalesMultiplier'] = 1.15 * month_forecast['PriceMultiplier']
                    
                    # Brüt Kar ve SMM aynı oranda artar (marj korunsun)
                    month_forecast['GrossProfit'] = month_forecast['GrossProfit'] * month_forecast['SalesMultiplier']
                    month_forecast['COGS'] = month_forecast['COGS'] * month_forecast['SalesMultiplier']
                    
                    # Marjı yeniden hesapla
                    month_forecast['GrossMargin%'] = np.where(
                        month_forecast['Sales'] > 0,
                        month_forecast['GrossProfit'] / month_forecast['Sales'],
                        0
                    )
                    
                    # Stok
                    month_forecast['Stock'] = month_forecast['Stock'] * 1.10
                    
                    # Stok oranı
                    month_forecast['Stock_COGS_Ratio'] = np.where(
                        month_forecast['COGS'] > 0,
                        month_forecast['Stock'] / month_forecast['COGS'],
                        0
                    )
                    
                    forecast_data.append(month_forecast)
                    
                    continue
            
            # *** DİĞER AYLAR İÇİN NORMAL TAHMİN ***
            # 2026+ için: GEÇEN YILIN AYNI AYINI BASE AL
            if target_year >= 2026:
                # Önce self.data'dan bak (gerçek veri için)
                same_month_prev_year = self.data[
                    (self.data['Year'] == target_year - 1) & 
                    (self.data['Month'] == target_month)
                ]
                
                # Gerçek veri yoksa, önceki tahminlerden bak
                if len(same_month_prev_year) == 0 or same_month_prev_year['Sales'].sum() < 100000:
                    # forecast_data içinde ara (örn: 2025/11-12 tahmini)
                    for prev_forecast in forecast_data:
                        if len(prev_forecast) > 0:
                            if prev_forecast.iloc[0]['Year'] == target_year - 1 and prev_forecast.iloc[0]['Month'] == target_month:
                                same_month_prev_year = prev_forecast.copy()
                                break
                
                if len(same_month_prev_year) > 0 and same_month_prev_year['Sales'].sum() > 100000:
                    # Geçen yılın aynı ayını kullan - direkt, trend ekleme!
                    month_forecast = same_month_prev_year.copy()
                    month_forecast['Year'] = target_year
                    month_forecast['Month'] = target_month
                else:
                    # Fallback: base_data
                    month_forecast = base_data.copy()
                    month_forecast['Year'] = target_year
                    month_forecast['Month'] = target_month
            else:
                # 2025 içindeyiz, base_data kullan
                month_forecast = base_data.copy()
                month_forecast['Year'] = target_year
                month_forecast['Month'] = target_month
            
            # Mevsimselliği ekle
            month_forecast = month_forecast.merge(
                seasonality[seasonality['Month'] == target_month],
                on=['MainGroup', 'Month'],
                how='left'
            )
            month_forecast['SeasonalityIndex'] = month_forecast['SeasonalityIndex'].fillna(1.0)
            
            # Hedefleri uygula
            if monthly_growth_targets is not None:
                month_forecast['MonthlyGrowthTarget'] = monthly_growth_targets.get(target_month, growth_param)
            else:
                month_forecast['MonthlyGrowthTarget'] = growth_param
            
            if maingroup_growth_targets is not None:
                month_forecast['MainGroupGrowthTarget'] = month_forecast['MainGroup'].map(maingroup_growth_targets)
                month_forecast['MainGroupGrowthTarget'] = month_forecast['MainGroupGrowthTarget'].fillna(growth_param)
            else:
                month_forecast['MainGroupGrowthTarget'] = growth_param
            
            # Alınan dersler
            if lessons_learned is not None:
                month_forecast['LessonsScore'] = month_forecast.apply(
                    lambda row: lessons_learned.get((row['MainGroup'], target_month), 0),
                    axis=1
                )
                month_forecast['LessonsAdjustment'] = month_forecast['LessonsScore'] * 0.005
            else:
                month_forecast['LessonsAdjustment'] = 0
            
            # *** STOK SAĞLIK FAKTÖRÜNÜ EKLE ***
            month_forecast['StockHealthFactor'] = month_forecast['MainGroup'].map(stock_health_factors)
            month_forecast['StockHealthFactor'] = month_forecast['StockHealthFactor'].fillna(1.0)
            
            # Kombine büyüme hedefi
            month_forecast['CombinedGrowthTarget'] = (
                (month_forecast['MonthlyGrowthTarget'] + month_forecast['MainGroupGrowthTarget']) / 2 +
                month_forecast['LessonsAdjustment']
            )
            
            # Fiyat değişimini hesapla
            month_forecast['PriceChange'] = month_forecast.apply(
                lambda row: price_change_matrix.get((row['MainGroup'], target_month), inflation_rate) 
                if price_change_matrix else inflation_rate,
                axis=1
            )
            
            # 2026 Birim Fiyat = 2025 Fiyat × (1 + Fiyat Değişimi)
            month_forecast['UnitPrice'] = month_forecast['UnitPrice'] * (1 + month_forecast['PriceChange'])
            
            # Zaman faktörü (uzak gelecek daha konservatif)
            time_discount = 1.0 - (i * 0.01)
            time_discount = max(time_discount, 0.85)
            
            # SATIŞ TAHMİNİ (CİRO) - STOK SAĞLIK FAKTÖRÜ VE MEVSİMSELLİK İLE
            month_forecast['Sales'] = (
                month_forecast['Sales'] *
                (1 + organic_growth * 0.3) *  # Organik büyüme %30
                (1 + month_forecast['CombinedGrowthTarget']) *
                (0.8 + month_forecast['SeasonalityIndex'] * 0.2) *
                month_forecast['StockHealthFactor']
            )
            
            # ADET TAHMİNİ = Ciro / Birim Fiyat
            month_forecast['Quantity'] = np.where(
                month_forecast['UnitPrice'] > 0,
                month_forecast['Sales'] / month_forecast['UnitPrice'],
                0
            )
            
            # Marj iyileştirme
            month_forecast['GrossMargin%'] = (month_forecast['GrossMargin%'] + margin_improvement).clip(0, 1)
            month_forecast['GrossProfit'] = month_forecast['Sales'] * month_forecast['GrossMargin%']
            month_forecast['COGS'] = month_forecast['Sales'] - month_forecast['GrossProfit']
            
            # Stok
            month_forecast['Stock'] = month_forecast['Stock'] * (1 + stock_change_pct)
            month_forecast['Stock_COGS_Ratio'] = np.where(
                month_forecast['COGS'] > 0,
                month_forecast['Stock'] / month_forecast['COGS'],
                0
            )
            
            # Gereksiz kolonları temizle
            month_forecast = month_forecast[['Year', 'Month', 'MainGroup', 'Quantity', 'UnitPrice',
                                            'Sales', 'GrossProfit', 'GrossMargin%', 'Stock', 'COGS', 
                                            'Stock_COGS_Ratio']]
            
            forecast_data.append(month_forecast)
        
        # Tüm tahminleri birleştir
        all_forecasts = pd.concat(forecast_data, ignore_index=True)
        
        return all_forecasts
    
    def get_full_data_with_forecast(self, num_months=15, growth_param=0.1, margin_improvement=0.0, 
                                    stock_change_pct=0.0, monthly_growth_targets=None, 
                                    maingroup_growth_targets=None, lessons_learned=None,
                                    inflation_adjustment=1.0, organic_multiplier=0.5,
                                    price_change_matrix=None, inflation_rate=0.25):
        """Gerçekleşen veri + gelecek tahminlerini birleştir"""
        
        # Gelecek tahminini yap
        forecast = self.forecast_future_months(
            num_months=num_months,
            growth_param=growth_param,
            margin_improvement=margin_improvement,
            stock_change_pct=stock_change_pct,
            monthly_growth_targets=monthly_growth_targets,
            maingroup_growth_targets=maingroup_growth_targets,
            lessons_learned=lessons_learned,
            inflation_adjustment=inflation_adjustment,
            organic_multiplier=organic_multiplier,
            price_change_matrix=price_change_matrix,
            inflation_rate=inflation_rate
        )
        
        # Gerçekleşen veriyi düzenle - TAHMİN EDİLEN AYLARI ÇIKAR
        historical = self.data[['Year', 'Month', 'MainGroup', 'Quantity', 'UnitPrice',
                               'Sales', 'GrossProfit', 'GrossMargin%', 'Stock', 'COGS', 
                               'Stock_COGS_Ratio']].copy()
        
        # Sadece gerçek veriyi al (son gerçekleşen aya kadar)
        historical = historical[
            (historical['Year'] < self.last_actual_year) |
            ((historical['Year'] == self.last_actual_year) & (historical['Month'] <= self.last_actual_month))
        ]
        
        # Birleştir
        full_data = pd.concat([historical, forecast], ignore_index=True)
        
        return full_data
    
    def get_summary_stats(self, data):
        """Özet istatistikler - Haftalık normalize edilmiş stok/SMM oranı dahil"""
        
        summary = {}
        
        # Tüm yılları al
        years = sorted(data['Year'].unique())
        
        for year in years:
            year_data = data[data['Year'] == year].copy()
            
            # Yıllık Stok/SMM hesapla
            # Önce her ay için toplam stok ve SMM hesapla
            monthly_totals = year_data.groupby('Month').agg({
                'Stock': 'sum',
                'COGS': 'sum'
            }).reset_index()
            
            # Ortalama aylık stok ve toplam yıllık SMM
            avg_monthly_stock = monthly_totals['Stock'].mean()
            total_yearly_cogs = monthly_totals['COGS'].sum()
            
            # Haftalık oran: Ort. Aylık Stok / (Toplam Yıllık SMM / 52)
            stock_cogs_weekly = (avg_monthly_stock / (total_yearly_cogs / 52)) if total_yearly_cogs > 0 else 0
            
            summary[year] = {
                'Total_Sales': year_data['Sales'].sum(),
                'Total_GrossProfit': year_data['GrossProfit'].sum(),
                'Avg_GrossMargin%': (year_data['GrossProfit'].sum() / year_data['Sales'].sum() * 100) if year_data['Sales'].sum() > 0 else 0,
                'Avg_Stock': year_data['Stock'].mean(),
                'Avg_Stock_COGS_Ratio': year_data['Stock_COGS_Ratio'].mean(),
                'Avg_Stock_COGS_Weekly': stock_cogs_weekly
            }
        
        return summary
    
    def get_forecast_quality_metrics(self, data):
        """Forecast kalite metriklerini hesapla"""
        
        # 2024 ve 2025 verilerini al
        data_2024 = data[data['Year'] == 2024].groupby('Month')['Sales'].sum().reset_index()
        data_2025 = data[data['Year'] == 2025].groupby('Month')['Sales'].sum().reset_index()
        
        # Ortak ayları bul
        common_months = set(data_2024['Month']) & set(data_2025['Month'])
        
        if len(common_months) < 3:
            return {
                'r2_score': None,
                'mape': None,
                'trend_consistency': None,
                'confidence_level': 'Düşük',
                'avg_growth_2024_2025': None
            }
        
        # Ortak aylara göre filtrele
        sales_2024 = data_2024[data_2024['Month'].isin(common_months)].sort_values('Month')['Sales'].values
        sales_2025 = data_2025[data_2025['Month'].isin(common_months)].sort_values('Month')['Sales'].values
        
        # Büyüme oranları
        growth_rates = (sales_2025 - sales_2024) / sales_2024
        
        # Tutarlılık
        trend_consistency = 1 - min(np.std(growth_rates), 1.0)
        
        # R²
        if len(sales_2024) > 1:
            correlation = np.corrcoef(sales_2024, sales_2025)[0, 1]
            r2_score = correlation ** 2
        else:
            r2_score = 0.5
        
        # MAPE
        mape = np.mean(np.abs(growth_rates)) * 100
        
        # Güven seviyesi
        if r2_score > 0.8 and trend_consistency > 0.7:
            confidence = 'Yüksek'
        elif r2_score > 0.6 and trend_consistency > 0.5:
            confidence = 'Orta'
        else:
            confidence = 'Düşük'
        
        return {
            'r2_score': r2_score,
            'mape': mape,
            'trend_consistency': trend_consistency,
            'confidence_level': confidence,
            'avg_growth_2024_2025': np.mean(growth_rates) * 100
        }
