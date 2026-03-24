import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import wikipedia

st.set_page_config(page_title="Cricket Strategy Intelligence", layout="wide")

# -------------------------
# RELIABLE IMAGE FETCHING
# -------------------------
@st.cache_data(ttl=3600)
def get_p_img(name):
    if pd.isna(name) or name == "N/A" or not str(name).strip():
        return "https://ui-avatars.com/api/?name=NA&size=250"
    try:
        results = wikipedia.search(str(name) + " cricketer")
        if results:
            page = wikipedia.page(results[0], auto_suggest=False)
            for img in page.images:
                if img.lower().endswith(('.jpg', '.jpeg', '.png')) and "commons" in img.lower():
                    return img
        return f"https://ui-avatars.com/api/?name={name}&background=random"
    except:
        return f"https://ui-avatars.com/api/?name={name}&background=random"

# -------------------------
# DATA PROCESSING ENGINE
# -------------------------
@st.cache_data
def load_and_process():
    df = pd.read_csv("IPL.csv")
    
    # Standarize column names for ease
    df.rename(columns={'batter': 'player', 'runs_total': 'runs'}, inplace=True)
    
    # 1. BATTING STATS
    p_bat = df.groupby('player').agg(runs=('runs', 'sum'), balls_faced=('ball', 'count')).reset_index()
    p_bat['strike_rate'] = (p_bat['runs'] / p_bat['balls_faced'] * 100).round(2)
    
    # 2. BOWLING STATS
    p_bowl = df.groupby('bowler').agg(runs_conceded=('runs', 'sum'), wickets=('player_out', 'count'), balls_bowled=('ball', 'count')).reset_index()
    p_bowl['economy'] = (p_bowl['runs_conceded'] / (p_bowl['balls_bowled'] / 6)).round(2)
    p_bowl.rename(columns={'bowler': 'player'}, inplace=True)
    
    # 3. BASE & ROLE (Categorize Players)
    base = pd.merge(p_bat, p_bowl[['player', 'wickets', 'economy']], on='player', how='outer').fillna(0)
    
    def assign_role(row):
        if row['wickets'] >= 15 and row['runs'] >= 400: return "All-Rounder"
        if row['wickets'] >= 15 and row['runs'] < 400: return "Bowler"
        return "Batsman"
        
    base['role'] = base.apply(assign_role, axis=1)

    # 4. BEST PARTNER (Batsman)
    pairs = []
    for _, g in df.groupby(['match_id', 'innings']):
        players = g['player'].unique()
        for i in range(len(players)):
            for j in range(len(players)):
                if i != j: pairs.append((players[i], players[j]))
                
    best_partner = pd.DataFrame(pairs, columns=['player', 'partner']).groupby(['player', 'partner']).size().reset_index(name='count')
    best_partner = best_partner.sort_values(['player', 'count'], ascending=[True, False]).drop_duplicates('player')
    
    # 5. NEMESIS & VICTIM
    outs = df[df['player_out'].notna()]
    nemesis = outs.groupby(['player_out', 'bowler']).size().reset_index(name='count').sort_values(['player_out', 'count'], ascending=[True, False]).drop_duplicates('player_out')
    nemesis.rename(columns={'player_out': 'player', 'bowler': 'nemesis_bowler'}, inplace=True)
    
    victim = outs.groupby(['bowler', 'player_out']).size().reset_index(name='count').sort_values(['bowler', 'count'], ascending=[True, False]).drop_duplicates('bowler')
    victim.rename(columns={'bowler': 'player', 'player_out': 'best_victim'}, inplace=True)
    
    # 6. SPIN VS PACE & PHASE
    spinners = ['ashwin','narine','chahal','jadeja','kuldeep','axar','rashid','bishnoi','zampa']
    df['is_spin'] = df['bowler'].str.lower().str.contains('|'.join(spinners), na=False)
    spin_runs = df[df['is_spin']].groupby('player')['runs'].sum().reset_index(name='spin_runs')
    pace_runs = df[~df['is_spin']].groupby('player')['runs'].sum().reset_index(name='pace_runs')
    
    df['phase'] = df['over'].apply(lambda x: 'Powerplay' if x<=6 else ('Middle' if x<=15 else 'Death'))
    best_phase = df.groupby(['player', 'phase'])['runs'].sum().reset_index().sort_values(['player', 'runs'], ascending=[True, False]).drop_duplicates('player')

    # 7. FINAL SAFE MERGE
    final = base.copy()
    for df_to_merge in [best_partner[['player', 'partner']], nemesis[['player', 'nemesis_bowler']], 
                        victim[['player', 'best_victim']], spin_runs, pace_runs, best_phase[['player', 'phase']]]:
        final = final.merge(df_to_merge, on='player', how='left')
    
    return df, final

# Load the data
df_main, merged_data = load_and_process()

# -------------------------
# PLAYER ANALYSIS UI
# -------------------------
st.title("🏏 Cricket Strategy Intelligence System")
st.markdown("---")
name_input = st.text_input("Search Player (e.g. MS Dhoni, Z Khan, Hardik Pandya)")

if name_input:
    res = merged_data[merged_data['player'].str.contains(name_input, case=False, na=False)]
    if not res.empty:
        r = res.iloc[0].to_dict() 
        
        # BULLETPROOF VARIABLES
        role = r.get('role', 'Batsman')
        player_name = r.get('player', 'Unknown')
        
        partner = r.get('partner', 'N/A')
        if pd.isna(partner): partner = 'N/A'
        
        nemesis = r.get('nemesis_bowler', 'N/A')
        if pd.isna(nemesis): nemesis = 'N/A'
        
        victim = r.get('best_victim', 'N/A')
        if pd.isna(victim): victim = 'N/A'
        
        # Stats variables
        runs = int(r.get('runs', 0))
        wickets = int(r.get('wickets', 0))
        eco = r.get('economy', 0.0)
        sr = r.get('strike_rate', 0.0)
        phase = r.get('phase', 'N/A')
        spin_r = r.get('spin_runs', 0)
        pace_r = r.get('pace_runs', 0)

        # ----------------- ALL-ROUNDER LAYOUT (4 Images) -----------------
        if role == "All-Rounder":
            st.subheader(f"⚔️ All-Rounder Profile: {player_name}")
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.image(get_p_img(player_name), caption=f"Main: {player_name}", use_container_width=True)
            with c2: st.image(get_p_img(partner), caption=f"Partner: {partner}", use_container_width=True)
            with c3: st.image(get_p_img(victim), caption=f"Top Victim: {victim}", use_container_width=True)
            with c4: st.image(get_p_img(nemesis), caption=f"Nemesis: {nemesis}", use_container_width=True)
            
            st.markdown("---")
            st.subheader("📊 Complete Stats (Bat & Bowl)")
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                st.write(f"**Total Runs:** {runs} | Strike Rate: {sr}")
                st.write(f"**Total Wickets:** {wickets} | Economy: {eco}")
            with col_b2:
                st.write(f"**Best Phase (Bat):** {phase}")
                st.write(f"**Best Partner:** {partner}")
            with col_b3:
                st.write(f"**Top Target (Bowl):** {victim}")
                st.write(f"**Biggest Threat (Bat):** {nemesis}")

        # ----------------- BOWLER LAYOUT (2 Images) -----------------
        elif role == "Bowler":
            st.subheader(f"🎯 Bowler Profile: {player_name}")
            c1, c_vs, c2 = st.columns([1, 0.2, 1])
            with c1: st.image(get_p_img(player_name), caption=f"Main: {player_name}", width=250)
            with c_vs: st.markdown("<h1 style='text-align: center; margin-top: 100px;'>VS</h1>", unsafe_allow_html=True)
            with c2: st.image(get_p_img(victim), caption=f"Top Victim: {victim}", width=250)
            
            st.markdown("---")
            b1, b2, b3 = st.columns(3)
            b1.metric("Total Wickets", wickets)
            b2.metric("Economy Rate", eco)
            b3.metric("Best Spell / Target", victim)

        # ----------------- BATSMAN LAYOUT (3 Images) -----------------
        else:
            st.subheader(f"🤝 Matchup & Partnerships: {player_name}")
            col_p, col_vs, col_n = st.columns([1.5, 0.2, 1])
            with col_p:
                sc1, sc2 = st.columns(2)
                sc1.image(get_p_img(player_name), caption=f"Main: {player_name}", use_container_width=True)
                sc2.image(get_p_img(partner), caption=f"Best Partner: {partner}", use_container_width=True)
            with col_vs: st.markdown("<h1 style='text-align: center; margin-top: 80px;'>VS</h1>", unsafe_allow_html=True)
            with col_n: st.image(get_p_img(nemesis), caption=f"Nemesis: {nemesis}", width=200)

            st.markdown("---")
            st.subheader("📊 Detailed Performance")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.write(f"**Role:** {role}")
                st.write(f"**Best Phase:** {phase}")
                st.write(f"**Best Partner:** {partner}")
            with a2:
                spin_s = "Strong" if spin_r >= pace_r else "Average"
                pace_s = "Strong" if pace_r > spin_r else "Average"
                st.write(f"**Spin Strength:** {spin_s}")
                st.write(f"**Pace Strength:** {pace_s}")
                st.write(f"**Strike Rate:** {sr}")
            with a3:
                st.write(f"**Ideal Situation:** {phase} Dominance")
                st.write(f"**Biggest Threat:** {nemesis}")

        # ----------------- MAP / GRAPH (For Batsman & All-Rounder) -----------------
        if role in ["Batsman", "All-Rounder"]:
            st.markdown("<br>", unsafe_allow_html=True)
            fig, ax = plt.subplots(figsize=(8, 2))
            ax.barh(['Spin Runs', 'Pace Runs'], [spin_r, pace_r], color=['#FF9933', '#000080'])
            ax.set_title("Runs Distribution Map")
            st.pyplot(fig)
            
    else:
        st.error("Player not found in database. Please check the spelling.")

# =========================================================
# EXTRA SECTIONS: HEAD-TO-HEAD, TOSS STRATEGY, LIVE WIN PREDICTION
# =========================================================

st.markdown("---")
st.header("⚔️ Team & Match Strategy")

col_t1, col_t2, col_t3 = st.columns(3)

# 1. TEAM HEAD TO HEAD PREDICTION
with col_t1:
    st.subheader("Head-to-Head Prediction")
    teams = sorted(df_main['batting_team'].dropna().unique())
    team_a = st.selectbox("Team 1", teams, index=0)
    team_b = st.selectbox("Team 2", teams, index=1 if len(teams)>1 else 0)

    if st.button("Predict Win Percentage"):
        if team_a == team_b:
            st.warning("Please select different teams.")
        else:
            t1_runs = df_main[df_main['batting_team'] == team_a]['runs'].mean()
            t2_runs = df_main[df_main['batting_team'] == team_b]['runs'].mean()
            
            if (t1_runs + t2_runs) > 0:
                p1 = round((t1_runs / (t1_runs + t2_runs)) * 100, 1)
            else:
                p1 = 50.0
                
            st.write(f"### {team_a}: {p1}%")
            st.write(f"### {team_b}: {round(100 - p1, 1)}%")
            st.progress(int(p1))

# 2. TOSS STRATEGY
with col_t2:
    st.subheader("🪙 Toss Strategy")
    pitch_type = st.selectbox("Pitch Condition", ["Dry", "Normal", "Green"])
    dew_factor = st.radio("Dew Factor?", ["No", "Yes"])
    
    if st.button("Get Strategic Move"):
        if dew_factor == "Yes" or pitch_type == "Normal":
            st.info("🏏 Decision: Bowl First (Advantage chasing due to conditions)")
        else:
            st.success("🏏 Decision: Bat First (Pitch likely to slow down)")

# 3. LIVE WIN PREDICTION
with col_t3:
    st.subheader("📈 Live Win Prediction")
    score = st.number_input("Current Score", min_value=0, max_value=400, value=150)
    overs = st.number_input("Overs Completed", min_value=1.0, max_value=20.0, value=15.0)

    if st.button("Calculate Live Probability"):
        run_rate = score / overs
        win_chance = min(round((run_rate / 11.5) * 100, 2), 100.0)
        st.metric(label="Estimated Win Probability", value=f"{win_chance}%")