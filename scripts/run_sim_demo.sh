#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/jazzy/setup.bash
source /home/guliwa/scout_sim_ws/install/setup.bash

ros2 launch scout_dog_walk dog_walk_sim.launch.py web_port:=19181 rosbridge_port:=19090 "$@"
