import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import random

# Function to add jitter
def add_jitter(val, scale=0.001):
    return val + random.uniform(-scale, scale)

# Extract unique values from comma-separated fields
def extract_unique(series):
    items = set()
    for entry in series.dropna():
        for item in entry.split(','):
            items.add(item.strip())
    return sorted(items)

# Load and preprocess data
@st.cache_data
def load_data():
    df = pd.read_excel("Activities_cleaned.xlsx")
    df['lat_jittered'] = df['primary_site_lat'].apply(add_jitter)
    df['long_jittered'] = df['primary_site_long'].apply(add_jitter)
    return df

final_df = load_data()

# Dropdown options
faculty_list = extract_unique(final_df['faculty_partners'])
focus_area_list = extract_unique(final_df['focus_cleaned'])
activity_list = sorted(final_df['activity_name'].dropna().unique())
campus_partner_list = extract_unique(final_df['campus_partners'])

# Streamlit UI
st.title("Interactive Map of Activities")

selected_faculty = st.sidebar.selectbox("Faculty:", ['All'] + faculty_list)
selected_focus = st.sidebar.selectbox("Focus Area:", ['All'] + focus_area_list)
selected_activity = st.sidebar.selectbox("Activity:", ['All'] + activity_list)
selected_campus = st.sidebar.selectbox("Campus Partner:", ['All'] + campus_partner_list)

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
    'Esri Satellite': 'Tiles © Esri, Maxar, Earthstar Geographics, and the GIS User Community'
}
selected_tile = st.sidebar.selectbox('Map Style:', list(tile_options.keys()))

if st.sidebar.button("Reset Filters"):
    selected_faculty = 'All'
    selected_focus = 'All'
    selected_activity = 'All'
    selected_campus = 'All'
    selected_tile = 'OpenStreetMap'

# Filtering logic
def row_matches(row):
    faculty_names = extract_unique(pd.Series(row['faculty_partners'])) if pd.notna(row['faculty_partners']) else []
    campus_names = extract_unique(pd.Series(row['campus_partners'])) if pd.notna(row['campus_partners']) else []
    focus_cleaned_str = str(row['focus_cleaned']).strip().lower()

    faculty_match = (selected_faculty == 'All' or selected_faculty in faculty_names)
    focus_match = (selected_focus == 'All' or selected_focus.lower() in focus_cleaned_str)
    activity_match = (selected_activity == 'All' or selected_activity == row['activity_name'])
    campus_match = (selected_campus == 'All' or selected_campus in campus_names)

    return faculty_match and focus_match and activity_match and campus_match

filtered_df = final_df[final_df.apply(row_matches, axis=1)]

# Create the map
m = folium.Map(
    location=[final_df['lat_jittered'].mean(), final_df['long_jittered'].mean()],
    zoom_start=9,
    control_scale=True,
    tiles=None
)

folium.TileLayer(
    tiles=tile_options[selected_tile],
    attr=tile_attribution[selected_tile],
    name=selected_tile,
    control=False
).add_to(m)

marker_cluster = MarkerCluster().add_to(m)

# Add markers with formatted HTML popup
for _, row in filtered_df.iterrows():
    # Create clickable link for primary contact if faculty_url exists
    primary_contact = str(row['primary_contact']).strip()
    faculty_url = str(row.get('faculty_url', '')).strip()
    if primary_contact and faculty_url and faculty_url.lower() != 'nan':
        primary_contact_html = f'<a href="{faculty_url}" target="_blank">{primary_contact}</a>'
    elif primary_contact:
        primary_contact_html = primary_contact
    else:
        primary_contact_html = 'N/A'

    # Build popup HTML content
    popup_html = f"""
    <div style="width: 300px; font-size: 13px;">
        <b>Activity:</b> <a href="{row['activity_url']}" target="_blank">{row['activity_name']}</a><br>
        <b>Faculty:</b> {row['faculty_partners']}<br>
        <b>Campus Partners:</b> {row['campus_partners']}<br>
        <b>Community Partners:</b> {row['community_organizations']}<br>
        <b>Primary Contact:</b> {primary_contact_html}<br>
        <b>Email:</b> <a href="mailto:{row['primary_contact_email']}">{row['primary_contact_email']}</a>
    </div>
    """

    iframe = folium.IFrame(popup_html, width=300, height=180)
    popup = folium.Popup(iframe, max_width=300)

    folium.CircleMarker(
        location=[row['lat_jittered'], row['long_jittered']],
        radius=7,
        color='red',
        fill=True,
        fill_opacity=0.8,
        popup=popup,
        tooltip=row['activity_name']
    ).add_to(marker_cluster)

# Render map
st_data = st_folium(m, width=700, height=500)
