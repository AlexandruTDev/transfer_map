import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx

# --- CONFIG ---
DATA_FILE = "data/processed/transfer_base_table.csv"
st.set_page_config(layout="wide", page_title="Romanian Football Analytics Hub")

# --- 🎨 THEME OVERRIDE (CSS) ---
# FIXED: Removed the broken slider CSS. Only coloring the Multiselect Tags blue now.
st.markdown("""
<style>
    /* Change the background color of the 'tags' in multiselect to Blue */
    span[data-baseweb="tag"] {
        background-color: #1f77b4 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def calculate_age(row):
    try:
        if pd.isna(row['Date_of_Birth']): return None
        dob_str = str(row['Date_of_Birth'])
        if '/' in dob_str:
            birth_year = int(dob_str.split('/')[-1])
        elif '-' in dob_str:
            birth_year = int(dob_str.split('-')[0])
        else:
            return None
        season_start = int("20" + str(row['Season']).split('/')[0])
        return season_start - birth_year
    except:
        return None

def normalize_transfer_type(row):
    t_type = str(row['Transfer_Type']).lower()
    fee_val = float(row['Fee_Est_M']) if pd.notna(row['Fee_Est_M']) else 0.0
    if "loan" in t_type: return "Loan"
    elif fee_val > 0: return "Fee"
    else: return "Free"

def classify_migration(row):
    origin_ro = row['Origin_Country'] == 'Romania'
    dest_ro = row['Destination_Country'] == 'Romania'
    citizenship = str(row['Citizenship']).strip()
    is_national = 'Romania' in citizenship 
    
    if origin_ro and dest_ro:
        return "Domestic Move"
    elif origin_ro and not dest_ro:
        return "Export (Out)"
    elif not origin_ro and dest_ro:
        if is_national:
            return "Repatriation (Return)"
        else:
            return "Foreign Import"
    else:
        return "External"

# --- LOAD DATA ---
@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(DATA_FILE, low_memory=False)
        bad_values = ["TBD", "Unknown", "nan", "Retired", "Without Club", "Disqualification"]
        mask = (
            (~df['Origin_League'].isin(bad_values)) & 
            (~df['Destination_League'].isin(bad_values)) &
            (df['Origin_League'].notna()) & 
            (df['Destination_League'].notna()) &
            (df['Origin_Country'].notna()) & 
            (df['Destination_Country'].notna())
        )
        data = df[mask].copy()
        
        data['Origin_Label'] = data['Origin_Country'] + ": " + data['Origin_League']
        data['Destination_Label'] = data['Destination_Country'] + ": " + data['Destination_League']
        data['Age'] = data.apply(calculate_age, axis=1)
        data['Fee_Est_M'] = pd.to_numeric(data['Fee_Est_M'], errors='coerce').fillna(0.0)
        data['UI_Type'] = data.apply(normalize_transfer_type, axis=1)
        data['Migration_Type'] = data.apply(classify_migration, axis=1)
        
        return data
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.error(f"❌ Data file not found: {DATA_FILE}")
    st.stop()

# ==============================================================================
# 🌍 SIDEBAR: ABOUT & FILTERS
# ==============================================================================

# --- 1. ABOUT SECTION ---
st.sidebar.title("🇷🇴 RO Transfer Hub")
with st.sidebar.expander("ℹ️ About & Methodology", expanded=False):
    st.markdown("""
    **What is this?**
    A visual intelligence tool for analyzing transfer flows in the Romanian ecosystem.
    
    **Data Source:**
    Processed data derived from Transfermarkt public records.
    
    **Definitions:**
    * **Repatriation:** A player with Romanian citizenship transferring from a foreign league back to Romania.
    * **Foreign Import:** A non-Romanian player transferring to Romania.
    * **Fee Estimates:** Values are in € Millions. 'Free' transfers are treated as €0.
    
    **How to use:**
    * Use the global filters below to slice the data by Season, Age, or Cost, then use the Tabs to explore Flows vs. Networks.
    * Use the **Path Analyzer** (bottom of the page) to view details of the parties involved in transfers across leagues. (I.E. Italy -> Superliga)
    * Use the **Club Networks tab** to see an overview between club interactions and identify strong partnerships.
    * By hovering over a specific flow in the chart, you can see the path direction (from/to) and the volume of players transferred.
    * The Internal (Domestic) option shows the player movements between Romanian leagues only.
    """)

st.sidebar.markdown("---")
st.sidebar.header("🌍 Global Filters")

# --- 2. FILTERS ---
selected_seasons = st.sidebar.multiselect(
    "📅 Seasons", sorted(df['Season'].unique()), default=sorted(df['Season'].unique())
)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Player Metrics")

min_a = int(df['Age'].min()) if df['Age'].notna().any() else 15
max_a = int(df['Age'].max()) if df['Age'].notna().any() else 40
selected_age = st.sidebar.slider("🎂 Player Age", min_a, max_a, (16, 38))

all_types = ["Loan", "Free", "Fee"]
selected_types = st.sidebar.multiselect("🔀 Transfer Type", all_types, default=all_types)

min_fee = 0.0
if "Fee" in selected_types:
    max_fee_data = df['Fee_Est_M'].max()
    slider_max = float(max_fee_data) if max_fee_data > 0 else 5.0
    min_fee = st.sidebar.slider("💰 Min. Fee (€ Millions)", 0.0, slider_max, 0.0, 0.05)

# Apply Global Filters
filtered_df = df[df['Season'].isin(selected_seasons)].copy()
filtered_df = filtered_df[
    (filtered_df['Age'] >= selected_age[0]) & 
    (filtered_df['Age'] <= selected_age[1]) &
    (filtered_df['UI_Type'].isin(selected_types))
]
if min_fee > 0:
    condition = (filtered_df['UI_Type'] != 'Fee') | (filtered_df['Fee_Est_M'] >= min_fee)
    filtered_df = filtered_df[condition]

# --- TABS ---
tab1, tab2 = st.tabs(["🗺️ Player Transit Map (Sankey)", "🕸️ Club Networks (Partnerships)"])

# ==============================================================================
# TAB 1: SANKEY
# ==============================================================================
with tab1:
    st.header("🗺️ Player Transit Map")
    
    c_view1, c_view2, c_view3 = st.columns([1, 2, 2])
    with c_view1:
        min_flow = st.slider("🔍 Minimum Trasnfers Made", 1, 50, 3)
    with c_view2:
        view_mode = st.radio("Focus Mode", ["Imports (In to RO)", "Exports (Out of RO)", "Internal (Domestic)"], horizontal=True)

    # Context-Aware Migration Filter
    valid_migrations = []
    if view_mode == "Imports (In to RO)":
        valid_migrations = ["Foreign Import", "Repatriation (Return)"]
    elif view_mode == "Internal (Domestic)":
        valid_migrations = ["Domestic Move"]

    with c_view3:
        if len(valid_migrations) > 1: 
            selected_migrations = st.multiselect("🛂 Filter Migration Pattern", options=valid_migrations, default=valid_migrations)
        else:
            if view_mode == "Exports (Out of RO)":
                st.caption("✅ Showing all exports")
                selected_migrations = ["Export (Out)"]
            else:
                st.caption("✅ Showing all domestic moves")
                selected_migrations = ["Domestic Move"]

    # Filter Data
    sankey_df = filtered_df.copy()
    sankey_df = sankey_df[sankey_df['Migration_Type'].isin(selected_migrations)]

    if view_mode == "Imports (In to RO)":
        sankey_df = sankey_df[(sankey_df['Origin_Country'] != "Romania") & (sankey_df['Destination_Country'] == "Romania")]
    elif view_mode == "Exports (Out of RO)":
        sankey_df = sankey_df[(sankey_df['Origin_Country'] == "Romania") & (sankey_df['Destination_Country'] != "Romania")]
    elif view_mode == "Internal (Domestic)":
        sankey_df = sankey_df[
            (sankey_df['Origin_Country'] == "Romania") & 
            (sankey_df['Destination_Country'] == "Romania") & 
            (sankey_df['Origin_League'] != sankey_df['Destination_League']) 
        ]

    flows = sankey_df.groupby(['Origin_Label', 'Destination_Label']).size().reset_index(name='Count')
    flows = flows[flows['Count'] >= min_flow]

    if not flows.empty:
        all_nodes = list(pd.concat([flows['Origin_Label'], flows['Destination_Label']]).unique())
        node_map = {name: i for i, name in enumerate(all_nodes)}
        
        if view_mode == "Internal (Domestic)":
            st.info("**Legend:** 🔵 **Blue:** SuperLiga (Down) | 🟠 **Orange:** Liga 2 (Up) | 🟢 **Green:** Youth/Liga 3")
        
        node_colors = []
        for node in all_nodes:
            if "romania:" in node.lower():
                if "superliga" in node.lower(): node_colors.append("#1f77b4")
                elif "liga 2" in node.lower(): node_colors.append("#ff7f0e")
                else: node_colors.append("#2ca02c")
            else:
                node_colors.append("#e6e6e6")

        link_colors = []
        if view_mode == "Internal (Domestic)":
            for _, row in flows.iterrows():
                src = row['Origin_Label'].lower()
                if "romania:" in src:
                    if "superliga" in src: link_colors.append("rgba(31, 119, 180, 0.4)")
                    elif "liga 2" in src: link_colors.append("rgba(255, 127, 14, 0.4)")
                    else: link_colors.append("rgba(44, 160, 44, 0.4)")
                else: link_colors.append("rgba(200, 200, 200, 0.3)")
        else:
            for count in flows['Count']:
                if count >= 10: link_colors.append("rgba(200, 0, 0, 0.6)")
                elif count >= 5: link_colors.append("rgba(255, 165, 0, 0.6)")
                else: link_colors.append("rgba(180, 180, 180, 0.4)")

        flows['Source_ID'] = flows['Origin_Label'].map(node_map)
        flows['Target_ID'] = flows['Destination_Label'].map(node_map)
        
        fig = go.Figure(data=[go.Sankey(
            textfont=dict(size=13, color="black", family="Arial Black"),
            node=dict(pad=20, thickness=20, line=dict(color="black", width=0.5), label=all_nodes, color=node_colors, hovertemplate='<b>%{label}</b><br>Volume: %{value}<extra></extra>'),
            link=dict(source=flows['Source_ID'], target=flows['Target_ID'], value=flows['Count'], color=link_colors, hovertemplate='%{source.label} ➔ %{target.label}<br><b>%{value} Players</b><extra></extra>')
        )])
        fig.update_layout(height=max(600, len(all_nodes) * 35), margin=dict(l=10, r=10, t=30, b=30))
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🕵️ Path Analyzer")
        flow_options = flows.apply(lambda x: f"{x['Origin_Label']} ➔ {x['Destination_Label']} ({x['Count']} players)", axis=1).tolist()
        selected_flow = st.selectbox("Select a Route to Inspect:", ["Select a route..."] + sorted(flow_options))
        if selected_flow and selected_flow != "Select a route...":
            parts = selected_flow.split(" ➔ ")
            inspector_df = sankey_df[(sankey_df['Origin_Label'] == parts[0]) & (sankey_df['Destination_Label'] == parts[1].split(" (")[0])]
            
            citizenship_counts = inspector_df['Citizenship'].value_counts().reset_index()
            citizenship_counts.columns = ['Nation', 'Count']
            club_breakdown = inspector_df.groupby(['Origin_Club', 'Destination_Club']).size().reset_index(name='Transfers').sort_values(by='Transfers', ascending=False)
            
            c_insp1, c_insp2, c_insp3 = st.columns([1, 1, 2])
            with c_insp1:
                st.markdown("**Nationality Breakdown**")
                fig_pie = px.pie(citizenship_counts, values='Count', names='Nation', hole=0.4)
                fig_pie.update_layout(height=250, margin=dict(t=0,b=0,l=0,r=0), showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)
            with c_insp2:
                st.markdown("**Top Connectors**")
                st.dataframe(club_breakdown[['Origin_Club', 'Destination_Club', 'Transfers']], use_container_width=True, hide_index=True)
            with c_insp3:
                st.markdown("**📋 Player Manifest**")
                manifest = inspector_df[['Player_Name', 'Age', 'Citizenship', 'Fee_Est_M', 'Transfer_Type']].sort_values(by='Fee_Est_M', ascending=False)
                st.dataframe(manifest, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ No transfers found.")

# ==============================================================================
# TAB 2: CLUB NETWORK
# ==============================================================================
with tab2:
    st.header("🕸️ Club Partnership Networks")
    c_net1, c_net2, c_net3 = st.columns([1, 1, 2])
    with c_net1: network_scope = st.radio("Network Scope", ["SuperLiga Internal", "SuperLiga ↔ Liga 2", "All Domestic"])
    with c_net2: min_strength = st.slider("Minimum Transfers Made", 1, 20, 3, key="net_strength")

    net_df = filtered_df.copy()
    if network_scope == "SuperLiga Internal":
        net_df = net_df[(net_df['Origin_League'] == 'Superliga') & (net_df['Destination_League'] == 'Superliga') & (net_df['Origin_Country'] == 'Romania')]
    elif network_scope == "SuperLiga ↔ Liga 2":
        net_df = net_df[((net_df['Origin_League'] == 'Superliga') & (net_df['Destination_League'] == 'Liga 2')) | ((net_df['Origin_League'] == 'Liga 2') & (net_df['Destination_League'] == 'Superliga'))]
    elif network_scope == "All Domestic":
        net_df = net_df[(net_df['Origin_Country'] == 'Romania') & (net_df['Destination_Country'] == 'Romania')]
    
    edges_df = net_df.groupby(['Origin_Club', 'Destination_Club']).size().reset_index(name='Weight')
    edges_df = edges_df[edges_df['Weight'] >= min_strength]

    if not edges_df.empty:
        unique_clubs = sorted(list(set(edges_df['Origin_Club']).union(set(edges_df['Destination_Club']))))
        with c_net3:
            focus_club = st.selectbox("🎯 Focus on specific Club:", ["Show Whole Network"] + unique_clubs)
            direction_mode = "All Interactions"
            if focus_club != "Show Whole Network":
                direction_mode = st.radio("Show Relationship:", ["All Interactions", "Incoming (Buying From)", "Outgoing (Selling To)"], horizontal=True)

        if focus_club != "Show Whole Network":
            if direction_mode == "Incoming (Buying From)":
                edges_df = edges_df[edges_df['Destination_Club'] == focus_club]
                table_title = f"Top Sellers to {focus_club}"
            elif direction_mode == "Outgoing (Selling To)":
                edges_df = edges_df[edges_df['Origin_Club'] == focus_club]
                table_title = f"Top Buyers from {focus_club}"
            else:
                edges_df = edges_df[(edges_df['Origin_Club'] == focus_club) | (edges_df['Destination_Club'] == focus_club)]
                table_title = f"Top Partners for {focus_club}"
        else:
            table_title = "Top Partnerships"

        if edges_df.empty:
             st.warning(f"No connections found.")
        else:
            G = nx.from_pandas_edgelist(edges_df, 'Origin_Club', 'Destination_Club', ['Weight'])
            pos = nx.spring_layout(G, k=2.0, seed=42, iterations=50)
            edge_x, edge_y = [], []
            for edge in G.edges(data=True):
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
            edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=1, color='#888'), hoverinfo='none', mode='lines')
            node_x, node_y, node_text, node_size, node_colors = [], [], [], [], []
            for node in G.nodes():
                x, y = pos[node]
                node_x.append(x)
                node_y.append(y)
                in_degree = G.degree(node)
                node_size.append(10 + (in_degree * 2))
                if focus_club != "Show Whole Network" and node == focus_club: node_colors.append("red")
                else: node_colors.append("#1f77b4")
            node_trace = go.Scatter(x=node_x, y=node_y, mode='markers+text', text=[node for node in G.nodes()], textposition="top center", hoverinfo='text', marker=dict(showscale=False, color=node_colors, size=node_size, line_width=2))
            node_trace.textfont = dict(size=10, color="black")
            fig_net = go.Figure(data=[edge_trace, node_trace], layout=go.Layout(showlegend=False, hovermode='closest', margin=dict(b=0,l=0,r=0,t=0), height=700, xaxis=dict(showgrid=False, zeroline=False, showticklabels=False), yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)))
            
            c_g, c_d = st.columns([2.5, 1.5])
            with c_g: st.plotly_chart(fig_net, use_container_width=True)
            with c_d:
                st.markdown(f"### 🏆 {table_title}")
                display_df = edges_df.copy()
                if focus_club != "Show Whole Network":
                     if direction_mode == "Incoming (Buying From)": display_df = display_df[['Origin_Club', 'Weight']].rename(columns={'Origin_Club': 'Seller Club', 'Weight': '# of transfers'})
                     elif direction_mode == "Outgoing (Selling To)": display_df = display_df[['Destination_Club', 'Weight']].rename(columns={'Destination_Club': 'Buyer Club', 'Weight': '# of transfers'})
                else:
                    display_df.rename(columns={'Weight': '# of transfers'}, inplace=True)
                
                st.dataframe(display_df.sort_values(by='# of transfers', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ No connections found.")