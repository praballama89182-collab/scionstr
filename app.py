import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="PPC & Total Sales Master Dashboard", page_icon="📊", layout="wide")

# Mapping for Campaign Prefixes
BRAND_MAP = {
    'MA': 'Maison de l’Avenir',
    'CL': 'Creation Lamis',
    'JPD': 'Jean Paul Dupont',
    'PC': 'Paris Collection',
    'DC': 'Dorall Collection',
    'CPT': 'CP Trendies'
}

# Mapping for Business Report Titles
BRAND_KEYWORDS = {
    'Maison de l’Avenir': ['MAISON DE L’AVENIR', 'MAISON DE LAVENIR', 'MAISON'],
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

def calculate_rates(spend, sales, imps, clicks, orders, overall_sales=0):
    """Calculates all PPC ratios safely."""
    ctr = (clicks / imps) if imps > 0 else 0
    cpc = (spend / clicks) if clicks > 0 else 0
    roas = (sales / spend) if spend > 0 else 0
    acos = (spend / sales) if sales > 0 else 0
    cvr = (orders / clicks) if clicks > 0 else 0
    tacos = (spend / overall_sales) if overall_sales > 0 else 0
    return ctr, cpc, roas, acos, cvr, tacos

def display_dashboard(spend, sales, imps, clicks, orders, overall_sales=0):
    """Displays a clean row of 10 metrics."""
    ctr, cpc, roas, acos, cvr, tacos = calculate_rates(spend, sales, imps, clicks, orders, overall_sales)
    
    # Row 1: Volume
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Ad Spend", f"{spend:,.2f}")
    m2.metric("Ad Sales", f"{sales:,.2f}")
    m3.metric("Overall Sales", f"{overall_sales:,.2f}")
    m4.metric("Impressions", f"{int(imps):,}")
    m5.metric("Clicks", f"{int(clicks):,}")
    
    # Row 2: Efficiency
    e1, e2, e3, e4, e5 = st.columns(5)
    e1.metric("CTR", f"{ctr:.2%}")
    e2.metric("CPC", f"{cpc:.2f}")
    e3.metric("ACOS", f"{acos:.2%}")
    e4.metric("ROAS", f"{roas:.2f}")
    e5.metric("TACOS", f"{tacos:.2%}")

st.title("Amazon Unified Brand Dashboard")
st.sidebar.header("Data Uploads")
ads_file = st.sidebar.file_uploader("1. Search Term Report (Ads)", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("2. Business Report (Total Sales)", type=["csv", "xlsx"])

if ads_file:
    # Load and Clean Ads
    ads_df = pd.read_csv(ads_file, encoding='utf-8-sig') if ads_file.name.endswith('.csv') else pd.read_excel(ads_file)
    ads_df = ads_df.map(clean_numeric)
    ads_df.columns = [c.strip() for c in ads_df.columns]
    ads_df['Brand'] = ads_df['Campaign Name'].apply(lambda x: BRAND_MAP.get(str(x).replace('|', '_').split('_')[0].strip().upper(), str(x).replace('|', '_').split('_')[0].strip().upper()))
    
    # Dynamic Cols
    search_col = next((c for c in ads_df.columns if 'Search Term' in c), 'Customer Search Term')
    ad_sales_col = next((c for c in ads_df.columns if 'Sales' in c), '7 Day Total Sales')
    ad_orders_col = next((c for c in ads_df.columns if 'Orders' in c), '7 Day Total Orders')

    # Load and Clean Business
    total_sales_map = {}
    if biz_file:
        biz_df = pd.read_csv(biz_file) if biz_file.name.endswith('.csv') else pd.read_excel(biz_file)
        biz_df = biz_df.map(clean_numeric)
        title_col = next((c for c in biz_df.columns if 'Title' in c), biz_df.columns[2])
        biz_sales_col = next((c for c in biz_df.columns if 'Sales' in c), 'Ordered Product Sales')
        biz_df['Brand'] = biz_df[title_col].apply(identify_brand_from_title)
        total_sales_map = biz_df.groupby('Brand')[biz_sales_col].sum().to_dict()

    # --- UI TABS ---
    unique_brands = sorted(ads_df['Brand'].unique())
    tabs = st.tabs(["🌍 Overall Portfolio"] + unique_brands)

    # 1. Overall Portfolio Tab
    with tabs[0]:
        st.subheader("Combined Portfolio Performance")
        total_biz = sum(total_sales_map.values())
        display_dashboard(ads_df['Spend'].sum(), ads_df[ad_sales_col].sum(), ads_df['Impressions'].sum(), 
                          ads_df['Clicks'].sum(), ads_df[ad_orders_col].sum(), total_biz)
        st.divider()

    # 2. Brand Tabs
    summary_data_for_export = []
    for i, brand in enumerate(unique_brands):
        with tabs[i+1]:
            b_ads = ads_df[ads_df['Brand'] == brand]
            b_biz = total_sales_map.get(brand, 0.0)
            
            st.subheader(f"🚀 {brand} Snapshot")
            display_dashboard(b_ads['Spend'].sum(), b_ads[ad_sales_col].sum(), b_ads['Impressions'].sum(), 
                              b_ads['Clicks'].sum(), b_ads[ad_orders_col].sum(), b_biz)
            
            # Add to export summary
            ctr, cpc, roas, acos, cvr, tacos = calculate_rates(b_ads['Spend'].sum(), b_ads[ad_sales_col].sum(), b_ads['Impressions'].sum(), b_ads['Clicks'].sum(), b_ads[ad_orders_col].sum(), b_biz)
            summary_data_for_export.append({'Brand': brand, 'Ad Spend': b_ads['Spend'].sum(), 'Ad Sales': b_ads[ad_sales_col].sum(), 'Overall Sales': b_biz, 'Imps': b_ads['Impressions'].sum(), 'Clicks': b_ads['Clicks'].sum(), 'ACOS': acos, 'ROAS': roas, 'TACOS': tacos})

            st.divider()
            st.subheader("Detailed Campaign & Search Term Analysis")
            detail = b_ads.groupby(['Campaign Name', search_col]).agg({'Impressions':'sum','Clicks':'sum','Spend':'sum',ad_sales_col:'sum',ad_orders_col:'sum'}).reset_index()
            # Calculate metrics for the table
            detail['CTR'] = (detail['Clicks']/detail['Impressions']).fillna(0)
            detail['ACOS'] = (detail['Spend']/detail[ad_sales_col]).replace([np.inf, -np.inf], 0).fillna(0)
            detail['ROAS'] = (detail[ad_sales_col]/detail['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
            st.dataframe(detail.sort_values(by=ad_sales_col, ascending=False), use_container_width=True)

    # --- EXPORT ---
    st.divider()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(summary_data_for_export).to_excel(writer, sheet_name='OVERVIEW', index=False)
        for b in unique_brands:
            b_df = ads_df[ads_df['Brand'] == b].groupby(['Campaign Name', search_col]).agg({'Spend':'sum', ad_sales_col:'sum', 'Clicks':'sum', 'Impressions':'sum'}).reset_index()
            b_df.to_excel(writer, sheet_name=b[:31], index=False)

    st.download_button("📥 Download Master Multi-Tab Report", data=output.getvalue(), file_name="Master_Brand_Report.xlsx", use_container_width=True)
