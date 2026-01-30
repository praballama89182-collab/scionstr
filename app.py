import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="PPC & Organic Master Dashboard", page_icon="📊", layout="wide")

# Brand Mapping
BRAND_MAP = {
    'MA': 'Maison de l’Avenir',
    'CL': 'Creation Lamis',
    'JPD': 'Jean Paul Dupont',
    'PC': 'Paris Collection',
    'DC': 'Dorall Collection',
    'CPT': 'CP Trendies'
}

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

def calculate_all_metrics(spend, ad_sales, imps, clicks, orders, total_sales):
    """Calculates all rates, organic metrics, and contributions."""
    organic_sales = max(0, total_sales - ad_sales)
    ad_contrib = (ad_sales / total_sales) if total_sales > 0 else 0
    org_contrib = (organic_sales / total_sales) if total_sales > 0 else 0
    
    ctr = (clicks / imps) if imps > 0 else 0
    cpc = (spend / clicks) if clicks > 0 else 0
    acos = (spend / ad_sales) if ad_sales > 0 else 0
    roas = (ad_sales / spend) if spend > 0 else 0
    tacos = (spend / total_sales) if total_sales > 0 else 0
    
    return {
        "organic_sales": organic_sales,
        "ad_contrib": ad_contrib,
        "org_contrib": org_contrib,
        "ctr": ctr, "cpc": cpc, "acos": acos, "roas": roas, "tacos": tacos
    }

def display_dashboard(spend, ad_sales, imps, clicks, orders, total_sales):
    m = calculate_all_metrics(spend, ad_sales, imps, clicks, orders, total_sales)
    
    st.markdown("#### 💰 Sales & Contribution Mix")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Overall Sales", f"{total_sales:,.2f}")
    c2.metric("Ad Sales", f"{ad_sales:,.2f}", help="Sales from Amazon Advertising")
    c3.metric("Organic Sales", f"{m['organic_sales']:,.2f}", help="Total Sales minus Ad Sales")
    c4.metric("Ad Contribution", f"{m['ad_contrib']:.1%}")
    c5.metric("Organic Contribution", f"{m['org_contrib']:.1%}")

    st.markdown("#### ⚡ Ad Efficiency & Traffic")
    e1, e2, e3, e4, e5, e6 = st.columns(6)
    e1.metric("Ad Spend", f"{spend:,.2f}")
    e2.metric("ACOS", f"{m['acos']:.2%}")
    e3.metric("ROAS", f"{m['roas']:.2f}")
    e4.metric("TACOS", f"{m['tacos']:.2%}")
    e5.metric("CTR", f"{m['ctr']:.2%}")
    e6.metric("CPC", f"{m['cpc']:.2f}")

st.title("Amazon Master Dashboard: Organic vs. Ads")
st.sidebar.header("Upload Files")
ads_file = st.sidebar.file_uploader("1. Search Term Report (Ads)", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("2. Business Report (Total Sales)", type=["csv", "xlsx"])
brand_st_file = st.sidebar.file_uploader("3. Brand Search Term Report (Search Analytics)", type=["csv", "xlsx"])

if ads_file:
    # 1. Load Ads
    ads_df = pd.read_csv(ads_file, encoding='utf-8-sig') if ads_file.name.endswith('.csv') else pd.read_excel(ads_file)
    ads_df = ads_df.map(clean_numeric)
    ads_df.columns = [c.strip() for c in ads_df.columns]
    ads_df['Brand'] = ads_df['Campaign Name'].apply(lambda x: BRAND_MAP.get(str(x).replace('|', '_').split('_')[0].strip().upper(), str(x).replace('|', '_').split('_')[0].strip().upper()))
    
    ad_sales_col = next((c for c in ads_df.columns if 'Sales' in c), '7 Day Total Sales')
    ad_orders_col = next((c for c in ads_df.columns if 'Orders' in c), '7 Day Total Orders')
    search_col = next((c for c in ads_df.columns if 'Search Term' in c), 'Customer Search Term')

    # 2. Load Business
    total_sales_map = {}
    if biz_file:
        biz_df = pd.read_csv(biz_file) if biz_file.name.endswith('.csv') else pd.read_excel(biz_file)
        biz_df = biz_df.map(clean_numeric)
        title_col = next((c for c in biz_df.columns if 'Title' in c), biz_df.columns[2])
        biz_sales_col = next((c for c in biz_df.columns if 'Sales' in c), 'Ordered Product Sales')
        biz_df['Brand'] = biz_df[title_col].apply(identify_brand_from_title)
        total_sales_map = biz_df.groupby('Brand')[biz_sales_col].sum().to_dict()

    # 3. Load Brand ST Report (New)
    brand_st_df = None
    if brand_st_file:
        brand_st_df = pd.read_csv(brand_st_file) if brand_st_file.name.endswith('.csv') else pd.read_excel(brand_st_file)
        st.sidebar.success("Brand Search Term Report Loaded")

    # 4. UI Tabs
    unique_brands = sorted(ads_df['Brand'].unique())
    tabs = st.tabs(["🌍 Overall Portfolio"] + unique_brands)

    # Portfolio Tab
    with tabs[0]:
        display_dashboard(ads_df['Spend'].sum(), ads_df[ad_sales_col].sum(), ads_df['Impressions'].sum(), 
                          ads_df['Clicks'].sum(), ads_df[ad_orders_col].sum(), sum(total_sales_map.values()))
    
    # Individual Brand Tabs
    summary_for_export = []
    for i, brand in enumerate(unique_brands):
        with tabs[i+1]:
            b_ads = ads_df[ads_df['Brand'] == brand]
            b_total = total_sales_map.get(brand, 0.0)
            
            display_dashboard(b_ads['Spend'].sum(), b_ads[ad_sales_col].sum(), b_ads['Impressions'].sum(), 
                              b_ads['Clicks'].sum(), b_ads[ad_orders_col].sum(), b_total)
            
            m = calculate_all_metrics(b_ads['Spend'].sum(), b_ads[ad_sales_col].sum(), b_ads['Impressions'].sum(), b_ads['Clicks'].sum(), b_ads[ad_orders_col].sum(), b_total)
            summary_for_export.append({'Brand': brand, 'Total Sales': b_total, 'Ad Sales': b_ads[ad_sales_col].sum(), 'Organic Sales': m['organic_sales'], 'Ad Contribution %': m['ad_contrib'], 'Ad Spend': b_ads['Spend'].sum(), 'ACOS': m['acos'], 'TACOS': m['tacos']})

            st.divider()
            
            # Show Brand Search Term Data if available
            if brand_st_df is not None:
                st.subheader(f"🔍 Brand Search Analytics - {brand}")
                st.caption("Insights from the uploaded Brand Search Term Report")
                st.dataframe(brand_st_df, use_container_width=True)
                st.divider()

            st.subheader("Search Term Drilldown")
            detail = b_ads.groupby(['Campaign Name', search_col]).agg({'Impressions':'sum','Clicks':'sum','Spend':'sum',ad_sales_col:'sum',ad_orders_col:'sum'}).reset_index()
            st.dataframe(detail.sort_values(by=ad_sales_col, ascending=False), use_container_width=True)

    # 5. Export
    st.divider()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(summary_for_export).to_excel(writer, sheet_name='OVERVIEW', index=False)
        for b in unique_brands:
            ads_df[ads_df['Brand'] == b].to_excel(writer, sheet_name=b[:31], index=False)
    st.download_button("📥 Download Master Multi-Tab Report", data=output.getvalue(), file_name="Master_Brand_Report.xlsx", use_container_width=True)
