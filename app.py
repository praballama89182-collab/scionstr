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

st.title("Amazon Brand Performance Dashboard")
st.write("Calculates PPC metrics, cleans 'AED', and exports a tabbed Excel report.")

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
    unique_brands = sorted(df['Brand'].unique())

    # --- UI DASHBOARD ---
    tabs = st.tabs(unique_brands)
    summary_list = []

    for i, brand in enumerate(unique_brands):
        with tabs[i]:
            brand_raw = df[df['Brand'] == brand]
            
            # Totals for Overview
            t_spend = brand_raw['Spend'].sum()
            t_sales = brand_raw[sales_col].sum()
            t_imps = brand_raw['Impressions'].sum()
            t_clicks = brand_raw['Clicks'].sum()
            t_orders = brand_raw[orders_col].sum()
            
            # Store for the Summary sheet
            summary_list.append({
                'Brand': brand, 'Spend': t_spend, 'Sales': t_sales, 
                'Impressions': t_imps, 'Clicks': t_clicks, 'Orders': t_orders
            })

            # Display Metrics Row
            c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
            c1.metric("Spends", f"{t_spend:,.2f}")
            c2.metric("Sales", f"{t_sales:,.2f}")
            c3.metric("Impressions", f"{t_imps:,}")
            c4.metric("Clicks", f"{t_clicks:,}")
            c5.metric("CTR", f"{(t_clicks/t_imps):.2%}" if t_imps > 0 else "0%")
            c6.metric("ROAS", f"{(t_sales/t_spend):.2f}" if t_spend > 0 else "0.00")
            c7.metric("CVR", f"{(t_orders/t_clicks):.2%}" if t_clicks > 0 else "0%")

            st.divider()

            # Detailed Search Term Table
            brand_summary = brand_raw.groupby(['Campaign Name', search_col]).agg({
                'Impressions': 'sum', 'Clicks': 'sum', 'Spend': 'sum',
                sales_col: 'sum', orders_col: 'sum'
            }).reset_index()
            brand_summary = calculate_metrics(brand_summary, sales_col, orders_col)
            brand_summary = brand_summary.sort_values(by=sales_col, ascending=False)

            st.dataframe(brand_summary.style.format({
                'CTR': '{:.2%}', 'CVR': '{:.2%}', 'ACOS': '{:.2%}',
                'ROAS': '{:.2f}', 'CPC': '{:.2f}', 'Spend': '{:.2f}', sales_col: '{:.2f}'
            }), use_container_width=True)

    # --- TAB-WISE EXPORT LOGIC ---
    st.divider()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # 1. Create Summary Sheet
        summary_df = pd.DataFrame(summary_list)
        summary_df = calculate_metrics(summary_df, 'Sales', 'Orders')
        summary_df.to_excel(writer, sheet_name='OVERVIEW', index=False)
        
        # 2. Create Individual Brand Sheets
        for brand in unique_brands:
            brand_data = df[df['Brand'] == brand].groupby(['Campaign Name', search_col]).agg({
                'Impressions': 'sum', 'Clicks': 'sum', 'Spend': 'sum',
                sales_col: 'sum', orders_col: 'sum'
            }).reset_index()
            brand_data = calculate_metrics(brand_data, sales_col, orders_col)
            brand_data = brand_data.sort_values(by=sales_col, ascending=False)
            
            # Clean sheet name (max 31 chars for Excel)
            sheet_name = brand[:31]
            brand_data.to_excel(writer, sheet_name=sheet_name, index=False)

    st.download_button(
        label="📥 Download Tabbed Brand Report (Excel)",
        data=output.getvalue(),
        file_name=f"Multi_Brand_Report_{uploaded_file.name}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
