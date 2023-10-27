import adafruit_ads1x15.ads1115 as ADS
import paho.mqtt.client as mqtt
import RPi.GPIO as GPIO
import datetime
import board
import busio
import time
import json
import glob
import sys
import os
from adafruit_ads1x15.analog_in import AnalogIn

### INFORMAÇÕES PARA CONEXÃO COM A PLATAFORMA THINGSBOARD ###
THINGSBOARD_HOST = 'demo.thingsboard.io'
ACCESS_TOKEN = '4JlWXm7ZW3nQommCSsQk'

sensor_temp = {'temperature2': 0}
sensor_umid = {'umidade': 0}
sensor_ph = {'ph': 0}

client = mqtt.Client()

### Token de Acesso ###
client.username_pw_set(ACCESS_TOKEN)

### Conexão ao ThingsBoard usando o protocolo MQTT em um intervalo de 60s ###
client.connect(THINGSBOARD_HOST, 1883, 60)
client.loop_start()

### Leitura do sensor de temperatura DS18B20 ###
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
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        return (temp_c)
    
### Leitura do barramento i2c e definição dos canais ###
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
canal0 = 0
canal1 = 1

### Cálculo umidade do solo ###
def calcular_umidade(valor1):
    valor_min = 26372
    valor_max = 4000
    umidade_min = 0
    umidade_max = 100
    umidade = ((valor1 - valor_min) / (valor_max - valor_min)) * (umidade_max - umidade_min) + umidade_min
    return umidade

### Cálculo pH do solo ###
def calcular_ph(valor2):
    calculo_tensao = (valor2/65535.0) * 5.0
    ph = ((calculo_tensao-0) * 1.2) + 3
    return ph

### Módulo relé ###
res_aquec = 17
cooler = 22
stsResAquec = 0

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(res_aquec, GPIO.OUT)
GPIO.setup(cooler, False)

try:
    while True:
        
        temperatura = read_temp()
        chan1 = AnalogIn(ads, canal0)
        valor1 = chan1.value
        chan2 = AnalogIn(ads, canal1)
        valor2 = chan2.value
        umidade = calcular_umidade(valor1)
        ph = calcular_ph(valor2)
        
        ### Arredondar valores para duas casas decimais ###
        temperatura = round(temperatura, 2)
        umidade = round(umidade, 2)
        ph = round(ph, 2)
        
        print("Temperatura: {:.2f}\u00b0C".format(temperatura))
        print("Umidade do solo: {:.2f} %".format(umidade))
        print("pH do solo: {:.2f}".format(ph))
        print("Aguardando 5 segundos para a próxima leitura")
        print("--------------------------------------------")
        
        ### Lógica para acionamento da resistência de aquecimento ###
        if (temperatura < 27):
                print('Resistência ligada')
                GPIO.output(res_aquec, GPIO.LOW)
        if (temperatura >= 27):
                print('Resistência desligada')
                GPIO.output(res_aquec, GPIO.HIGH)
        
        ### Lógica para acionamento da ventilação forçada ###
        if (temperatura >= 29 or umidade >= 90):
                print('Ventilação forçada ligada')
                GPIO.output(cooler, False)
        else:
                print('Ventilação forçada desligada')
                GPIO.output(cooler, True)
        
        ### Envio dos sinais de monitoramento para o ThingsBoard ###
        sensor_temp['temperatura'] = temperatura
        sensor_umid['umidade'] = umidade
        sensor_ph['ph'] = ph
        
        client.publish('v1/devices/me/telemetry', json.dumps(sensor_temp), 1)
        client.publish('v1/devices/me/telemetry', json.dumps(sensor_umid), 1)
        client.publish('v1/devices/me/telemetry', json.dumps(sensor_ph), 1)
        
        ### Envio dos sinais de monitoramento para o arquivo txt ###
        data_e_hora = datetime.datetime.now().strftime("%d-%m-%Y  %H:%M:%S")
        
        with open('dados.txt', 'a') as arquivo:
            arquivo.write(f'{data_e_hora} - Temperatura: {temperatura}  |  Umidade do solo: {umidade}  |  pH do solo: {ph}\n')
            
        time.sleep(5)
            
except KeyboardInterrupt:
    pass

client.loop_stop()
client.disconnect()