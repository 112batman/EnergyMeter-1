#!/usr/bin/env python3

from gpiozero import Button # Import the Button class from the GPIO Zero library to wait for meter's S0 pulse rising edge
from signal import pause
from time import monotonic
from datetime import datetime, date
from os import nice, getenv
import redis
import json
from dotenv import load_dotenv

pulsecounter = 0 # Assign start value
start = monotonic() # Start value is the current time from a monotonic clock (i.e. a clock that cannot go backwards)
interval = 0 # Assign start value
currentday = date.today().isoformat()
restart = True

INTERVAL_MAX = 120 # Energy calculation interval length in seconds
PULSE_FREQ_METER = 1000 # Pulse "frequency" in imp/kWh for the energy meter you are using (ABB C11 in this case)

S0_pulse = Button("BOARD38", False) # Meter connected to RasPi GPIO pin38 = GPIO20. Connected with an external PD and therefore internal PU/PD = False

global r
if getenv("is_docker") == "true":
    r = redis.Redis(host = "redis", port = 6379)
else:
    load_dotenv("../.env") # load .env file
    r = redis.Redis(db = getenv("redis_db_index"), password = getenv("redis_key"))
    nice(0) # Low niceness to give script high priority (not required on docker)

def new_day(): # Logic for creating an object for the start of a day
    global currentday # Make currentday available within function

    currentday = date.today().isoformat() # Update currentday

    emptyday = { # Init empty start of the day object
        "date": currentday,
        "energy": 0,
        "restart": restart
    }

    r.rpush("HP_consumption_daily", json.dumps(emptyday)) # Stringify object using json.dumps and push to database

def count_pulse():
    global pulsecounter
    global start
    global interval
    global restart

    stop = monotonic()
    elapsed = stop - start
    start = monotonic()
    interval += elapsed
    pulsecounter += 1

    if interval < INTERVAL_MAX:
        pass
    else: # When more time than INTERVAL_MAX has elapsed since the previous interval, energy and power are calculated
        energy = int((1000 / PULSE_FREQ_METER) * pulsecounter) # Energy consumed in the interval in Wh
        power = 3.6 * energy / interval # Average power in the interval in kW

        datapoint = { # Create a datapoint for the current pulse
            "datetime": datetime.now().replace(microsecond=0).isoformat(),
            "energy": energy,
            "power": round(power, 2),
            "restart": restart
        }

        r.rpush("HP_consumption", json.dumps(datapoint)) # Push current consumption (date/time, energy, power, restart flag) to database

        # Reset pulsecounter and interval
        pulsecounter = 0
        interval = 0
        
        if restart == True: # If script was (re)started
            new_day() # Create an entry in HP_consumption_daily with date of restart
            restart = False # Reset restart flag

        if date.today().isoformat() != currentday: # If this pulse is on a different day then the previous
            new_day() # Run new day logic

        lastentry = r.rpop("HP_consumption_daily") # Get stored json object (as string) and remove it from db
        parsedlastentry = json.loads(lastentry) # Convert json string to python dict
        parsedlastentry["energy"] += energy # Add energy to value of dict key "energy" 
        stringifiedentry = json.dumps(parsedlastentry) # Convert python dict to json string
        r.rpush("HP_consumption_daily", stringifiedentry) # Add string json object to the database

print("Started counting!")

S0_pulse.when_pressed = count_pulse # Wait for the S0 pulse rising edge

pause() # Prevent script from exiting