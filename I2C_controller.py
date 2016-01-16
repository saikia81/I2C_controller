#!/usr/bin/python2
# coding=utf-8

# MCP23017 or comparable chips (some changes will have to be made to use the parser with other devices)
# This is a combination of tools to test and control the MCP23017 i2c bus, it can be easily altered to work with other
# chipsets.
# This module contains 'SMBus_controller' a class which can be used to control any SMBus device, and is not limited to
# the MCP23017
# This module also contains a 'MCP23017_controller' class, which has functions to control the registries

import sys
# sys.path.append('/home/pi/Tri-Zone/pycharm-debug.egg') # remote debug
# import pydevd # remote debug
# pydevd.settrace('192.168.178.144', port=1337, stdoutToServer=True, stderrToServer=True) # remote debug

import itertools as iter
import sys
import time
import smbus  # smbus protocol (a I2C subset of features)

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

actions = {}  # filled after function declerations
modes = {}  # filled after function declerations
active_busses = {}  # reusing busses instead of creating new ones, every created bus shoud be added.
active_devices = {}  # devices (e.g. 0x20 : SMBus())
variables = {'on': 255, 'off': 0, 'input': 255, 'output': 0}  # these are accepted write/read values
last_command = {'action': None}  # save the last command for reüsing


# parse functions
def repr_binary(data):  # returns data as a string of 8 bits
    if type(data) == int:
        return str(format(data, '08b'))
    else:
        raise TypeError("Invalid parameter; must be of type: 'int', not: " + repr(type(data)))


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


def register_lookup(reg):
    if type(reg) == int:
        pass
    elif type(reg) == str:
        if '0x' in reg.lower() or '0b' in reg.lower():
            return int(reg, base=0)  # base=0; the base will be interpreted

        try:
            return int(reg)  # string might be a number
        except ValueError:
            pass

        try:
            return register_addresses[reg.higher()]  # known register names
        except KeyError:
            print("[-]register not found: " + reg)
            return
    else:
        raise TypeError("Invalid parameter; must be of type: 'str' or 'int', not: " + repr(type(reg)))


def data_lookup(data):  # returns the data as an int or None
    if type(data) == int:
        return data
    elif type(data) == str and len(data) != 0:
        if '0x' in data.lower() or '0b' in data.lower():
            try:
                return int(data, base=0)  # base=0; the base will be interpreted
            except ValueError:
                pass  # next method

        try:
            return variables[data]
        except KeyError:
            try:
                return int(data)  # if data is a number return it
            except ValueError:
                pass
            print("[-]var not found: " + data)
    else:
        raise TypeError("Invalid parameter; must be of type: 'str' or 'int', not: " + repr(type(data)))


# parser
# takes a string or list of strings. structures the command as a dictionary, 'commands' and 'modes' are function lists
# (e.g. {'action': 'write', var_name: var_value}
def parse_command_strings(command_string, exclude=None):
    if exclude is None: exclude = []
    command = {'action': None}

    # todo: try to make this into a function, or make it look nicer
    length = len(command_string)
    if length == 0:
        return command
    elif type(command_string) == str:
        command_strings = command_string.split()
        length = len(command_strings)
    elif type(command_string) == list:
        command_strings = command_string
    else:
        raise TypeError("Invalid parameter; must be of type: 'str' or 'list'")

    command['action'] = command_strings[0].lower()
    if command['action'] in actions.keys():
        function, var_names = actions[command['action']]
        if type(var_names) not in [list, tuple, str] and var_names != None:
            raise (TypeError(var_names))
        elif var_names == None:
            return command  # if no variables are needed: the function is done

        for var in exclude:  # excluding variables; optional
            var_names.remove(var)

        # todo: god please tidy this up! (this could be done more functional
        if type(var_names) == str:
            command[var_names] = ""
            string = command_strings[1].lower()  # first (and only parameter) is at 1
            if ',' in string:  # list of strings
                command[var_names] = string.translate(None, '[]').split(',')
            else:  # list of one string
                command[var_names] = [string]
        elif not len(var_names) != length - 1:  # length - 1: command_strings length minus 'action'
            for var_name in var_names:
                command[var_name] = ""
            for i, var_name in enumerate(var_names, start=1):
                string = command_strings[i].lower()
                if ',' in string:  # list of strings
                    command[var_name] = string.translate(None, '[]').split(',')
                else:  # list of one string
                    command[var_name] = [string]
        else:
            print("too many variables: " + repr(length - 1) + ". needed: " + repr(len(var_names)))
    else:
        print("action not found: '" + repr(command['action']) + "'")

    return command


# parse command dictionary, finds the function and
def parse_command(command):
    global last_command
    args = list()
    if type(command) != dict:
        print("[-]command type invalid, must be dict, instead is: " + repr(type(command)))
        return
    elif len(command) == 0:
        return

    action = command['action']
    if action in modes.keys():
        print("[+]mode activated")
        modes[action][0]()  # enter mode: 'action' in the global modes list
        return
    elif action in actions.keys():
        var_names = actions[action][-1]
        if var_names is not None:
            args.extend([command[var] for var in var_names])  # variables sorted for function call

        parameters_list = list(map(list, iter.product(*args)))  # build list of parameter lists that can be run
        # todo: add correction/control code for command_list generation (replace iter.product)

        for parameters in parameters_list:
            try:
                actions[action][0](*parameters)
                print("[+]command: " + repr(parameters))
                if command['action'] not in ('redo', 'repeat'):  # make sure no recursion happens
                    last_command = command
            except IOError:
                print("[-]IO failed: '" + repr(parameters[:].insert(0, action)) + "'")  # uses copy of args for output
    else:
        print("[-]action failed: '" + repr(args[:].insert(0, action)) + "'")  # uses copy of args for output


# modes
def test_mode():
    command = {'action': ""}
    while command['action'] not in ['q', 'quit', 'exit']:
        command = parse_command_strings(raw_input("\ntest> "))
        parse_command(command)
    quit()


def device_mode(command):
    command = {'action': ""}

    device = device_factory(raw_input("insert device address > "))

    while command['action'] not in ['q', 'quit', 'exit']:
        command = parse_command_strings(raw_input("\ntest> "), exclude=['device'])
        command['device'] = device
        parse_command(command)
    quit()


def timer(time, action, *vars):
    if action not in actions.keys():
        print("[-]action: '" + action + "' not found!")
        return
    while (True):
        parse_command(parse_command_strings(action + ' '.join(vars)))
        # todo: finish timer function


# actions
def write_byte(device_addr, reg, data):
    if reg == "a":
        reg = "GPIOA"
    elif reg == "b":
        reg = "GPIOB"
    device = device_factory(device_addr)
    device.write_byte(reg, data)


def read_byte(device_addr, reg):
    device = device_factory(device_addr)
    data = device.read_byte(reg)
    return data


def pin_mode(device_addr, reg, io):  # todo: rewrite into 'port_mode'
    device = device_factory(device_addr)
    device.pin_mode(reg, io)

    # print("[-]Invalid register: " + repr(gpiox)) # todo: handle success result


def blink(device, reg, blink_amount=3):
    print("[+]blinking: " + repr(device) + " " + repr(reg))

    for x in xrange(blink_amount):
        write_byte(device, reg, 0b00000000)
        time.sleep(1)
        write_byte(device, reg, 0b11111111)
        time.sleep(1)


def redo(repeat_amount=1):
    for i in xrange(repeat_amount):
        parse_command(last_command)


def compare_devices_regs(device1, device2,
                         regs=register_addresses.keys()):  # todo: debug
    device1_regs = dict()
    device2_regs = dict()

    for reg in regs:
        device1_regs[reg] = read_byte(device1, reg)
        device2_regs[reg] = read_byte(device2, reg)

    print("[+]registries comparison")
    for reg in regs:
        # device1_reg, device2_reg in zip(device1_regs.iteritems(), device2_regs.iteritems()):
        if device1_regs[reg] == device2_regs[reg]:
            print("[=]" + reg + ": " + repr_binary(device1[reg]))
        else:
            print("[!=]" + device1 + ": " + repr_binary(device1_regs[reg]))
            print("[!=]" + device2 + ": " + repr_binary(device2_regs[reg]))


def list_commands():
    print("-- command list --")
    print("# modes")
    for mode in modes.keys():
        print mode
    print("# actions")
    for action in actions.keys():
        print action
    print("-----------------")


def debug_IO(device_addr):
    device = device_factory(device_addr)
    print("++++++++ debug ++++++++")
    print("| " + repr(device))
    print("-----------------------")


# add functions and variables (to extend toolset)
# command structure: '[mode_name] [variable_names]'
# when no variable names are specified the default is None
# todo: Test how None in a tuble interpretation works
modes['test_mode'] = (test_mode, (None))
modes['device_mode'] = (test_mode, (None))
modes['timer'] = (timer, (vars))

# command structure: '[action_name] [variable_values]'
actions['w'] = (write_byte, ('device', 'reg', 'data'))  # command example: 'w bus reg data' -> w 32 1 255
actions['r'] = (read_byte, ('device', 'reg'))
actions['blink'] = (blink, ('device', 'reg'))
actions['blinkx'] = (blink, ('device', 'reg', 'blink_amount'))
actions['pinm'] = (pin_mode, ('device', 'reg', 'io'))
actions['redo'] = (redo, (None))
actions['compare'] = (compare_devices_regs, ('device1', 'device2'))  # todo: add manual registry selection
actions['debugio'] = (debug_IO, tuple('device'))
actions['list'] = (list_commands, (None))

# synonyms
actions['write'] = actions['w']
actions['read'] = actions['r']
actions['pinmode'] = actions['pinm']
actions['pin_mode'] = actions['pinm']
actions['repeat'] = actions['redo']
actions['cmp'] = actions['compare']
actions['dbg'] = actions['debugio']
actions['lst'] = actions['list']


# SMBus
def bus_factory(bus_address):
    if bus_address in active_busses.keys():
        return active_busses[bus_address]
    else:
        try:
            active_busses[bus_address] = smbus.SMBus(bus_address)
            return active_busses[bus_address]
        except IOError:
            print("[-]bus address not found: " + bus_address)


def device_factory(device_addr):
    device_addr = find_int(device_addr)
    if device_addr in active_devices.keys():
        return active_devices[device_addr]
    else:
        try:
            active_devices[device_addr] = SMBusController(device_addr)
            return active_devices[device_addr]
        except IOError:
            print("[-]device not found: " + device_addr)


# bus_address is set as 1 for raspberry pi 2 b
class SMBusController(object):
    def __init__(self, device_address, bus_address=1):
        print("[+]init smbus: " + repr(device_address))
        self.bus_address = bus_address
        self.device_address = device_address
        self.data_matrix = dict([(reg, 0) for reg in register_addresses.keys()])
        self.bus = bus_factory(self.bus_address)
        # print("matrix debug: " + repr(self.data_matrix))

    def __repr__(self):
        return "\n---- bus {0} ----\nIODIRA: {1} \t GPIOA: {3}\nIODIRB: {2} \t GPIOB: {4}\n------------------".format(
                self.device_address,
                repr_binary(self.read_byte('IODIRA')),
                repr_binary(self.read_byte('IODIRB')),
                repr_binary(self.read_byte('GPIOA')),
                repr_binary(self.read_byte('GPIOB')))

    def __str__(self):
        return self.__repr__()

    def __cmp__(self, other):
        return self.device_address == other.device_address \
               and self.bus is other.bus  # todo: decide betweeen device address, and active bus.

    def read_byte(self, reg):
        data = -1

        reg = register_lookup(reg)

        try:
            if reg != 0: assert (reg)  # Python interprets 0 as False, every other int returns True
        except AssertionError:
            raise ValueError(reg)

        try:
            data = self.bus.read_byte_data(self.device_address, reg)
            print("[+]read: " + register_names[reg] + ": " + repr_binary(data))
        except TypeError as ex:
            print("wrong type: accepted reg address include: string, and int. Instead found: " + str((type(reg))))
            print("[-]debug; reg: '" + repr(reg) + "' data: '" + repr(data)) + "'"  # debug
        return data

    def write_byte(self, reg, data):
        data = data_lookup(data)
        reg = register_lookup(reg)

        try:
            self.bus.write_byte_data(self.device_address, reg, data)
            print("[+]written: " + register_names[reg] + ": " + repr_binary(data))
        except:
            print("[-]Error: reg:" + repr(reg) + ", data:" + repr(data))

    # returns boolean with success result
    def port_mode(self, gpiox, IO_mode):
        if type(IO_mode) != str or type(gpiox) not in [str, int]:
            raise TypeError('port mode parameters')

        if IO_mode.lower() in ['w', 'output', 'o']:
            IO_mode = 0
        elif IO_mode.lower() in ['r', 'input', 'i']:
            IO_mode = 255
        else:
            raise ValueError(IO_mode)

        if gpiox in [0, 1]:
            pass
        elif type(gpiox) == int:
            return False  # int must be 0 or 1
        elif gpiox.lower() in ['a', 'b']:
            gpiox = 'IODIR' + gpiox.upper()
        else:
            return False

        self.write_byte(gpiox, IO_mode)
        return True


class MCP23017Controller(SMBusController):
    def write_port(self, port, data):  # port A or B
        self.wite_byte('GPIO' + port, (data))
        return True

    def read_port(self, port):  # port A or B
        data = self.read_byte("GPIO" + port.higher())
        return data

    def set_IO_mode(self, IO_mode, port_list=['a', 'b']):  # sets all (or one) of the ports to read or write
        for port in port_list:
            self.port_mode(port, IO_mode)
        return True


def main():
    if len(sys.argv) > 1:
        command = parse_command_strings(sys.argv[1:])
        print("[+]command: " + repr((command)))
        parse_command(command)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("ctrl + c")

    # debug
    print("++++++ debug ++++++")
    for device in active_devices.values():
        print(device)
