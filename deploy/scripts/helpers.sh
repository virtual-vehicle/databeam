#!/bin/bash

# include this file with: source helpers.sh

# show a message between two horizontal lines
print_headline () {
    # print a continuous horizontal line
    printf '%.s\u2500' $(seq 1 $(tput cols))
    # print message from first argument
    printf "\n$1\n"
    # print a dashed horizontal line
    printf '%.s-' $(seq 1 $(tput cols))
    echo ""  # newline
}

# check if string-argument $1 is in string-argument $2
stringContain() {
    # echo "check if $1 is in $2"
    case $2 in 
        *$1* ) return 0;; 
        *) return 1;; 
    esac
}

# recursively remove trailing slashes
remove_trailing_slashes() {
    res="${1%/}"
    if [ "$1" = "$res" ]
    then echo "$res"
    else remove_trailing_slashes "$res"
    fi
}

# convert stuff like ~ or /.. to a real path
real_path() {
    echo "/$(realpath -m --relative-to / $1)"
}

# wait for y/n user input to continue
askNoYes() {
    # Returns 1 if the user answered no.
    # Returns 0 if the user answered yes.
    local q="$1 (yes or no [y/n]?) : "
    while true; do
        read -p "$q" yn
        case $yn in
            [Yy]* ) return 0; ;;
            [Nn]* ) return 1; ;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}