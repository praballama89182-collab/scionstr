import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="PPC Brand Analyzer Pro", page_icon="📊", layout="wide")

# Updated Brand Mapping
BRAND_MAP = {
    'MA': 'Maison de l’Avenir',
    'CL': 'Creation Lamis',
    'JPD': 'Jean Paul Dupont',
    'PC': 'Paris Collection',
    'DC': 'Dorall Collection',
    'CPT': 'CP Trendies'
}

st.title("Amazon Brand Performance Dashboard")
st.write("Summary metrics and search term analysis by Brand.")

uploaded_file = st.file_uploader("Upload Search Term Report", type=["csv", "xlsx"])

def calculate_metrics(df, sales_col, orders_col):
    """Accurately calculates rates and ratios for dataframes."""
    df['CTR'] = (df['Clicks'] / df['Impressions']).replace([np.inf, -np.inf], 0).fillna(0)
    df['CPC'] = (df['Spend'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
    df['CVR'] = (df[orders_col] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
    df['ACOS'] = (df['Spend'] / df[sales_col]).replace([np.inf, -np.inf], 0).fillna(0)
    df['ROAS'] = (df[sales_col] / df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
    return df

if uploaded_file:
    ext = uploaded_file.name.split('.')[-1]
    
    # 1. Load Data
    if ext == 'csv':
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        except:
            df = pd.read_csv(uploaded_file, encoding='cp1252')
    else:
        df = pd.read_excel(uploaded_file)

    # 2. Global Clean: Strip 'AED' and commas
    def clean_numeric(val):
        if isinstance(val, str):
            cleaned = val.replace('AED', '').replace('aed', '').replace(',', '').strip()
            try:
                return pd.to_numeric(cleaned)
            except:
                return cleaned
        return val

    df = df.map(clean_numeric)
    df.columns = [c.strip() for c in df.columns]

    # 3. Dynamic Column Selection
    search_col = next((c for c in df.columns if 'Search Term' in c), 'Customer Search Term')
    sales_col = next((c for c in df.columns if 'Sales' in c), '7 Day Total Sales')
    orders_col = next((c for c in df.columns if 'Orders' in c), '7 Day Total Orders')

    # 4. Brand Identification
    def get_brand_name(campaign):
        prefix = str(campaign).replace('|', '_').split('_')[0].strip().upper()
        return BRAND_MAP.get(prefix, prefix)

    df['Brand'] = df['Campaign Name'].apply(get_brand_name)

    # 5. Interface: Brand Tabs
    unique_brands = sorted(df['Brand'].unique())
    tabs = st.tabs(unique_brands)

    for i, brand in enumerate(unique_brands):
        with tabs[i]:
            # Filter brand data
            brand_raw = df[df['Brand'] == brand]
            
            # --- OVERVIEW SECTION ---
            st.subheader(f"🚀 {brand} Overview")
            
            # Calculate Brand Totals
            total_spend = brand_raw['Spend'].sum()
            total_sales = brand_raw[sales_col].sum()
            total_imps = brand_raw['Impressions'].sum()
            total_clicks = brand_raw['Clicks'].sum()
            total_orders = brand_raw[orders_col].sum()
            
            # Calculate Brand Rates
            brand_ctr = (total_clicks / total_imps) if total_imps > 0 else 0
            brand_roas = (total_sales / total_spend) if total_spend > 0 else 0
            brand_cvr = (total_orders / total_clicks) if total_clicks > 0 else 0

            # Display Metrics in Columns
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
            col1.metric("Spends", f"{total_spend:,.2f}")
            col2.metric("Sales", f"{total_sales:,.2f}")
            col3.metric("Impressions", f"{total_imps:,}")
            col4.metric("Clicks", f"{total_clicks:,}")
            col5.metric("CTR", f"{brand_ctr:.2%}")
            col6.metric("ROAS", f"{brand_roas:.2f}")
            col7.metric("CVR", f"{brand_cvr:.2%}")

            st.divider()

            # --- SEARCH TERM TABLE ---
            st.subheader("🔍 Search Term & Campaign Detail")
            brand_summary = brand_raw.groupby(['Campaign Name', search_col]).agg({
                'Impressions': 'sum',
                'Clicks': 'sum',
                'Spend': 'sum',
                sales_col: 'sum',
                orders_col: 'sum'
            }).reset_index()

            brand_summary = calculate_metrics(brand_summary, sales_col, orders_col)
            brand_summary = brand_summary.sort_values(by=sales_col, ascending=False)

            st.dataframe(brand_summary.style.format({
                'CTR': '{:.2%}', 'CVR': '{:.2%}', 'ACOS': '{:.2%}',
                'ROAS': '{:.2f}', 'CPC': '{:.2f}', 'Spend': '{:.2f}',
                sales_col: '{:.2f}'
            }), use_container_width=True)

    # 6. Global Export
    st.divider()
    full_export = df.copy()
    full_export = calculate_metrics(full_export, sales_col, orders_col)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        full_export.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Download Master Report",
        data=output.getvalue(),
        file_name=f"Master_Brand_Report_{uploaded_file.name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
