import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import os
import plotly.express as px
from matplotlib import rcParams
from matplotlib.font_manager import FontProperties


st.set_page_config(page_title="Election Analytics Automation", layout="wide")
st.title("🗳️ Election Analytics Automation")
st.caption("Upload your Excel file to generate vote analysis, candidate insights, strategy lists, and trends.")

# ---------------------- Helpers ----------------------
@st.cache_data
def load_excel(file):
    xl = pd.ExcelFile(file)
    for name in ["Filtered", "Sheet1", "Data", "Sheet0"]:
        if name in xl.sheet_names:
            return xl.parse(name)
    return xl.parse(xl.sheet_names[0])

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "क्र.सं.": "serial",
        "लुम्बिनी प्रदेश क्षे.नं.३(१)": "province_constituency",
        "जिल्ला": "district",
        "स्थानीय तह": "local_level",
        "व डा": "ward",
        "वडा": "ward",
        "पद": "position",
        "उम्मेदवारको नाम": "candidate_name",
        "लिङ्ग": "gender",
        "उमेर": "age",
        "राजनीतिक दल/स्वतन्त्र": "party",
        "प्राप्त मत": "votes",
    }
    df = df.rename(columns=lambda c: str(c).replace("\n", " ").strip())
    df = df.rename(columns={c: mapping.get(c, c) for c in df.columns})
    if "ward" in df.columns:
        df["ward"] = pd.to_numeric(df["ward"], errors="coerce")
    if "age" in df.columns:
        df["age"] = pd.to_numeric(df["age"], errors="coerce")
    if "votes" in df.columns:
        df["votes"] = pd.to_numeric(df["votes"].astype(str).str.replace(r"[^0-9\-]", "", regex=True), errors="coerce")
    return df

def add_age_groups(df):
    if "age" not in df.columns: return df
    bins = [0, 25, 30, 35, 40, 50, 60, 120]
    labels = ["<=25", "26-30", "31-35", "36-40", "41-50", "51-60", "60+"]
    df["age_group"] = pd.cut(df["age"], bins=bins, labels=labels, include_lowest=True)
    return df

def to_excel_bytes(dfs: dict) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        for name, d in dfs.items():
            if not d.empty:
                d.to_excel(writer, index=False, sheet_name=name[:31])
    return out.getvalue()

def set_devanagari_font():
    font_path = r'C:\Users\Admin\Downloads\devanagari-plain9190-122439-pm\Devanagari Plain9190 122439 PM\Devanagari Plain9190 122439 PM.ttf'
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        devanagari_font = FontProperties(fname=font_path)
        plt.rcParams["font.family"] = devanagari_font.get_name()
        plt.rcParams["axes.unicode_minus"] = False
        return devanagari_font
    else:
        st.warning("Devanagari font file not found!")
        return None

devanagari_font = set_devanagari_font()

# ---------------------- UI: Upload ----------------------
uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
if not uploaded: st.stop()

df = add_age_groups(normalize_columns(load_excel(uploaded)))


# ---------------------- Summary Dashboard ----------------------
st.subheader("📊 Overall Election Summary")

# Total candidates
total_candidates = len(df)



# Total wards
total_wards = df["ward"].nunique() if "ward" in df.columns else 0

# Average age of candidates
avg_age = df["age"].mean() if "age" in df.columns else None

# Male vs Female ratio
if "gender" in df.columns:
    male_count = df[df["gender"].str.contains("पुरुष|M", na=False)].shape[0]
    female_count = df[df["gender"].str.contains("महिला|F", na=False)].shape[0]
else:
    male_count, female_count = 0, 0

# Total votes & Average votes
if "votes" in df.columns:
    total_votes = df["votes"].sum()
    avg_votes = df["votes"].mean()
else:
    total_votes, avg_votes = 0, 0

# Display metrics in a row
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("👤 Total Candidates", f"{total_candidates:,}")
c2.metric("📍 Total Wards", f"{total_wards:,}")
c3.metric("📊 Avg. Age", f"{avg_age:.1f}" if avg_age else "N/A")
c4.metric("♂️ Male : Female", f"{male_count} : {female_count}")
c5.metric("🗳 Total Votes", f"{total_votes:,}")
c6.metric("📈 Avg. Votes", f"{avg_votes:.1f}")


# ---------------------- 1) Vote Analysis ----------------------
st.subheader("1️⃣ Vote Analysis")

# Dynamically select grouping columns that exist in df
group_cols = [c for c in ["district", "local_level", "ward"] if c in df.columns]
votes_by_party = df.groupby(group_cols + ["party"], dropna=False)["votes"].sum().reset_index()

# Party totals
party_totals = df.groupby("party")["votes"].sum().reset_index().sort_values("votes", ascending=False)
st.write("**Total votes by party:**")
st.dataframe(party_totals)

# Dropdown to select party dynamically
target_party = st.selectbox("Select a party", party_totals["party"].unique())

# Top 20 areas for selected party
party_votes = votes_by_party[votes_by_party["party"] == target_party] \
    .sort_values("votes", ascending=False).head(20)

st.subheader("🔒 Loyal Voter Base (Ward-wise Average)")

if "ward" in df.columns:
    # 👉 Use agg() to calculate both sum and mean
    loyal_base = (
        df.groupby("ward")["votes"]
        .agg(votes="sum", avg_votes="mean")   # sum as votes, mean as avg_votes
        .reset_index()
    )

    # Sort by avg_votes for loyal base ranking
    loyal_base = loyal_base.sort_values("avg_votes", ascending=False)

    # Show in Streamlit
    st.dataframe(loyal_base)


    fig = px.bar(
        loyal_base,
        x=loyal_base["ward"].astype(str),
        y="avg_votes",
        title="Average Votes per Ward (Loyal Base)",
        text="avg_votes",
        color="avg_votes",
        color_continuous_scale="Blues",
        category_orders={"ward": loyal_base["ward"].astype(str).tolist()}  # 👈 preserve order
    )

    fig.update_layout(
        xaxis_title="Ward Number",
        yaxis_title="Average Votes",
    )

    st.plotly_chart(fig, use_container_width=True)

st.subheader("🧑‍💼 Position-wise Performance")

# Votes per party per position (with total + avg)
pos_summary = (
    df.groupby(["position", "party"])["votes"]
    .agg(total_votes="sum", avg_votes="mean")
    .reset_index()
)
st.dataframe(pos_summary)

fig = px.bar(
    pos_summary,
    x="position",
    y="total_votes",
    color="party",
    barmode="group",
    title="Total Votes by Position & Party"
)
st.plotly_chart(fig, use_container_width=True)



# Top candidate per position + avg votes
winners_by_position = df.loc[df.groupby("position")["votes"].idxmax()][
    ["position", "candidate_name", "party", "votes"]
]

# Add average votes column
avg_votes_pos = df.groupby("position")["votes"].mean().reset_index().rename(columns={"votes": "avg_votes"})
winners_by_position = winners_by_position.merge(avg_votes_pos, on="position", how="left")

st.write("🏆 Top candidates per position (with Avg. Votes):")
st.dataframe(winners_by_position)

st.subheader("2️⃣ Share & Strongholds")

    # Check required columns
if all(col in df.columns for col in group_cols + ["party", "votes"]):

        # Group by area + party
        party_share = df.groupby(group_cols + ["party"], dropna=False)["votes"].sum().reset_index()

        # Total votes per area (all parties)
        area_totals = df.groupby(group_cols)["votes"].sum().reset_index().rename(columns={"votes":"area_total"})

        # Merge total votes to calculate vote share
        party_share = party_share.merge(area_totals, on=group_cols, how="left")
        party_share["vote_share"] = party_share["votes"] / party_share["area_total"]

        # Metrics
        party_share["vote_strength"] = party_share["vote_share"]
        party_share["consistency_index"] = (party_share["votes"] - party_share["votes"].mean()) / party_share["votes"].std()
        party_share["improvement_potential"] = party_share["area_total"] - party_share["votes"]

        # Create combined area name for visualization
        party_share["area_name"] = party_share[group_cols].astype(str).agg(" - ".join, axis=1)

        # Strongholds = top 10 by vote_strength
        strongholds = party_share.sort_values("vote_strength", ascending=False).head(10)

        # Weakholds = bottom 10 by vote_strength
        weakholds = party_share.sort_values("vote_strength", ascending=True).head(10)

        # Show in Streamlit
        st.markdown("### 🏆 Top Strongholds (High Vote Strength)")
        st.dataframe(strongholds[group_cols + ["party","votes","vote_strength","consistency_index","improvement_potential"]])

        st.markdown("### ⚠️ Weak Areas (Low Vote Strength)")
        st.dataframe(weakholds[group_cols + ["party","votes","vote_strength","consistency_index","improvement_potential"]])
# ---------------------- Part 2: Election Performance Insights ----------------------
st.subheader("भाग २: निर्वाचन प्रदर्शन विश्लेषण")

# ---------------- Stronghold (बलियो वडा) ----------------
st.markdown("### 🟢 बलियो वडा")
strongholds = df.groupby(["ward","party"])["votes"].sum().reset_index()
strongholds = strongholds.sort_values("votes", ascending=False).groupby("party").head(2)

for _, row in strongholds.iterrows():
    st.write(f"✅ वडा नं {row['ward']} → {row['party']} ({row['votes']} मत)")

# ---------------- Weakhold (कमजोर वडा) ----------------
st.markdown("### 🔴 कमजोर वडा")
weakholds = df.groupby(["ward","party"])["votes"].sum().reset_index()
weakholds = weakholds.sort_values("votes", ascending=True).groupby("party").head(2)

for _, row in weakholds.iterrows():
    st.write(f"⚠️ वडा नं {row['ward']} → {row['party']} ({row['votes']} मत)")

# ---------------- Close Win / Close Loss Alerts ----------------

ward_results = df.groupby(["ward","party"])["votes"].sum().reset_index()

# For each ward, find top 2 candidates
close_contests = []
for ward, data in ward_results.groupby("ward"):
    top2 = data.sort_values("votes", ascending=False).head(2)
    if len(top2) == 2:
        margin = top2.iloc[0]["votes"] - top2.iloc[1]["votes"]
        if margin <= 50:  # threshold for 'close'
            close_contests.append((ward, top2.iloc[0]["party"], top2.iloc[1]["party"], margin))

# ---------------------- 3) Margins & Key Insights ----------------------
st.subheader("भाग ३: प्रमुख नतिजा / विजय र पराजय")

# Group votes by ward for the single party
ward_votes = df.groupby(["ward","candidate_name"])["votes"].sum().reset_index()

# ---------------- Stronghold (बलियो वडा) ----------------
st.markdown("### 🟢 बलियो वडा (Top Strong Wards)")
strongwards = ward_votes.sort_values("votes", ascending=False).groupby("ward").head(1)
for _, row in strongwards.iterrows():
    st.write(f"✅ वडा नं {row['ward']} → {row['candidate_name']} ({row['votes']} मत)")

# ---------------- Weakhold (कमजोर वडा) ----------------
st.markdown("### 🔴 कमजोर वडा (Weak Wards)")
weakwards = ward_votes.sort_values("votes", ascending=True).groupby("ward").head(1)
for _, row in weakwards.iterrows():
    st.write(f"⚠️ वडा नं {row['ward']} → {row['candidate_name']} ({row['votes']} मत)")

# ---------------- Close Win / Close Loss ----------------
st.markdown("### ⚖️ नजिकको जित/हार (Close Contests)")
close_threshold = 50  # votes threshold for "close"
close_contests = []

for ward, data in ward_votes.groupby("ward"):
    top2 = data.sort_values("votes", ascending=False).head(2)
    if len(top2) == 2:
        margin = top2.iloc[0]["votes"] - top2.iloc[1]["votes"]
        if margin <= close_threshold:
            close_contests.append((ward, top2.iloc[0]["candidate_name"], top2.iloc[1]["candidate_name"], margin))

if close_contests:
    for ward, winner, runnerup, margin in close_contests:
        st.write(f"⚠️ वडा नं {ward}: {winner} ले {runnerup} लाई {margin} मतले मात्र जित्यो")
else:
    st.write("👍 कुनै नजिकको जित/हार छैन")

# ---------------- Top Candidates Overall ----------------
st.markdown("### 🏆 शीर्ष उम्मेदवारहरु (Top Candidates)")
top_candidates = ward_votes.sort_values("votes", ascending=False).head(5)
for _, row in top_candidates.iterrows():
    st.write(f"🏅 {row['candidate_name']} → वडा नं {row['ward']} ({row['votes']} मत)")


# ---------------------- 4) Candidate Insights ----------------------
st.subheader("4️⃣ Candidate Insights")

# ---------------- Candidate Performance ----------------
if "candidate_name" in df.columns:
    top_cand = df.sort_values("votes", ascending=False).head(20)
    st.write("**Top 20 candidates by votes:**")

    # Horizontal bar chart for readability
    fig = px.bar(
        top_cand.sort_values("votes"),
        x="votes", y="candidate_name",
        color="party", orientation="h",
        title="Top 20 Candidates by Votes"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(top_cand[["candidate_name","party","position","votes"]])

    # Vote distribution across all candidates
    fig = px.histogram(df, x="votes", nbins=30, title="Distribution of Candidate Votes")
    st.plotly_chart(fig, use_container_width=True)

    # Overperformers (vs ward average)
    if "ward" in df.columns:
        ward_avg = df.groupby("ward")["votes"].mean().reset_index().rename(columns={"votes":"ward_avg"})
        df_perf = df.merge(ward_avg, on="ward", how="left")
        df_perf["performance_ratio"] = df_perf["votes"] / df_perf["ward_avg"]
        top_perf = df_perf.sort_values("performance_ratio", ascending=False).head(20)
        st.write("🔥 Top 20 Overperforming Candidates (vs Ward Avg):")
        st.dataframe(top_perf[["candidate_name","party","ward","votes","ward_avg","performance_ratio"]])

# ---------------- Gender Insights ----------------
if "gender" in df.columns:
    gender_perf = df.groupby(["gender","party"])["votes"].sum().reset_index()
    st.write("**Performance by gender & party:**")
    st.dataframe(gender_perf)

    fig = px.bar(gender_perf, x="party", y="votes", color="gender",
                 title="Performance by Gender & Party", barmode="stack")
    st.plotly_chart(fig, use_container_width=True)

    # Winning candidates by gender
    if "candidate_name" in df.columns and "position" in df.columns:
        winners = df.loc[df.groupby("position")["votes"].idxmax()]
        gender_wins = winners.groupby("gender")["candidate_name"].count().reset_index()
        st.write("🏆 Winning Candidates by Gender:")
        st.dataframe(gender_wins)

# ---------------- Age Insights ----------------
if "age_group" in df.columns:
    age_perf = df.groupby(["age_group","party"])["votes"].sum().reset_index()
    st.write("**Performance by age group & party:**")
    st.dataframe(age_perf)

    fig = px.bar(age_perf, x="age_group", y="votes", color="party",
                 title="Votes by Age Group & Party", barmode="group")
    st.plotly_chart(fig, use_container_width=True)

    # Avg. votes per candidate by age group
    age_success = df.groupby("age_group")["votes"].mean().reset_index().rename(columns={"votes":"avg_votes"})
    st.write("⭐ Average Votes per Candidate by Age Group:")
    st.dataframe(age_success)

    fig = px.line(age_success, x="age_group", y="avg_votes", markers=True,
                  title="Avg. Candidate Votes by Age Group")
    st.plotly_chart(fig, use_container_width=True)

# ---------------- Party Loyalty Indicator ----------------
party_concentration = df.groupby("party")["votes"].apply(
    lambda x: (x.max()/x.sum())*100 if x.sum() > 0 else 0
).reset_index()
party_concentration.rename(columns={"votes":"max_candidate_share"}, inplace=True)
st.write("📌 Party Loyalty Indicator (Max Candidate’s % of Party Votes):")
st.dataframe(party_concentration)

