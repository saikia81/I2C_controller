#!/usr/bin/python2
# coding=utf-8

# MCP23017 or comparable chips (some changes will have to be made to use the parser with other devices)
# This is a combination of tools to test and control the MCP23017 i2c bus, it can be easily altered to work with other
# controller types.
# This module contains 'SMBus_controller' a class which can be used to control any SMBus device, and is not limited to
# the MCP23017
# This module also contains a 'MCP23017_controller' class, which has functions to control the registries

import logging
from logging.config import fileConfig
logger = logging.getLogger()
fileConfig('I2C_controller/logger.conf', defaults={'logfilename': 'I2C_controller/I2C.log'})

import sys
import time

# debugging without actual smbus device (use the MCP23017ControllerTester class)
class fakemodule(object):
    @staticmethod
    def SMBus(*args):
        return None
sys.modules["fakemodule"] = fakemodule

# smbus protocol (a I2C subset of features)
import smbus

# global variables
# MCP23017 register address with names
register_names = {0x00: "IODIRA",   0x01: "IODIRB",    0x02: "IPOLA",   0x03: "IPOLB",
                  0x04: "GPINTENA", 0x05: "GPINTENB",  0x06: "DEFVALA", 0x07: "DEFVALB",
                  0x08: "INTCONA",  0x09: "INTCONB",   0x0A: "IOCON",   0x0B: "IOCON",
                  0x0C: "GPPUA",    0x0D: "GPPUB",     0x0E: "INTFA",   0x0F: "INTFB",
                  0x10: "INTCAPA",  0x11: "INTCAPB",   0x12: "GPIOA",   0x13: "GPIOB",
                  0x14: "OLATA",    0x15: "OLATB"}


register_addresses = dict([(name, address) for address, name in register_names.items()])  # reverse register_names
register_groups = [name[:-1] for name in register_names.values()[::2]]  # register types (uses register_names)

active_busses = {}  # reusing busses instead of creating new ones, every created bus should be added.
active_devices = {}  # devices (e.g. {0x20 : MCP23017()})
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
# uses MCP23017Controller class

def device_factory(device_addr):
    device_addr = find_int(device_addr)
    if device_addr in active_devices.keys():
        return active_devices[device_addr]
    else:
        try:
            active_devices[device_addr] = MCP23017Controller(device_addr)
            return active_devices[device_addr]
        except IOError:
            logger.critical("device not found or blocking: " + device_addr)

# smbus wrapper
# bus_address is set as 1 for raspberry pi 2 b
class SMBusController(object):
    def __init__(self, device_address, bus_address=1):
        logger.info("init smbus: " + repr(device_address))
        self.bus_address = bus_address
        self.device_address = device_address
        self.bus = bus_factory(bus_address)

    # throws valueError when reg is not in between -1 and 33
    # reg must be an int here, if a string is available use MCP23017Controller.write_reg
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


class MCP23017Controller(SMBusController):
    # makes a string representation that displays the IO_mode, and the port values
    # reads from the device for the reg values
    def __repr__(self):
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

    # read 8-bits from a IO port
    # port A or B
    def read_port(self, port):
        data = self.read_reg("GPIO" + port.upper())
        logger.debug("{} read on port {}: {}".format(self.device_address, port.upper(), repr_binary(data)))
        return data

    # set IO_mode for port(s) (default MCP23017 ports: 0x00, and 0x01)
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
class MCP23017ControllerTester(MCP23017Controller):
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
    c = MCP23017Controller(32)
    c.write_port('A', 0)
    print("testing workds")
    c.write_port('B', 0)