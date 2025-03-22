from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, GObject, Gdk
import os

class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("NCTasks")
        self.set_size_request(625, 500)  
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
            hexpand=True,
            halign=Gtk.Align.FILL,
            xalign=0.5  
        )
        input_box.append(self.task_entry)
        
        #STATUS
        self.status_combo = Gtk.ComboBoxText()
        for status in ["Todo", "Started"]:
            self.status_combo.append_text(status)
        self.status_combo.set_active(0)
        status_renderer = self.status_combo.get_cells()[0]
        status_renderer.set_property("xalign", 0.5)
        input_box.append(self.status_combo)

        #PRIO
        self.priority_combo = Gtk.ComboBoxText()
        for priority in ["Low", "Medium", "High"]:
            self.priority_combo.append_text(priority)
        self.priority_combo.set_active(0)
        priority_renderer = self.priority_combo.get_cells()[0]
        priority_renderer.set_property("xalign", 0.5)
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

        # ADD
        self.add_btn = Gtk.Button(label="Add Task", icon_name="list-add-symbolic")
        self.add_btn.connect("clicked", self.app.on_add_clicked)
        input_box.append(self.add_btn)

    def create_task_list(self):
        self.scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.listbox.connect("selected-rows-changed", self.on_selection_changed)
        self.scrolled_window.set_child(self.listbox)
        self.grid.attach(self.scrolled_window, 0, 1, 5, 1)
        
    def populate_listbox(self):
        while True:
            row = self.listbox.get_row_at_index(0)
            if row is None:
                break
            self.listbox.remove(row)

        for task in self.app.task_list:
            uid, summary, priority, status, due = task
            row = Gtk.ListBoxRow()
            row.uid = uid

            grid = Gtk.Grid(column_spacing=10, margin_start=5, margin_end=5)

            labels = [
                Gtk.Label(label=summary, xalign=0),
                Gtk.Label(label=priority, xalign=0.5),
                Gtk.Label(label=status, xalign=0.5),
                Gtk.Label(label=due, xalign=1)
            ]

            # Apply alignment and expansion
            alignments = [Gtk.Align.START, Gtk.Align.CENTER, Gtk.Align.CENTER, Gtk.Align.END]

            for i, (label, align) in enumerate(zip(labels, alignments)):
                label.set_halign(align)
                label.set_hexpand(True)
                grid.attach(label, i, 0, 1, 1)

            row.set_child(grid)
            self.listbox.append(row)

        self.listbox.queue_draw()

    def on_selection_changed(self, listbox):
        selected_rows = listbox.get_selected_rows()
        num_selected = len(selected_rows)
        self.edit_btn.set_sensitive(num_selected == 1)
        self.delete_btn.set_sensitive(num_selected >= 1)

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
    

class MyApp(Gtk.Application):

    def __init__(self):
        super().__init__(application_id="com.sickmitch.NCTasks")

    def do_activate(self):
        win = Window(self)
        win.present()

if __name__ == "__main__":
    app = MyApp()
    app.run()