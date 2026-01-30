import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="PPC & Total Sales Analyzer", page_icon="📊", layout="wide")

# Updated Brand Mapping
BRAND_MAP = {
    'MA': 'Maison de l’Avenir',
    'CL': 'Creation Lamis',
    'JPD': 'Jean Paul Dupont',
    'PC': 'Paris Collection',
    'DC': 'Dorall Collection',
    'CPT': 'CP Trendies'
}

# Keywords for Business Report mapping (since it has no Campaign Name)
BRAND_KEYWORDS = {
    'Maison de l’Avenir': ['MAISON DE L’AVENIR', 'MAISON DE LAVENIR'],
    'Creation Lamis': ['CREATION LAMIS', 'CREATION DELUXE', 'CREATION'],
    'Jean Paul Dupont': ['JEAN PAUL DUPONT', 'JPD'],
    'Paris Collection': ['PARIS COLLECTION'],
    'Dorall Collection': ['DORALL COLLECTION'],
    'CP Trendies': ['CP TRENDIES', 'CPT']
}

def clean_numeric(val):
    if isinstance(val, str):
        cleaned = val.replace('AED', '').replace('\xa0', '').replace(',', '').strip()
        try: return pd.to_numeric(cleaned)
        except: return val
    return val

def identify_brand_from_title(title):
    title_upper = str(title).upper()
    for brand, keywords in BRAND_KEYWORDS.items():
        if any(kw in title_upper for kw in keywords):
            return brand
    return 'Other'

def calculate_metrics(df, sales_col, orders_col):
    df['CTR'] = (df['Clicks'] / df['Impressions']).replace([np.inf, -np.inf], 0).fillna(0)
    df['CPC'] = (df['Spend'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
    df['CVR'] = (df[orders_col] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
    df['ACOS'] = (df['Spend'] / df[sales_col]).replace([np.inf, -np.inf], 0).fillna(0)
    df['ROAS'] = (df[sales_col] / df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
    return df

st.title("Amazon Master Dashboard: Ads + Total Sales")
st.sidebar.header("Upload Files")
ads_file = st.sidebar.file_uploader("1. Upload Search Term Report (Ads)", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("2. Upload Business Report (Total Sales)", type=["csv", "xlsx"])

if ads_file:
    # --- PROCESS ADS DATA ---
    ads_df = pd.read_csv(ads_file, encoding='utf-8-sig') if ads_file.name.endswith('.csv') else pd.read_excel(ads_file)
    ads_df = ads_df.map(clean_numeric)
    ads_df.columns = [c.strip() for c in ads_df.columns]
    
    # Identify Brand and calculate metrics
    ads_df['Brand'] = ads_df['Campaign Name'].apply(lambda x: BRAND_MAP.get(str(x).replace('|', '_').split('_')[0].strip().upper(), str(x).replace('|', '_').split('_')[0].strip().upper()))
    
    search_col = next((c for c in ads_df.columns if 'Search Term' in c), 'Customer Search Term')
    ad_sales_col = next((c for c in ads_df.columns if 'Sales' in c), '7 Day Total Sales')
    ad_orders_col = next((c for c in ads_df.columns if 'Orders' in c), '7 Day Total Orders')

    # --- PROCESS BUSINESS DATA ---
    total_sales_map = {}
    if biz_file:
        biz_df = pd.read_csv(biz_file) if biz_file.name.endswith('.csv') else pd.read_excel(biz_file)
        biz_df = biz_df.map(clean_numeric)
        title_col = 'Title' if 'Title' in biz_df.columns else biz_df.columns[2]
        sales_val_col = 'Ordered Product Sales' if 'Ordered Product Sales' in biz_df.columns else biz_df.columns[-2]
        
        biz_df['Brand'] = biz_df[title_col].apply(identify_brand_from_title)
        total_sales_map = biz_df.groupby('Brand')[sales_val_col].sum().to_dict()

    # --- UI TABS ---
    unique_brands = sorted(ads_df['Brand'].unique())
    tabs = st.tabs(["🌍 Overall Portfolio"] + unique_brands)

    # OVERALL TAB
    with tabs[0]:
        t_spend = ads_df['Spend'].sum()
        t_ad_sales = ads_df[ad_sales_col].sum()
        t_overall_sales = sum(total_sales_map.values())
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Spends", f"{t_spend:,.2f}")
        c2.metric("Ad Sales", f"{t_ad_sales:,.2f}")
        c3.metric("Overall Sales", f"{t_overall_sales:,.2f}" if biz_file else "Upload Biz Report")
        c4.metric("Total ROAS", f"{(t_ad_sales/t_spend):.2f}" if t_spend > 0 else "0.00")
        c5.metric("TACOS", f"{(t_spend/t_overall_sales):.2%}" if t_overall_sales > 0 else "N/A")

    # BRAND TABS
    for i, brand in enumerate(unique_brands):
        with tabs[i+1]:
            brand_ads = ads_df[ads_df['Brand'] == brand]
            b_spend = brand_ads['Spend'].sum()
            b_ad_sales = brand_ads[ad_sales_col].sum()
            b_overall = total_sales_map.get(brand, 0.0)

            st.subheader(f"🚀 {brand} Summary")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Ad Spends", f"{b_spend:,.2f}")
            col2.metric("Ad Sales", f"{b_ad_sales:,.2f}")
            col3.metric("Overall Sales", f"{b_overall:,.2f}")
            col4.metric("TACOS", f"{(b_spend/b_overall):.2%}" if b_overall > 0 else "N/A")

            # Search Term Detail
            detail = brand_ads.groupby(['Campaign Name', search_col]).agg({'Impressions':'sum','Clicks':'sum','Spend':'sum',ad_sales_col:'sum',ad_orders_col:'sum'}).reset_index()
            st.dataframe(calculate_metrics(detail, ad_sales_col, ad_orders_col).sort_values(by=ad_sales_col, ascending=False), use_container_width=True)

    # --- EXPORT ---
    st.divider()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Overview Sheet
        summary_data = []
        for b in unique_brands:
            b_raw = ads_df[ads_df['Brand'] == b]
            summary_data.append({'Brand': b, 'Spends': b_raw['Spend'].sum(), 'Ad Sales': b_raw[ad_sales_col].sum(), 'Overall Sales': total_sales_map.get(b, 0)})
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='OVERVIEW', index=False)
        
        for b in unique_brands:
            sheet_df = ads_df[ads_df['Brand'] == b].groupby(['Campaign Name', search_col]).agg({'Spend':'sum', ad_sales_col:'sum'}).reset_index()
            sheet_df.to_excel(writer, sheet_name=b[:31], index=False)

    st.download_button("📥 Download Multi-Tab Master Report", data=output.getvalue(), file_name="Master_Brand_Report.xlsx", use_container_width=True)
