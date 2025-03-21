from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, GObject, Gdk
import os

class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("NCTasks")
        self.app = app
        self.grid = Gtk.Grid(
            column_spacing=5,
            row_spacing=5,
            margin_start=15,
            margin_end=15,
            margin_top=15,
            margin_bottom=15
        )
        self.init_styling()
        self.create_input_fields()
        self.create_task_list()
        self.create_action_buttons()
        self.create_status_bar()
        self.set_child(self.grid)
        
    def create_input_fields(self):
        from .dialogs import on_due_date_clicked
        
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.grid.attach(input_box, 0, 0, 5, 1)
        self.task_entry = Gtk.Entry(
            placeholder_text="Task description",
            hexpand=True,  # Use built-in property
            halign=Gtk.Align.FILL
        )
        input_box.append(self.task_entry)
        
        #STATUS
        self.status_combo = Gtk.ComboBoxText()
        for status in ["Todo", "Started"]:
            self.status_combo.append_text(status)
        self.status_combo.set_active(0)
        input_box.append(self.status_combo)

        #PRIO
        self.priority_combo = Gtk.ComboBoxText()
        for priority in ["Low", "Medium", "High"]:
            self.priority_combo.append_text(priority)
        self.priority_combo.set_active(0)
        input_box.append(self.priority_combo)

        # DUE
        self.due_button = Gtk.Button()
        self.due_button.set_size_request(110, -1)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)  # Optional animation        
        
        icon = Gtk.Image.new_from_icon_name("org.gnome.Calendar")
        self.date_label = Gtk.Label()

        self.stack.add_named(icon, "icon")
        self.stack.add_named(self.date_label, "date")
        self.stack.set_visible_child_name("icon")  # Initial state

        self.due_button.set_child(self.stack)
        self.due_button.connect("clicked", on_due_date_clicked, self.due_button, self.stack, self.date_label)
        input_box.append(self.due_button)
        
        # self.due_button = Gtk.Button(icon_name="org.gnome.Calendar")
        # self.due_button.connect("clicked", on_due_date_clicked, self.due_button)
        # input_box.append(self.due_button)

        # ADD
        self.add_btn = Gtk.Button(label="Add Task", icon_name="list-add-symbolic")
        self.add_btn.connect("clicked", self.app.on_add_clicked)
        input_box.append(self.add_btn)

    def create_task_list(self):
        self.scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.app.task_list = Gtk.ListStore(str, str, str, str, str)  # UID, Task, Priority, Status, Due
        self.treeview = Gtk.TreeView(model=self.app.task_list)

        # Enable multiple selection
        selection = self.treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect("changed", self.on_selection_changed)

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

        self.scrolled_window.set_child(self.treeview)
        self.grid.attach(self.scrolled_window, 0, 1, 5, 1)

    def create_action_buttons(self):
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        ## SYNC BUTTON
        image_refresh = Gtk.Image.new_from_icon_name("view-refresh-symbolic")
        image_refresh.set_pixel_size(16)
        self.sync_btn = Gtk.Button.new()
        btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        btn_content.append(image_refresh)
        btn_content.append(Gtk.Label(label="Sync Now"))
        self.sync_btn.set_child(btn_content)  
        self.sync_btn.connect("clicked", self.app.on_sync_clicked)
        btn_box.append(self.sync_btn)

        ##REMOVE BUTTON
        image_refresh = Gtk.Image.new_from_icon_name("edit-delete-symbolic")
        image_refresh.set_pixel_size(16)
        self.delete_btn = Gtk.Button.new()
        btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        btn_content.append(image_refresh)
        btn_content.append(Gtk.Label(label="Delete Selected"))
        self.delete_btn.set_child(btn_content)  
        self.delete_btn.connect("clicked", self.app.on_del_clicked)
        self.delete_btn.set_sensitive(False)
        btn_box.append(self.delete_btn)

        ##EDIT BUTTON
        image_refresh = Gtk.Image.new_from_icon_name("document-open-symbolic")
        image_refresh.set_pixel_size(16)
        self.edit_btn = Gtk.Button.new()
        btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        btn_content.append(image_refresh)
        btn_content.append(Gtk.Label(label="Edit Selected"))
        self.edit_btn.set_child(btn_content)  
        self.edit_btn.connect("clicked", self.app.on_edit_clicked)
        self.edit_btn.set_sensitive(False)
        btn_box.append(self.edit_btn)

        self.grid.attach(btn_box, 0, 2, 5, 1)

    def create_status_bar(self):
        self.status_bar = Gtk.Statusbar()
        # Configure and add the status bar (Statusbar widget)
        self.status_bar.set_hexpand(True)
        self.status_bar.set_halign(Gtk.Align.START)

        # Attach to grid
        self.grid.attach(self.status_bar, 0, 3, 5, 1)

    def on_selection_changed(self, selection):
        model, paths = selection.get_selected_rows()
        num_selected = len(paths)  # Now this gives the correct count
        self.edit_btn.set_sensitive(num_selected == 1)
        self.delete_btn.set_sensitive(num_selected >= 1)

    def calendar_dialog(self, widget):
            from .dialogs import on_due_date_clicked
            on_due_date_clicked(widget, self.calendar_icon)
            print ()

    def init_styling(self):
        self.root_dir = os.getenv("ROOT_DIR", os.path.expanduser("~/.config/nctasks_split"))
        css_provider = Gtk.CssProvider()
        try:
            css_path = os.path.join(self.root_dir, 'style.css')
            css_provider.load_from_path(css_path)
            # GTK4 changes: use add_provider_for_display with Gdk.Display
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print(f"Error loading CSS: {e}")
    
class TaskItem(GObject.Object):
    __gtype_name__ = 'TaskItem'
    
    def __init__(self, uid, task, priority, status, due):
        super().__init__()
        self.uid = uid
        self.task = task
        self.priority = priority
        self.status = status
        self.due = due


# Now when adding tasks, use:
# new_item = TaskItem(uid, task, priority, status, due)
# self.task_store.append(new_item)


class MyApp(Gtk.Application):

    def __init__(self):
        super().__init__(application_id="com.sickmitch.NCTasks")

    def do_activate(self):
        win = Window(self)
        win.present()

if __name__ == "__main__":
    app = MyApp()
    app.run()