#!/usr/bin/env python3
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Float32
import threading
import json
import time

ROUTES = {
    # 场地 5m x 2.5m，沿用 GitHub master 里的队友路线逻辑。
    # 步骤格式: (linear_x m/s, angular_z rad/s, 持续秒数[, pause_after=True])
    # speed_scale 只缩放线速度；角速度和持续时间保持不变。
    "home": [
        # 短途如厕: 直线 3m 往返，含 2 次停留
        # 0.15 m/s x 10s = 1.5m，两段共 3m
        (0.15, 0.0, 10.0),  # 前进 1.5m
        (0.0,  0.0,  4.0),  # 停留：闻一闻
        (0.15, 0.0, 10.0),  # 前进 1.5m（累计 3.0m）
        (0.0,  0.0,  5.0),  # 停留：休息
        (0.0,  0.5,  5.55), # 掉头 180°实机校准：理论 6.28s 会过转
        (0.15, 0.0, 20.0),  # 返回 3.0m
        (0.0,  0.0,  2.0),  # 停车结束
    ],

    "neighborhood": [
        # 小区散步: 自定义折线，共 7m，只有转弯停顿无狗狗停留
        # 0.15 m/s x 6.67s = 1m；x 13.33s = 2m；0.5 rad/s x 3.14s = 90°
        # 右转 az=-0.5，左转 az=+0.5
        (0.15,  0.0,  6.67),  # 前进 1m
        (0.0,  -0.5,  3.14),  # 右转 90°
        (0.15,  0.0,  6.67),  # 前进 1m
        (0.0,   0.5,  3.14),  # 左转 90°
        (0.15,  0.0,  6.67),  # 前进 1m
        (0.0,   0.5,  3.14),  # 左转 90°
        (0.15,  0.0, 13.33),  # 前进 2m
        (0.0,  -0.5,  3.14),  # 右转 90°
        (0.15,  0.0,  6.67),  # 前进 1m
        (0.0,  -0.5,  3.14),  # 右转 90°
        (0.15,  0.0,  6.67),  # 前进 1m
    ],

    "park": [
        # 公园放松: 椭圆S型单程约4.2m，连续无停顿
        # 正弦角速度: w(t)=0.110*cos(2*pi*t/30)，8段 x 3.75s，总行程30s
        # 数值积分轨迹: 左峰(2.1m, +0.71m) -> 回中心(4.2m, 0)，起止朝正前方
        # pause_after=False：段间不刹停，保持平滑弧线。
        (0.15,  0.101, 3.75, False),  # 左弧渐强（θ: 0→22°）
        (0.15,  0.042, 3.75, False),  # 左弧渐弱（θ: 22°→31°峰值）
        (0.15, -0.042, 3.75, False),  # 开始回正（θ: 31°→22°）
        (0.15, -0.101, 3.75, False),  # 回正渐强（θ: 22°→0° 左峰位置）
        (0.15, -0.101, 3.75, False),  # 右弧渐强（θ: 0°→-22°）
        (0.15, -0.042, 3.75, False),  # 右弧渐弱（θ: -22°→-31°峰值）
        (0.15,  0.042, 3.75, False),  # 开始回正（θ: -31°→-22°）
        (0.15,  0.101, 3.75, False),  # 回正收尾（θ: -22°→0° 终点）
    ],
}


class DogWalkNode(Node):
    def __init__(self):
        super().__init__("dog_walk_node")

        self.declare_parameter("cmd_vel_topic", "/cmd_vel")
        self.declare_parameter("min_speed_scale", 0.2)
        self.declare_parameter("max_speed_scale", 1.0)
        cmd_vel_topic = self.get_parameter("cmd_vel_topic").value
        self.min_speed_scale = self.get_parameter("min_speed_scale").value
        self.max_speed_scale = self.get_parameter("max_speed_scale").value

        self.cmd_pub    = self.create_publisher(Twist,  cmd_vel_topic,       10)
        self.status_pub = self.create_publisher(String, "/dog_walk/status",  10)

        self.create_subscription(String, "/dog_walk/command",     self.on_command, 10)
        self.create_subscription(String, "/dog_walk/route",       self.on_route,   10)
        self.create_subscription(Float32, "/dog_walk/speed_scale", self.on_speed,  10)

        self.current_route = "neighborhood"
        self.speed_scale   = 1.0
        self.state         = "idle"
        self.stop_event    = threading.Event()
        self.pause_event   = threading.Event()
        self.pause_event.set()
        self.walk_thread   = None
        self.step_index    = 0
        self.step_total    = 0
        self.step_action   = "待机"
        self.route_run_id  = 0
        self.state_lock    = threading.Lock()

        self.create_timer(0.5, self.publish_status)
        self.get_logger().info(f"Dog Walk Node ready, publishing Twist to {cmd_vel_topic}")

    def on_command(self, msg):
        cmd = msg.data.strip()
        self.get_logger().info(f"Command: {cmd}")

        if cmd == "start" and self.state in ("idle", "stopped", "done"):
            self.start_walk()
        elif cmd == "stop":
            self.stop_walk()
        elif cmd == "pause" and self.state == "running":
            self.state = "paused"
            self.pause_event.clear()
        elif cmd == "resume" and self.state == "paused":
            self.state = "running"
            self.pause_event.set()

    def on_route(self, msg):
        if self.state in ("idle", "stopped", "done"):
            route = msg.data.strip()
            if route not in ROUTES:
                self.get_logger().warn(f"Unknown route ignored: {route}")
                return
            self.current_route = route
            self.step_index = 0
            self.step_total = len(ROUTES[route])
            self.step_action = "待机"

    def on_speed(self, msg):
        try:
            value = float(msg.data)
        except (TypeError, ValueError):
            self.get_logger().warn(f"Invalid speed scale ignored: {msg.data}")
            return
        self.speed_scale = max(self.min_speed_scale, min(self.max_speed_scale, value))

    def start_walk(self):
        old_thread = None
        with self.state_lock:
            old_thread = self.walk_thread if self.walk_thread and self.walk_thread.is_alive() else None
            if old_thread:
                self.stop_event.set()
                self.pause_event.set()

        if old_thread:
            old_thread.join(timeout=1.0)

        with self.state_lock:
            self.route_run_id += 1
            run_id = self.route_run_id
            self.stop_event = threading.Event()
            self.pause_event.set()
            self.state = "running"
            self.step_index = 0
            self.step_total = len(ROUTES.get(self.current_route, ROUTES["neighborhood"]))
            self.step_action = "启动"
            self.walk_thread = threading.Thread(
                target=self.execute_route,
                args=(run_id, self.stop_event),
                daemon=True,
            )
            self.walk_thread.start()

    def stop_walk(self):
        thread = None
        with self.state_lock:
            self.stop_event.set()
            self.pause_event.set()
            self.state = "stopped"
            self.step_action = "已停止"
            thread = self.walk_thread if self.walk_thread and self.walk_thread.is_alive() else None
        self.send_stop(repeats=5)
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def execute_route(self, run_id, stop_event):
        route = ROUTES.get(self.current_route, ROUTES["neighborhood"])
        self.step_total = len(route)
        for index, step in enumerate(route, start=1):
            if stop_event.is_set() or run_id != self.route_run_id:
                break
            lx, az, dur, *rest = step
            pause_after = rest[0] if rest else True
            scale = self.speed_scale
            scaled_duration = self.scaled_duration(lx, az, dur, scale)
            self.step_index = index
            self.step_action = self.describe_step(lx, az, dur, scaled_duration)
            self.get_logger().info(
                f"Route {self.current_route} step {index}/{self.step_total}: "
                f"{self.step_action}, speed_scale={scale:.2f}"
            )
            self.run_step(lx * scale, az, scaled_duration, stop_event, run_id)
            if not stop_event.is_set() and pause_after and (lx != 0.0 or az != 0.0):
                self.send_stop()
                time.sleep(0.3)
        if not stop_event.is_set() and run_id == self.route_run_id:
            self.send_stop(repeats=3)
            with self.state_lock:
                self.state = "done"
                self.step_action = "完成"

    def scaled_duration(self, lx, az, duration, scale):
        return duration

    def describe_step(self, lx, az, duration, scaled_duration):
        if lx == 0.0 and az == 0.0:
            return f"停留 {duration:.0f}s"
        if lx == 0.0:
            direction = "左转" if az > 0 else "右转"
            return f"原地{direction} {scaled_duration:.1f}s"
        if az == 0.0:
            return f"直行 {scaled_duration:.1f}s"
        direction = "左弯" if az > 0 else "右弯"
        return f"{direction} {scaled_duration:.1f}s"

    def run_step(self, lx, az, duration, stop_event, run_id):
        twist = Twist()
        twist.linear.x  = lx
        twist.angular.z = az
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if stop_event.is_set() or run_id != self.route_run_id:
                return
            if not self.pause_event.is_set():
                self.send_stop()
                paused_at = time.monotonic()
                self.pause_event.wait()
                if stop_event.is_set() or run_id != self.route_run_id:
                    return
                deadline += time.monotonic() - paused_at
            self.cmd_pub.publish(twist)
            time.sleep(0.1)

    def send_stop(self, repeats=1):
        stop = Twist()
        for _ in range(repeats):
            self.cmd_pub.publish(stop)
            time.sleep(0.03)

    def publish_status(self):
        status = {
            "state":            self.state,
            "route":            self.current_route,
            "speed_scale":      round(self.speed_scale, 2),
            "available_routes": list(ROUTES.keys()),
            "step_index":       self.step_index,
            "step_total":       self.step_total,
            "step_action":      self.step_action,
        }
        msg = String()
        msg.data = json.dumps(status, ensure_ascii=False)
        self.status_pub.publish(msg)


def main():
    rclpy.init()
    node = DogWalkNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.stop_walk()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
