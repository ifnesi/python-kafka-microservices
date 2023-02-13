#!/usr/bin/env bash

config_file="config/$1"
if [ -z "$1" ]
then
    echo
    echo "Error: Missing configuration file. Usage: ./start_demo.sh {CONFIGURATION_FILE} (under the folder 'config/')"
    echo
elif test -f "$config_file"
then
    source _venv/bin/activate

    ./stop_demo.sh

    python3 msvc_status.py $1 &
    python3 msvc_assemble.py $1 &
    python3 msvc_bake.py $1 &
    python3 msvc_delivery.py $1 &
    python3 webapp.py $1 &

    sleep 3
    echo
    echo "#######################################################"
    echo "Navigate to http://127.0.0.1:8000 to order your pizza"
    echo "#######################################################"
    echo

    deactivate
else
    echo
    echo "Error: Configuration file not found: $config_file"
    echo
fi