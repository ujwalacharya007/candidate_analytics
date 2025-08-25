
import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt

st.set_page_config(page_title="Election Analytics Automation", layout="wide")

st.title("🗳️ Election Analytics Automation")
st.caption("Upload your Excel file to generate vote analysis, candidate insights, strategy lists, and trends.")

# ---------------------- Helpers ----------------------
@st.cache_data
def load_excel(file):
    xl = pd.ExcelFile(file)
    # Try common sheet names, fallback to the first
    target = None
    for name in ["Filtered", "Sheet1", "Data", "Sheet0"]:
        if name in xl.sheet_names:
            target = name
            break
    if target is None:
        target = xl.sheet_names[0]
    df = xl.parse(target)
    return df

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # flatten whitespace/newlines in column names
    ren = {c: str(c).replace("\\n", " ").replace("  ", " ").strip() for c in df.columns}
    df = df.rename(columns=ren)

    # Nepali -> English mapping (best-effort; keep original too)
    mapping = {
        "क्र.सं.": "serial",
        "लुम्बिनी प्रदेश क्षे.नं.३(१)": "province_constituency",
        "जिल्ला": "district",
        "स्थानीय तह": "local_level",
        "व डा": "ward",
        "वडा": "ward",
        "व डा ": "ward",
        "पद": "position",
        "उम्मेदवारको नाम": "candidate_name",
        "लिङ्ग": "gender",
        "उमेर": "age",
        "राजनीतिक दल/स्वतन्त्र": "party",
        "प्राप्त मत": "votes",
        "प्राप्त मत  ": "votes",
        "प्राप्त मत  ": "votes",
        "प्राप्त मत  ": "votes",
    }
    # Also handle columns that had newlines in sample
    for c in list(df.columns):
        c2 = (str(c)
              .replace("\\n", " ")
              .replace("  ", " ")
              .replace("   ", " ")
              .strip())
        if c2 in mapping:
            df.rename(columns={c: mapping[c2]}, inplace=True)

    # coerce key fields if present
    if "ward" in df.columns:
        df["ward"] = pd.to_numeric(df["ward"], errors="coerce")
    if "age" in df.columns:
        df["age"] = pd.to_numeric(df["age"], errors="coerce")
    if "votes" in df.columns:
        # remove stray whitespace/non-digits and cast
        df["votes"] = pd.to_numeric(df["votes"].astype(str).str.replace(r"[^0-9\-]", "", regex=True), errors="coerce")
    return df

def add_age_groups(df: pd.DataFrame) -> pd.DataFrame:
    if "age" not in df.columns:
        return df
    bins = [0, 25, 30, 35, 40, 50, 60, 120]
    labels = ["<=25", "26-30", "31-35", "36-40", "41-50", "51-60", "60+"]
    df["age_group"] = pd.cut(df["age"], bins=bins, labels=labels, include_lowest=True)
    return df

def require_cols(df: pd.DataFrame, cols):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}. Please ensure your Excel has these fields (in Nepali headers are OK).")
        st.stop()

def to_excel_bytes(df_dict: dict) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        for name, d in df_dict.items():
            d.to_excel(writer, index=False, sheet_name=name[:31])
    return out.getvalue()

# ---------------------- UI: Upload ----------------------
uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])

if not uploaded:
    st.info("Upload your Excel file to get started. The app will detect Nepali headers and normalize them automatically.")
    st.stop()

raw = load_excel(uploaded)
df = normalize_columns(raw.copy())
df = add_age_groups(df)

# Determine available dims
dims = {
    "district": "district" if "district" in df.columns else None,
    "local_level": "local_level" if "local_level" in df.columns else None,
    "ward": "ward" if "ward" in df.columns else None,
    "position": "position" if "position" in df.columns else None,
    "gender": "gender" if "gender" in df.columns else None,
    "age_group": "age_group" if "age_group" in df.columns else None,
    "party": "party" if "party" in df.columns else None,
}

require_cols(df, [c for c in ["party", "votes"] if c])

# pick target party for strategy
with st.sidebar:
    st.header("⚙️ Settings")
    parties = sorted(df["party"].dropna().astype(str).unique())
    target_party = st.selectbox("Select your party", parties, index=0 if parties else None)
    top_n = st.slider("How many top/bottom wards to show", 5, 50, 10)

st.success("File loaded. Columns detected: " + ", ".join([k for k,v in dims.items() if v]))

# ---------------------- 1) Vote Analysis ----------------------
st.subheader("1) Vote Analysis")

group_cols = []
if dims["district"]: group_cols.append("district")
if dims["local_level"]: group_cols.append("local_level")
if dims["ward"]: group_cols.append("ward")

if not group_cols:
    st.warning("No district/local_level/ward columns found; showing totals by party only.")
    group_cols = []

votes_by_party = df.groupby(group_cols + ["party"], dropna=False)["votes"].sum().reset_index().sort_values("votes", ascending=False)
st.write("**Total votes by party** (grouped):")
st.dataframe(votes_by_party)

# Strongholds/weakholds (relative share within each area)
if group_cols:
    area_totals = df.groupby(group_cols)["votes"].sum().reset_index().rename(columns={"votes":"area_total"})
    merged = votes_by_party.merge(area_totals, on=group_cols, how="left")
    merged["vote_share_pct"] = (merged["votes"] / merged["area_total"] * 100).round(2)
    st.write("**Vote share (%) by party within area**:")
    st.dataframe(merged.sort_values("vote_share_pct", ascending=False))

    # strong/weak for target party
    tp = merged[merged["party"].astype(str) == str(target_party)].copy()
    strongholds = tp.sort_values("vote_share_pct", ascending=False).head(top_n)
    weakholds = tp.sort_values("vote_share_pct", ascending=True).head(top_n)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Top {top_n} strongholds for {target_party}**")
        st.dataframe(strongholds)
    with c2:
        st.markdown(f"**Top {top_n} weakholds for {target_party}**")
        st.dataframe(weakholds)

    # simple bar chart for target party by ward/local level
    fig, ax = plt.subplots()
    plot_df = tp.copy()
    label = " - ".join([c for c in group_cols if c])
    plot_df["label"] = plot_df[group_cols].astype(str).agg(" / ".join, axis=1)
    top_plot = plot_df.sort_values("votes", ascending=False).head(20)
    ax.bar(top_plot["label"], top_plot["votes"])
    ax.set_xticklabels(top_plot["label"], rotation=60, ha="right")
    ax.set_title(f"Top 20 areas by votes – {target_party}")
    ax.set_ylabel("Votes")
    st.pyplot(fig)

# Positions pattern
if dims["position"]:
    pos_stats = df.groupby(["position", "party"])["votes"].agg(["sum","mean","count"]).reset_index().sort_values("sum", ascending=False)
    st.write("**Patterns by position & party** (sum/mean/count):")
    st.dataframe(pos_stats)

# ---------------------- 2) Candidate Insights ----------------------
st.subheader("2) Candidate Insights")

# Gender performance
if dims["gender"]:
    gender_perf = df.groupby(["gender", "party"])["votes"].agg(["mean", "sum", "count"]).reset_index()
    st.write("**Performance by gender & party**:")
    st.dataframe(gender_perf)

# Age group performance
if dims["age_group"]:
    age_perf = df.groupby(["age_group", "party"])["votes"].agg(["mean", "sum", "count"]).reset_index()
    st.write("**Performance by age group & party**:")
    st.dataframe(age_perf)

# Position performance
if dims["position"]:
    position_perf = df.groupby(["position", "party"])["votes"].agg(["mean", "sum", "count"]).reset_index()
    st.write("**Performance by position & party**:")
    st.dataframe(position_perf)

# Identify over/under performers (z-score within position)
if dims["position"]:
    temp = df.copy()
    temp["pos_mean"] = temp.groupby("position")["votes"].transform("mean")
    temp["pos_std"] = temp.groupby("position")["votes"].transform("std")
    temp["z_score"] = (temp["votes"] - temp["pos_mean"]) / temp["pos_std"]
    over_perf = temp.sort_values("z_score", ascending=False).head(20)
    under_perf = temp.sort_values("z_score", ascending=True).head(20)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Top 20 over-performing candidates (within position)**")
        st.dataframe(over_perf[["candidate_name","party","position","gender","age","votes","z_score"]])
    with c2:
        st.markdown("**Top 20 under-performing candidates (within position)**")
        st.dataframe(under_perf[["candidate_name","party","position","gender","age","votes","z_score"]])

# ---------------------- 3) Geographical Strategy ----------------------
st.subheader("3) Geographical Strategy (Lists)")

if group_cols:
    # Areas with low votes for target party
    tp_votes = votes_by_party[votes_by_party["party"].astype(str) == str(target_party)].copy()
    if not tp_votes.empty:
        low_tp = tp_votes.sort_values("votes").head(top_n)
        st.markdown(f"**Areas with LOW votes for {target_party} (focus for mobilization)**")
        st.dataframe(low_tp)

    # Areas with high opposition share (max other party share)
    if group_cols:
        area_totals = df.groupby(group_cols)["votes"].sum().reset_index().rename(columns={"votes":"area_total"})
        area_party = df.groupby(group_cols + ["party"])["votes"].sum().reset_index()
        area_party = area_party.merge(area_totals, on=group_cols, how="left")
        area_party["share"] = area_party["votes"]/area_party["area_total"]
        opp = area_party[area_party["party"].astype(str) != str(target_party)].copy()
        # get the opposition party with highest share in each area
        opp_top = opp.sort_values(["share"], ascending=False).groupby(group_cols).head(1)
        opp_top = opp_top.sort_values("share", ascending=False).head(top_n)
        st.markdown("**Areas with high opposition dominance (targeted outreach)**")
        st.dataframe(opp_top)

# ---------------------- 4) Trend Analysis ----------------------
st.subheader("4) Trend Analysis")

# Trends by gender over wards (if possible)
if dims["gender"] and dims["ward"]:
    tdf = df.groupby(["ward", "gender"])["votes"].mean().reset_index().pivot(index="ward", columns="gender", values="votes").fillna(0)
    fig, ax = plt.subplots()
    tdf.plot(ax=ax)
    ax.set_title("Average votes by gender across wards")
    ax.set_xlabel("Ward")
    ax.set_ylabel("Avg votes")
    st.pyplot(fig)

# Trends by age group (if present)
if dims["age_group"] and dims["ward"]:
    tdf2 = df.groupby(["ward", "age_group"])["votes"].mean().reset_index().pivot(index="ward", columns="age_group", values="votes").fillna(0)
    fig2, ax2 = plt.subplots()
    tdf2.plot(ax=ax2)
    ax2.set_title("Average votes by age group across wards")
    ax2.set_xlabel("Ward")
    ax2.set_ylabel("Avg votes")
    st.pyplot(fig2)

# ---------------------- 5) Performance Optimization ----------------------
st.subheader("5) Performance Optimization")

# Low participation proxy: areas where target party has low vote share vs area total
if group_cols:
    merged = df.groupby(group_cols + ["party"])["votes"].sum().reset_index()
    area_totals = df.groupby(group_cols)["votes"].sum().reset_index().rename(columns={"votes":"area_total"})
    merged = merged.merge(area_totals, on=group_cols, how="left")
    merged["share"] = merged["votes"]/merged["area_total"]
    low_share = merged[merged["party"].astype(str) == str(target_party)].sort_values("share").head(top_n)
    st.markdown(f"**Low-share areas for {target_party} (mobilize)**")
    st.dataframe(low_share)

# Correlations
corr_items = []
if "age" in df.columns:
    corr_items.append(("Age vs Votes (Pearson)", df["age"].corr(df["votes"])))
if "gender" in df.columns:
    # encode gender to numeric (simple)
    g_map = {g:i for i,g in enumerate(df["gender"].dropna().unique())}
    corr_items.append(("Gender(code) vs Votes (Pearson)", pd.Series(df["gender"]).map(g_map).corr(df["votes"])))
if "position" in df.columns:
    p_map = {p:i for i,p in enumerate(df["position"].dropna().unique())}
    corr_items.append(("Position(code) vs Votes (Pearson)", pd.Series(df["position"]).map(p_map).corr(df["votes"])))

if corr_items:
    corr_df = pd.DataFrame(corr_items, columns=["Metric","Pearson r"]).round(3)
    st.write("**Simple correlations with votes** (interpret with caution):")
    st.dataframe(corr_df)

# ---------------------- Downloads ----------------------
st.subheader("⬇️ Download Outputs")

outputs = {}
outputs["votes_by_party"] = votes_by_party

if group_cols:
    outputs["strongholds_"+str(target_party)] = strongholds if 'strongholds' in locals() else pd.DataFrame()
    outputs["weakholds_"+str(target_party)] = weakholds if 'weakholds' in locals() else pd.DataFrame()
if dims["position"]:
    outputs["position_patterns"] = pos_stats if 'pos_stats' in locals() else pd.DataFrame()
if dims["gender"]:
    outputs["gender_performance"] = gender_perf if 'gender_perf' in locals() else pd.DataFrame()
if dims["age_group"]:
    outputs["age_group_performance"] = age_perf if 'age_perf' in locals() else pd.DataFrame()
if dims["position"]:
    outputs["position_performance"] = position_perf if 'position_perf' in locals() else pd.DataFrame()
if group_cols:
    outputs["low_share_"+str(target_party)] = low_share if 'low_share' in locals() else pd.DataFrame()

excel_bytes = to_excel_bytes(outputs)
st.download_button("Download analysis as Excel", data=excel_bytes, file_name="election_analysis_outputs.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.caption("Tip: For geographical maps, upload a ward-level GeoJSON in a future version to draw choropleth maps. This version provides ranked lists and charts.")
