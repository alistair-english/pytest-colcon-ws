cmake_minimum_required(VERSION 3.8)
project(tiny_pkg_b NONE)

find_package(ament_cmake REQUIRED)
find_package(tiny_pkg REQUIRED)

ament_index_register_resource(test_resource CONTENT "world")

ament_package()
