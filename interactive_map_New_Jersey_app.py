import streamlit as st
import pandas as pd
import requests
import folium
from shapely.geometry import shape, Point, MultiPolygon, Polygon
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
import random

st.set_page_config(layout="wide")

# ----------------------
# Load NJ county GeoJSON
@st.cache_data(show_spinner=True)
def load_nj_counties():
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    nj_features = [f for f in data['features'] if f['properties']['STATE'] == '34']
    return nj_features

# ----------------------
# Load and jitter Excel data (with stable seed)
@st.cache_data(show_spinner=True)
def load_data():
    random.seed(42)  # ✅ Fix refresh loop by stabilizing jitter
    df = pd.read_excel('Activities_cleaned.xlsx', engine='openpyxl')
    df['lat_jittered'] = df['primary_site_lat'].apply(lambda x: x + random.uniform(-0.001, 0.001))
    df['long_jittered'] = df['primary_site_long'].apply(lambda x: x + random.uniform(-0.001, 0.001))
    return df

# ----------------------
# Joyful colors
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

def extract_unique(series):
    items = set()
    for val in series.dropna():
        for item in val.split(','):
            items.add(item.strip())
    return sorted(items)

# ----------------------
# Main app
def main():
    st.title("Optimized Interactive NJ Map with Activities")

    nj_features = load_nj_counties()
    final_df = load_data()

    nj_polygons = [shape(f['geometry']) for f in nj_features]
    nj_boundary = MultiPolygon(nj_polygons)
    minx, miny, maxx, maxy = nj_boundary.bounds
    center_lat = (miny + maxy) / 2
    center_lon = (minx + maxx) / 2

    county_names = sorted({f['properties']['NAME'] for f in nj_features})
    county_color_map = dict(zip(county_names, joyful_color_palette(len(county_names))))

    # Sidebar filters
    faculty_list = extract_unique(final_df['faculty_partners'])
    focus_area_list = extract_unique(final_df['focus_cleaned'])
    activity_list = sorted(final_df['activity_name'].dropna().unique())
    campus_partner_list = extract_unique(final_df['campus_partners'])

    st.sidebar.header("Filters")
    faculty_selected = st.sidebar.selectbox('Faculty:', options=['All'] + faculty_list, index=0)
    focus_selected = st.sidebar.selectbox('Focus Area:', options=['All'] + focus_area_list, index=0)
    activity_selected = st.sidebar.selectbox('Activity:', options=['All'] + activity_list, index=0)
    campus_selected = st.sidebar.selectbox('Campus:', options=['All'] + campus_partner_list, index=0)

    # Initialize map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles=None)
    folium.TileLayer(
        tiles='https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}.png',
        attr='© OpenStreetMap contributors, © CARTO',
        control=False
    ).add_to(m)

    # Draw counties
    for feature in nj_features:
        county = feature['properties']['NAME']
        fill_color = county_color_map[county]
        folium.GeoJson(
            feature['geometry'],
            style_function=lambda f, color=fill_color: {
                "fillColor": color,
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.7
            }
        ).add_to(m)

    # Draw county labels
    for feature in nj_features:
        county = feature['properties']['NAME']
        geom = shape(feature['geometry'])
        centroid = geom.centroid
        folium.Marker(
            [centroid.y, centroid.x],
            icon=folium.DivIcon(
                html=f'<div style="font-size:13px;font-weight:bold;color:black;text-shadow:1px 1px white;">{county}</div>'
            )
        ).add_to(m)

    # Mask outside NJ
    world = Polygon([(-180,-90),(-180,90),(180,90),(180,-90)])
    holes = [poly.exterior.coords[:] for poly in nj_polygons if isinstance(poly, Polygon)]
    mask = Polygon(world.exterior.coords, holes=holes)
    folium.GeoJson(
        data=mask.__geo_interface__,
        style_function=lambda x: {
            'fillColor': 'white', 'fillOpacity': 1, 'weight': 0
        }
    ).add_to(m)

    # Add filtered markers
    marker_cluster = MarkerCluster().add_to(m)

    for _, row in final_df.iterrows():
        pt = Point(row['long_jittered'], row['lat_jittered'])
        if not nj_boundary.contains(pt):
            continue

        fnames = [f.strip() for f in str(row['faculty_partners']).split(',')] if pd.notna(row['faculty_partners']) else []
        foc_vals = [f.strip() for f in str(row['focus_cleaned']).split(',')] if pd.notna(row['focus_cleaned']) else []
        cpnames = [c.strip() for c in str(row['campus_partners']).split(',')] if pd.notna(row['campus_partners']) else []

        if ((faculty_selected == 'All' or faculty_selected in fnames) and
            (focus_selected == 'All' or focus_selected in foc_vals) and
            (activity_selected == 'All' or activity_selected == row['activity_name']) and
            (campus_selected == 'All' or campus_selected in cpnames)):

            popup_html = f"""
            <div style="width:300px;font-size:13px;">
              <b>Activity:</b> <a href="{row['activity_url']}" target="_blank">{row['activity_name']}</a><br>
              <b>Faculty:</b> {row['faculty_partners']}<br>
              <b>Campus:</b> {row['campus_partners']}<br>
              <b>Contact:</b> <a href="mailto:{row['primary_contact_email']}">{row['primary_contact_email']}</a>
            </div>"""
            folium.CircleMarker(
                location=[row['lat_jittered'], row['long_jittered']],
                radius=7, color='crimson', fill=True, fill_opacity=0.8,
                popup=popup_html, tooltip=row['activity_name']
            ).add_to(marker_cluster)

    st_folium(m, width=900, height=700)

if __name__ == "__main__":
    main()
