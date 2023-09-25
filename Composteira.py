import paho.mqtt.client as mqtt
import Adafruit_DHT as dht
import RPi.GPIO as GPIO
import time
import json
import glob
import sys
import os

THINGSBOARD_HOST = 'demo.thingsboard.io'
ACCESS_TOKEN = '4JlWXm7ZW3nQommCSsQk'


# Data capture and upload interval in seconds. Less interval will eventually hang the DHT22.
INTERVAL = 3

sensor_data = {'temperature': 0, 'humidity': 0}
sensor_temp = {'temperature2': 0}

next_reading = time.time() 

client = mqtt.Client()

# Set access token
client.username_pw_set(ACCESS_TOKEN)

# Connect to ThingsBoard using default MQTT port and 60 seconds keepalive interval
client.connect(THINGSBOARD_HOST, 1883, 60)

client.loop_start()

########## sensor temp 2 ######
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
 
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'

def read_temp_raw():
    f = open(device_file, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        return (temp_c)
##########
try:
    while True:
        humidity,temperature = dht.read_retry(dht.DHT22, 27)
        temperature2 = read_temp()
        humidity = round(humidity, 2)
        temperature = round(temperature, 2)
        print(u"Temperature: {:g}\u00b0C, Humidity: {:g}%, Temperature2: {:g}\u00b0C".format(temperature, humidity, temperature2))
        sensor_data['temperature'] = temperature
        sensor_data['humidity'] = humidity
        sensor_temp['temperature2'] = temperature2

        # Sending humidity and temperature data to ThingsBoard
        client.publish('v1/devices/me/telemetry', json.dumps(sensor_data), 1)
        client.publish('v1/devices/me/telemetry', json.dumps(sensor_temp), 1)
        
        next_reading += INTERVAL
        sleep_time = next_reading-time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)
except KeyboardInterrupt:
    pass

client.loop_stop()
client.disconnect()
