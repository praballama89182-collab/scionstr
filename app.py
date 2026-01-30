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

st.title("Amazon Search Term Performance Dashboard")
st.write("Processing brands, cleaning 'AED', and calculating ACOS, ROAS, CTR, and CPC.")

uploaded_file = st.file_uploader("Upload Search Term Report", type=["csv", "xlsx"])

def calculate_metrics(df, sales_col, orders_col):
    """Calculates rates and ratios correctly after aggregation."""
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
        df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
    else:
        df = pd.read_excel(uploaded_file)

    # 2. Global Clean: Strip 'AED' and convert to numeric
    def clean_numeric(val):
        if isinstance(val, str):
            cleaned = val.replace('AED', '').replace('aed', '').replace(',', '').strip()
            try:
                return pd.to_numeric(cleaned)
            except:
                return cleaned
        return val

    df = df.map(clean_numeric)

    # 3. Detect column names dynamically (Amazon uses different spaces/formats)
    search_col = next((c for c in df.columns if 'Search Term' in c), df.columns[0])
    sales_col = next((c for c in df.columns if 'Sales' in c), 'Sales')
    orders_col = next((c for c in df.columns if 'Orders' in c), 'Orders')

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
            st.subheader(f"Top Search Terms: {brand}")
            
            # Group by Search Term and SUM basic volumes
            brand_summary = df[df['Brand'] == brand].groupby(search_col).agg({
                'Impressions': 'sum',
                'Clicks': 'sum',
                'Spend': 'sum',
                sales_col: 'sum',
                orders_col: 'sum'
            })

            # Calculate Rates (CTR, CPC, ACOS, ROAS, CVR)
            brand_summary = calculate_metrics(brand_summary, sales_col, orders_col)
            
            # Sort by Sales
            brand_summary = brand_summary.sort_values(by=sales_col, ascending=False)

            # Display with formatting
            st.dataframe(brand_summary.style.format({
                'CTR': '{:.2%}',
                'CVR': '{:.2%}',
                'ACOS': '{:.2%}',
                'ROAS': '{:.2f}',
                'CPC': '{:.2f}',
                'Spend': '{:.2f}',
                sales_col: '{:.2f}'
            }), use_container_width=True)

    # 6. Prepare Full Export
    st.divider()
    
    # Calculate metrics for the global dataframe before export
    full_report = df.groupby(['Brand', 'Campaign Name', search_col]).agg({
        'Impressions': 'sum',
        'Clicks': 'sum',
        'Spend': 'sum',
        sales_col: 'sum',
        orders_col: 'sum'
    }).reset_index()
    
    full_report = calculate_metrics(full_report, sales_col, orders_col)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        full_report.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Download Professional Brand Report (Calculated Metrics)",
        data=output.getvalue(),
        file_name=f"Full_Brand_Report_{uploaded_file.name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
