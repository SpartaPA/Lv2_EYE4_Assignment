"""카메라 드라이버 + 인지 노드 + 깊이 컬러 도구 + RViz를 터미널 하나로 실행 (화면 확인용 — 제어·모터 없음)

실행 (ROS 환경과 이 워크스페이스 install을 source한 터미널, 어느 폴더에서든 이 파일 경로로):
  ros2 launch ~/Lv2_EYE4_Assignment/lv2_module5/tools/camera_view.launch.py
인자:
  rviz:=false             RViz 없이 (Pi에서 노드만 띄울 때)
  depth_view:=false       깊이 컬러 도구 없이
  discovery_range:=SUBNET 다른 장비(노트북 RViz 등)와 통신할 때. 기본 LOCALHOST = 이 컴퓨터 안에서만
종료: RViz 창을 닫거나 Ctrl+C → 전부 같이 종료
      (이 노트북의 RViz는 종료할 때 exit code -11로 끝나는 경우가 있어 정상 닫기와 충돌을 구분할 수 없음
       → 어느 쪽이든 전부 종료. 드물게 RViz가 실행 중 죽으면 다시 실행하면 됨)
설정: 해상도·fps = config/camera.yaml, 인지 파라미터 = tracker.yaml, 화면 배치 = rviz/tracking_view.rviz
"""
from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, SetEnvironmentVariable,
                            Shutdown)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

LV2 = Path(__file__).resolve().parents[1]                      # lv2_module5
PKG = LV2 / "ros2_ws" / "src" / "realsense_tracker"
CAMERA_YAML = LV2 / "config" / "camera.yaml"
TRACKER_YAML = PKG / "config" / "tracker.yaml"
RVIZ_CONFIG = PKG / "rviz" / "tracking_view.rviz"
DEPTH_VIEW = LV2 / "tools" / "depth_view.py"


def generate_launch_description():
    cam = yaml.safe_load(CAMERA_YAML.read_text(encoding="utf-8")) or {}
    profile = f"{cam.get('width', 640)},{cam.get('height', 480)},{cam.get('fps', 30)}"
    rs_launch = Path(get_package_share_directory("realsense2_camera")) / "launch" / "rs_launch.py"
    return LaunchDescription([
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("depth_view", default_value="true"),
        DeclareLaunchArgument("discovery_range", default_value="LOCALHOST"),
        # 같은 네트워크의 다른 팀 노드와 섞이지 않게 기본은 이 컴퓨터 안에서만 통신
        SetEnvironmentVariable("ROS_AUTOMATIC_DISCOVERY_RANGE", LaunchConfiguration("discovery_range")),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(rs_launch)),
            launch_arguments={"align_depth.enable": "true",
                              "rgb_camera.color_profile": profile,
                              "depth_module.depth_profile": profile}.items()),
        Node(package="realsense_tracker", executable="perception_node", output="screen",
             parameters=[str(TRACKER_YAML), {"camera_config": str(CAMERA_YAML), "publish_debug_image": True}]),
        ExecuteProcess(cmd=["python3", str(DEPTH_VIEW)], output="screen",
                       condition=IfCondition(LaunchConfiguration("depth_view"))),
        Node(package="rviz2", executable="rviz2", arguments=["-d", str(RVIZ_CONFIG)], output="log",
             condition=IfCondition(LaunchConfiguration("rviz")), on_exit=Shutdown(reason="RViz closed")),
    ])
