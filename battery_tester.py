from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QDialog, QMessageBox, QInputDialog
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QTimer, Qt
import sys
import os
import csv
import datetime
import re
import serial
import pymysql

class BatteryTestApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        def resource_path(relative_path):
            try:
                base_path = sys._MEIPASS  # PyInstaller temp folder
            except Exception:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)
        loadUi(resource_path("battery_tester_design.ui"), self)

        self.port_config_path = {}

        try:
            with open(self.resource_path("config.txt"), "r") as file:
                for line in file:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        self.port_config_path[key.strip()] = value.strip()

            self.description = self.port_config_path.get("PORT")

        except Exception as e:
            print(f"Error reading config file: {e}")

        self.dmm = None
        port_name = self.port_config_path.get("PORT")

        if port_name:
            try:
                self.dmm = serial.Serial(port_name, baudrate=9600, timeout=1)
                self.portreflector.setText(f"Connected: {port_name}")
                self.voltagereader.setEnabled(True)
            except Exception as e:
                self.portreflector.setText("Connection Failed")
                self.voltagereader.setText("Connection Failed")
                print(f"Serial connection error: {e}")
        else:
            self.portreflector.setText("No Port Configured")
            self.voltagereader.setText("No Port Configured")

        self.message_form = QDialog()
        loadUi(resource_path("messageform.ui"), self.message_form)

        self.loginbutton.clicked.connect(self.login)
        self.logoutbutton.clicked.connect(self.logout)
        self.message_form.pushbuttonerror.clicked.connect(self.quit)

        # FIX 1: Connect serialnumber field so pressing Enter triggers scan
        self.serialnumber.returnPressed.connect(self.scan_serial)

        self.set_light(self.lightPassorFail, "lightgrey")

        self.serialnumber.setEnabled(False)
        self.progressBar.setEnabled(False)
        self.portreflector.setEnabled(False)
        self.progressBar.setValue(0)
        self.failreasoncombobox.hide()
        self.failreasontext.hide()

        self.update_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_voltage_display)

        if self.dmm and self.dmm.is_open:
            self.timer.start(1000)

        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.update_test_progress)

        self.test_time_elapsed = 0
        self.test_duration = 1
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)
        self.current_serial = None

    def login(self):
        ke_no = self.operatoren.text().strip().upper()
        shift = self.shift.currentText().strip().upper()

        if ke_no == "":
            self.message_form.errorlabel.setText("Set Your KE no.!!")
            self.message_form.show()
            return
        elif shift == "" or shift == "--SELECT--":
            self.message_form.errorlabel.setText("Set Your Shift!!")
            self.message_form.show()
            return

        self.loginbutton.setEnabled(False)
        self.operatoren.setEnabled(False)
        self.shift.setEnabled(False)
        self.progressBar.setEnabled(True)
        self.serialnumber.setEnabled(True)

    def scan_serial(self):
        if self.test_timer.isActive():
            QMessageBox.warning(self, "Wait", "Test in progress...")
            return

        serial_num = self.serialnumber.text().strip()

        if not serial_num:
            QMessageBox.warning(self, "Missing Serial", "Enter a serial number.")
            return

        if self.has_passed_before(serial_num):
            QMessageBox.information(self, "Already Passed", "This serial has already passed and cannot be tested again.")
            self.serialnumber.clear()
            return

        ok, message = self.check_station_status(serial_num)

        if not ok:
            QMessageBox.warning(self, "Station Check Failed", message)
            self.write_row(serial_num, f"Rejected - {message}")
            self.serialnumber.clear()
            return

        # FIX 2: Reset light and progress bar at the start of each new test
        self.set_light(self.lightPassorFail, "lightgrey")
        self.progressBar.setValue(0)
        self.failreasoncombobox.hide()
        self.failreasontext.hide()

        # FIX 3: Removed premature write_row here — only log after test result
        self.current_serial = serial_num
        self.test_time_elapsed = 0
        self.test_timer.start(100)
        self.serialnumber.clear()

    def update_test_progress(self):
        self.test_time_elapsed += 0.1

        progress_percent = int((self.test_time_elapsed / self.test_duration) * 100)
        self.progressBar.setValue(progress_percent)

        if self.test_time_elapsed >= self.test_duration:
            self.test_timer.stop()
            self.progressBar.setValue(100)
            self.run_test_after_delay()

    def run_test_after_delay(self):
        voltage = self.read_voltage()

        operator = self.operatoren.text().strip()
        shift = self.shift.currentText().strip()
        po_ok, po_num = self.check_po_num(self.current_serial)
        po_num = po_num if po_ok else ""
        existing_rep = self.get_current_test_rep(self.current_serial)
        next_rep = existing_rep + 1

        if voltage is None:
            self.set_light(self.lightPassorFail, "red", "ERROR")
            QMessageBox.critical(self, "Error", "DMM not connected or read failed")
            success, message = self.record_result(self.current_serial, 0, None)
            if success:
                self.write_row(
                    self.current_serial,
                    po_num,
                    operator,
                    shift,
                    datetime.datetime.now(),
                    None,
                    self.test_duration,
                    next_rep,
                    0,
                    None,
                )
            else:
                QMessageBox.warning(self, "Database Error", f"Failed to record error result: {message}")
            return

        if 3.7 <= voltage <= 4.2:
            action = "Pass"
            status_value = 1
            self.set_light(self.lightPassorFail, "green", "PASS")
            self.failreasoncombobox.hide()
            self.failreasontext.hide()
            fail_reason = None
        else:
            action = "Fail"
            status_value = 0
            self.set_light(self.lightPassorFail, "red", "FAIL")
            fail_reason = None
            if existing_rep >= 2:
                self.failreasoncombobox.show()
                self.failreasontext.show()
                fail_reason = self.ask_fail_reason()
                if not fail_reason:
                    QMessageBox.warning(self, "Fail Reason Required", "Please select a failure reason before recording.")
                    return
                self.failreasoncombobox.hide()
                self.failreasontext.hide()

        success, message = self.record_result(self.current_serial, status_value, voltage, fail_reason)
        if not success:
            QMessageBox.warning(self, "Database Error", f"Failed to record result: {message}")
            return
        self.write_row(
            self.current_serial,
            po_num,
            operator,
            shift,
            datetime.datetime.now(),
            voltage,
            self.test_duration,
            next_rep,
            status_value,
            fail_reason,
        )
        if status_value == 1:
            update_success, update_message = self.update_mainboard_battery_flag(self.current_serial)
            if not update_success:
                QMessageBox.warning(self, "Database Error", f"Failed to update mainboard_main: {update_message}")
    
    def check_po_num(self, serial_num):
        try:
            conn = pymysql.connect(
                host="192.168.1.38",
                user="labeling",
                password="labeling",
                database="ledtech"
            )

            cursor = conn.cursor()
            query = """
                SELECT po_num
                FROM mainboard_burnin
                WHERE serial_num = %s
                """
            cursor.execute(query, (serial_num,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return False, "Serial not found in database"
            return True, result[0]
        except Exception as e:
            return False, f"DB Error: {e}"

    def has_passed_before(self, serial_num):
        try:
            conn = pymysql.connect(
                host="192.168.1.38",
                user="labeling",
                password="labeling",
                database="ledtech"
            )
            cursor = conn.cursor()
            cursor.execute("SELECT battery FROM mainboard_main WHERE serial_num = %s", (serial_num,))
            result = cursor.fetchone()
            if result and result[0] == 1:
                conn.close()
                return True
            cursor.execute("SELECT status FROM mainboard_battery WHERE serial_num = %s", (serial_num,))
            result = cursor.fetchone()
            conn.close()
            return bool(result and result[0] == 1)
        except Exception:
            return False

    def get_current_test_rep(self, serial_num):
        try:
            conn = pymysql.connect(
                host="192.168.1.38",
                user="labeling",
                password="labeling",
                database="ledtech"
            )
            cursor = conn.cursor()
            cursor.execute("SELECT test_rep FROM mainboard_battery WHERE serial_num = %s", (serial_num,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else 0
        except Exception:
            return 0

    def ask_fail_reason(self):
        items = [self.failreasoncombobox.itemText(i) for i in range(self.failreasoncombobox.count())]
        if not items:
            return ""
        reason, ok = QInputDialog.getItem(self, "Failure Reason", "Select failure reason:", items, 0, False)
        reason = reason.strip()
        if not ok or not reason or reason.startswith("--"):
            return ""
        return reason

    def check_station_status(self, serial_num):
        try:
            conn = pymysql.connect(
                host="192.168.1.38",
                user="labeling",
                password="labeling",
                database="ledtech"
            )
            cursor = conn.cursor()
            query = """
                SELECT test, soldering1, burnin
                FROM mainboard_main
                WHERE serial_num = %s
            """
            cursor.execute(query, (serial_num,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return False, "Serial not found in database"

            test, soldering1, burnin = result
            missing = []
            if test == 0:
                missing.append("TEST")
            if soldering1 == 0:
                missing.append("SOLDERING1")
            if burnin == 0:
                missing.append("BURNIN")

            if missing:
                return False, f"Incomplete: {', '.join(missing)}"

            return True, "All stations passed"

        except Exception as e:
            return False, f"DB Error: {e}"

    def update_voltage_display(self):
        if not self.dmm or not self.dmm.is_open:
            self.voltagereader.setText("Disconnected")
            return

        voltage = self.read_voltage()
        if voltage is not None:
            self.voltagereader.setText(f"{voltage:.2f} V")
        else:
            self.voltagereader.setText("No Reading")

    def read_voltage(self):
        if not self.dmm:
            return None
        try:
            self.dmm.reset_input_buffer()
            self.dmm.reset_output_buffer()
            self.dmm.write(b'MEAS:VOLT:DC?\r\n')
            self.dmm.flush()
            response = self.dmm.readline().decode('ascii', errors='ignore').strip()
            if not response:
                response = self.dmm.read_until(expected=b'\n', size=100).decode('ascii', errors='ignore').strip()

            match = re.search(r'[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?', response)
            if not match:
                return None

            return float(match.group(0))
        except Exception:
            return None
    def record_result(self, serial_num, status, voltage, fail_reason=None):
        try:
            conn = pymysql.connect(
                host="192.168.1.38",
                user="testing",
                password="testing",
                database="ledtech"
            )
            cursor = conn.cursor()
            
            # Get PO number
            po_ok, po_data = self.check_po_num(serial_num)
            po_num = po_data if po_ok else ""
            
            operator = self.operatoren.text().strip()
            shift = self.shift.currentText().strip()
            
            cursor.execute("SELECT test_rep FROM mainboard_battery WHERE serial_num = %s", (serial_num,))
            existing = cursor.fetchone()
            if existing:
                test_rep = existing[0] + 1
                query = """
                    UPDATE mainboard_battery
                    SET po_num = %s,
                        operator_en = %s,
                        shift = %s,
                        date_time = %s,
                        vbat_volt = %s,
                        duration = %s,
                        test_rep = %s,
                        status = %s,
                        fail_reason = %s
                    WHERE serial_num = %s
                """
                cursor.execute(query, (
                    po_num,
                    operator,
                    shift,
                    datetime.datetime.now(),
                    voltage,
                    self.test_duration,
                    test_rep,
                    status,
                    fail_reason,
                    serial_num,
                ))
            else:
                test_rep = 1
                query = """
                    INSERT INTO mainboard_battery 
                    (serial_num, po_num, operator_en, shift, date_time, vbat_volt, duration, test_rep, status, fail_reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    serial_num, 
                    po_num, 
                    operator, 
                    shift, 
                    datetime.datetime.now(), 
                    voltage,
                    self.test_duration,
                    test_rep,
                    status,
                    fail_reason,
                ))
            conn.commit()
            conn.close()
            return True, "Result recorded"
        except Exception as e:
            return False, f"DB Error: {e}"

    def update_mainboard_battery_flag(self, serial_num):
        try:
            conn = pymysql.connect(
                host="192.168.1.38",
                user="testing",
                password="testing",
                database="ledtech"
            )
            cursor = conn.cursor()
            query = """
                UPDATE mainboard_main
                SET battery = 1
                WHERE serial_num = %s
            """
            cursor.execute(query, (serial_num,))
            conn.commit()
            conn.close()
            return True, "Updated mainboard_main"
        except Exception as e:
            return False, f"DB Error: {e}"

    def write_row(
        self,
        serial,
        po_num=None,
        operator=None,
        shift=None,
        date_time=None,
        vbat_volt=None,
        duration=None,
        test_rep=None,
        status=None,
        fail_reason=None,
    ):
        file_exists = os.path.isfile("results.csv")
        with open("results.csv", "a", newline="") as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow([
                    "Serial",
                    "PO Number",
                    "Operator",
                    "Shift",
                    "DateTime",
                    "VBAT_Volt",
                    "Duration",
                    "Test_Rep",
                    "Status",
                    "Fail_Reason",
                ])
            if date_time is None:
                date_time = datetime.datetime.now()
            writer.writerow([
                serial,
                po_num,
                operator,
                shift,
                date_time,
                vbat_volt,
                duration,
                test_rep,
                status,
                fail_reason,
            ])

    def resource_path(self, relative_path):
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except AttributeError:
            # If not running as PyInstaller bundle, use current directory
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def update_ui(self):
        self.set_light(self.lightPassorFail, "lightgrey")

    def set_light(self, label, color, text="", heightsize=40, widthsize=100):
        label.setFixedSize(widthsize, heightsize)
        label.setText(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"""
            background-color: {color};
            border-radius: 5px;
            border: 2px solid #555;
            color: white;
            font-weight: bold;
            font-size: 14px;
        """)

    def logout(self):
        self.loginbutton.setEnabled(True)
        self.operatoren.setEnabled(True)
        self.shift.setEnabled(True)
        self.progressBar.setEnabled(False)
        self.serialnumber.setEnabled(False)
        self.progressBar.setValue(0)
        self.set_light(self.lightPassorFail, "lightgrey")  # FIX 4: Reset light on logout
        self.operatoren.clear()
        self.shift.setCurrentIndex(0)

    def quit(self):
        self.message_form.close()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = BatteryTestApp()
    window.show()
    sys.exit(app.exec_())