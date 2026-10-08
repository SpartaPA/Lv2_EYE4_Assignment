"""Raspberry Pi 단일 runtime 실행 구성 (담당: 통합)

모든 ROS 2 노드는 Raspberry Pi 한 대에서 실행한다. 사용자 PC는 SSH 터미널로 명령만 입력한다.
  D435 (Pi USB 3) → realsense2_camera → perception_node → /target → control_node → /control/pan_tilt_cmd
  → opencr_node → USB Serial → OpenCR → Pan/Tilt DYNAMIXEL

  - realsense2_camera (공식 wrapper): Color / 정렬 Depth / CameraInfo. 해상도·FPS는 config/camera.yaml
  - perception_node: config/tracker.yaml + camera.yaml → /target
  - control_node: start_control:=true 일 때만 (기본 false — 안전 기본값). config/control.yaml
  - opencr_node: start_opencr:=true 일 때만 (기본 false). config/opencr_live.yaml
      opencr_node가 실행돼도 모터는 움직이지 않는다: /opencr/prepare, /opencr/arm 을 운영자가 직접 호출해야 함.
      시리얼 로그와 서비스 응답을 따로 보려면 opencr_node는 별도 SSH 터미널에서 ros2 run으로 실행해도 된다 (README).

인자
  start_realsense:=false   bag 재생 등 카메라 없이 실행할 때
  start_control:=true      실제 추적 시연
  start_opencr:=true       같은 launch에서 OpenCR bridge까지 실행
  control_params / opencr_params / tracker_params / camera_config 로 설정 파일 교체
"""
import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def realsense(context):
    """camera.yaml의 width/height/fps로 wrapper 프로파일을 만든다 (해상도 값의 Source of Truth는 camera.yaml 하나)."""
    path = LaunchConfiguration("camera_config").perform(context)
    with open(path, "r", encoding="utf-8") as f:
        cam = yaml.safe_load(f) or {}
    profile = f"{int(cam['width'])},{int(cam['height'])},{int(cam['fps'])}"
    # forwarding=False: rs_launch.py는 보이는 launch 인자를 전부 노드 파라미터로 넘기므로
    # 이 파일의 인자(start_control 등)가 "not supported" 경고로 섞이지 않게 아래 3개만 전달
    return [GroupAction([IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare("realsense2_camera"), "launch", "rs_launch.py"])),
        launch_arguments={
            "align_depth.enable": "true",
            "rgb_camera.color_profile": profile,
            "depth_module.depth_profile": profile,
        }.items(),
    )], forwarding=False, condition=IfCondition(LaunchConfiguration("start_realsense")))]


def generate_launch_description():
    config_dir = PathJoinSubstitution([FindPackageShare("realsense_tracker"), "config"])

    perception = Node(
        package="realsense_tracker",
        executable="perception_node",
        name="perception_node",
        output="screen",
        parameters=[LaunchConfiguration("tracker_params"),
                    {"camera_config": LaunchConfiguration("camera_config")}],
    )
    opencr = Node(
        package="realsense_tracker",
        executable="opencr_node",
        name="opencr_node",
        output="screen",
        parameters=[LaunchConfiguration("opencr_params")],
        condition=IfCondition(LaunchConfiguration("start_opencr")),
    )
    control = Node(
        package="realsense_tracker",
        executable="control_node",
        name="control_node",
        output="screen",
        parameters=[LaunchConfiguration("control_params")],
        condition=IfCondition(LaunchConfiguration("start_control")),
    )

    return LaunchDescription([
        DeclareLaunchArgument("camera_config",
                              default_value=PathJoinSubstitution([config_dir, "camera.yaml"]),
                              description="Camera profile and wrapper topic names (plain YAML)."),
        DeclareLaunchArgument("tracker_params",
                              default_value=PathJoinSubstitution([config_dir, "tracker.yaml"]),
                              description="perception_node parameter file."),
        DeclareLaunchArgument("control_params",
                              default_value=PathJoinSubstitution([config_dir, "control.yaml"]),
                              description="control_node parameter file (production)."),
        DeclareLaunchArgument("opencr_params",
                              default_value=PathJoinSubstitution([config_dir, "opencr_live.yaml"]),
                              description="opencr_node parameter file (used only when start_opencr:=true)."),
        DeclareLaunchArgument("start_opencr", default_value="false",
                              description="Start opencr_node (OpenCR serial bridge). Motors still need prepare/arm."),
        DeclareLaunchArgument("start_realsense", default_value="true",
                              description="Start the official realsense2_camera wrapper."),
        DeclareLaunchArgument("start_control", default_value="false",
                              description="Start control_node. Default false for safety; true for tracking."),
        OpaqueFunction(function=realsense),
        perception,
        control,
        opencr,
    ])
