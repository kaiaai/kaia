#!/usr/bin/env python3
#
# Copyright 2023 REMAKE.AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription, LaunchContext
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def make_nodes(context: LaunchContext, robot_model, lds_model, use_sim_time):
    robot_model_str = context.perform_substitution(robot_model)
    lds_model_str = context.perform_substitution(lds_model)
    use_sim_time_str = context.perform_substitution(use_sim_time)
    description_package_path = get_package_share_path(robot_model_str)

    urdf_path_name = os.path.join(
      description_package_path,
      'urdf',
      'robot.urdf.xacro')

    robot_description = ParameterValue(Command(['xacro ', urdf_path_name]), value_type=str)

    param_path_name = os.path.join(
        description_package_path,
        'config',
        'telem.yaml'
        )
    print('URDF file   : {}'.format(urdf_path_name))
    print('Telem params: {}'.format(param_path_name))
    print('LDS model   : {}'.format(lds_model_str))

    return [
        Node(
            package="kaiaai_telemetry",
            executable="telem",
            output="screen",
#            parameters = [param_path_name]
            parameters = [param_path_name, {'laser_scan.lds_model': lds_model_str}]
        ),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time_str.lower() == 'true',
                'robot_description': robot_description
            }]
        )
    ]


def generate_launch_description():

    return LaunchDescription([
        DeclareLaunchArgument(
            name='robot_model',
            default_value='makerspet_snoopy',
            description='Robot description package name'
        ),
        DeclareLaunchArgument(
            name='lds_model',
            default_value='YDLIDAR-X4',
            choices=['YDLIDAR-X4', 'LDS02RR', 'YDLIDAR-X2', 'YDLIDAR-X3-PRO'],
            description='Laser distance scan sensor model'
        ),
        DeclareLaunchArgument(
            name='use_sim_time',
            default_value='false',
            choices=['true', 'false'],
            description='Use simulation (Gazebo) clock if true'
        ),
        Node(
            package='micro_ros_agent',
            executable='micro_ros_agent',
            name='micro_ros_agent',
            output="screen",
            arguments=["udp4", "-p", "8888"]  # , "-v6"
        ),
        OpaqueFunction(function=make_nodes, args=[
            LaunchConfiguration('robot_model'),
            LaunchConfiguration('lds_model'),
            LaunchConfiguration('use_sim_time')
        ]),
    ])
