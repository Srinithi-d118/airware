from concurrent.futures import ThreadPoolExecutor

import requests
import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
import streamlit as st
from secret import TOKEN
from health_advice import PROFILES, get_advice

st.set_page_config(page_title="AirAware", page_icon="🌫️", layout="wide")

# ---------- Look and feel ----------
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(160deg, #0f2027, #203a43, #2c5364);
    }
    h1, h2, h3, h4, p, label, span, div { color: #eef3f7; }
    [data-testid="stSidebar"] { background: rgba(10, 20, 30, 0.85); }
    [data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.07);
        border: 1px solid rgba(255, 255, 255, 0.12);
        padding: 14px;
        border-radius: 14px;
    }
    .banner {
        padding: 22px 26px;
        border-radius: 18px;
        color: white;
        animation: glow 2.2s ease-in-out infinite;
    }
    @keyframes glow {
        0%   { box-shadow: 0 0 8px rgba(255,255,255,0.15); }
        50%  { box-shadow: 0 0 34px rgba(255,255,255,0.45); }
        100% { box-shadow: 0 0 8px rgba(255,255,255,0.15); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

RISK_MULTIPLIER = {
    "Healthy adult": 1.0,
    "Child": 1.3,
    "Elderly person": 1.3,
    "Asthma / lung patient": 1.6,
}

PM25_BREAKPOINTS = [
    (0, 50, 0.0, 12.0),
    (51, 100, 12.1, 35.4),
    (101, 150, 35.5, 55.4),
    (151, 200, 55.5, 150.4),
    (201, 300, 150.5, 250.4),
    (301, 500, 250.5, 500.4),
]

# One main city (usually the capital) for each state and union territory
CITY_COORDS = {
    "Andhra Pradesh": (16.51, 80.52),
    "Arunachal Pradesh": (27.08, 93.61),
    "Assam": (26.14, 91.74),
    "Bihar": (25.59, 85.14),
    "Chhattisgarh": (21.25, 81.63),
    "Goa": (15.50, 73.83),
    "Gujarat": (23.22, 72.65),
    "Haryana": (28.46, 77.03),
    "Himachal Pradesh": (31.10, 77.17),
    "Jharkhand": (23.34, 85.31),
    "Karnataka": (12.97, 77.59),
    "Kerala": (8.52, 76.94),
    "Madhya Pradesh": (23.26, 77.41),
    "Maharashtra": (19.08, 72.88),
    "Manipur": (24.82, 93.94),
    "Meghalaya": (25.57, 91.88),
    "Mizoram": (23.73, 92.72),
    "Nagaland": (25.67, 94.11),
    "Odisha": (20.30, 85.82),
    "Punjab": (30.90, 75.86),
    "Rajasthan": (26.91, 75.79),
    "Sikkim": (27.33, 88.61),
    "Tamil Nadu": (13.08, 80.27),
    "Telangana": (17.39, 78.49),
    "Tripura": (23.83, 91.28),
    "Uttar Pradesh": (26.85, 80.95),
    "Uttarakhand": (30.32, 78.03),
    "West Bengal": (22.57, 88.36),
    "Delhi": (28.61, 77.21),
    "Jammu & Kashmir": (34.08, 74.80),
    "Ladakh": (34.15, 77.58),
    "Chandigarh": (30.73, 76.78),
    "Puducherry": (11.93, 79.83),
    "Andaman & Nicobar": (11.62, 92.73),
    "Lakshadweep": (10.57, 72.64),
    "Daman & Diu": (20.40, 72.83),
}


def aqi_color(aqi):
    if aqi <= 50:
        return "#2e9e4f"
    if aqi <= 100:
        return "#d4a017"
    if aqi <= 150:
        return "#e8751a"
    if aqi <= 200:
        return "#d62f2f"
    if aqi <= 300:
        return "#8e3a9e"
    return "#7e0023"


def hex_to_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def aqi_to_pm25(aqi):
    for a_lo, a_hi, c_lo, c_hi in PM25_BREAKPOINTS:
        if aqi <= a_hi:
            return c_lo + (aqi - a_lo) * (c_hi - c_lo) / (a_hi - a_lo)
    return 500.0


def risk_score(aqi, profile):
    base = min(aqi / 300 * 100, 100)
    return min(round(base * RISK_MULTIPLIER[profile]), 100)


def gauge(score, color):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": "Health risk score"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 33], "color": "#1f6f43"},
                    {"range": [33, 66], "color": "#a17a0b"},
                    {"range": [66, 100], "color": "#8b1e1e"},
                ],
            },
        )
    )
    fig.update_layout(
        height=270,
        margin=dict(l=20, r=20, t=60, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "white"},
    )
    return fig


@st.cache_data(ttl=600)
def fetch(city):
    query = city.strip()
    url = f"https://api.waqi.info/feed/{query}/?token={TOKEN}"

    # If the user typed a state or union territory, use its main city location
    for state, (lat, lon) in CITY_COORDS.items():
        if state.lower() == query.lower():
            url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={TOKEN}"
            break

    try:
        data = requests.get(url, timeout=10).json()
        if data.get("status") != "ok":
            return None
        d = data["data"]
        return {
            "aqi": int(d["aqi"]),
            "station": d["city"]["name"],
            "iaqi": d.get("iaqi", {}),
            "forecast": d.get("forecast", {}).get("daily", {}).get("pm25", []),
        }
    except Exception:
        return None


def _geo_fetch(item):
    """Get the AQI of the nearest station to a latitude/longitude."""
    name, (lat, lon) = item
    try:
        url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={TOKEN}"
        data = requests.get(url, timeout=10).json()
        if data.get("status") == "ok":
            d = data["data"]
            aqi = int(d["aqi"])
            return {
                "City": name,
                "Station": d["city"]["name"],
                "AQI": aqi,
                "lat": lat,
                "lon": lon,
                "color": hex_to_rgb(aqi_color(aqi)) + [210],
            }
    except Exception:
        return None
    return None


@st.cache_data(ttl=600)
def load_map_data():
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_geo_fetch, CITY_COORDS.items()))
    return [r for r in results if r]
# ---------- Sidebar ----------
st.sidebar.title("🌫️ AirAware")
st.sidebar.caption("Air Quality Alert System")
city = st.sidebar.text_input("Your city or state", "Bangalore")
profile = st.sidebar.selectbox("Who are you?", PROFILES)
limit = st.sidebar.slider("Alert me when AQI goes above", 50, 300, 100, 10)

st.title("🌫️ AirAware")
st.caption("Live air quality with health advice made for you")
tab1, tab2, tab3 = st.tabs(["Today", "3D India map", "About"])

# ---------- Tab 1: Today ----------
with tab1:
    result = fetch(city)
    if result is None:
        st.error("City not found or no data. Try another name.")
    else:
        aqi = result["aqi"]
        level, advice = get_advice(aqi, profile)
        color = aqi_color(aqi)

        st.markdown(
            f"""
            <div class="banner" style="background:{color};">
              <div style="font-size:16px;">{result['station']}</div>
              <div style="font-size:56px;font-weight:700;">AQI {aqi}</div>
              <div style="font-size:22px;">{level}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")

        if aqi > limit:
            st.error(f"🚨 ALERT: AQI {aqi} is above your limit of {limit}.")
        else:
            st.success(f"✅ AQI {aqi} is within your limit of {limit}.")

        col1, col2 = st.columns([1, 1])
        score = risk_score(aqi, profile)
        col1.plotly_chart(gauge(score, color))

        pm25_index = result["iaqi"].get("pm25", {}).get("v", aqi)
        pm25_conc = aqi_to_pm25(float(pm25_index))
        cigs = pm25_conc / 22
        pm10 = result["iaqi"].get("pm10", {}).get("v", "n/a")

        col2.metric("🚬 Cigarettes per day equivalent", f"{cigs:.1f}")
        col2.caption("Breathing this air all day is roughly like smoking this many cigarettes (approximate).")
        col2.metric("PM2.5 index", pm25_index)
        col2.caption(f"PM10 index: {pm10}")

        st.subheader(f"Advice for: {profile}")
        st.info(advice)

        if result["forecast"]:
            st.subheader("PM2.5 forecast")
            fdf = pd.DataFrame(result["forecast"])
            fdf = fdf.set_index("day")[["avg", "min", "max"]]
            st.line_chart(fdf)

# ---------- Tab 2: 3D map ----------
with tab2:
    st.subheader("3D air quality map of India")
    st.caption(
        "One reading for each state and union territory (nearest monitoring station). "
        "Taller and redder columns mean worse air. Drag to rotate. Hold Ctrl and drag to tilt."
    )

    if st.button("Load live map"):
        with st.spinner("Fetching live data for all states and union territories..."):
            st.session_state["map_rows"] = load_map_data()

    rows = st.session_state.get("map_rows")
    if rows:
        df = pd.DataFrame(rows)
        layer = pdk.Layer(
            "ColumnLayer",
            data=df,
            get_position=["lon", "lat"],
            get_elevation="AQI",
            elevation_scale=1500,
            radius=35000,
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
            extruded=True,
        )
        view = pdk.ViewState(latitude=22.0, longitude=79.0, zoom=3.7, pitch=55, bearing=10)
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view,
                map_provider="carto",
                map_style="dark",
                tooltip={"text": "{City}\nAQI: {AQI}\nStation: {Station}"},
            )
        )
        worst = df.sort_values("AQI", ascending=False).iloc[0]
        best = df.sort_values("AQI").iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Most polluted right now", worst["City"], f"AQI {worst['AQI']}")
        c2.metric("Cleanest right now", best["City"], f"AQI {best['AQI']}")
        c3.metric("States/UTs with data", f"{len(df)} of {len(CITY_COORDS)}")
        st.bar_chart(df.set_index("City")["AQI"])
    else:
        st.info("Click **Load live map** to see all states and union territories.")

# ---------- Tab 3: About ----------
with tab3:
    st.subheader("About AirAware")
    st.write(
        "AirAware shows live air quality and gives health advice that depends on "
        "who you are. Data source: World Air Quality Index project (aqicn.org)."
    )
    st.write(
        "The risk score is our own simple model: AQI scaled to 0-100 and increased "
        "for sensitive groups. The cigarette equivalent uses the rule of thumb that "
        "22 µg/m³ of PM2.5 is about one cigarette a day."
    )
    st.write(
        "Limitation: readings come from monitoring stations, which are mostly in cities. "
        "Each state on the map shows the nearest available station."
    )
    st.caption("General guidance only, not medical advice.")