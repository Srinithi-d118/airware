import base64
import os
import random
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests
import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
import streamlit as st
from secret import TOKEN
from health_advice import PROFILES, get_advice
from alerts import send_alert_email
from history import save_reading, load_history

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

    /* ---- Dropdown lists: dark background, light text ---- */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[data-baseweb="popover"] ul,
    ul[role="listbox"],
    div[data-baseweb="menu"] {
        background-color: #12303b !important;
    }
    div[data-baseweb="popover"] li,
    ul[role="listbox"] li,
    div[data-baseweb="menu"] li {
        background-color: #12303b !important;
        color: #eef3f7 !important;
    }
    div[data-baseweb="popover"] li *,
    ul[role="listbox"] li *,
    div[data-baseweb="menu"] li * {
        color: #eef3f7 !important;
    }
    div[data-baseweb="popover"] li:hover,
    ul[role="listbox"] li:hover,
    ul[role="listbox"] li[aria-selected="true"],
    div[data-baseweb="menu"] li:hover {
        background-color: #2c5364 !important;
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

AVATAR = {
    "Healthy adult": "🧑",
    "Child": "🧒",
    "Elderly person": "👵",
    "Asthma / lung patient": "🩺",
}

PM25_BREAKPOINTS = [
    (0, 50, 0.0, 12.0),
    (51, 100, 12.1, 35.4),
    (101, 150, 35.5, 55.4),
    (151, 200, 55.5, 150.4),
    (201, 300, 150.5, 250.4),
    (301, 500, 250.5, 500.4),
]

LEGEND = [
    ("#2e9e4f", "Good 0-50"),
    ("#d4a017", "Moderate 51-100"),
    ("#e8751a", "Sensitive 101-150"),
    ("#d62f2f", "Unhealthy 151-200"),
    ("#8e3a9e", "Very unhealthy 201-300"),
    ("#7e0023", "Hazardous 300+"),
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


def scene_html(aqi):
    """A city skyline drawn in code. The sky gets hazier as the AQI rises."""
    if aqi <= 50:
        top, bottom, haze = "#5bb8f5", "#dff3ff", 0.0
    elif aqi <= 100:
        top, bottom, haze = "#7fb2d6", "#e8f0f3", 0.12
    elif aqi <= 150:
        top, bottom, haze = "#b3a583", "#ecdcb9", 0.28
    elif aqi <= 200:
        top, bottom, haze = "#9a8672", "#d3bda3", 0.42
    elif aqi <= 300:
        top, bottom, haze = "#76635e", "#aa9288", 0.58
    else:
        top, bottom, haze = "#463838", "#6b5853", 0.72

    sun_opacity = max(0.15, 1 - haze * 1.1)
    buildings = [
        (0, 60, 90), (70, 50, 130), (130, 70, 100), (210, 40, 150),
        (260, 80, 110), (350, 50, 140), (410, 70, 95), (490, 55, 125),
        (555, 75, 105), (640, 45, 145), (695, 60, 100), (765, 35, 120),
    ]

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 220">']
    parts.append(
        '<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{top}"/>'
        f'<stop offset="1" stop-color="{bottom}"/>'
        '</linearGradient></defs>'
    )
    parts.append('<rect width="800" height="220" fill="url(#sky)"/>')
    parts.append(
        f'<circle cx="650" cy="62" r="30" fill="#ffd54f" opacity="{sun_opacity:.2f}"/>'
    )
    for x, w, h in buildings:
        parts.append(
            f'<rect x="{x}" y="{220 - h}" width="{w}" height="{h}" '
            'fill="#1c2b36" opacity="0.92"/>'
        )
    parts.append(
        f'<rect width="800" height="220" fill="#8a7a6a" opacity="{haze * 0.55:.2f}"/>'
    )
    rnd = random.Random(7)
    for _ in range(min(aqi // 3, 90)):
        x = rnd.uniform(0, 800)
        y = rnd.uniform(15, 200)
        r = rnd.uniform(1, 3)
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="#5b4636" opacity="0.5"/>')
    parts.append('</svg>')

    svg = "".join(parts)
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return (
        f'<img src="data:image/svg+xml;base64,{b64}" '
        'style="width:100%;border-radius:18px;display:block;"/>'
    )


def action_items(aqi, profile):
    """Four simple action cards. Sensitive people get stricter advice."""
    t = aqi + (30 if profile != "Healthy adult" else 0)
    ok, warn, bad = "#2e9e4f", "#e8751a", "#d62f2f"

    if t <= 100:
        exercise = ("🏃", "Outdoor exercise", "Go ahead", ok)
    elif t <= 150:
        exercise = ("🏃", "Outdoor exercise", "Keep it light and short", warn)
    else:
        exercise = ("🏃", "Outdoor exercise", "Do it indoors today", bad)

    if t <= 100:
        mask = ("😷", "Mask", "Not needed", ok)
    elif t <= 150:
        mask = ("😷", "Mask", "Wear one if you are sensitive", warn)
    else:
        mask = ("😷", "Mask", "Wear an N95 mask outside", bad)

    if t <= 100:
        windows = ("🪟", "Windows", "Open for fresh air", ok)
    elif t <= 150:
        windows = ("🪟", "Windows", "Open only briefly", warn)
    else:
        windows = ("🪟", "Windows", "Keep them closed", bad)

    if t <= 100:
        purifier = ("🌀", "Air purifier", "Optional", ok)
    elif t <= 150:
        purifier = ("🌀", "Air purifier", "Helpful indoors", warn)
    else:
        purifier = ("🌀", "Air purifier", "Run one if you can", bad)

    return [exercise, mask, windows, purifier]


def action_cards_html(items):
    cards = ""
    for icon, title, text, color in items:
        cards += (
            f'<div style="flex:1;min-width:150px;background:rgba(255,255,255,0.07);'
            f'border:1px solid {color};border-left:6px solid {color};'
            f'border-radius:14px;padding:12px;">'
            f'<div style="font-size:30px;">{icon}</div>'
            f'<div style="font-weight:700;">{title}</div>'
            f'<div style="font-size:14px;">{text}</div></div>'
        )
    return f'<div style="display:flex;gap:12px;flex-wrap:wrap;">{cards}</div>'


@st.cache_data(ttl=600)
def _get_data(url):
    """Download data from the API. If it fails, raise an error.
    Streamlit does not remember errors, so a failed lookup is never saved."""
    reply = requests.get(url, timeout=10).json()
    if reply.get("status") != "ok":
        raise ValueError(str(reply.get("data")))
    return reply["data"]


def fetch(city):
    """Returns (result, error_message). One of them is None."""
    query = city.strip()
    if not query:
        return None, "Please type a city or state."

    name_url = f"https://api.waqi.info/feed/{quote(query)}/?token={TOKEN}"
    urls = [name_url]

    # If the user typed a state or union territory, try its main city location first
    for state, (lat, lon) in CITY_COORDS.items():
        if state.lower() == query.lower():
            geo_url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={TOKEN}"
            urls = [geo_url, name_url]
            break

    last_error = "unknown error"
    for url in urls:
        try:
            d = _get_data(url)
            return {
                "aqi": int(d["aqi"]),
                "station": d["city"]["name"],
                "iaqi": d.get("iaqi", {}),
                "forecast": d.get("forecast", {}).get("daily", {}).get("pm25", []),
            }, None
        except Exception as e:
            last_error = str(e)
    return None, last_error


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
                "color": hex_to_rgb(aqi_color(aqi)) + [225],
                "halo": hex_to_rgb(aqi_color(aqi)) + [70],
            }
    except Exception:
        return None
    return None


def load_map_data():
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_geo_fetch, CITY_COORDS.items()))
    return [r for r in results if r]


# ---------- Sidebar ----------
if os.path.exists("images/logo.png"):
    st.sidebar.image("images/logo.png")
st.sidebar.title("🌫️ AirAware")
st.sidebar.caption("Air Quality Alert System")
city = st.sidebar.text_input("Your city or state", "Bangalore")
profile = st.sidebar.selectbox("Who are you?", PROFILES)
limit = st.sidebar.slider("Alert me when AQI goes above", 50, 300, 100, 10)

st.sidebar.markdown("**Alerts**")
email_to = st.sidebar.text_input("Send alerts to (email)", "")
telegram_id = st.sidebar.text_input(
    "Your Telegram chat ID (optional)",
    "",
    help="1) Open our AirAware bot in Telegram and press Start. "
         "2) Message @userinfobot to get your chat ID (a number). "
         "3) Type that number here.",
)
auto_email = st.sidebar.checkbox("Alert me automatically when above limit")

# ---------- Header ----------
if os.path.exists("images/banner.jpg"):
    st.image("images/banner.jpg", use_container_width=True)
st.title("🌫️ AirAware")
st.caption("Live air quality with health advice made for you")
tab1, tab_trends, tab2, tab3 = st.tabs(["Today", "Trends", "3D India map", "About"])

# ---------- Tab 1: Today ----------
with tab1:
    result, error = fetch(city)
    if result is None:
        st.error(f"No data for '{city}'. Reason: {error}")
        st.caption("Try another name, for example Chennai, Delhi or Mumbai. "
                   "If every city fails, check your internet or your token in secret.py.")
    else:
        aqi = result["aqi"]
        level, advice = get_advice(aqi, profile)
        color = aqi_color(aqi)

        pm25_index = result["iaqi"].get("pm25", {}).get("v", aqi)
        pm10 = result["iaqi"].get("pm10", {}).get("v", "n/a")

        # Save this reading so the Trends tab can show history
        try:
            save_reading(city.strip().title(), result["station"], aqi, pm25_index)
        except Exception:
            pass

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

        # ---- Sky picture ----
        st.markdown(scene_html(aqi), unsafe_allow_html=True)
        st.caption("Illustration: the sky gets hazier and fills with particles as the AQI rises.")

        # ---- Action cards ----
        st.subheader(f"{AVATAR[profile]} What to do today: {profile}")
        st.markdown(action_cards_html(action_items(aqi, profile)), unsafe_allow_html=True)
        st.write("")

        # ---- Alerts (email and/or Telegram) ----
        if email_to or telegram_id:
            if aqi > limit and auto_email:
                alert_key = f"{city}|{aqi}|{limit}|{email_to}|{telegram_id}"
                if st.session_state.get("last_alert") != alert_key:
                    ok, msg = send_alert_email(
                        email_to, result["station"], aqi, level, advice,
                        profile, limit, telegram_id,
                    )
                    st.session_state["last_alert"] = alert_key
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

            if st.button("📣 Send alert now"):
                ok, msg = send_alert_email(
                    email_to, result["station"], aqi, level, advice,
                    profile, limit, telegram_id,
                )
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        col1, col2 = st.columns([1, 1])
        score = risk_score(aqi, profile)
        col1.plotly_chart(gauge(score, color))

        pm25_conc = aqi_to_pm25(float(pm25_index))
        cigs = pm25_conc / 22

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

# ---------- Tab: Trends ----------
with tab_trends:
    st.subheader("AQI trends")
    st.caption("Every time a city is checked on the Today tab, the reading is saved here.")
    hist = load_history()
    if hist.empty:
        st.info("No history yet. Check a city on the Today tab, then come back here.")
    else:
        cities = sorted(hist["city"].unique())
        pick = st.selectbox("Choose a city", cities)
        h = hist[hist["city"] == pick].sort_values("time")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Readings saved", len(h))
        m2.metric("Average AQI", round(h["aqi"].mean()))
        m3.metric("Highest AQI", int(h["aqi"].max()))
        m4.metric("Lowest AQI", int(h["aqi"].min()))

        if len(h) >= 2:
            change = int(h["aqi"].iloc[-1]) - int(h["aqi"].iloc[-2])
            if change > 0:
                st.warning(f"📈 Air is getting worse: AQI went up by {change} since the last reading.")
            elif change < 0:
                st.success(f"📉 Air is getting better: AQI went down by {abs(change)} since the last reading.")
            else:
                st.info("➡️ AQI is the same as the last reading.")

        st.line_chart(h.set_index("time")["aqi"])
        st.dataframe(h.tail(20), hide_index=True)

        st.download_button(
            "Download history as CSV",
            hist.to_csv(index=False),
            file_name="airaware_history.csv",
            mime="text/csv",
        )

# ---------- Tab 2: 3D map ----------
with tab2:
    st.subheader("🗺️ Live air quality map of India")
    st.caption(
        "One reading for each state and union territory (nearest monitoring station). "
        "Drag to rotate, scroll to zoom, hold Ctrl and drag to tilt."
    )

    if st.button("Load live map"):
        with st.spinner("Fetching live data for all states and union territories..."):
            st.session_state["map_rows"] = load_map_data()

    rows = st.session_state.get("map_rows")
    if rows:
        df = pd.DataFrame(rows)
        ELEV = 2000
        df["top"] = df["AQI"] * ELEV
        df["label"] = df["AQI"].astype(str)
        df["bubble"] = 40000 + df["AQI"] * 350

        # ---- Controls ----
        ca, cb, cc = st.columns([2, 1, 1])
        mode = ca.radio(
            "Map style", ["3D columns", "Glow bubbles", "Heat map"], horizontal=True
        )
        focus = cb.selectbox("Zoom to", ["All India"] + sorted(CITY_COORDS))
        theme = cc.selectbox("Background", ["dark", "light"])
        text_color = [255, 255, 255, 240] if theme == "dark" else [20, 20, 20, 240]

        # ---- Legend ----
        chips = "".join(
            f'<span style="background:{c};padding:4px 12px;border-radius:14px;'
            f'margin:0 6px 6px 0;color:white;font-size:13px;display:inline-block;">{t}</span>'
            for c, t in LEGEND
        )
        st.markdown(chips, unsafe_allow_html=True)

        # ---- Layers ----
        layers = []
        if mode == "3D columns":
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=df,
                    get_position=["lon", "lat"],
                    get_radius=90000,
                    get_fill_color="halo",
                    pickable=False,
                )
            )
            layers.append(
                pdk.Layer(
                    "ColumnLayer",
                    data=df,
                    get_position=["lon", "lat"],
                    get_elevation="AQI",
                    elevation_scale=ELEV,
                    radius=40000,
                    get_fill_color="color",
                    pickable=True,
                    auto_highlight=True,
                    extruded=True,
                )
            )
            label_position = ["lon", "lat", "top"]
        elif mode == "Glow bubbles":
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=df,
                    get_position=["lon", "lat"],
                    get_radius="bubble",
                    get_fill_color="halo",
                    pickable=False,
                )
            )
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=df,
                    get_position=["lon", "lat"],
                    get_radius=24000,
                    get_fill_color="color",
                    pickable=True,
                    auto_highlight=True,
                )
            )
            label_position = ["lon", "lat"]
        else:
            layers.append(
                pdk.Layer(
                    "HeatmapLayer",
                    data=df,
                    get_position=["lon", "lat"],
                    get_weight="AQI",
                    radius_pixels=80,
                    intensity=1.2,
                    threshold=0.05,
                    color_range=[
                        [46, 158, 79],
                        [212, 160, 23],
                        [232, 117, 26],
                        [214, 47, 47],
                        [142, 58, 158],
                        [126, 0, 35],
                    ],
                )
            )
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=df,
                    get_position=["lon", "lat"],
                    get_radius=14000,
                    get_fill_color="color",
                    pickable=True,
                )
            )
            label_position = ["lon", "lat"]

        layers.append(
            pdk.Layer(
                "TextLayer",
                data=df,
                get_position=label_position,
                get_text="label",
                get_size=16,
                get_color=text_color,
                get_pixel_offset=[0, -8],
                pickable=False,
            )
        )

        # ---- View ----
        if focus == "All India":
            lat0, lon0, zoom = 22.0, 79.0, 3.7
        else:
            lat0, lon0 = CITY_COORDS[focus]
            zoom = 6.2
        pitch = 55 if mode == "3D columns" else 0
        view = pdk.ViewState(
            latitude=lat0, longitude=lon0, zoom=zoom, pitch=pitch, bearing=10
        )

        st.pydeck_chart(
            pdk.Deck(
                layers=layers,
                initial_view_state=view,
                map_provider="carto",
                map_style=theme,
                tooltip={
                    "html": "<b>{City}</b><br/>AQI: {AQI}<br/>Station: {Station}",
                    "style": {"backgroundColor": "#102a33", "color": "white"},
                },
            ),
            height=620,
        )

        # ---- Summary cards ----
        worst = df.sort_values("AQI", ascending=False).iloc[0]
        best = df.sort_values("AQI").iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Most polluted right now", worst["City"], f"AQI {worst['AQI']}")
        c2.metric("Cleanest right now", best["City"], f"AQI {best['AQI']}")
        c3.metric("India average (these places)", round(df["AQI"].mean()))
        c4.metric("States/UTs with data", f"{len(df)} of {len(CITY_COORDS)}")

        # ---- Rankings ----
        top_max = int(max(300, df["AQI"].max()))
        left, right = st.columns(2)
        with left:
            st.markdown("**🔴 Top 5 most polluted**")
            worst5 = df.sort_values("AQI", ascending=False).head(5)[["City", "Station", "AQI"]]
            st.dataframe(
                worst5,
                hide_index=True,
                column_config={
                    "AQI": st.column_config.ProgressColumn(
                        "AQI", min_value=0, max_value=top_max, format="%d"
                    )
                },
            )
        with right:
            st.markdown("**🟢 Top 5 cleanest**")
            best5 = df.sort_values("AQI").head(5)[["City", "Station", "AQI"]]
            st.dataframe(
                best5,
                hide_index=True,
                column_config={
                    "AQI": st.column_config.ProgressColumn(
                        "AQI", min_value=0, max_value=top_max, format="%d"
                    )
                },
            )

        st.bar_chart(df.set_index("City")["AQI"])
    elif rows is not None:
        st.warning("No data came back. Check your internet connection and click Load live map again.")
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
        "22 µg/m³ of PM2.5 is about one cigarette a day. The sky picture is drawn "
        "in code and only illustrates how hazy the air is."
    )
    st.write(
        "Alerts: email works for any address. Telegram alerts go to the chat ID the user "
        "types in, after they press Start on our bot. If email is blocked on a network, "
        "the alert falls back to Telegram."
    )
    st.write(
        "Limitations: readings come from monitoring stations, which are mostly in cities. "
        "Each state on the map shows the nearest available station. Alerts are sent "
        "while the website is open, and history is saved only when a city is checked."
    )
    st.caption("General guidance only, not medical advice.")