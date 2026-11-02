from datetime import datetime, timezone, timedelta
import tkinter as tk
from tkinter import messagebox
import requests
import threading
import os
import time
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tkinter import scrolledtext

# Load API key from .env
load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")

GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# Cache weather results for 10 minutes
weather_cache = {}

# Configure automatic retries for temporary server errors
retry_strategy = Retry(
    total=3,
    connect=3,
    read=3,
    status=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=frozenset(["GET"])
)

session = requests.Session()

adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)


# Make an API request
def make_request(url, params):
    response = session.get(
        url,
        params=params,
        timeout=10
    )

    if response.status_code == 401:
        raise ValueError("Invalid API key or unauthorized access.")

    if response.status_code == 429:
        raise ValueError(
            "API rate limit reached. Please wait before trying again."
        )

    response.raise_for_status()

    return response.json()


# Get weather information
def get_weather(city):

    # Check cache first
    cache_key = city.lower()

    if cache_key in weather_cache:
        saved_time, saved_data = weather_cache[cache_key]

        if time.monotonic() - saved_time < 600:
            return saved_data, True

    # Step 1: Find city coordinates
    geo_params = {
        "q": city,
        "limit": 1,
        "appid": API_KEY
    }

    locations = make_request(GEO_URL, geo_params)

    if not locations:
        raise ValueError("City not found. Check the city name.")

    latitude = locations[0]["lat"]
    longitude = locations[0]["lon"]

    # Step 2: Get current weather
    weather_params = {
        "lat": latitude,
        "lon": longitude,
        "appid": API_KEY,
        "units": "metric"
    }

    data = make_request(WEATHER_URL, weather_params)

    # Save result in cache
    weather_cache[cache_key] = (time.monotonic(), data)

    return data, False

def get_forecast(city):

    # Find city coordinates
    geo_params = {
        "q": city,
        "limit": 1,
        "appid": API_KEY
    }

    locations = make_request(GEO_URL, geo_params)

    if not locations:
        raise ValueError("City not found!")

    latitude = locations[0]["lat"]
    longitude = locations[0]["lon"]

    # Request five-day forecast
    forecast_params = {
        "lat": latitude,
        "lon": longitude,
        "appid": API_KEY,
        "units": "metric"
    }

    forecast_data = make_request(
        FORECAST_URL,
        forecast_params
    )

    return forecast_data


# Display five-day forecast
def show_forecast(data):

    forecast_window = tk.Toplevel(root)
    forecast_window.title("5 Day Weather Forecast")
    forecast_window.geometry("550x500")
    forecast_window.configure(bg="#1e1e2e")

    tk.Label(
        forecast_window,
        text="5 DAY WEATHER FORECAST",
        font=("Arial", 18, "bold"),
        bg="#1e1e2e",
        fg="white"
    ).pack(pady=20)

    output = scrolledtext.ScrolledText(
        forecast_window,
        width=55,
        height=20,
        bg="#11111b",
        fg="#a6e3a1",
        font=("Consolas", 10)
    )

    output.pack(padx=15, pady=10, fill="both", expand=True)

    # Group forecast entries by local date
    timezone_offset = data["city"]["timezone"]
    daily_data = {}

    for item in data["list"]:

        local_time = (
            datetime.fromtimestamp(item["dt"], timezone.utc)
            + timedelta(seconds=timezone_offset)
        )

        day = local_time.date()

        if day not in daily_data:
            daily_data[day] = []

        daily_data[day].append((local_time, item))

    # Choose the forecast closest to noon
    for day, entries in list(daily_data.items())[:5]:

        selected_time, selected = min(
            entries,
            key=lambda entry: abs(
                entry[0].hour * 60 + entry[0].minute - 720
            )
        )

        temperature = selected["main"]["temp"]
        condition = selected["weather"][0]["description"].title()
        humidity = selected["main"]["humidity"]
        rain = selected.get("pop", 0) * 100

        output.insert(
            tk.END,
            f"\nDATE: {day.strftime('%d %B %Y')}\n"
        )

        output.insert(
            tk.END,
            f"Time: {selected_time.strftime('%I:%M %p')}\n"
        )

        output.insert(tk.END, f"Temperature: {temperature} °C\n")
        output.insert(tk.END, f"Weather: {condition}\n")
        output.insert(tk.END, f"Humidity: {humidity}%\n")
        output.insert(tk.END, f"Rain Probability: {rain:.0f}%\n")

        output.insert(tk.END, "-" * 40 + "\n")

    output.config(state="disabled")


# Fetch forecast in background
def search_forecast():

    city = city_entry.get().strip()

    if not city:
        messagebox.showwarning(
            "Input Required",
            "Enter a city name first!"
        )
        return

    if not API_KEY:
        messagebox.showerror(
            "API Key Missing",
            "Check your .env file."
        )
        return

    forecast_button.config(state="disabled")
    status_label.config(text="Loading five-day forecast...")

    def worker():

        try:
            data = get_forecast(city)

            root.after(
                0,
                lambda result=data: show_forecast(result)
            )

            root.after(
                0,
                lambda: status_label.config(
                    text="Forecast loaded successfully!"
                )
            )

        except Exception as error:
            error_message = str(error)

            root.after(
                0,
                lambda msg=error_message: show_error(msg)
            )

        finally:
            root.after(
                0,
                lambda: forecast_button.config(state="normal")
            )

    threading.Thread(
        target=worker,
        daemon=True
    ).start()



# Display weather information
def show_weather(data, cached):

    city_name = data["name"]
    country = data["sys"]["country"]

    temperature = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]

    condition = data["weather"][0]["description"].title()
    wind_speed = data["wind"]["speed"]

    result = (
        f"Location: {city_name}, {country}\n\n"
        f"Temperature: {temperature} °C\n"
        f"Feels Like: {feels_like} °C\n"
        f"Weather: {condition}\n"
        f"Humidity: {humidity}%\n"
        f"Wind Speed: {wind_speed} m/s\n\n"
        f"Data source: OpenWeather\n"
        f"Cache: {'Used saved result' if cached else 'Fresh API result'}"
    )

    result_label.config(text=result)
    status_label.config(text="Weather information loaded successfully!")


# Search button action
def search_weather():

    city = city_entry.get().strip()

    if not city:
        messagebox.showwarning(
            "Input Required",
            "Please enter a city name."
        )
        return

    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        messagebox.showerror(
            "API Key Missing",
            "Please add your API key in the .env file."
        )
        return

    search_button.config(state="disabled")
    status_label.config(text="Connecting to weather API...")
    result_label.config(text="Please wait...")

    # Run API request in background
    thread = threading.Thread(
        target=fetch_weather,
        args=(city,),
        daemon=True
    )

    thread.start()


# Fetch data without freezing the GUI

def fetch_weather(city):

    try:
        data, cached = get_weather(city)

        root.after(
            0,
            lambda: show_weather(data, cached)
        )

    except requests.exceptions.Timeout:
        root.after(
            0,
            lambda: show_error("Request timed out. Try again.")
        )

    except requests.exceptions.ConnectionError:
        root.after(
            0,
            lambda: show_error("Check your internet connection.")
        )

    except requests.exceptions.HTTPError as error:
        error_message = str(error)

        root.after(
            0,
            lambda msg=error_message: show_error(
                f"API HTTP error: {msg}"
            )
        )

    except (ValueError, KeyError) as error:
        error_message = str(error)

        root.after(
            0,
            lambda msg=error_message: show_error(msg)
        )

    except requests.exceptions.RequestException as error:
        error_message = str(error)

        root.after(
            0,
            lambda msg=error_message: show_error(
                f"Network error: {msg}"
            )
        )

    except Exception as error:
        error_message = str(error)

        root.after(
            0,
            lambda msg=error_message: show_error(
                f"Unexpected error: {msg}"
            )
        )

# Display errors
def show_error(error):

    result_label.config(text="Unable to retrieve weather data.")
    status_label.config(text="Request failed.")

    messagebox.showerror("API Error", error)


# ---------------- GUI ----------------

root = tk.Tk()

root.title("Python Weather API App")
root.geometry("600x570")
root.resizable(False, False)
root.configure(bg="#1e1e2e")

# Heading
title = tk.Label(
    root,
    text="LIVE WEATHER APP",
    font=("Arial", 22, "bold"),
    bg="#1e1e2e",
    fg="white"
)
title.pack(pady=25)

subtitle = tk.Label(
    root,
    text="Powered by OpenWeather API",
    font=("Arial", 11),
    bg="#1e1e2e",
    fg="#b0b0c0"
)
subtitle.pack()

# City input
city_label = tk.Label(
    root,
    text="Enter City Name",
    font=("Arial", 12),
    bg="#1e1e2e",
    fg="white"
)
city_label.pack(pady=15)

city_entry = tk.Entry(
    root,
    font=("Arial", 14),
    width=30,
    justify="center"
)
city_entry.pack(pady=5)

city_entry.bind(
    "<Return>",
    lambda event: search_weather()
)

# Search button
search_button = tk.Button(
    root,
    text="Get Weather",
    command=search_weather,
    font=("Arial", 12, "bold"),
    bg="#3b82f6",
    fg="white",
    padx=20,
    pady=10
)
search_button.pack(pady=20)

forecast_button = tk.Button(
    root,
    text="5 Day Forecast",
    command=search_forecast,
    font=("Arial", 11, "bold"),
    bg="#9333ea",
    fg="white",
    padx=20,
    pady=8
)

forecast_button.pack(pady=5)

# Weather result
result_label = tk.Label(
    root,
    text="Search for a city to see live weather.",
    font=("Arial", 12),
    bg="#11111b",
    fg="#a6e3a1",
    justify="left",
    width=48,
    height=11,
    anchor="w",
    padx=20
)
result_label.pack(pady=10)

# Status
status_label = tk.Label(
    root,
    text="Ready",
    font=("Arial", 10),
    bg="#1e1e2e",
    fg="#b0b0c0"
)
status_label.pack(pady=10)

# Start application
root.mainloop()
