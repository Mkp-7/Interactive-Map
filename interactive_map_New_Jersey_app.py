import streamlit as st
import pandas as pd
import folium
import json
import random
from shapely.geometry import shape, MultiPolygon
from streamlit_folium import st_folium

st.set_page_config(layout="wide")

# Cache to load your CSV data
@st.cache_data
def load_data():
    df = pd.read_csv("Activities_cleaned.csv")
    return df

# Cache to load your GeoJSON file for municipalities (adjust path if needed)
@st.cache_data
def load_geojson():
    with open("nj_municipalities.geojson", "r") as f:
        return json.load(f)

# Cache to generate stable colors per municipality
@st.cache_data
def generate_colors(names):
    random.seed(42)
    colors = []
    for _ in range(len(names)):
        h = random.randint(0, 360)
        s = random.randint(50, 80)
        l = random.randint(60, 80)
        colors.append(f"hsl({h}, {s}%, {l}%)")
    return dict(zip(names, colors))

# Load data and geojson
df = load_data()
geojson_data = load_geojson()

# Confirm column names for municipality and county — adjust if your CSV uses different case/column names
municipality_col = "municipality" if "municipality" in df.columns else "Municipality"
county_col = "county" if "county" in df.columns else "County"

# Clean up columns to ensure existence
if municipality_col not in df.columns or county_col not in df.columns:
    st.error(f"CSV must include '{municipality_col}' and '{county_col}' columns.")
    st.stop()

# Get sorted unique values
counties = sorted(df[county_col].dropna().unique())
municipalities = sorted(df[municipality_col].dropna().unique())

# Generate colors
municipality_colors = generate_colors(municipalities)

# Sidebar filters
st.sidebar.title("Filter Activities")
selected_county = st.sidebar.selectbox("Select County", ["All"] + counties)
if selected_county == "All":
    available_municipalities = municipalities
else:
    available_municipalities = sorted(df[df[county_col] == selected_county][municipality_col].unique())
selected_municipality = st.sidebar.selectbox("Select Municipality", ["All"] + available_municipalities)

# Filter data
filtered_df = df.copy()
if selected_county != "All":
    filtered_df = filtered_df[filtered_df[county_col] == selected_county]
if selected_municipality != "All":
    filtered_df = filtered_df[filtered_df[municipality_col] == selected_municipality]

# Initialize Folium map centered on NJ roughly
m = folium.Map(location=[40.0583, -74.4057], zoom_start=8, control_scale=True)

# Add municipalities layer colored by municipality_colors
for feature in geojson_data["features"]:
    muni_name = feature["properties"].get("NAME") or feature["properties"].get("name")
    color = municipality_colors.get(muni_name, "#ccc")

    style = {
        "fillColor": color,
        "color": "black",
        "weight": 1,
        "fillOpacity": 0.6,
    }

    tooltip = folium.GeoJsonTooltip(
        fields=["NAME"] if "NAME" in feature["properties"] else ["name"],
        aliases=["Municipality:"],
        sticky=False,
        labels=True,
    )

    folium.GeoJson(
        data=feature,
        style_function=lambda x, style=style: style,
        tooltip=tooltip,
    ).add_to(m)

# Add markers for filtered activities
for _, row in filtered_df.iterrows():
    lat = row.get("lat_jittered")
    lon = row.get("long_jittered")
    if pd.notnull(lat) and pd.notnull(lon):
        popup_html = f"""
        <b>{row.get('activity_name', 'No Name')}</b><br>
        {row.get('campus_partners', '')}<br>
        {row.get(municipality_col, '')}, {row.get(county_col, '')}
        """
        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color="blue",
            fill=True,
            fill_color="blue",
            fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(m)

# Title and map display
st.title("🗺️ Interactive NJ Activities Map")
st.markdown("Zoom and hover over municipalities to explore activities.")
st_data = st_folium(m, width=1200, height=700)

# Show filtered data in an expander
with st.expander("📋 View Filtered Data"):
    st.dataframe(filtered_df.reset_index(drop=True))
