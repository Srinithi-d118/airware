import requests
from secret import TOKEN

city = input("Enter city name: ")
url = f"https://api.waqi.info/feed/{city}/?token={TOKEN}"

try:
    response = requests.get(url, timeout=10)
    data = response.json()

    if data["status"] == "ok":
        print("Station:", data["data"]["city"]["name"])
        print("AQI:", data["data"]["aqi"])
    else:
        print("Problem:", data.get("data"))
except Exception as e:
    print("Error:", e)