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
import select
import sys
import rclpy
import re
from rclpy.node import Node
from rclpy.parameter import Parameter
from ament_index_python.packages import get_package_share_path
from geometry_msgs.msg import Twist

if os.name == 'nt':
    import msvcrt
else:
    import termios
    import tty


class TeleopKeyboardNode(Node):
    def __init__(self, start_parameter_services=False):
        super().__init__(
            'teleop_keyboard_node',
            start_parameter_services=start_parameter_services
        )
        self.declare_parameters(
            namespace='',
            parameters=[
                ('max_lin_vel', 0.22),
                ('max_ang_vel', 12.84),
                ('lin_vel_step_size', 0.01),
                ('ang_vel_step_size', 0.1)
            ])
        self.max_lin_vel = self.get_parameter('max_lin_vel').value
        self.max_ang_vel = self.get_parameter('max_ang_vel').value
        self.lin_vel_step_size = self.get_parameter('lin_vel_step_size').value
        self.ang_vel_step_size = self.get_parameter('ang_vel_step_size').value
        print(self.max_ang_vel)

        self.tty_attr = None if os.name == 'nt' else termios.tcgetattr(sys.stdin)

        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)

        self.target_linear_velocity = 0.0
        self.target_angular_velocity = 0.0
        self.control_linear_velocity = 0.0
        self.control_angular_velocity = 0.0

        print('Control Kaia.ai-compatible Robot')
        print('---------------------')
        print('Moving around:')
        print('      w')
        print(' a    s    d')
        print('      x')
        print('w/x   : increase/decrease linear  velocity')
        print('a/d   : increase/decrease angular velocity')
        print('s     : keep straight')
        print('Space : force stop')
        print('CTRL-C to quit')


    def get_key(self):
        if os.name == 'nt':
            return msvcrt.getch().decode('utf-8')

        tty.setraw(sys.stdin.fileno())
        rlist, _, _ = select.select([sys.stdin], [], [])

        key = sys.stdin.read(1) if rlist else ''

        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.tty_attr)
        return key

    def print_vels(self):
        print('Linear velocity {:.3f}\tAngular velocity {:.3f}'.format(
            round(self.target_linear_velocity, 3),
            round(self.target_angular_velocity, 3))
        )

    @staticmethod
    def make_simple_profile(output, input, slop):
        if input > output:
            output = min(input, output + slop)
        elif input < output:
            output = max(input, output - slop)
        else:
            output = input

        return output

    @staticmethod
    def constrain(input_vel, low_bound, high_bound):
        if input_vel < low_bound:
            input_vel = low_bound
        elif input_vel > high_bound:
            input_vel = high_bound
        else:
            input_vel = input_vel

        return input_vel

    def check_linear_limit_velocity(self, velocity):
        return self.constrain(velocity, -self.max_lin_vel, self.max_lin_vel)

    def check_angular_limit_velocity(self, velocity):
        return self.constrain(velocity, -self.max_ang_vel, self.max_ang_vel)

    def perform(self):
        key = self.get_key()
        if key == 'w':
            self.target_linear_velocity = \
                self.check_linear_limit_velocity(self.target_linear_velocity + self.lin_vel_step_size)
            self.print_vels()
        elif key == 'x':
            self.target_linear_velocity = \
                self.check_linear_limit_velocity(self.target_linear_velocity - self.lin_vel_step_size)
            self.print_vels()
        elif key == 'a':
            self.target_angular_velocity = \
                self.check_angular_limit_velocity(self.target_angular_velocity + self.ang_vel_step_size)
            self.print_vels()
        elif key == 'd':
            self.target_angular_velocity = \
                self.check_angular_limit_velocity(self.target_angular_velocity - self.ang_vel_step_size)
            self.print_vels()
        elif key == 's':
            self.target_angular_velocity = 0
            self.print_vels()
        elif key == ' ':
            self.target_linear_velocity = 0.0
            self.control_linear_velocity = 0.0
            self.target_angular_velocity = 0.0
            self.control_angular_velocity = 0.0
            self.print_vels()
        elif (key == '\x03'):
            print('Stopping the robot and exiting on CTRL-C press')

            twist = Twist()
            twist.linear.x = 0.0
            twist.linear.y = 0.0
            twist.linear.z = 0.0

            twist.angular.x = 0.0
            twist.angular.y = 0.0
            twist.angular.z = 0.0

            self.publisher_.publish(twist)

            if os.name != 'nt':
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.tty_attr)

            return False

        twist = Twist()

        self.control_linear_velocity = \
            self.make_simple_profile(
                self.control_linear_velocity,
                self.target_linear_velocity,
                (self.lin_vel_step_size / 2.0)
            )

        twist.linear.x = self.control_linear_velocity
        twist.linear.y = 0.0
        twist.linear.z = 0.0

        self.control_angular_velocity = \
            self.make_simple_profile(
                self.control_angular_velocity,
                self.target_angular_velocity,
                (self.ang_vel_step_size / 2.0)
        )

        twist.angular.x = 0.0
        twist.angular.y = 0.0
        twist.angular.z = self.control_angular_velocity

        self.publisher_.publish(twist)
        return True


def main(args=None):
    if (len(sys.argv) == 4 and sys.argv[1] == '--ros-args'):
        yaml_path_name = sys.argv[3]
    else:
        if (len(sys.argv) == 2 and sys.argv[1].startswith('description:=')):
            description = sys.argv[1][13:]
        else:
            description = os.getenv('KAIAAI_ROBOT', 'kaiaai_snoopy')

        yaml_path_name = os.path.join(
            get_package_share_path(description),
            'config',
            'teleop_keyboard.yaml'
            )

        args = [
            '--ros-args',
            '--params-file',
            yaml_path_name
        ]

    print('YAML file name : {}'.format(yaml_path_name))

    rclpy.init(args=args)
    node = TeleopKeyboardNode(start_parameter_services=False)

    while(node.perform()):
        rclpy.spin_once(node, timeout_sec=0.001)

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
