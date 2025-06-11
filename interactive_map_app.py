import streamlit as st
import folium
import requests
import pandas as pd
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# --- Load NJ counties (FIPS = '34') ---
url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
geojson_data = requests.get(url).json()
nj_features = [f for f in geojson_data['features'] if f['properties']['STATE'] == '34']

nj_polygons = []
for feature in nj_features:
    geom = shape(feature['geometry'])
    nj_polygons.append(geom)

nj_boundary = MultiPolygon(nj_polygons)
minx, miny, maxx, maxy = nj_boundary.bounds
center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2

# --- Assume final_df is loaded here with required columns ---
# For example: final_df = pd.read_csv('your_data.csv')
# Replace the below with your actual data loading:
final_df = ...  # Your actual DataFrame loading here

# --- Helper function to extract unique values from comma-separated string columns ---
def extract_unique(series):
    items = set()
    for entry in series.dropna():
        for item in entry.split(','):
            items.add(item.strip())
    return sorted(items)

faculty_list = extract_unique(final_df['faculty_partners'])
focus_area_list = extract_unique(final_df['focus_cleaned'])
activity_list = sorted(final_df['activity_name'].dropna().unique())
campus_partner_list = extract_unique(final_df['campus_partners'])

# --- Streamlit Sidebar Filters ---
st.sidebar.title("Filters")
selected_faculty = st.sidebar.selectbox("Faculty:", options=['All'] + faculty_list, index=0)
selected_focus_areas = st.sidebar.multiselect("Focus Areas:", options=focus_area_list)
selected_activity = st.sidebar.selectbox("Activity:", options=['All'] + activity_list, index=0)
selected_campus = st.sidebar.selectbox("Campus:", options=['All'] + campus_partner_list, index=0)
if st.sidebar.button("Reset Filters"):
    selected_faculty = 'All'
    selected_focus_areas = []
    selected_activity = 'All'
    selected_campus = 'All'

# --- Build the map ---
m = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles=None)

tile_attribution = {
    'CartoDB Positron No Labels': '© OpenStreetMap contributors, © CARTO'
}
folium.TileLayer(
    tiles='https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}.png',
    attr=tile_attribution['CartoDB Positron No Labels'],
    name='CartoDB Positron No Labels',
    control=False
).add_to(m)

m.fit_bounds([[miny, minx], [maxy, maxx]])
m.options['maxBounds'] = [[miny, minx], [maxy, maxx]]

# Add NJ county borders
folium.GeoJson(
    {
        "type": "FeatureCollection",
        "features": nj_features
    },
    style_function=lambda x: {
        "fillColor": "#ffffff00",  # transparent fill
        "color": "blue",
        "weight": 2,
    }
).add_to(m)

# Filter markers first and collect for counting per county
filtered_points = []

for _, row in final_df.iterrows():
    point = Point(row['long_jittered'], row['lat_jittered'])
    if not nj_boundary.contains(point):
        continue  # Skip points outside NJ

    faculty_names = [f.strip() for f in row['faculty_partners'].split(',')] if pd.notna(row['faculty_partners']) else []
    focus_values = [f.strip() for f in row['focus_cleaned'].split(',')] if pd.notna(row['focus_cleaned']) else []
    campus_names = [c.strip() for c in row['campus_partners'].split(',')] if pd.notna(row['campus_partners']) else []

    if ((selected_faculty == 'All' or selected_faculty in faculty_names) and
        (not selected_focus_areas or all(f in focus_values for f in selected_focus_areas)) and
        (selected_activity == 'All' or selected_activity == row['activity_name']) and
        (selected_campus == 'All' or selected_campus in campus_names)):
        filtered_points.append((point, row))

total_markers = len(filtered_points)

# Count markers per county
county_marker_counts = {f['properties']['NAME']: 0 for f in nj_features}

for point, _ in filtered_points:
    for feature in nj_features:
        county_name = feature['properties']['NAME']
        geom = shape(feature['geometry'])
        if geom.contains(point):
            county_marker_counts[county_name] += 1
            break

# Add county labels with percentage only if percentage > 0
for feature in nj_features:
    county_name = feature['properties']['NAME']
    geom = shape(feature['geometry'])
    centroid = geom.centroid
    count = county_marker_counts.get(county_name, 0)
    percentage = (count / total_markers * 100) if total_markers > 0 else 0
    if percentage > 0:
        label_html = f"""
        <div style="font-size: 12px; font-weight: bold; color: blue;">
            {county_name}<br>
            <span style="font-weight: normal; color: black;">{percentage:.1f}%</span>
        </div>
        """
        folium.map.Marker(
            [centroid.y, centroid.x],
            icon=folium.DivIcon(html=label_html)
        ).add_to(m)

# Mask outside NJ
world = Polygon([
    (-180, -90),
    (-180, 90),
    (180, 90),
    (180, -90)
])
holes = [poly.exterior.coords[:] for poly in nj_boundary.geoms]
mask_polygon = Polygon(world.exterior.coords, holes=holes)
mask_geojson = folium.GeoJson(
    data=mask_polygon.__geo_interface__,
    style_function=lambda x: {
        'fillColor': 'white',
        'color': 'white',
        'fillOpacity': 1,
        'weight': 0
    }
)
m.add_child(mask_geojson)

# Marker cluster group
marker_cluster = MarkerCluster().add_to(m)

# Add filtered markers
for _, row in filtered_points:
    popup_html = f"""
    <div style="width: 300px; font-size: 13px;">
    <b>Activity:</b> <a href="{row['activity_url']}" target="_blank">{row['activity_name']}</a><br>
    <b>Faculty:</b> {row['faculty_partners']}<br>
    <b>Campus Partners:</b> {row['campus_partners']}<br>
    <b>Community Partners:</b> {row['community_organizations']}<br>
    <b>Contact:</b> <a href="mailto:{row['primary_contact_email']}">{row['primary_contact_email']}</a>
    </div>
    """

    folium.CircleMarker(
        location=[row['lat_jittered'], row['long_jittered']],
        radius=7,
        color='crimson',
        fill=True,
        fill_opacity=0.8,
        popup=popup_html,
        tooltip=row['activity_name']
    ).add_to(marker_cluster)

# Display map in Streamlit
st_data = st_folium(m, width=700, height=600)
