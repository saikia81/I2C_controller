import sys
import smbus
import time

register_names = {0x00:"IODIRA", 0x01:"IODIRB", 0x02:"IPOLA", 0x03:"IPOLB", 
    0x04:"GPINTENA", 0x05:"GPINTENB", 0x06:"DEFVALA", 0x07:"DEFVALB", 0x08:"INTCONA", 
    0x09:"INTCONB", 0x0A:"IOCON", 0x0B:"IOCON", 0x0C:"GPPUA", 0x0D:"GPPUB", 
    0x0E:"INTFA", 0x0F:"INTFB", 0x10:"INTCAPA", 0x11:"INTCAPB", 0x12:"GPIOA", 
    0x13:"GPIOB", 0x14:"OLATA", 0x15:"OLATB"}

register_values = dict([(name,value) for value, name in register_names.items()]) #reverse register_names


variables = {'on':255, 'off':0, 'input' : 255, 'output' : 0}

active_busses = {}
on = 255
off = 0
input = 255
output = 0


def parse_commands(commands, bus = False):
    if len(commands) == 0:
        return
    
    data = ""
    if commands[0] == "test_mode":
        length = 1
        command = ['']
        while command[0] not in ['q','qqq','quit','exit','stop']:
            command = raw_input("\ntest_mode> ").split()
            parse_commands(command)
        
    if commands[0] == 'input_loop':
        length = 1
        busses = []
        for argument in xrange(1, 4):
            try:
                busses.append(I2CBus(commands[argument]))
                length += 1
            except IndexError:
                break
            except:
                print("something went wrong interpreting: " + commands[argument])
                exit()

        for bus in busses:
            bus.set_register_read_mode()
        
        while True:
            bus.read_all()
        
    elif commands[0] == 'read_test': #command accepts register names ONLY
        length = 1
        busses = []
        for i in xrange(1, 5):
            try:
                busses.append(I2CBus(commands[i]))
                length += 1
            except Exception as ex:
                print("[-]" + repr(ex))
                break
        read_test(busses)
        return parse_commands(commands[length:])
    elif commands[0] == 'read_all':
        length = 2
        I2CBus(int(commands[1])).read_all()
    elif commands[0][0] == 'r':
        length = 3
    elif commands[0] == 'find':
        length = 1
        print("[+]found addresses: " + repr(I2CBus(0x20).test_address()))
        return parse_commands(commands[length:])
    elif commands[0] == 'all':
        length = 2
        all = I2CBus(0x20).test_address()
        for bus in all:
            device = I2CBus(bus)
            device.write_regs([0x00,0x01], on if commands[1] == "on" else off)
            device.write_regs([0x12,0x13], on if commands[1] == "on" else off)
        return parse_commands(commands[length:])
    elif commands[0][0] == 'w':
        length = 4
        if commands[3] == "on":
            data = 255
        elif commands[3] == "off": 
            data = 0
        else:
            data = int(commands[3])
    else:
        print("command not recognized: " + repr(commands))
        return

    if len(commands) < length:
        print("[-]command missing parameter (2 for read, 3 for write)")
        return
        
    bus = I2CBus(int(commands[1]))

    
    try:
        reg = commands[2]
        reg = register_values[reg]
    except KeyError:
        print("register not found in dic")
        try:
            reg = int(commands[2])
        except ValueError:
            print("register not an int")
            if reg.lower() == "a":
                reg = 0x12
            elif reg.lower() == "b":
                reg = 0x13
            elif reg.lower() == "gppux":
                reg = [0x0C, 0x0D]
            elif reg.lower() == "iodirx":
                reg = [0x00, 0x01]
            elif reg.lower() == "gpiox":
                reg = [0x12, 0x13]
            else:
                print("[-]couldn't interpret register: " + repr(reg))
    except IndexError:
        return parse_commands(commands[length:])
        
    rw = commands[0][0]
    if rw == 'r':
        print("[+]read!")
        bus.read_regs(reg)
    elif rw == 'w':
        print("[+]write!")
        bus.write_regs(reg, data)
           
    print("\n[+]command: " + rw + " " + repr(reg) +  " " +  repr(data))
    print(repr(bus))
           
    return parse_commands(commands[length:])

def read_test(busses):
    if len(busses) == 1:
        busses.set_register_read_mode([0, 1])
        busses.read_all()
    elif len(busses) > 1:
        for bus in busses:
            bus.set_register_read_mode([0, 1])
            bus.read_all()
    else:
        print("[-]no buss(es) specified for read_test!")
        
        
class I2CBus(object):
    def __init__(self, BUS_ADDRESS = 0x20):
        print("[+]init: " + repr(BUS_ADDRESS))
        self.data_matrix = [[['w', 0]]*8]*2
        self.LINUX_BUS_ADDRESS = 1 
        self.BUS_ADDRESS = BUS_ADDRESS
        
        if BUS_ADDRESS in active_busses.keys():
            self.bus = active_busses[BUS_ADDRESS]
        else:
            self.bus = smbus.SMBus(self.LINUX_BUS_ADDRESS)
            active_busses[BUS_ADDRESS] = self.bus
            
    def __repr__(self):
        gpioA_str = bin(self.read_byte(0x12))
        gpioB_str = bin(self.read_byte(0x13))
        return """
---- bus {0} ----
GPIOA:  {1}
IODIRA: {2}
GPIOB:  {3}
IODIRA: {4}
------------------
""".format(self.BUS_ADDRESS, gpioA_str, bin(self.read_byte(0x00)), gpioB_str, bin(self.read_byte(0x01)))

    def check_read_mode(self, reg = [0x12, 0x13], bit_pos = -1):
        reg = reg - 0x12 if reg - 0x12 == 0  else reg #accepts GPIOx or DIORx
        
        if bit_pos != -1:
            read_or_write = lambda rw: 1 if rw == 'r' else 0
            return [read_or_write(i) for i in self.data_matrix[reg][::2]][bit_pos]
        else:
            return 1 if 'w' not in self.data_matrix[reg][::2] else 0
            
    def read_single_bit(self, reg = [0x12, 0x13], bit_pos = -1): #least significant bit is 0
        if 0 < (self.read_byte(reg) & 2**bit_pos):
            print("bit: " + repr(bit_pos) + "@" + register_names[reg] + "\t: " + repr(0 < self.read_byte(reg) & 2**bit_pos))
        else:
            print("[-]PinMode is write")
            
    def set_register_write_mode(self, IODIRx, pin_data = 0b00000000):
        if IODIRx[-1] == "A":
            reg = self.IODIRA
        elif IODIRx[-1] == "B":
            reg = self.IODIRB
        else:
            return 1
            
        for index, pin in enumerate(bin(pin_data)[2:]):
            print("[rm]" + repr(index), repr(pin))
            self.data_matrix[reg][index][0] = 'r' if pin else 'w'
        
        self.write_byte(IODIRx, pin_data)
        
    def set_register_read_mode(self, IODIRx = [0x12, 0x13], pin_data = 255):
        regs = []
        if IODIRx[-1] == "A":
            regs.append(self.IODIRA)
        elif IODIRx[-1] == "B":
            regs.append(self.IODIRB)
        elif str not in map(type, IODIRx): #checks if an int is availabe, doesn't check if all are int
            regs = [int(reg) for reg in IODIRx]
        else:
            return 1
        print "debug: " + repr(regs)
        for reg in regs:
            for index, pin in enumerate(format(pin_data, '08b')[:]):
                print("[rm] " + repr(index + 1) + " : " + pin)
                #self.data_matrix[reg][index][0] = 'r' if pin else 'w'
            self.write_byte(reg, pin_data)
    
    #returns list with found addresses
    def test_address(self, start = 0, end = 101):
        print("[+]looking for adresses")
        found = []
        for i in xrange(start, end):
            try:
                self.bus.read_byte_data(i, 0)
                print("[+]  found: " + repr(i))
                found.append(i)
            except IOError:
                continue
        if len(found) == 0:
            print("[-]nothing was found")
        return found
    
    def read_byte(self, reg):
        if reg is not str:
            print("[-]reg is: " + repr(type(reg)))
            
        register_name = register_names[reg]          
            
        data = self.bus.read_byte_data(self.BUS_ADDRESS, reg)
        print("[+]register: " + register_name + "\t=  " + repr(bin(data)) + "")   
        return data
    
    def read_regs(self, regs = [0x12, 0x13]):
        if type(regs) is int:
            self.read_byte(regs)
        elif type(regs) is list:
            for reg in regs:
                self.read_byte(reg)
        else:
            print("[-]regs is not a list or int!")
    
    def read_all(self):
        for reg in register_names.keys():
            print(repr(reg) +  ": " + repr(bin(self.read_byte(reg))))
        
    def write_byte(self, reg, data):
        print("[+]writing to: " + register_names[18] + "\tdata: " + repr(255))
        self.bus.write_byte_data(self.BUS_ADDRESS, reg, data)
        
    def write_regs(self, regs, data):
        if type(regs) is int:
            self.write_byte(regs, data)
        elif type(regs) is list:
            for reg in regs:
                self.write_byte(reg, data)
        else:
            print("[-]regs is not a list or ")
        
    def all_on(self):
        self.write_byte(0x12, 0xff)
        self.write_byte(0x13, 0xff)
        
    def all_off(self):
        self.write_byte(0x12, 0x00)
        self.write_byte(0x13, 0x00)
        
    def IODIRx(self, x = [0,1], pinMode = 1): #work in progress
        if pinMode[0] == 'o':
            pinMode = 1
        else:
            pinMode = 0
        print("[+]testing: " + repr(self.BUS_ADDRESS))
        
    def test (self):
        print("[+]testing: " + repr(self.BUS_ADDRESS))
        self.write_byte(self.GPIOA, 0b11111111)
        self.write_byte(self.GPIOB, 0b11111111)
        time.sleep(2)
        self.write_byte(self.GPIOA, 0b00000000)
        self.write_byte(self.GPIOB, 0b00000000)
        print self.bus.read_byte_data(self.BUS_ADDRESS, self.GPIOA)
        print self.bus.read_byte_data(self.BUS_ADDRESS, self.GPIOB)
        time.sleep(2)
        self.write_byte(self.GPIOA, 0b11111111)
        self.write_byte(self.GPIOB, 0b11111111)
        print self.bus.read_byte_data(self.BUS_ADDRESS, self.GPIOA)
        print self.bus.read_byte_data(self.BUS_ADDRESS, self.GPIOB)
        time.sleep(2)
        
        
    #off-on
    def blink(self, blink_amount = 1, GPIOs = [0X12, 0X13]):
        print("[+]blinking: " + repr(self.BUS_ADDRESS) + " " + repr(GPIOs))
        for GPIOx in GPIOs:
            self.write_byte(GPIOx, 0b11111111)
        
        for x in xrange(blink_amount):
            print("[+]blink")
            for GPIOx in GPIOs:
                self.write_byte(GPIOx, 0b00000000)
            time.sleep(1)
            for GPIOx in GPIOs:
                self.write_byte(GPIOx, 0b11111111)
            time.sleep(1)
            
    def show(self, GPIOx = 0x12):
        print("showing: " + repr(self.BUS_ADDRESS))
        self.blink(3)
        time.sleep(2)
        for x in xrange(5):
            for i in xrange(0,8):
                self.write_byte(GPIOx, 0b11111111 - 2**i)
            time.sleep(1)
        self.blink(10)
                
def test():
    device0 = I2CBus(0x20)
    #device0.find_addresses(end=50)
    device1 = I2CBus(0x21)
    device2 = I2CBus(0x22)
    device2.read_all()
    device2.write_byte(0x12, 0xff)
    print("--------------------")
    device2.write_byte(0x13, 0xff)
    device2.read_all()
    
    
    device0.all_on()
    device1.all_on()
    device2.all_on()
    
    #device2.show()
    
    device0.all_off()
    device1.all_off()
    device2.all_off()
    
    device2.set_register_read_mode("A")
    device2.set_register_read_mode("A")
    device2.read_all()
    device2.read_single_bit(0x13, 2)

if __name__ == '__main__':
    parse_commands(sys.argv[1:]) #give all command line arguments to parser (excludes file name; parameter 1)
    
