from __future__ import annotations

from bosch_plr.checksum import crc8, crc32

from PyQt6.QtBluetooth import QBluetoothSocket, QBluetoothServiceInfo, QBluetoothAddress
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtWidgets import QApplication

from qasync import QEventLoop

import asyncio
import struct
from collections.abc import Awaitable
from typing import Literal


def create_request(msg):
    msg_bytes = bytearray.fromhex(msg)
    
    mode32 = msg_bytes[0] & 0b00001100

    if mode32 == 0b00000000:
        checksum = crc8(msg_bytes)
    elif mode32 == 0b00000100:
        checksum = crc8(msg_bytes)
    elif mode32 == 0b00001000:
        checksum = crc32(msg_bytes)
    else:
        return None
    
    msg_bytes.append(checksum)
    
    return bytes(msg_bytes)

def parse_frame(msg):
    frame = {}

    info = msg[0]

    # 7654 3210  = bits of first byte (info)
    # --         bit 7+6 -> frame type (response or request)
    #   -- ----  other   -> depends on type

    info76 = info & 0b11000000

    if info76 == 0b00000000:
        frame['frame_type'] = 'response'

        # device status

        # 7654 3210 = bits of first byte (info)
        #   -       bit 5 -> hand raised (e.g. device request to talk) 
        #    -      bit 4 -> device not ready (e.g. sensor not calibrated)
        #      -    bit 3 -> hardware error

        frame['hand_raised']    = info & 0b00100000 != 0
        frame['not_ready']      = info & 0b00010000 != 0
        frame['hardware_error'] = info & 0b00001000 != 0

        # communication status
        
        # 7654 3210 = bits of first byte (info)
        #       --- bits 2+1+0 -> communication status
        
        info210 = info & 0b00000111

        if info210 == 0b000:
            frame['comm_status'] = 'success'
        elif info210 == 0b001:
            frame['comm_status'] = 'communication_timeout'
        elif info210 == 0b010:
            frame['comm_status'] = 'invalid_mode'  # or "frame overflow"
        elif info210 == 0b011:
            frame['comm_status'] = 'checksum_error'
        elif info210 == 0b100:
            frame['comm_status'] = 'unknown_command'
        elif info210 == 0b101:
            frame['comm_status'] = 'invalid_access_level'
        elif info210 == 0b110:
            frame['comm_status'] = 'invalid_data'
        elif info210 == 0b111:
            frame['comm_status'] = '<reserved>'

    elif info76 == 0b11000000:
        frame['frame_type'] = 'request'
           
        # mode:
        
        # 7654 3210  = bits of first byte (info)
        #      --    bit 3+2 -> request format
        #        --  bit 1+0 -> response format

        info32 = info & 0b00001100
        
        if info32 == 0b00000000:
            frame['request_format'] = 'long'
        elif info32 == 0b00000100:
            frame['request_format'] = 'short'
        elif info32 == 0b00001000:
            frame['request_format'] = 'extended'
        else:
            frame['request_format'] = 'reserved'
        
        info10 = info & 0b00000011
        
        if info10 == 0b00000000:
            frame['response_format'] = 'long'
        elif info10 == 0b00000001:
            frame['response_format'] = 'short'
        elif info10 == 0b00000010:
            frame['response_format'] = 'extended'
        else:
            frame['response_format'] = 'reserved'

        # command 
        
        frame['command'] = msg[1]

        # data length

        if frame['request_format'] == 'long':
            data_length = msg[2]
        elif frame['request_format'] == 'short':
            data_length = 0
        elif frame['request_format'] == 'extended':
            data_length = msg[2:3]
        
        frame['data_length'] = data_length

        # data

        if frame['request_format'] == 'long':
            data = msg[3:3+data_length]
        elif frame['request_format'] == 'short':
            data = msg[3:3]  # empty
        elif frame['request_format'] == 'extended':
            data = msg[4:4+data_length]

        frame['data'] = data

        # checksum

        if frame['request_format'] == 'long':
            checksum = msg[3+data_length]
        elif frame['request_format'] == 'short':
            checksum = msg[2]
        elif frame['request_format'] == 'extended':
            checksum = msg[4+data_length]

        frame['checksum'] = checksum
    
    else:
        frame['frame_type'] = 'invalid'

    return frame

def parse_exchange_data(data):
    result = ExchangeData()

    dev_mode_ref = data[0]
    dev_status = data[1]
    
    result.id = struct.unpack('<H', data[2:4])[0]
    result.result = struct.unpack('f', data[4:8])[0]
    result.component_1 = struct.unpack('f', data[8:12])[0]
    result.component_2 = struct.unpack('f', data[12:16])[0]

    mode10 = dev_mode_ref & 0b00000011

    if mode10 == 0:
        result.mode = 'front'
    elif mode10 == 1:
        result.mode = 'tripod'
    elif mode10 == 2:
        result.mode = 'rear'
    elif mode10 == 3:
        result.mode = 'pin'

    mode3 = dev_status & 0b00001000

    if mode3 != 0:
        result.units = 'imperial'
    else:
        result.units = 'metric'
    
    status2 = dev_status & 0b00000100

    result.low_battery = status2 != 0

    status1 = dev_status & 0b00000010
    
    result.temperature_warning = status1 != 0

    status0 = dev_status & 0b00000001
    
    result.laser_on = status0 != 0
    
    return result

def parse_str(data):
    return data.decode('ascii').rstrip('\x00')

def parse_version(data):
    main, sub, bug = data
    return f'{main}.{sub}.{bug}'

def parse_info(data):
    result = {}

    result['date_code'] = parse_str(data[:4])
    result['serial_number'] = struct.unpack('I', data[4:8])[0]
    result['sw_revision'] = struct.unpack('H', data[8:10])[0]
    result['sw_version'] = parse_version(data[10:13])
    result['hw_version'] = parse_version(data[13:16])
    result['part_number'] = parse_str(data[16:29])

    return result

def request(msg):
    request_frame = create_request(msg)

    def fn(callback):
        def wrapper(device):
            future = asyncio.Future()

            def resolve(data):
                result = callback(device, data)
                future.set_result(result)

            device._socket.writeData(request_frame)
            device._resolves.append(resolve)

            return future

        return wrapper

    return fn


class ExchangeData:
    id: int
    result: float
    component_1: float
    component_2: float
    mode: Literal['front', 'tripod', 'rear', 'pin']
    units: Literal['metric', 'imperial']
    low_battery: bool
    temperature_warning: bool
    laser_on: bool


class Device(QObject):
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    received_measurement = pyqtSignal(ExchangeData)

    def __init__(self):
        super().__init__()

        self._resolves = []
        self._pending = []

        self._socket = QBluetoothSocket(QBluetoothServiceInfo.Protocol.RfcommProtocol)
        self._socket.connected.connect(lambda: self.connected.emit())
        self._socket.disconnected.connect(lambda: self.disconnected.emit())
        self._socket.readyRead.connect(self._ready_read)
        self._socket.errorOccurred.connect(self.error_occured)

    def connect(self, address, port=0x0005):
        future = asyncio.Future()

        def callback():
            future.set_result(None)
            self._socket.connected.disconnect(callback)

        self._socket.connected.connect(callback)

        self._socket.connectToService(QBluetoothAddress(address), port)

        return future

    def disconnect(self):
        future = asyncio.Future()

        if not self._socket.isOpen():
            future.set_result(None)
            return future

        def callback():
            future.set_result(None)
            self._socket.disconnected.disconnect(callback)

        self._socket.disconnected.connect(callback)

        self._socket.close()
        self._socket.disconnect()

        return future

    def error_occured(self, error):
        msg = self._socket.errorString()
        print(f'Error: {msg}')

    def _ready_read(self):
        msg = self._socket.readData(1024)

        # TODO: validate checksum

        frame = parse_frame(msg)

        if frame['frame_type'] == 'response':
            length = msg[1]
            data = msg[2:2+length]

            callback = self._resolves.pop()

            if frame['comm_status'] == 'success':
                callback(data)

        elif frame['frame_type'] == 'request':
            cmd = frame['command']

            if cmd == 85:
                exchange_data = parse_exchange_data(frame['data'])
                self.received_measurement.emit(exchange_data)

                if len(self._pending) > 0:
                    pending = self._pending.pop()
                    pending.set_result(exchange_data)
            else:
                print(f'Command {cmd} not supported.')

    @request('C0 05 00')
    def name(self, data):
        return parse_str(data)

    @request('C0 06 00')
    def info(self, data):
        return parse_info(data)

    @request('C0 40 00')
    def measure(self, data):
        distance = int(struct.unpack("<L", data)[0]) * 0.05
        return distance

    @request('C0 41 00')
    def laser_on(self, data):
        pass

    @request('C0 42 00')
    def laser_off(self, data):
        pass

    @request('C0 47 00')
    def backlight_on(self, data):
        pass

    @request('C0 48 00')
    def backlight_off(self, data):
        pass

    @request('C0 55 02 01 00')
    def begin_receive(self, data):
        return parse_exchange_data(data)

    def user_measure(self) -> Awaitable[ExchangeData]:
        future = asyncio.Future()
        self._pending.append(future)
        return future

    @staticmethod
    def run(address, port=0x0005):
        def decorator(fn):
            def runner(*args, **kwargs):
                app = QApplication([])

                loop = QEventLoop(app)
                asyncio.set_event_loop(loop)

                device = Device()

                async def program():
                    await device.connect(address, port)
                    await device.begin_receive()
                    await device.disconnect()
                
                loop.run_until_complete(program())

            return runner

        return decorator
