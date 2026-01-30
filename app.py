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
    """Clean currency strings and non-breaking spaces to return pure numbers."""
    if isinstance(val, str):
        cleaned = val.replace('AED', '').replace('$', '').replace('\xa0', '').replace(',', '').strip()
        try: return pd.to_numeric(cleaned)
        except: return val
    return val

def get_brand_robust(name):
    """Maps campaign or product names to brands using prefixes and full titles."""
    if pd.isna(name): return "Unmapped"
    n = str(name).upper().replace('’', "'").replace('LAVENIR', "L'AVENIR").strip()
    for prefix, full_name in BRAND_MAP.items():
        fn = full_name.upper().replace('’', "'")
        if any(n.startswith(f"{prefix}{sep}") for sep in ["_", " ", "-", " |", " -"]):
            return full_name
        if fn in n or prefix in n.split():
            return full_name
    return "Unmapped"

def find_robust_col(df, keywords, exclude=['acos', 'roas', 'cpc', 'ctr', 'rate']):
    """Finds metric columns while avoiding ratio/percentage columns."""
    for col in df.columns:
        col_clean = str(col).strip().lower()
        if any(kw.lower() in col_clean for kw in keywords):
            if not any(ex.lower() in col_clean for ex in exclude):
                return col
    return None

def calculate_rates(df):
    """Universal calculation for CTR, CVR, ROAS, and ACOS."""
    df['CTR'] = (df['Clicks'] / df['Impressions']).replace([np.inf, -np.inf], 0).fillna(0)
    df['CVR'] = (df['Orders'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
    df['ROAS'] = (df['Ad Sales'] / df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
    df['ACOS'] = (df['Spend'] / df['Ad Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    df['TACOS'] = (df['Spend'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    return df

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
        for col in df.columns:
            if not any(x in col.lower() for x in ['name', 'title', 'term', 'targeting', 'match', 'brand']):
                df[col] = df[col].apply(clean_numeric)
        return df

    sp_df, sb_df, biz_df = load_and_process(sp_file), load_and_process(sb_file), load_and_process(biz_file)

    # Column Detection
    sp_sales_col = find_robust_col(sp_df, ['Sales'])
    sb_sales_col = find_robust_col(sb_df, ['Sales'])
    sp_orders_col = find_robust_col(sp_df, ['Orders'])
    sb_orders_col = find_robust_col(sb_df, ['Orders'])
    biz_sales_col = find_robust_col(biz_df, ['Ordered Product Sales', 'Sales'])
    biz_title_col = find_robust_col(biz_df, ['Title'])
    search_col = find_robust_col(sp_df, ['Customer Search Term', 'Search Term'])

    # Map Brands
    sp_df['Brand'] = sp_df['Campaign Name'].apply(get_brand_robust)
    sb_df['Brand'] = sb_df['Campaign Name'].apply(get_brand_robust)
    biz_df['Brand'] = biz_df[biz_title_col].apply(get_brand_robust)

    # Aggregate Ads (SP + SB)
    metrics = {'Spend': 'sum', 'Clicks': 'sum', 'Impressions': 'sum'}
    sp_grouped = sp_df.groupby('Brand').agg({**metrics, sp_sales_col: 'sum', sp_orders_col: 'sum'}).rename(columns={sp_sales_col: 'Ad Sales', sp_orders_col: 'Orders'})
    sb_grouped = sb_df.groupby('Brand').agg({**metrics, sb_sales_col: 'sum', sb_orders_col: 'sum'}).rename(columns={sb_sales_col: 'Ad Sales', sb_orders_col: 'Orders'})
    total_ads = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    # Aggregate Business
    total_biz = biz_df.groupby('Brand')[biz_sales_col].sum().reset_index().rename(columns={biz_sales_col: 'Total Sales'})

    # Merge & Final Table
    final_df = pd.merge(total_ads, total_biz, on='Brand', how='outer').fillna(0)
    final_df = calculate_rates(final_df[final_df['Brand'] != "Unmapped"])

    # UI Construction
    tabs = st.tabs(["🌍 Portfolio Overview"] + sorted(list(BRAND_MAP.values())))

    with tabs[0]:
        st.subheader("Global Portfolio Overview")
        t = final_df.select_dtypes(include=[np.number]).sum()
        # Portfolio Rates
        p_ctr = t['Clicks'] / t['Impressions'] if t['Impressions'] > 0 else 0
        p_cvr = t['Orders'] / t['Clicks'] if t['Clicks'] > 0 else 0
        p_roas = t['Ad Sales'] / t['Spend'] if t['Spend'] > 0 else 0
        p_acos = t['Spend'] / t['Ad Sales'] if t['Ad Sales'] > 0 else 0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total Sales", f"{t['Total Sales']:,.2f}")
        c2.metric("Imp", f"{int(t['Impressions']):,}")
        c3.metric("Clicks", f"{int(t['Clicks']):,}")
        c4.metric("ROAS", f"{p_roas:.2f}")
        c5.metric("CTR", f"{p_ctr:.2%}")
        c6.metric("CVR", f"{p_cvr:.2%}")
        
        st.divider()
        st.dataframe(final_df.sort_values(by='Total Sales', ascending=False), hide_index=True, use_container_width=True)

    for i, brand_name in enumerate(sorted(BRAND_MAP.values())):
        with tabs[i+1]:
            b_row = final_df[final_df['Brand'] == brand_name]
            if not b_row.empty:
                r = b_row.iloc[0]
                st.subheader(f"Metrics: {brand_name}")
                k1, k2, k3, k4, k5, k6 = st.columns(6)
                k1.metric("Overall Sales", f"{r['Total Sales']:,.2f}")
                k2.metric("Imp", f"{int(r['Impressions']):,}")
                k3.metric("Clicks", f"{int(r['Clicks']):,}")
                k4.metric("ROAS", f"{r['ROAS']:.2f}")
                k5.metric("CTR", f"{r['CTR']:.2%}")
                k6.metric("CVR", f"{r['CVR']:.2%}")
                
                st.divider()
                st.subheader("Campaign & Search Term Performance")
                # Combine Search Term Data for this brand
                b_sp = sp_df[sp_df['Brand'] == brand_name][['Campaign Name', search_col, 'Impressions', 'Clicks', 'Spend', sp_sales_col, sp_orders_col]]
                b_sp.rename(columns={sp_sales_col: 'Sales', sp_orders_col: 'Orders'}, inplace=True)
                
                b_sb = sb_df[sb_df['Brand'] == brand_name][['Campaign Name', search_col, 'Impressions', 'Clicks', 'Spend', sb_sales_col, sb_orders_col]]
                b_sb.rename(columns={sb_sales_col: 'Sales', sb_orders_col: 'Orders'}, inplace=True)
                
                b_detail = pd.concat([b_sp, b_sb]).sort_values(by='Sales', ascending=False)
                st.dataframe(b_detail, use_container_width=True, hide_index=True)
            else:
                st.warning(f"No data detected for {brand_name}.")

    # Export
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='PORTFOLIO_AUDIT', index=False)
    st.sidebar.download_button("📥 Download Master Audit Report", data=output.getvalue(), file_name="Amazon_Portfolio_Audit.xlsx", use_container_width=True)
else:
    st.info("Upload SP, SB, and Business reports to view the combined audit and search term drilldown.")
