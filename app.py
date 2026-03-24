
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import wikipedia

st.set_page_config(page_title="Cricket Strategy Intelligence", layout="wide")

# -------------------------
# RELIABLE IMAGE FUNCTION
# -------------------------
@st.cache_data(ttl=3600)
def get_player_image(player_name):
    try:
        search_query = f"{player_name} cricketer profile"
        search_results = wikipedia.search(search_query)
        if search_results:
            page = wikipedia.page(search_results[0], auto_suggest=False)
            for img in page.images:
                if img.lower().endswith(('.jpg', '.png', '.jpeg')) and "commons" in img.lower():
                    return img
        return f"https://ui-avatars.com/api/?name={player_name}&size=250&background=random"
    except:
        return f"https://ui-avatars.com/api/?name={player_name}&size=250&background=random"

# -------------------------
# DATA LOADING & PROCESSING
# -------------------------
@st.cache_data
def load_and_process_all():
    df = pd.read_csv("IPL.csv")
    cols = ['match_id','innings','batting_team','bowling_team','over','ball','batter','bowler','runs_total']
    df1 = df[cols].copy()
    df1.rename(columns={'match_id':'mid','innings':'inn','batting_team':'bat_team','bowling_team':'bowl_team','batter':'player','runs_total':'runs'}, inplace=True)
    
    # Bowl Type
    spin_list = ['ashwin','narine','chahal','jadeja','kuldeep','axar','rashid','bishnoi','zampa']
    df1['bowl_type'] = df1['bowler'].apply(lambda x: 'spin' if any(s in str(x).lower() for s in spin_list) else 'pace')
    
    # Basic Stats
    p_runs = df1.groupby('player')['runs'].sum().reset_index()
    s_runs = df1[df1['bowl_type']=='spin'].groupby('player')['runs'].sum().reset_index().rename(columns={'runs':'spin_runs'})
    pace_runs = df1[df1['bowl_type']=='pace'].groupby('player')['runs'].sum().reset_index().rename(columns={'runs':'pace_runs'})
    
    merged = p_runs.merge(s_runs, on='player', how='left').merge(pace_runs, on='player', how='left').fillna(0)
    
    # Phase Analysis
    df1['phase'] = df1['over'].apply(lambda x: 'Powerplay' if x<=6 else ('Middle' if x<=15 else 'Death'))
    phase_runs = df1.groupby(['player','phase'])['runs'].sum().reset_index()
    best_phase = phase_runs.loc[phase_runs.groupby('player')['runs'].idxmax()]
    merged = merged.merge(best_phase[['player','phase']], on='player', how='left').rename(columns={'phase':'best_phase'})

    # PARTNERSHIP LOGIC (Wapis Add Kiya)
    grp = df1.groupby(['mid','inn'])['player'].apply(list)
    pairs = []
    for lst in grp:
        unique = list(set(lst))
        for i in range(len(unique)):
            for j in range(len(unique)):
                if i != j: pairs.append((unique[i], unique[j]))
    
    pairs_df = pd.DataFrame(pairs, columns=['player','partner'])
    best_partner = pairs_df.groupby(['player','partner']).size().reset_index(name='cnt')
    best_partner = best_partner.sort_values(['player','cnt'], ascending=[True,False]).drop_duplicates('player')
    merged = merged.merge(best_partner[['player','partner']], on='player', how='left').rename(columns={'partner':'best_partner'})

    # Strength & Situation
    merged['spin_strength'] = (merged['spin_runs'] / (merged['runs']+1)).apply(lambda x: 'Strong' if x > 0.3 else 'Average')
    merged['pace_strength'] = (merged['pace_runs'] / (merged['runs']+1)).apply(lambda x: 'Strong' if x > 0.3 else 'Average')
    merged['best_situation'] = merged['spin_strength'].apply(lambda x: 'Middle Overs' if x == 'Strong' else 'Powerplay')
    
    return df1, merged

df1, merged = load_and_process_all()

# -------------------------
# PLAYER UI
# -------------------------
st.title("🏏 Cricket Strategy Intelligence System")
st.subheader("🔍 Player Analysis")
name = st.text_input("Enter player name")

if name:
    res = merged[merged['player'].str.contains(name, case=False, na=False)]
    if not res.empty:
        r = res.iloc[0]
        c1, c2 = st.columns([1, 2])
        with c1:
            img = get_player_image(r['player'])
            st.image(img, width=250, caption=r['player'])
        with c2:
            st.markdown(f"### {r['player']} Analysis")
            st.write(f"**Total Runs:** {int(r['runs'])}")
            st.write(f"**Spin Strength:** {r['spin_strength']} | Pace Strength: {r['pace_strength']}")
            st.write(f"**Best Partner:** {r['best_partner']}")
            st.write(f"**Best Phase:** {r['best_phase']}")
            st.write(f"**Ideal Situation:** {r['best_situation']}")
            
            fig, ax = plt.subplots(figsize=(5, 2))
            ax.barh(['Spin Runs', 'Pace Runs'], [r['spin_runs'], r['pace_runs']], color=['#FF9933', '#000080'])
            st.pyplot(fig)
    else:
        st.error("Player not found!")

# -------------------------
# TEAM VS TEAM PREDICTION
# -------------------------
st.markdown("---")
st.header("📊 Team Head-to-Head Prediction")
teams = sorted(df1['bat_team'].unique())
col_t1, col_t2 = st.columns(2)
with col_t1: t1 = st.selectbox("Team 1", teams, index=0)
with col_t2: t2 = st.selectbox("Team 2", teams, index=1)

if st.button("Predict Head-to-Head"):
    t1_m = df1[df1['bat_team'] == t1]['runs'].mean()
    t2_m = df1[df1['bat_team'] == t2]['runs'].mean()
    p1 = round((t1_m / (t1_m + t2_m)) * 100, 1)
    st.metric(f"{t1} Win %", f"{p1}%")
    st.progress(int(p1))
    st.metric(f"{t2} Win %", f"{100-p1}%")

# -------------------------
# LIVE MATCH PREDICTION (Wapis Add Kiya)
# -------------------------
st.markdown("---")
st.header("📈 Live Match Prediction")
score_col, over_col = st.columns(2)
with score_col:
    curr_score = st.number_input("Current Score", 0, 300, value=150)
with over_col:
    curr_overs = st.number_input("Overs Completed", 1, 20, value=15)

if st.button("Predict Live Win %"):
    rr = curr_score / curr_overs
    win_p = min(round((rr / 12) * 100, 2), 100.0)
    st.write(f"### Predicted Win Probability: **{win_p}%**")
    st.progress(win_p/100)

# -------------------------
# TOSS STRATEGY
# -------------------------
st.markdown("---")
st.header("🪙 Toss Strategy")
pitch = st.selectbox("Pitch", ["Normal", "Dry", "Green"])
dew = st.radio("Dew?", ["Yes", "No"])
if st.button("Get Decision"):
    res = "Bowl First" if dew == "Yes" or pitch == "Normal" else "Bat First"
    st.success(f"Strategic Move: **{res}**")