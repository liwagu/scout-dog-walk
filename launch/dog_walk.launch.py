from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import AnyLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    port_name_arg = DeclareLaunchArgument(
        "port_name",
        default_value="can0",
        description="SocketCAN interface connected to Scout Mini",
    )
    web_port_arg = DeclareLaunchArgument(
        "web_port",
        default_value="8080",
        description="HTTP port for the local web control console",
    )
    rosbridge_port_arg = DeclareLaunchArgument(
        "rosbridge_port",
        default_value="9090",
        description="WebSocket port for rosbridge",
    )
    rosbridge_address_arg = DeclareLaunchArgument(
        "rosbridge_address",
        default_value="",
        description="Bind address for rosbridge. Empty means all interfaces.",
    )
    cmd_vel_topic_arg = DeclareLaunchArgument(
        "cmd_vel_topic",
        default_value="/cmd_vel",
        description="Twist command topic for the real Scout Mini driver",
    )

    scout_base_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("scout_base"),
                "launch",
                "scout_mini_base.launch.py",
            ])
        ),
        launch_arguments={"port_name": LaunchConfiguration("port_name")}.items(),
    )

    rosbridge_launch = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("rosbridge_server"),
                "launch",
                "rosbridge_websocket_launch.xml",
            ])
        ),
        launch_arguments={
            "port": LaunchConfiguration("rosbridge_port"),
            "address": LaunchConfiguration("rosbridge_address"),
        }.items(),
    )

    dog_walk_node = Node(
        package="scout_dog_walk",
        executable="dog_walk_node.py",
        name="dog_walk_node",
        output="screen",
        respawn=True,
        parameters=[{"cmd_vel_topic": LaunchConfiguration("cmd_vel_topic")}],
    )

    web_server = Node(
        package="scout_dog_walk",
        executable="web_server.py",
        name="dog_walk_web_server",
        output="screen",
        parameters=[{"port": LaunchConfiguration("web_port")}],
    )

    return LaunchDescription([
        port_name_arg,
        web_port_arg,
        rosbridge_port_arg,
        rosbridge_address_arg,
        cmd_vel_topic_arg,
        scout_base_launch,
        rosbridge_launch,
        dog_walk_node,
        web_server,
    ])
