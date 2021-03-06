#!/usr/bin/python2
# coding=utf-8

# MPU6050 or comparable chips (some changes will have to be made to use the parser with other devices)
# This is a combination of tools to test and control the MPU6050 i2c bus, it can be easily altered to work with other
# controller types.
# This module contains 'SMBus_controller' a class which can be used to control any SMBus device, and is not limited to
# the MPU6050
# This module also contains a 'MPU6050_controller' class, which has functions to control the registries

import logging
from logging.config import fileConfig
logger = logging.getLogger()
fileConfig('logger.conf', defaults={'logfilename': 'I2C.log'})

import sys
import time

# debugging without actual smbus device (use the MPU6050 class)
class fakemodule(object):
    @staticmethod
    def SMBus(*args):
        return None
sys.modules["fakemodule"] = fakemodule

# smbus protocol (a I2C subset of features)
import smbus

# global variables
# mpu6050 register address with names
#master slave registers
register_names = {13: "SELF_TEST_X", 14: "SELF_TEST_Y", 15: "SELF_TEST_Z", 16: "SELF_TEST_A",
                  25: "SMPLRT_DIV", 26: "CONFIG", 27: "GYRO_CONFIG", 28: "ACCEL_CONFIG", 31: "MOT_THR", 35: "FIFO_EN",
                  # I2C slaves controll and config
                  36: "I2C_MST_CTRL", 37: "I2C_SLV0_ADDR", 38: "I2C_SLV0_REG", 39: "I2C_SLV0_CTRL", 40: "I2C_SLV1_ADDR",
                  41: "I2C_SLV1_REG", 42: "I2C_SLV1_CTRL", 43: "I2C_SLV2_ADDR", 44: "I2C_SLV2_REG", 45: "I2C_SLV2_CTRL",
                  47: "I2C_SLV3_REG", 48: "I2C_SLV3_CTRL", 49: "I2C_SLV4_ADDR", 50: "I2C_SLV4_REG", 51: "I2C_SLV4_DO",
                  52: "I2C_SLV4_CTRL", 53: "I2C_SLV4_DI", 54: "I2C_MST_STATUS", 55: "INT_PIN_CFG", 56: "INT_ENABLE",
                  13: "SELF_TEST_X", 14: "SELF_TEST_Y", 15: "SELF_TEST_Z", 16: "SELF_TEST_A", 25: "SMPLRT_DIV",
                  # configs
                  26: "CONFIG", 27: "GYRO_CONFIG", 28: "ACCEL_CONFIG", 31: "MOT_THR", 35: "FIFO_EN",
                  # I2C slaves controll and config
                  36: "I2C_MST_CTRL", 37: "I2C_SLV0_ADDR", 38: "I2C_SLV0_REG", 39: "I2C_SLV0_CTRL", 40: "I2C_SLV1_ADDR",
                  41: "I2C_SLV1_REG", 42: "I2C_SLV1_CTRL", 43: "I2C_SLV2_ADDR", 44: "I2C_SLV2_REG", 45: "I2C_SLV2_CTRL",
                  47: "I2C_SLV3_REG", 48: "I2C_SLV3_CTRL", 49: "I2C_SLV4_ADDR", 50: "I2C_SLV4_REG", 51: "I2C_SLV4_DO",
                  52: "I2C_SLV4_CTRL", 53: "I2C_SLV4_DI", 54: "I2C_MST_STATUS", 55: "INT_PIN_CFG",
                  # sensor value
                  64: 'ACCEL_ZOUT_L', 65: 'TEMP_OUT_H',  66: 'TEMP_OUT_L',  67: 'GYRO_XOUT_H', 68: 'GYRO_XOUT_L',
                  69: 'GYRO_YOUT_H',  70: 'GYRO_YOUT_L', 71: 'GYRO_ZOUT_H', 72: 'GYRO_ZOUT_L',
                  # external I2C data
                  73: 'EXT_SENS_DATA_00', 74: 'EXT_SENS_DATA_01', 75: 'EXT_SENS_DATA_02', 76: 'EXT_SENS_DATA_03',
                  77: 'EXT_SENS_DATA_04', 78: 'EXT_SENS_DATA_05', 79: 'EXT_SENS_DATA_06', 80: 'EXT_SENS_DATA_07',
                  81: 'EXT_SENS_DATA_08', 82: 'EXT_SENS_DATA_09', 83: 'EXT_SENS_DATA_10', 84: 'EXT_SENS_DATA_11',
                  85: 'EXT_SENS_DATA_12', 86: 'EXT_SENS_DATA_13', 87: 'EXT_SENS_DATA_14', 88: 'EXT_SENS_DATA_15',
                  89: 'EXT_SENS_DATA_16', 90: 'EXT_SENS_DATA_17', 91: 'EXT_SENS_DATA_18', 92: 'EXT_SENS_DATA_19',
                  93: 'EXT_SENS_DATA_20', 94: 'EXT_SENS_DATA_21', 95: 'EXT_SENS_DATA_22', 96: 'EXT_SENS_DATA_23',
                  # 
                  99: 'I2C_SLV0_DO', 100: 'I2C_SLV1_DO', 58: 'INT_STATUS',
                  59: 'ACCEL_XOUT_H', 60: 'ACCEL_XOUT_L', 61: 'ACCEL_YOUT_H', 62: 'ACCEL_YOUT_L', 63: 'ACCEL_ZOUT_H',
                  101: 'I2C_SLV2_DO', 102: 'I2C_SLV3_DO', 103: 'I2C_MST_DELAY_CT', 104: 'SIGNAL_PATH_RES',
                  105: 'MOT_DETECT_CTRL', 106: 'USER_CTRL', 107: 'PWR_MGMT_1', 108: 'PWR_MGMT_2', 114: 'FIFO_COUNTH',
                  115: 'FIFO_COUNTL', 116: 'FIFO_R_W', 117: 'WHO_AM_I'
                  }


register_addresses = dict([(name, address) for address, name in register_names.items()])  # reverse register_names
register_groups = [name[:-1] for name in register_names.values()[::2]]  # register types (uses register_names)

active_busses = {}  # reusing busses instead of creating new ones, every created bus should be added.
active_devices = {}  # devices (e.g. 0x20 : MPU6050())
variables = {'on': 255, 'off': 0, 'input': 255, 'output': 0}  # these are accepted write/read values


#tools
def repr_binary(data):  # returns data as a string displaying 8 bits
    if type(data) == int:
        return str(format(data, '08b'))
    else:
        raise TypeError("Invalid parameter; must be of type: 'int', not: " + repr(type(data)))

# given an int it returns the int
# given a string it looks if the string can be interpreted as a number
# if all else fails it raises a ValueError
def find_int(number):
    var_type = type(number)
    if var_type == int:
        return number
    elif var_type == str:
        if '0x' in number.lower() or '0b' in number.lower():
            return int(number, base=0)  # base=0; the base will be interpreted
        try:
            return int(number)  # string might be a number
        except ValueError:
            raise ValueError(number)
    else:
        raise TypeError("Invalid parameter; must be of type: 'int', not: " + repr(type(number)))

# given an int it returns it
# given a string it tries to interpret it as a number when prefixed with 0b (binary) or 0x (hexadecimal)
# if it fails it will try to look up the string in the registry dictionaries (global)
# if all else fails it raises a ValueError
def register_lookup(reg):
    if type(reg) == int:
        return reg
    elif type(reg) == str:
        try:
            return find_int(reg)
        except ValueError:
            pass

        try:
            return register_addresses[reg.upper()]  # known register names
        except KeyError:
            logger.error("register not found: " + reg)
            raise ValueError(reg)
    else:
        raise TypeError("Invalid parameter; must be of type: 'str' or 'int', not: " + repr(type(reg)))

# given an int it returns the int
# given a string it looks if the string can be interpreted as a number
# or if the string is found in the values dictionary (global)
# if all else fails it raises a ValueError
def data_lookup(data):  # returns the data as an int or None
    if type(data) == int:
        return data
    elif type(data) == str and len(data) != 0:
        try:
            return find_int(data)
        except ValueError:
            pass

        try:
            return variables[data]
        except KeyError:
            logger.error("[-]var not found: " + data)
            raise ValueError(data)
    else:
        raise TypeError("Invalid parameter; must be of type: 'str' or 'int', not: " + repr(type(data)))


# smbus.SMBus
# creates a bus if it doesn't exist, if it has already been created it returns the existing bus (from active_busses)
def bus_factory(bus_address):
    if bus_address in active_busses.keys():
        return active_busses[bus_address]
    else:
        try:
            active_busses[bus_address] = smbus.SMBus(bus_address)
            return active_busses[bus_address]
        except IOError:
            logger.critical("bus address not found: " + bus_address)

# creates a device if it doesn't exist, if it has already been created it returns the existing device
# uses MPU6050Controller class

def device_factory(device_addr):
    device_addr = find_int(device_addr)
    if device_addr in active_devices.keys():
        return active_devices[device_addr]
    else:
        try:
            active_devices[device_addr] = MPU6050Controller(device_addr)
            return active_devices[device_addr]
        except IOError:
            logger.critical("device not found or blocking: " + device_addr)

# smbus wrapper
# bus_address is set as 1 for raspberry pi 2 b
class SMBusController(object):
    def __init__(self, device_address, bus_address=1):
        logger.debug("init smbus: " + repr(device_address))
        self.bus_address = bus_address
        self.device_address = device_address
        self.bus = bus_factory(bus_address)

    # throws valueError when reg is not in between -1 and 33
    # reg must be an int here, if a string is available use MPU6050Controller.write_reg
    def read_byte(self, reg):
        data = -1
        if type(reg) != int or 0 > reg > 32:
            raise ValueError(reg)

        data = self.bus.read_byte_data(self.device_address, reg)

        #logger.debug("read reg: {}  |data: {}".format(repr(reg), repr(data)))  # debug
        return data

    # writes a byte 'data' to a registry 'reg'
    def write_byte(self, reg, data):
        #logger.debug("read reg: {} |data: {}".format(reg,data))  # todo: delete debug line!
        self.bus.write_byte_data(self.device_address, reg, data)


class MPU6050Controller(SMBusController):
    # makes a string representation that displays the IO_mode, and the port values
    # reads from the device for the reg values
    def __repr__(self):  # todo: change this up to only return this in string; repr should give info on the object
        return "\n---- bus {0} ----\nIODIRA: {1} \t GPIOA: {3}\nIODIRB: {2} \t GPIOB: {4}\n------------------".format(
            self.device_address,
            repr_binary(self.read_reg('IODIRA')),
            repr_binary(self.read_reg('IODIRB')),
            repr_binary(self.read_reg('GPIOA')),
            repr_binary(self.read_reg('GPIOB')))

    def __str__(self):
        return self.__repr__()

    # uses device address and active bus, making it possible to use the same address on another bus
    def __cmp__(self, other):
        return self.device_address == other.device_address and self.bus is other.bus

    #write to a registry (by name, hex, or bin string) data can be a string as well
    def write_reg(self, reg, data):
        reg = register_lookup(reg)
        data = data_lookup(data)
        #logger.warning("mode set reg: {} |data: {}".format(repr(reg), repr(data)))
        self.write_byte(reg, data)
        #logger.debug("written reg: {} |data: {}".format(register_names[reg],repr_binary(data)))

    # write data to a port-extender
    # calls write_reg
    def write_port(self, port, data):  # port A or B
        logger.debug("{} write on port {}: {}".format(self.device_address, port.upper(), repr_binary(data)))

        return self.write_reg('GPIO' + port.upper(), data)

    # read a registry (by name, hex, or bin string)
    # calls read_byte
    def read_reg(self, reg):
        reg = register_lookup(reg)  # register lookup accepts register names, and hex or bin in a string.
        data = self.read_byte(reg)
        #logger.debug("read: reg: {} |data: {}".format(reg,data))
        return data

    # read 8-bits from am IO port
    # port A or B
    def read_port(self, port):
        data = self.read_reg("GPIO" + port.upper())
        logger.debug("{} read on port {}: {}".format(self.device_address, port.upper(), repr_binary(data)))
        return data

    # set IO_mode for port(s) (default MPU6050 ports: 0x00, and 0x01)
    # multiple values accepted (including 'input', and 'output')
    # sets all (or one) of the ports to read or write
    def set_io_mode(self, io_mode, port_list=None):
        if port_list is None: port_list = ['A', 'B']  # mutual parameters (list) aren't instantiated at call, but at def
        for port in port_list:
            self.port_mode(port, io_mode)

    # returns boolean with success result
    # todo: make function shorter!
    def port_mode(self, gpiox, io_mode):
        if type(io_mode) != str or type(gpiox) not in [str, int]:
            raise TypeError('port mode parameters')

        if io_mode.lower() in ['w', 'output', 'o']:
            io_mode = 0
        elif io_mode.lower() in ['r', 'input', 'i']:
            io_mode = 255
        else:
            raise ValueError(io_mode)

        if gpiox in [0, 1]:
            pass
        elif type(gpiox) == int:
            return False  # int must be 0 or 1
        elif gpiox.upper() in ['A', 'B']:
            gpiox = 'IODIR' + gpiox.upper()
        else:
            return False

        self.write_reg('GPIO' + gpiox[-1], io_mode)
        logger.info("{} mode set on device: {} |port: {}".format('input' if io_mode==255 else 'output',
                                                                 self.device_address, gpiox))

        return True

# debug class
# fake input output, uses the cli
class MPU6050ControllerTester(MPU6050Controller):
    def __init__(self, device_address, bus_address=1):
        logger.info("init smbus: " + repr(device_address))
        self.bus_address = bus_address
        self.device_address = device_address
        self.bus = ""
        self.data_byte = 0  # fake input

    def write_byte(self, reg, data):
        logger.info("written reg: {} |data: {}".format(reg, data))

    def read_byte(self, reg, input_data = True):
        time.sleep(1)
        reg = register_lookup(reg)  # register lookup accepts register names, and hex or bin in a string.
        self.data_byte += 1
        self.data_byte = self.data_byte + 1 if self.data_byte < 8 else 0
        logger.info("input on reg: {} |data: {}".format(register_names[reg], repr_binary(self.data_byte)))
        return self.data_byte

if __name__ == '__main__':
    c = MPU6050Controller(32)
    c.write_port('A', 0)
    print("[+]  wrote 0 byte to port 'A'")
    c.write_port('B', 0)
    print("[+]  wrote 0 byte to port 'B'")
