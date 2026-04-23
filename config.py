import pymysql
from tkinter import messagebox
from datetime import datetime
import os

class Database:
    def __init__(self):
        self.config = {
            "host": "192.168.1.38",
            "user": "labeling",
            "password": "labeling",
            "database": "ledtech"
        }
    
    def get_batch_info(self, serial_num):
        try:
            db = pymysql.connect(**self.config)
            cursor = db.cursor()
            cursor.execute("SELECT batch_code, po_num FROM faceware_assembly1 WHERE serial_num = %s",
                           (serial_num,)
            )
            result = cursor.fetchone()
            cursor.close()
            db.close()

            if result:
                return result
            return None, None
        except pymysql.Error as err:
            print(f"database error", err)
            return None, None
        
class InsertDatabaseHandler:
    """Handle database inserts and updates"""
    
    def __init__(self):
        self.config = {
            'host': '192.168.1.38',
            'user': 'testing',
            'password': 'testing',
            'database': 'ledtech'
        }
        # Load config file
        BASE_DIR = os.path.dirname(__file__)
        config_path = os.path.join(BASE_DIR, "label_config.txt")
        inner_zpl = os.path.join(BASE_DIR, "inner_zpl.txt")
        outer_zpl = os.path.join(BASE_DIR, "outer_zpl.txt")

        self.config_data = {}

        try:
            with open(config_path, "r") as file:
                for line in file:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        self.config_data[key.strip()] = value.strip()

            self.description = self.config_data.get("DESCRIPTION", "")
            self.sku = self.config_data.get("SKU_NUMBER", "")
            self.customer_po = self.config_data.get("CUSTOMER_PO", "")
            self.inner_printer = self.config_data.get("INNER_PRINTER", "")
            self.outer_printer = self.config_data.get("OUTER_PRINTER", "")

        except Exception as e:
            print(f"[CONFIG ERROR] {e}")
            self.description = ""
            self.sku = ""
            self.customer_po = ""

    def record_operator_activity(self, operator, shift, serial_num, batch_code, po_num,
                             ship_mode, innerbox, outerbox, pallet_num, status):
        """Insert operator data with box counting information"""
        try:
            db = pymysql.connect(**self.config)
            cursor = db.cursor(pymysql.cursors.DictCursor)
            # Verify serial exists in faceware_main
            cursor.execute("SELECT * FROM faceware_main WHERE serial_num = %s", (serial_num,))
            main_data = cursor.fetchone()

            if not main_data:
                messagebox.showerror("Database Error", f"Serial {serial_num} not found in faceware_main")
                cursor.close()
                db.close()
                return False

            # Verify all required stations have status = 1
            required_stations = [
                "assembly1", "lasermarking1",
                "assembly2", "soldering2", "vi2",
                "assembly4", "vi3", "finaltest",
                "packing", "lasermarking2", "fvi"
            ]

            incomplete_stations = [
                s for s in required_stations
                if s not in main_data or main_data[s] != 1
            ]

            if incomplete_stations:
                messagebox.showerror(
                    "Incomplete Stations",
                    f"Serial {serial_num} hasn't completed all required stations.\n"
                    f"Missing: {', '.join(incomplete_stations)}"
                )
                cursor.close()
                db.close()
                return False

            # Get batch_code & PO if not provided
            if not batch_code or not po_num:
                cursor.execute(
                    "SELECT batch_code, po_num FROM faceware_assembly1 WHERE serial_num = %s",
                    (serial_num,)
                )
                result = cursor.fetchone()
                if result:
                    batch_code = result['batch_code']
                    po_num = result['po_num']
                else:
                    messagebox.showerror("Database Error", f"Could not find batch info for {serial_num}")
                    cursor.close()
                    db.close()
                    return False

            if not self.description or not self.sku or not self.customer_po:
                messagebox.showerror('Config error:', 'missing label config.txt values!')
                cursor.close()
                db.close()
                return False
            

            # ... (all your existing validation checks stay the same) ...

            # Insert packaging record with status = 0 first
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            insert_query = """
                INSERT INTO faceware_packaging
                (serial_num, po_num, operator_en, shift, date_time,
                description, sku, customer_po, batch_code,
                ship_mode, innerbox, outerbox, pallet_num, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                serial_num,
                po_num,
                operator,
                shift,
                now,
                self.description,
                self.sku,
                self.customer_po,
                batch_code,
                ship_mode,
                innerbox,
                outerbox,
                pallet_num,
                status,          # ← now correctly uses the parameter
            ))

            # ✅ Update faceware_packaging status to 1
            cursor.execute("""
                UPDATE faceware_packaging
                SET status = 1
                WHERE serial_num = %s AND po_num = %s AND batch_code = %s
            """, (serial_num, po_num, batch_code))

            # ✅ Update faceware_main packaging status to 1
            cursor.execute("""
                UPDATE faceware_main
                SET packaging = 1
                WHERE serial_num = %s
            """, (serial_num,))

            db.commit()
            print(f"[DB] ✅ Recorded & status updated: Serial {serial_num} | "
                f"Innerbox {innerbox} | Outerbox {outerbox} | Pallet {pallet_num}")
            cursor.close()
            db.close()
            return True

        except pymysql.Error as err:
            print(f"[DB ERROR] {err}")
            messagebox.showerror("Database Error", f"⚠️ Database error occurred:\n{err}")
            if 'cursor' in locals():
                cursor.close()
            if 'db' in locals():
                db.close()
            return False

    def check_existing_packaging(self, serial_num, po_num=None, batch_code=None, status=None):
        """Check if serial_num already exists in faceware_packaging"""
        try:
            db = pymysql.connect(**self.config)
            cursor = db.cursor(pymysql.cursors.DictCursor)
            
            if po_num is not None and batch_code is not None and status is not None:
                query = """
                    SELECT * FROM faceware_packaging
                    WHERE serial_num = %s AND po_num = %s AND batch_code = %s AND status = %s
                """
                cursor.execute(query, (serial_num, po_num, batch_code, status))
            else:
                query = """
                    SELECT * FROM faceware_packaging
                    WHERE serial_num = %s
                """
                cursor.execute(query, (serial_num,))

            result = cursor.fetchone()
            
            cursor.close()
            db.close()
            return result is not None
                
        except pymysql.Error as err:
            print(f"[DB ERROR] {err}")
            return None

    #------------------------------------------------------get all unit in batch
    def get_batch_unit_count(self, batch_code, po_num):
        """Count units packaged for a batch code"""
        try:
            db = pymysql.connect(**self.config)
            cursor = db.cursor()
            
            query = """
                SELECT COUNT(*) FROM faceware_packaging
                WHERE batch_code = %s AND po_num = %s
            """
            cursor.execute(query, (batch_code, po_num))
            count = cursor.fetchone()[0]
            
            cursor.close()
            db.close()
            return count
                
        except pymysql.Error as err:
            print(f"[DB ERROR] {err}")
            return 0

    def get_pallet_unit_count(self, pallet_num, po_num):
        """Count units in a specific pallet"""
        try:
            db = pymysql.connect(**self.config)
            cursor = db.cursor()
            
            query = """
                SELECT COUNT(*) FROM faceware_packaging
                WHERE pallet_num = %s AND po_num = %s
            """
            cursor.execute(query, (pallet_num, po_num))
            count = cursor.fetchone()[0]
            
            cursor.close()
            db.close()
            return count
                
        except pymysql.Error as err:
            print(f"[DB ERROR] {err}")
            return 0

    def update_packaging_status(self, serial_num, po_num, batch_code):
        """Update packaging status after label printing"""
        try:
            db = pymysql.connect(**self.config)
            cursor = db.cursor()

            update_main_query = """
                UPDATE faceware_main 
                SET packaging = 1 
                WHERE serial_num = %s
            """
            cursor.execute(update_main_query, (serial_num,))
            
            update_packaging_query = """
                UPDATE faceware_packaging
                SET status = 1 
                WHERE serial_num = %s AND po_num = %s AND batch_code = %s
            """
            cursor.execute(update_packaging_query, (serial_num, po_num, batch_code))
            
            db.commit()
            cursor.close()
            db.close()
            return True

        except pymysql.Error as err:
            print(f"[DB ERROR] {err}")
            return False

    def get_unfinished_batches(self):
        """Return list of unfinished batches"""
        try:
            db = pymysql.connect(**self.config)
            cursor = db.cursor(pymysql.cursors.DictCursor)
            
            query = """
                SELECT batch_code, po_num, COUNT(*) as unit_count
                FROM faceware_packaging
                WHERE status = 0
                GROUP BY batch_code, po_num
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            cursor.close()
            db.close()
            return results
                
        except pymysql.Error as err:
            print(f"[DB ERROR] {err}")
            return []

    def get_all_batch_codes(self):
        """Return list of all batch codes with their PO numbers and unit counts"""
        try:
            db = pymysql.connect(**self.config)
            cursor = db.cursor(pymysql.cursors.DictCursor)
            
            query = """
                SELECT batch_code, po_num, COUNT(*) as unit_count, 
                       SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as completed_units,
                       SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) as pending_units
                FROM faceware_packaging
                GROUP BY batch_code, po_num
                ORDER BY batch_code
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            cursor.close()
            db.close()
            return results
                
        except pymysql.Error as err:
            print(f"[DB ERROR] {err}")
            return []