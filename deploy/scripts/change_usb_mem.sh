#!/bin/bash

# stop on error
set -e

USBMEM_SIZE=1000


edit_usbmem_parameter () {
    if [ -f /sys/module/usbcore/parameters/usbfs_memory_mb ] ; then
        echo "Parameter usbfs_memory_mb in /sys/module/usbcore/parameters changed to $USBMEM_SIZE"
        sudo sh -c "echo $USBMEM_SIZE > /sys/module/usbcore/parameters/usbfs_memory_mb"
    fi
}


edit_grub_line () {
    local KEY=$1
    if $(grep -q "$KEY=" "/etc/default/grub"); then
        # Parameter exists. We have to append the new value.
        local LINE=$(grep "$KEY=" /etc/default/grub | sed 's/.$//')
        if ! echo "$LINE" | grep -q "usbcore.usbfs_memory_mb="; then
            LINE="$LINE usbcore.usbfs_memory_mb=$USBMEM_SIZE\""
            sudo sed -i "s/$KEY=.*$/$LINE/" /etc/default/grub
        fi
    else
        # Parameter doesn't exist. We have to append it to the end of the file.
        local LINE="$KEY=\"quiet splash usbcore.usbfs_memory_mb=$USBMEM_SIZE\""
        sudo sh -c "echo '$LINE' >> /etc/default/grub"
    fi
}


update_grub() {
    if [ -f /sbin/update-grub ] ; then
        echo "Preparing grub.cfg for next boot."
        sudo update-grub
        echo "Please reboot system to make the parameter change permanent."
    else
        echo "GRUB update script not found. Cannot change usbmem."
    fi
}


# Change usb mem: Current session
edit_usbmem_parameter

# Change usb mem: permanent (future sessions)
if [ -f /etc/default/grub ] ; then
    edit_grub_line "GRUB_CMDLINE_LINUX_DEFAULT"
    edit_grub_line "GRUB_CMDLINE_LINUX"
    update_grub
else
    echo "GRUB not found. Cannot change usbmem."
fi
