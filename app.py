import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="PPC Portfolio Analyzer", page_icon="📊", layout="wide")

# Brand Mapping
BRAND_MAP = {
    'MA': 'Maison de l’Avenir',
    'CL': 'Creation Lamis',
    'JPD': 'Jean Paul Dupont',
    'PC': 'Paris Collection',
    'DC': 'Dorall Collection',
    'CPT': 'CP Trendies'
}

st.title("Amazon Master Portfolio Dashboard")
st.write("Combined overview and individual brand analysis with 'AED' cleaning.")

uploaded_file = st.file_uploader("Upload Search Term Report", type=["csv", "xlsx"])

def calculate_metrics(df, sales_col, orders_col):
    """Accurately calculates rates and ratios."""
    df['CTR'] = (df['Clicks'] / df['Impressions']).replace([np.inf, -np.inf], 0).fillna(0)
    df['CPC'] = (df['Spend'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
    df['CVR'] = (df[orders_col] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
    df['ACOS'] = (df['Spend'] / df[sales_col]).replace([np.inf, -np.inf], 0).fillna(0)
    df['ROAS'] = (df[sales_col] / df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
    return df

def display_metric_row(label, data, s_col, o_col):
    """Helper to display the 7-column metric row."""
    t_spend = data['Spend'].sum()
    t_sales = data[s_col].sum()
    t_imps = data['Impressions'].sum()
    t_clicks = data['Clicks'].sum()
    t_orders = data[o_col].sum()
    
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric(f"Total Spends", f"{t_spend:,.2f}")
    c2.metric(f"Total Sales", f"{t_sales:,.2f}")
    c3.metric("Impressions", f"{t_imps:,}")
    c4.metric("Clicks", f"{t_clicks:,}")
    c5.metric("CTR", f"{(t_clicks/t_imps):.2%}" if t_imps > 0 else "0%")
    c6.metric("ROAS", f"{(t_sales/t_spend):.2f}" if t_spend > 0 else "0.00")
    c7.metric("CVR", f"{(t_orders/t_clicks):.2%}" if t_clicks > 0 else "0%")

if uploaded_file:
    ext = uploaded_file.name.split('.')[-1]
    
    # 1. Load & Clean Data
    if ext == 'csv':
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        except:
            df = pd.read_csv(uploaded_file, encoding='cp1252')
    else:
        df = pd.read_excel(uploaded_file)

    df = df.map(lambda x: pd.to_numeric(str(x).replace('AED', '').replace('aed', '').replace(',', '').strip(), errors='ignore') if isinstance(x, str) else x)
    df.columns = [c.strip() for c in df.columns]

    # 2. Identify Columns
    search_col = next((c for c in df.columns if 'Search Term' in c), 'Customer Search Term')
    sales_col = next((c for c in df.columns if 'Sales' in c), '7 Day Total Sales')
    orders_col = next((c for c in df.columns if 'Orders' in c), '7 Day Total Orders')

    # 3. Brand Identification
    df['Brand'] = df['Campaign Name'].apply(lambda x: BRAND_MAP.get(str(x).replace('|', '_').split('_')[0].strip().upper(), str(x).replace('|', '_').split('_')[0].strip().upper()))
    unique_brands = sorted(df['Brand'].unique())

    # --- UI TABS ---
    all_tabs_names = ["🌍 Overall Portfolio"] + unique_brands
    tabs = st.tabs(all_tabs_names)

    # TAB 1: OVERALL PORTFOLIO
    with tabs[0]:
        st.subheader("Combined Performance (All Brands)")
        display_metric_row("Portfolio", df, sales_col, orders_col)
        st.divider()
        st.write("### Brand-wise Summary")
        brand_summary_table = df.groupby('Brand').agg({
            'Impressions': 'sum', 'Clicks': 'sum', 'Spend': 'sum',
            sales_col: 'sum', orders_col: 'sum'
        }).reset_index()
        brand_summary_table = calculate_metrics(brand_summary_table, sales_col, orders_col)
        st.dataframe(brand_summary_table.style.format({
            'CTR': '{:.2%}', 'CVR': '{:.2%}', 'ACOS': '{:.2%}', 'ROAS': '{:.2f}', 'CPC': '{:.2f}', 'Spend': '{:.2f}', sales_col: '{:.2f}'
        }), use_container_width=True)

    # INDIVIDUAL BRAND TABS
    for i, brand in enumerate(unique_brands):
        with tabs[i+1]:
            brand_raw = df[df['Brand'] == brand]
            st.subheader(f"🚀 {brand} Overview")
            display_metric_row(brand, brand_raw, sales_col, orders_col)
            st.divider()
            
            st.subheader("🔍 Search Term & Campaign Detail")
            detail = brand_raw.groupby(['Campaign Name', search_col]).agg({
                'Impressions': 'sum', 'Clicks': 'sum', 'Spend': 'sum', sales_col: 'sum', orders_col: 'sum'
            }).reset_index()
            detail = calculate_metrics(detail, sales_col, orders_col).sort_values(by=sales_col, ascending=False)
            st.dataframe(detail.style.format({
                'CTR': '{:.2%}', 'CVR': '{:.2%}', 'ACOS': '{:.2%}', 'ROAS': '{:.2f}', 'CPC': '{:.2f}', 'Spend': '{:.2f}', sales_col: '{:.2f}'
            }), use_container_width=True)

    # --- EXPORT LOGIC ---
    st.divider()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Total Portfolio Overview
        portfolio_summary = pd.DataFrame([{'Brand': 'TOTAL PORTFOLIO', 'Impressions': df['Impressions'].sum(), 'Clicks': df['Clicks'].sum(), 'Spend': df['Spend'].sum(), 'Sales': df[sales_col].sum(), 'Orders': df[orders_col].sum()}])
        calculate_metrics(portfolio_summary, 'Sales', 'Orders').to_excel(writer, sheet_name='TOTAL_PORTFOLIO', index=False)
        
        # Sheet 2: Brand Comparison
        brand_summary_table.to_excel(writer, sheet_name='BRAND_COMPARISON', index=False)
        
        # Subsequent Sheets: Individual Brands
        for brand in unique_brands:
            brand_data = df[df['Brand'] == brand].groupby(['Campaign Name', search_col]).agg({
                'Impressions': 'sum', 'Clicks': 'sum', 'Spend': 'sum', sales_col: 'sum', orders_col: 'sum'
            }).reset_index()
            calculate_metrics(brand_data, sales_col, orders_col).sort_values(by=sales_col, ascending=False).to_excel(writer, sheet_name=brand[:31], index=False)

    st.download_button(label="📥 Download Master Multi-Tab Report", data=output.getvalue(), file_name=f"Master_Report_{uploaded_file.name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
