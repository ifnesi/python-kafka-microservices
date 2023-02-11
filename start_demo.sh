#!/usr/bin/env bash

source _venv/bin/activate

./stop_demo.sh

python3 svc_status.py $1 &
python3 svc_assemble.py $1 &
python3 svc_bake.py $1 &
python3 svc_delivery.py $1 &
python3 app.py $1 &

deactivate