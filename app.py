import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="PPC & Organic Projections", page_icon="📊", layout="wide")

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
        cleaned = val.replace('AED', '').replace('₹', '').replace('\xa0', '').replace(',', '').strip()
        try: return pd.to_numeric(cleaned)
        except: return val
    return val

def get_brand(campaign_name):
    if pd.isna(campaign_name): return "Unmapped"
    name = str(campaign_name).upper().strip()
    for prefix, full_name in BRAND_MAP.items():
        if any(name.startswith(f"{prefix}{sep}") for sep in ["_", " ", "-", " |", " -"]):
            return full_name
    for prefix, full_name in BRAND_MAP.items():
        if prefix in name:
            return full_name
    return "Unmapped"

def find_col(df, primary_keywords, exclude_keywords=[]):
    """Fuzzy search for column names while excluding irrelevant ones like ACOS."""
    cols = df.columns
    # First pass: look for exact-ish matches
    for col in cols:
        col_lower = col.lower()
        if any(pk.lower() in col_lower for pk in primary_keywords):
            if not any(ek.lower() in col_lower for ek in exclude_keywords):
                return col
    return None

st.title("📊 Amazon Master Projections")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("🚀 Growth Settings")
roas_uplift = st.sidebar.slider("ROAS Uplift (%)", 0, 100, 20) / 100
organic_lift = st.sidebar.slider("Organic Lift (%)", 0, 50, 5) / 100
spend_growth = st.sidebar.slider("Spend Growth (%)", -50, 200, 0) / 100

st.sidebar.divider()
st.sidebar.header("Upload Files")
sp_file = st.sidebar.file_uploader("1. Sponsored Products Report", type=["csv", "xlsx"])
sb_file = st.sidebar.file_uploader("2. Sponsored Brands Report", type=["csv", "xlsx"])
biz_file = st.sidebar.file_uploader("3. Business Report (Total Sales)", type=["csv", "xlsx"])

if sp_file and sb_file and biz_file:
    def load_df(file):
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
        df = df.applymap(clean_numeric) # Compatibility fix
        df.columns = [str(c).strip() for c in df.columns] 
        return df

    sp_df = load_df(sp_file)
    sb_df = load_df(sb_file)
    biz_df = load_df(biz_file)
    
    # Standardizing Columns
    metrics_map = {
        'Spend': ['Spend', 'Cost'],
        'Clicks': ['Clicks'],
        'Impressions': ['Impressions', 'Imps'],
        'Sales': ['Total Sales', 'Sales', 'Revenue']
    }
    exclude_for_sales = ['ACOS', 'ROAS', 'CPC', 'CTR']

    # Identify dynamic columns
    sp_camp_col = find_col(sp_df, ['Campaign Name', 'Campaign'])
    sb_camp_col = find_col(sb_df, ['Campaign Name', 'Campaign'])
    
    sp_cols = {m: find_col(sp_df, k, exclude_for_sales if m == 'Sales' else []) for m, k in metrics_map.items()}
    sb_cols = {m: find_col(sb_df, k, exclude_for_sales if m == 'Sales' else []) for m, k in metrics_map.items()}
    
    biz_sales_col = find_col(biz_df, ['Sales', 'Revenue'], ['ACOS', 'ROAS'])
    biz_title_col = find_col(biz_df, ['Title', 'Product Name'])

    # Aggregate Ads
    sp_df['Brand'] = sp_df[sp_camp_col].apply(get_brand) if sp_camp_col else "Unmapped"
    sb_df['Brand'] = sb_df[sb_camp_col].apply(get_brand) if sb_camp_col else "Unmapped"

    def group_ads(df, col_map):
        agg_dict = {col_map[m]: 'sum' for m in ['Spend', 'Sales', 'Clicks', 'Impressions'] if col_map[m]}
        rename_dict = {col_map['Sales']: 'Ad Sales', col_map['Spend']: 'Spend', col_map['Clicks']: 'Clicks', col_map['Impressions']: 'Impressions'}
        return df.groupby('Brand').agg(agg_dict).rename(columns=rename_dict)

    sp_grouped = group_ads(sp_df, sp_cols)
    sb_grouped = group_ads(sb_df, sb_cols)
    ads_combined = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    # Process Business Data
    biz_df['Brand'] = biz_df[biz_title_col].apply(lambda x: next((v for k,v in BRAND_MAP.items() if k in str(x).upper()), "Unmapped")) if biz_title_col else "Unmapped"
    biz_grouped = biz_df.groupby('Brand')[biz_sales_col].sum().reset_index().rename(columns={biz_sales_col: 'Total Sales'})

    # Final Merge
    final_baseline = pd.merge(ads_combined, biz_grouped, on='Brand', how='left').fillna(0)
    
    brand_metrics = []
    for _, row in final_baseline.iterrows():
        if row['Brand'] == "Unmapped": continue
        
        c_spend, c_ad_sales, c_total_sales = row['Spend'], row['Ad Sales'], row['Total Sales']
        c_roas = c_ad_sales / c_spend if c_spend > 0 else 0
        c_org_pct = (c_total_sales - c_ad_sales) / c_total_sales if c_total_sales > 0 else 0
        c_cpc, c_ctr = c_spend / row['Clicks'] if row['Clicks'] > 0 else 0, row['Clicks'] / row['Impressions'] if row['Impressions'] > 0 else 0
        
        # Growth
        t_spend = c_spend * (1 + spend_growth)
        t_roas = c_roas * (1 + roas_uplift)
        t_ad_rev = t_spend * t_roas
        t_org_pct = min(0.95, c_org_pct + organic_lift)
        t_total_rev = t_ad_rev / (1 - t_org_pct) if t_org_pct < 1 else t_ad_rev
        
        brand_metrics.append({
            'Brand': row['Brand'], 'Imp': int((t_spend/c_cpc)/c_ctr) if c_cpc>0 and c_ctr>0 else 0,
            'Clicks': int(t_spend/c_cpc) if c_cpc>0 else 0, 'Spends': round(t_spend, 2),
            'ROAS': round(t_roas, 2), 'Ad Revenue': round(t_ad_rev, 2), 'Organic (%)': round(t_org_pct, 4),
            'Paid (%)': round(1 - t_org_pct, 4), 'Organic Revenue': round(t_total_rev - t_ad_rev, 2), 
            'Overall Revenue': round(t_total_rev, 2), 'T-ROAS': round(t_total_rev / t_spend, 2) if t_spend > 0 else 0,
            'T-ACOS': round(t_spend / t_total_rev, 4) if t_total_rev > 0 else 0
        })

    proj_df = pd.DataFrame(brand_metrics)
    
    # UI and Export Logic...
    tabs = st.tabs(["🌎 Amazon Portfolio"] + proj_df['Brand'].tolist())
    # (Rest of UI and Export code as before...)
    with tabs[0]:
        st.subheader("Combined Platform Projections")
        st.dataframe(proj_df, use_container_width=True, hide_index=True)

    # Simplified weekly logic for brevity in this snippet
    weights = [0.30, 0.20, 0.20, 0.20, 0.10]
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        proj_df.to_excel(writer, sheet_name='Combined_Overview', index=False)
        for i, brand in enumerate(proj_df['Brand'].tolist()):
            b_row = proj_df[proj_df['Brand'] == brand].iloc[0]
            weekly_rows = [{"Week": f"Week {w+1}", "Overall Revenue": round(b_row['Overall Revenue']*wt, 2)} for w, wt in enumerate(weights)]
            pd.DataFrame(weekly_rows).to_excel(writer, sheet_name=brand[:31], startrow=4, index=False)

    st.sidebar.download_button("📥 Download Master Report", data=output.getvalue(), file_name="Amazon_Platform_Projections.xlsx")

else:
    st.info("Please upload all three reports (SP, SB, and Business) to start.")
