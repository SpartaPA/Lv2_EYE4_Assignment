import csv
import queue
import sys
import threading
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import PointStamped

CASES = {
    "center": (0.0, 0.0, 0.1),
    "right":  (0.4, 0.0, 0.1),
    "left":   (-0.4, 0.0, 0.1),
    "down":   (0.0, 0.4, 0.1),
    "up":     (0.0, -0.4, 0.1),
    "none":   (0.0, 0.0, 0.0),
}
commands = queue.Queue()

def keyboard():
    for line in sys.stdin:
        commands.put(line.strip().lower())
    commands.put("quit")

rclpy.init()
node = Node("interactive_usb_dry_target")
qos = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)
publisher = node.create_publisher(PointStamped, "/target", qos)

logfile = open(sys.argv[1], "x", newline="")
writer = csv.writer(logfile)
writer.writerow(["monotonic_sec", "case", "publishing", "x", "y", "z"])

current = "center"
publishing = True
running = True

def record():
    writer.writerow([
        time.monotonic(), current, publishing, *CASES[current]
    ])
    logfile.flush()

def tick():
    global current, publishing, running
    while not commands.empty():
        command = commands.get_nowait()
        if command == "quit":
            running = False
            return
        if command == "silence":
            publishing = False
        elif command in CASES:
            current = command
            publishing = True
        else:
            print("Use: center right left down up none silence quit",
                  flush=True)
            continue
        record()
        print(f"Selected {command}; publishing={publishing}", flush=True)

    if publishing:
        msg = PointStamped()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.point.x, msg.point.y, msg.point.z = CASES[current]
        publisher.publish(msg)

record()
threading.Thread(target=keyboard, daemon=True).start()
timer = node.create_timer(0.05, tick)

print("Publishing CENTER at 20 Hz.", flush=True)
print("Type: center right left down up none silence quit", flush=True)

try:
    while running and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.1)
except KeyboardInterrupt:
    pass
finally:
    logfile.close()
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
