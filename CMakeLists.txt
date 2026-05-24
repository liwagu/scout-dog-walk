cmake_minimum_required(VERSION 3.8)
project(scout_dog_walk)

find_package(ament_cmake REQUIRED)

install(PROGRAMS
  scripts/dog_walk_node.py
  scripts/web_server.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY
  launch
  web
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
