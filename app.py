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
    """Removes AED/symbols and keeps pure numbers for calculation."""
    if isinstance(val, str):
        # Handle AED, smart spaces, and commas
        cleaned = val.replace('AED', '').replace('$', '').replace('\xa0', '').replace(',', '').strip()
        try: return pd.to_numeric(cleaned)
        except: return val
    return val

def get_brand_robust(name):
    """Resilient mapping for both campaign prefixes and full brand titles."""
    if pd.isna(name): return "Unmapped"
    # Normalize: Remove smart quotes and extra spaces
    n = str(name).upper().replace('’', "'").replace('LAVENIR', "L'AVENIR").strip()
    
    for prefix, full_name in BRAND_MAP.items():
        fn = full_name.upper().replace('’', "'")
        # Match Prefix (e.g., CPT | or MA _)
        if any(n.startswith(f"{prefix}{sep}") for sep in ["_", " ", "-", " |", " -"]):
            return full_name
        # Match Full Name in Title (e.g., CP Trendies Makeup Kit)
        if fn in n or prefix in n.split():
            return full_name
            
    return "Unmapped"

def find_robust_col(df, keywords, exclude=['acos', 'roas', 'cpc', 'ctr']):
    """Dynamically locates metric columns while avoiding ratios."""
    for col in df.columns:
        col_clean = str(col).strip().lower()
        if any(kw.lower() in col_clean for kw in keywords):
            if not any(ex.lower() in col_clean for ex in exclude):
                return col
    return None

st.title("📊 Amazon Portfolio Performance Overview")
st.info("Verified Audit: Consolidating SP + SB + Business Metrics")

st.sidebar.header("Upload Files")
sp_file = st.sidebar.file_uploader("1. Sponsored Products Report", type=["csv", "xlsx"])
sb_file = st.sidebar.file_uploader("2. Sponsored Brands Report", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("3. Business Report (Total Sales)", type=["csv", "xlsx"])

if sp_file and sb_file and biz_file:
    def load_and_process(file):
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        df.columns = [str(c).strip() for c in df.columns]
        # Only clean columns that are NOT identifying strings
        for col in df.columns:
            if not any(x in col.lower() for x in ['name', 'title', 'term', 'targeting', 'match', 'brand']):
                df[col] = df[col].apply(clean_numeric)
        return df

    sp_df, sb_df, biz_df = load_and_process(sp_file), load_and_process(sb_file), load_and_process(biz_file)

    # Dynamic Column Detection
    sp_sales_col = find_robust_col(sp_df, ['Sales'])
    sb_sales_col = find_robust_col(sb_df, ['Sales'])
    biz_sales_col = find_robust_col(biz_df, ['Ordered Product Sales', 'Sales'])
    biz_title_col = find_robust_col(biz_df, ['Title'])

    # Map Brands
    sp_df['Brand'] = sp_df['Campaign Name'].apply(get_brand_robust)
    sb_df['Brand'] = sb_df['Campaign Name'].apply(get_brand_robust)
    biz_df['Brand'] = biz_df[biz_title_col].apply(get_brand_robust)

    # Aggregate Ads (SP + SB)
    metrics = {'Spend': 'sum', 'Clicks': 'sum', 'Impressions': 'sum'}
    sp_grouped = sp_df.groupby('Brand').agg({**metrics, sp_sales_col: 'sum'}).rename(columns={sp_sales_col: 'Ad Sales'})
    sb_grouped = sb_df.groupby('Brand').agg({**metrics, sb_sales_col: 'sum'}).rename(columns={sb_sales_col: 'Ad Sales'})
    total_ads = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    # Aggregate Business
    total_biz = biz_df.groupby('Brand')[biz_sales_col].sum().reset_index().rename(columns={biz_sales_col: 'Total Sales'})

    # Final Combined DataFrame
    final_df = pd.merge(total_ads, total_biz, on='Brand', how='outer').fillna(0)
    final_df = final_df[final_df['Brand'] != "Unmapped"]

    # Calculate Rates
    final_df['Organic Sales'] = final_df['Total Sales'] - final_df['Ad Sales']
    final_df['ROAS'] = round(final_df['Ad Sales'] / final_df['Spend'], 2).replace([np.inf, -np.inf], 0).fillna(0)
    final_df['TACOS'] = round(final_df['Spend'] / final_df['Total Sales'], 4).replace([np.inf, -np.inf], 0).fillna(0)
    final_df['Ad Contribution'] = round(final_df['Ad Sales'] / final_df['Total Sales'], 4).replace([np.inf, -np.inf], 0).fillna(0)

    # UI Construction
    tabs = st.tabs(["🌍 Portfolio Overview"] + sorted(list(BRAND_MAP.values())))

    with tabs[0]:
        st.subheader("Global Portfolio Overview")
        t = final_df.select_dtypes(include=[np.number]).sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Sales", f"{t['Total Sales']:,.2f}")
        c2.metric("Portfolio Spend", f"{t['Spend']:,.2f}")
        c3.metric("Portfolio ROAS", f"{t['Ad Sales']/t['Spend']:.2f}" if t['Spend'] > 0 else "0.00")
        c4.metric("Avg TACOS", f"{t['Spend']/t['Total Sales']:.1%}")
        st.divider()
        st.dataframe(final_df.sort_values(by='Total Sales', ascending=False), hide_index=True, use_container_width=True)

    for i, brand_name in enumerate(sorted(BRAND_MAP.values())):
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
                st.warning(f"No data detected for {brand_name}. Please verify campaign naming.")

    # Export
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='PORTFOLIO_AUDIT', index=False)
    st.sidebar.download_button("📥 Download Audit Report", data=output.getvalue(), file_name="Amazon_Portfolio_Audit.xlsx", use_container_width=True)
else:
    st.info("Upload SP, SB, and Business reports to view the combined historical overview.")
