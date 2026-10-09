import tkinter as tk
from tkinter import ttk, messagebox
import hashlib
import re
from datetime import datetime, date, timedelta
from database import get_connection

BG = "#eef2f7"
NAVY = "#172554"
BLUE = "#2563eb"
RED = "#dc2626"
STATUSES = ["Available", "Reserved", "Occupied", "Maintenance"]
ENROLLMENT_PATTERN = re.compile(r"^ADT\d{2}[A-Z]{4}\d{4}$", re.IGNORECASE)


def hash_password(password):
    # Kept compatible with the existing demo login records.
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def db_connection():
    connection = get_connection()
    if not connection:
        messagebox.showerror("Database Error", "Cannot connect to MySQL.")
    return connection


def initialise_app_tables():
    """Create the student table if it does not already exist."""
    connection = db_connection()
    if not connection:
        return False
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                enrollment_no VARCHAR(20) PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                class_name VARCHAR(50) NOT NULL,
                phone_number VARCHAR(20) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("SHOW COLUMNS FROM students LIKE 'phone_number'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE students ADD COLUMN phone_number VARCHAR(20) NULL")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reading_room_bookings (
                booking_id INT AUTO_INCREMENT PRIMARY KEY,
                enrollment_no VARCHAR(20) NOT NULL,
                resource_id INT NOT NULL,
                seat_number INT NOT NULL DEFAULT 1,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                status ENUM('Booked','Cancelled','Completed') NOT NULL DEFAULT 'Booked',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_room_booking_resource_time (resource_id, start_time, end_time),
                INDEX idx_room_booking_student_time (enrollment_no, start_time)
            )
        """)
        cursor.execute("SHOW COLUMNS FROM reading_room_bookings LIKE 'seat_number'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE reading_room_bookings ADD COLUMN seat_number INT NOT NULL DEFAULT 1 AFTER resource_id")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS class_timetable (
                timetable_id INT AUTO_INCREMENT PRIMARY KEY,
                class_name VARCHAR(50) NOT NULL,
                day_name ENUM('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday') NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                subject_name VARCHAR(100) NOT NULL,
                batch_name VARCHAR(20) NOT NULL DEFAULT 'All',
                room_no VARCHAR(30) NOT NULL,
                is_lab TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_timetable_class_day (class_name, day_name, start_time)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_allocations (
                allocation_id INT AUTO_INCREMENT PRIMARY KEY,
                class_name VARCHAR(50) NOT NULL,
                batch_name VARCHAR(10) NOT NULL,
                enrollment_no VARCHAR(20) NOT NULL,
                resource_id INT NOT NULL,
                allocation_type ENUM('Regular','Temporary') NOT NULL DEFAULT 'Regular',
                allocation_status ENUM('Assigned','Absent','Released') NOT NULL DEFAULT 'Assigned',
                note VARCHAR(255) NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_lab_alloc_class_batch (class_name, batch_name),
                INDEX idx_lab_alloc_resource (resource_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                teacher_id VARCHAR(10) PRIMARY KEY,
                full_name VARCHAR(120) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        teacher_seed = [
            ("SA", "Prof. Simran Ahuja"),
            ("VBO", "Prof. Vishal Bogam"),
            ("RAA", "Prof. Radhika Adki"),
            ("AD", "Dr. Aaradhna Deshmukh"),
            ("SW", "Prof. Shashikant Waghule"),
            ("AVR", "Prof. Avinash Rakh"),
            ("SJ", "Dr. Suvarna Joshi"),
            ("SHC", "Prof. Swapnil Chaudhari"),
            ("DDP", "Prof. Dr. Dnyaneshwari Patil"),
            ("ARP", "Prof. Archana Pakhare"),
        ]
        for teacher_id, teacher_name in teacher_seed:
            cursor.execute(
                "INSERT IGNORE INTO teachers (teacher_id, full_name) VALUES (%s, %s)",
                (teacher_id, teacher_name)
            )

        # Correct the inventory model: library tables are single-user; reading-room tables seat 4 or 8.
        cursor.execute("UPDATE resources SET capacity=1 WHERE resource_type='Library Table'")
        cursor.execute("SELECT resource_id FROM resources WHERE resource_type='Reading Room Seat' ORDER BY resource_id")
        room_rows = cursor.fetchall()
        for index, (resource_id,) in enumerate(room_rows, start=1):
            capacity = 8 if index in (5, 10, 15, 20) else 4
            cursor.execute("UPDATE resources SET resource_name=%s, capacity=%s WHERE resource_id=%s",
                           (f'Table {index}', capacity, resource_id))
        # Seed a small, repeatable prototype dataset so the screens are usable on first launch.
        # Existing records are kept; only missing demo records are inserted.
        resource_seed = []
        for i in range(1, 26):
            resource_seed.append((f"Table {i}", "Library Table", "Library", 1))
        for i in range(1, 26):
            resource_seed.append((f"Table {i}", "Reading Room Seat", "Reading Room - 3rd Floor", 8 if i in (5, 10, 15, 20) else 4))
        lab_rooms = ["N509", "N510", "S407", "S516", "S618", "S506", "S408"]
        for room in lab_rooms:
            for i in range(1, 37):
                resource_seed.append((f"{room}{i:03d}", "Lab Computer", room, 1))
        for resource_name, resource_type, location, capacity in resource_seed:
            cursor.execute(
                "SELECT resource_id FROM resources WHERE resource_name=%s AND resource_type=%s AND location=%s LIMIT 1",
                (resource_name, resource_type, location)
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO resources (resource_name, resource_type, location, status, capacity) VALUES (%s,%s,%s,'Available',%s)",
                    (resource_name, resource_type, location, capacity)
                )

        # Ensure 72 synthetic SY-08 demo students exist even if an earlier
        # version inserted only a few records. These are NOT real student data.
        for roll in range(1, 73):
            enrollment = f"ADT25SOCB{9000 + roll:04d}"
            phone = f"91{9000000000 + roll}"
            cursor.execute("SELECT enrollment_no FROM students WHERE enrollment_no=%s", (enrollment,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO students (enrollment_no, full_name, class_name, phone_number) VALUES (%s,%s,%s,%s)",
                    (enrollment, f"Demo Student {roll:02d}", "SY-08", phone)
                )

        timetable_seed = [
            ("SY-08", "Monday", "13:40:00", "15:30:00", "DMSL", "Batch A", "S407"),
            ("SY-08", "Monday", "13:40:00", "15:30:00", "DSL", "Batch B", "S516"),
            ("SY-08", "Tuesday", "13:40:00", "15:30:00", "PAI Lab", "Batch A", "S618"),
            ("SY-08", "Tuesday", "13:40:00", "15:30:00", "DMSL", "Batch B", "S407"),
            ("SY-08", "Thursday", "10:50:00", "11:45:00", "DMS Lab", "W1", "N509"),
            ("SY-08", "Thursday", "10:50:00", "11:45:00", "DMS Lab", "W2", "N509"),
            ("SY-08", "Thursday", "10:50:00", "11:45:00", "MFC-III Lab", "W3", "N509"),
            ("SY-08", "Friday", "10:50:00", "11:45:00", "APP Lab", "Batch A", "S506"),
            ("SY-08", "Friday", "10:50:00", "11:45:00", "DSA Lab", "Batch B", "S408"),
        ]
        for entry in timetable_seed:
            cursor.execute(
                "SELECT timetable_id FROM class_timetable WHERE class_name=%s AND day_name=%s AND start_time=%s AND end_time=%s AND subject_name=%s AND batch_name=%s AND room_no=%s LIMIT 1",
                entry
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO class_timetable (class_name,day_name,start_time,end_time,subject_name,batch_name,room_no,is_lab) VALUES (%s,%s,%s,%s,%s,%s,%s,1)",
                    entry
                )

        connection.commit()
        cursor.close()
        return True
    except Exception as error:
        connection.rollback()
        messagebox.showerror("Database Setup Error", str(error))
        return False
    finally:
        connection.close()


def styled_button(parent, text, command, color=BLUE):
    return tk.Button(
        parent, text=text, command=command, bg=color, fg="white",
        activebackground=color, activeforeground="white",
        font=("Segoe UI", 10, "bold"), relief="flat",
        padx=14, pady=8, cursor="hand2"
    )


def make_header(window, title, role):
    header = tk.Frame(window, bg=NAVY, padx=20, pady=16)
    header.pack(fill="x")
    # Every child page has a consistent Back button; closing this Toplevel
    # returns to its parent page without ending the application.
    back_button = tk.Button(
        header, text="← Back", command=window.destroy,
        bg="#334155", fg="white", activebackground="#475569",
        activeforeground="white", relief="flat", padx=14, pady=7,
        font=("Segoe UI", 10, "bold"), cursor="hand2"
    )
    back_button.pack(side="right", padx=(12, 0))
    tk.Label(header, text=title.upper(), font=("Segoe UI", 19, "bold"),
             bg=NAVY, fg="white").pack(anchor="w")
    tk.Label(header, text=f"Logged in as: {role}", font=("Segoe UI", 10),
             bg=NAVY, fg="#bfdbfe").pack(anchor="w", pady=(4, 0))


def open_lab_management(parent, role):
    """Show a compact list of labs first; select a lab to inspect its computers."""
    window = tk.Toplevel(parent)
    window.title("Computer Lab Management")
    window.geometry("1000x600")
    window.configure(bg=BG)
    make_header(window, "Computer Lab Management", role)
    content = tk.Frame(window, bg=BG, padx=20, pady=20)
    content.pack(fill="both", expand=True)

    view_state = {"mode": "labs", "location": None}
    heading = tk.Label(content, text="Computer Labs", font=("Segoe UI", 16, "bold"), bg=BG, fg=NAVY)
    heading.pack(anchor="w", pady=(0, 12))
    info = tk.Label(content, text="Select a lab to view its computers and status.", bg=BG, fg="#475569")
    info.pack(anchor="w", pady=(0, 8))

    columns = ("lab", "count", "available", "maintenance")
    tree = ttk.Treeview(content, columns=columns, show="headings", height=16)
    for col, text, width in [("lab", "Lab / Room Number", 300), ("count", "Total Computers", 160),
                             ("available", "Available", 160), ("maintenance", "Under Maintenance", 190)]:
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="center")
    scroll = ttk.Scrollbar(content, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="left", fill="y")

    def load_labs():
        view_state["mode"] = "labs"
        view_state["location"] = None
        heading.config(text="Computer Labs")
        info.config(text="Select a lab and click 'Open Selected Lab' to view its computers.")
        for col, text, width in [("lab", "Lab / Room Number", 300), ("count", "Total Computers", 160),
                                 ("available", "Available", 160), ("maintenance", "Under Maintenance", 190)]:
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="center")
        tree.delete(*tree.get_children())
        connection = db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor()
            cursor.execute("""SELECT location, COUNT(*),
                SUM(CASE WHEN status='Available' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status='Maintenance' THEN 1 ELSE 0 END)
                FROM resources WHERE resource_type='Lab Computer'
                GROUP BY location ORDER BY location""")
            for row in cursor.fetchall():
                tree.insert("", "end", values=(row[0], row[1], row[2] or 0, row[3] or 0))
            cursor.close()
        except Exception as error:
            messagebox.showerror("Error", str(error), parent=window)
        finally:
            connection.close()

    def open_selected_lab():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select Lab", "Select a lab room first.", parent=window)
            return
        if view_state["mode"] == "labs":
            room = str(tree.item(selected[0], "values")[0])
            view_state["mode"] = "computers"
            view_state["location"] = room
            heading.config(text=f"Lab {room} — Computers")
            info.config(text="Computer IDs are listed only inside the selected lab. Select a computer to update its status.")
            for col, text, width in [("id", "ID", 70), ("name", "Computer Name", 220),
                                     ("location", "Lab / Location", 220), ("status", "Status", 160)]:
                tree.heading(col, text=text)
                tree.column(col, width=width, anchor="center" if col in ("id", "status") else "w")
            tree.delete(*tree.get_children())
            connection = db_connection()
            if not connection:
                return
            try:
                cursor = connection.cursor()
                cursor.execute("""SELECT resource_id, resource_name, location, status FROM resources
                                  WHERE resource_type='Lab Computer' AND location=%s ORDER BY resource_name""", (room,))
                for row in cursor.fetchall():
                    tree.insert("", "end", values=row)
                cursor.close()
            except Exception as error:
                messagebox.showerror("Error", str(error), parent=window)
            finally:
                connection.close()
        else:
            update_status()

    def add_computer():
        if role not in ("Admin", "Staff"):
            messagebox.showwarning("Permission Denied", "Only Admin and Staff can add computers.", parent=window)
            return
        form = tk.Toplevel(window)
        form.title("Add Lab Computer")
        form.geometry("390x270")
        form.configure(bg="white")
        form.transient(window)
        form.grab_set()
        tk.Label(form, text="Add Lab Computer", font=("Segoe UI", 15, "bold"), bg="white", fg=NAVY).pack(pady=16)
        tk.Label(form, text="Computer Name", bg="white").pack()
        name_entry = tk.Entry(form, width=32, font=("Segoe UI", 11)); name_entry.pack(pady=(4, 12))
        tk.Label(form, text="Lab / Location", bg="white").pack()
        location_entry = tk.Entry(form, width=32, font=("Segoe UI", 11)); location_entry.pack(pady=(4, 14))
        def save():
            name, location = name_entry.get().strip().upper(), location_entry.get().strip().upper()
            if not name or not location:
                messagebox.showwarning("Missing Details", "Enter both computer name and location.", parent=form); return
            connection = db_connection()
            if not connection: return
            try:
                cursor = connection.cursor()
                cursor.execute("INSERT INTO resources (resource_name, resource_type, location, status) VALUES (%s, 'Lab Computer', %s, 'Available')", (name, location))
                connection.commit(); cursor.close(); form.destroy(); load_labs()
            except Exception as error:
                connection.rollback(); messagebox.showerror("Error", str(error), parent=form)
            finally: connection.close()
        styled_button(form, "Save Computer", save).pack()

    def add_lab_generate_computers():
        if role != "Admin":
            messagebox.showwarning("Permission Denied", "Only Admin can create a lab and generate its computers.", parent=window); return
        form = tk.Toplevel(window); form.title("Create Lab and Generate Computers"); form.geometry("430x330")
        form.configure(bg="white"); form.transient(window); form.grab_set()
        tk.Label(form, text="Create Lab / Generate Computers", font=("Segoe UI", 14, "bold"), bg="white", fg=NAVY).pack(pady=(18, 14))
        tk.Label(form, text="Lab / Room Number (e.g. S516)", bg="white").pack(anchor="w", padx=32)
        room_entry = tk.Entry(form, width=30, font=("Segoe UI", 11)); room_entry.pack(padx=32, fill="x", pady=(4, 12))
        tk.Label(form, text="Total computers required (e.g. 36)", bg="white").pack(anchor="w", padx=32)
        count_entry = tk.Entry(form, width=30, font=("Segoe UI", 11)); count_entry.insert(0, "36"); count_entry.pack(padx=32, fill="x", pady=(4, 12))
        tk.Label(form, text="Names will be generated as S516001, S516002, ...", bg="white", fg="#475569", wraplength=360).pack(pady=(0, 14))
        def generate():
            room = room_entry.get().strip().upper(); count_text = count_entry.get().strip()
            if not room or not room.replace("-", "").isalnum():
                messagebox.showwarning("Invalid Lab Number", "Enter a valid room code, e.g. S516.", parent=form); return
            try:
                desired_count = int(count_text)
                if desired_count < 1 or desired_count > 999: raise ValueError
            except ValueError:
                messagebox.showwarning("Invalid Count", "Enter a number from 1 to 999.", parent=form); return
            connection = db_connection()
            if not connection: return
            try:
                cursor = connection.cursor()
                cursor.execute("SELECT resource_name FROM resources WHERE resource_type='Lab Computer' AND location=%s", (room,))
                existing = {str(row[0]).strip().upper() for row in cursor.fetchall()}; created = 0
                for number in range(1, desired_count + 1):
                    computer_name = f"{room}{number:03d}"
                    if computer_name not in existing:
                        cursor.execute("INSERT INTO resources (resource_name, resource_type, location, status, capacity) VALUES (%s, 'Lab Computer', %s, 'Available', 1)", (computer_name, room)); created += 1
                connection.commit(); cursor.close(); form.destroy(); load_labs()
                messagebox.showinfo("Lab Created", f"Lab {room} has computers up to {room}{desired_count:03d}.\nNew computers added: {created}.", parent=window)
            except Exception as error:
                connection.rollback(); messagebox.showerror("Error Creating Lab", str(error), parent=form)
            finally: connection.close()
        styled_button(form, "Generate Computers", generate).pack(pady=(0, 16))

    def update_status():
        if role not in ("Admin", "Staff"):
            messagebox.showwarning("Permission Denied", "Students cannot change computer status.", parent=window)
            return
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select Computer", "Open a lab, then click one computer row first.", parent=window)
            return

        # Do not trust the displayed row shape alone: the lab summary has a similar table.
        values = tree.item(selected[0], "values")
        if view_state.get("mode") != "computers" or not view_state.get("location"):
            messagebox.showwarning(
                "Open a Lab First",
                "You have selected a lab summary row, not an individual computer.\n\n"
                "Select the room (for example S516), click 'Open Selected Lab / Computer', "
                "then select a computer such as S516001 and click Update Status.",
                parent=window
            )
            return
        if len(values) < 4:
            messagebox.showwarning("Select Computer", "Select an individual computer row.", parent=window)
            return

        # Fetch by resource_id to ensure we update the exact selected computer.
        try:
            resource_id = int(values[0])
        except (TypeError, ValueError):
            messagebox.showwarning("Select Computer", "This is not a computer record. Open the lab and select a computer.", parent=window)
            return
        connection = db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT resource_id, resource_name, location, status FROM resources WHERE resource_id=%s AND resource_type='Lab Computer'", (resource_id,))
            computer = cursor.fetchone()
            cursor.close()
        except Exception as error:
            messagebox.showerror("Error", str(error), parent=window)
            connection.close()
            return
        connection.close()
        if not computer:
            messagebox.showwarning("Select Computer", "The selected row is not a computer record. Refresh the lab list and try again.", parent=window)
            return

        form = tk.Toplevel(window)
        form.title("Update Computer Status")
        form.geometry("370x220")
        form.configure(bg="white")
        form.transient(window)
        form.grab_set()
        tk.Label(form, text=f"Computer: {computer[1]}", font=("Segoe UI", 12, "bold"), bg="white", fg=NAVY).pack(pady=(20, 8))
        tk.Label(form, text=f"Lab: {computer[2]}", bg="white", fg="#475569").pack()
        status_box = ttk.Combobox(form, values=STATUSES, state="readonly", width=24)
        status_box.set(computer[3])
        status_box.pack(pady=12)

        def save():
            new_status = status_box.get().strip()
            if new_status not in STATUSES:
                messagebox.showwarning("Invalid Status", "Select a valid status.", parent=form)
                return
            conn = db_connection()
            if not conn:
                return
            try:
                cur = conn.cursor()
                cur.execute("UPDATE resources SET status=%s WHERE resource_id=%s AND resource_type='Lab Computer'", (new_status, computer[0]))
                conn.commit()
                cur.close()
                form.destroy()
                # Refresh the current room, preserving the computer-detail view.
                room = view_state["location"]
                tree.delete(*tree.get_children())
                cur = conn.cursor()
                cur.execute("SELECT resource_id, resource_name, location, status FROM resources WHERE resource_type='Lab Computer' AND location=%s ORDER BY resource_name", (room,))
                for item in cur.fetchall():
                    tree.insert("", "end", values=item)
                cur.close()
            except Exception as error:
                conn.rollback()
                messagebox.showerror("Error", str(error), parent=form)
            finally:
                conn.close()
        styled_button(form, "Save Status", save).pack(pady=(0, 12))

    def delete_computer():
        if role != "Admin":
            messagebox.showwarning("Permission Denied", "Only Admin can delete computers.", parent=window); return
        selected = tree.selection()
        if not selected or view_state["mode"] != "computers":
            messagebox.showwarning("Select Computer", "Open a lab and select a computer first.", parent=window); return
        row = tree.item(selected[0], "values")
        if not messagebox.askyesno("Confirm Deletion", f"Delete {row[1]}?", parent=window): return
        connection = db_connection()
        if not connection: return
        try:
            cursor = connection.cursor(); cursor.execute("DELETE FROM resources WHERE resource_id=%s AND resource_type='Lab Computer'", (row[0],)); connection.commit(); cursor.close()
            load_labs()
        except Exception as error:
            connection.rollback(); messagebox.showerror("Cannot Delete", str(error), parent=window)
        finally: connection.close()

    buttons = tk.Frame(window, bg=BG, padx=20, pady=12); buttons.pack(fill="x")

    def go_back_to_labs():
        # Return from the selected lab's computer list to the lab summary.
        load_labs()

    back_button = tk.Button(buttons, text="← Back to Labs", command=go_back_to_labs,
                            padx=14, pady=8, state="disabled")
    back_button.pack(side="left", padx=4)

    def sync_back_button(*_args):
        back_button.config(state="normal" if view_state["mode"] == "computers" else "disabled")

    # Keep the back button state in sync whenever the view changes.
    _original_load_labs = load_labs
    def load_labs_with_back_state():
        _original_load_labs()
        sync_back_button()
    load_labs = load_labs_with_back_state

    _original_open_selected_lab = open_selected_lab
    def open_selected_lab_with_back_state():
        _original_open_selected_lab()
        sync_back_button()
    open_selected_lab = open_selected_lab_with_back_state

    tk.Button(buttons, text="Refresh", command=lambda: load_labs() if view_state["mode"] == "labs" else open_selected_lab(),
              padx=14, pady=8).pack(side="left", padx=4)
    styled_button(buttons, "Open Selected Lab / Computer", open_selected_lab).pack(side="left", padx=4)
    if role in ("Admin", "Staff"): styled_button(buttons, "Add Computer", add_computer).pack(side="left", padx=4)
    if role == "Admin":
        styled_button(buttons, "Create Lab / Generate Computers", add_lab_generate_computers).pack(side="left", padx=4)
        tk.Button(buttons, text="Update Status", command=update_status, padx=14, pady=8).pack(side="left", padx=4)
        styled_button(buttons, "Delete Computer", delete_computer, RED).pack(side="left", padx=4)
    # Double-click a lab row to open its computers directly.
    def on_tree_double_click(event):
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
        tree.selection_set(item_id)
        if view_state["mode"] == "labs":
            open_selected_lab()
        # In computer view, double-click opens the status editor for that computer.
        elif view_state["mode"] == "computers":
            update_status()

    tree.bind("<Double-1>", on_tree_double_click)

    # Refresh the current view every 5 seconds so status changes made by other staff
    # or sessions are reflected without requiring a manual refresh.
    def refresh_current_view():
        if not window.winfo_exists():
            return
        current_mode = view_state["mode"]
        current_room = view_state["location"]
        if current_mode == "labs":
            load_labs()
        elif current_room:
            connection = db_connection()
            if connection:
                try:
                    cursor = connection.cursor()
                    cursor.execute("""SELECT resource_id, resource_name, location, status FROM resources
                                      WHERE resource_type='Lab Computer' AND location=%s ORDER BY resource_name""", (current_room,))
                    rows = cursor.fetchall()
                    cursor.close()
                    selected_values = tree.item(tree.selection()[0], "values") if tree.selection() else None
                    tree.delete(*tree.get_children())
                    selected_item = None
                    for item in rows:
                        iid = tree.insert("", "end", values=item)
                        if selected_values and str(item[0]) == str(selected_values[0]):
                            selected_item = iid
                    if selected_item:
                        tree.selection_set(selected_item)
                except Exception as error:
                    print("Auto-refresh error:", error)
                finally:
                    connection.close()
        window.after(5000, refresh_current_view)

    load_labs()
    window.after(5000, refresh_current_view)



def open_resource_management(parent, role, resource_type, title, noun, student_enrollment=None):
    window = tk.Toplevel(parent)
    window.title(title)
    window.geometry("1120x650")
    window.configure(bg=BG)
    make_header(window, title, role)
    content = tk.Frame(window, bg=BG, padx=20, pady=18)
    content.pack(fill="both", expand=True)
    tk.Label(content, text=f"{noun} Inventory and Live Usage", font=("Segoe UI", 16, "bold"), bg=BG, fg=NAVY).pack(anchor="w", pady=(0, 10))

    columns = ("id", "name", "capacity", "in_use", "available", "status", "booked_slots", "last_user", "last_end")
    tree = ttk.Treeview(content, columns=columns, show="headings", height=13)
    headings = {"id": "ID", "name": noun, "capacity": "Capacity", "in_use": "In Use", "available": "Available", "status": "Status", "booked_slots": "Booked Time Slots (Today)", "last_user": "Last Used By", "last_end": "Last End Time"}
    widths = {"id": 55, "name": 120, "capacity": 70, "in_use": 65, "available": 75, "status": 100, "booked_slots": 230, "last_user": 190, "last_end": 150}
    for col in columns:
        tree.heading(col, text=headings[col])
        tree.column(col, width=widths[col], anchor="center" if col in ("id", "capacity", "in_use", "available", "status") else "w")
    scroll = ttk.Scrollbar(content, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="left", fill="y")

    def load():
        tree.delete(*tree.get_children())
        connection = db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT r.resource_id, r.resource_name, r.capacity, r.status,
                       (SELECT COUNT(*) FROM usage_sessions us
                        WHERE us.resource_id=r.resource_id AND us.session_status='Active') AS active_count,
                       (SELECT CONCAT(s.full_name, ' (', s.enrollment_no, ')')
                        FROM usage_sessions us JOIN students s ON s.enrollment_no=us.enrollment_no
                        WHERE us.resource_id=r.resource_id AND us.session_status='Completed'
                        ORDER BY us.end_time DESC, us.session_id DESC LIMIT 1) AS last_user,
                       (SELECT us.end_time FROM usage_sessions us
                        WHERE us.resource_id=r.resource_id AND us.session_status='Completed'
                        ORDER BY us.end_time DESC, us.session_id DESC LIMIT 1) AS last_end
                FROM resources r
                WHERE r.resource_type=%s
                ORDER BY r.resource_id
            """, (resource_type,))
            rows = cursor.fetchall()
            for row in rows:
                rid, name, capacity, status, active_count, last_user, last_end = row
                available = max(int(capacity) - int(active_count), 0)
                display_status = "Maintenance" if status == "Maintenance" else ("Occupied" if available == 0 else ("In Use" if active_count else "Available"))
                booked_text = "—"
                if resource_type == "Reading Room Seat":
                    cursor.execute("""SELECT seat_number, TIME_FORMAT(start_time, '%h:%i %p'), TIME_FORMAT(end_time, '%h:%i %p')
                                     FROM reading_room_bookings
                                     WHERE resource_id=%s AND status='Booked' AND DATE(start_time)=CURDATE()
                                     ORDER BY start_time, seat_number""", (rid,))
                    booking_rows = cursor.fetchall()
                    booked_text = " | ".join([f"Seat {seat}: Booked {a}–{b}" for seat, a, b in booking_rows]) or "—"
                tree.insert("", "end", values=(rid, name, capacity, active_count, available, display_status, booked_text, last_user or "—", str(last_end) if last_end else "—"))
            cursor.close()
        except Exception as error:
            messagebox.showerror("Error loading inventory", str(error), parent=window)
        finally:
            connection.close()

    def selected_resource():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select Resource", f"Select a {noun.lower()} first.", parent=window)
            return None
        return tree.item(selected[0], "values")

    def start_session():
        if role not in ("Admin", "Staff", "Student"):
            messagebox.showwarning("Permission Denied", "You cannot start a usage session.", parent=window)
            return
        row = selected_resource()
        if not row:
            return
        resource_id, resource_name = int(row[0]), row[1]
        if row[5] == "Maintenance":
            messagebox.showwarning("Unavailable", "This resource is marked for maintenance.", parent=window)
            return
        if role == "Student":
            connection = db_connection()
            if not connection:
                return
            try:
                cursor = connection.cursor()
                cursor.execute("SELECT enrollment_no, full_name, class_name FROM students WHERE enrollment_no=%s", (student_enrollment,))
                students = cursor.fetchall()
                cursor.close()
            except Exception as error:
                messagebox.showerror("Error", str(error), parent=window)
                connection.close()
                return
            connection.close()
        else:
            connection = db_connection()
            if not connection:
                return
            try:
                cursor = connection.cursor()
                cursor.execute("SELECT enrollment_no, full_name, class_name FROM students ORDER BY full_name")
                students = cursor.fetchall()
                cursor.close()
            except Exception as error:
                messagebox.showerror("Error", str(error), parent=window)
                connection.close()
                return
            connection.close()
        if not students:
            messagebox.showinfo("No Students", "Register the student with a phone number before starting a session.", parent=window)
            return

        form = tk.Toplevel(window)
        form.title("Start Usage Session")
        form.geometry("460x350")
        form.configure(bg="white")
        form.transient(window)
        form.grab_set()
        tk.Label(form, text=f"Start Session — {resource_name}", font=("Segoe UI", 15, "bold"), bg="white", fg=NAVY).pack(pady=(18, 12))
        student_index = 0
        if role == "Student":
            tk.Label(form, text=f"Student: {students[0][0]} — {students[0][1]}", bg="white").pack(pady=(4, 12))
        else:
            tk.Label(form, text="Student (Enrollment No. — Name — Class)", bg="white").pack()
            student_labels = [f"{st[0]} — {st[1]} — {st[2]}" for st in students]
            student_box = ttk.Combobox(form, values=student_labels, state="readonly", width=48)
            student_box.pack(pady=(5, 12))
            student_box.current(0)
        capacity = int(row[2])
        tk.Label(form, text="Seat Number", bg="white").pack()
        seat_box = ttk.Combobox(form, values=[str(i) for i in range(1, capacity + 1)], state="readonly", width=12)
        seat_box.pack(pady=(5, 14))
        seat_box.current(0)
        if resource_type == "Reading Room Seat":
            # Reading-room tables have 4 seats, or 8 seats for the large tables.
            pass

        def save_session():
            # Students always start a session for their own enrollment number.
            # Admin/Staff choose a student from the dropdown.
            if role == "Student":
                enrollment_no = students[0][0]
            else:
                selected_index = student_box.current()
                if selected_index < 0:
                    messagebox.showwarning("Select Student", "Choose a student.", parent=form)
                    return
                enrollment_no = students[selected_index][0]

            seat_value = seat_box.get().strip()
            if not seat_value:
                messagebox.showwarning("Select Seat", "Choose a seat number.", parent=form)
                return
            seat_number = int(seat_value)
            connection2 = db_connection()
            if not connection2:
                return
            try:
                cursor2 = connection2.cursor()
                cursor2.execute("SELECT status, capacity FROM resources WHERE resource_id=%s", (resource_id,))
                current_resource = cursor2.fetchone()
                if not current_resource or current_resource[0] == "Maintenance":
                    raise ValueError("This resource is unavailable or under maintenance.")
                cursor2.execute("""SELECT COUNT(*) FROM usage_sessions
                                   WHERE resource_id=%s AND seat_number=%s AND session_status='Active'""", (resource_id, seat_number))
                if cursor2.fetchone()[0] > 0:
                    raise ValueError(f"Seat {seat_number} is already occupied.")
                cursor2.execute("""SELECT COUNT(*) FROM usage_sessions
                                   WHERE resource_id=%s AND enrollment_no=%s AND session_status='Active'""", (resource_id, enrollment_no))
                if cursor2.fetchone()[0] > 0:
                    raise ValueError("This student already has an active session at this resource.")
                cursor2.execute("""INSERT INTO usage_sessions
                                   (resource_id, enrollment_no, start_time, seat_number, session_status)
                                   VALUES (%s, %s, CURRENT_TIMESTAMP, %s, 'Active')""", (resource_id, enrollment_no, seat_number))
                cursor2.execute("UPDATE resources SET status='Occupied' WHERE resource_id=%s AND resource_type=%s", (resource_id, resource_type))
                connection2.commit()
                cursor2.close()
                form.destroy()
                load()
                messagebox.showinfo("Session Started", f"Session started for {enrollment_no} at {resource_name}, seat {seat_number}.", parent=window)
            except Exception as error:
                connection2.rollback()
                messagebox.showerror("Could Not Start Session", str(error), parent=form)
            finally:
                connection2.close()
        styled_button(form, "Start Session", save_session).pack(pady=4)

    def book_reading_room_slot():
        if role != "Student" or not student_enrollment:
            messagebox.showinfo("Student Booking", "Sign in as a student to book a Reading Room slot.", parent=window)
            return
        row = selected_resource()
        if not row:
            return
        resource_id, resource_name = int(row[0]), row[1]
        if resource_type != "Reading Room Seat":
            messagebox.showinfo("Not a Reading Room Table", "Time-slot booking is available for Reading Room tables.", parent=window)
            return
        if row[5] == "Maintenance":
            messagebox.showwarning("Unavailable", "This table is marked for maintenance.", parent=window)
            return

        form = tk.Toplevel(window)
        form.title("Book Reading Room Slot")
        form.geometry("430x470")
        form.configure(bg="white")
        form.transient(window)
        form.grab_set()
        tk.Label(form, text=f"Book a seat at {resource_name}", font=("Segoe UI", 15, "bold"), bg="white", fg=NAVY).pack(pady=(18, 8))
        tk.Label(form, text=f"Student: {student_enrollment}", bg="white").pack(pady=(0, 12))
        tk.Label(form, text="Seat number", bg="white").pack()
        seat_booking_box = ttk.Combobox(form, values=[str(i) for i in range(1, int(row[2]) + 1)], state="readonly", width=18)
        seat_booking_box.current(0)
        seat_booking_box.pack(pady=(4, 10))
        tk.Label(form, text="Booking date (YYYY-MM-DD)", bg="white").pack()
        date_entry = tk.Entry(form, width=20, justify="center")
        date_entry.insert(0, date.today().isoformat())
        date_entry.pack(pady=(4, 12))
        tk.Label(form, text="Start time", bg="white").pack()
        times = []
        current = datetime.strptime("09:20", "%H:%M")
        last = datetime.strptime("17:00", "%H:%M")
        # Ten-minute choices allow 30-minute minimum bookings from 9:20 AM.
        while current <= last:
            times.append(current.strftime("%I:%M %p"))
            current += timedelta(minutes=10)
        start_box = ttk.Combobox(form, values=times[:-1], state="readonly", width=18)
        start_box.current(0)
        start_box.pack(pady=(4, 10))
        tk.Label(form, text="End time", bg="white").pack()
        end_box = ttk.Combobox(form, values=times[1:], state="readonly", width=18)
        end_box.current(2)
        end_box.pack(pady=(4, 14))
        tk.Label(form, text="Allowed hours: 9:20 AM–5:00 PM", bg="white", fg="#475569").pack(pady=(0, 10))

        def save_booking():
            try:
                chosen_date = datetime.strptime(date_entry.get().strip(), "%Y-%m-%d").date()
                start_time = datetime.strptime(start_box.get(), "%I:%M %p").time()
                end_time = datetime.strptime(end_box.get(), "%I:%M %p").time()
                if chosen_date < date.today():
                    raise ValueError("Choose today or a future date.")
                start_dt = datetime.combine(chosen_date, start_time)
                end_dt = datetime.combine(chosen_date, end_time)
                if end_dt <= start_dt:
                    raise ValueError("End time must be later than start time.")
                if (end_dt - start_dt).total_seconds() < 30 * 60:
                    raise ValueError("Minimum booking duration is 30 minutes.")
                if start_time < datetime.strptime("09:20 AM", "%I:%M %p").time() or end_time > datetime.strptime("05:00 PM", "%I:%M %p").time():
                    raise ValueError("Booking must be between 9:20 AM and 5:00 PM.")
            except ValueError as error:
                messagebox.showwarning("Invalid Slot", str(error) or "Enter a valid date and time.", parent=form)
                return

            connection2 = db_connection()
            if not connection2:
                return
            try:
                cursor2 = connection2.cursor()
                cursor2.execute("SELECT status FROM resources WHERE resource_id=%s AND resource_type='Reading Room Seat'", (resource_id,))
                resource = cursor2.fetchone()
                if not resource or resource[0] == "Maintenance":
                    raise ValueError("This seat is unavailable or under maintenance.")
                seat_number = int(seat_booking_box.get())
                # Only the same seat at the same table conflicts; other seats remain bookable.
                cursor2.execute("""SELECT COUNT(*) FROM reading_room_bookings
                                   WHERE resource_id=%s AND seat_number=%s AND status='Booked'
                                     AND start_time < %s AND end_time > %s""", (resource_id, seat_number, end_dt, start_dt))
                if cursor2.fetchone()[0]:
                    raise ValueError(f"Seat {seat_number} at this table is already booked during that time. Choose another seat or time.")
                cursor2.execute("""SELECT COUNT(*) FROM reading_room_bookings
                                   WHERE enrollment_no=%s AND status='Booked'
                                     AND start_time < %s AND end_time > %s""", (student_enrollment, end_dt, start_dt))
                if cursor2.fetchone()[0]:
                    raise ValueError("You already have a Reading Room booking that overlaps this time.")
                cursor2.execute("""INSERT INTO reading_room_bookings
                                   (enrollment_no, resource_id, seat_number, start_time, end_time, status)
                                   VALUES (%s, %s, %s, %s, %s, 'Booked')""", (student_enrollment, resource_id, seat_number, start_dt, end_dt))
                connection2.commit()
                cursor2.close()
                form.destroy()
                load()
                messagebox.showinfo("Booking Confirmed", f"{resource_name}, Seat {seat_number} is booked for {chosen_date.isoformat()} from {start_dt.strftime('%I:%M %p')} to {end_dt.strftime('%I:%M %p')}.", parent=window)
            except Exception as error:
                connection2.rollback()
                messagebox.showerror("Could Not Book Slot", str(error), parent=form)
            finally:
                connection2.close()
        styled_button(form, "Confirm Booking", save_booking).pack(pady=4)

    def end_session():
        if role not in ("Admin", "Staff", "Student"):
            messagebox.showwarning("Permission Denied", "You cannot end a usage session.", parent=window)
            return
        row = selected_resource()
        if not row:
            return
        connection = db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor()
            if role == "Student":
                cursor.execute("""SELECT us.session_id, us.seat_number, us.enrollment_no,
                                          s.full_name, s.class_name, us.start_time
                                   FROM usage_sessions us JOIN students s ON s.enrollment_no=us.enrollment_no
                                   WHERE us.resource_id=%s AND us.session_status='Active' AND us.enrollment_no=%s
                                   ORDER BY us.seat_number""", (row[0], student_enrollment))
            else:
                cursor.execute("""SELECT us.session_id, us.seat_number, us.enrollment_no,
                                          s.full_name, s.class_name, us.start_time
                                   FROM usage_sessions us JOIN students s ON s.enrollment_no=us.enrollment_no
                                   WHERE us.resource_id=%s AND us.session_status='Active'
                                   ORDER BY us.seat_number""", (row[0],))
            active = cursor.fetchall()
            cursor.close()
        except Exception as error:
            messagebox.showerror("Error", str(error), parent=window)
            connection.close()
            return
        connection.close()
        if not active:
            messagebox.showinfo("No Active Sessions", "There are no active sessions for this resource.", parent=window)
            return
        form = tk.Toplevel(window)
        form.title("End Usage Session")
        form.geometry("650x330")
        form.configure(bg="white")
        form.transient(window)
        form.grab_set()
        tk.Label(form, text=f"End Session — {row[1]}", font=("Segoe UI", 15, "bold"), bg="white", fg=NAVY).pack(pady=(16, 10))
        choices = [f"Seat {x[1]} | {x[2]} | {x[3]} | {x[4]} | Started {x[5]}" for x in active]
        choice_box = ttk.Combobox(form, values=choices, state="readonly", width=78)
        choice_box.pack(pady=10)
        choice_box.current(0)

        def finish():
            idx = choice_box.current()
            if idx < 0:
                return
            session_id = active[idx][0]
            connection2 = db_connection()
            if not connection2:
                return
            try:
                cursor2 = connection2.cursor()
                cursor2.execute("""UPDATE usage_sessions
                                   SET end_time=CURRENT_TIMESTAMP,
                                       duration_minutes=TIMESTAMPDIFF(MINUTE, start_time, CURRENT_TIMESTAMP),
                                       session_status='Completed'
                                   WHERE session_id=%s AND session_status='Active'""", (session_id,))
                cursor2.execute("""SELECT COUNT(*) FROM usage_sessions
                                   WHERE resource_id=%s AND session_status='Active'""", (row[0],))
                remaining = cursor2.fetchone()[0]
                cursor2.execute("UPDATE resources SET status=%s WHERE resource_id=%s AND resource_type=%s AND status<>'Maintenance'",
                                ("Occupied" if remaining else "Available", row[0], resource_type))
                connection2.commit()
                cursor2.close()
                form.destroy()
                load()
                messagebox.showinfo("Session Completed", "End time recorded and duration calculated.", parent=window)
            except Exception as error:
                connection2.rollback()
                messagebox.showerror("Error", str(error), parent=form)
            finally:
                connection2.close()
        styled_button(form, "End Selected Session", finish).pack(pady=8)

    def view_active():
        row = selected_resource()
        if not row:
            return
        connection = db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor()
            if role == "Student":
                cursor.execute("""SELECT us.seat_number, us.enrollment_no, s.full_name, s.class_name, us.start_time
                                   FROM usage_sessions us JOIN students s ON s.enrollment_no=us.enrollment_no
                                   WHERE us.resource_id=%s AND us.session_status='Active' AND us.enrollment_no=%s
                                   ORDER BY us.seat_number""", (row[0], student_enrollment))
            else:
                cursor.execute("""SELECT us.seat_number, us.enrollment_no, s.full_name, s.class_name, us.start_time
                                   FROM usage_sessions us JOIN students s ON s.enrollment_no=us.enrollment_no
                                   WHERE us.resource_id=%s AND us.session_status='Active'
                                   ORDER BY us.seat_number""", (row[0],))
            rows = cursor.fetchall()
            cursor.close()
        except Exception as error:
            messagebox.showerror("Error", str(error), parent=window)
            return
        finally:
            connection.close()
        details = "\n".join([f"Seat {r[0]} | {r[1]} | {r[2]} | {r[3]} | Started: {r[4]}" for r in rows]) or "No active sessions."
        messagebox.showinfo(f"Current Users — {row[1]}", details, parent=window)

    buttons = tk.Frame(window, bg=BG, padx=20, pady=12)
    buttons.pack(fill="x")
    tk.Button(buttons, text="Refresh", command=load, padx=12, pady=8).pack(side="left", padx=4)
    styled_button(buttons, "Start Session", start_session).pack(side="left", padx=4)
    if resource_type == "Reading Room Seat":
        # Keep the slot-selection button visible in Reading Room Management.
        # The handler checks that the logged-in user is a student before booking.
        styled_button(buttons, "Book Time Slot", book_reading_room_slot, color="#0f766e").pack(side="left", padx=4)
    tk.Button(buttons, text="End Session", command=end_session, padx=12, pady=8).pack(side="left", padx=4)
    tk.Button(buttons, text="View Current Users", command=view_active, padx=12, pady=8).pack(side="left", padx=4)
    if role in ("Admin", "Staff"):
        def set_maintenance():
            selected = selected_resource()
            if not selected:
                return
            if int(selected[3]) > 0:
                messagebox.showwarning("Active Session", "End active sessions before changing a resource to maintenance.", parent=window)
                return
            connection2 = db_connection()
            if not connection2:
                return
            try:
                cursor2 = connection2.cursor()
                new_status = "Available" if selected[5] == "Maintenance" else "Maintenance"
                cursor2.execute("UPDATE resources SET status=%s WHERE resource_id=%s AND resource_type=%s", (new_status, selected[0], resource_type))
                connection2.commit()
                cursor2.close()
                load()
            except Exception as error:
                connection2.rollback()
                messagebox.showerror("Error", str(error), parent=window)
            finally:
                connection2.close()
        tk.Button(buttons, text="Toggle Maintenance", command=set_maintenance, padx=12, pady=8).pack(side="left", padx=4)
    load()


def open_library_management(parent, role, student_enrollment=None):
    open_resource_management(parent, role, "Library Table", "Library Management", "Single-User Table", student_enrollment)


def open_reading_room_management(parent, role, student_enrollment=None):
    open_resource_management(parent, role, "Reading Room Seat", "Reading Room Tables Management", "Table (4/8 seats)", student_enrollment)


def open_student_management(parent, role):
    if role not in ("Admin", "Staff"):
        messagebox.showwarning("Permission Denied", "Only Admin or Staff can manage student records.", parent=parent)
        return
    window = tk.Toplevel(parent)
    window.title("Student Registration")
    window.geometry("1000x580")
    window.configure(bg=BG)
    make_header(window, "Student Registration", role)
    content = tk.Frame(window, bg=BG, padx=20, pady=18)
    content.pack(fill="both", expand=True)
    tk.Label(content, text="Registered Students", font=("Segoe UI", 16, "bold"), bg=BG, fg=NAVY).pack(anchor="w", pady=(0, 10))
    columns = ("enrollment", "name", "class", "phone", "created")
    tree = ttk.Treeview(content, columns=columns, show="headings", height=15)
    for col, label, width in [("enrollment", "Enrollment Number", 210), ("name", "Full Name", 220), ("class", "Class / Division", 150), ("phone", "Phone Number", 140), ("created", "Registered At", 170)]:
        tree.heading(col, text=label)
        tree.column(col, width=width)
    tree.pack(fill="both", expand=True)

    def load():
        tree.delete(*tree.get_children())
        connection = db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT enrollment_no, full_name, class_name, phone_number, created_at FROM students ORDER BY full_name")
            for row in cursor.fetchall():
                tree.insert("", "end", values=row)
            cursor.close()
        except Exception as error:
            messagebox.showerror("Error", str(error), parent=window)
        finally:
            connection.close()

    def add_student():
        form = tk.Toplevel(window)
        form.title("Register Student")
        form.geometry("430x430")
        form.configure(bg="white")
        form.transient(window)
        form.grab_set()
        tk.Label(form, text="Register Student", font=("Segoe UI", 16, "bold"), bg="white", fg=NAVY).pack(pady=(18, 12))
        fields = []
        for label in ("Enrollment Number (e.g. ADT25SOCB0376)", "Full Name", "Class / Division", "Registered Phone Number"):
            tk.Label(form, text=label, bg="white").pack(anchor="w", padx=35)
            entry = tk.Entry(form, width=38, font=("Segoe UI", 10))
            entry.pack(padx=35, pady=(3, 10))
            fields.append(entry)

        def save():
            enrollment, name, class_name, phone = [e.get().strip() for e in fields]
            enrollment = enrollment.upper()
            if not enrollment or not name or not class_name or not phone:
                messagebox.showwarning("Missing Details", "Fill in all fields.", parent=form)
                return
            if not ENROLLMENT_PATTERN.fullmatch(enrollment):
                messagebox.showwarning("Invalid Enrollment Number", "Use the format ADT + 2 admission-year digits + 4-letter school code + 4 digits. Example: ADT25SOCB0376", parent=form)
                return
            connection = db_connection()
            if not connection:
                return
            try:
                cursor = connection.cursor()
                cursor.execute("INSERT INTO students (enrollment_no, full_name, class_name, phone_number) VALUES (%s, %s, %s, %s)", (enrollment, name, class_name, phone))
                connection.commit()
                cursor.close()
                form.destroy()
                load()
                messagebox.showinfo("Success", "Student registered successfully.", parent=window)
            except Exception as error:
                connection.rollback()
                messagebox.showerror("Could Not Register", str(error), parent=form)
            finally:
                connection.close()
        styled_button(form, "Save Student", save).pack(pady=6)

    buttons = tk.Frame(window, bg=BG, padx=20, pady=12)
    buttons.pack(fill="x")
    tk.Button(buttons, text="Refresh", command=load, padx=14, pady=8).pack(side="left", padx=4)
    styled_button(buttons, "Register Student", add_student).pack(side="left", padx=4)
    load()


def open_usage_history(parent, role, student_enrollment=None):
    window = tk.Toplevel(parent)
    window.title("Usage History")
    window.geometry("1250x600")
    window.configure(bg=BG)
    make_header(window, "Usage History", role)
    content = tk.Frame(window, bg=BG, padx=20, pady=18)
    content.pack(fill="both", expand=True)
    tk.Label(content, text="Completed and Active Sessions", font=("Segoe UI", 16, "bold"), bg=BG, fg=NAVY).pack(anchor="w", pady=(0, 10))
    columns = ("resource_type", "resource", "seat", "enrollment", "name", "class", "start", "end", "duration", "status")
    tree = ttk.Treeview(content, columns=columns, show="headings", height=16)
    labels = {"resource_type":"Resource Type", "resource":"Table / Seat", "seat":"Seat No.", "enrollment":"Enrollment No.", "name":"Student Name", "class":"Class / Division", "start":"Start Time", "end":"End Time", "duration":"Duration (min)", "status":"Session Status"}
    widths = {"resource_type":140, "resource":120, "seat":70, "enrollment":170, "name":160, "class":130, "start":155, "end":155, "duration":100, "status":120}
    for col in columns:
        tree.heading(col, text=labels[col])
        tree.column(col, width=widths[col], anchor="center" if col in ("seat", "duration", "status") else "w")
    scroll = ttk.Scrollbar(content, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="left", fill="y")

    def load():
        tree.delete(*tree.get_children())
        connection = db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor()
            query = """SELECT r.resource_type, r.resource_name, us.seat_number,
                                      us.enrollment_no, s.full_name, s.class_name,
                                      us.start_time, us.end_time,
                                      CASE WHEN us.session_status='Active'
                                           THEN TIMESTAMPDIFF(MINUTE, us.start_time, CURRENT_TIMESTAMP)
                                           ELSE us.duration_minutes END,
                                      us.session_status
                               FROM usage_sessions us
                               JOIN resources r ON r.resource_id=us.resource_id
                               JOIN students s ON s.enrollment_no=us.enrollment_no"""
            if role == "Student":
                cursor.execute(query + " WHERE us.enrollment_no=%s ORDER BY us.start_time DESC", (student_enrollment,))
            else:
                cursor.execute(query + " ORDER BY us.start_time DESC")
            for row in cursor.fetchall():
                tree.insert("", "end", values=tuple("—" if value is None else value for value in row))
            cursor.close()
        except Exception as error:
            messagebox.showerror("Error", str(error), parent=window)
        finally:
            connection.close()
    tk.Button(window, text="Refresh History", command=load, padx=14, pady=8).pack(anchor="w", padx=20, pady=(0, 12))
    load()


def open_lab_batch_allocation(parent, role):
    """Staff/Admin tool: assign one lab computer per student, with temporary replacements."""
    if role not in ("Admin", "Staff"):
        messagebox.showwarning("Access denied", "Only Admin and Staff can manage lab allocations.", parent=parent)
        return
    window = tk.Toplevel(parent)
    window.title("Lab Class and Batch Allocation")
    window.geometry("1120x720")
    window.configure(bg=BG)
    make_header(window, "Lab Class and Batch Allocation", role)
    controls = tk.Frame(window, bg=BG, padx=18, pady=12)
    controls.pack(fill="x")
    tk.Label(controls, text="Class / Division", bg=BG).grid(row=0, column=0, sticky="w")
    class_box = ttk.Combobox(controls, width=18, state="normal")
    class_box.grid(row=1, column=0, padx=(0, 12), pady=5)
    tk.Label(controls, text="Batch", bg=BG).grid(row=0, column=1, sticky="w")
    batch_box = ttk.Combobox(controls, values=("Batch A", "Batch B"), width=14, state="readonly")
    batch_box.current(0)
    batch_box.grid(row=1, column=1, padx=(0, 12), pady=5)
    tk.Label(controls, text="Lab / Location", bg=BG).grid(row=0, column=2, sticky="w")
    lab_box = ttk.Combobox(controls, width=24, state="readonly")
    lab_box.grid(row=1, column=2, padx=(0, 12), pady=5)
    status = tk.Label(controls, text="Select class, batch and lab.", bg=BG, fg=NAVY)
    status.grid(row=1, column=3, sticky="w", padx=8)

    body = tk.Frame(window, bg=BG, padx=18, pady=8)
    body.pack(fill="both", expand=True)
    left = tk.Frame(body, bg=BG)
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))
    right = tk.Frame(body, bg=BG)
    right.pack(side="left", fill="both", expand=True, padx=(8, 0))
    tk.Label(left, text="Students in selected batch", bg=BG, fg=NAVY, font=("Segoe UI", 12, "bold")).pack(anchor="w")
    student_tree = ttk.Treeview(left, columns=("eno", "name", "class", "computer", "type", "state"), show="headings", height=18)
    for c, h, w in [("eno","Enrollment No.",140),("name","Student",145),("class","Class",75),("computer","Computer",100),("type","Type",75),("state","Allocation",85)]:
        student_tree.heading(c,text=h); student_tree.column(c,width=w,anchor="w")
    student_tree.pack(fill="both", expand=True, pady=6)
    tk.Label(right, text="Computers in selected lab", bg=BG, fg=NAVY, font=("Segoe UI", 12, "bold")).pack(anchor="w")
    computer_tree = ttk.Treeview(right, columns=("id", "computer", "location", "status", "allocation"), show="headings", height=18)
    for c, h, w in [("id","ID",45),("computer","Computer",115),("location","Lab / Location",130),("status","Health",90),("allocation","Assignment",100)]:
        computer_tree.heading(c,text=h); computer_tree.column(c,width=w,anchor="w")
    computer_tree.pack(fill="both", expand=True, pady=6)

    def db_rows(sql, args=()):
        conn = db_connection()
        if not conn: return []
        try:
            cur = conn.cursor(); cur.execute(sql,args); rows=cur.fetchall(); cur.close(); return rows
        except Exception as e:
            messagebox.showerror("Database error", str(e), parent=window); return []
        finally: conn.close()

    def refresh_options():
        classes = [r[0] for r in db_rows("SELECT DISTINCT class_name FROM students ORDER BY class_name")]
        labs = [r[0] for r in db_rows("SELECT DISTINCT location FROM resources WHERE resource_type='Lab Computer' ORDER BY location")]
        current_class = class_box.get().strip()
        current_lab = lab_box.get().strip()
        class_box["values"] = classes
        lab_box["values"] = labs
        if not current_class and classes: class_box.set(classes[0])
        if current_lab in labs: lab_box.set(current_lab)
        elif labs: lab_box.current(0)

    def refresh():
        student_tree.delete(*student_tree.get_children()); computer_tree.delete(*computer_tree.get_children())
        class_name = class_box.get().strip(); batch = batch_box.get().strip(); lab = lab_box.get().strip()
        if not class_name or not batch or not lab: return
        all_students = db_rows("SELECT enrollment_no, full_name, class_name FROM students WHERE class_name=%s ORDER BY enrollment_no", (class_name,))
        # Deterministic roll-number order: first 36 in Batch A, next 36 in Batch B.
        selected_students = all_students[:36] if batch == "Batch A" else all_students[36:72]
        if len(all_students) > 72:
            status.config(text=f"{len(all_students)} students found; batches use first 36 / next 36 by enrollment.")
        else:
            status.config(text=f"{len(selected_students)} students in {batch}; expected up to 36.")
        allocations = db_rows("""SELECT a.enrollment_no, r.resource_name, a.allocation_type, a.allocation_status
            FROM lab_allocations a JOIN resources r ON r.resource_id=a.resource_id
            WHERE a.class_name=%s AND a.batch_name=%s AND a.allocation_status IN ('Assigned','Absent')""", (class_name,batch))
        alloc_map = {r[0]: (r[1],r[2],r[3]) for r in allocations}
        for eno,name,cls in selected_students:
            comp,typ,state = alloc_map.get(eno, ("—","—","Not assigned"))
            student_tree.insert("","end",values=(eno,name,cls,comp,typ,state))
        computers = db_rows("""SELECT r.resource_id,r.resource_name,r.location,r.status,
            (SELECT CONCAT(a.class_name,' ',a.batch_name, ' - ', a.allocation_type)
             FROM lab_allocations a WHERE a.resource_id=r.resource_id AND a.allocation_status='Assigned'
             ORDER BY a.allocation_id DESC LIMIT 1)
            FROM resources r WHERE r.resource_type='Lab Computer' AND r.location=%s ORDER BY r.resource_name""", (lab,))
        for rid,name,location,health,assigned in computers:
            computer_tree.insert("","end",values=(rid,name,location,health,assigned or "Free"))

    def selected_student():
        sel=student_tree.selection()
        if not sel:
            messagebox.showwarning("Select student","Select a student first.",parent=window); return None
        return student_tree.item(sel[0],"values")

    def selected_computer():
        sel=computer_tree.selection()
        if not sel:
            messagebox.showwarning("Select computer","Select a computer first.",parent=window); return None
        return computer_tree.item(sel[0],"values")

    def assign(temporary=False):
        st=selected_student(); comp=selected_computer()
        if not st or not comp: return
        eno=st[0]; rid=int(comp[0]); health=comp[3]; current_class=class_box.get().strip(); batch=batch_box.get().strip()
        if health == "Maintenance":
            messagebox.showwarning("Computer under maintenance","Choose a healthy computer for the temporary replacement.",parent=window); return
        if comp[4] != "Free":
            messagebox.showwarning("Computer assigned","This computer is already assigned. Mark its student absent/release it first.",parent=window); return
        conn=db_connection()
        if not conn: return
        try:
            cur=conn.cursor()
            cur.execute("SELECT allocation_id FROM lab_allocations WHERE enrollment_no=%s AND allocation_status='Assigned'",(eno,))
            existing=cur.fetchone()
            if existing:
                cur.execute("UPDATE lab_allocations SET allocation_status='Released' WHERE enrollment_no=%s AND allocation_status='Assigned'",(eno,))
            cur.execute("INSERT INTO lab_allocations (class_name,batch_name,enrollment_no,resource_id,allocation_type,allocation_status,note) VALUES (%s,%s,%s,%s,%s,'Assigned',%s)",
                        (current_class,batch,eno,rid,'Temporary' if temporary else 'Regular','Temporary replacement / spare computer' if temporary else 'Regular roll-number allocation'))
            conn.commit(); cur.close(); refresh()
            messagebox.showinfo("Computer assigned",f"{comp[1]} assigned to {eno} ({'temporary' if temporary else 'regular'}).",parent=window)
        except Exception as e:
            conn.rollback(); messagebox.showerror("Allocation failed",str(e),parent=window)
        finally: conn.close()

    def mark_absent():
        st=selected_student()
        if not st: return
        conn=db_connection()
        if not conn: return
        try:
            cur=conn.cursor()
            cur.execute("UPDATE lab_allocations SET allocation_status='Absent', note='Student absent; computer may be used temporarily' WHERE enrollment_no=%s AND class_name=%s AND batch_name=%s AND allocation_status='Assigned' AND allocation_type='Regular'",
                        (st[0],class_box.get().strip(),batch_box.get().strip()))
            changed=cur.rowcount; conn.commit(); cur.close(); refresh()
            if changed: messagebox.showinfo("Marked absent",f"{st[0]} marked absent. Their assigned computer is now available for temporary use.",parent=window)
            else: messagebox.showinfo("No regular assignment","This student has no active regular assignment to release.",parent=window)
        except Exception as e:
            conn.rollback(); messagebox.showerror("Error",str(e),parent=window)
        finally: conn.close()

    def auto_assign_batch():
        class_name=class_box.get().strip(); batch=batch_box.get().strip(); lab=lab_box.get().strip()
        if not class_name or not batch or not lab:
            messagebox.showwarning("Missing selection","Choose class, batch and lab.",parent=window); return
        students=db_rows("SELECT enrollment_no FROM students WHERE class_name=%s ORDER BY enrollment_no",(class_name,))
        students=students[:36] if batch=="Batch A" else students[36:72]
        if not students:
            messagebox.showinfo("No students",f"No students found for {class_name} / {batch}.",parent=window); return
        computers=db_rows("""SELECT r.resource_id,r.resource_name FROM resources r
            WHERE r.resource_type='Lab Computer' AND r.location=%s AND r.status='Available'
            AND NOT EXISTS (SELECT 1 FROM lab_allocations a WHERE a.resource_id=r.resource_id AND a.allocation_status='Assigned')
            ORDER BY r.resource_name""",(lab,))
        if len(computers)<len(students):
            messagebox.showwarning("Not enough computers",f"{len(students)} students but only {len(computers)} free, healthy computers in {lab}. Add/repair computers or assign a smaller group.",parent=window); return
        if not messagebox.askyesno("Assign batch",f"Assign {len(students)} students in {class_name} / {batch} to computers in {lab}, in enrollment-number order?",parent=window): return
        conn=db_connection()
        if not conn: return
        try:
            cur=conn.cursor()
            for i,(eno,) in enumerate(students):
                # Release any previous regular assignment for this student before reassigning.
                cur.execute("UPDATE lab_allocations SET allocation_status='Released' WHERE enrollment_no=%s AND allocation_status='Assigned' AND allocation_type='Regular'",(eno,))
                cur.execute("INSERT INTO lab_allocations (class_name,batch_name,enrollment_no,resource_id,allocation_type,allocation_status,note) VALUES (%s,%s,%s,%s,'Regular','Assigned','Auto-assigned in enrollment-number order')",
                            (class_name,batch,eno,computers[i][0]))
            conn.commit(); cur.close(); refresh()
            messagebox.showinfo("Batch assigned",f"Assigned {len(students)} students in roll/enrollment order.",parent=window)
        except Exception as e:
            conn.rollback(); messagebox.showerror("Assignment failed",str(e),parent=window)
        finally: conn.close()

    buttons=tk.Frame(window,bg=BG,padx=18,pady=10); buttons.pack(fill="x")
    styled_button(buttons,"Refresh",refresh).pack(side="left",padx=4)
    styled_button(buttons,"Auto-Assign Batch (Roll Order)",auto_assign_batch).pack(side="left",padx=4)
    styled_button(buttons,"Assign Selected Computer",lambda:assign(False)).pack(side="left",padx=4)
    styled_button(buttons,"Temporary Replacement",lambda:assign(True)).pack(side="left",padx=4)
    tk.Button(buttons,text="Mark Student Absent / Release PC",command=mark_absent,padx=10,pady=8).pack(side="left",padx=4)
    class_box.bind("<<ComboboxSelected>>",lambda e:refresh()); batch_box.bind("<<ComboboxSelected>>",lambda e:refresh()); lab_box.bind("<<ComboboxSelected>>",lambda e:refresh())
    refresh_options(); refresh()



def open_timetable_management(parent, role):
    """Prototype timetable for multiple classes; staff/admin can add the actual entries as available."""
    if role not in ("Admin", "Staff"):
        messagebox.showwarning("Access denied", "Only Admin and Staff can access timetable sessions.", parent=parent)
        return
    win = tk.Toplevel(parent)
    win.title("Timetable and Scheduled Lab Sessions")
    win.geometry("1180x700")
    win.configure(bg=BG)
    make_header(win, "Timetable and Scheduled Lab Sessions", role)

    form = tk.Frame(win, bg=BG, padx=16, pady=12)
    form.pack(fill="x")
    fields = [
        ("Class", ttk.Combobox(form, values=[f"SY-{i:02d}" for i in range(1, 27)] + ["SY-08"], width=13)),
        ("Day", ttk.Combobox(form, values=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"], state="readonly", width=12)),
        ("Start (HH:MM)", tk.Entry(form, width=12)),
        ("End (HH:MM)", tk.Entry(form, width=12)),
        ("Subject / Lab", tk.Entry(form, width=20)),
        ("Batch", ttk.Combobox(form, values=["Batch A","Batch B","W1","W2","W3","All"], state="readonly", width=12)),
        ("Room No.", tk.Entry(form, width=12)),
    ]
    widgets = {}
    for i, (label, widget) in enumerate(fields):
        tk.Label(form, text=label, bg=BG, fg=NAVY).grid(row=0, column=i, sticky="w", padx=4)
        widget.grid(row=1, column=i, sticky="ew", padx=4, pady=4)
        widgets[label] = widget
    widgets["Class"].set("SY-08")
    widgets["Day"].set("Monday")
    widgets["Start (HH:MM)"].insert(0, "13:40")
    widgets["End (HH:MM)"].insert(0, "15:30")
    widgets["Subject / Lab"].insert(0, "DMSL")
    widgets["Batch"].set("Batch A")
    widgets["Room No."].insert(0, "S407")

    tk.Label(win, text="Prototype: timetable entries are editable. Add each class/batch/room slot; the system does not assume every class has the same schedule.",
             bg=BG, fg=NAVY, wraplength=1100, justify="left").pack(anchor="w", padx=20, pady=(0,8))
    cols = ("id","class","day","start","end","subject","batch","room")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=19)
    for c, title, width in [("id","ID",45),("class","Class",95),("day","Day",100),("start","Start",80),("end","End",80),("subject","Subject / Lab",220),("batch","Batch",100),("room","Room No.",100)]:
        tree.heading(c,text=title); tree.column(c,width=width,anchor="w")
    tree.pack(fill="both",expand=True,padx=18,pady=8)

    def run_query(sql,args=(),fetch=False):
        conn=db_connection()
        if not conn: return [] if fetch else False
        try:
            cur=conn.cursor(); cur.execute(sql,args)
            rows=cur.fetchall() if fetch else []
            if not fetch: conn.commit()
            cur.close(); return rows if fetch else True
        except Exception as e:
            conn.rollback(); messagebox.showerror("Timetable error",str(e),parent=win); return [] if fetch else False
        finally: conn.close()

    def refresh():
        tree.delete(*tree.get_children())
        rows=run_query("SELECT timetable_id,class_name,day_name,TIME_FORMAT(start_time,'%H:%i'),TIME_FORMAT(end_time,'%H:%i'),subject_name,batch_name,room_no FROM class_timetable ORDER BY class_name, FIELD(day_name,'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'),start_time",fetch=True)
        for row in rows: tree.insert("","end",values=row)

    def add_entry():
        values=[widgets[x].get().strip() for x in ("Class","Day","Start (HH:MM)","End (HH:MM)","Subject / Lab","Batch","Room No.")]
        cls,day,start,end,subject,batch,room=values
        if not all(values):
            messagebox.showwarning("Missing details","Complete all timetable fields.",parent=win); return
        try:
            datetime.strptime(start,"%H:%M"); datetime.strptime(end,"%H:%M")
            if start >= end: raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid time","Enter times in 24-hour HH:MM format; end must be after start.",parent=win); return
        if run_query("INSERT INTO class_timetable (class_name,day_name,start_time,end_time,subject_name,batch_name,room_no,is_lab) VALUES (%s,%s,%s,%s,%s,%s,%s,1)",(cls.upper(),day,start,end,subject,batch,room)):
            refresh(); messagebox.showinfo("Saved",f"Saved {cls} {batch}: {subject}, {start}-{end}, room {room}.",parent=win)

    def delete_entry():
        selected=tree.selection()
        if not selected:
            messagebox.showwarning("Select entry","Select a timetable row to delete.",parent=win); return
        row=tree.item(selected[0],"values")
        if messagebox.askyesno("Delete timetable entry",f"Delete {row[1]} {row[2]} {row[5]} ({row[6]})?",parent=win):
            run_query("DELETE FROM class_timetable WHERE timetable_id=%s",(row[0],)); refresh()

    controls=tk.Frame(win,bg=BG,padx=18,pady=8); controls.pack(fill="x")
    styled_button(controls,"Add Timetable Entry",add_entry).pack(side="left",padx=4)
    tk.Button(controls,text="Delete Selected Entry",command=delete_entry,padx=12,pady=8).pack(side="left",padx=4)
    tk.Button(controls,text="Refresh",command=refresh,padx=12,pady=8).pack(side="left",padx=4)
    refresh()


def open_staff_personal_access(parent, full_name):
    """Simple personal staff access page without exposing admin-only controls."""
    win=tk.Toplevel(parent); win.title("Staff Personal Access"); win.geometry("520x360"); win.configure(bg=BG)
    make_header(win,"Staff Personal Access","Staff")
    tk.Label(win,text=f"Staff member: {full_name}",font=("Segoe UI",14,"bold"),bg=BG,fg=NAVY).pack(pady=(25,8))
    tk.Label(win,text="Use the buttons below for your own resource access. Class and batch computer allocations are managed separately.",wraplength=450,bg=BG,justify="center").pack(pady=8)
    tk.Button(win,text="Open Library Availability",command=lambda:open_library_management(win,"Staff",None),padx=16,pady=9).pack(pady=6)
    tk.Button(win,text="Open Reading Room Availability",command=lambda:open_reading_room_management(win,"Staff",None),padx=16,pady=9).pack(pady=6)
    tk.Button(win,text="Open Computer Lab Inventory",command=lambda:open_lab_management(win,"Staff"),padx=16,pady=9).pack(pady=6)


def open_dashboard(full_name, role, student_enrollment=None):
    dashboard = tk.Tk()
    dashboard.title("Campus Resource Management System")
    dashboard.geometry("1000x700")
    dashboard.configure(bg=BG)
    header = tk.Frame(dashboard, bg=NAVY, height=120)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header, text="CAMPUS RESOURCE MANAGEMENT", font=("Segoe UI", 22, "bold"), bg=NAVY, fg="white").pack(pady=(22, 5))
    tk.Label(header, text=f"Welcome, {full_name} ({role})", font=("Segoe UI", 11), bg=NAVY, fg="#bfdbfe").pack()
    content = tk.Frame(dashboard, bg=BG, padx=30, pady=20)
    content.pack(fill="both", expand=True)
    tk.Label(content, text="Dashboard", font=("Segoe UI", 22, "bold"), bg=BG, fg=NAVY).pack(anchor="w", pady=(0, 12))
    buttons = [
        ("Computer Lab Management\nView computers and availability", lambda: open_lab_management(dashboard, role)),
        ("Library Management\nSingle-user tables", lambda: open_library_management(dashboard, role, student_enrollment)),
        ("Reading Room Management\nTables with 4 seats and 8-seat large tables", lambda: open_reading_room_management(dashboard, role, student_enrollment)),
        ("Usage History\nView session times and durations", lambda: open_usage_history(dashboard, role, student_enrollment)),
    ]
    if role == "Staff":
        buttons.insert(0, ("Staff Personal Access\nYour resource access", lambda: open_staff_personal_access(dashboard, full_name)))
        buttons.insert(1, ("Timetable / Scheduled Lab Sessions\nManage class, batch, subject, time and room", lambda: open_timetable_management(dashboard, role)))
        buttons.insert(2, ("Lab Class / Batch Allocation\nView allotted computers and manage replacements", lambda: open_lab_batch_allocation(dashboard, role)))
    elif role == "Admin":
        buttons.insert(0, ("Timetable / Scheduled Lab Sessions\nManage class, batch, subject, time and room", lambda: open_timetable_management(dashboard, role)))
        buttons.insert(1, ("Lab Class / Batch Allocation\nView allotted computers and manage replacements", lambda: open_lab_batch_allocation(dashboard, role)))
    if role in ("Admin", "Staff"):
        buttons.insert(3, ("Student Registration\nAdd enrollment number, name, class and phone", lambda: open_student_management(dashboard, role)))
    for text, command in buttons:
        tk.Button(content, text=text, command=command, font=("Segoe UI", 12, "bold"), bg="white", fg=NAVY,
                  activebackground="#dbeafe", relief="flat", anchor="w", justify="left", padx=18, pady=12).pack(fill="x", pady=4)
    def show_logout_options():
        choice = tk.Toplevel(dashboard)
        choice.title("Logout")
        choice.geometry("390x190")
        choice.resizable(False, False)
        choice.transient(dashboard)
        choice.grab_set()
        tk.Label(choice, text="What would you like to do?", font=("Segoe UI", 12, "bold")).pack(pady=(22, 16))
        buttons = tk.Frame(choice)
        buttons.pack(pady=4)

        def login_again():
            choice.destroy()
            dashboard.destroy()
            open_login()

        def quit_application():
            choice.destroy()
            try:
                dashboard.quit()
            finally:
                dashboard.destroy()

        tk.Button(buttons, text="Login Again", command=login_again, bg=BLUE, fg="white",
                  relief="flat", padx=16, pady=9, font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)
        tk.Button(buttons, text="Quit Application", command=quit_application, bg=RED, fg="white",
                  relief="flat", padx=16, pady=9, font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)

    tk.Button(dashboard, text="Logout", command=show_logout_options, bg=RED, fg="white",
              font=("Segoe UI", 10, "bold"), relief="flat", padx=20, pady=8).pack(pady=(0, 14))
    dashboard.mainloop()


def student_login(root, enrollment_entry, phone_entry, name_entry, class_entry):
    enrollment = enrollment_entry.get().strip().upper()
    phone = phone_entry.get().strip()
    full_name = name_entry.get().strip()
    class_name = class_entry.get().strip()

    if not enrollment or not phone or not full_name or not class_name:
        messagebox.showwarning(
            "Missing Details",
            "Enter enrollment number, phone number, full name and class/division.",
            parent=root
        )
        return
    if not ENROLLMENT_PATTERN.fullmatch(enrollment):
        messagebox.showwarning("Invalid Enrollment Number", "Example format: ADT25SOCB0376", parent=root)
        return
    if not phone.isdigit() or len(phone) != 10:
        messagebox.showwarning("Invalid Phone Number", "Enter a valid 10-digit phone number.", parent=root)
        return
    if not initialise_app_tables():
        return
    connection = db_connection()
    if not connection:
        return
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT phone_number FROM students WHERE enrollment_no=%s",
            (enrollment,)
        )
        student = cursor.fetchone()

        if student is None:
            # First-time local access: collect and save the student's details.
            cursor.execute(
                "INSERT INTO students (enrollment_no, full_name, class_name, phone_number) VALUES (%s, %s, %s, %s)",
                (enrollment, full_name, class_name, phone)
            )
            connection.commit()
        elif student[0] is None or str(student[0]).strip() == "":
            # Legacy record: attach phone and update details supplied by the student.
            cursor.execute(
                "UPDATE students SET full_name=%s, class_name=%s, phone_number=%s WHERE enrollment_no=%s",
                (full_name, class_name, phone, enrollment)
            )
            connection.commit()
        elif str(student[0]).strip() == phone:
            # Returning student: refresh their name/class while keeping phone matched.
            cursor.execute(
                "UPDATE students SET full_name=%s, class_name=%s WHERE enrollment_no=%s",
                (full_name, class_name, enrollment)
            )
            connection.commit()
        else:
            cursor.close()
            messagebox.showerror(
                "Login Failed",
                "This enrollment number is already linked to a different phone number.",
                parent=root
            )
            return

        cursor.close()
        root.destroy()
        open_dashboard(full_name, "Student", enrollment)
    except Exception as error:
        connection.rollback()
        messagebox.showerror("Student Login Error", str(error), parent=root)
    finally:
        connection.close()


def open_teacher_login(parent):
    """Teacher login for prototype: timetable teacher ID abbreviation plus name."""
    win = tk.Toplevel(parent)
    win.title("Teacher Login")
    win.geometry("440x350")
    win.configure(bg=BG)
    make_header(win, "Teacher Login", "Use the teacher ID listed in the departmental timetable")
    form = tk.Frame(win, bg="white", padx=28, pady=24)
    form.pack(fill="both", expand=True, padx=22, pady=18)

    tk.Label(form, text="Teacher ID", bg="white", fg=NAVY, font=("Segoe UI", 10, "bold")).pack(anchor="w")
    teacher_id_entry = tk.Entry(form, font=("Segoe UI", 11), relief="solid", bd=1)
    teacher_id_entry.pack(fill="x", pady=(4, 12), ipady=5)

    tk.Label(form, text="Teacher Name", bg="white", fg=NAVY, font=("Segoe UI", 10, "bold")).pack(anchor="w")
    teacher_name_entry = tk.Entry(form, font=("Segoe UI", 11), relief="solid", bd=1)
    teacher_name_entry.pack(fill="x", pady=(4, 14), ipady=5)

    def login_teacher():
        teacher_id = teacher_id_entry.get().strip().upper()
        teacher_name = " ".join(teacher_name_entry.get().strip().split())
        if not teacher_id or not teacher_name:
            messagebox.showwarning("Missing Details", "Enter teacher ID and teacher name.", parent=win)
            return
        connection = db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor()
            # Look up by teacher ID first, then compare names while ignoring academic titles.
            cursor.execute(
                "SELECT full_name FROM teachers WHERE UPPER(teacher_id)=%s",
                (teacher_id,)
            )
            teacher = cursor.fetchone()
            cursor.close()

            def normalise_teacher_name(value):
                value = " ".join(value.strip().casefold().split())
                value = re.sub(r"^(prof(?:essor)?\.?|dr\.?|d\.?r\.?)(\s+)", "", value)
                return value.strip()

            if teacher and normalise_teacher_name(teacher[0]) == normalise_teacher_name(teacher_name):
                win.destroy()
                open_dashboard(teacher[0], "Staff")
            else:
                messagebox.showerror(
                    "Teacher Login Failed",
                    "Teacher ID and name did not match the timetable prototype records.",
                    parent=win
                )
        except Exception as error:
            messagebox.showerror("Teacher Login Error", str(error), parent=win)
        finally:
            connection.close()

    tk.Button(form, text="TEACHER LOGIN", command=login_teacher, font=("Segoe UI", 10, "bold"),
              bg=BLUE, fg="white", relief="flat", cursor="hand2", pady=9).pack(fill="x")
    tk.Label(form, text="Prototype access uses teacher ID + name; it is not secure identity verification.",
             wraplength=350, bg="white", fg="#64748b", font=("Segoe UI", 8)).pack(pady=(10, 0))


def open_login():
    root = tk.Tk()
    root.title("Campus Resource Management System")
    root.geometry("900x760")
    root.resizable(False, False)
    root.configure(bg=BG)
    header = tk.Frame(root, bg=NAVY, height=120)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header, text="CAMPUS RESOURCE MANAGEMENT", font=("Segoe UI", 22, "bold"), bg=NAVY, fg="white").pack(pady=(24, 5))
    tk.Label(header, text="Laboratory • Library • Reading Room", font=("Segoe UI", 11), bg=NAVY, fg="#bfdbfe").pack()
    card = tk.Frame(root, bg="white", padx=40, pady=28)
    card.place(relx=0.5, rely=0.52, anchor="center")
    tk.Label(card, text="Welcome Back", font=("Segoe UI", 20, "bold"), bg="white", fg=NAVY).pack(pady=(0, 6))
    tk.Label(card, text="Sign in to manage campus resources", font=("Segoe UI", 10), bg="white", fg="#64748b").pack(pady=(0, 14))
    tk.Label(card, text="Username", bg="white", fg="#334155", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    username = tk.Entry(card, width=34, font=("Segoe UI", 11), relief="solid", bd=1)
    username.pack(pady=(5, 14), ipady=7)
    tk.Label(card, text="Password", bg="white", fg="#334155", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    password = tk.Entry(card, width=34, font=("Segoe UI", 11), show="*", relief="solid", bd=1)
    password.pack(pady=(5, 18), ipady=7)

    def login():
        entered_username = username.get().strip()
        entered_password = password.get()
        if not entered_username or not entered_password:
            messagebox.showwarning("Missing Details", "Enter username and password.", parent=root)
            return
        connection = db_connection()
        if not connection:
            return
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT full_name, role, password_hash FROM users WHERE username=%s", (entered_username,))
            user = cursor.fetchone()
            cursor.close()
            if user and user[2] == hash_password(entered_password):
                if not initialise_app_tables():
                    return
                root.destroy()
                open_dashboard(user[0], user[1])
            else:
                messagebox.showerror("Login Failed", "Incorrect username or password.", parent=root)
        except Exception as error:
            messagebox.showerror("Login Error", str(error), parent=root)
        finally:
            connection.close()
    tk.Button(card, text="ADMIN / STAFF LOGIN", command=login, font=("Segoe UI", 11, "bold"), bg=BLUE, fg="white", relief="flat", cursor="hand2", width=30, pady=9).pack()
    tk.Button(card, text="TEACHER LOGIN (Teacher ID + Name)", command=lambda: (initialise_app_tables() and open_teacher_login(root)), font=("Segoe UI", 10, "bold"), bg="#0f766e", fg="white", relief="flat", cursor="hand2", width=30, pady=8).pack(pady=(7, 0))
    tk.Label(card, text="Student Login (No Prior Registration Needed)", font=("Segoe UI", 13, "bold"), bg="white", fg=NAVY).pack(pady=(18, 8))
    tk.Label(card, text="Enrollment Number", bg="white", fg="#334155").pack(anchor="w")
    student_enrollment = tk.Entry(card, width=34, font=("Segoe UI", 10), relief="solid", bd=1)
    student_enrollment.pack(pady=(3, 8), ipady=4)
    tk.Label(card, text="Phone Number", bg="white", fg="#334155").pack(anchor="w")
    student_phone = tk.Entry(card, width=34, font=("Segoe UI", 10), relief="solid", bd=1)
    student_phone.pack(pady=(3, 6), ipady=4)
    tk.Label(card, text="Full Name", bg="white", fg="#334155").pack(anchor="w")
    student_name = tk.Entry(card, width=34, font=("Segoe UI", 10), relief="solid", bd=1)
    student_name.pack(pady=(3, 6), ipady=4)
    tk.Label(card, text="Class / Division", bg="white", fg="#334155").pack(anchor="w")
    student_class = tk.Entry(card, width=34, font=("Segoe UI", 10), relief="solid", bd=1)
    student_class.pack(pady=(3, 8), ipady=4)
    tk.Button(card, text="STUDENT LOGIN", command=lambda: student_login(root, student_enrollment, student_phone, student_name, student_class), font=("Segoe UI", 10, "bold"), bg="#475569", fg="white", relief="flat", cursor="hand2", width=30, pady=8).pack()
    tk.Label(root, text="Academic Project | Python + Tkinter + MySQL", font=("Segoe UI", 9), bg=BG, fg="#64748b").pack(side="bottom", pady=12)
    username.focus_set()
    root.mainloop()


if __name__ == "__main__":
    open_login()
