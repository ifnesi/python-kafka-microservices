#!/usr/bin/env bash

for i in pid/*.pid; do
    echo
    echo "Stopping process $i..."
    kill -15 `cat $i` || true
done
