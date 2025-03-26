from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, Gdk
import os

class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("NCTasks")
        self.set_size_request(750, 500)  
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
        
    ### GENERATE UI UP TO DOWN 
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
        #PRIO
        self.priority_combo = Gtk.ComboBoxText()
        for priority in ["Priority", "Low", "Medium", "High"]:
            self.priority_combo.append_text(priority)
        self.priority_combo.set_active(0)
        priority_renderer = self.priority_combo.get_cells()[0]
        priority_renderer.set_property("xalign", 0.5)
        input_box.append(self.priority_combo)
        #STATUS
        self.status_combo = Gtk.ComboBoxText()
        for status in ["Status", "Todo", "Started"]:
            self.status_combo.append_text(status)
        self.status_combo.set_active(0)
        status_renderer = self.status_combo.get_cells()[0]
        status_renderer.set_property("xalign", 0.5)
        input_box.append(self.status_combo)
        # DUE
        self.due_button = Gtk.Button()
        self.due_button.set_size_request(110, -1)
        self.due_stack = Gtk.Stack()
        self.due_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)  # Optional animation        
        icon = Gtk.Image.new_from_icon_name("org.gnome.Calendar")
        self.date_label = Gtk.Label()
        self.due_stack.add_named(icon, "icon")
        self.due_stack.add_named(self.date_label, "date")
        self.due_stack.set_visible_child_name("icon")  # Initial state
        self.due_button.set_child(self.due_stack)
        self.due_button.connect("clicked", on_due_date_clicked, self.due_button, self.due_stack, self.date_label)
        input_box.append(self.due_button)
        # ADD/EDIT
        self.add_button = Gtk.Button()
        self.add_button.set_size_request(80, -1)
        self.add_stack = Gtk.Stack()
        self.add_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)  # Optional animation        
        add = Gtk.Image.new_from_icon_name("list-add-symbolic")
        edit = Gtk.Image.new_from_icon_name("edit-symbolic")
        self.add_stack.add_named(add, "add")
        self.add_stack.add_named(edit, "edit")
        self.add_stack.set_visible_child_name("add")  # Initial state
        self.add_button.set_child(self.add_stack)
        self.add_button.connect("clicked", self.on_stack_clicked, self.add_stack)
        input_box.append(self.add_button)
    
    def on_stack_clicked(self, widget, stack):
        active=stack.get_visible_child_name()
        if active == "add":
            self.action="add"
        else:
            self.action="edit"
        self.app.stack_handler(self.action)

    def create_task_list(self):
        self.scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.app.task_list = Gtk.ListStore(str, str, str, str, str)
        self.treeview = Gtk.TreeView(model=self.app.task_list)
        self.treeview.set_column_spacing(10) 
        # Enable multiple selection
        selection = self.treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect("changed", self.on_selection_changed)
        # Configure columns
        columns = [
            ("Task", 1, True),
            ("Priority", 2, False),
            ("Status", 3, False),
            ("Due", 4, False)
        ]
        for i, (title, col_id, expand) in enumerate(columns):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=col_id)
            column.set_expand(expand)  # Allow only "Task" to expand
            column.set_resizable(True)  # Allow resizing manually
            self.treeview.append_column(column)
        self.treeview.set_headers_visible(False)
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
        ##EDIT BUTTONEdit Selected
        ##SECONDARY TASK BUTTON
        image_refresh = Gtk.Image.new_from_icon_name("document-save-symbolic")
        image_refresh.set_pixel_size(16)
        self.edit_btn = Gtk.Button.new()
        btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        btn_content.append(image_refresh)
        btn_content.append(Gtk.Label(label="Add Secondary Task"))
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

    ### MANAGE SELECTION CHANGES
    def on_selection_changed(self, selection):
        model, paths = selection.get_selected_rows()
        num_selected = len(paths)  # Now this gives the correct count
        self.edit_btn.set_sensitive(num_selected == 1)
        self.delete_btn.set_sensitive(num_selected >= 1)

    ### CSS PROVIDER
    def init_styling(self):
        self.root_dir = os.path.dirname(__file__)
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