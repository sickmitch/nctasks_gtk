from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, GLib
from requests.auth import HTTPBasicAuth
from icalendar import Calendar, Todo
from datetime import datetime, timezone, date
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
import requests
import threading
import os
import uuid
from urllib.parse import urlparse, urljoin
from .dialogs import error_dialog, setup_dialog

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
    def on_add_clicked(self):
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
            error_dialog(self.window, "! Tasks needs a summary !")
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
        if hasattr(self, 'is_secondary'):
            todo.add('related-to', self.parent_uid)
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
            error_dialog(self.window, f"Failed to add task to server: {e}")
            return
        # Reset input fields and update the task list
        self.window.task_entry.set_text('')
        self.window.status_combo.set_active(0)
        self.window.priority_combo.set_active(0)
        self.window.due_stack.set_visible_child_name("icon")
        self.start_async_fetch()
    
    ### SYNC BUTTON HANDLER
    def on_sync_clicked(self, button):
        self.start_async_fetch()
    
    ### DELETE BUTTON HANDLER
    def on_del_clicked(self, button):
        uids_to_remove = self.get_selection()

        try:
            uid_to_href = self.extract_uid_to_href()
        except ValueError as e:
            error_dialog(self.window, str(e))
            return

        parsed_cal_url = urlparse(self.cal_url)
        server_base = f"{parsed_cal_url.scheme}://{parsed_cal_url.netloc}"

        for uid in uids_to_remove:
            event_href = uid_to_href.get(uid)
            if not event_href:
                error_dialog(self.window, f"No URL found for task with UID {uid}")
                continue

            event_url = urljoin(server_base, event_href)
            try:
                # Send a DELETE request to the server
                response = requests.delete(
                    url=event_url,
                    auth=HTTPBasicAuth(self.user, self.api_key))
                response.raise_for_status() 
                # Remove the task from the local calendar
                for component in self.cal.subcomponents:
                    if component.name == 'VTODO' and str(component.get('uid')) == uid:
                        self.cal.subcomponents.remove(component)
                        break
                self.window.status_bar.push(0, "Task successfully deleted from server")
            except requests.exceptions.RequestException as e:
                error_dialog(self.window, f"Failed to delete task from server: {e}")
        # Save the updated calendar and refresh the task list
        self.start_async_fetch()
    
    ### EDIT BUTTON HANDLER
    def on_edit_clicked(self, button): 
        self.reset_input()
        self.uid = self.get_selection()[0]
        # Find the VTODO component
        todo = None
        for component in self.cal.walk():
            if component.name == 'VTODO' and str(component.get('uid')) == self.uid:
                self.todo = component
                break
        # Get current values
        self.current_summary = str(self.todo.get('summary', ''))
        current_status = str(self.todo.get('status', 'NEEDS-ACTION'))
        current_priority = int(self.todo.get('priority', 9))
        current_due = self.todo.get('due')
        # Map combos to index
        status_map = {'NEEDS-ACTION': 0, 'IN-PROCESS': 1}
        self.current_status_label = status_map.get(current_status, 'Todo')
        priority_map = {1: 2, 5: 1, 9: 0}
        self.current_priority_label = priority_map.get(current_priority, 'Low')
        # Parse due date 
        if current_due != None:
            due_dt = current_due.dt
            if isinstance(due_dt, datetime):
                self.current_due_date = due_dt.date()
            elif isinstance(due_dt, date):
                self.current_due_date = due_dt
        else:
            self.current_due_date = current_due

        if self.current_due_date:
            date_obj = datetime.strptime(str(self.current_due_date), "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d-%m-%Y")
            self.window.due_button.selected_date = date_obj.date()
            self.window.date_label.set_text(formatted_date)
            self.window.due_stack.set_visible_child_name("date")

        self.window.task_entry.set_text(self.current_summary)
        self.window.status_combo.set_active(self.current_status_label)
        self.window.priority_combo.set_active(self.current_priority_label)
        self.window.add_stack.set_visible_child_name("edit")
        self.window.set_focus(self.window.task_entry)
        
    def on_edit_conclusion(self):
        task = self.window.task_entry.get_text()
        status_text = self.window.status_combo.get_active_text()
        priority_text = self.window.priority_combo.get_active_text()        
        if not task:
            error_dialog(self.window, "! Tasks needs a summary !")
            return
        # Map to right format
        status_map = {"Todo": "NEEDS-ACTION", "Started": "IN-PROCESS"}
        status = status_map.get(status_text, "NEEDS-ACTION")
        priority_map = {"Low": 9, "Medium": 5, "High": 1}
        priority = priority_map.get(priority_text, 9)
        # Update the VTODO component
        self.todo['summary'] = task
        self.todo['priority'] = priority
        self.todo['status'] = status
        # Handle no due 
        if hasattr(self.window.due_button, 'selected_date'):
            new_task_due = self.window.due_button.selected_date
        else:
            new_task_due = "None"
        if new_task_due != "None":
            if 'due' in self.todo:
                del self.todo['due']
            if isinstance(new_task_due, str):
                new_task_due = datetime.strptime(new_task_due, "%d-%m-%Y").date()
            self.todo.add('due', new_task_due)
        elif 'due' in self.todo:
            del self.todo['due']
        # Prepare and send PUT request
        cal = Calendar()
        cal.add('prodid', '-//NCTasks//')
        cal.add('version', '2.0')
        cal.add_component(self.todo)

        uid_to_href = self.extract_uid_to_href()
        event_href = uid_to_href.get(self.uid)
        parsed_cal_url = urlparse(self.cal_url)
        server_base = f"{parsed_cal_url.scheme}://{parsed_cal_url.netloc}"

        try:
            event_url = urljoin(server_base, event_href)
            response = requests.put(
                event_url,
                headers={'Content-Type': 'text/calendar; charset=utf-8'},
                auth=HTTPBasicAuth(self.user, self.api_key),
                data=cal.to_ical()
            )
            response.raise_for_status()
        except Exception as e:
            raise Exception(f"API error: {str(e)}")
        
        # Reset input fields
        self.reset_input()
        self.start_async_fetch()

    ### UI STATE
    def set_ui_state(self, busy, status=None):
        self.window.spinner.set_visible(busy)
        self.window.sync_btn.set_sensitive(not busy)
        
        if busy:
            self.window.spinner.start()
        else:
            self.window.spinner.stop()
            
        if status:
            self.window.status_bar.push(0, status)

    ### SECONDARY BUTTON HANDLER
    def on_secondary_clicked(self, button):
        self.reset_input()
        self.is_secondary = "True"
        self.window.add_stack.set_visible_child_name("add")
        self.window.set_focus(self.window.task_entry)
        self.parent_uid = self.get_selection()[0]

    ### ADD BUTTON STACK HANDLer
    def stack_handler(self, action):
        if action == "add":
            self.on_add_clicked()
        if action == "edit":
            self.on_edit_conclusion()
        
    ### GET SELECTION FROM COLUMNVIEW
    def get_selection(self):
        selection = self.window.column_view.get_model()  # Get MultiSelection model
        bitset = selection.get_selection()  # Get selected rows as a Bitset
        uids_to_remove = []

        for i in range(bitset.get_size()):
            index = bitset.get_nth(i)  # Get the index of the selected item
            item = selection.get_item(index)  # Retrieve the TaskObject
            if item:
                uids_to_remove.append(item.uid)  # Store the UID for removal

        return uids_to_remove

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
    
    ###RESET INPUT FIELDS
    def reset_input(self, *_):
        self.window.task_entry.set_text('')
        self.window.status_combo.set_active(0)
        self.window.priority_combo.set_active(0)
        self.window.due_stack.set_visible_child_name("icon")
        self.window.add_stack.set_visible_child_name("add")

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
        self.set_ui_state(busy=True, status="Connecting to Nextcloud...")
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
            GLib.idle_add(self.set_ui_state, False, ("Last sync at " + datetime.now().strftime("%H:%M")))

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
    
    def update_task_list(self):
        priority_map = {1: 'High', 5: 'Medium', 9: 'Low'}
        priority_sort_order = {'High': 3, 'Medium': 2, 'Low': 1, 'Not Set': 0}
        status_map = {'IN-PROCESS': 'Started', 'NEEDS-ACTION': 'Todo', 'COMPLETED': 'Completed'}

        # Clear existing tasks
        self.task_list.remove_all()

        tasks = []
        parent_to_children = {}

        # First pass: collect tasks and build parent-child mapping
        for component in self.cal.walk():
            if component.name == 'VTODO':
                try:
                    uid = str(component.get('uid', ''))
                    task = str(component.get('summary', 'Untitled Task'))

                    # Map priority
                    priority_val = int(component.get('priority', '9999'))  
                    priority = priority_map.get(priority_val, 'Not Set')

                    # Map status
                    status_val = str(component.get('status', 'None'))
                    status = status_map.get(status_val, 'None')

                    # Parse due date
                    due = component.get('due')
                    if due:
                        if isinstance(due, str):
                            if 'T' in due:
                                due_date = datetime.strptime(due, '%Y%m%dT%H%M%S')
                            else:
                                due_date = datetime.strptime(due, '%Y%m%d')
                        else:
                            due_date = due.dt
                            if isinstance(due_date, date) and not isinstance(due_date, datetime):
                                due_date = datetime.combine(due_date, datetime.min.time(), timezone.utc)
                            elif due_date.tzinfo is None:
                                due_date = due_date.replace(tzinfo=timezone.utc)
                        due_str = due_date.strftime('󰥔   %a %d/%m H:%H')
                    else:
                        due_date = datetime.max.replace(tzinfo=timezone.utc)
                        due_str = 'Not Set'

                    # Check for parent-child relation
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

        # Populate ListStore with sorted tasks, ensuring children follow parents
        for uid, task, priority, status, due_str, _ in tasks:
            task_obj = self.window.TaskObject(uid=uid, task=task, priority=priority, status=status, due=due_str)
            self.task_list.append(task_obj)

            if uid in parent_to_children:
                children = parent_to_children[uid]
                children.sort(key=lambda x: (x[5], -priority_sort_order[x[2]]))
                for child_uid, child_task, child_priority, child_status, child_due_str, _ in children:
                    child_task_obj = self.window.TaskObject(uid=child_uid, task=f" 󰳟   {child_task}", priority=child_priority, status=child_status, due=child_due_str)
                    self.task_list.append(child_task_obj)