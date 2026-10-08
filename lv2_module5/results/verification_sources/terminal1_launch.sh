#!/usr/bin/env bash
set -e

cd /home/pa17/git/Lv2_EYE4_Assignment/lv2_module5/ros2_ws
source /opt/ros/lyrical/setup.bash
source install/setup.bash

export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_LOCALHOST_ONLY

ros2 launch realsense_tracker tracker.launch.py \
  start_realsense:=true \
  start_control:=true \
  start_opencr:=true
