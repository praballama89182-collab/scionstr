import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Amazon Performance Overview", page_icon="📊", layout="wide")

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

def get_brand_from_name(name):
    if pd.isna(name): return "Unmapped"
    name_upper = str(name).upper().strip()
    for prefix, full_name in BRAND_MAP.items():
        if any(sep in name_upper for sep in [f"{prefix}_", f"{prefix} ", f"{prefix}-", f"{prefix} |"]):
            return full_name
    for prefix, full_name in BRAND_MAP.items():
        if prefix in name_upper:
            return full_name
    return "Unmapped"

def find_metric_col(df, keywords, exclude=['acos', 'roas']):
    for col in df.columns:
        if any(kw.lower() in col.lower() for kw in keywords):
            if not any(ex.lower() in col.lower() for ex in exclude):
                return col
    return None

st.title("📊 Amazon Portfolio Performance Overview")
st.markdown("### Historical Audit (SP + SB + Business Report)")

st.sidebar.header("Upload Files")
sp_file = st.sidebar.file_uploader("1. Sponsored Products Report", type=["csv", "xlsx"])
sb_file = st.sidebar.file_uploader("2. Sponsored Brands Report", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("3. Business Report (Total Sales)", type=["csv", "xlsx"])

if sp_file and sb_file and biz_file:
    # 1. Load Data
    def load_data(file):
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        df = df.applymap(clean_numeric)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    sp_df = load_data(sp_file)
    sb_df = load_data(sb_file)
    biz_df = load_data(biz_file)

    # 2. Map Columns
    sp_sales_col = find_metric_col(sp_df, ['Sales'])
    sb_sales_col = find_metric_col(sb_df, ['Sales'])
    biz_sales_col = find_metric_col(biz_df, ['Sales', 'Revenue'])
    biz_title_col = find_metric_col(biz_df, ['Title', 'Product Name'])

    # 3. Aggregate Ad Metrics by Brand
    sp_df['Brand'] = sp_df['Campaign Name'].apply(get_brand_from_name)
    sb_df['Brand'] = sb_df['Campaign Name'].apply(get_brand_from_name)

    ad_agg = {
        'Spend': 'sum',
        'Clicks': 'sum',
        'Impressions': 'sum'
    }

    sp_grouped = sp_df.groupby('Brand').agg({**ad_agg, sp_sales_col: 'sum'}).rename(columns={sp_sales_col: 'Ad Sales'})
    sb_grouped = sb_df.groupby('Brand').agg({**ad_agg, sb_sales_col: 'sum'}).rename(columns={sb_sales_col: 'Ad Sales'})
    
    # Merge SP and SB
    total_ads = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    # 4. Aggregate Business Metrics by Brand
    biz_df['Brand'] = biz_df[biz_title_col].apply(get_brand_from_name)
    total_biz = biz_df.groupby('Brand')[biz_sales_col].sum().reset_index().rename(columns={biz_sales_col: 'Total Sales'})

    # 5. Combine and Calculate Audit Metrics
    final_df = pd.merge(total_ads, total_biz, on='Brand', how='outer').fillna(0)
    
    # Filter for known brands only
    final_df = final_df[final_df['Brand'].isin(BRAND_MAP.values())]

    def calc_metrics(df):
        df['Organic Sales'] = df['Total Sales'] - df['Ad Sales']
        df['Ad Contrib %'] = (df['Ad Sales'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
        df['Organic Contrib %'] = (df['Organic Sales'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
        df['ROAS'] = (df['Ad Sales'] / df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
        df['ACOS'] = (df['Spend'] / df['Ad Sales']).replace([np.inf, -np.inf], 0).fillna(0)
        df['TACOS'] = (df['Spend'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
        df['CTR'] = (df['Clicks'] / df['Impressions']).replace([np.inf, -np.inf], 0).fillna(0)
        df['CPC'] = (df['Spend'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
        return df

    final_df = calc_metrics(final_df)

    # UI Structure
    tabs = st.tabs(["🌍 Portfolio Overview"] + list(BRAND_MAP.values()))

    # Tab 1: Overall Summary
    with tabs[0]:
        st.subheader("Combined Portfolio Metrics")
        portfolio_totals = final_df.select_dtypes(include=[np.number]).sum()
        
        # Calculate rates for portfolio
        p_roas = portfolio_totals['Ad Sales'] / portfolio_totals['Spend']
        p_tacos = portfolio_totals['Spend'] / portfolio_totals['Total Sales']
        p_ad_contrib = portfolio_totals['Ad Sales'] / portfolio_totals['Total Sales']

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Sales", f"AED {portfolio_totals['Total Sales']:,.2f}")
        c2.metric("Portfolio ROAS", f"{p_roas:.2f}")
        c3.metric("Avg TACOS", f"{p_tacos:.1%}")
        c4.metric("Ad Contribution", f"{p_ad_contrib:.1%}")

        st.divider()
        st.dataframe(final_df.sort_values(by='Total Sales', ascending=False), hide_index=True, use_container_width=True)

    # Brand Tabs
    for i, brand_name in enumerate(BRAND_MAP.values()):
        with tabs[i+1]:
            b_data = final_df[final_df['Brand'] == brand_name]
            if not b_data.empty:
                row = b_data.iloc[0]
                st.subheader(f"Metrics for {brand_name}")
                
                # Metric Cards
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Overall Sales", f"{row['Total Sales']:,.2f}")
                m2.metric("Ad Sales", f"{row['Ad Sales']:,.2f}")
                m3.metric("Organic Sales", f"{row['Organic Sales']:,.2f}")
                m4.metric("Ad Contribution", f"{row['Ad Contrib %']:.1%}")

                m5, m6, m7, m8 = st.columns(4)
                m5.metric("ROAS", f"{row['ROAS']:.2f}")
                m6.metric("ACOS", f"{row['ACOS']:.1%}")
                m7.metric("TACOS", f"{row['TACOS']:.1%}")
                m8.metric("CPC", f"{row['CPC']:.2f}")

                st.divider()
                st.write("### Brand Data Summary")
                st.table(b_data)
            else:
                st.warning(f"No data found for {brand_name}")

    # Export
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='PORTFOLIO_OVERVIEW', index=False)
        for brand in BRAND_MAP.values():
            final_df[final_df['Brand'] == brand].to_excel(writer, sheet_name=brand[:31], index=False)
    st.sidebar.download_button("📥 Download Audit Report", data=output.getvalue(), file_name="Amazon_Portfolio_Audit.xlsx", use_container_width=True)

else:
    st.info("Please upload SP Search Term, SB Search Term, and Business reports to generate the overview.")
