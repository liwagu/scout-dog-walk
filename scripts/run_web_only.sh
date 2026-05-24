#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/jazzy/setup.bash
source /home/guliwa/scout_dog_ws/install/setup.bash

ros2 run scout_dog_walk web_server.py --ros-args -p port:=8080
