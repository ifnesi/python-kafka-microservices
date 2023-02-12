#!/usr/bin/env bash

source _venv/bin/activate

./stop_demo.sh

python3 msvc_status.py $1 &
python3 msvc_assemble.py $1 &
python3 msvc_bake.py $1 &
python3 msvc_delivery.py $1 &
python3 webapp.py $1 &

deactivate