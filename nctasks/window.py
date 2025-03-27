from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, Gdk, GObject, Gio, Pango
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
        edit = Gtk.Image.new_from_icon_name("document-send-symbolic")
        self.add_stack.add_named(add, "add")
        self.add_stack.add_named(edit, "edit")
        self.add_stack.set_visible_child_name("add")  # Initial state
        self.add_button.set_child(self.add_stack)
        self.add_button.connect("clicked", self.on_stack_clicked, self.add_stack)
        input_box.append(self.add_button)
        ## Is here cos add_stack need to be defined before
        self.task_entry.connect("activate", self.on_stack_clicked, self.add_stack)
    
    def on_stack_clicked(self, widget, stack):
        active=stack.get_visible_child_name()
        if active == "add":
            self.action="add"
        else:
            self.action="edit"
        self.app.stack_handler(self.action)

    # Create a custom list item class to hold task data
    class TaskObject(GObject.Object):
        __gtype_name__ = 'TaskObject'
        uid = GObject.Property(type=str)
        task = GObject.Property(type=str)
        priority = GObject.Property(type=str)
        status = GObject.Property(type=str)
        due = GObject.Property(type=str)

    def create_task_list(self):
        self.scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.app.task_list = Gio.ListStore(item_type=self.TaskObject)

        # Create ColumnView with multi-selection
        self.column_view = Gtk.ColumnView(
            model=Gtk.MultiSelection.new(self.app.task_list),
            show_row_separators=True,
            show_column_separators=True
        )

        # Create columns with spacing
        columns = [
            ("Task", "task", True),
            ("Priority", "priority", False),
            ("Status", "status", False),
            ("Due", "due", False)
        ]

        for title, property_name, expand in columns:
            # Create column with title
            column = Gtk.ColumnViewColumn(title=None)

            # Create factory for cell renderers
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._on_factory_setup)
            factory.connect("bind", self._on_factory_bind(property_name))

            column.set_factory(factory)
            column.set_expand(expand)
            column.set_resizable(True)
            self.column_view.append_column(column)

        # Configure selection
        self.column_view.get_model().connect("selection-changed", self.on_selection_changed)


        table_header: Gtk.ListItemWidget = self.column_view.get_first_child()
        table_header.set_visible(False)

        self.scrolled_window.set_child(self.column_view)
        self.grid.attach(self.scrolled_window, 0, 1, 5, 1)

    def _on_factory_setup(self, factory, list_item):
        label = Gtk.Label(xalign=0)  # Align text to left
        label.set_ellipsize(Pango.EllipsizeMode.END)  # Prevent text overflow
        list_item.set_child(label)

    def _on_factory_bind(self, property_name):
        def bind_handler(factory, list_item):
            label = list_item.get_child()
            obj = list_item.get_item()
            label.set_text(obj.get_property(property_name) or "")
        return bind_handler

    def on_selection_changed(self, selection, position, n_items):
        num_selected = selection.get_selection().get_size()  # Use get_size() for Bitset

        self.edit_btn.set_sensitive(num_selected == 1)
        self.secondary_btn.set_sensitive(num_selected == 1)
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
        image_refresh = Gtk.Image.new_from_icon_name("document-edit-symbolic")
        image_refresh.set_pixel_size(16)
        self.edit_btn = Gtk.Button.new()
        btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        btn_content.append(image_refresh)
        btn_content.append(Gtk.Label(label="Edit Task"))
        self.edit_btn.set_child(btn_content)  
        self.edit_btn.connect("clicked", self.app.on_edit_clicked)
        self.edit_btn.set_sensitive(False)
        btn_box.append(self.edit_btn)
        ##SECONDARY TASK BUTTON
        image_refresh = Gtk.Image.new_from_icon_name("document-save-symbolic")
        image_refresh.set_pixel_size(16)
        self.secondary_btn = Gtk.Button.new()
        btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        btn_content.append(image_refresh)
        btn_content.append(Gtk.Label(label="Add Secondary Task"))
        self.secondary_btn.set_child(btn_content)  
        self.secondary_btn.connect("clicked", self.app.on_secondary_clicked)
        self.secondary_btn.set_sensitive(False)
        btn_box.append(self.secondary_btn)
        self.grid.attach(btn_box, 0, 2, 5, 1)

    def create_status_bar(self):
        self.status_bar = Gtk.Statusbar()
        # Configure and add the status bar (Statusbar widget)
        self.status_bar.set_hexpand(True)
        self.status_bar.set_halign(Gtk.Align.START)
        # Attach to grid
        self.grid.attach(self.status_bar, 0, 3, 5, 1)

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