#!/usr/bin/env bash
set -e

source /opt/ros/lyrical/setup.bash
source /home/pa17/git/Lv2_EYE4_Assignment/lv2_module5/ros2_ws/install/setup.bash

export ROS_DOMAIN_ID=77
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_LOCALHOST_ONLY

echo 'OpenCR services:'
ros2 service list | grep opencr || true
echo
echo '상태 확인:'
echo 'ros2 topic echo /opencr/bridge_status --field data --once'
echo
echo 'BOOT 확인 후 실행:'
echo 'ros2 service call /opencr/prepare std_srvs/srv/Trigger "{}"'
echo
echo 'READY 및 stop: false 확인 후 실행:'
echo 'ros2 service call /opencr/arm std_srvs/srv/Trigger "{}"'
