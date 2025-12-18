import array, fcntl, struct, termios, os

fd = open("/dev/ttyS0", "wb")
raw = struct.pack('@i', 18)
fcntl.ioctl(fd, termios.TIOCSETD, raw)


#ts = termios.tcgetattr(fd)
# [1280, 5, 3261, 35387, 13, 13, [b'\x03', b'\x1c', b'\x7f', b'\x15', b'\x04', b'\x00', b'\x01', b'\x00', b'\x11', b'\x13', b'\x1a', b'\x00', b'\x12', b'\x0f', b'\x17', b'\x16', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00', b'\x00']]
#print(ts)
#termios.tcsetattr(fd, termios.TCSAFLUSH, ts) --> ldattach seems to mess this up


# setserial
# gpsd launch
# gpsd quit
# tcsetattr
# python ioctl



# this seems to keep the serial port awake:

# sudo ldattach ...
# sudo ppstest ...

# in second terminal:
import fcntl, struct, termios, time
fd = open('/dev/ttyS0', 'r')
raw = struct.pack('@i', 18)
while True:
    time.sleep(0.5)
    # get the status of modem bits
    fcntl.ioctl(fd, termios.TIOCMGET, raw)  # from https://salsa.debian.org/debian/statserial/-/blob/debian/master/statserial.c
    # https://linux.die.net/man/4/tty_ioctl

