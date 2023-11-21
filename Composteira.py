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
topic = 'v1/devices/me/telemetry'

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
    valor_min = 22500
    valor_max = 6500
    umidade_min = 0
    umidade_max = 100
    
    umidade = ((valor1 - valor_min) / (valor_max - valor_min)) * (umidade_max - umidade_min) + umidade_min
    return umidade

### Cálculo pH do solo ###
def calcular_ph(valor2):
    valor_min = 14000
    valor_max = 33000
    ph_min = 3
    ph_max = 9
    
    ph = ((valor2-valor_min)/(valor_max-valor_min)) * (ph_max-ph_min) + ph_min
    
    return ph

### Módulo relé ###
res_aquec = 17
cooler = 22
stsResAquec = 0

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(res_aquec, GPIO.OUT)
GPIO.setup(cooler, False)

### Ativar e desativar Led indicador no ThingsBoard ###
def ligar_resistencia():
    GPIO.output(res_aquec, GPIO.LOW)
    client.publish("v1/devices/me/telemetry", '{"resistencia": true}')
    
def ligar_cooler():
    GPIO.output(cooler, False)   
    client.publish("v1/devices/me/telemetry", '{"cooler": true}')
    
def desligar_resistencia():
    GPIO.output(res_aquec, GPIO.HIGH)
    client.publish("v1/devices/me/telemetry", '{"resistencia": false}')
    
def desligar_cooler():    
    GPIO.output(cooler, True)
    client.publish("v1/devices/me/telemetry", '{"cooler": false}')
    
### Sinais de monitoramento para o ThingsBoard ###
sensor_temp = {'temperatura': 0}
sensor_umid = {'umidade': 0}
sensor_ph = {'ph': 0}

cont1 = 0
cont2 = 0
cont3 = 0
salvaTempo1 = 0
salvaTempo2 = 0

try:
    while True:
        
        if cont1 == 0:
            salvaTempo1 = time.time()
            cont1 = 1
        
        if cont2 == 0:
            salvaTempo2 = time.time()
            cont2 = 1
            
        tempoDecorrido1 = time.time() - salvaTempo1
        tempoDecorrido2 = time.time() - salvaTempo2
        
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
        
        ### Lógica para acionamento da resistência de aquecimento ###
        if (temperatura < 28):
                ligar_resistencia()
               # print('Resistência ligada')
                GPIO.output(res_aquec, GPIO.LOW)
                cont3 += 1
        if (temperatura > 40):
                desligar_resistencia()
               # print('Resistência ligada')
                GPIO.output(res_aquec, GPIO.HIGH)

        ### Lógica para acionamento da ventilação forçada ###
        if (umidade > 70:
                ligar_cooler()
               # print('Ventilação forçada ligada')
                GPIO.output(cooler, False)
        else:
                desligar_cooler()
               # print('Ventilação forçada desligada')
                GPIO.output(cooler, True)
        
        ### Envio dos sinais de monitoramento para o ThingsBoard ###
        if (tempoDecorrido1 >= 20):
            sensor_temp['temperatura'] = temperatura
            sensor_umid['umidade'] = umidade
            sensor_ph['ph'] = ph
        
            client.publish(topic, json.dumps(sensor_temp), 1)
            client.publish(topic, json.dumps(sensor_umid), 1)
            client.publish(topic, json.dumps(sensor_ph), 1)
            
            print("--------------------------------------------")
            print("Temperatura: {:.2f}\u00b0C".format(temperatura))
            print("Umidade do solo: {:.2f} %".format(umidade))
            print("pH do solo: {:.2f}".format(ph))
            print("Tempo em que a resistencia ficou ligada: {:.1f}".format(cont3/60), "minutos")
            print("Aguardando 20 segundos para a próxima leitura")
            print("--------------------------------------------")
            
            cont1 = 0
        
        ### Envio dos sinais de monitoramento para o arquivo txt ###
        if (tempoDecorrido2 >= 3579 and tempoDecorrido2 < 3599):
            ligar_cooler()
        else:
            desligar_cooler()
        
        if (tempoDecorrido2 >= 3600):
            data_e_hora = datetime.datetime.now().strftime("%d-%m-%Y  %H:%M:%S")
        
            with open('dados.txt', 'a') as arquivo:
                 arquivo.write(f'{data_e_hora} - Temperatura: {temperatura}  /  Umidade: {umidade}  /  pH: {ph}\n')
            
            print("dados escritos")
            cont2 = 0
            
except KeyboardInterrupt:
    pass

client.loop_stop()
client.disconnect()
