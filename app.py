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
        # Matches prefix followed by common separators
        if any(name.startswith(f"{prefix}{sep}") for sep in ["_", " ", "-", " |"]):
            return full_name
    # Fallback: contains check
    for prefix, full_name in BRAND_MAP.items():
        if prefix in name:
            return full_name
    return "Unmapped"

def find_col(df, keywords):
    """Finds a column name in a dataframe that contains any of the keywords (case-insensitive)."""
    for col in df.columns:
        if any(kw.lower() in col.lower() for kw in keywords):
            return col
    return None

st.title("📊 Amazon Master Projections")
st.info("Combined SP + SB Advertising & Organic Growth Model")

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
    # 1. Load and Standardize Column Names
    def load_df(file):
        df = pd.read_csv(file).map(clean_numeric) if file.name.endswith('.csv') else pd.read_excel(file).map(clean_numeric)
        df.columns = [str(c).strip() for c in df.columns] # Strip whitespace from headers
        return df

    sp_df = load_df(sp_file)
    sb_df = load_df(sb_file)
    biz_df = load_df(biz_file)
    
    # 2. Identify Dynamic Columns
    sp_camp_col = find_col(sp_df, ['Campaign Name', 'Campaign'])
    sb_camp_col = find_col(sb_df, ['Campaign Name', 'Campaign'])
    sp_sales_col = find_col(sp_df, ['Sales'])
    sb_sales_col = find_col(sb_df, ['Sales'])
    biz_sales_col = find_col(biz_df, ['Sales', 'Revenue'])
    biz_title_col = find_col(biz_df, ['Title', 'Product Name'])

    # 3. Aggregate Ad Data (SP + SB)
    sp_df['Brand'] = sp_df[sp_camp_col].apply(get_brand) if sp_camp_col else "Unmapped"
    sb_df['Brand'] = sb_df[sb_camp_col].apply(get_brand) if sb_camp_col else "Unmapped"

    sp_grouped = sp_df.groupby('Brand').agg({'Spend': 'sum', sp_sales_col: 'sum', 'Clicks': 'sum', 'Impressions': 'sum'}).rename(columns={sp_sales_col: 'Ad Sales'})
    sb_grouped = sb_df.groupby('Brand').agg({'Spend': 'sum', sb_sales_col: 'sum', 'Clicks': 'sum', 'Impressions': 'sum'}).rename(columns={sb_sales_col: 'Ad Sales'})
    
    ads_combined = sp_grouped.add(sb_grouped, fill_value=0).reset_index()

    # 4. Process Business Data
    biz_df['Brand'] = biz_df[biz_title_col].apply(lambda x: next((v for k, v in BRAND_MAP.items() if k in str(x).upper()), "Unmapped")) if biz_title_col else "Unmapped"
    biz_grouped = biz_df.groupby('Brand')[biz_sales_col].sum().reset_index().rename(columns={biz_sales_col: 'Total Sales'})

    # 5. Merge and Calculate Projections
    final_baseline = pd.merge(ads_combined, biz_grouped, on='Brand', how='left').fillna(0)
    
    brand_metrics = []
    for _, row in final_baseline.iterrows():
        if row['Brand'] == "Unmapped" or row['Brand'] == 0: continue
        
        curr_spend = row['Spend']
        curr_ad_sales = row['Ad Sales']
        curr_total_sales = row['Total Sales']
        
        c_roas = curr_ad_sales / curr_spend if curr_spend > 0 else 0
        c_org_pct = (curr_total_sales - curr_ad_sales) / curr_total_sales if curr_total_sales > 0 else 0
        c_cpc = curr_spend / row['Clicks'] if row['Clicks'] > 0 else 0
        c_ctr = row['Clicks'] / row['Impressions'] if row['Impressions'] > 0 else 0
        
        # PROJECTION LOGIC
        target_spend = curr_spend * (1 + spend_growth)
        target_roas = c_roas * (1 + roas_uplift)
        target_ad_rev = target_spend * target_roas
        target_org_pct = min(0.95, c_org_pct + organic_lift)
        target_total_rev = target_ad_rev / (1 - target_org_pct) if target_org_pct < 1 else target_ad_rev
        
        brand_metrics.append({
            'Brand': row['Brand'], 
            'Imp': int((target_spend/c_cpc)/c_ctr) if c_cpc>0 and c_ctr>0 else 0,
            'Clicks': int(target_spend/c_cpc) if c_cpc>0 else 0, 
            'Spends': round(target_spend, 2), 'ROAS': round(target_roas, 2), 
            'Ad Revenue': round(target_ad_rev, 2), 'Organic (%)': round(target_org_pct, 4),
            'Paid (%)': round(1 - target_org_pct, 4), 'Organic Revenue': round(target_total_rev - target_ad_rev, 2), 
            'Overall Revenue': round(target_total_rev, 2), 'T-ROAS': round(target_total_rev / target_spend, 2) if target_spend > 0 else 0,
            'T-ACOS': round(target_spend / target_total_rev, 4) if target_total_rev > 0 else 0
        })

    proj_df = pd.DataFrame(brand_metrics)
    
    # 6. Build UI Tabs
    tabs = st.tabs(["🌎 Amazon Portfolio"] + proj_df['Brand'].tolist())

    with tabs[0]:
        st.subheader("🏆 Combined Amazon Platform Projections")
        # Sum all projections for the portfolio row
        ts, tar, tor, tr = proj_df['Spends'].sum(), proj_df['Ad Revenue'].sum(), proj_df['Overall Revenue'].sum(), proj_df['Organic Revenue'].sum()
        platform_total = pd.DataFrame([{
            'Brand': 'TOTAL AMAZON PLATFORM', 'Imp': int(proj_df['Imp'].sum()), 'Clicks': int(proj_df['Clicks'].sum()),
            'Spends': round(ts, 2), 'ROAS': round(tar/ts, 2) if ts>0 else 0, 'Ad Revenue': round(tar, 2),
            'Organic (%)': round(tr/tor, 4) if tor>0 else 0, 'Paid (%)': round(tar/tor, 4) if tor>0 else 0,
            'Organic Revenue': round(tr, 2), 'Overall Revenue': round(tor, 2), 
            'T-ROAS': round(tor/ts, 2) if ts>0 else 0, 'T-ACOS': round(ts/tor, 4) if tor>0 else 0
        }])
        st.dataframe(platform_total, use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("🏢 Brand-Wise Monthly Summary")
        st.dataframe(proj_df, use_container_width=True, hide_index=True)

    weights = [0.30, 0.20, 0.20, 0.20, 0.10]
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        platform_total.to_excel(writer, sheet_name='Combined_Overview', index=False)
        proj_df.to_excel(writer, sheet_name='Combined_Overview', startrow=5, index=False)

        for i, brand in enumerate(proj_df['Brand'].tolist()):
            with tabs[i+1]:
                b_row = proj_df[proj_df['Brand'] == brand].iloc[0]
                st.subheader(f"📊 {brand} Projections")
                st.dataframe(pd.DataFrame([b_row]), use_container_width=True, hide_index=True)
                st.divider()
                st.markdown("#### 📅 Weekly Segregation (30/20/20/20/10)")
                weekly_rows = [{"Week": f"Week {w+1}", "Imp": int(b_row['Imp']*wt), "Clicks": int(b_row['Clicks']*wt),
                                "Spends": round(b_row['Spends']*wt, 2), "ROAS": b_row['ROAS'], "Ad Revenue": round(b_row['Ad Revenue']*wt, 2),
                                "Organic (%)": b_row['Organic (%)'], "Paid (%)": b_row['Paid (%)'], 
                                "Organic Revenue": round(b_row['Organic Revenue']*wt, 2), "Overall Revenue": round(b_row['Overall Revenue']*wt, 2),
                                "T-ROAS": b_row['T-ROAS'], "T-ACOS": b_row['T-ACOS']} for w, wt in enumerate(weights)]
                weekly_df = pd.DataFrame(weekly_rows)
                st.dataframe(weekly_df, use_container_width=True, hide_index=True)
                
                # Excel: Brand Sheet (Monthly on top, Weekly below)
                pd.DataFrame([b_row]).to_excel(writer, sheet_name=brand[:31], index=False)
                weekly_df.to_excel(writer, sheet_name=brand[:31], startrow=4, index=False)

    st.sidebar.download_button("📥 Download Master Report", data=output.getvalue(), file_name="Amazon_Platform_Projections.xlsx", use_container_width=True)

else:
    st.info("Upload SP, SB, and Business reports to generate the Amazon Portfolio projections.")
