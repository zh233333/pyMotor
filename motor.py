import serial
import time
from threading import Event
import time
import datetime

def remove_comment(string):
    return string.split(';')[0].strip()

def send_wake_up(ser):
    ser.write(str.encode("\r\n\r\n"))
    time.sleep(2)
    ser.flushInput()

def wait_for_movement_completion(ser, cleaned_line):
    Event().wait(1)
    if cleaned_line not in ('$X', '$$'):
        idle_counter = 0
        while True:
            ser.reset_input_buffer()
            ser.write(str.encode('?\n'))
            grbl_response = ser.readline().strip().decode('utf-8')
            if 'Idle' in grbl_response:
                idle_counter += 1
            if idle_counter > 10:
                break

class Motor:
    """
    Represents a motor controller.

    Args:
        port (str): The serial port path.
        baud_rate (int, optional): The baud rate for serial communication. Defaults to 115200.
        feed_rate (int, optional): The feed rate for motor movement. Defaults to 1000.
        verbose (bool, optional): Whether to print verbose output. Defaults to False.
        auto_position_save (bool, optional): Whether to automatically save motor positions. Defaults to True.
        default_feed_rate (int, optional): The default feed rate for motor movement. Defaults to 100.
        name (str, optional): The name of the motor. Defaults to "Motor".
        id (int, optional): The ID of the motor. Defaults to 0.
    """

    def __init__(self, port, baud_rate=115200, verbose=False, auto_position_save=True, default_feed_rate=100, name="Motor", id=0):
        self.name = name
        self.id = id
        self.port_path = port
        self.baud_rate = baud_rate
        self.ser = serial.Serial(self.port_path, self.baud_rate)
        self.verbose = verbose
        self.default_feed_rate = default_feed_rate
    
    def __enter__(self):
        send_wake_up(self.ser)
        self.restore_position()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save_position()
        self.close()


    def save_position(self):
        """
        Saves the current motor position to a file.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        position_data = "{"
        position_data += f"\"timestamp\": \"{timestamp}\", "
        position_data += f"\"work_position\": {self.get_work_position()}, "
        position_data += f"\"id\": {self.id}, "
        position_data += "}" + "\n"
        with open("motor_positions.txt", "a") as file:
            file.write(position_data)

    def restore_position(self, position_file_path="motor_positions.txt", verbose=False):
        """
        Restores the motor position from a file.

        Args:
            position_file_path (str, optional): The path to the position file. Defaults to "motor_positions.txt".
        """


        with open(position_file_path, "r") as file:
            lines = file.readlines()
            if lines:
                last_line = lines[-1].strip()
            dict_str = eval(last_line)
            position = dict_str['work_position']
            print(f"Restored position: {position}")
            # position = last_line.split(": ")[1]
            # position = position.strip('[').strip(']').split(', ')
            # position = [float(p) for p in position]
            # self.set_work_position(position)

            if verbose:
                print(f"Restored position: {position}")

    

    def send_command(self, command):
        """
        Sends a command to the motor controller.

        Args:
            command (str): The command to send.

        Returns:
            str: The response from the motor controller.
        """
        self.ser.write(f"{command}\n".encode())

        if self.verbose:
            print(f"Sent command: {command}")
        wait_for_movement_completion(self.ser, command)
        grbl_response = self.ser.readline().strip().decode('utf-8')

        if self.verbose:
            print(f"GRBL Response: {grbl_response}")
        return grbl_response

    def set_spindle_speed(self, speed):
        """
        Sets the spindle speed of the motor.

        Args:
            speed (int): The spindle speed.

        Returns:
            str: The command to set the spindle speed.
        """
        command = f'S{speed}'
        return command

    def home(self):
        """
        Sends a home command to the motor.

        Returns:
            str: The home command.
        """
        command = '$H'
        return command

    def unlock(self):
        """
        Sends an unlock command to the motor.

        Returns:
            str: The unlock command.
        """
        command = '$X'
        return command

    def print_status(self):
        """
        Prints the status of the motor.
        """
        self.status(verbose=True)


    def status(self, verbose=False):
        """
        Gets the status of the motor.

        Args:
            verbose (bool, optional): Whether to print the status. Defaults to True.

        Returns:
            dict: The status of the motor.
        """
        self.ser.write(str.encode('?\n'))
        grbl_raw = self.ser.readline().strip().decode('utf-8')                      
        grbl_response = grbl_raw[1:-1].split(",")
        if self.verbose:
            print(f"GRBL Response: {grbl_response}")
        if (len(grbl_response) < 6):
            return self.status(verbose = verbose)
        
        grbl_is_idle = grbl_response[0] == 'Idle'
        grbl_machine_position = ",".join(grbl_response[1:4]).split(":")[1].split(",")
        grbl_work_position = ",".join(grbl_response[4:]).split(":")[1].split(",")
        output = {
            "GRBL is idle": grbl_is_idle,
            "Machine position": [float(i) for i in grbl_machine_position],
            "Work position": [float(i) for i in grbl_work_position]
        }

        if verbose:
            print(output)
        return output

    def stream_gcode(self, gcode_path):
        """
        Streams G-code commands from a file to the motor.

        Args:
            gcode_path (str): The path to the G-code file.
        """
        with open(gcode_path, "r") as file:
            for line in file:
                cleaned_line = remove_comment(line)
                if cleaned_line:
                    print(f"Sending gcode: {cleaned_line}")
                    self.send_command(cleaned_line)

    def close(self):
        """
        Closes the serial connection to the motor.
        """
        if self.ser:
            self.ser.close()

    def move(self, axis, pos, feed_rate=None):
        """
        Moves the motor to a specified position.

        Args:
            axis (str): The axis to move ('x', 'y', or 'z').
            pos (float): The position to move to.
            feed_rate (int, optional): The feed rate for the movement. Defaults to None.

        Raises:
            ValueError: If an invalid axis is provided.
        """
        if axis in ['1', '2', '3']:
            mapping = {'1': 'X', '2': 'Y', '3': 'Z'}
            axis = mapping[axis]

        if axis in ['x', 'y', 'z']:
            axis = axis.upper()
        
        if axis not in ['X', 'Y', 'Z']:
            raise ValueError('Invalid axis')
        
        if feed_rate is None:
            feed_rate = self.default_feed_rate
        
        command = f'G0 {axis}{pos} F{feed_rate}'
        self.send_command(command)



    def set_work_position(self, machine_position):
        """
        Sets the work position of the motor.

        Args:
            machine_position (list): The machine position to set.

        Returns:
            str: The command to set the work position.
        """
        command = f'G92 X{machine_position[0]} Y{machine_position[1]} Z{machine_position[2]}'
        self.send_command(command)

    def get_work_position(self):
        """
        Gets the current work position of the motor.

        Returns:
            list: The work position.
        """
        return self.status(verbose=False)["Work position"]

class Motor_manager():
    def __init__(self, motor_list):
        self.motor_list = motor_list

if __name__ == "__main__":
    # with Motor(port='/dev/tty.usbmodem11301') as motor:
    #     # motor.status()
    #     # motor.move('x', 30)
    #     # print(motor.get_work_position())
    #     print('year=h')

    Motor(port='/dev/tty.usbmodem11301').save_position()

    print('========================= END OF EXECUTION =========================')
