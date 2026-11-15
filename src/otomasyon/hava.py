"""Kastamonu weather from Open-Meteo (no API key)."""
import json
import urllib.request

URL = ("https://api.open-meteo.com/v1/forecast?latitude=41.3887&longitude=33.7827"
       "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m"
       "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
       "&timezone=Europe%2FIstanbul&forecast_days=2")
KOD = {0: "☀️ açık", 1: "🌤️ az bulutlu", 2: "⛅ parçalı bulutlu", 3: "☁️ kapalı", 45: "🌫️ sisli", 48: "🌫️ kırağılı sis",
       51: "🌦️ hafif çisenti", 53: "🌦️ çisenti", 55: "🌧️ yoğun çisenti", 61: "🌧️ hafif yağmur", 63: "🌧️ yağmur",
       65: "🌧️ kuvvetli yağmur", 71: "🌨️ hafif kar", 73: "🌨️ kar", 75: "❄️ yoğun kar", 80: "🌦️ sağanak",
       81: "🌧️ sağanak", 82: "⛈️ şiddetli sağanak", 95: "⛈️ fırtına"}


def ozet(gun: int = 0) -> str:
    """One line for the briefing: gun=0 today, 1 tomorrow."""
    d = json.load(urllib.request.urlopen(URL, timeout=15))["daily"]
    durum = KOD.get(d["weather_code"][gun], "?")
    return (f"{durum} {d['temperature_2m_min'][gun]:.0f}°/{d['temperature_2m_max'][gun]:.0f}°"
            f" · yağış %{d['precipitation_probability_max'][gun]}")


if __name__ == "__main__":
    c = json.load(urllib.request.urlopen(URL, timeout=15))["current"]
    print(f"Şu an: {KOD.get(c['weather_code'], '?')} {c['temperature_2m']:.0f}°C "
          f"(hissedilen {c['apparent_temperature']:.0f}°C), rüzgar {c['wind_speed_10m']:.0f} km/s")
    print("Bugün:", ozet(0))
    print("Yarın:", ozet(1))
