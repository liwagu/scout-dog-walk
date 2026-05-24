import os

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import AnyLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def launch_setup(context, *args, **kwargs):
    headless = LaunchConfiguration("headless").perform(context).lower() == "true"
    gz_flags = "-s -v 4 -r " if headless else "-v 4 -r "
    world = PathJoinSubstitution([
        FindPackageShare("scout_gazebo_sim"),
        "worlds",
        LaunchConfiguration("world_name"),
    ])

    install_dir = get_package_prefix("scout_description")
    if "GZ_SIM_RESOURCE_PATH" in os.environ:
        os.environ["GZ_SIM_RESOURCE_PATH"] = (
            os.environ["GZ_SIM_RESOURCE_PATH"] + ":" + install_dir + "/share/"
        )
    else:
        os.environ["GZ_SIM_RESOURCE_PATH"] = install_dir + "/share/"

    os.environ["GZ_SIM_SYSTEM_PLUGIN_PATH"] = ":".join([
        os.environ.get("GZ_SIM_SYSTEM_PLUGIN_PATH", default=""),
        os.environ.get("LD_LIBRARY_PATH", default=""),
    ])

    gz_sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("ros_gz_sim"),
                "launch",
                "gz_sim.launch.py",
            ])
        ),
        launch_arguments={
            "gz_args": [gz_flags, world],
            "on_exit_shutdown": "true",
        }.items(),
    )

    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("scout_gazebo_sim"),
                "launch",
                "scout_mini_robot_state_publisher.launch.py",
            ])
        ),
        launch_arguments={
            "use_sim_time": "true",
            "namespace": "scout_mini",
        }.items(),
    )

    robot_spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("scout_gazebo_sim"),
                "launch",
                "spawn_scout_mini.launch.py",
            ])
        ),
        launch_arguments={
            "namespace": "scout_mini",
            "x_pose": LaunchConfiguration("x_pose"),
            "y_pose": LaunchConfiguration("y_pose"),
            "yaw_pose": LaunchConfiguration("yaw_pose"),
        }.items(),
    )

    ros_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "--ros-args",
            "-p",
            "config_file:=" + os.path.join(
                get_package_share_directory("scout_gazebo_sim"),
                "config",
                "scout_mini_bridge_ros_gz.yaml",
            ),
        ],
    )

    ros_gz_image = Node(
        package="ros_gz_image",
        executable="image_bridge",
        arguments=["/scout_mini/rgb_cam/image_raw"],
    )

    return [gz_sim_launch, robot_state_publisher, robot_spawn, ros_gz_bridge, ros_gz_image]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            "web_port",
            default_value="8080",
            description="HTTP port for the local web control console",
        ),
        DeclareLaunchArgument(
            "rosbridge_port",
            default_value="9090",
            description="WebSocket port for rosbridge. Change this when a real robot stack already uses 9090.",
        ),
        DeclareLaunchArgument(
            "headless",
            default_value="false",
            description="Run Gazebo server-only. Use true for SSH/CI, false for Ubuntu desktop GUI.",
        ),
        DeclareLaunchArgument(
            "use_rviz",
            default_value="false",
            description="Reserved for compatibility; Gazebo GUI is the primary simulator view.",
        ),
        DeclareLaunchArgument("world_name", default_value="empty.world"),
        DeclareLaunchArgument("x_pose", default_value="0.0"),
        DeclareLaunchArgument("y_pose", default_value="0.0"),
        DeclareLaunchArgument("yaw_pose", default_value="3.14"),
        OpaqueFunction(function=launch_setup),
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(
                PathJoinSubstitution([
                    FindPackageShare("rosbridge_server"),
                    "launch",
                    "rosbridge_websocket_launch.xml",
                ])
            ),
            launch_arguments={
                "port": LaunchConfiguration("rosbridge_port"),
            }.items(),
        ),
        Node(
            package="scout_dog_walk",
            executable="dog_walk_node.py",
            name="dog_walk_node",
            output="screen",
            respawn=True,
            parameters=[
                {"use_sim_time": True},
                {"cmd_vel_topic": "/scout_mini/cmd_vel"},
                {"max_speed_scale": 3.0},
            ],
        ),
        Node(
            package="scout_dog_walk",
            executable="web_server.py",
            name="dog_walk_web_server",
            output="screen",
            parameters=[{"port": LaunchConfiguration("web_port")}],
        ),
    ])
