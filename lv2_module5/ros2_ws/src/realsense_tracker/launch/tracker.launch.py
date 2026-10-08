"""Pi의 전체 runtime: D435 → 인지 → 2축 제어 → USB Serial → OpenCR.
설정은 설치된 패키지의 기존 YAML에서 자동으로 읽는다. PC는 SSH 접속용이다.
"""
from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent
from launch.events import Shutdown
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory('realsense_tracker')) / 'config'
    with (config / 'camera.yaml').open(encoding='utf-8') as stream:
        camera = yaml.safe_load(stream)
    profile = f"{int(camera['width'])},{int(camera['height'])},{int(camera['fps'])}"
    wrapper = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(Path(get_package_share_directory('realsense2_camera'))
                                          / 'launch' / 'rs_launch.py')),
        launch_arguments={'enable_color': 'true', 'enable_depth': 'true',
                          'align_depth.enable': 'true', 'rgb_camera.color_profile': profile,
                          'depth_module.depth_profile': profile}.items())
    perception = Node(package='realsense_tracker', executable='perception_node',
                      name='perception_node', output='screen',
                      parameters=[str(config / 'tracker.yaml'),
                                  {'camera_config': str(config / 'camera.yaml')}])
    control = Node(package='realsense_tracker', executable='control_node',
                   name='control_node', output='screen', parameters=[str(config / 'control.yaml')])
    opencr = Node(package='realsense_tracker', executable='opencr_node',
                  name='opencr_node', output='screen', parameters=[str(config / 'opencr_live.yaml')])
    # bridge 종료(Serial 오류 포함) 시 전체 실행도 종료한다. 재연결·자동 재시작은 없다.
    shutdown = RegisterEventHandler(OnProcessExit(
        target_action=opencr, on_exit=[EmitEvent(event=Shutdown(reason='OpenCR bridge exited'))]))
    return LaunchDescription([shutdown, wrapper, perception, control, opencr])
