from bosch_plr.device import Device

from PyQt6 import QtBluetooth
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QComboBox
from qasync import QEventLoop, asyncSlot

import asyncio
import json
import sys

app = QApplication(sys.argv)

loop = QEventLoop(app)
asyncio.set_event_loop(loop)

device = Device()


def device_found(info):
    name = info.name()

    if not name.startswith('Bosch PLR'):
        return

    address = info.address().toString()    
    
    device_list.addItem(name, address)

def device_selected(_):
    global device
    
    if device is not None:
        device.disconnect()
    
    address = device_list.currentData()

    device = Device()

    device.connected.connect(connected)
    device.disconnected.connect(disconnected)
    device.received_measurement.connect(received_measurement)

    device.connect(address)

def connected():
    print('connected')

def disconnected():
    print('disconnected')

def received_measurement(data):
    print(json.dumps(data, indent=2))

@asyncSlot()
async def name(_):
    print(await device.name())

@asyncSlot()
async def measure(_):
    print(await device.measure())

@asyncSlot()
async def info(_):
    print(await device.info())


group = QWidget()
group.setLayout(QVBoxLayout())
group.setMinimumWidth(200)

device_list = QComboBox()
device_list.currentIndexChanged.connect(device_selected)
group.layout().addWidget(device_list)

button = QPushButton('Measure')
button.clicked.connect(measure)
group.layout().addWidget(button)

button = QPushButton('Laser on')
button.clicked.connect(lambda: device.laser_on())
group.layout().addWidget(button)

button = QPushButton('Laser off')
button.clicked.connect(lambda: device.laser_off())
group.layout().addWidget(button)

button = QPushButton('Backlight on')
button.clicked.connect(lambda: device.backlight_on())
group.layout().addWidget(button)

button = QPushButton('Backlight off')
button.clicked.connect(lambda: device.backlight_off())
group.layout().addWidget(button)

button = QPushButton('Device info')
button.clicked.connect(info)
group.layout().addWidget(button)

button = QPushButton('Device name')
button.clicked.connect(name)
group.layout().addWidget(button)

button = QPushButton('Begin receive')
button.clicked.connect(lambda: device.begin_receive())
group.layout().addWidget(button)

# search for devices

discovery_agent = QtBluetooth.QBluetoothDeviceDiscoveryAgent()
discovery_agent.setLowEnergyDiscoveryTimeout(5000)
discovery_agent.deviceDiscovered.connect(device_found)
discovery_agent.start(QtBluetooth.QBluetoothDeviceDiscoveryAgent.DiscoveryMethod.ClassicMethod)

def run():
    group.show()

    with loop:
        loop.run_forever()


if __name__ == '__main__':
    run()
