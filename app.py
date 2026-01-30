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
        # Removes AED, symbols, non-breaking spaces, and commas
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

st.title("📊 Amazon Portfolio Performance Audit")
st.info("Consolidated Analysis: Sponsored Products + Sponsored Brands + Business Report")

st.sidebar.header("Upload Files")
sp_file = st.sidebar.file_uploader("1. Sponsored Products Report", type=["csv", "xlsx"])
sb_file = st.sidebar.file_uploader("2. Sponsored Brands Report", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("3. Business Report (Total Sales)", type=["csv", "xlsx"])

if sp_file and sb_file and biz_file:
    def load_and_standardize(file):
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        df.columns = [str(c).strip() for c in df.columns]
        # Clean numeric values only for columns that shouldn't be text
        for col in df.columns:
            if not any(x in col.lower() for x in ['name', 'title', 'term', 'targeting', 'match', 'brand', 'asin']):
                df[col] = df[col].apply(clean_numeric)
        return df

    sp_df, sb_df, biz_df = load_and_standardize(sp_file), load_and_standardize(sb_file), load_and_standardize(biz_file)

    # Robust Mapping
    sp_df['Brand'] = sp_df['Campaign Name'].apply(get_brand_robust)
    sb_df['Brand'] = sb_df['Campaign Name'].apply(get_brand_robust)
    title_col = find_robust_col(biz_df, ['Title', 'Product Name'])
    biz_df['Brand'] = biz_df[title_col].apply(get_brand_robust)

    # Column Detection
    sp_sales_col = find_robust_col(sp_df, ['Sales'])
    sb_sales_col = find_robust_col(sb_df, ['Sales'])
    sp_orders_col = find_robust_col(sp_df, ['Orders'])
    sb_orders_col = find_robust_col(sb_df, ['Orders'])
    biz_sales_col = find_robust_col(biz_df, ['Ordered Product Sales', 'Sales'])
    search_col = find_robust_col(sp_df, ['Customer Search Term', 'Search Term'])

    # Aggregate Ads
    metrics_map = {'Spend': 'sum', 'Clicks': 'sum', 'Impressions': 'sum'}
    sp_grouped = sp_df.groupby('Brand').agg({**metrics_map, sp_sales_col: 'sum', sp_orders_col: 'sum'}).rename(columns={sp_sales_col: 'Ad Sales', sp_orders_col: 'Orders'})
    sb_grouped = sb_df.groupby('Brand').agg({**metrics_map, sb_sales_col: 'sum', sb_orders_col: 'sum'}).rename(columns={sb_sales_col: 'Ad Sales', sb_orders_col: 'Orders'})
    total_ads = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    # Aggregate Business
    total_biz = biz_df.groupby('Brand')[biz_sales_col].sum().reset_index().rename(columns={biz_sales_col: 'Total Sales'})

    # Final Audit Table
    final_df = calculate_audit_kpis(pd.merge(total_ads, total_biz, on='Brand', how='outer').fillna(0))
    final_df = final_df[final_df['Brand'] != "Unmapped"]

    # --- UI STRUCTURE ---
    tabs = st.tabs(["🌍 Portfolio Overview"] + sorted(list(BRAND_MAP.values())))

    def display_metrics(data_row, title=""):
        st.subheader(f"{title} - Performance Mix")
        
        col_p, col_o = st.columns(2)
        
        with col_p:
            st.markdown("#### 🚀 Paid Advertising Metrics")
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Ad Sales", f"{data_row['Ad Sales']:,.2f}")
            p2.metric("Spend", f"{data_row['Spend']:,.2f}")
            p3.metric("ROAS", f"{data_row['ROAS']:.2f}")
            p4.metric("ACOS", f"{data_row['ACOS']:.1%}")
            
            p5, p6, p7, p8 = st.columns(4)
            p5.metric("Impressions", f"{int(data_row['Impressions']):,}")
            p6.metric("Clicks", f"{int(data_row['Clicks']):,}")
            p7.metric("CTR", f"{data_row['CTR']:.2%}")
            p8.metric("CVR", f"{data_row['CVR']:.2%}")

        with col_o:
            st.markdown("#### 🌱 Organic & Total Metrics")
            o1, o2, o3, o4 = st.columns(4)
            o1.metric("Total Sales", f"{data_row['Total Sales']:,.2f}")
            o2.metric("Organic Sales", f"{data_row['Organic Sales']:,.2f}")
            o3.metric("Paid Contrib", f"{data_row['Paid Contrib']:.1%}")
            o4.metric("Organic Contrib", f"{data_row['Organic Contrib']:.1%}")
            
            o5 = st.columns(1)[0]
            o5.metric("TACOS (Total ACOS)", f"{data_row['TACOS']:.1%}", help="Total Advertising Cost of Sales")

    with tabs[0]:
        t_row = final_df.select_dtypes(include=[np.number]).sum()
        # Portfolio average rates
        t_row['CTR'] = t_row['Clicks'] / t_row['Impressions'] if t_row['Impressions'] > 0 else 0
        t_row['CVR'] = t_row['Orders'] / t_row['Clicks'] if t_row['Clicks'] > 0 else 0
        t_row['ROAS'] = t_row['Ad Sales'] / t_row['Spend'] if t_row['Spend'] > 0 else 0
        t_row['ACOS'] = t_row['Spend'] / t_row['Ad Sales'] if t_row['Ad Sales'] > 0 else 0
        t_row['TACOS'] = t_row['Spend'] / t_row['Total Sales'] if t_row['Total Sales'] > 0 else 0
        t_row['Paid Contrib'] = t_row['Ad Sales'] / t_row['Total Sales'] if t_row['Total Sales'] > 0 else 0
        t_row['Organic Contrib'] = (t_row['Total Sales'] - t_row['Ad Sales']) / t_row['Total Sales'] if t_row['Total Sales'] > 0 else 0
        t_row['Organic Sales'] = t_row['Total Sales'] - t_row['Ad Sales']
        
        display_metrics(t_row, "Global Portfolio")
        st.divider()
        st.subheader("Brand-Wise Breakdown")
        st.dataframe(final_df.sort_values(by='Total Sales', ascending=False), hide_index=True, use_container_width=True)

    for i, brand_name in enumerate(sorted(BRAND_MAP.values())):
        with tabs[i+1]:
            b_data = final_df[final_df['Brand'] == brand_name]
            if not b_data.empty:
                r = b_data.iloc[0]
                display_metrics(r, brand_name)
                
                st.divider()
                st.subheader("📊 Campaign & Search Term Drilldown")
                b_sp = sp_df[sp_df['Brand'] == brand_name][['Campaign Name', search_col, 'Impressions', 'Clicks', 'Spend', sp_sales_col, sp_orders_col]]
                b_sp.rename(columns={sp_sales_col: 'Sales', sp_orders_col: 'Orders'}, inplace=True)
                b_sb = sb_df[sb_df['Brand'] == brand_name][['Campaign Name', search_col, 'Impressions', 'Clicks', 'Spend', sb_sales_col, sb_orders_col]]
                b_sb.rename(columns={sb_sales_col: 'Sales', sb_orders_col: 'Orders'}, inplace=True)
                
                drill_df = pd.concat([b_sp, b_sb]).sort_values(by='Sales', ascending=False)
                st.dataframe(drill_df, use_container_width=True, hide_index=True)
            else:
                st.warning(f"No relevant data found for {brand_name}.")

    # Export
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='PORTFOLIO_AUDIT', index=False)
    st.sidebar.download_button("📥 Download Master Report", data=output.getvalue(), file_name="Amazon_Portfolio_Audit.xlsx", use_container_width=True)
else:
    st.info("Upload SP, SB, and Business reports to generate the Performance Audit.")
