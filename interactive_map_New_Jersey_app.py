import streamlit as st
import pandas as pd
import requests
import folium
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from folium.plugins import MarkerCluster
from shapely.ops import unary_union
from streamlit_folium import st_folium
import random
import json

st.set_page_config(layout="wide")

@st.cache_data(show_spinner=True)
def load_data():
    df = pd.read_excel('Activities_cleaned.xlsx', engine='openpyxl')
    return df

@st.cache_data(show_spinner=True)
def load_geojson():
    with open("nj_municipalities.geojson", "r") as f:
        municipal_geo = json.load(f)
    return municipal_geo


def joyful_color_palette(n):
    if n == 0:
        return []
    step = max(1, int(360 / n))
    hues = list(range(0, 360, step))
    random.shuffle(hues)
    colors = [f"hsl({hue}, 65%, 70%)" for hue in hues]
    while len(colors) < n:
        colors.append(f"hsl({random.randint(0,359)}, 65%, 70%)")
    return colors[:n]

def build_nj_boundary(muni_features):
    all_polygons = []
    for feat in muni_features:
        geom = shape(feat["geometry"])
        if isinstance(geom, Polygon):
            all_polygons.append(geom)
        elif isinstance(geom, MultiPolygon):
            all_polygons.extend(geom.geoms)
    return MultiPolygon(all_polygons)

def main():
    st.title("Interactive NJ Map with Activities")

    # Load data
    final_df = load_data()
    municipal_geo = load_geojson()
    muni_features = municipal_geo["features"]

    # NJ boundary
    nj_boundary = build_nj_boundary(muni_features)
    minx, miny, maxx, maxy = nj_boundary.bounds
    center_lat, center_lon = (miny + maxy)/2, (minx + maxx)/2

    # Counties and municipalities
    counties = sorted({feat["properties"]["COUNTY"] for feat in muni_features})
    municipalities = sorted({feat["properties"]["NAME"] for feat in muni_features})

    county_color_map = dict(zip(counties, joyful_color_palette(len(counties))))
    municipality_color_map = dict(zip(municipalities, joyful_color_palette(len(municipalities))))

    # Sidebar filters
    faculty_list = sorted(set(x.strip() for vals in final_df['faculty_partners'].dropna() for x in vals.split(',')))
    focus_area_list = sorted(set(x.strip() for vals in final_df['focus_cleaned'].dropna() for x in vals.split(',')))
    activity_list = sorted(final_df['activity_name'].dropna().unique())
    campus_partner_list = sorted(set(x.strip() for vals in final_df['campus_partners'].dropna() for x in vals.split(',')))

    st.sidebar.header("Filters")

    faculty_selected = st.sidebar.selectbox('Faculty:', options=['All'] + faculty_list, index=0)
    focus_area_selected = st.sidebar.multiselect('Focus Areas:', options=focus_area_list)
    activity_selected = st.sidebar.selectbox('Activity:', options=['All'] + activity_list, index=0)
    campus_selected = st.sidebar.selectbox('Campus:', options=['All'] + campus_partner_list, index=0)
    color_theme = st.sidebar.selectbox('Color Theme:', options=['County Color Theme', 'Mixed Random Colors'], index=0)

    # Initialize map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles=None)
    folium.TileLayer(
        tiles='https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}.png',
        attr='© OpenStreetMap contributors, © CARTO',
        control=False
    ).add_to(m)
    m.fit_bounds([[miny, minx], [maxy, maxx]])
    m.options['maxBounds'] = [[miny, minx], [maxy, maxx]]

    county_to_polygons = {c: [] for c in counties}

    # Draw municipalities with colors
    for feat in muni_features:
        props = feat["properties"]
        county = props["COUNTY"]
        municipality = props["NAME"]
        fill_color = (county_color_map[county] if color_theme == 'County Color Theme' 
                      else municipality_color_map[municipality])

        polygon = shape(feat["geometry"])
        county_to_polygons[county].append(polygon)

        folium.GeoJson(
            feat["geometry"],
            style_function=lambda f, color=fill_color: {
                "fillColor": color,
                "color": "black",
                "weight": 0.3,
                "fillOpacity": 0.7
            },
            tooltip=f"{municipality}, {county}"
        ).add_to(m)

    # Draw thick county boundaries + labels
    for county, polygons in county_to_polygons.items():
        merged = unary_union(polygons)
        folium.GeoJson(
            merged.__geo_interface__,
            style_function=lambda f: {
                "color": "black",
                "weight": 2.5,
                "fillOpacity": 0
            }
        ).add_to(m)
        centroid = merged.centroid
        folium.map.Marker(
            [centroid.y, centroid.x],
            icon=folium.DivIcon(
                html=f'<div style="font-size:14px; font-weight:bold; color:black; text-shadow: 1px 1px white;">{county}</div>'
            )
        ).add_to(m)

    # Mask outside NJ — FIXED: safely collect holes from all polygons
    world = Polygon([(-180,-90),(-180,90),(180,90),(180,-90)])

    holes = []
    for polys in county_to_polygons.values():
        for poly in polys:
            if isinstance(poly, Polygon) and poly.exterior:
                holes.append(list(poly.exterior.coords))

    mask = Polygon(world.exterior.coords, holes=holes)
    folium.GeoJson(mask.__geo_interface__,
                   style_function=lambda x: {'fillColor':'white','fillOpacity':1,'weight':0}
                  ).add_to(m)

    marker_cluster = MarkerCluster().add_to(m)

    # Filter and add markers
    for _, row in final_df.iterrows():
        pt = Point(row['long_jittered'], row['lat_jittered'])
        if not nj_boundary.contains(pt):
            continue

        fnames = [f.strip() for f in row['faculty_partners'].split(',')] if pd.notna(row['faculty_partners']) else []
        foc_vals = [f.strip() for f in row['focus_cleaned'].split(',')] if pd.notna(row['focus_cleaned']) else []
        cpnames = [c.strip() for c in row['campus_partners'].split(',')] if pd.notna(row['campus_partners']) else []

        if ((faculty_selected == 'All' or faculty_selected in fnames) and
            (not focus_area_selected or all(f in foc_vals for f in focus_area_selected)) and
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

    st_data = st_folium(m, width=900, height=700)

if __name__ == "__main__":
    main()
