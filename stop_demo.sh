#!/usr/bin/env bash

for i in pid/*.pid; do
    [ -f "$i" ] || break
    echo
    echo "Stopping process $i..."
    kill -15 `cat $i` || true
    rm $i
done

sleep 2
echo
echo "Demo stopped"
echo
