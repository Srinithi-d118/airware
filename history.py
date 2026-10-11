import csv
import os
from datetime import datetime

import pandas as pd

FILE = "history.csv"
COLUMNS = ["time", "city", "station", "aqi", "pm25"]


def load_history():
    if not os.path.exists(FILE):
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(FILE)
    df["time"] = pd.to_datetime(df["time"])
    return df


def save_reading(city, station, aqi, pm25):
    now = datetime.now()

    # Do not save the same reading twice within 10 minutes
    df = load_history()
    if not df.empty:
        same_city = df[df["city"] == city]
        if not same_city.empty:
            last = same_city.iloc[-1]
            seconds = (now - last["time"]).total_seconds()
            if seconds < 600 and int(last["aqi"]) == int(aqi):
                return

    is_new_file = not os.path.exists(FILE)
    with open(FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(COLUMNS)
        writer.writerow([now.strftime("%Y-%m-%d %H:%M:%S"), city, station, aqi, pm25])