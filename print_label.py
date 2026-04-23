import os
import serial
import time
from PyQt5.QtWidgets import QMessageBox

class LabelPrinter:
    def __init__(self):
        BASE_DIR = os.path.dirname(__file__)

        self.config_data = {}

        config_path = os.path.join(BASE_DIR, "label_config.txt")
        inner_zpl_path = os.path.join(BASE_DIR, "inner_zpl.txt")
        outer_zpl_path = os.path.join(BASE_DIR, "outer_zpl.txt")

        try:
            # Read config
            with open(config_path, "r") as file:
                for line in file:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        self.config_data[key.strip()] = value.strip()

            self.inner_printer_port = self.config_data.get("INNER_PRINTER", "")
            self.outer_printer_port = self.config_data.get("OUTER_PRINTER", "")

            # Load ZPL
            with open(inner_zpl_path, "r") as f:
                self.inner_zpl_template = f.read()

            with open(outer_zpl_path, "r") as f:
                self.outer_zpl_template = f.read()

        except Exception as e:
            print(f"[Printer Error] {e}")
    
    def send_to_printer(self, port, zpl_data):
        ser = None
        try:
            ser = serial.Serial(
                port=port,
                baudrate=9600,
                bytesize=8,
                timeout=1,
                stopbits=serial.STOPBITS_ONE
            )

            ser.write(zpl_data.encode('utf-8'))
            ser.flush()
            time.sleep(0.5)

            print(f"Printed to {port}")

        except Exception as e:
            print(f"[Print Error] {port}: {e}")
            QMessageBox.critical(None, f"Print Error {port}: {e}")

        finally:
            if ser and ser.is_open:
                ser.close()
                time.sleep(0.3)  # give OS time to release

    def print_inner(self, data):
        if not self.inner_printer_port:
            print("No INNER printer configured")
            return

        zpl = self.inner_zpl_template.replace("{DATA}", data)
        self.send_to_printer(self.inner_printer_port, zpl)

    def print_outer(self, data):
        if not self.outer_printer_port:
            print("No OUTER printer configured")
            return

        zpl = self.outer_zpl_template.replace("{DATA}", data)
        self.send_to_printer(self.outer_printer_port, zpl)

    def test_connection(self):
        ports = [
            ("INNER", self.inner_printer_port),
            ("OUTER", self.outer_printer_port)
        ]

        for name, port in ports:
            if not port:
                print(f"{name} printer not configured")
                continue

            try:
                with serial.Serial(port=port, baudrate=9600, timeout=1) as ser:
                    print(f"{name} printer OK on {port}")
            except Exception as e:
                print(f"{name} printer FAILED on {port}: {e}")