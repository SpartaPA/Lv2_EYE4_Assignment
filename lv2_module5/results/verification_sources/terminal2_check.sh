#!/usr/bin/env bash
set -e

source /opt/ros/lyrical/setup.bash
source /home/pa17/git/Lv2_EYE4_Assignment/lv2_module5/ros2_ws/install/setup.bash

export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_LOCALHOST_ONLY

echo '--- nodes ---'
ros2 node list
echo '--- camera: Ctrl+C to stop ---'
ros2 topic hz /camera/camera/color/image_raw
