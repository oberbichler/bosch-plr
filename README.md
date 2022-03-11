# Python Bluetooth interface for Bosch PLR devices

Python interface to remote control BOSCH PLM 40 C (might also work with other devices).

It implements the *exchange data container* where measurements are triggered by the device ("Event by LRF" similar to the MeasureOn App).

## Features
- measure distance
- turn laser on and off
- turn display backlight on and off
- get device name and device info (serial number, HW/SW version...)
- recive data from device via exchange data container ("Event by LRF")

## Dependencies
The interface uses the Bluetooth module from [PyQt5](https://pypi.org/project/PyQt6/). It uses [crc](https://pypi.org/project/crc/) to compute checksums. [qasync](https://pypi.org/project/qasync/) allows the usage of `asyncio` with `PyQt`. [Poetry](https://python-poetry.org/) is used as build system.

## Example

The interface taskes advantage of `async/await`.

```python
from bosch_plr.device import Device
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop, asyncSlot
import asyncio
import json

app = QApplication([])

loop = QEventLoop(app)
asyncio.set_event_loop(loop)

async def main():
  device = Device()

  await device.connect('<mac-address of the device>')

  info = await device.info()
  
  print(info)

  distance = await device.measure()  # trigger measurement from computer

  print(distance)

  await device.disconnect()

if __name__ ==  '__main__':
    loop.run_until_complete(main())

>>> info = {'date_code': '131', 'serial_number': ..., 'sw_revision': 2263, 'sw_version': '1.3.3', 'hw_version': '6.0.0', 'part_number': '...'}
>>> distance = 47.318
```

## Run sandbox
```shell
poetry run sandbox
```

## Reference
- [Bosch_GLM_PLR_Bluetooth_App_Kit](https://developer.bosch.com/products-and-services/sdks/bosch-glm-plr-app-kit)
- [Hacking the Bosch GLM 20 Laser Measuring Tape](https://www.eevblog.com/forum/projects/hacking-the-bosch-glm-20-laser-measuring-tape/msg1331649/#msg1331649)
- Android Bluetooth HCI snoop log + [Wireshark](https://www.wireshark.org/)
