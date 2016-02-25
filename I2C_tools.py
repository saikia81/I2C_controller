#!/usr/bin/python2
# coding=utf-8

import sys
import itertools as itert
from time import sleep, time
import time

import I2C_controller
from I2C_controller import register_lookup
from I2C_controller import data_lookup
from I2C_controller import register_addresses
from I2C_controller import variables
from I2C_controller import device_factory
from I2C_controller import register_names
from I2C_controller import repr_binary
from I2C_controller import find_int

try:
    from watchdog import Watchdog
except ImportError:
    print("[-]warning: no watchdog found")

# global variables
actions = {}  # filled after function declarations
modes = {}  # filled after function declarations
last_command = {'action': None}  # save the last command for reusing


def turn_bit_on(column_value, row_value, address):
    address_column, address_row = 2**address[0], 2**address[1]
    if column_value & address_column == 0:
        column_value += address_column
    if row_value & address_row == 0:
        row_value += address_row
    return column_value, row_value

def turn_bit_off(column_value, row_value, address):
    address_column, address_row = 2**address[0], 2**address[1]

    if column_value & address_column == 0 or row_value & address_row == 0:
        return column_value, row_value

    if address_row ^ row_value != 0:
        column_value -= address_column

    if address_column ^ column_value != 0:
        row_value -= address_row

    return column_value, row_value


# parse functions
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
        if type(var_names) not in [list, tuple, str] and var_names is not None:
            raise TypeError(var_names)
        elif var_names is None:
            return command  # if no variables are needed: the function is done

        for var in exclude:  # excluding variables; optional
            var_names.remove(var)

        # todo: god please tidy this up! (this could be done more functionally)
        # do it yourself!


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


# parse command dictionary, finds the function and call it with the parsed parameters
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
            if type(var_names) == str: var_names = (var_names,)
            args.extend([command[var] for var in var_names])  # variables sorted for function call

        parameters_list = list(map(list, itert.product(*args)))  # build list of parameter lists that can be run
        # todo: add correction/control code for command_list generation (replace iter.product)
        # my statistics class didn't use Python, no idea which expression to use, sorry :(

        for parameters in parameters_list:
            try:
                actions[action][0](*parameters)
                print("[+]command: " + repr(parameters))
                if command['action'] not in ('redo', 'repeat'):  # make sure no recursion happens
                    last_command = command
            except IOError as ex:
                print("[-]IO failed: '" + repr(parameters) + "'")  # uses copy of args for output
                print(ex.message)
    else:
        print("[-]no action: '" + repr(args) + "'")  # uses copy of args for output


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


def timer(time, action, *parameters):
    if action not in actions.keys():
        print("[-]action: '" + action + "' not found!")
        return
    while (True):
        parse_command(parse_command_strings(action + ' '.join(parameters)))
        sleep(1)
        # todo: finish timer function


# actions
def write_byte(device_addr, reg, data):
    if reg == "a":
        reg = "GPIOA"
    elif reg == "b":
        reg = "GPIOB"
    data = data_lookup(data)
    reg = register_lookup(reg)
    device = device_factory(device_addr)

    device.write_byte(reg, data)


def read_byte(device_addr, reg):
    device = device_factory(device_addr)
    reg = register_lookup(reg)
    data = device.read_byte(reg)
    print("[+]read: " + register_names[reg] + ": " + repr_binary(data))
    return data


def pin_mode(device_addr, reg, io):  # todo: rewrite into 'port_mode'
    device = device_factory(device_addr)
    device.pin_mode(reg, io)

    # print("[-]Invalid register: " + repr(gpiox)) # todo: handle success result


def blink(device, reg, blink_amount=3):
    print("[+]blinking: " + repr(device) + " " + repr(reg))

    for x in xrange(blink_amount):
        write_byte(device, reg, 0b00000000)
        sleep(1)
        write_byte(device, reg, 0b11111111)
        sleep(1)


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
    for line in repr(device).split('\n'):
        print("| " + line)
    print("-----------------------")


def find_devices():
    devices = list()
    for i in xrange(128):
        try:
            device_factory(i)
            devices.append(i)
            print(i)
        except IOError:
            pass
        return devices

def turn_on_address(device_addrss, column, row):
    device = device_factory(device_addrss)
    column, row = find_int(column), find_int(row)
    column, row = turn_bit_on(0, 0, (column, row))
    if 0 > column > 8 or 0 > row > 8:
        raise ValueError("[-] column and row have to be 0 to 8, instead\nrow: {}\ncolumn: {}".format(row, column))
    device.write_port('A', column)
    device.write_port('B', row)
    return

def listen(device_address):
    device = device_factory(device_address)
    change = False
    drive = 'B'
    inp = 'A'
    prev_column_data = 0
    prev_row_data = 0

    device.set_io_mode('output', drive)
    device.set_io_mode('input', inp)

    while True:
        if change:
            print("[+] input detected: row: {}| column: {}".format(repr_binary(row_data), repr_binary(column_data)))
            change = False
        column_data = device.read_port(drive)
        row_data = device.read_port(inp)
        if column_data != prev_column_data or row_data != prev_row_data:
            change = True
            prev_column_data = column_data
            prev_row_data = row_data
        time.sleep(0.1)

def watchdog(device_address):
    Watchdog(int(device_address)).start()

def speed_test(device_address):
    device = device_factory(device_address)
    start_time = time.time()
    for i in xrange(256):
        device.read_port('a')
    end_time = time.time()

    delta_time = end_time - start_time
    print("Read port 'a' 256 times in: {}ms".format(delta_time*1000))


# add functions and variables (to extend toolset)
# command structure: '[mode_name] [variable_names]'
# when no variable names are specified the default is None
# todo: Discover how None in a tuple interpretation works
modes['test_mode'] = (test_mode, (None))
modes['device_mode'] = (test_mode, (None))
modes['timer'] = (timer, (vars))
modes['listen'] = (listen, ('device_address'))

# command structure: '[action_name] [variable_values]'
actions['w'] = (write_byte, ('device', 'reg', 'data'))  # command example: 'w bus reg data' -> w 32 1 255
actions['r'] = (read_byte, ('device', 'reg'))
actions['blink'] = (blink, ('device', 'reg'))
actions['blinkx'] = (blink, ('device', 'reg', 'blink_amount'))
actions['pinm'] = (pin_mode, ('device', 'reg', 'io'))
actions['redo'] = (redo, (None))
actions['compare'] = (compare_devices_regs, ('device1', 'device2'))  # todo: add manual registry selection
actions['debug'] = (debug_IO, ('device'))
actions['list'] = (list_commands, (None))
actions['find'] = (find_devices, (None))
actions['address'] = (turn_on_address, ('device_addrss', 'column', 'row'))
actions['watchdog'] = (watchdog, ('device_address'))
actions['speed_test'] = (speed_test, ('device_address'))

# synonyms
actions['write'] = actions['w']
actions['read'] = actions['r']
actions['pinmode'] = actions['pinm']
actions['pin_mode'] = actions['pinm']
actions['repeat'] = actions['redo']
actions['cmp'] = actions['compare']
actions['dbg'] = actions['debug']
actions['lst'] = actions['list']


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
    except IOError as ex:
        print("[-]IO error: ")

    # debug
    print("++++++ debug ++++++")
    for device in I2C_controller.active_devices.values():
        print(device)
