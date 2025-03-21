from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, Gdk
from datetime import datetime, timezone, date
from icalendar import vDatetime
import requests
from requests.auth import HTTPBasicAuth
from icalendar import Calendar

def create_edit_dialog(parent, current_summary, current_status_label, 
                      current_priority_label, current_due_date, todo,
                      cal_url, user, api_key, refresh_callback):
    dialog = Gtk.Dialog(title="Edit Task")
    dialog.set_transient_for(parent)
    dialog.set_modal(True)
    dialog.set_default_size(400, -1)
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dialog.add_button("OK", Gtk.ResponseType.OK)

    content_area = dialog.get_content_area()
    grid = Gtk.Grid()
    grid.set_column_spacing(10)
    grid.set_row_spacing(10)
    grid.set_margin_start(15)
    grid.set_margin_end(15)
    grid.set_margin_top(15)
    grid.set_margin_bottom(15)
    content_area.append(grid)

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
    due_button.connect("clicked", on_due_date_clicked, due_button)
    grid.attach(due_label, 0, 3, 1, 1)
    grid.attach(due_button, 1, 3, 1, 1)

    def on_response(dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            handle_edit_response(
                summary_entry,
                status_combo,
                priority_combo,
                due_button,
                todo,
                cal_url,
                user,
                api_key,
                refresh_callback
            )
        dialog.destroy()

    dialog.connect("response", on_response)
    dialog.present()
    return dialog

def handle_edit_response(summary_entry, status_combo, priority_combo, due_button,
                        todo, cal_url, user, api_key, refresh_callback):
    new_summary = summary_entry.get_text()
    
    status_idx = status_combo.get_active()
    new_status_label = status_combo.get_model()[status_idx][0] if status_idx != -1 else ""
    
    priority_idx = priority_combo.get_active()
    new_priority_label = priority_combo.get_model()[priority_idx][0] if priority_idx != -1 else ""
    
    new_due_str = due_button.get_label() #OCIO

    # Map back to iCalendar values
    status_reverse_map = {"Todo": "NEEDS-ACTION", "Started": "IN-PROCESS", "Completed": "COMPLETED"}
    new_status = status_reverse_map.get(new_status_label, 'NEEDS-ACTION')
    priority_reverse_map = {'Low': 9, 'Medium': 5, 'High': 1}
    new_priority = priority_reverse_map.get(new_priority_label, 9)
    
    new_due = None
    if new_due_str != "Select Date":
        try:
            new_due_date = datetime.strptime(new_due_str, '%Y-%m-%d').date()
            new_due_datetime = datetime.combine(new_due_date, datetime.min.time(), timezone.utc)
            new_due = vDatetime(new_due_datetime).to_ical().decode('utf-8')
        except Exception as e:
            print(f"Error parsing date: {e}")

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
    
    try:
        event_url = f"{cal_url}/{todo['uid']}.ics"
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

def on_due_date_clicked(button, due_button, stack, date_label):
    dialog = Gtk.Dialog(title="Select Due Date")
    dialog.set_transient_for(button.get_root())
    dialog.set_modal(True)
    dialog.set_default_size(400, 200)

    calendar = Gtk.Calendar()
    content_area = dialog.get_content_area()
    content_area.append(calendar)

    dialog.add_buttons(
        "Cancel", Gtk.ResponseType.CANCEL,
        "Clear", 42,
        "OK", Gtk.ResponseType.OK
    )

    def on_date_response(dialog, response):
        if response == Gtk.ResponseType.OK:
            selected_date = calendar.get_date().format("%Y-%m-%d")
            date_label.set_text(selected_date)
            stack.set_visible_child_name("date")  # Show date view
            due_button.selected_date = selected_date
        elif response == 42:  # Handle "Clear"
            stack.set_visible_child_name("icon")  # Show icon view
            if hasattr(due_button, 'selected_date'):
                del due_button.selected_date
        dialog.destroy()

    dialog.connect("response", on_date_response)
    dialog.present()


def error_dialog(message):
    dialog = Gtk.MessageDialog(
        modal=True,  # Blocks interaction with the main window
        buttons=Gtk.ButtonsType.CLOSE,
        message_type=Gtk.MessageType.ERROR,
        text="Error",
        secondary_text=message  # The message received from the invoker
    )
    dialog.connect("response", lambda d, r: d.destroy())

    dialog.show()