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
    """Safely converts currency strings to pure numbers for mathematical analysis."""
    if isinstance(val, str):
        # Removes AED, commas, and non-breaking spaces
        cleaned = val.replace('AED', '').replace('$', '').replace('\xa0', '').replace(',', '').strip()
        try:
            return pd.to_numeric(cleaned)
        except:
            return val
    return val

def get_brand_robust(name):
    """Resilient mapping for both campaign prefixes and long product titles."""
    if pd.isna(name): return "Unmapped"
    n = str(name).upper().replace('’', "'").replace('LAVENIR', "L'AVENIR").strip()
    
    # 1. Match Prefix (Campaign Names)
    for prefix, full_name in BRAND_MAP.items():
        if any(n.startswith(f"{prefix}{sep}") for sep in ["_", " ", "-", " |", " -"]):
            return full_name
            
    # 2. Match Full Name (Product Titles)
    for prefix, full_name in BRAND_MAP.items():
        if full_name.upper().replace('’', "'") in n:
            return full_name
            
    # 3. Last Resort: Individual Word match
    words = n.split()
    for prefix, full_name in BRAND_MAP.items():
        if prefix in words:
            return full_name
            
    return "Unmapped"

def find_robust_col(df, keywords, exclude=['acos', 'roas', 'cpc', 'ctr', 'rate']):
    """Dynamically finds metric columns while avoiding calculated ratios."""
    for col in df.columns:
        col_clean = str(col).strip().lower()
        if any(kw.lower() in col_clean for kw in keywords):
            if not any(ex.lower() in col_clean for ex in exclude):
                return col
    return None

def calculate_audit_kpis(df):
    """Calculates all performance ratios for ads and organic contribution."""
    df['CTR'] = (df['Clicks'] / df['Impressions']).replace([np.inf, -np.inf], 0).fillna(0)
    df['CVR'] = (df['Orders'] / df['Clicks']).replace([np.inf, -np.inf], 0).fillna(0)
    df['ROAS'] = (df['Ad Sales'] / df['Spend']).replace([np.inf, -np.inf], 0).fillna(0)
    df['ACOS'] = (df['Spend'] / df['Ad Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    df['TACOS'] = (df['Spend'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    df['Organic Sales'] = df['Total Sales'] - df['Ad Sales']
    df['Paid Contrib'] = (df['Ad Sales'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    df['Organic Contrib'] = (df['Organic Sales'] / df['Total Sales']).replace([np.inf, -np.inf], 0).fillna(0)
    return df

st.title("📊 Amazon Portfolio Audit & Drilldown")
st.info("Combined Historical View: SP + SB + Business Metrics")

st.sidebar.header("Upload Files")
sp_file = st.sidebar.file_uploader("1. Sponsored Products Report", type=["csv", "xlsx"])
sb_file = st.sidebar.file_uploader("2. Sponsored Brands Report", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("3. Business Report (Total Sales)", type=["csv", "xlsx"])

if sp_file and sb_file and biz_file:
    def load_and_standardize(file):
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        df.columns = [str(c).strip() for c in df.columns]
        # Clean numeric columns only (not Titles or Campaign Names)
        for col in df.columns:
            if not any(x in col.lower() for x in ['name', 'title', 'term', 'targeting', 'match', 'brand', 'asin']):
                df[col] = df[col].apply(clean_numeric)
        return df

    sp_df, sb_df, biz_df = load_and_standardize(sp_file), load_and_standardize(sb_file), load_and_standardize(biz_file)

    # 1. Map Brands
    sp_df['Brand'] = sp_df['Campaign Name'].apply(get_brand_robust)
    sb_df['Brand'] = sb_df['Campaign Name'].apply(get_brand_robust)
    
    title_col = find_robust_col(biz_df, ['Title', 'Product Name'])
    biz_df['Brand'] = biz_df[title_col].apply(get_brand_robust)

    # 2. Identify Sales/Metric Columns
    sp_sales_col = find_robust_col(sp_df, ['Sales'])
    sb_sales_col = find_robust_col(sb_df, ['Sales'])
    sp_orders_col = find_robust_col(sp_df, ['Orders'])
    sb_orders_col = find_robust_col(sb_df, ['Orders'])
    biz_sales_col = find_robust_col(biz_df, ['Ordered Product Sales', 'Sales'])
    search_col = find_robust_col(sp_df, ['Customer Search Term', 'Search Term'])

    # 3. Aggregate Metrics
    metrics = {'Spend': 'sum', 'Clicks': 'sum', 'Impressions': 'sum'}
    sp_grouped = sp_df.groupby('Brand').agg({**metrics, sp_sales_col: 'sum', sp_orders_col: 'sum'}).rename(columns={sp_sales_col: 'Ad Sales', sp_orders_col: 'Orders'})
    sb_grouped = sb_df.groupby('Brand').agg({**metrics, sb_sales_col: 'sum', sb_orders_col: 'sum'}).rename(columns={sb_sales_col: 'Ad Sales', sb_orders_col: 'Orders'})
    total_ads = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    total_biz = biz_df.groupby('Brand')[biz_sales_col].sum().reset_index().rename(columns={biz_sales_col: 'Total Sales'})

    # Final Combined DataFrame
    final_df = calculate_audit_kpis(pd.merge(total_ads, total_biz, on='Brand', how='outer').fillna(0))
    final_df = final_df[final_df['Brand'] != "Unmapped"]

    # --- UI LAYOUT ---
    tabs = st.tabs(["🌎 Portfolio Overview"] + sorted(list(BRAND_MAP.values())))

    # Overview Tab
    with tabs[0]:
        st.subheader("Global Portfolio Performance Summary")
        totals = final_df.select_dtypes(include=[np.number]).sum()
        
        # Calculate Platform KPIs
        p_ctr = totals['Clicks'] / totals['Impressions'] if totals['Impressions'] > 0 else 0
        p_cvr = totals['Orders'] / totals['Clicks'] if totals['Clicks'] > 0 else 0
        p_roas = totals['Ad Sales'] / totals['Spend'] if totals['Spend'] > 0 else 0
        p_acos = totals['Spend'] / totals['Ad Sales'] if totals['Ad Sales'] > 0 else 0
        p_paid = totals['Ad Sales'] / totals['Total Sales'] if totals['Total Sales'] > 0 else 0
        p_org = (totals['Total Sales'] - totals['Ad Sales']) / totals['Total Sales'] if totals['Total Sales'] > 0 else 0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Total Sales", f"{totals['Total Sales']:,.2f}")
        c2.metric("Ad Sales", f"{totals['Ad Sales']:,.2f}")
        c3.metric("Spend", f"{totals['Spend']:,.2f}")
        c4.metric("ROAS", f"{p_roas:.2f}")
        c5.metric("CTR", f"{p_ctr:.2%}")
        c6.metric("CVR", f"{p_cvr:.2%}")

        st.markdown("#### Contribution & Efficiency")
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Paid Contribution", f"{p_paid:.1%}")
        e2.metric("Organic Contribution", f"{p_org:.1%}")
        e3.metric("ACOS", f"{p_acos:.1%}")
        e4.metric("TACOS", f"{totals['Spend']/totals['Total Sales']:.1%}")

        st.divider()
        st.dataframe(final_df.sort_values(by='Total Sales', ascending=False), hide_index=True, use_container_width=True)

    # Brand-Specific Tabs
    for i, brand_name in enumerate(sorted(BRAND_MAP.values())):
        with tabs[i+1]:
            b_row = final_df[final_df['Brand'] == brand_name]
            if not b_row.empty:
                r = b_row.iloc[0]
                st.subheader(f"Performance: {brand_name}")
                k1, k2, k3, k4, k5, k6 = st.columns(6)
                k1.metric("Total Sales", f"{r['Total Sales']:,.2f}")
                k2.metric("Ad Sales", f"{r['Ad Sales']:,.2f}")
                k3.metric("Organic Sales", f"{r['Organic Sales']:,.2f}")
                k4.metric("ROAS", f"{r['ROAS']:.2f}")
                k5.metric("CTR", f"{r['CTR']:.2%}")
                k6.metric("CVR", f"{r['CVR']:.2%}")
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Paid Contrib", f"{r['Paid Contrib']:.1%}")
                m2.metric("Organic Contrib", f"{r['Organic Contrib']:.1%}")
                m3.metric("ACOS", f"{r['ACOS']:.1%}")
                m4.metric("TACOS", f"{r['TACOS']:.1%}")

                st.divider()
                st.subheader("Granular Campaign & Search Term Performance")
                # Merge Ad Report details
                b_sp = sp_df[sp_df['Brand'] == brand_name][['Campaign Name', search_col, 'Impressions', 'Clicks', 'Spend', sp_sales_col, sp_orders_col]]
                b_sp.rename(columns={sp_sales_col: 'Sales', sp_orders_col: 'Orders'}, inplace=True)
                b_sb = sb_df[sb_df['Brand'] == brand_name][['Campaign Name', search_col, 'Impressions', 'Clicks', 'Spend', sb_sales_col, sb_orders_col]]
                b_sb.rename(columns={sb_sales_col: 'Sales', sb_orders_col: 'Orders'}, inplace=True)
                
                detail = pd.concat([b_sp, b_sb]).sort_values(by='Sales', ascending=False)
                st.dataframe(detail, use_container_width=True, hide_index=True)
            else:
                st.warning(f"No relevant data found for {brand_name}. Please verify report contents.")

    # Export Report
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='PORTFOLIO_AUDIT', index=False)
    st.sidebar.download_button("📥 Download Master Audit Report", data=output.getvalue(), file_name="Amazon_Portfolio_Audit.xlsx", use_container_width=True)

else:
    st.info("Upload SP, SB, and Business reports to generate the performance audit.")
