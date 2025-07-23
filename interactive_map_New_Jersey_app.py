import streamlit as st
import folium
import pandas as pd
import json
import random
import requests
from folium.features import GeoJson, GeoJsonTooltip
from streamlit_folium import st_folium
from folium import Marker, Popup
from branca.colormap import linear

st.set_page_config(layout="wide")
st.title("New Jersey Activity Map")

# -----------------------
# Fix for random refresh
random.seed(42)

@st.cache_data(show_spinner=True)
def load_nj_counties():
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return [f for f in data['features'] if f['properties']['STATE'] == '34']  # NJ = 34

@st.cache_data(show_spinner=True)
def load_data():
    df = pd.read_excel("Activities_cleaned.xlsx", engine="openpyxl")
    df['lat_jittered'] = df['primary_site_lat'].apply(lambda x: x + random.uniform(-0.001, 0.001))
    df['long_jittered'] = df['primary_site_long'].apply(lambda x: x + random.uniform(-0.001, 0.001))
    return df

# -----------------------
# Load data
nj_county_features = load_nj_counties()
df = load_data()
counties = sorted(df["County"].dropna().unique())
municipalities = sorted(df["Municipality"].dropna().unique())

# -----------------------
# Fixed Joyful Color Palette
def joyful_color_palette(n):
    base_colors = [
        "#FF6B6B", "#FFB347", "#FFD700", "#90EE90", "#87CEFA", "#CBAACB",
        "#FF69B4", "#FFA07A", "#20B2AA", "#FF6347", "#00CED1", "#DDA0DD"
    ]
    return (base_colors * (n // len(base_colors) + 1))[:n]

county_colors = dict(zip(counties, joyful_color_palette(len(counties))))

# -----------------------
# Sidebar
selected_county = st.sidebar.selectbox("Select a County", counties)
show_municipality_borders = st.sidebar.checkbox("Show Municipality Borders", value=True)

# -----------------------
# Filter Data
filtered_df = df[df["County"] == selected_county]

# -----------------------
# Folium Map
m = folium.Map(location=[40.0583, -74.4057], zoom_start=8, tiles="CartoDB positron")

# Add county borders
folium.GeoJson(
    {"type": "FeatureCollection", "features": nj_county_features},
    style_function=lambda feature: {
        "fillColor": county_colors.get(feature["properties"].get("NAME"), "#ffffff"),
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.5,
    }
).add_to(m)

# Optional: Add municipality borders (local file or external)
if show_municipality_borders:
    with open("nj_municipalities.geojson", "r") as f:
        muni_data = json.load(f)

    folium.GeoJson(
        muni_data,
        name="Municipalities",
        style_function=lambda feature: {
            "fillColor": "#00000000",
            "color": "#555",
            "weight": 1,
            "fillOpacity": 0.1,
        }
    ).add_to(m)

# Add markers
for _, row in filtered_df.iterrows():
    popup_html = f"""
    <b>Program:</b> {row.get("Program_Name", "N/A")}<br>
    <b>Activity:</b> {row.get("Activity_Name", "N/A")}<br>
    <b>Municipality:</b> {row.get("Municipality", "N/A")}<br>
    <b>County:</b> {row.get("County", "N/A")}
    """
    Marker(
        location=[row["lat_jittered"], row["long_jittered"]],
        popup=Popup(popup_html, max_width=300),
        icon=folium.Icon(color="blue", icon="info-sign"),
    ).add_to(m)

# -----------------------
# Display Map
st_data = st_folium(m, width=1400, height=700)
