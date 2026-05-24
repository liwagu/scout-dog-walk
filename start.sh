#!/usr/bin/env bash
set -eo pipefail

source /opt/ros/jazzy/setup.bash
source "$HOME/scout_ws/install/setup.bash"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOG_NODE="$APP_DIR/scripts/dog_walk_node.py"
WEB_DIR="$APP_DIR/web"
WEB_PORT="${SCOUT_DOG_WEB_PORT:-8080}"
ROSBRIDGE_PORT="${SCOUT_DOG_ROSBRIDGE_PORT:-9090}"
TAILSCALE_IP="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
ROSBRIDGE_ADDRESS="${SCOUT_DOG_ROSBRIDGE_ADDRESS:-0.0.0.0}"
LOG_DIR="${SCOUT_DOG_LOG_DIR:-/tmp/scout_dog}"

if [ -z "$ROSBRIDGE_ADDRESS" ]; then
    ROSBRIDGE_ADDRESS="0.0.0.0"
fi

mkdir -p "$LOG_DIR"

if [ ! -f "$DOG_NODE" ]; then
    echo "dog node not found: $DOG_NODE" >&2
    exit 1
fi

publish_stop() {
    timeout 2 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
        "{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}" \
        >/dev/null 2>&1 || true
}

stop_pid_file() {
    pid_file="$1"
    [ -f "$pid_file" ] || return 0
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    [ -n "$pid" ] || return 0
    kill "$pid" >/dev/null 2>&1 || true
}

stop_started_processes() {
    echo ""
    echo "-> 停止本次 start.sh 启动的进程..."
    publish_stop
    for pid_file in "$LOG_DIR"/*.pid; do
        stop_pid_file "$pid_file"
    done
}

stop_old_processes() {
    echo "-> 发送零速并清理旧的实机控制进程..."
    publish_stop
    pkill -f "$APP_DIR/scripts/dog_walk_node.py" || true
    pkill -f "rosbridge_websocket" || true
    pkill -f "http.server $WEB_PORT" || true
    pkill -f "run_scout_mini.sh|scout_base_node" || true
    fuser -k "${ROSBRIDGE_PORT}/tcp" >/dev/null 2>&1 || true
    fuser -k "${WEB_PORT}/tcp" >/dev/null 2>&1 || true
    sleep 1
}

trap stop_started_processes INT TERM
stop_old_processes

if bash "$HOME/scout_ws/scripts/setup_can0_500k.sh"; then
    bash "$HOME/scout_ws/scripts/run_scout_mini.sh" >"$LOG_DIR/scout_base.log" 2>&1 &
    echo $! > "$LOG_DIR/scout_base.pid"
else
    echo ""
    echo "CAN 总线未就绪，底盘驱动未启动。"
    echo "请拔插 USB-CAN 适配器后重新运行 bash /home/guliwa/scout_dog/start.sh"
    echo ""
fi

ros2 launch rosbridge_server rosbridge_websocket_launch.xml \
    port:="$ROSBRIDGE_PORT" \
    address:="$ROSBRIDGE_ADDRESS" \
    >"$LOG_DIR/rosbridge.log" 2>&1 &
echo $! > "$LOG_DIR/rosbridge.pid"

python3 "$DOG_NODE" >"$LOG_DIR/dog_walk_node.log" 2>&1 &
echo $! > "$LOG_DIR/dog_walk_node.pid"

cd "$WEB_DIR"
python3 -m http.server "$WEB_PORT" >"$LOG_DIR/web.log" 2>&1 &
echo $! > "$LOG_DIR/web.pid"

sleep 2

echo ""
echo "控制台进程已启动"
if [ "$ROSBRIDGE_ADDRESS" = "0.0.0.0" ]; then
    echo "  Ubuntu 本机: http://localhost:$WEB_PORT  -> ws://localhost:$ROSBRIDGE_PORT"
    if [ -n "$TAILSCALE_IP" ]; then
        echo "  Tailscale:  http://$TAILSCALE_IP:$WEB_PORT -> ws://$TAILSCALE_IP:$ROSBRIDGE_PORT"
    fi
else
    echo "  Web UI:     http://$ROSBRIDGE_ADDRESS:$WEB_PORT"
    echo "  rosbridge:  ws://$ROSBRIDGE_ADDRESS:$ROSBRIDGE_PORT"
    if [ "$ROSBRIDGE_ADDRESS" = "$TAILSCALE_IP" ]; then
        echo "  安全模式:   rosbridge 只监听 Tailscale，同局域网不能直接连接 9090"
    fi
fi
echo "  logs:       $LOG_DIR"

if grep -Eq "Robot initialized|Using CAN bus to talk with the robot" "$LOG_DIR/scout_base.log" 2>/dev/null; then
    echo "底盘驱动日志显示已初始化。"
else
    echo "警告：尚未从日志确认底盘已初始化；如果底盘没开机，网页可能能连上但车不会动。"
    echo "      查看：tail -f $LOG_DIR/scout_base.log"
fi
wait
