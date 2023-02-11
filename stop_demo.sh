#!/usr/bin/env bash

for i in pid/*.pid; do
    echo
    echo "Stopping process $i..."
    kill -9 `cat $i` || true
done
