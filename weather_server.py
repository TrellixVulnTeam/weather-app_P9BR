import sqlite3
import time
import requests
import yaml
import json
import subprocess
from flask import Flask, request
from flask_restful import Resource, Api

# Basic setup for Flask
app = Flask(__name__)
api = Api(app)

# Get secrets sorted locally
with open("secrets.yml") as y:
    token_string = yaml.safe_load(y)

# Figure out host IP to determine what IP to server from
guest_ip = subprocess.check_output(["hostname", "-I"]).strip()


def k_to_f (temp_in_k):
    f = ((9/5)*(temp_in_k - 273) + 32)
    return round(f,2) # decimal place standard is based on what I get from the API (2 decimial places)

def update_weather_table(timestamp, temp):
    conn = sqlite3.connect('weather.db')
    c = conn.cursor()
    c.execute("INSERT INTO weather VALUES (:epoch_time, :temp_f)",{'epoch_time': timestamp, 'temp_f':temp,} )
    conn.commit()
    conn.close()


def read_table_data ():
    # Read Data from table
    conn = sqlite3.connect('weather.db')
    c = conn.cursor()
    c.execute("SELECT * FROM weather")
    print(c.fetchall())
    conn.close()

# Delete Old rows (for updates to data, so we don't let the DB grow too big)
def clean_old_table_data(timestamp):
    conn = sqlite3.connect('weather.db')
    c = conn.cursor()
    c.execute("DELETE FROM weather WHERE epoch_time < ?", (timestamp,))
    conn.commit()
    conn.close()

def database_check_or_create():
    # Connect to sqlite and create db if it doesn't exist
    conn = sqlite3.connect('weather.db')
    c = conn.cursor()
    c.execute("""CREATE TABLE if not exists weather(
            epoch_time interger,
            temp_f real
    )""")
    conn.close()

def get_weather_from_api():
    api_address = "http://api.openweathermap.org/data/2.5/weather?id=4975802&appid={}".format(token_string['token'])
    response = requests.get(api_address)
    return dict(response.json())


class Weather(Resource):
    def get(self):
        conn = sqlite3.connect('weather.db')
        c = conn.cursor()
        query_data = c.execute("SELECT * FROM weather")
        data = c.fetchall()
        if (int(time.time()) - data[0][0]) < 15: # rounding time, as the source data API runs on 10-minute intervals. Milliseconds and fractions thereof aren't worth the complexity.
            result = {'weather_data_last_update': data[0][0], 'temp_in_f':data[0][1]} # Note: I know there are good json-ifying libraries out there, but of the few i tried there were issues getting all of them set up wtih the normal pip install commands. So, I figured this was a faster, dirtier, more POC-esque way of getting around the issue.
        else:
            temp_ts = int(time.time())
            weather_json = get_weather_from_api()
            update_weather_table(temp_ts, float(k_to_f(weather_json['main']['temp'])))
            clean_old_table_data(temp_ts)
            result = {'weather_data_last_update': data[0][0], 'temp_in_f':data[0][1]}
        return result
        conn.close()


# ts is timestamp in epoch
ts = int(time.time())
database_check_or_create()

api.add_resource(Weather, '/weather')

if __name__ == '__main__':
     app.run(host=guest_ip , port='5002')

