cmake_minimum_required(VERSION 3.8)
project(tiny_pkg)

find_package(ament_cmake REQUIRED)

ament_index_register_resource(test_resource CONTENT "hello")

ament_package()
