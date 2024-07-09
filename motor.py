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
    """

    def __init__(self, port, baud_rate=115200, verbose=False, auto_position_save=True, default_feed_rate=100, name = "Motor", id = 0):
        self.name = name
        self.id = id
        self.port_path = port
        self.baud_rate = baud_rate
        self.ser = None
        self.verbose = verbose
        self.default_feed_rate = default_feed_rate
    
    def save_position(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        position_data = f"{timestamp}: {self.status()["Work position"]}\n"
        with open("motor_positions.txt", "a") as file:
            file.write(position_data)

    def __enter__(self):
        self.ser = serial.Serial(self.port_path, self.baud_rate)
        send_wake_up(self.ser)
        self.restore_position()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save_position()
        self.close()

    def send_command(self, command):
        self.ser.write(f"{command}\n".encode())

        if self.verbose:
            print(f"Sent command: {command}")
        wait_for_movement_completion(self.ser, command)
        grbl_response = self.ser.readline().strip().decode('utf-8')

        if self.verbose:
            print(f"GRBL Response: {grbl_response}")
        return grbl_response

    def set_spindle_speed(self, speed):
        command = f'S{speed}'
        return command

    def home(self):
        command = '$H'
        return command

    def unlock(self):
        command = '$X'
        return command

    def status(self, verbose=True):

        self.ser.write(str.encode('?\n'))
        grbl_raw = self.ser.readline().strip().decode('utf-8')                      
        grbl_response = grbl_raw[1:-1].split(",")
        if self.verbose:
            print(f"GRBL Response: {grbl_response}")
        if (len(grbl_response) < 6):
            return self.status()
        
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
        with open(gcode_path, "r") as file:
            for line in file:
                cleaned_line = remove_comment(line)
                if cleaned_line:
                    print(f"Sending gcode: {cleaned_line}")
                    self.send_command(cleaned_line)

    def close(self):
        if self.ser:
            self.ser.close()

    def move(self, axis, pos, feed_rate = None):
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

    def restore_position(self, position_file_path="motor_positions.txt"):
        with open(position_file_path, "r") as file:
            lines = file.readlines()
            if lines:
                last_line = lines[-1].strip()
            position = last_line.split(": ")[1]
            # print(position)
            position = position.strip('[').strip(']').split(', ')
            position = [float(p) for p in position]
            # print(position)
            self.set_work_position(position)

    def set_work_position(self, machine_position):
        command = f'G92 X{machine_position[0]} Y{machine_position[1]} Z{machine_position[2]}'
        self.send_command(command)
        self.ser.readline()

    def get_work_position(self):
        return self.status()["Work position"]

class Motor_manager():
    def __init__(self, motor_list):
        self.motor_list = motor_list

    

if __name__ == "__main__":
    with Motor(port = '/dev/tty.usbmodem11301') as motor:
        motor.status()
        motor.move('x', 30)
        print(motor.get_work_position())

    print('EOF')





















"""

    # Example commands

        #motor.home()
        #motor.set_feed_rate(1000)
        # motor.set_spindle_speed(1000)


        # Stream G-code file
        # gcode_path = 'path/to/your/gcode_file.gcode'
        # motor.stream_gcode(gcode_path)
"""    