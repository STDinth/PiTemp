import time
import threading
import spidev
import paho.mqtt.client as mqtt
import subprocess

# ============================ GLOBALA VARIABLER, SETUP OCH INIT ============================



# Initialize SPI
spi = spidev.SpiDev()
spi.open(0, 0)  # Open SPI bus 0, device 0 (CS0)
spi.max_speed_hz = 1000000  # 1 MHz

# MAX7219 Registers
DECODE_MODE = 0x09
INTENSITY = 0x0A
SCAN_LIMIT = 0x0B
SHUTDOWN = 0x0C
DISPLAY_TEST = 0x0F

# MQTT messages
msgRecieved = ""
msgRecievedK = ""

# Global variables
lista = []
loopActive = False
valueStrNew = ""
filePath = "/home/Pi4/PYTHON/temp_file.txt"
findDot = 0

# Segment map for 7-segment display
segmentMap = {
    '0': 0b01111110, '1': 0b00110000, '2': 0b01101101, '3': 0b01111001,
    '4': 0b00110011, '5': 0b01011011, '6': 0b01011111, '7': 0b01110000,
    '8': 0b01111111, '9': 0b01111011, ' ': 0b00000000, '.': 0b10000000
}

# ============================ FUNCTIONS FOR SPI AND DISPLAY ============================

def initializeMax7219():
    """Initialize MAX7219-display"""
    spi.xfer2([DECODE_MODE, 0x00])  # Ingen BCD-avkodning
    spi.xfer2([INTENSITY, 0x01])    # intensitet
    spi.xfer2([SCAN_LIMIT, 0x07])   # Skanna alla siffror (0-7)
    spi.xfer2([DISPLAY_TEST, 0x00]) # Stäng av displaytestläge
    spi.xfer2([SHUTDOWN, 0x01])     # Aktivera displayen

def sendDigit(position, value, addDecimal=False):
    """Sending digit to a specific position"""
    valueStr = str(value)
    segmentValue = segmentMap.get(valueStr, 0b00000000)
    if addDecimal:
        segmentValue |= segmentMap['.'] 
    spi.xfer2([position, segmentValue])

def clearDisplay():
    """Clear all segment"""
    for position in range(1, 9):
        spi.xfer2([position, 0b00000000])

def divideDigit(value):
    global lista, findDot
    lista.clear()
    findDot = str(value).find('.')
    valueStrNew = str(value)
    for i in range(len(valueStrNew)):
        digitValue = valueStrNew[i]
        if digitValue != '.':
            lista.append(digitValue)

def displayNumberFromList():
    """Display digits on max7219"""
    global findDot

    for i in range(len(lista)):
        if i == findDot - 1:  # Kontrollera om decimaltecknet ska läggas till
            sendDigit(len(lista) - i, lista[i], addDecimal=True)
        else:
            sendDigit(len(lista) - i, lista[i])

# ============================ FUNCTION FOR TEMPERATURE MANAGEMENT ============================

def readTempFromFile(filePath):
    try:
        with open(filePath, 'r') as file:
            temp = file.read().strip()
            print(f"Reading temperature from: {filePath}")

            return float(temp)
    except FileNotFoundError:
        print("Temp file not found.")
        with open("temp_file.txt", "r") as file:
            pass
    except ValueError:
        print("Could not convert temp to float.")
    return None

def sendTemperature():
    """Publish temperature to MQTT-broker"""
    while True:
        tempC = readTempFromFile(filePath)
        tempK = tempC + 273.15
        if tempC is not None:
            result = client.publish("ela23/FRA", f"{tempK:.2f}K")
            result.wait_for_publish()
        time.sleep(1)

# ============================ FUNCTIONS FOR MQTT MANAGEMENT ============================

def onConnect(client, userdata, flags, rc):
    """Callback when client connects to MQTT"""
    client.subscribe("ela23/FRA")
    client.subscribe("ela23/Hugo")

def onMessage(client, userdata, msg):
    """Callback when a message receives"""
    global msgRecieved, loopActive
    try:
        if msg.topic == "ela23/FRA":
            decodedStrK = msg.payload.decode('utf-8').rstrip('K')
            msgRecieved = float(decodedStrK)
            print(f"Received message: {msgRecieved}")
        elif msg.topic == "ela23/Hugo":
            print(f"Message from Hugo: {msg.payload.decode('utf-8')}")
            decodedMsg = msg.payload.decode('utf-8')
            if decodedMsg == "activate":
                if not loopActive:
                    loopActive = True
                    print("Activate loop")
                    sendLoopThread = threading.Thread(target=loopMsg)
                    sendLoopThread.start()
            elif decodedMsg == "deactivate":
                loopActive = False
                print("loop deactivated")  
    except ValueError:
        print("Failed to convert message to float. Received:", msg.payload)
        msgRecieved = None

def loopMsg():
    i = 1
    while loopActive:
        if i == 1:
            for j in range(10, 0, -1):
                countdown = client.publish("ela23/Hugo", f"madness begins in {j}")
                countdown.wait_for_publish()
                print(f"ela23/Hugo madess begins in {j}")
                time.sleep(1)
                flag = False
        client.publish(f"ela23/Hugo madness{i}", f"{i}")
        i += i
        


def receiveDisplayTemperature():
    """Receive from MQTT and display temperature"""
    while True:
        clearDisplay()
        if isinstance(msgRecieved, float):
            divideDigit(msgRecieved)
            displayNumberFromList()
        else:
            print("error")
        time.sleep(1)

# ============================ MAIN PROGRAM ============================

process = subprocess.Popen(['./PiTemp.sh', '&'])

# Initialize hardware
initializeMax7219()

# Create MQTT client
client = mqtt.Client()
client.on_connect = onConnect
client.on_message = onMessage
client.connect("test.mosquitto.org", 1883, 60)
client.loop_start()

# Create threads
sendThread = threading.Thread(target=sendTemperature)
receiveThread = threading.Thread(target=receiveDisplayTemperature)

sendThread.start()
receiveThread.start()

try:
    sendThread.join()
    receiveThread.join()
except KeyboardInterrupt:
    pass
finally:
    process.terminate()
    process.wait()
    subprocess.run(['pkill', '-f', 'PiTemp.sh'])
    print("\nPiTemp.sh avslutad")
    spi.close()
    client.loop_stop()
    client.disconnect()