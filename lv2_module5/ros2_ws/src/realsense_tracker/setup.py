from setuptools import find_packages, setup
from glob import glob
setup(name='realsense_tracker', version='0.1.0', packages=find_packages(exclude=['test']),
 data_files=[('share/ament_index/resource_index/packages',['resource/realsense_tracker']),
 ('share/realsense_tracker',['package.xml']),
 ('share/realsense_tracker/launch',glob('launch/*.launch.py')),
 ('share/realsense_tracker/config',glob('config/*.yaml'))],
 install_requires=['setuptools'], zip_safe=True,
 maintainer='MinHyeok Cho', maintainer_email='maze00runner@gmail.com',
 description='Pan Tilt control and dry OpenCR bridge', license='Apache-2.0',
 entry_points={'console_scripts':[
 'control_node = realsense_tracker.control_node:main',
 'opencr_node = realsense_tracker.opencr_node:main',
 'test_control_dry = realsense_tracker.test_control_dry:main']})
