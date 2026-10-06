from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    config=str(Path(get_package_share_directory('realsense_tracker'))/'config'/'control_dry.yaml')
    return LaunchDescription([
        Node(package='realsense_tracker',executable='control_node',parameters=[config],output='screen'),
        Node(package='realsense_tracker',executable='opencr_node',parameters=[config],output='screen')])
