#!/bin/sh

#setserial -v /dev/ttyS0 low_latency

# https://gpsd.gitlab.io/gpsd/gpsd.html
# -n .. don’t wait for a client to connect before polling whatever GPS is associated with it
# -b .. broken-device-safety mode, otherwise known as read-only mode
# -s .. serial port speed to the GNSS device
# -S .. TCP/IP port on which to listen for GPSD clients

echo "starting gpsd: port=$GPSD_TCP_PORT baud=$GPS_BAUDRATE source=$GPS_SOURCE pps=$PPS_SOURCE"
gpsd -n -b -S ${GPSD_TCP_PORT:-2947} -s $GPS_BAUDRATE $GPS_SOURCE $PPS_SOURCE
echo "started gpsd"

sleep 2

echo "removing old chrony pid file"
rm -f run/chronyd.pid

echo "replacing pps device in chrony config"
if [ -n "$PPS_SOURCE" ]; then
    echo "using PPS ${PPS_SOURCE}"
    sed "s#PPS_REFCLOCK#refclock PPS ${PPS_SOURCE} lock NMEA refid PPS prefer#g" /etc/chrony/chrony.conf_orig > /etc/chrony/chrony.conf
else
    echo "do not use PPS"
    sed "s/PPS_REFCLOCK//g" /etc/chrony/chrony.conf_orig > /etc/chrony/chrony.conf
fi
# cat /etc/chrony/chrony.conf

echo "starting chronyd"
chronyd
echo "started chrony"

# if the PPS source is the DCD pin of a tty, find originating tty device
PPS_TTY_SOURCE=$(cat "${PPS_SOURCE/"dev"/"sys/class/pps"}/path")

echo "found tty: $PPS_TTY_SOURCE for pps: $PPS_SOURCE"

# query tty pin states regularly to keep it awake
python3 -c """
import fcntl, struct, termios, time, signal
tty_interface = '$PPS_TTY_SOURCE'
if tty_interface:
    print(f'keeping {tty_interface} alive')
    fd = open(tty_interface, 'r')
    raw = struct.pack('@i', 18)
    while True:
        time.sleep(1.5)
        # get the status of modem bits
        fcntl.ioctl(fd, termios.TIOCMGET, raw)
else:
    print('ERROR: no PPS_TTY_SOURCE available')
    signal.pause()
"""
