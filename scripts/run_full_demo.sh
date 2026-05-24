#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/jazzy/setup.bash
source /home/guliwa/scout_ws/install/setup.bash
source /home/guliwa/scout_dog_ws/install/setup.bash

ros2 launch scout_dog_walk dog_walk.launch.py
