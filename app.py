import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Amazon Portfolio Audit", page_icon="📊", layout="wide")

# Brand Configuration
BRAND_MAP = {
    'MA': 'Maison de l’Avenir',
    'CL': 'Creation Lamis',
    'JPD': 'Jean Paul Dupont',
    'PC': 'Paris Collection',
    'DC': 'Dorall Collection',
    'CPT': 'CP Trendies'
}

def clean_numeric(val):
    if isinstance(val, str):
        cleaned = val.replace('AED', '').replace('$', '').replace('\xa0', '').replace(',', '').strip()
        try: return pd.to_numeric(cleaned)
        except: return val
    return val

def get_brand_robust(name):
    if pd.isna(name): return "Unmapped"
    n = str(name).upper().replace('’', "'").replace('LAVENIR', "L'AVENIR").strip()
    for prefix, full_name in BRAND_MAP.items():
        if any(n.startswith(f"{prefix}{sep}") for sep in ["_", " ", "-", " |", " -"]):
            return full_name
        if full_name.upper().replace('’', "'") in n:
            return full_name
    return "Unmapped"

def calculate_audit_kpis(df):
    df['CTR'] = (df['Clicks'] / df['Impressions']).replace([np.inf, -np.inf], 0).fillna(0)
    df['CVR'] = (df['Orders'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
    df['ROAS'] = (df['Ad Sales'] / df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
    df['ACOS'] = (df['Spend'] / df['Ad Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    df['TACOS'] = (df['Spend'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    df['Organic Sales'] = df['Total Sales'] - df['Ad Sales']
    df['Paid Contrib'] = (df['Ad Sales'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    df['Organic Contrib'] = (df['Organic Sales'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    return df

st.title("📊 Amazon Portfolio Performance Audit")

st.sidebar.header("Upload Files")
sp_file = st.sidebar.file_uploader("1. Sponsored Products", type=["csv", "xlsx"])
sb_file = st.sidebar.file_uploader("2. Sponsored Brands", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("3. Business Report", type=["csv", "xlsx"])

if sp_file and sb_file and biz_file:
    def load_and_standardize(file):
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        df.columns = [str(c).strip() for c in df.columns]
        # Cleanup math-only columns
        for col in df.columns:
            if not any(x in col.lower() for x in ['name', 'title', 'term', 'brand']):
                df[col] = df[col].apply(clean_numeric)
        return df

    sp_df, sb_df, biz_df = load_and_standardize(sp_file), load_and_standardize(sb_file), load_and_standardize(biz_file)

    # Logic for CP Trendies and others
    sp_df['Brand'] = sp_df['Campaign Name'].apply(get_brand_robust)
    sb_df['Brand'] = sb_df['Campaign Name'].apply(get_brand_robust)
    biz_df['Brand'] = biz_df['Title'].apply(get_brand_robust)

    # Aggregation
    sp_grouped = sp_df.groupby('Brand').agg({'Spend': 'sum', '7 Day Total Sales ': 'sum', 'Clicks': 'sum', 'Impressions': 'sum', '7 Day Total Orders (#)': 'sum'}).rename(columns={'7 Day Total Sales ': 'Ad Sales', '7 Day Total Orders (#)': 'Orders'})
    sb_grouped = sb_df.groupby('Brand').agg({'Spend': 'sum', '14 Day Total Sales ': 'sum', 'Clicks': 'sum', 'Impressions': 'sum', '14 Day Total Orders (#)': 'sum'}).rename(columns={'14 Day Total Sales ': 'Ad Sales', '14 Day Total Orders (#)': 'Orders'})
    total_ads = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    total_biz = biz_df.groupby('Brand')['Ordered Product Sales'].sum().reset_index().rename(columns={'Ordered Product Sales': 'Total Sales'})
    final_df = calculate_audit_kpis(pd.merge(total_ads, total_biz, on='Brand', how='outer').fillna(0))
    final_df = final_df[final_df['Brand'] != "Unmapped"]

    tabs = st.tabs(["🌍 Portfolio Overview"] + sorted(list(BRAND_MAP.values())))

    def display_two_row_metrics(row_data):
        # Row 1: Sales & Contribution
        st.markdown("### 💰 Sales & Contribution")
        r1_c1, r1_c2, r1_c3, r1_c4, r1_c5 = st.columns(5)
        r1_c1.metric("Total Sales", f"{row_data['Total Sales']:,.2f}")
        r1_c2.metric("Ad Sales", f"{row_data['Ad Sales']:,.2f}")
        r1_c3.metric("Organic Sales", f"{row_data['Organic Sales']:,.2f}")
        r1_c4.metric("Paid Contrib %", f"{row_data['Paid Contrib']:.1%}")
        r1_c5.metric("Organic Contrib %", f"{row_data['Organic Contrib']:.1%}")

        # Row 2: Ad Efficiency & Traffic
        st.markdown("### ⚡ Ad Efficiency & Traffic")
        r2_c1, r2_c2, r2_c3, r2_c4, r2_c5, r2_c6 = st.columns(6)
        r2_c1.metric("Ad Spend", f"{row_data['Spend']:,.2f}")
        r2_c2.metric("ROAS", f"{row_data['ROAS']:.2f}")
        r2_c3.metric("TACOS", f"{row_data['TACOS']:.1%}")
        r2_c4.metric("CTR", f"{row_data['CTR']:.2%}")
        r2_c5.metric("CVR", f"{row_data['CVR']:.2%}")
        r2_c6.metric("Clicks", f"{int(row_data['Clicks']):,}")

    with tabs[0]:
        t_row = final_df.select_dtypes(include=[np.number]).sum()
        # Avg Rates for Portfolio
        t_row['CTR'] = t_row['Clicks'] / t_row['Impressions'] if t_row['Impressions'] > 0 else 0
        t_row['CVR'] = t_row['Orders'] / t_row['Clicks'] if t_row['Clicks'] > 0 else 0
        t_row['ROAS'] = t_row['Ad Sales'] / t_row['Spend'] if t_row['Spend'] > 0 else 0
        t_row['ACOS'] = t_row['Spend'] / t_row['Ad Sales'] if t_row['Ad Sales'] > 0 else 0
        t_row['TACOS'] = t_row['Spend'] / t_row['Total Sales'] if t_row['Total Sales'] > 0 else 0
        t_row['Paid Contrib'] = t_row['Ad Sales'] / t_row['Total Sales'] if t_row['Total Sales'] > 0 else 0
        t_row['Organic Contrib'] = 1 - t_row['Paid Contrib']
        t_row['Organic Sales'] = t_row['Total Sales'] - t_row['Ad Sales']
        
        display_two_row_metrics(t_row)
        st.divider()
        st.subheader("🏢 Brand Breakdown")
        st.dataframe(final_df.sort_values(by='Total Sales', ascending=False), hide_index=True, use_container_width=True)

    for i, brand in enumerate(sorted(BRAND_MAP.values())):
        with tabs[i+1]:
            b_data = final_df[final_df['Brand'] == brand].iloc[0]
            display_two_row_metrics(b_data)
            st.divider()
            st.subheader("📊 Search Term Drilldown")
            drill_df = pd.concat([
                sp_df[sp_df['Brand'] == brand][['Campaign Name', 'Customer Search Term', 'Impressions', 'Clicks', 'Spend', '7 Day Total Sales ']],
                sb_df[sb_df['Brand'] == brand][['Campaign Name', 'Customer Search Term', 'Impressions', 'Clicks', 'Spend', '14 Day Total Sales ']]
            ]).sort_values(by='Spend', ascending=False)
            st.dataframe(drill_df, hide_index=True, use_container_width=True)

    # Download Report
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='PORTFOLIO_AUDIT', index=False)
    st.sidebar.download_button("📥 Download Report", data=output.getvalue(), file_name="Amazon_Portfolio_Audit.xlsx")
