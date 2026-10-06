# 초안: 인지 담당(김상화)이 perception_node 빌드·실행에 필요한 최소 내용만 작성 — 통합 담당 검토 필요
# 다른 노드(camera/control/opencr)는 구현되면 entry_points에 추가
from glob import glob

from setuptools import find_packages, setup

package_name = "realsense_tracker"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="EYE4",
    maintainer_email="hwa04866@gmail.com",
    description="EYE4 RealSense 기반 파란색 퍽 추적 패키지",
    license="TODO",
    entry_points={
        "console_scripts": [
            "perception_node = realsense_tracker.perception_node:main",
        ],
    },
)
