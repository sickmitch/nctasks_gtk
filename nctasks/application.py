from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, GLib
from requests.auth import HTTPBasicAuth
from icalendar import Calendar, Todo
from datetime import datetime, timezone, date
from datetime import datetime
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
import requests
import threading
import os
import uuid
from .dialogs import create_edit_dialog, error_dialog

class Application(Gtk.Application):

    def __init__(self):
        super().__init__(application_id="com.sickmitch.NCTasks")
        self.task_list = [] 

    def do_activate(self):
        from .window import Window  # Import here to avoid circular import
        self.load_environment_vars()
        self.start_async_fetch()
        self.window = Window(self)
        self.window.present()
        self.window.status_bar.push(0, "Synchronized at "+ datetime.now().strftime("%H:%M:%S"))

    def on_add_clicked(self, button):
        task = self.window.task_entry.get_text()
        status_text = self.window.status_combo.get_active_text()
        priority_text = self.window.priority_combo.get_active_text()
        if hasattr(self.window.due_button, 'selected_date'):
            new_task_due = self.window.due_button.selected_date
        else:
            new_task_due = "None"

        if not task:
            error_dialog("! Tasks needs a summary !")
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
        if new_task_due == "None":
            new_task_due = datetime.now().strftime('%Y-%m-%d')
        due_date = datetime.strptime(new_task_due, '%Y-%m-%d').date()
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
        self.window.task_entry.set_text('')
        self.start_async_fetch()

    def on_sync_clicked(self, button):
        self.start_async_fetch()

    def on_del_clicked(self, button):
        selection = self.window.treeview.get_selection()
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
                
                self.window.status_bar.push(0, "Task successfully deleted from server")

            except requests.exceptions.RequestException as e:
                self.show_error(f"Failed to delete task from server: {e}")

        # Save the updated calendar and refresh the task list
        self.start_async_fetch()

    def on_edit_clicked(self, button):  ###### DA SISTEMARE
        # Get selected rows from TreeView's selection
        selection = self.window.treeview.get_selection()
        model, paths = selection.get_selected_rows()

        # Check number of selected items
        num_selected = len(paths)
        if num_selected != 1:  # Require exactly one selection for editing
            return

        # Get UID from the first (and only) selected row
        treeiter = model.get_iter(paths[0])
        uid = model[treeiter][0]

        # Find the VTODO component (rest of your code remains unchanged)
        todo = None
        for component in self.cal.walk():
            if component.name == 'VTODO' and str(component.get('uid')) == uid:
                todo = component
                break
        if not todo:
            self.show_error("Task not found!")
            return

        # Get current values
        self.current_summary = str(todo.get('summary', ''))
        current_status = str(todo.get('status', 'NEEDS-ACTION'))
        current_priority = int(todo.get('priority', 9))
        current_due = todo.get('due')

        # Map status to UI labels (unchanged)
        status_map = {'NEEDS-ACTION': 'Todo', 'IN-PROCESS': 'Started', 'COMPLETED': 'Completed'}
        self.current_status_label = status_map.get(current_status, 'Todo')

        # Map priority to UI labels (unchanged)
        priority_map = {1: 'High', 5: 'Medium', 9: 'Low'}
        self.current_priority_label = priority_map.get(current_priority, 'Low')

        # Parse due date 
        current_due_date = None
        if current_due:
            due_dt = current_due.dt
            if isinstance(due_dt, datetime):
                self.current_due_date = due_dt.date()
            elif isinstance(due_dt, date):
                self.current_due_date = due_dt
        
        create_edit_dialog(
            parent=self.window,
            current_summary=self.current_summary,
            current_status_label=self.current_status_label,
            current_priority_label=self.current_priority_label,
            current_due_date=self.current_due_date,
            todo=todo,
            cal_url=self.cal_url,
            user=self.user,
            api_key=self.api_key,
            refresh_callback=self.start_async_fetch)

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

    def start_async_fetch(self):
        threading.Thread(target=self.fetch_caldav_data, daemon=True).start()

    def fetch_caldav_data(self):
        try:
            # Send PROPFIND request to CalDAV server
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
                    </d:propfind>''',
                timeout=10  # Set timeout to avoid hanging requests
            )

            # Check if the response is valid
            response.raise_for_status()

            # Ensure response contains XML/ICS data
            if "xml" not in response.headers.get("Content-Type", ""):
                raise ValueError("Invalid response content type. Expected XML.")

            # Save received data
            os.makedirs(os.path.dirname(self.ics_file), exist_ok=True)
            with open(self.ics_file, 'wb') as f:
                f.write(response.content)

            # Update UI with fresh data
            GLib.idle_add(self.update_calendar_data)

        except requests.exceptions.RequestException as e:
            error_message = f"Sync failed: {str(e)}"
            print(error_message)  # Debugging
            GLib.idle_add(self.show_error, error_message)

        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            print(error_message)  # Debugging
            GLib.idle_add(self.show_error, error_message)

        finally:
            self.window.status_bar.push(0, "Synchronized at "+ datetime.now().strftime("%H:%M:%S"))

    def update_calendar_data(self):
        """Load and display calendar data"""
        self.cal = self.load_or_create_calendar()
        self.update_task_list()
        # self.status_bar.push(0, "Synchronized: " + datetime.now().strftime("%H:%M:%S"))

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
                        due_str = due_date.strftime('󰥔   %a %d/%m H:%H')
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
                    self.task_list.append([child_uid, f" 󰳟   {child_task}", child_priority, child_status, child_due_str])