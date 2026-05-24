#!/usr/bin/env python3
"""Serves the web UI on port 8080."""
import os
import signal
from http.server import HTTPServer, SimpleHTTPRequestHandler

import rclpy
from ament_index_python.packages import get_package_share_directory


def main():
    rclpy.init()
    node = rclpy.create_node('dog_walk_web_server')
    node.declare_parameter('port', 8080)
    port = node.get_parameter('port').get_parameter_value().integer_value

    web_dir = os.path.join(get_package_share_directory('scout_dog_walk'), 'web')
    os.chdir(web_dir)
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    def stop_server(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, stop_server)
    signal.signal(signal.SIGTERM, stop_server)
    node.get_logger().info(f"Web UI running at http://0.0.0.0:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
