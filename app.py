import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Brand Search Term Analyzer", page_icon="📈", layout="wide")

# Updated records: MA maps to Maison de l’Avenir
BRAND_MAP = {
    'MA': 'Maison de l’Avenir',
    'CL': 'Creation Lamis',
    'JPD': 'Jean Paul Dupont',
    'PC': 'Paris Collection',
    'DC': 'Dorall Collection',
    'CPT': 'CP Trendies'
}

st.title("E-commerce Brand Analysis Dashboard")
st.write("Automatically cleaning 'AED' and grouping Search Terms by Brand.")

uploaded_file = st.file_uploader("Upload Amazon Search Term Report", type=["csv", "xlsx"])

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

    # 3. Brand Identification Logic
    def get_brand_name(campaign):
        # Handles both | (Maison de l'Avenir style) and _ (Creation Lamis style)
        prefix = str(campaign).replace('|', '_').split('_')[0].strip().upper()
        return BRAND_MAP.get(prefix, prefix)

    df['Brand'] = df['Campaign Name'].apply(get_brand_name)

    # 4. Interface: Create Tabs for each Brand
    unique_brands = sorted(df['Brand'].unique())
    tabs = st.tabs(unique_brands)

    for i, brand in enumerate(unique_brands):
        with tabs[i]:
            st.subheader(f"Search Term Performance: {brand}")
            
            # Filter for specific brand
            brand_df = df[df['Brand'] == brand].copy()
            
            # Identify columns for aggregation (handling minor naming variations)
            search_col = 'Customer Search Term' if 'Customer Search Term' in brand_df.columns else brand_df.columns[0]
            sales_col = '7 Day Total Sales ' if '7 Day Total Sales ' in brand_df.columns else '7 Day Total Sales'
            
            # Pivot: Rows = Search Terms
            summary = brand_df.groupby(search_col).agg({
                'Impressions': 'sum',
                'Clicks': 'sum',
                'Spend': 'sum',
                sales_col: 'sum'
            }).sort_values(by=sales_col, ascending=False)

            st.dataframe(summary, use_container_width=True)

    # 5. Export Full Cleaned Data
    st.divider()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    
    st.download_button(
        label="📥 Download All Cleaned Data (Excel)",
        data=output.getvalue(),
        file_name=f"Cleaned_Report_{uploaded_file.name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
