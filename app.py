import requests
import streamlit as st
from secret import TOKEN
from health_advice import PROFILES, get_advice

st.set_page_config(page_title="AirAware", page_icon="🌫️")
st.title("🌫️ AirAware")
st.caption("Air Quality Alert System with personal health advice")

city = st.text_input("Enter your city", "Bangalore")
profile = st.selectbox("Who are you?", PROFILES)

if st.button("Check air quality"):
    url = f"https://api.waqi.info/feed/{city}/?token={TOKEN}"
    try:
        data = requests.get(url, timeout=10).json()
        if data["status"] == "ok":
            aqi = int(data["data"]["aqi"])
            station = data["data"]["city"]["name"]
            level, advice = get_advice(aqi, profile)

            st.subheader(station)
            st.metric("Air Quality Index (AQI)", aqi)
            st.write("Level:", level)

            if aqi <= 100:
                st.success(advice)
            elif aqi <= 200:
                st.warning(advice)
            else:
                st.error(advice)
        else:
            st.error("City not found. Try another name.")
    except Exception as e:
        st.error(f"Error: {e}")

st.caption("General guidance only, not medical advice.")