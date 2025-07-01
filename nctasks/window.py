from gi import require_versions
require_versions({"Gtk": "4.0", "Adw": "1"})
from gi.repository import Gtk, Gdk, GObject, Gio, Pango, GLib
import os
import re

    # Create a custom list item class to hold task data
class TaskObject(GObject.Object):
    __gtype_name__ = 'TaskObject'
    uid = GObject.Property(type=str)
    task = GObject.Property(type=str)
    priority = GObject.Property(type=str)
    status = GObject.Property(type=str)
    due = GObject.Property(type=str)
    description = GObject.Property(type=str)

class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title("NCTasks")
        self.set_size_request(750, 500)  
        self.app = app
        self.grid = Gtk.Grid(
            column_spacing=5,
            row_spacing=5,
            margin_start=10,
            margin_end=10,
            margin_top=10,
            margin_bottom=10
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
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, hexpand=True, vexpand=False, halign=Gtk.Align.FILL, valign=Gtk.Align.FILL)
        self.grid.attach(input_box, 0, 0, 5, 1)
        # Vertical box for summary and description (expand as much as possible)
        entry_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, vexpand=True, halign=Gtk.Align.FILL, valign=Gtk.Align.FILL)
        self.task_entry = Gtk.Entry(
            placeholder_text="Task summary",
            hexpand=True,
            halign=Gtk.Align.FILL,
            xalign=0.5,
            vexpand=True,
            valign=Gtk.Align.FILL
        )
        entry_vbox.append(self.task_entry)
        self.description_entry = Gtk.Entry(
            placeholder_text="Task description (optional)",
            hexpand=True,
            halign=Gtk.Align.FILL,
            xalign=0.5,
            vexpand=True,
            valign=Gtk.Align.FILL
        )
        entry_vbox.append(self.description_entry)
        input_box.append(entry_vbox)
        # Priority and Status stacked vertically (do not expand)
        prio_status_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=False, vexpand=True, halign=Gtk.Align.END, valign=Gtk.Align.FILL)
        self.priority_combo = Gtk.ComboBoxText(hexpand=False, halign=Gtk.Align.FILL)
        for priority in ["Priority", "Low", "Medium", "High"]:
            self.priority_combo.append_text(priority)
        self.priority_combo.set_active(0)
        priority_renderer = self.priority_combo.get_cells()[0]
        priority_renderer.set_property("xalign", 0.5)
        prio_status_vbox.append(self.priority_combo)
        self.status_combo = Gtk.ComboBoxText(hexpand=False, halign=Gtk.Align.FILL)
        for status in ["Status", "Todo", "Started"]:
            self.status_combo.append_text(status)
        self.status_combo.set_active(0)
        status_renderer = self.status_combo.get_cells()[0]
        status_renderer.set_property("xalign", 0.5)
        prio_status_vbox.append(self.status_combo)
        input_box.append(prio_status_vbox)
        # Due and Add button stacked vertically (make as compact as possible)
        due_add_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=False, vexpand=True, halign=Gtk.Align.END, valign=Gtk.Align.FILL)
        self.due_button = Gtk.Button()
        self.due_button.set_size_request(40, -1)  # Smaller width
        self.due_stack = Gtk.Stack()
        self.due_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        icon = Gtk.Image.new_from_icon_name("org.gnome.Calendar")
        self.date_label = Gtk.Label()
        self.due_stack.add_named(icon, "icon")
        self.due_stack.add_named(self.date_label, "date")
        self.due_stack.set_visible_child_name("icon")
        self.due_button.set_child(self.due_stack)
        self.due_button.connect("clicked", on_due_date_clicked, self.due_button, self.due_stack, self.date_label)
        due_add_vbox.append(self.due_button)
        self.add_button = Gtk.Button()
        self.add_button.set_size_request(40, -1)  # Smaller width
        self.add_stack = Gtk.Stack()
        self.add_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        add = Gtk.Image.new_from_icon_name("list-add-symbolic")
        edit = Gtk.Image.new_from_icon_name("document-send-symbolic")
        self.add_stack.add_named(add, "add")
        self.add_stack.add_named(edit, "edit")
        self.add_stack.set_visible_child_name("add")
        self.add_button.set_child(self.add_stack)
        self.add_button.connect("clicked", self.on_stack_clicked, self.add_stack)
        due_add_vbox.append(self.add_button)
        input_box.append(due_add_vbox)
        # Connect task_entry activate to add/edit
        self.task_entry.connect("activate", self.on_stack_clicked, self.add_stack)
        self.initial_values = {
            "task_entry": self.task_entry.get_text(),
            "priority": self.priority_combo.get_active_text(),
            "status": self.status_combo.get_active_text(),
            "due": self.due_stack.get_visible_child_name(),
        }
        self.state_changed = False
        GLib.timeout_add(500, self.watch_for_changes)

    def watch_for_changes(self):
        current_values = {
            "task_entry": self.task_entry.get_text(),
            "priority": self.priority_combo.get_active_text(),
            "status": self.status_combo.get_active_text(),
            "due": self.due_stack.get_visible_child_name(),
        }
        if current_values != self.initial_values:
            self.state_changed = True
        else:
            self.state_changed = False
        self.reset_btn.set_visible(self.state_changed)
        return True  # Keep the timer running

    def on_stack_clicked(self, widget, stack):
        active=stack.get_visible_child_name()
        if active == "add":
            self.action="add"
        else:
            self.action="edit"
        self.app.stack_handler(self.action)


    def create_task_list(self):
        self.scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.app.task_list = Gio.ListStore(item_type=TaskObject)

        # Create ColumnView with multi-selection
        self.column_view = Gtk.ColumnView(
            model=Gtk.MultiSelection.new(self.app.task_list),
            show_row_separators=True,
            show_column_separators=True
        )

        # Add double-click event handler
        self.column_view.connect("activate", self.on_row_activated)

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
        # Use a vertical box to show summary and description
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        summary_label = Gtk.Label(xalign=0)
        summary_label.set_ellipsize(Pango.EllipsizeMode.END)
        summary_label.set_use_markup(True)
        description_label = Gtk.Label(xalign=0)
        description_label.set_ellipsize(Pango.EllipsizeMode.END)
        description_label.set_use_markup(True)
        description_label.get_style_context().add_class("dim-label")  # For lighter font
        vbox.append(summary_label)
        vbox.append(description_label)
        list_item.set_child(vbox)

    def _on_factory_bind(self, property_name):
        def bind_handler(factory, list_item):
            vbox = list_item.get_child()
            summary_label = vbox.get_first_child()
            description_label = vbox.get_last_child()
            obj = list_item.get_item()
            label_text = obj.get_property(property_name) or ""
            description = obj.get_property("description") or ""

            if property_name == 'task':
                match = re.match(r"(\s*󰳟\s*)?(.*)", label_text)
                if match:
                    prefix = match.group(1) or ""
                    summary = match.group(2) or ""
                else:
                    prefix = ""
                    summary = label_text
                is_high_priority = hasattr(obj, 'priority') and obj.get_property('priority') == 'High'
                is_collapsed = hasattr(obj, 'is_parent') and obj.is_parent and hasattr(obj, 'is_collapsed') and obj.is_collapsed
                summary_markup = summary
                if is_high_priority and is_collapsed:
                    summary_markup = f'<u><b>{summary}</b></u>'
                elif is_high_priority:
                    summary_markup = f'<b>{summary}</b>'
                elif is_collapsed:
                    summary_markup = f'<u>{summary}</u>'
                markup = f'{prefix}{summary_markup}'
                summary_label.set_markup(markup)
                # Show description below summary, smaller and lighter
                if description:
                    description_label.set_markup(f'<span size="small" foreground="#888">{description}</span>')
                    description_label.set_visible(True)
                else:
                    description_label.set_visible(False)
            else:
                summary_label.set_text(label_text)
                description_label.set_visible(False)

        return bind_handler

    def on_selection_changed(self, selection, position, n_items):
        num_selected = selection.get_selection().get_size()  # Use get_size() for Bitset

        self.edit_btn.set_sensitive(num_selected == 1)
        self.edit_btn.set_visible(num_selected == 1)
        self.secondary_btn.set_sensitive(num_selected == 1)
        self.secondary_btn.set_visible(num_selected == 1)
        self.walker_btn.set_sensitive(num_selected >= 1)
        self.complete_btn.set_visible(num_selected >= 1)
        self.complete_btn.set_sensitive(num_selected >= 1)
        self.walker_btn.set_visible(num_selected >= 1)
        self.delete_btn.set_sensitive(num_selected >= 1)
        self.delete_btn.set_visible(num_selected >= 1)

    def create_action_buttons(self):
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        # Helper function to create buttons with Unicode icons
        def create_button(label, icon, callback, visible=True, sensitive=True):
            icon_label = Gtk.Label(label=icon)
            icon_label.set_margin_end(5)  # Add spacing

            btn = Gtk.Button.new()
            btn_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            btn_content.append(icon_label)
            btn_content.append(Gtk.Label(label=label))

            btn.set_child(btn_content)
            btn.connect("clicked", callback)
            btn.set_visible(visible)
            btn.set_sensitive(sensitive)
            btn_box.append(btn)
            return btn

        # Create buttons with Unicode icons
        self.sync_btn = create_button("Sync", "", self.app.on_sync_clicked)
        self.delete_btn = create_button("Delete", "󰺝", self.app.on_del_clicked, visible=False, sensitive=False)
        self.edit_btn = create_button("Edit", "", self.app.on_edit_clicked, visible=False, sensitive=False)
        self.secondary_btn = create_button("Add Secondary", "󱞪", self.app.on_secondary_clicked, visible=False, sensitive=False)
        self.reset_btn = create_button("Reset", "󰁯", self.app.reset_input, visible=False)
        self.walker_btn = create_button("Progress", "", self.app.walker_clicked, visible=False)
        self.complete_btn = create_button("Complete", "", self.app.complete_clicked, visible=False)

        self.grid.attach(btn_box, 0, 2, 5, 1)

    ### STATUS BAR
    def create_status_bar(self):
        self.status_bar = Gtk.Statusbar()
        self.spinner = Gtk.Spinner()
        self.status_container = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, 
            spacing=5
        )
        # Append widgets to the Box
        self.status_container.append(self.spinner)
        self.status_container.append(self.status_bar)
        # Configure expand properties
        self.spinner.set_hexpand(False)
        self.status_bar.set_hexpand(True)
        self.grid.attach(self.status_container, 0, 3, 5, 1)

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
    
    def on_row_activated(self, column_view, position):
        # Get the activated item
        model = column_view.get_model()
        item = model.get_item(position)
        if hasattr(item, 'is_parent') and item.is_parent:
            self.app.toggle_collapse(item.uid)

class MyApp(Gtk.Application):

    def __init__(self):
        super().__init__(application_id="com.sickmitch.NCTasks")

    def do_activate(self):
        win = Window(self)
        win.present()

if __name__ == "__main__":
    app = MyApp()
    app.run()