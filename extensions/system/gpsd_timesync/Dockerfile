FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

# install gpsd and chrony
RUN apt-get -y install chrony gpsd pps-tools

# install gpsmon debug tool
RUN apt-get -y --no-install-recommends install gpsd-clients

COPY ./extensions/system/gpsd_timesync/chrony.conf /etc/chrony/chrony.conf_orig
COPY ./extensions/system/gpsd_timesync/run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]

# docker run --rm -it --name="gpstest" --network="host" --cap-add SYS_TIME --device=/dev/pps1:/dev/pps1 --device=/dev/ttyUSB1:/dev/ttyUSB1 -e GPS_BAUDRATE=115200 -e GPS_SOURCE=/dev/ttyUSB1 -e PPS_SOURCE=/dev/pps1 -e GPSD_TCP_PORT=2947 amff/db_system_gpsd_timesync:latest

# CLI command to start docker with privileged and network mode host
# docker run -it --rm --privileged --network="host" amff/db_system_gpsd_timesync:latest bash