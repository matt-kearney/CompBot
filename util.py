import os

lanes = ["MID", "ADC", "SUP", "JUN", "TOP"]


def valid_lane(lane):
    return lane.upper() in lanes


def debug(message):
    if os.environ.get("DEBUG", -1) == "True":
        print("[DEBUG]", message)

def role_text(role):
    role = role.upper()
    if role == "mid":
        return "Mid"
    if role == "adc":
        return "ADC"
    if role == "sup":
        return "Support"
    if role == "top":
        return "Top"
    if role == "jun":
        return "Jungle"
