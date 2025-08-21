import serial.tools.list_ports
from src.HapticModel import HapticDriver

class SerialCtrl:
    
    def __init__(self):
        self.driver = HapticDriver()
        self.port = None
        self.baud = None
        self.com_list = []

    def getCOMList(self):
        ports = serial.tools.list_ports.comports()
        self.com_list = [com[0] for com in ports]  # Get COM port list
        self.com_list.insert(0, "-")  # Add placeholder option

    def SerialOpen(self, ComGUI):
        # Get selected COM port and baud rate from GUI
        self.port = ComGUI.clicked_com.get()
        self.baud = ComGUI.clicked_bd.get()

        if self.port == "-" or self.baud == "-":
            print("Error: Select a valid COM port and baud rate.")
            return

        if self.driver.is_connected():
            print("[HapticUI]: Already connected, not reconnecting.")
            return

        print(f"[HapticUI]: COM={self.port}, Baudrate={self.baud}")

        try:
            self.driver.connect(self.port, int(self.baud))  # 🔧 Baudrate int olmalı
            self.send_data('{"cmd":"set","deney_no":1}')
        except Exception as e:
            print(f"[HapticUI][ERROR]: Connection failed -> {str(e)}")


    def send_data(self, data):
        print(f"Sending data: {data}")
        self.driver.sendMessageToSTM(data + "\r\n")
        print(f"Data sent: {data}")

    def set_receive_callback(self, callback):
        self.driver.onDataReceive = callback


if __name__ == "__main__":
    SerialCtrl()
