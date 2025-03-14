#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk
from icalendar import Calendar, Todo, vDatetime
from datetime import datetime, timezone, date
import uuid
import os
import xml.etree.ElementTree as ET
import requests
from requests.auth import HTTPBasicAuth
import threading
from dotenv import load_dotenv

class NCTasksGTK(Gtk.Window):
    def __init__(self):
        super().__init__(title="NC Tasks GTK")
        self.set_border_width(15)
        self.set_default_size(600, 400)
        # Load environment variables first
        self.load_environment_vars()
        # Initialize UI
        self.init_ui()
        # Start async data loading
        self.start_async_fetch()
        # Initialize needed variables
        self.new_task_due = None

    def create_action_buttons(self):
        """Create bottom action buttons"""
        btn_box = Gtk.Box(spacing=5)
        
        self.sync_btn = Gtk.Button(label="Sync Now", image=Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON))
        self.sync_btn.connect("clicked", self.on_sync_clicked)
        
        self.remove_btn = Gtk.Button(label="Remove Selected", image=Gtk.Image.new_from_icon_name("list-remove-symbolic", Gtk.IconSize.BUTTON))
        self.remove_btn.connect("clicked", self.on_remove_clicked)
        self.remove_btn.set_sensitive(False)
        
        self.edit_btn = Gtk.Button(label="Edit Task", image=Gtk.Image.new_from_icon_name("document-edit-symbolic", Gtk.IconSize.BUTTON))
        self.edit_btn.connect("clicked", self.on_edit_clicked)
        self.edit_btn.set_sensitive(False)
        
        self.clear_btn = Gtk.Button(label="Clear All", image=Gtk.Image.new_from_icon_name("edit-clear-all-symbolic", Gtk.IconSize.BUTTON))
        self.clear_btn.connect("clicked", self.on_clear_clicked)
        
        btn_box.pack_start(self.sync_btn, False, False, 0)
        btn_box.pack_start(self.remove_btn, False, False, 0)
        btn_box.pack_start(self.edit_btn, False, False, 0)
        btn_box.pack_start(self.clear_btn, False, False, 0)
        self.grid.attach(btn_box, 0, 2, 5, 1)

    def load_environment_vars(self):
            """Load and validate required environment variables"""
            # Load from .env file or system environment
            load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

            self.base_url = os.getenv("BASE_URL")
            self.user = os.getenv("USERNAME")
            self.api_key = os.getenv("API_KEY")
            self.root_dir = os.getenv("ROOT_DIR", os.path.expanduser("~/.config/nctasks_gtk"))

            missing = []
            if not self.base_url: missing.append("BASE_URL")
            if not self.user: missing.append("USERNAME")
            if not self.api_key: missing.append("API_KEY")

            if missing:
                raise ValueError(
                    f"Missing required environment variables:\n"
                    f"{', '.join(missing)}\n\n"
                    f"Create a .env file with these values or set them system-wide."
                )

            self.cal_url = f"{self.base_url}/remote.php/dav/calendars/{self.user}/attivit"
            self.ics_file = os.path.join(self.root_dir, 'tasks')

    def show_fatal_error(self, message):
        """Show error dialog and quit"""
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            message_format=message
        )
        dialog.run()
        dialog.destroy()
        Gtk.main_quit()

    def init_ui(self):
        """Initialize all UI components"""
        # CSS setup
        self.init_styling()
        
        # Main layout
        self.grid = Gtk.Grid(column_spacing=5, row_spacing=5)
        self.add(self.grid)
        
        # Status components
        self.status_bar = Gtk.Statusbar()
        self.spinner = Gtk.Spinner()
        
        # Task input components
        self.create_input_fields()
        self.create_task_list()
        self.create_action_buttons()
        
        # Assemble UI
        self.grid.attach(self.status_bar, 0, 3, 5, 1)
        self.grid.attach_next_to(self.spinner, self.status_bar, Gtk.PositionType.LEFT, 1, 1)

    def init_styling(self):
        """Initialize CSS styling"""
        css_provider = Gtk.CssProvider()
        try:
            css_path = os.path.join(self.root_dir, 'style.css')
            css_provider.load_from_path(css_path)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(f"Error loading CSS: {e}")

    def create_input_fields(self):
        """Create task input components"""
        self.task_entry = Gtk.Entry(placeholder_text="Task description")
        self.status_combo = Gtk.ComboBoxText()
        for status in ["Todo", "Started"]:
            self.status_combo.append_text(status)
        self.status_combo.set_active(0)
        self.priority_combo = Gtk.ComboBoxText()
        for priority in ["Low", "Medium", "High"]:
            self.priority_combo.append_text(priority)
        self.priority_combo.set_active(0)
        self.calendar_icon = Gtk.Button()
        self.calendar_icon.set_image(Gtk.Image.new_from_icon_name("org.gnome.Calendar", Gtk.IconSize.BUTTON))
        self.calendar_icon.connect("clicked", self.on_calendar_icon_clicked)
        self.add_btn = Gtk.Button(label="Add Task", image=Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON))
        self.add_btn.connect("clicked", self.on_add_clicked)
        
        input_box = Gtk.Box(spacing=5)
        input_box.pack_start(self.task_entry, True, True, 0)
        input_box.pack_start(self.status_combo, False, False, 0)
        input_box.pack_start(self.priority_combo, False, False, 0)
        input_box.pack_start(self.calendar_icon, False, False, 0)
        input_box.pack_start(self.add_btn, False, False, 0)
        
        self.grid.attach(input_box, 0, 0, 5, 1)

    def start_async_fetch(self):
        """Start background data synchronization"""
        self.set_ui_state(busy=True, status="Connecting to Nextcloud...")
        threading.Thread(target=self.fetch_caldav_data, daemon=True).start()

    def fetch_caldav_data(self):
        """Background thread for CalDAV synchronization"""
        try:
            # Fetch fresh data from server
            response = requests.request(
                method='PROPFIND',
                url=self.cal_url,
                headers={
                    'Depth': '1',
                    'Content-Type': 'application/xml'
                },
                auth=HTTPBasicAuth(self.user, self.api_key),
                data='''<?xml version="1.0" encoding="UTF-8"?>
                    <d:propfind xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
                        <d:prop>
                            <d:getetag/>
                            <cal:calendar-data/>
                        </d:prop>
                    </d:propfind>'''
            )
            response.raise_for_status()
            
            # Save received data
            with open(self.ics_file, 'wb') as f:
                f.write(response.content)
            
            # Update UI with fresh data
            GLib.idle_add(self.update_calendar_data)
            
        except Exception as e:
            GLib.idle_add(self.show_error, f"Sync failed: {str(e)}")
        finally:
            GLib.idle_add(self.set_ui_state, False, ("Synced at " + datetime.now().strftime("%H:%M")))

    def create_task_list(self):
        """Create task list display"""
        self.scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.task_list = Gtk.ListStore(str, str, str, str, str)  # UID, Task, Priority, Status, Due
        self.treeview = Gtk.TreeView(model=self.task_list)

        # Enable multiple selection
        selection = self.treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)

        # Configure columns
        columns = [
            ("Task", 1),
            ("Priority", 2),
            ("Status", 3),
            ("Due", 4)
        ]

        for i, (title, col_id) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=col_id)
            self.treeview.append_column(column)

        self.scrolled_window.add(self.treeview)
        self.grid.attach(self.scrolled_window, 0, 1, 5, 1)
        # Enable multiple selection and connect signal
        selection = self.treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect("changed", self.on_selection_changed)

    def on_selection_changed(self, selection):
        """Handle task selection changes to update button states"""
        model, paths = selection.get_selected_rows()
        num_selected = len(paths)
        self.edit_btn.set_sensitive(num_selected == 1)
        self.remove_btn.set_sensitive(num_selected >= 1)

    def on_edit_clicked(self, widget):
        """Handle edit button click"""
        selection = self.treeview.get_selection()
        model, paths = selection.get_selected_rows()
        if len(paths) != 1:
            return

        treeiter = model.get_iter(paths[0])
        uid = model[treeiter][0]

        # Find the VTODO component
        todo = None
        for component in self.cal.walk():
            if component.name == 'VTODO' and str(component.get('uid')) == uid:
                todo = component
                break
        if not todo:
            self.show_error("Task not found!")
            return

        # Get current values
        current_summary = str(todo.get('summary', ''))
        current_status = str(todo.get('status', 'NEEDS-ACTION'))
        current_priority = int(todo.get('priority', 9))
        current_due = todo.get('due')

        # Map status to UI labels
        status_map = {'NEEDS-ACTION': 'Todo', 'IN-PROCESS': 'Started', 'COMPLETED': 'Completed'}
        current_status_label = status_map.get(current_status, 'Todo')

        # Map priority to UI labels
        priority_map = {1: 'High', 5: 'Medium', 9: 'Low'}
        current_priority_label = priority_map.get(current_priority, 'Low')

        # Parse due date
        current_due_date = None
        if current_due:
            due_dt = current_due.dt
            if isinstance(due_dt, datetime):
                current_due_date = due_dt.date()
            elif isinstance(due_dt, date):
                current_due_date = due_dt

        # Create edit dialog
        dialog = Gtk.Dialog(title="Edit Task", parent=self, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("OK", Gtk.ResponseType.OK)
        content_area = dialog.get_content_area()
        grid = Gtk.Grid(column_spacing=10, row_spacing=10, margin=10)
        content_area.add(grid)

        # Summary field
        summary_label = Gtk.Label(label="Summary:")
        summary_entry = Gtk.Entry()
        summary_entry.set_text(current_summary)
        grid.attach(summary_label, 0, 0, 1, 1)
        grid.attach(summary_entry, 1, 0, 1, 1)

        # Status combo
        status_label = Gtk.Label(label="Status:")
        status_combo = Gtk.ComboBoxText()
        for status in ["Todo", "Started", "Completed"]:
            status_combo.append_text(status)
        status_combo.set_active(["Todo", "Started", "Completed"].index(current_status_label))
        grid.attach(status_label, 0, 1, 1, 1)
        grid.attach(status_combo, 1, 1, 1, 1)

        # Priority combo
        priority_label = Gtk.Label(label="Priority:")
        priority_combo = Gtk.ComboBoxText()
        for priority in ["Low", "Medium", "High"]:
            priority_combo.append_text(priority)
        priority_combo.set_active(["Low", "Medium", "High"].index(current_priority_label))
        grid.attach(priority_label, 0, 2, 1, 1)
        grid.attach(priority_combo, 1, 2, 1, 1)

        # Due date picker
        due_label = Gtk.Label(label="Due Date:")
        due_button = Gtk.Button()
        if current_due_date:
            due_button.set_label(current_due_date.strftime('%Y-%m-%d'))
        else:
            due_button.set_label("Select Date")
        due_button.connect("clicked", self.on_edit_due_date_clicked, due_button)
        grid.attach(due_label, 0, 3, 1, 1)
        grid.attach(due_button, 1, 3, 1, 1)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            # Update task details
            new_summary = summary_entry.get_text()
            new_status_label = status_combo.get_active_text()
            new_priority_label = priority_combo.get_active_text()
            new_due_str = due_button.get_label()

            # Map back to iCalendar values
            status_reverse_map = {v: k for k, v in status_map.items()}
            new_status = status_reverse_map.get(new_status_label, 'NEEDS-ACTION')
            priority_reverse_map = {'Low': 9, 'Medium': 5, 'High': 1}
            new_priority = priority_reverse_map.get(new_priority_label, 9)
            new_due = None
            if new_due_str != "Select Date":
                try:
                    new_due_date = datetime.strptime(new_due_str, '%Y-%m-%d').date()
                    # Convert date to datetime with timezone
                    new_due_datetime = datetime.combine(new_due_date, datetime.min.time(), timezone.utc)
                    # Convert the datetime to the correct iCalendar format
                    new_due = vDatetime(new_due_datetime).to_ical().decode('utf-8')
                except Exception as e:
                    print(f"Error parsing date: {e}")
                    new_due = None

            # Update the VTODO component
            todo['summary'] = new_summary
            todo['status'] = new_status
            todo['priority'] = new_priority
            if new_due:
                todo['due'] = new_due
            elif 'due' in todo:
                del todo['due']


            # Prepare and send PUT request
            cal = Calendar()
            cal.add('prodid', '-//NCTasks//')
            cal.add('version', '2.0')
            cal.add_component(todo)
            ics_data = cal.to_ical()

            event_url = f"{self.cal_url}/{uid}.ics"
            try:
                response = requests.put(
                    event_url,
                    headers={
                        'Content-Type': 'text/calendar; charset=utf-8'
                    },
                    auth=HTTPBasicAuth(self.user, self.api_key),
                    data=ics_data
                )
                response.raise_for_status()
                self.start_async_fetch()  # Refresh the task list
            except Exception as e:
                self.show_error(f"Failed to update task: {e}")

        dialog.destroy()

    def on_edit_due_date_clicked(self, widget, due_button):
        """Handle due date selection in edit dialog"""
        dialog = Gtk.Dialog(title="Select Due Date", parent=self, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("OK", Gtk.ResponseType.OK)
        calendar = Gtk.Calendar()
        content_area = dialog.get_content_area()
        content_area.add(calendar)
        dialog.show_all()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            year, month, day = calendar.get_date()
            due_str = f"{year}-{month+1:02d}-{day:02d}"
            due_button.set_label(due_str)
        dialog.destroy()
    def update_calendar_data(self):
        """Load and display calendar data"""
        self.cal = self.load_or_create_calendar()
        self.update_task_list()
        self.show_all()
        self.status_bar.push(0, "Synchronized: " + datetime.now().strftime("%H:%M:%S"))

    def set_ui_state(self, busy, status=None):
        """Update UI state during operations"""
        self.spinner.set_visible(busy)
        self.sync_btn.set_sensitive(not busy)
        
        if busy:
            self.spinner.start()
        else:
            self.spinner.stop()
            
        if status:
            self.status_bar.push(0, status)

        # Initial task list update

    def load_or_create_calendar(self):
        cal = Calendar()
        cal.add('prodid', '-//NCTasks//mxm.dk//')
        cal.add('version', '2.0')

        if not os.path.exists(self.ics_file):
            return cal

        try:
            # Parse XML and extract calendar data
            tree = ET.parse(self.ics_file)
            root = tree.getroot()
            
            # XML namespaces
            namespaces = {
                'd': 'DAV:',
                'cal': 'urn:ietf:params:xml:ns:caldav'
            }
            
            # Find all successful responses with calendar data
            for response in root.findall('.//d:response', namespaces):
                status = response.find('.//d:status', namespaces)
                if status is None or '200 OK' not in status.text:
                    continue
                
                calendar_data = response.find('.//cal:calendar-data', namespaces)
                if calendar_data is None:
                    continue
                
                # Parse iCalendar content
                ical_content = calendar_data.text.strip()
                try:
                    sub_cal = Calendar.from_ical(ical_content)
                    for component in sub_cal.walk():
                        if component.name == 'VTODO':
                            cal.add_component(component)
                except Exception as e:
                    print(f"Error parsing iCalendar content: {e}")
            
            return cal
            
        except Exception as e:
            print(f"Error loading calendar data: {e}")
            return cal

    def update_task_list(self):
        priority_map = {1: 'High', 5: 'Medium', 9: 'Low'}
        priority_sort_order = {'High': 3, 'Medium': 2, 'Low': 1, 'Not Set': 0}
        status_map = {'IN-PROCESS': 'Started', 'NEEDS-ACTION': 'Todo', 'COMPLETED': 'Completed'}

        self.task_list.clear()
        tasks = []
        parent_to_children = {}

        # First pass: collect all tasks and build parent-child relationships
        for component in self.cal.walk():
            if component.name == 'VTODO':
                try:
                    uid = str(component.get('uid', ''))
                    task = str(component.get('summary', 'Untitled Task'))

                    # Map priority to descriptive label
                    priority_val = int(component.get('priority', '9999'))  # Default to "Not Set"
                    priority = priority_map.get(priority_val, 'Not Set')

                    # Map status to descriptive label
                    status_val = str(component.get('status', 'None'))
                    status = status_map.get(status_val, 'None')

                    # Parse the due field
                    due = component.get('due')
                    if due:
                        if isinstance(due, str):
                            # Handle string due dates
                            if 'T' in due:
                                # Datetime format: DUE:20250318T235959
                                due_date = datetime.strptime(due, '%Y%m%dT%H%M%S')
                            else:
                                # Date format: DUE;VALUE=DATE:20250316
                                due_date = datetime.strptime(due, '%Y%m%d')
                        else:
                            # Handle datetime and date objects
                            due_date = due.dt
                            if isinstance(due_date, date) and not isinstance(due_date, datetime):
                                due_date = datetime.combine(due_date, datetime.min.time(), timezone.utc)
                            elif due_date.tzinfo is None:  # Convert naive datetime to UTC
                                due_date = due_date.replace(tzinfo=timezone.utc)
                        due_str = due_date.strftime('󰥔 %a %d/%m H:%H')
                    else:
                        due_date = datetime.max.replace(tzinfo=timezone.utc)  # Make datetime max timezone-aware
                        due_str = 'Not Set'

                    # Check for RELATED-TO field
                    related_to = str(component.get('related-to', ''))
                    if related_to:
                        if related_to not in parent_to_children:
                            parent_to_children[related_to] = []
                        parent_to_children[related_to].append((uid, task, priority, status, due_str, due_date))
                    else:
                        tasks.append((uid, task, priority, status, due_str, due_date))

                except Exception as e:
                    print(f"Error parsing task: {e}")

        # Sort tasks: first by due date (ascending), then by priority (descending)
        tasks.sort(key=lambda x: (x[5], -priority_sort_order[x[2]]))

        # Populate self.task_list with sorted tasks, ensuring children follow their parents
        for uid, task, priority, status, due_str, _ in tasks:
            self.task_list.append([uid, task, priority, status, due_str])
            if uid in parent_to_children:
                children = parent_to_children[uid]
                children.sort(key=lambda x: (x[5], -priority_sort_order[x[2]]))
                for child_uid, child_task, child_priority, child_status, child_due_str, _ in children:
                    self.task_list.append([child_uid, f" 󰳟 {child_task}", child_priority, child_status, child_due_str])

    def create_new_calendar(self):
        cal = Calendar()
        cal.add('prodid', '-//NCTasks//mxm.dk//')
        cal.add('version', '2.0')
        return cal

    def save_calendar(self):
        with open(self.ics_file, 'wb') as f:
            f.write(self.cal.to_ical())

    def on_add_clicked(self, widget):
        task = self.task_entry.get_text()
        priority_text = self.priority_combo.get_active_text()
        status_text = self.status_combo.get_active_text()

        if not task:
            self.show_error("Task description cannot be empty!")
            return

        status_map = {"Todo": "NEEDS-ACTION", "Started": "IN-PROCESS"}
        status = status_map.get(status_text, "NEEDS-ACTION")

        priority_map = {"Low": 9, "Medium": 5, "High": 1}
        priority = priority_map.get(priority_text, 9)

        # Generate a unique UID for the task
        uid = str(uuid.uuid4())

        # Create a Todo component
        todo = Todo()
        todo.add('uid', uid)
        todo.add('summary', task)
        if not self.new_task_due:
            self.new_task_due = datetime.now().strftime('%Y-%m-%d')
        due_date = datetime.strptime(self.new_task_due, '%Y-%m-%d').date()
        todo.add('due', due_date)
        todo.add('status', status)
        todo.add('priority', priority)
        todo.add('dtstamp', datetime.now())

        # Create a Calendar instance and add the Todo
        cal = Calendar()
        cal.add('prodid', '-//My Calendar App//')
        cal.add('version', '2.0')
        cal.add_component(todo)

        # Generate the .ics data
        ics_data = cal.to_ical()

        # Determine the URL for the new task on the server
        event_url = f"{self.cal_url}/{uid}.ics"

        try:
            # Push the .ics data to the server using PUT
            response = requests.put(
                url=event_url,
                headers={
                    'Content-Type': 'text/calendar; charset=utf-8',
                },
                auth=HTTPBasicAuth(self.user, self.api_key),
                data=ics_data
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.show_error(f"Failed to add task to server: {e}")
            return

        # Clear the input field and update the task list
        self.task_entry.set_text('')
        self.fetch_caldav_data()
        self.update_task_list()

    def on_remove_clicked(self, widget):
        selection = self.treeview.get_selection()
        model, paths = selection.get_selected_rows()

        if not paths:
            return  # No rows selected

        # Collect all UIDs to remove
        uids_to_remove = []
        for path in paths:
            treeiter = model.get_iter(path)
            uid_to_remove = model[treeiter][0]  # Get the UID of the selected task
            uids_to_remove.append(uid_to_remove)

        # Construct the URLs for the tasks to delete
        for uid in uids_to_remove:
            event_url = f"{self.cal_url}/{uid}.ics"

            try:
                # Send a DELETE request to the server
                response = requests.delete(
                    url=event_url,
                    auth=HTTPBasicAuth(self.user, self.api_key)
                )
                response.raise_for_status()  # Raise an exception for HTTP errors

                # Remove the task from the local calendar
                for component in self.cal.subcomponents:
                    if component.name == 'VTODO' and str(component.get('uid')) == uid:
                        self.cal.subcomponents.remove(component)
                        break

            except requests.exceptions.RequestException as e:
                self.show_error(f"Failed to delete task from server: {e}")

        # Save the updated calendar and refresh the task list
        self.save_calendar()
        self.update_task_list()

    def on_clear_clicked(self, widget):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            message_format="Clear all tasks?"
        )
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.OK:
            self.cal = self.create_new_calendar()
            self.save_calendar()
            self.update_task_list()

    def on_calendar_icon_clicked(self, widget):
        dialog = Gtk.Dialog(
            title="Select Due Date",
            parent=self,
            modal=True,
            destroy_with_parent=True
        )
        dialog.set_default_size(400, 200)
        # Create content area
        content_area = dialog.get_content_area()
        # Create calendar widget
        calendar = Gtk.Calendar()
        content_area.add(calendar)
        # Add buttons
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("OK", Gtk.ResponseType.OK)
        # Show all widgets in the dialog
        dialog.show_all()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            year, month, day = calendar.get_date()
            self.new_task_due = f"{year}-{month + 1:02d}-{day:02d}"
        print(self.new_task_due)

        dialog.destroy()

    def show_error(self, message):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            message_format=message
        )
        dialog.run()
        dialog.destroy()

    def on_sync_clicked(self, widget):
        """Handle manual sync button click"""
        self.start_async_fetch()

if __name__ == "__main__":
    win = NCTasksGTK()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()