from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, Gdk
from datetime import datetime, timezone, date
from icalendar import vDatetime
from requests.auth import HTTPBasicAuth
from icalendar import Calendar

def create_edit_dialog(parent, current_summary, current_status_label, 
                      current_priority_label, current_due_date, todo,
                      cal_url, user, api_key, refresh_callback):
    dialog = Gtk.Dialog(title="Edit Task")
    dialog.set_transient_for(parent)
    dialog.set_modal(True)
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
    summary_entry = Gtk.Entry(xalign=0.5)
    summary_entry.set_text(current_summary)
    summary_entry.set_size_request(250, -1)

    grid.attach(summary_label, 0, 0, 1, 1)
    grid.attach(summary_entry, 1, 0, 1, 1)

    # Status combo
    status_label = Gtk.Label(label="Status:")
    status_combo = Gtk.ComboBoxText()
    for status in ["Todo", "Started", "Completed"]:
        status_combo.append_text(status)
    status_combo.set_active(["Todo", "Started", "Completed"].index(current_status_label))
    status_renderer = status_combo.get_cells()[0]
    status_renderer.set_property("xalign", 0.5)
    grid.attach(status_label, 0, 1, 1, 1)
    grid.attach(status_combo, 1, 1, 1, 1)

    # Priority combo
    priority_label = Gtk.Label(label="Priority:")
    priority_combo = Gtk.ComboBoxText()
    for priority in ["Low", "Medium", "High"]:
        priority_combo.append_text(priority)
    priority_combo.set_active(["Low", "Medium", "High"].index(current_priority_label))
    priority_renderer = priority_combo.get_cells()[0]
    priority_renderer.set_property("xalign", 0.5)
    grid.attach(priority_label, 0, 2, 1, 1)
    grid.attach(priority_combo, 1, 2, 1, 1)

    # Due date picker
    due_label = Gtk.Label(label="Due Date:")
    grid.attach(due_label, 0, 3, 1, 1)

    due_button = Gtk.Button()
    # due_button.set_size_request(110, -1)
    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)  # Optional animation        
    
    icon = Gtk.Image.new_from_icon_name("org.gnome.Calendar")
    date_label = Gtk.Label()

    stack.add_named(icon, "icon")
    stack.add_named(date_label, "date")

    due_button.set_child(stack)

    if current_due_date != None:
        date_label.set_text(str(current_due_date))
        stack.set_visible_child_name("date") # Initial state
    else:
        stack.set_visible_child_name("icon")  # Initial state
    grid.attach(due_button, 1, 3, 1, 1)
    due_button.connect("clicked", on_due_date_clicked, due_button, stack, date_label)

    def on_response(dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            from .application import Application
            Application.handle_edit_response(
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
            selected_date = calendar.get_date().format("%d-%m-%Y")
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