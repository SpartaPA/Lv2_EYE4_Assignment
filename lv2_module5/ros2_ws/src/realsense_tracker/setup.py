from glob import glob

from setuptools import find_packages, setup

package_name = "realsense_tracker"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", [path for path in glob("config/*.yaml") if not path.endswith("serial_dry.yaml")]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="EYE4",
    maintainer_email="hwa04866@gmail.com",
    description="EYE4 RealSense Pan/Tilt target tracking package",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "perception_node = realsense_tracker.perception_node:main",
            "control_node = realsense_tracker.control_node:main",
            "opencr_node = realsense_tracker.opencr_node:main",
            "dry_bridge = realsense_tracker.dry_bridge:main",
            "test_control_dry = realsense_tracker.test_control_dry:main",
            "test_serial_pty = realsense_tracker.test_serial_pty:main",
            "test_serial_ros = realsense_tracker.test_serial_ros:main",
        ],
    },
)
