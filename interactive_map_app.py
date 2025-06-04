# interactive_map_app.py

import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import random
import streamlit as st

# Tile options and attribution
tile_options = {
    'OpenStreetMap': 'OpenStreetMap',
    'CartoDB Positron': 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    'CartoDB Dark Matter': 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    'Esri Satellite': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
}

tile_attribution = {
    'OpenStreetMap': '© OpenStreetMap contributors',
    'CartoDB Positron': '© OpenStreetMap contributors, © CARTO',
    'CartoDB Dark Matter': '© OpenStreetMap contributors, © CARTO',
    'Esri Satellite': 'Tiles © Esri, Maxar, Earthstar Geographics'
}

st.set_page_config(layout="wide")

@st.cache_data
def load_data():
    df = pd.read_excel("Acitivities_cleaned.xlsx")
    # Add jitter columns once, cache the result
    df['lat_jittered'] = df['primary_site_lat'].apply(lambda val: val + random.uniform(-0.001, 0.001))
    df['long_jittered'] = df['primary_site_long'].apply(lambda val: val + random.uniform(-0.001, 0.001))
    return df

def extract_unique(series):
    items = set()
    for entry in series.dropna():
        for item in entry.split(','):
            items.add(item.strip())
    return sorted(items)

def main():
    df = load_data()

    faculty_list = extract_unique(df['faculty_partners'])
    focus_area_list = extract_unique(df['focus_cleaned'])
    activity_list = sorted(df['activity_name'].dropna().unique())
    campus_partner_list = extract_unique(df['campus_partners'])

  # Sidebar filters with reset functionality
    st.sidebar.title("Filters")
    
    # Define default values
    default_values = {
        "faculty": "All",
        "focus": ["All"],
        "activity": "All",
        "campus": "All",
        "tile": "OpenStreetMap"
    }
    
    # Handle reset
    if "reset" not in st.session_state:
        st.session_state.reset = False
    
    if st.sidebar.button("🔄 Reset Filters"):
        st.session_state.faculty = default_values["faculty"]
        st.session_state.focus = default_values["focus"]
        st.session_state.activity = default_values["activity"]
        st.session_state.campus = default_values["campus"]
        st.session_state.tile = default_values["tile"]
    
    # Focus area: include "All" option
    focus_area_list = ["All"] + focus_area_list
    
    # Render widgets with session state
    selected_faculty = st.sidebar.selectbox(
        "Faculty:", ["All"] + faculty_list,
        key="faculty"
    )
    selected_focus = st.sidebar.multiselect(
        "Focus Areas:", focus_area_list,
        default=st.session_state.get("focus", ["All"]),
        key="focus"
    )
    selected_activity = st.sidebar.selectbox(
        "Activity:", ["All"] + activity_list,
        key="activity"
    )
    selected_campus = st.sidebar.selectbox(
        "Campus Partner:", ["All"] + campus_partner_list,
        key="campus"
    )
    selected_tile = st.sidebar.selectbox(
        "Map Style:", list(tile_options.keys()),
        key="tile"
    )

    filtered_df = df.copy()
    if selected_faculty != "All":
        filtered_df = filtered_df[filtered_df['faculty_partners'].fillna("").str.contains(selected_faculty)]

    if selected_focus and "All" not in selected_focus:
        filtered_df = filtered_df[filtered_df['focus_cleaned'].apply(
        lambda x: all(f in x for f in selected_focus) if pd.notna(x) else False)]

    if selected_activity != "All":
        filtered_df = filtered_df[filtered_df['activity_name'] == selected_activity]

    if selected_campus != "All":
        filtered_df = filtered_df[filtered_df['campus_partners'].fillna("").str.contains(selected_campus)]


    # Create map
    m = folium.Map(
        location=[39.8943, -74.1596],  # Latitude, Longitude
        zoom_start=8,
        tiles=None
    )

    folium.TileLayer(
        tiles=tile_options[selected_tile],
        attr=tile_attribution[selected_tile],
        name=selected_tile,
        control=False
    ).add_to(m)

    marker_cluster = MarkerCluster().add_to(m)

    for _, row in filtered_df.iterrows():
        popup_html = f"""
        <div style="width: 300px; font-size: 13px;">
        <b>Activity:</b> <a href="{row['activity_url']}" target="_blank">{row['activity_name']}</a><br>
        <b>Faculty:</b> {row['faculty_partners']}<br>
        <b>Campus Partners:</b> {row['campus_partners']}<br>
        <b>Community Partners:</b> {row['community_organizations']}<br>
        <b>Primary Contact:</b> <a href="mailto:{row['primary_contact_email']}">{row['primary_contact_email']}</a>
        </div>
        """
        folium.CircleMarker(
            location=[row['lat_jittered'], row['long_jittered']],
            radius=10,
            color='red',
            fill=True,
            fill_opacity=0.8,
            popup=popup_html,
            tooltip=row['activity_name']
        ).add_to(marker_cluster)

    st.title("Community Engagement Activities Map")
    st_data = st_folium(m, width=None, height=500)

if __name__ == "__main__":
    main()
