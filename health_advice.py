PROFILES = ["Healthy adult", "Child", "Elderly person", "Asthma / lung patient"]

LEVELS = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for sensitive groups"),
    (200, "Unhealthy"),
    (300, "Very unhealthy"),
    (500, "Hazardous"),
]

ADVICE = {
    "Good": {
        "Healthy adult": "Air is clean. Enjoy outdoor activities.",
        "Child": "Safe to play outside.",
        "Elderly person": "Safe for a normal walk.",
        "Asthma / lung patient": "Safe, but carry your inhaler as usual.",
    },
    "Moderate": {
        "Healthy adult": "Fine for outdoor activity.",
        "Child": "Outdoor play is fine. Watch for coughing.",
        "Elderly person": "Light outdoor activity is fine.",
        "Asthma / lung patient": "Limit long outdoor exertion and keep your inhaler near you.",
    },
    "Unhealthy for sensitive groups": {
        "Healthy adult": "Reduce heavy outdoor exercise.",
        "Child": "Keep outdoor play short.",
        "Elderly person": "Avoid long walks outside. Prefer indoor activity.",
        "Asthma / lung patient": "Stay indoors if possible and wear an N95 mask outside.",
    },
    "Unhealthy": {
        "Healthy adult": "Avoid heavy exercise outside. Wear a mask if you go out.",
        "Child": "Keep children indoors for play.",
        "Elderly person": "Stay indoors and keep windows closed.",
        "Asthma / lung patient": "Stay indoors, keep windows closed, and keep medicine ready.",
    },
    "Very unhealthy": {
        "Healthy adult": "Avoid outdoor activity. Wear an N95 mask if you must go out.",
        "Child": "Children should stay indoors.",
        "Elderly person": "Stay indoors. Use an air purifier if you have one.",
        "Asthma / lung patient": "Stay indoors and call a doctor if breathing gets difficult.",
    },
    "Hazardous": {
        "Healthy adult": "Stay indoors. Avoid all outdoor activity.",
        "Child": "Stay indoors with windows closed.",
        "Elderly person": "Stay indoors and seek help if you feel unwell.",
        "Asthma / lung patient": "Stay indoors. Get medical help quickly if you have symptoms.",
    },
}


def get_level(aqi):
    for max_aqi, name in LEVELS:
        if aqi <= max_aqi:
            return name
    return "Hazardous"


def get_advice(aqi, profile):
    level = get_level(aqi)
    return level, ADVICE[level][profile]