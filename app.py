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

def get_brand_from_name(name):
    if pd.isna(name): return "Unmapped"
    name_upper = str(name).upper().strip()
    for prefix, full_name in BRAND_MAP.items():
        # Matching prefixes with common separators
        if any(name_upper.startswith(f"{prefix}{sep}") for sep in ["_", " ", "-", " |", " -"]):
            return full_name
    # Fallback search
    for prefix, full_name in BRAND_MAP.items():
        if prefix in name_upper:
            return full_name
    return "Unmapped"

def find_robust_col(df, keywords, exclude=['acos', 'roas', 'cpc', 'ctr']):
    """Finds a column name regardless of case or hidden spaces, avoiding ratio columns."""
    for col in df.columns:
        col_clean = str(col).strip().lower()
        if any(kw.lower() in col_clean for kw in keywords):
            # Ensure we don't pick up ACOS/ROAS columns as 'Sales'
            if not any(ex.lower() in col_clean for ex in exclude):
                return col
    return None

def group_ad_report(df, cols):
    """Safely aggregates metrics only if the columns exist in the dataframe."""
    agg_map = {}
    rename_map = {}
    
    metric_configs = [
        ('spend', 'Spend'),
        ('sales', 'Ad Sales'),
        ('clicks', 'Clicks'),
        ('imps', 'Impressions')
    ]
    
    for key, label in metric_configs:
        col_name = cols.get(key)
        if col_name and col_name in df.columns:
            agg_map[col_name] = 'sum'
            rename_map[col_name] = label
            
    if not agg_map:
        return pd.DataFrame(columns=['Brand', 'Spend', 'Ad Sales', 'Clicks', 'Impressions']).set_index('Brand')
        
    return df.groupby('Brand').agg(agg_map).rename(columns=rename_map)

st.title("📊 Amazon Portfolio Performance Overview")
st.info("Combined Audit: Sponsored Products + Sponsored Brands + Business Report")

st.sidebar.header("Upload Files")
sp_file = st.sidebar.file_uploader("1. Sponsored Products Report", type=["csv", "xlsx"])
sb_file = st.sidebar.file_uploader("2. Sponsored Brands Report", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("3. Business Report (Total Sales)", type=["csv", "xlsx"])

if sp_file and sb_file and biz_file:
    def load_and_clean(file):
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        # Use applymap for older pandas, map for newer
        df = df.applymap(clean_numeric) if hasattr(df, 'applymap') else df.map(clean_numeric)
        df.columns = [str(c).strip() for c in df.columns] 
        return df

    sp_df = load_and_clean(sp_file)
    sb_df = load_and_clean(sb_file)
    biz_df = load_and_clean(biz_file)

    # Robust Column Mapping per report type
    sp_cols = {
        'camp': find_robust_col(sp_df, ['Campaign Name', 'Campaign']),
        'sales': find_robust_col(sp_df, ['Total Sales', 'Sales'], exclude=['acos', 'roas', 'cpc', 'ctr']),
        'spend': find_robust_col(sp_df, ['Spend', 'Cost']),
        'clicks': find_robust_col(sp_df, ['Clicks']),
        'imps': find_robust_col(sp_df, ['Impressions'])
    }
    
    sb_cols = {
        'camp': find_robust_col(sb_df, ['Campaign Name', 'Campaign']),
        'sales': find_robust_col(sb_df, ['Total Sales', 'Sales'], exclude=['acos', 'roas', 'cpc', 'ctr']),
        'spend': find_robust_col(sb_df, ['Spend', 'Cost']),
        'clicks': find_robust_col(sb_df, ['Clicks']),
        'imps': find_robust_col(sb_df, ['Impressions'])
    }

    biz_sales_col = find_robust_col(biz_df, ['Sales', 'Revenue'], exclude=['acos', 'roas'])
    biz_title_col = find_robust_col(biz_df, ['Title', 'Product Name'])

    # Process and Merge Advertising Data
    sp_df['Brand'] = sp_df[sp_cols['camp']].apply(get_brand_from_name) if sp_cols['camp'] else "Unmapped"
    sb_df['Brand'] = sb_df[sb_cols['camp']].apply(get_brand_from_name) if sb_cols['camp'] else "Unmapped"

    sp_grouped = group_ad_report(sp_df, sp_cols)
    sb_grouped = group_ad_report(sb_df, sb_cols)
    total_ads = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    # Process Business Report
    biz_df['Brand'] = biz_df[biz_title_col].apply(get_brand_from_name) if biz_title_col else "Unmapped"
    total_biz = biz_df.groupby('Brand')[biz_sales_col].sum().reset_index().rename(columns={biz_sales_col: 'Total Sales'})

    # Final Consolidated Audit Table
    final_df = pd.merge(total_ads, total_biz, on='Brand', how='outer').fillna(0)
    final_df = final_df[final_df['Brand'].isin(BRAND_MAP.values())]

    # Calculate Performance Ratios
    final_df['Organic Sales'] = final_df['Total Sales'] - final_df['Ad Sales']
    final_df['ROAS'] = (final_df['Ad Sales'] / final_df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
    final_df['TACOS'] = (final_df['Spend'] / final_df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    final_df['Ad Contribution'] = (final_df['Ad Sales'] / final_df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)

    # --- UI Tabs ---
    tabs = st.tabs(["🌍 Portfolio Overview"] + list(BRAND_MAP.values()))

    with tabs[0]:
        st.subheader("Global Portfolio Metrics")
        totals = final_df.select_dtypes(include=[np.number]).sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Platform Sales", f"AED {totals['Total Sales']:,.2f}")
        c2.metric("Portfolio Ad Spend", f"AED {totals['Spend']:,.2f}")
        c3.metric("Portfolio ROAS", f"{totals['Ad Sales']/totals['Spend']:.2f}" if totals['Spend'] > 0 else "0.00")
        c4.metric("Avg TACOS", f"{totals['Spend']/totals['Total Sales']:.1%}")
        
        st.divider()
        st.dataframe(final_df.sort_values(by='Total Sales', ascending=False), hide_index=True, use_container_width=True)

    for i, brand_name in enumerate(BRAND_MAP.values()):
        with tabs[i+1]:
            b_row = final_df[final_df['Brand'] == brand_name]
            if not b_row.empty:
                r = b_row.iloc[0]
                st.subheader(f"Brand Metrics: {brand_name}")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Overall Sales", f"{r['Total Sales']:,.2f}")
                k2.metric("Ad Sales", f"{r['Ad Sales']:,.2f}")
                k3.metric("Organic Sales", f"{r['Organic Sales']:,.2f}")
                k4.metric("Ad Contribution", f"{r['Ad Contribution']:.1%}")
                
                k5, k6, k7, k8 = st.columns(4)
                k5.metric("ROAS", f"{r['ROAS']:.2f}")
                k6.metric("TACOS", f"{r['TACOS']:.1%}")
                k7.metric("CPC", f"{r['Spend']/r['Clicks']:.2f}" if r['Clicks'] > 0 else "0.00")
                k8.metric("CTR", f"{r['Clicks']/r['Impressions']:.2%}" if r['Impressions'] > 0 else "0.00")
            else:
                st.warning(f"No data available for {brand_name}")

    # Export Report
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='PORTFOLIO_AUDIT', index=False)
        for b in BRAND_MAP.values():
            final_df[final_df['Brand'] == b].to_excel(writer, sheet_name=b[:31], index=False)
    st.sidebar.download_button("📥 Download Master Report", data=output.getvalue(), file_name="Amazon_Portfolio_Audit.xlsx", use_container_width=True)

else:
    st.info("Upload SP Search Term, SB Search Term, and Business reports to generate the overview.")
