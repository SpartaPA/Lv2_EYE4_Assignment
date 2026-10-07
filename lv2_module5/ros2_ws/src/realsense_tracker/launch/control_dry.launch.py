"""모의(DRY) 제어 실행 (담당: 제어 + 통합) — control_node + opencr_node DRY sink

카메라·시리얼·모터 없이 /target을 직접 발행해 명령·상태를 확인할 때 사용한다 (문제 2 수동 확인).
설정: config/control_dry.yaml (고정 모의값). opencr_node는 포트를 열지 않는다.
자동 판정 시험은 `ros2 run realsense_tracker test_control_dry --output-dir <dir>` 을 사용한다.
"""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = str(Path(get_package_share_directory('realsense_tracker')) / 'config' / 'control_dry.yaml')
    return LaunchDescription([
        Node(package='realsense_tracker', executable='control_node', parameters=[config], output='screen'),
        Node(package='realsense_tracker', executable='opencr_node', parameters=[config], output='screen'),
    ])
