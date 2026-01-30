import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="PPC Brand Analyzer Pro", page_icon="📊", layout="wide")

# Brand Mapping
BRAND_MAP = {
    'MA': 'Maison de l’Avenir',
    'CL': 'Creation Lamis',
    'JPD': 'Jean Paul Dupont',
    'PC': 'Paris Collection',
    'DC': 'Dorall Collection',
    'CPT': 'CP Trendies'
}

st.title("Amazon Search Term & Campaign Performance")
st.write("Organizing reports by Brand and Campaign with calculated PPC metrics.")

uploaded_file = st.file_uploader("Upload Search Term Report", type=["csv", "xlsx"])

def calculate_metrics(df, sales_col, orders_col):
    """Accurately calculates rates and ratios."""
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

    # 3. Identify columns dynamically
    # Note: Using .strip() on column names to handle Amazon's hidden trailing spaces
    df.columns = [c.strip() for c in df.columns]
    
    search_col = next((c for c in df.columns if 'Search Term' in c), 'Customer Search Term')
    sales_col = next((c for c in df.columns if 'Sales' in c), '7 Day Total Sales')
    orders_col = next((c for c in df.columns if 'Orders' in c), '7 Day Total Orders')
    impressions_col = 'Impressions'
    clicks_col = 'Clicks'
    spend_col = 'Spend'

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
            st.subheader(f"{brand} Search Term Performance")
            
            # Group by Campaign AND Search Term
            brand_summary = df[df['Brand'] == brand].groupby(['Campaign Name', search_col]).agg({
                impressions_col: 'sum',
                clicks_col: 'sum',
                spend_col: 'sum',
                sales_col: 'sum',
                orders_col: 'sum'
            }).reset_index()

            # Calculate metrics on grouped data
            brand_summary = calculate_metrics(brand_summary, sales_col, orders_col)
            
            # Sort by Sales
            brand_summary = brand_summary.sort_values(by=sales_col, ascending=False)

            # Display with professional formatting
            st.dataframe(brand_summary.style.format({
                'CTR': '{:.2%}',
                'CVR': '{:.2%}',
                'ACOS': '{:.2%}',
                'ROAS': '{:.2f}',
                'CPC': '{:.2f}',
                spend_col: '{:.2f}',
                sales_col: '{:.2f}'
            }), use_container_width=True)

    # 6. Final Export
    st.divider()
    
    # Clean the global report for export
    full_export = df.copy()
    full_export = calculate_metrics(full_export, sales_col, orders_col)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        full_export.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Download Full Cleaned Report with Metrics",
        data=output.getvalue(),
        file_name=f"Cleaned_{uploaded_file.name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
