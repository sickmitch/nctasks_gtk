from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, GLib
from requests.auth import HTTPBasicAuth
from icalendar import Calendar, Todo
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
import requests
from urllib.parse import urlparse, urljoin
import threading
import os
import uuid
from .dialogs import create_edit_dialog, error_dialog, setup_dialog

class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.sickmitch.NCTasks")
        self.task_list = [] 

    def do_activate(self):
        from .window import Window
        self.window = Window(self)
        self.window.present()
        self.load_environment_vars()

    ### ADD BUTTON HANDLER
    def on_add_clicked(self, button):
        # Fetch values from UI
        task = self.window.task_entry.get_text()
        status_text = self.window.status_combo.get_active_text()
        priority_text = self.window.priority_combo.get_active_text()        
        # Handle no due 
        if hasattr(self.window.due_button, 'selected_date'):
            new_task_due = self.window.due_button.selected_date
        else:
            new_task_due = "None"
        # Handle empty summary entry
        if not task:
            error_dialog("! Tasks needs a summary !")
            return
        # Map to right format
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
        if new_task_due != "None":
            new_task_due = datetime.strptime(new_task_due, "%d-%m-%Y").date()
            todo.add('due', new_task_due)
        todo.add('status', status)
        todo.add('priority', priority)
        todo.add('dtstamp', datetime.now())
        # Create a Calendar instance and add the Todo
        cal = Calendar()
        cal.add('prodid', '-//NCTasks//')
        cal.add('version', '2.0')
        cal.add_component(todo)
        # Generate the .ics data
        ics_data = cal.to_ical()
        # Determine the URL for the new task on the server
        event_url = f"{self.cal_url}/{uid}.ics"
        #  Push the .ics data to the server using PUT, handle errors
        try:
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
            error_dialog(f"Failed to add task to server: {e}")
            return
        # Reset input fields and update the task list
        self.window.task_entry.set_text('')
        self.window.status_combo.set_active(0)
        self.window.priority_combo.set_active(0)
        self.window.stack.set_visible_child_name("icon")  # Show date view
        if hasattr(self.window.due_button, 'selected_date'):
            del self.window.due_button.selected_date
        self.start_async_fetch()
    
    ### SYNC BUTTON HANDLER
    def on_sync_clicked(self, button):
        self.start_async_fetch()

    ### HREF EXTRACT 
    def extract_uid_to_href(self):
        try:
            tree = ET.parse(self.ics_file)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML file: {e}")
    
        root = tree.getroot()
        namespaces = {
            'd': 'DAV:',
            'cal': 'urn:ietf:params:xml:ns:caldav'
        }
        uid_to_href = {}

        for response in root.findall('d:response', namespaces):
            href_element = response.find('d:href', namespaces)
            if href_element is None:
                continue
            href = href_element.text.strip()

            propstat = response.find('d:propstat', namespaces)
            if propstat is None:
                continue
            prop = propstat.find('d:prop', namespaces)
            if prop is None:
                continue
            calendar_data_element = prop.find('cal:calendar-data', namespaces)
            if calendar_data_element is None or not calendar_data_element.text:
                continue

            uid_in_cal = None
            for line in calendar_data_element.text.splitlines():
                line = line.strip()
                if line.startswith('UID:'):
                    uid_in_cal = line.split(':', 1)[1].strip()
                    break
            if uid_in_cal:
                uid_to_href[uid_in_cal] = href

        return uid_to_href


    def on_del_clicked(self, button):
        selection = self.window.treeview.get_selection()
        model, paths = selection.get_selected_rows()
        uids_to_remove = [model[model.get_iter(path)][0] for path in paths]

        try:
            uid_to_href = self.extract_uid_to_href()
        except ValueError as e:
            error_dialog(str(e))
            return

        parsed_cal_url = urlparse(self.cal_url)
        server_base = f"{parsed_cal_url.scheme}://{parsed_cal_url.netloc}"

        for uid in uids_to_remove:
            event_href = uid_to_href.get(uid)
            if not event_href:
                error_dialog(f"No URL found for task with UID {uid}")
                continue

            event_url = urljoin(server_base, event_href)
            try:
                response = requests.delete(
                    url=event_url,
                    auth=HTTPBasicAuth(self.user, self.api_key)
                )
                response.raise_for_status()

                for component in self.cal.subcomponents:
                    if component.name == 'VTODO' and str(component.get('uid')) == uid:
                        self.cal.subcomponents.remove(component)
                        break
                self.window.status_bar.push(0, "Task successfully deleted from server")
            except requests.exceptions.RequestException as e:
                error_dialog(f"Failed to delete task from server: {e}")

        self.start_async_fetch()
    
    ### EDIT BUTTON HANDLER
    def on_edit_clicked(self, button): 
        # Get selected rows from TreeView's selection
        selection = self.window.treeview.get_selection()
        model, paths = selection.get_selected_rows()
        # Check number of selected items
        num_selected = len(paths)
        treeiter = model.get_iter(paths[0])
        uid = model[treeiter][0]
        # Find the VTODO component
        todo = None
        for component in self.cal.walk():
            if component.name == 'VTODO' and str(component.get('uid')) == uid:
                todo = component
                break
        if not todo:
            error_dialog("Task not found!")
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
        if current_due != None:
            due_dt = current_due.dt
            if isinstance(due_dt, datetime):
                self.current_due_date = due_dt.date()
            elif isinstance(due_dt, date):
                self.current_due_date = due_dt
        else:
            self.current_due_date = current_due
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
            uid=uid,
            refresh_callback=self.start_async_fetch,
            extract_uid_to_href=self.extract_uid_to_href)

    ### HANDLE EDIT TASK NEW VALUES
    def handle_edit_response(summary_entry, status_combo, priority_combo, due_button,
                            todo, cal_url, user, api_key, uid, refresh_callback, extract_uid_to_href):
        # define new Todo values
        new_summary = summary_entry.get_text()
        status_idx = status_combo.get_active()
        new_status_label = status_combo.get_model()[status_idx][0] if status_idx != -1 else ""
        priority_idx = priority_combo.get_active()
        new_priority_label = priority_combo.get_model()[priority_idx][0] if priority_idx != -1 else ""
        # Map back to iCalendar values
        status_reverse_map = {"Todo": "NEEDS-ACTION", "Started": "IN-PROCESS", "Completed": "COMPLETED"}
        new_status = status_reverse_map.get(new_status_label, 'NEEDS-ACTION')
        priority_reverse_map = {'Low': 9, 'Medium': 5, 'High': 1}
        new_priority = priority_reverse_map.get(new_priority_label, 9)
        # Various DUE cases handling
        if hasattr(due_button, 'selected_date'):
            new_due_str = due_button.selected_date
        else:
            new_due_str = "Not Set"
        if new_due_str != "Not Set":
            try:
                new_due_str = datetime.strptime(new_due_str, "%d-%m-%Y").date()
            except Exception as e:
                print(f"Error parsing date: {e}")
        # Update the VTODO component
        todo['summary'] = new_summary
        todo['status'] = new_status
        todo['priority'] = new_priority
        if new_due_str != "Not Set":                         #### ugly but works
            todo.add('due', new_due_str)
        elif 'due' in todo:
            del todo['due']
        # Prepare and send PUT request
        cal = Calendar()
        cal.add('prodid', '-//NCTasks//')
        cal.add('version', '2.0')
        cal.add_component(todo)

        uid_to_href = extract_uid_to_href()
        event_href = uid_to_href.get(uid)
        parsed_cal_url = urlparse(cal_url)
        server_base = f"{parsed_cal_url.scheme}://{parsed_cal_url.netloc}"
        
        try:
            event_url = urljoin(server_base, event_href)
            response = requests.put(
                event_url,
                headers={'Content-Type': 'text/calendar; charset=utf-8'},
                auth=HTTPBasicAuth(user, api_key),
                data=cal.to_ical()
            )
            response.raise_for_status()
            refresh_callback()
        except Exception as e:
            raise Exception(f"API error: {str(e)}")

    ### LOAD UP ENV AND CHECK FOR MISSING, IF SOMETHING MISSING TRIGGER SETUP
    def load_environment_vars(self):
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        load_dotenv(env_path)
        def check_missing_env(base_url, user, api_key, calendar, root_dir):
            required = {
                "BASE_URL": base_url,
                "USERNAME": user,
                "API_KEY": api_key,
                "CALENDAR": calendar,
                "ROOT_DIR": root_dir
            }
            missing = [var for var, val in required.items() if not val]
            return missing
        # Assign variables from .env
        self.base_url = os.getenv("BASE_URL")
        self.user = os.getenv("USERNAME")
        self.api_key = os.getenv("API_KEY")
        self.calendar = os.getenv("CALENDAR")
        self.root_dir = os.getenv("ROOT_DIR", os.path.expanduser("~/.config/nctasks_gtk"))
        # Check for missing variables
        missing = check_missing_env(self.base_url,self.user,self.api_key,self.calendar,self.root_dir)
        if missing:
            if self.window.get_mapped():
                setup_dialog(missing,parent=self.window,refresh_callback=self.load_environment_vars)
        else:
            self.cal_url = f"{self.base_url}/remote.php/dav/calendars/{self.user}/{self.calendar}"
            self.ics_file = os.path.join(self.root_dir, 'tasks')
            self.start_async_fetch()           
            
    ### HANDLE SETUP DIALOG VALUES
    def handle_setup_response(url, user, api_key, calendar, root_dir, refresh_callback):
        module_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(module_dir, '.env')
        # Write to .env
        env_content = f'''
BASE_URL="{url}"
USERNAME="{user}"
API_KEY="{api_key}"
CALENDAR="{calendar}"
ROOT_DIR="{root_dir}"
        '''
        with open(env_path, 'w') as env_file:
            env_file.write(env_content)
        refresh_callback()

    ### ASYNC FETCH
    def start_async_fetch(self):
        self.window.status_bar.push(0, "  Calling Nextcloud server.....")
        threading.Thread(target=self.fetch_caldav_data, daemon=True).start()

    ### FETCHING
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
                timeout=10 
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
            GLib.idle_add(error_dialog, error_message)
        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            GLib.idle_add(error_dialog, error_message)
        finally:
            self.window.status_bar.push(0, "󰪩  Successfully synchronized at "+ datetime.now().strftime("%H:%M:%S"))

    ### LOAD NEW DATA AND UPDATE UI
    def update_calendar_data(self):
        self.cal = self.load_or_create_calendar()
        self.update_task_list()

    ### LOAD THE .ICS INTO MEMORY
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
    
    ### PARSE AND ASSIGN THE TASK LIST
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