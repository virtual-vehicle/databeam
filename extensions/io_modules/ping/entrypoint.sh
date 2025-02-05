#!/bin/bash

set -e
avahi-daemon -D

exec "$@"
