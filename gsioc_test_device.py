import serial
import signal
import time

""" Configuration using com0com and hub4com:

Note: Gilson 506C is connected to physical port COM1. GSIOC server points to COM12.

com0com 2.2.2.0:
>install 1 EmuBR=yes,EmuOverrun=yes PortName=COM12,EmuBR=yes,EmuOverrun=yes
>install 2 EmuBR=yes,EmuOverrun=yes PortName=COM13,EmuBR=yes,EmuOverrun=yes
>list
       CNCA2 PortName=-,EmuBR=yes,EmuOverrun=yes
       CNCB2 PortName=COM13,EmuBR=yes,EmuOverrun=yes
       CNCA1 PortName=-,EmuBR=yes,EmuOverrun=yes
       CNCB1 PortName=COM12,EmuBR=yes,EmuOverrun=yes

hub4com 2.1.0.0:
command prompt> hub4com --baud=19200 --parity=e --octs=off --route=1,2:0 --route=0:1,2 \\.\CNCA1 \\.\CNCA2 \\.\COM1

This routes all traffic from CNCA1 (<->COM12) back and forth to CNCA2 (<-> virtual COM13) and COM1 (physical port)

"""

interrupt = False

class GSIOC(object):
    """
    Virtual GSIOC object.
    """

    def __init__(self, gsioc_address, port='COM13', baudrate=19200, parity=serial.PARITY_EVEN):
        """
        Connects to a virtual COM port.

        Inputs:
        gsioc_address -- address of GSIOC virtual device
        port -- virtual COM port identifier
        baudrate -- baud rate of virtual COM port. GSIOC must be 19200, 9600, or 4800
        parity -- parity of virtual COM port. Must be even for GSIOC specification.

        8 bits, 1 stop bit are defaults and part of the GSIOC spec.
        """

        self.address = gsioc_address    # between 1 and 63
        self.active = True
        self.interrupt = False
        self.ser = serial.Serial(port=port, baudrate=baudrate, parity=parity, timeout=0.1)

        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signal, frame):
        """
        Handles stop signals for a clean exit
        """
        self.interrupt = True

    def start_loop(self):
        """
        Starts GSIOC listener. Only ends when an interrupt signal is received.
        """

        print('Starting GSIOC listener... Ctrl+C to exit.')
        self.interrupt = False

        # infinite loop to wait for a command
        while not self.interrupt:
            # waits for a command
            cmd = self.wait_for_command()

            # parses received command
            self.parse_command(cmd)

        # close serial port before exiting when interrupt is received
        self.ser.close()

    def wait_for_command(self):
        """
        Waits for an address byte from the GSIOC master. Also handles byte 255, which
        disconnects all GSIOC listeners, by sending an active break signal.
        """

        # collect single bytes. Timeout is set for responsiveness to keyboard interrupts.
        address_not_found = True
        while address_not_found & (not self.interrupt):
            comm = self.read1()

            # if address matches, echo the address
            if comm == self.address + 128:
                print(f'address matches, writing {chr(self.address + 128).encode()}')
                address_not_found = False
                self.write1(chr(self.address + 128))
            
            # if result is byte 255, send a break character
            # TODO: check if this should be self.ser.send_break
            elif comm == 255:
                print('sending break')
                self.write1(chr(10))
        
        # once address is found, read the single-byte command
        comm = self.read1()
        
        return comm

    def parse_command(self, cmd):
        """
        Parses various command bytes.

        cmd -- the ascii code number of the command byte
        """
        if cmd is not None:
            if chr(cmd) == '%':
                # identification request
                self.send('Virtual GSIOC')
            else:
                # all other commands
                print(f'Command received: {cmd}, {chr(cmd)}')
                self.send(f'You sent me {chr(cmd)}')

    def read1(self):
        """
        Reads a single byte and handles logging
        """
        comm = self.ser.read()
        if len(comm):
            print(comm)
            print(int(comm.hex(), base=16))#, len(comm), [ord(c) for c in comm])
            return int(comm.hex(), base=16)
        else:
            return None

    def read_ack(self):
        """
        Waits for acknowledgement of a sent byte from the master
        """
        ret = self.read1()
        if ret == 6:
            print('acknowledgement received')
        else:
            print(f'wrong acknowledgement character received: {ret}')

    def write1(self, char):
        """
        Writes a single character to the serial port. Latin-1 encoding is critical.
        """
        self.ser.write(char.encode(encoding='latin-1'))

    def send(self, msg):
        """
        Sends a message to the serial port, one character at a time
        """
        for char in msg[:-1]:
            self.write1(char)
            self.read_ack()

        # last character gets sent with high bit (add ASCII 128)
        self.write1(chr(ord(msg[-1]) + 128))


if __name__ == '__main__':

    virtual_port = 'COM13'
    baud_rate = 19200
    read_timeout = 0.1
    write_timeout = 0.1
    gsioc_address = 62

#    signal.signal(signal.SIGINT, signal_handler)

    gsioc = GSIOC(gsioc_address, port=virtual_port, baudrate=baud_rate, parity=serial.PARITY_EVEN)
    gsioc.start_loop()


    if 0:

        ser = serial.Serial(port='COM13', baudrate=baud_rate, parity=serial.PARITY_EVEN)

        while 1:
            comm = ser.read()
            print(comm)
            print(int(comm.hex(), base=16))#, len(comm), [ord(c) for c in comm])

        ser.close()





