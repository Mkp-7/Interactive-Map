import streamlit as st
import pandas as pd
import folium
import requests
import random
from shapely.geometry import shape, Point, MultiPolygon, Polygon
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

st.set_page_config(layout="wide")

# Load NJ counties GeoJSON
@st.cache_data
def load_nj_counties():
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    geojson = requests.get(url).json()
    nj_features = [f for f in geojson['features'] if f['properties']['STATE'] == '34']
    return nj_features

# Load Excel data
@st.cache_data
def load_data():
    df = pd.read_excel("Activities_cleaned.xlsx", engine="openpyxl")
    df['lat_jittered'] = df['primary_site_lat'].apply(lambda x: x + random.uniform(-0.001, 0.001))
    df['long_jittered'] = df['primary_site_long'].apply(lambda x: x + random.uniform(-0.001, 0.001))
    return df

# Generate joyful colors
@st.cache_data
def joyful_color_palette(n):
    if n == 0:
        return []
    step = max(1, int(360 / n))
    hues = list(range(0, 360, step))
    random.shuffle(hues)
    colors = [f"hsl({h}, 65%, 70%)" for h in hues]
    while len(colors) < n:
        colors.append(f"hsl({random.randint(0,359)}, 65%, 70%)")
    return colors[:n]

def reset_filters():
    st.session_state.faculty_selected = 'All'
    st.session_state.focus_selected = 'All'
    st.session_state.activity_selected = 'All'
    st.session_state.campus_selected = 'All'

def main():
    st.set_page_config(layout="wide")

    # Load and clean data
    df = load_data()
    if df.empty:
        st.error("Data could not be loaded.")
        return

    # Optional filtering
    filtered_df = df  # or apply filters if you need

    # Create the map
    m = folium.Map(location=[40.0583, -74.4057], zoom_start=7)

    for _, row in filtered_df.iterrows():
        if pd.notnull(row['primary_site_lat']) and pd.notnull(row['primary_site_long']):
            folium.Marker(
                location=[row['primary_site_lat'], row['primary_site_long']],
                popup=row.get('activity_name', 'Activity'),
                tooltip=row.get('activity_name', 'Activity')
            ).add_to(m)

    # Apply styling and display
    st.markdown("""
        <style>
            .map-border {
                border: 4px solid black;
                padding: 20px;
                margin-top: 20px;
                border-radius: 10px;
                box-sizing: border-box;
            }
        </style>
        <div class="map-border">
    """, unsafe_allow_html=True)

    # Title
    st.title("Interactive Map of Activities")

    # Subtitle text
    st.markdown(
        '<p style="font-size:16px; font-family:Arial; margin-top:-10px;">Count shows number of locations</p>',
        unsafe_allow_html=True
    )

    # Map display
    st_folium(m, width=900, height=600)

    # Close the container div
    st.markdown("</div>", unsafe_allow_html=True)

