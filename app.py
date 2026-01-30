import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Amazon Historical Performance", page_icon="📊", layout="wide")

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
    """Safely converts currency strings to floats for math operations."""
    if isinstance(val, str):
        cleaned = val.replace('AED', '').replace('$', '').replace('\xa0', '').replace(',', '').strip()
        try:
            return pd.to_numeric(cleaned)
        except:
            return 0.0
    return val if isinstance(val, (int, float)) else 0.0

def get_brand_from_name(name):
    """Maps campaign or product names to brands using prefixes."""
    if pd.isna(name): return "Unmapped"
    name_upper = str(name).upper().strip()
    for prefix, full_name in BRAND_MAP.items():
        if any(sep in name_upper for sep in [f"{prefix}_", f"{prefix} ", f"{prefix}-", f"{prefix} |"]):
            return full_name
    for prefix, full_name in BRAND_MAP.items():
        if prefix in name_upper:
            return full_name
    return "Unmapped"

def find_robust_col(df, keywords, exclude=['acos', 'roas']):
    """Finds a column name regardless of case or hidden spaces."""
    for col in df.columns:
        col_clean = str(col).strip().lower()
        if any(kw.lower() in col_clean for kw in keywords):
            if not any(ex.lower() in col_clean for ex in exclude):
                return col
    return None

st.title("📊 Amazon Portfolio Historical Overview")
st.info("Verified Audit: Sponsored Products + Sponsored Brands + Business Report")

st.sidebar.header("Upload Files")
sp_file = st.sidebar.file_uploader("1. Sponsored Products Report", type=["csv", "xlsx"])
sb_file = st.sidebar.file_uploader("2. Sponsored Brands Report", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("3. Business Report (Total Sales)", type=["csv", "xlsx"])

if sp_file and sb_file and biz_file:
    def load_clean_df(file):
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        # Apply cleaning to all columns to ensure numbers are math-ready
        df = df.applymap(clean_numeric) if hasattr(df, 'applymap') else df.map(clean_numeric)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    sp_df = load_clean_df(sp_file)
    sb_df = load_clean_df(sb_file)
    biz_df = load_clean_df(biz_file)

    # Dynamic Column Mapping based on File Test
    sp_camp_col = find_robust_col(sp_df, ['Campaign Name', 'Campaign'])
    sb_camp_col = find_robust_col(sb_df, ['Campaign Name', 'Campaign'])
    sp_sales_col = find_robust_col(sp_df, ['Sales'], exclude=['acos', 'roas', 'cpc', 'ctr'])
    sb_sales_col = find_robust_col(sb_df, ['Sales'], exclude=['acos', 'roas', 'cpc', 'ctr'])
    biz_sales_col = find_robust_col(biz_df, ['Sales', 'Revenue'], exclude=['acos', 'roas'])
    biz_title_col = find_robust_col(biz_df, ['Title', 'Product Name'])

    # Aggregate Ads (SP + SB)
    sp_df['Brand'] = sp_df[sp_camp_col].apply(get_brand_from_name) if sp_camp_col else "Unmapped"
    sb_df['Brand'] = sb_df[sb_camp_col].apply(get_brand_from_name) if sb_camp_col else "Unmapped"

    ad_metrics = {'Spend': 'sum', 'Clicks': 'sum', 'Impressions': 'sum'}
    sp_grouped = sp_df.groupby('Brand').agg({**ad_metrics, sp_sales_col: 'sum'}).rename(columns={sp_sales_col: 'Ad Sales'})
    sb_grouped = sb_df.groupby('Brand').agg({**ad_metrics, sb_sales_col: 'sum'}).rename(columns={sb_sales_col: 'Ad Sales'})
    
    total_ads = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    # Aggregate Business Data
    biz_df['Brand'] = biz_df[biz_title_col].apply(get_brand_from_name) if biz_title_col else "Unmapped"
    total_biz = biz_df.groupby('Brand')[biz_sales_col].sum().reset_index().rename(columns={biz_sales_col: 'Total Sales'})

    # Final Combined DataFrame
    final_df = pd.merge(total_ads, total_biz, on='Brand', how='outer').fillna(0)
    final_df = final_df[final_df['Brand'].isin(BRAND_MAP.values())]

    # Derived Audit Metrics
    final_df['Organic Sales'] = final_df['Total Sales'] - final_df['Ad Sales']
    final_df['ROAS'] = round(final_df['Ad Sales'] / final_df['Spend'], 2).replace([np.inf, -np.inf], 0).fillna(0)
    final_df['TACOS'] = round(final_df['Spend'] / final_df['Total Sales'], 4).replace([np.inf, -np.inf], 0).fillna(0)
    final_df['Ad Contribution'] = round(final_df['Ad Sales'] / final_df['Total Sales'], 4).replace([np.inf, -np.inf], 0).fillna(0)

    # UI Construction
    tabs = st.tabs(["🌍 Portfolio Overview"] + list(BRAND_MAP.values()))

    # Tab 1: Global Portfolio Summary
    with tabs[0]:
        st.subheader("🏆 Portfolio-Wide Performance Metrics")
        t = final_df.select_dtypes(include=[np.number]).sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Sales", f"AED {t['Total Sales']:,.2f}")
        c2.metric("Portfolio ROAS", f"{t['Ad Sales']/t['Spend']:.2f}" if t['Spend']>0 else "0.00")
        c3.metric("Avg TACOS", f"{t['Spend']/t['Total Sales']:.1%}")
        c4.metric("Ad Contribution", f"{t['Ad Sales']/t['Total Sales']:.1%}")
        st.divider()
        st.dataframe(final_df.sort_values(by='Total Sales', ascending=False), hide_index=True, use_container_width=True)

    # Individual Brand Tabs
    for i, brand_name in enumerate(BRAND_MAP.values()):
        with tabs[i+1]:
            row = final_df[final_df['Brand'] == brand_name]
            if not row.empty:
                r = row.iloc[0]
                st.subheader(f"Historical Audit: {brand_name}")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Overall Sales", f"{r['Total Sales']:,.2f}")
                k2.metric("Ad Sales", f"{r['Ad Sales']:,.2f}")
                k3.metric("Organic Sales", f"{r['Organic Sales']:,.2f}")
                k4.metric("Ad Contribution", f"{r['Ad Contribution']:.1%}")
                k5, k6, k7, k8 = st.columns(4)
                k5.metric("ROAS", f"{r['ROAS']:.2f}")
                k6.metric("TACOS", f"{r['TACOS']:.1%}")
                k7.metric("Clicks", f"{int(r['Clicks'])}")
                k8.metric("Impressions", f"{int(r['Impressions'])}")
            else:
                st.warning(f"No relevant data detected for {brand_name}")

    # Export Logic
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='OVERALL_AUDIT', index=False)
        for b in BRAND_MAP.values():
            final_df[final_df['Brand'] == b].to_excel(writer, sheet_name=b[:31], index=False)
    st.sidebar.download_button("📥 Download Master Audit Report", data=output.getvalue(), file_name="Amazon_Historical_Audit.xlsx", use_container_width=True)

else:
    st.info("Upload SP, SB, and Business reports to generate the combined portfolio overview.")
