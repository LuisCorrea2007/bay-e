"""Optional ROS 2 robot bridge.

Disabled unless BAYE_ROS2_ENABLE=1. Movement is published only after a real
hardware heartbeat has been received. This file is import-safe on systems
without ROS 2.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from .robot import RobotAdapter, RobotTelemetry


class Ros2RobotAdapter(RobotAdapter):
    name = "ros2"

    def __init__(self) -> None:
        self.enabled = os.getenv("BAYE_ROS2_ENABLE", "0") == "1"
        self._last_heartbeat = 0.0
        self._battery: float | None = None
        self._charging = False
        self._room: str | None = None
        self._node = None
        self._cmd_pub = None
        self._head_pub = None
        self._spin_thread = None
        if self.enabled:
            self._boot()

    def _boot(self) -> None:
        try:
            import rclpy
            from geometry_msgs.msg import Twist, Vector3
            from sensor_msgs.msg import BatteryState
            from std_msgs.msg import Bool, String
            try:
                from rclpy.action import ActionClient
                from nav2_msgs.action import NavigateToPose
                self._NavigateToPose = NavigateToPose
                self._ActionClient = ActionClient
            except Exception:
                self._NavigateToPose = None
                self._ActionClient = None

            if not rclpy.ok():
                rclpy.init(args=None)
            self._rclpy = rclpy
            self._Twist = Twist
            self._Vector3 = Vector3
            self._node = rclpy.create_node("baye_core")
            self._cmd_pub = self._node.create_publisher(Twist, "/cmd_vel", 10)
            self._head_pub = self._node.create_publisher(Vector3, "/baye/head_target", 10)
            self._nav_client = (
                self._ActionClient(self._node, self._NavigateToPose, "navigate_to_pose")
                if self._ActionClient and self._NavigateToPose else None
            )
            self._node.create_subscription(Bool, "/baye/hardware_alive", self._alive_cb, 10)
            self._node.create_subscription(BatteryState, "/battery_state", self._battery_cb, 10)
            self._node.create_subscription(String, "/baye/current_room", self._room_cb, 10)
            self._spin_thread = threading.Thread(target=rclpy.spin, args=(self._node,), daemon=True)
            self._spin_thread.start()
        except Exception:
            self.enabled = False

    def _alive_cb(self, msg) -> None:
        if bool(msg.data):
            self._last_heartbeat = time.time()

    def _battery_cb(self, msg) -> None:
        if msg.percentage == msg.percentage:
            self._battery = max(0.0, min(100.0, float(msg.percentage) * 100.0))
        self._charging = int(getattr(msg, "power_supply_status", 0)) == 1

    def _room_cb(self, msg) -> None:
        self._room = str(msg.data)

    def telemetry(self) -> RobotTelemetry:
        connected = self.enabled and (time.time() - self._last_heartbeat) < 3.0
        return RobotTelemetry(connected=connected, battery=self._battery, charging=self._charging, room=self._room)

    def move(self, direction: str) -> dict[str, Any]:
        if not self.telemetry().connected:
            raise RuntimeError("ROS2 bridge has no live hardware heartbeat")
        msg = self._Twist()
        linear = float(os.getenv("BAYE_ROS_LINEAR", "0.18"))
        angular = float(os.getenv("BAYE_ROS_ANGULAR", "0.65"))
        if direction in ("up", "forward"): msg.linear.x = linear
        elif direction in ("down", "backward"): msg.linear.x = -linear
        elif direction == "left": msg.angular.z = angular
        elif direction == "right": msg.angular.z = -angular
        elif direction != "stop": raise ValueError(direction)
        self._cmd_pub.publish(msg)
        return {"ok": True, "direction": direction}

    def look(self, yaw: float, pitch: float) -> dict[str, Any]:
        if not self.telemetry().connected:
            raise RuntimeError("ROS2 bridge has no live hardware heartbeat")
        msg = self._Vector3()
        msg.x, msg.y = float(yaw), float(pitch)
        self._head_pub.publish(msg)
        return {"ok": True, "yaw": yaw, "pitch": pitch}

    def navigate(self, goal: dict[str, Any]) -> dict[str, Any]:
        if not self.telemetry().connected:
            raise RuntimeError("ROS2 bridge has no live hardware heartbeat")
        if self._nav_client is None or not self._nav_client.wait_for_server(timeout_sec=0.25):
            raise RuntimeError("Nav2 navigate_to_pose action is unavailable")
        import math
        msg = self._NavigateToPose.Goal()
        msg.pose.header.frame_id = str(goal.get("frame_id", "map"))
        msg.pose.header.stamp = self._node.get_clock().now().to_msg()
        msg.pose.pose.position.x = float(goal["x"])
        msg.pose.pose.position.y = float(goal["y"])
        yaw = float(goal.get("yaw", 0.0))
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        future = self._nav_client.send_goal_async(msg)
        return {"ok": True, "status": "submitted", "goal": {"x": goal["x"], "y": goal["y"], "yaw": yaw}, "future": bool(future)}