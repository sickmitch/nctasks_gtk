from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, Gdk
from datetime import datetime, timezone, date
from icalendar import vDatetime
from requests.auth import HTTPBasicAuth
from icalendar import Calendar
import webbrowser
import os
from dotenv import load_dotenv


### DUE DATE DIALOG
def on_due_date_clicked(button, due_button, stack, date_label):
    # Define dialog
    dialog = Gtk.Dialog(title="Select Due Date and Time")
    dialog.set_transient_for(button.get_root())
    dialog.set_modal(True)
    dialog.set_default_size(400, 300)

    calendar = Gtk.Calendar()
    hour_spin = Gtk.SpinButton()
    hour_spin.set_adjustment(Gtk.Adjustment(lower=0, upper=23, step_increment=1, page_increment=1))
    minute_spin = Gtk.SpinButton()
    minute_spin.set_adjustment(Gtk.Adjustment(lower=0, upper=50, step_increment=10, page_increment=1))

    # Labels
    time_label = Gtk.Label(label="Time (HH:MM)")
    hour_label = Gtk.Label(label="Hour:")
    minute_label = Gtk.Label(label="Minute:")

    # Layout
    content_area = dialog.get_content_area()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=10, margin_bottom=10, margin_start=10, margin_end=10)
    box.append(calendar)

    time_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    time_box.append(time_label)
    time_box.append(hour_label)
    time_box.append(hour_spin)
    time_box.append(minute_label)
    time_box.append(minute_spin)

    box.append(time_box)
    content_area.append(box)

    dialog.add_buttons(
        "Cancel", Gtk.ResponseType.CANCEL,
        "Clear", 42,
        "OK", Gtk.ResponseType.OK
    )

    def on_date_response(dialog, response):
        if response == Gtk.ResponseType.OK:
            selected_date = calendar.get_date().format("%d-%m-%Y")
            selected_time = f"{int(hour_spin.get_value()):02d}:{int(minute_spin.get_value()):02d}"
            date_label.set_text(f"{selected_date} {selected_time}")
            stack.set_visible_child_name("date")  # Show date view
            due_button.selected_date = f"{selected_date} {selected_time}"
        elif response == 42:  # Handle "Clear"
            stack.set_visible_child_name("icon")  # Show icon view
            if hasattr(due_button, 'selected_date'):
                del due_button.selected_date
        dialog.destroy()

    dialog.connect("response", on_date_response)
    dialog.present()

#### SETUP DIALOG
def setup_dialog(missing, parent, refresh_callback):
    parent.present()
    parent.grab_focus()
    # Dialog 
    dialog = Gtk.Dialog(title="Setup Tasks", transient_for=parent, modal=True)
    dialog.set_transient_for(parent)
    dialog.set_application(parent.get_application())
    # dialog.set_size_request(1000, 400)
    # Header 
    header_bar = Gtk.HeaderBar()
    header_bar.set_title_widget(Gtk.Label(label="Fill to setup Tasks"))
    header_bar.set_show_title_buttons(False)
    dialog.set_titlebar(header_bar)
    # Buttons
    dialog.add_buttons(
        "Cancel", Gtk.ResponseType.CANCEL,
        "Git Help", Gtk.ResponseType.HELP,
        "Submit", Gtk.ResponseType.OK,)
    # Grid
    content_area = dialog.get_content_area()
    grid = Gtk.Grid()
    grid.set_column_spacing(10)
    grid.set_row_spacing(10)
    grid.set_margin_start(15)
    grid.set_margin_end(15)
    grid.set_margin_top(15)
    grid.set_margin_bottom(15)
    # Url
    url_entry = Gtk.Entry(hexpand=True,halign=Gtk.Align.FILL,xalign=0.5)
    if "BASE_URL" not in missing:
        url_entry.set_text(os.getenv("BASE_URL"))
    url_label = Gtk.Label(label="Base URL")
    url_entry.set_size_request(250, -1)
    grid.attach(url_label, 0, 1, 1, 1)
    grid.attach(url_entry, 1, 1, 1, 1)
    # User
    user_entry = Gtk.Entry(hexpand=True,halign=Gtk.Align.FILL,xalign=0.5)
    if "USERNAME" not in missing:
        user_entry.set_text(os.getenv("USERNAME"))
    user_label = Gtk.Label(label="Username")
    user_entry.set_size_request(250, -1)
    grid.attach(user_label, 0, 2, 1, 1)
    grid.attach(user_entry, 1, 2, 1, 1)
    # Api_key
    api_key_entry = Gtk.Entry(hexpand=True,halign=Gtk.Align.FILL,xalign=0.5)
    if "API_KEY" not in missing:
        api_key_entry.set_text(os.getenv("API_KEY"))
    api_key_label = Gtk.Label(label="Password or Api_key to use for authentication")
    api_key_entry.set_size_request(250, -1)
    grid.attach(api_key_label, 0, 3, 1, 1)
    grid.attach(api_key_entry, 1, 3, 1, 1)
    # Calendar            
    calendar_entry = Gtk.Entry(hexpand=True,halign=Gtk.Align.FILL,xalign=0.5)
    if "CALENDAR" not in missing:
        calendar_entry.set_text(os.getenv("CALENDAR"))
    else:     
        calendar_entry.set_placeholder_text("lower case only")
    calendar_label = Gtk.Label(label="The calendar fetched to get tasks,only lower case")
    calendar_entry.set_size_request(250, -1)
    grid.attach(calendar_label, 0, 4, 1, 1)
    grid.attach(calendar_entry, 1, 4, 1, 1)
    # Root_dir
    root_dir_entry = Gtk.Entry(hexpand=True,halign=Gtk.Align.FILL,xalign=0.5)
    if "ROOT_DIR" not in missing:
        root_dir_entry.set_text(os.getenv("ROOT_DIR"))
    root_dir_label = Gtk.Label(label="Absolute path to Tasks code")
    root_dir_entry.set_size_request(250, -1)
    grid.attach(root_dir_label, 0, 5, 1, 1)
    grid.attach(root_dir_entry, 1, 5, 1, 1)

    content_area.append(grid)

    def on_response(dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            from .application import Application
            app = Application()
            app.handle_setup_response(
                url_entry.get_text(),
                user_entry.get_text(), 
                api_key_entry.get_text(), 
                calendar_entry.get_text(), 
                root_dir_entry.get_text(),
                refresh_callback)
        if response_id == Gtk.ResponseType.HELP:
            webbrowser.open("https://github.com/sickmitch/nctasks_gtk")
        if response_id == Gtk.ResponseType.CANCEL:
            from .window import Window
            Window.destroy()
        dialog.destroy()
    dialog.connect("response", on_response)

    dialog.show()
    dialog.set_visible(True)
    dialog.grab_focus()
    

#### ERROR MESSAGE
def error_dialog(parent, message):
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,  
        buttons=Gtk.ButtonsType.CLOSE,
        message_type=Gtk.MessageType.ERROR,
        text="Error",
        secondary_text=message
    )
    dialog.connect("response", lambda d, r: d.destroy())

    dialog.show()