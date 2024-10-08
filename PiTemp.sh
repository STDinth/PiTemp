#!/bin/bash
while true; do
    temp=$(echo "$(cat /sys/class/thermal/thermal_zone0/temp) / 1000" | bc -l)
    echo "$temp" > /home/Pi4/PYTHON/temp_file.txt
    sleep 1
done
