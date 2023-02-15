#!/usr/bin/env bash

kafka_config_file="config_kafka/$1"
sys_config_file="config_sys/${2:-default.ini}"

if [ -z "$1" ]
then
    echo
    echo "Error: Missing configuration file. Usage: ./start_demo.sh {KAFKA_CONFIG_FILE} (under the folder 'config_kafka/')"
    echo
    exit 1
fi

if ! test -f "$kafka_config_file"
then
    echo
    echo "Error: Kafka configuration file not found: $kafka_config_file"
    echo
    exit 1
fi

if ! test -f "$sys_config_file"
then
    echo
    echo "Error: System configuration file not found: $sys_config_file"
    echo
    exit 1
else
    source _venv/bin/activate

    ./stop_demo.sh

    python3 msvc_status.py $1 $2 &
    python3 msvc_assemble.py $1 $2 &
    python3 msvc_bake.py $1 $2 &
    python3 msvc_delivery.py $1 $2 &
    python3 webapp.py $1 $2 &

    sleep 3

    echo
    echo "#######################################################"
    echo "Navigate to http://127.0.0.1:8000 to order your pizza"
    echo "#######################################################"
    echo

    deactivate
fi
