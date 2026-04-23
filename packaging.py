import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QDialog
from PyQt5.uic import loadUi
from PyQt5.QtCore import QTimer
from config import InsertDatabaseHandler, Database
from print_label import LabelPrinter
from datetime import datetime
# from zpl_codes import inner_zpl, outer_zpl
import os
import csv

class PackagingApp(QMainWindow):
    def __init__(self):
        super(PackagingApp, self).__init__()
        def resource_path(relative_path):
            try:
                base_path = sys._MEIPASS  # PyInstaller temp folder
            except AttributeError:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)
        
        loadUi(resource_path("try.ui"), self)

        # Load the message form dialog
        self.message_form = QDialog()
        loadUi(resource_path("messageform.ui"), self.message_form)

        self.reprint_form = QMainWindow()
        loadUi(resource_path("reprint.ui"), self.reprint_form)

        self.duplicatemessage_form = QMainWindow()
        loadUi(resource_path("duplicate_message.ui"), self.duplicatemessage_form)

        self.setWindowTitle("Packaging App")
        self.loginbutton.clicked.connect(self.login)
        self.logoutbutton.clicked.connect(self.logout)
        self.neworchangebatchbutton.clicked.connect(self.start_new_batch)
        self.startnewscanherelabel.hide()
        self.reprintbutton.clicked.connect(self.reprint_batch)

        self.db = Database()  # Initialize database connection
        self.current_pallet_count = 0
        
        self.label_printer = LabelPrinter()  # Initialize label printer
        # self.label_printer.test_connection()

        # Display COM ports in UI
        self.innerprinterport.setText(self.label_printer.inner_printer_port)
        self.outerprinterport.setText(self.label_printer.outer_printer_port)
        self.innerprinterport.setEnabled(True)
        self.outerprinterport.setEnabled(True)

        # Connect the button inside the message_form dialog
        self.message_form.pushbuttonerror.clicked.connect(self.quit)

        self.shippingmodecombobox.currentTextChanged.connect(self.update_total_boxes)
        self.scanherelineEdit.setEnabled(False)
        self.scanherelineEdit.returnPressed.connect(self.scan_serial)
        self.resultstextEdit.setEnabled(False)
        self.batchcode.setEnabled(False)
        self.currentpalletlabel_2.setEnabled(False)
        self.totalunitsinbatch.setEnabled(False)
        self.progressBar.setEnabled(False)
        self.progressBar.setValue(0)
        
        self.innerprinterport.setEnabled(False)
        self.outerprinterport.setEnabled(False)
        
        progress_pallet = (
            self.logoutbutton,
            self.neworchangebatchbutton,
            self.reprintbutton,
            self.scanherelineEdit,
            self.resultstextEdit,
            self.totalbatchtableWidget,
            # self.boxperpalletcombobox
        )

        for widget in progress_pallet:
            widget.setEnabled(False)

        # Initialize database handler
        self.db_handler = InsertDatabaseHandler()

        # Pre-populate boxperpalletcombobox based on default shipping mode
        self.update_total_boxes(self.shippingmodecombobox.currentText())

        self.units_per_innerbox = 2
        self.innerboxes_per_outerbox = 5
        self.csv_file = resource_path("packaging_log.csv")
    
    def get_innerbox_number(self, total_units_before):
        next_unit = total_units_before + 1
        print_label = self.label_printer.print_inner()
        return ((next_unit - 1) // self.units_per_innerbox) + 1, print_label

    def get_outerbox_number(self, innerbox_number):
        print_label = self.label_printer.print_outer()
        return ((innerbox_number - 1) // self.innerboxes_per_outerbox) + 1, print_label

    def log_to_csv(self, data):
        file_exists = os.path.isfile(self.csv_file)
        with open(self.csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["serial_num", "po_num", "operator_en", "shift", "date_time", "description", "sku", "customer_po", "batch_code", "ship_mode", "innerbox", "outerbox", "pallet_num", "status"])
            writer.writerow(data)
    #---------------------------------disconnect printer on close
    def closeEvent(self, event):
        event.accept()

    def login(self):
        #-------------------------------------------------------login widget
        ke_no = self.loginlineEdit.text().strip().upper()

        if ke_no == "":
            self.message_form.show()
            return

        shift_text = self.shiftcomboBox.currentText()   # e.g. "Morning" or "Night"
        shipping_mode = self.shippingmodecombobox.currentText()
        box_per_pallet = self.boxperpalletcombobox.currentText()
        
        self.loginbutton.setEnabled(False)
        print(f"Login successful for ke_no: {ke_no}, Shift: {shift_text}, Shipping Mode: {shipping_mode}")

        #-------------------------------------------------------Session&progress widget
        # FIX 1: Reflect all login values into their display labels
        self.operatorreflectlabel.setText(ke_no)
        self.shiftreflectlabel.setText(shift_text)
        self.shippingmodereflectlabel.setText(shipping_mode)
        self.boxperpalletreflectlabel.setText(box_per_pallet)
        # FIX 2: Pre-populate box-per-pallet options based on the chosen shipping mode
        self.update_total_boxes(shipping_mode)
        self.boxperpalletcombobox.setEnabled(False)

        # Disable login inputs after successful login
        self.loginlineEdit.setEnabled(False)
        self.shiftcomboBox.setEnabled(False)
        self.shippingmodecombobox.setEnabled(False)
        self.neworchangebatchbutton.setEnabled(True)
        self.reprintbutton.setEnabled(True)
        self.logoutbutton.setEnabled(True)
        self.scanherelineEdit.setEnabled(True)
        self.resultstextEdit.setEnabled(True)
        self.totalbatchtableWidget.setEnabled(True)

        self.pallet_limit = int(box_per_pallet) if box_per_pallet.isdigit() else 1
        self.current_pallet_count = 0

        self.progressBar.setEnabled(True)
        self.progressBar.setMaximum(self.pallet_limit)
        self.progressBar.setValue(0)
        self.progressBar.setTextVisible(True)

        self.table_batch()

    def logout(self):
        print("Logout successful")
        # FIX 3: Reset all reflect labels (removed non-existent modereflectlabel)
        self.operatorreflectlabel.setText("---")
        self.shiftreflectlabel.setText("---")
        self.shippingmodereflectlabel.setText("---")
        self.batchcode.setText("---")
        self.currentunitinpallet.setText("---")
        self.boxperpalletreflectlabel.setText("---")
        self.currentpalletlabel_2.setText("---")
        self.progressBar.setValue(0)

        self.loginlineEdit.setEnabled(True)
        self.loginlineEdit.clear()
        self.shiftcomboBox.setEnabled(True)
        self.shippingmodecombobox.setEnabled(True)
        self.loginbutton.setEnabled(True)
        self.boxperpalletcombobox.setEnabled(True)

        self.scanherelineEdit.setEnabled(False)
        self.resultstextEdit.setEnabled(False)
        self.totalbatchtableWidget.setEnabled(False)
        self.reprintbutton.setEnabled(False)
        self.neworchangebatchbutton.setEnabled(False)
        self.logoutbutton.setEnabled(False)

        self.totalbatchtableWidget.setRowCount(0)
        self.totalunitsinbatch.setText("---")
        self.resultstextEdit.clear()

    def quit(self):
        self.message_form.close()

    def counting_unit(self):
        innerbox = 0
        outerbox = 0
        pallet_num = 0
    def scan_serial(self):
        scanned_code = self.scanherelineEdit.text().strip()
        self.scanherelineEdit.clear()

        if not scanned_code:
            return
        try:
            batch_code, po_num = self.db.get_batch_info(scanned_code)
            batch_code = str(batch_code).upper()
            po_num = str(po_num).upper()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", str(e))
            return

        if not batch_code:
            QMessageBox.warning(self, "Not Found", f"Serial {scanned_code} is NOT in the database!")
            self.resultstextEdit.append(f"<span style='color: red;'>❌ {scanned_code} - NOT FOUND</span>")
            self.scanherelineEdit.setFocus()
            return

        # ✅ ALWAYS get latest total from DB first
        totalunitsinbatch = self.db_handler.get_batch_unit_count(batch_code, po_num) or 0

        # ✅ Compute pallet values BEFORE insert (used for duplicate case)
        current_pallet_count = totalunitsinbatch % self.pallet_limit
        current_pallet_number = (totalunitsinbatch // self.pallet_limit) + 1
        current_innerbox = self.get_innerbox_number(totalunitsinbatch)
        current_outerbox = self.get_outerbox_number(current_innerbox)

        existing = self.db_handler.check_existing_packaging(scanned_code)

        if existing:
            QMessageBox.warning(self, "Duplicate Entry", f"Serial {scanned_code} already exists!")

            self.resultstextEdit.append(
                f"<span style='color: orange;'>⚠️ {scanned_code} - DUPLICATE</span>"
            )

            # ✅ UI update
            self.batchcode.setText(str(batch_code))
            self.totalunitsinbatch.setText(str(totalunitsinbatch))

            self.currentunitinpallet.setText(
                f"{current_pallet_count} / {self.pallet_limit}"
            )

            self.currentpalletlabel_2.setText(
                f"{current_pallet_number}"
            )

            self.scanherelineEdit.setFocus()

            self.update_progress_bar(current_pallet_count, self.pallet_limit)
            return

        # ================= SAVE =================
        operator = self.operatorreflectlabel.text()

        shift_map = {
            "Morning": "A",
            "Night": "B"
        }
        shift = shift_map.get(self.shiftreflectlabel.text(), "A")

        ship_mode = self.shippingmodereflectlabel.text()

        boxes_per_pallet_text = self.boxperpalletcombobox.currentText()
        boxes_per_pallet = int(boxes_per_pallet_text) if boxes_per_pallet_text.isdigit() else 1

        success = self.db_handler.record_operator_activity(
            operator,
            shift,
            scanned_code,
            batch_code,
            po_num,
            ship_mode,
            innerbox=current_innerbox,
            outerbox=current_outerbox,
            pallet_num=current_pallet_number,
            status=1
        )

        if success:
            self.resultstextEdit.append(
                f"<span style='color: green;'>✅ {scanned_code} - OK</span>"
            )

            # ✅ Log to CSV for local database
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            csv_data = [
                scanned_code,
                po_num,
                operator,
                shift,
                now,
                self.db_handler.description,
                self.db_handler.sku,
                self.db_handler.customer_po,
                batch_code,
                ship_mode,
                current_innerbox,  # innerbox
                current_outerbox,  # outerbox
                current_pallet_number,
                1   # status
            ]
            self.log_to_csv(csv_data)

            # ✅ REFETCH AFTER INSERT (VERY IMPORTANT)
            totalunitsinbatch = self.db_handler.get_batch_unit_count(batch_code, po_num) or 0

            # ✅ Recompute after insert
            current_pallet_count = totalunitsinbatch % self.pallet_limit
            current_pallet_number = (totalunitsinbatch // self.pallet_limit) + 1

            # ✅ UI update
            self.totalunitsinbatch.setText(str(totalunitsinbatch))
            self.batchcode.setText(str(batch_code))

            self.currentunitinpallet.setText(
                f"{current_pallet_count} / {self.pallet_limit}"
            )

            self.currentpalletlabel_2.setText(
                f"{current_pallet_number}"
            )

            # ✅ Notify if pallet completed exactly
            if current_pallet_count == 0 and totalunitsinbatch != 0:
                QMessageBox.information(
                    self,
                    "Pallet Complete",
                    f"Pallet #{current_pallet_number - 1} completed."
                )

            self.update_progress_bar(current_pallet_count, self.pallet_limit)

            self.table_batch()

        else:
            self.resultstextEdit.append(
                f"<span style='color: red;'>❌ {scanned_code} - FAILED</span>"
            )

        self.scanherelineEdit.setFocus()
    
    def update_progress_bar(self, current, limit):
        if limit <= 0:
            return

        percent = int((current / limit) * 100)
        self.progressBar.setValue(current)
        self.progressBar.setMaximum(limit)
        self.progressBar.setTextVisible(True)
        self.progressBar.setFormat(f"{percent}%")

        # Color logic
        if percent <= 60:
            color = "#2ecc71"   # green
        elif percent <= 85:
            color = "#f1c40f"   # yellow
        else:
            color = "#e74c3c"   # red

        self.progressBar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #999;
                border-radius: 5px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)

    def reprint_batch(self):
        self.reprint_form.show()

    def update_total_boxes(self, value):
        self.boxperpalletcombobox.clear()
        if value == "Air":
            self.boxperpalletcombobox.addItems(["150", "170"])
        elif value == "Sea":
            self.boxperpalletcombobox.addItems(["200", "230", "250"])

    def start_new_batch(self):
        self.startnewscanherelabel.show()
        QTimer.singleShot(2000, self.startnewscanherelabel.hide)
        self.boxperpalletcombobox.setCurrentIndex(-1)
        self.progressBar.setValue(0)
        self.currentpalletlabel_2.setText("---")
        self.totalunitsinbatch.setText("---")
        self.currentunitinpallet.setText("---")
        self.batchcode.setText("---")

    def table_batch(self):
        """Display all batch codes in the table"""
        self.totalbatchtableWidget.setRowCount(0)

        batches = self.db_handler.get_all_batch_codes()

        if not batches:
            print("No batch codes found in database")
            return

        self.totalbatchtableWidget.setRowCount(len(batches))

        if self.totalbatchtableWidget.columnCount() == 0:
            self.totalbatchtableWidget.setColumnCount(4)
            self.totalbatchtableWidget.setHorizontalHeaderLabels([
                "Batch Code", "PO Number", "Total Units", "Completed"
            ])

        for row, batch in enumerate(batches):
            self.totalbatchtableWidget.setItem(row, 0, QtWidgets.QTableWidgetItem(str(batch['batch_code'])))
            self.totalbatchtableWidget.setItem(row, 1, QtWidgets.QTableWidgetItem(str(batch['po_num'])))
            self.totalbatchtableWidget.setItem(row, 2, QtWidgets.QTableWidgetItem(str(batch['unit_count'])))
            self.totalbatchtableWidget.setItem(row, 3, QtWidgets.QTableWidgetItem(str(batch['completed_units'])))

        self.totalbatchtableWidget.resizeColumnsToContents()

        print(f"Displayed {len(batches)} batch codes in table")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PackagingApp()
    window.show()
    sys.exit(app.exec_())   