#!/usr/bin/python
# Vendored from https://github.com/FrgyCZ/VL53L3CX-python (python/VL53L3CX.py).
# Requires vl53l3cx_python*.so from: pip install -r requirements-rpi.txt

# MIT License
#
# Copyright (c) 2017 John Bryan Moore
# Copyright (c) 2024 Jakub Frgal
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from ctypes import CDLL, CFUNCTYPE, POINTER, c_int, c_uint, pointer, c_ubyte, c_uint8, c_uint32, c_uint16
from smbus2 import SMBus, i2c_msg
import os
import site
import glob


class VL53L3CXError(RuntimeError):
    pass


# Read/write function pointer types.
_I2C_READ_FUNC = CFUNCTYPE(c_int, c_ubyte, c_uint16, POINTER(c_ubyte), c_ubyte)
_I2C_WRITE_FUNC = CFUNCTYPE(c_int, c_ubyte, c_uint16, POINTER(c_ubyte), c_ubyte)

# Load VL53L3CX shared lib
_POSSIBLE_LIBRARY_LOCATIONS = [os.path.dirname(os.path.realpath(__file__))]

try:
    _POSSIBLE_LIBRARY_LOCATIONS += site.getsitepackages()
except AttributeError:
    pass

try:
    _POSSIBLE_LIBRARY_LOCATIONS += [site.getusersitepackages()]
except AttributeError:
    pass

for lib_location in _POSSIBLE_LIBRARY_LOCATIONS:
    files = glob.glob(lib_location + "/vl53l3cx_python*.so")
    if len(files) > 0:
        lib_file = files[0]
        try:
            _TOF_LIBRARY = CDLL(lib_file)
            break
        except OSError as e:
            print("Could not load library: {}".format(e))
else:
    raise OSError('Could not find vl53l3cx_python.so')


class VL53L3CX:
    """VL53L3CX ToF."""
    def __init__(self, i2c_bus=1, i2c_address=0x29):
        """Initialize the VL53L3X ToF Sensor from ST"""
        self._i2c_bus = i2c_bus
        self.i2c_address = i2c_address

        self._i2c = SMBus()
        self.distance = -1
        try:
            self._i2c.open(bus=self._i2c_bus)
            self._i2c.read_byte_data(self.i2c_address, 0x00)
        except IOError:
            raise RuntimeError("VL53L3CX not found on adddress: {:02x}".format(self.i2c_address))
        finally:
            self._i2c.close()

        self._dev = None
        # Register Address
        self.ADDR_UNIT_ID_HIGH = 0x16  # Serial number high byte
        self.ADDR_UNIT_ID_LOW = 0x17   # Serial number low byte
        self.ADDR_I2C_ID_HIGH = 0x18   # Write serial number high byte for I2C address unlock
        self.ADDR_I2C_ID_LOW = 0x19    # Write serial number low byte for I2C address unlock
        self.ADDR_I2C_SEC_ADDR = 0x8a  # Write new I2C address after unlock

    def open(self, reset=False):
        self._i2c.open(bus=self._i2c_bus)
        self._configure_i2c_library_functions()
        self._dev = _TOF_LIBRARY.initialise(self.i2c_address, reset)

    def close(self):
        self._i2c.close()
        self._dev = None

    def _configure_i2c_library_functions(self):
        # I2C bus read callback for low level library.
        def _i2c_read(address, reg, data_p, length):
            ret_val = 0

            msg_w = i2c_msg.write(address, [reg >> 8, reg & 0xff])
            msg_r = i2c_msg.read(address, length)

            self._i2c.i2c_rdwr(msg_w, msg_r)

            if ret_val == 0:
                for index in range(length):
                    data_p[index] = ord(msg_r.buf[index])

            return ret_val

        # I2C bus write callback for low level library.
        def _i2c_write(address, reg, data_p, length):
            ret_val = 0
            data = []

            for index in range(length):
                data.append(data_p[index])

            msg_w = i2c_msg.write(address, [reg >> 8, reg & 0xff] + data)

            self._i2c.i2c_rdwr(msg_w)

            return ret_val

        # Pass i2c read/write function pointers to VL53L1X library.
        self._i2c_read_func = _I2C_READ_FUNC(_i2c_read)
        self._i2c_write_func = _I2C_WRITE_FUNC(_i2c_write)
        _TOF_LIBRARY.VL53LX_set_i2c(self._i2c_read_func, self._i2c_write_func)

    def start_ranging(self):
        """Start VL53L3CX ToF Sensor Ranging"""
        _TOF_LIBRARY.startRanging(self._dev)

    def set_distance_mode(self, mode):
        """Set distance mode

        :param mode: One of 1 = Short, 2 = Medium or 3 = Long

        """
        _TOF_LIBRARY.setDistanceMode(self._dev, mode)

    def stop_ranging(self):
        """Stop VL53L3CX ToF Sensor Ranging"""
        print(_TOF_LIBRARY.stopRanging(self._dev))

    def get_distance(self):
        """Get distance from VL53L3CX ToF Sensor"""
        self.distance = _TOF_LIBRARY.getDistance(self._dev)
        return self.distance

    def is_ranging_ready(self):
        """Check if ranging data is ready"""
        return _TOF_LIBRARY.isRangingReady(self._dev)

    def set_timing_budget(self, timing_budget):
        """Set the timing budget in microseocnds"""
        _TOF_LIBRARY.setMeasurementTimingBudgetMicroSeconds(self._dev, timing_budget)

    def change_address(self, new_address):
        status = _TOF_LIBRARY.setDeviceAddress(self._dev, new_address)
        if status == 0:
            self.i2c_address = new_address
        else:
            raise RuntimeError("change_address failed with code: {}".format(status))
        return True
        
    def wait_for_data(self):
        """Interupt the program and wait for ranging data"""
        return _TOF_LIBRARY.waitForData(self._dev)
