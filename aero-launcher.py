#!/usr/bin/env python3
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from aero_css import CSS


class AppLauncher(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Aplicativos")
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
            self.set_app_paintable(True)
        self.get_style_context().add_class("launcher-toplevel")
        self.set_default_size(620, 680)
        self.set_resizable(True)
        self.set_decorated(False)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.connect("key-press-event", self._key_pressed)
        self.connect("delete-event", self._close)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        panel.get_style_context().add_class("launcher-window")
        self.add(panel)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label="Aplicativos", xalign=0)
        title.get_style_context().add_class("launcher-title")
        title.set_hexpand(True)
        self.count = Gtk.Label()
        self.count.get_style_context().add_class("launcher-count")
        close = Gtk.Button.new_with_label("Fechar")
        close.get_style_context().add_class("icon-btn")
        close.connect("clicked", self._close)
        header.pack_start(title, True, True, 0)
        header.pack_start(self.count, False, False, 0)
        header.pack_start(close, False, False, 0)
        panel.pack_start(header, False, False, 0)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Buscar aplicativo pelo nome")
        self.search.connect("search-changed", self._filter_changed)
        self.search.connect("activate", self._launch_selected)
        panel.pack_start(self.search, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.get_style_context().add_class("launcher-scroll")
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(False)
        self.listbox.set_filter_func(self._filter_row)
        self.listbox.connect("row-activated", self._row_activated)
        scroller.add(self.listbox)
        panel.pack_start(scroller, True, True, 0)

        self.apps = []
        self._load_apps()
        self.show_all()
        self.search.grab_focus()
        self.listbox.select_row(self.listbox.get_row_at_index(0))

    def _load_apps(self):
        app_infos = [app for app in Gio.AppInfo.get_all() if app.should_show() and app.get_name()]
        app_infos.sort(key=lambda app: app.get_name().casefold())
        seen = set()
        for app in app_infos:
            app_id = app.get_id() or app.get_name()
            if app_id in seen:
                continue
            seen.add(app_id)
            name = app.get_name()
            description = app.get_description() or app.get_executable() or "Aplicativo"
            icon = Gtk.Image.new_from_gicon(app.get_icon(), Gtk.IconSize.DIALOG) if app.get_icon() else Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DIALOG)
            icon.set_pixel_size(38)
            icon_box = Gtk.Box()
            icon_box.get_style_context().add_class("app-icon")
            icon_box.set_size_request(54, 54)
            icon_box.set_halign(Gtk.Align.CENTER)
            icon_box.set_valign(Gtk.Align.CENTER)
            icon_box.pack_start(icon, True, True, 0)

            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            name_label = Gtk.Label(label=name, xalign=0)
            name_label.get_style_context().add_class("app-name")
            name_label.set_ellipsize(3)
            description_label = Gtk.Label(label=description, xalign=0)
            description_label.get_style_context().add_class("app-description")
            description_label.set_ellipsize(3)
            labels.pack_start(name_label, False, False, 0)
            labels.pack_start(description_label, False, False, 0)

            row_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_content.get_style_context().add_class("app-row-content")
            row_content.pack_start(icon_box, False, False, 0)
            row_content.pack_start(labels, True, True, 0)
            row = Gtk.ListBoxRow()
            row.get_style_context().add_class("app-row")
            row.add(row_content)
            row.app_info = app
            row.search_text = " ".join((name, description, app_id)).casefold()
            self.listbox.add(row)
            self.apps.append(row)

        self.count.set_text("%d aplicativos" % len(self.apps))

    def _filter_row(self, row):
        query = self.search.get_text().strip().casefold()
        return not query or query in row.search_text

    def _filter_changed(self, *_args):
        self.listbox.invalidate_filter()
        first = self.listbox.get_row_at_index(0)
        if first:
            self.listbox.select_row(first)
        self.count.set_text("%d encontrados" % sum(row.get_child_visible() for row in self.apps))

    def _launch_selected(self, *_args):
        row = self.listbox.get_selected_row() or self.listbox.get_row_at_index(0)
        if row:
            self._launch(row)

    def _row_activated(self, _listbox, row):
        self._launch(row)

    def _launch(self, row):
        try:
            row.app_info.launch([], None)
        except GLib.Error as error:
            print("Nao foi possivel abrir %s: %s" % (row.app_info.get_name(), error), file=sys.stderr)
            return
        self.get_application().quit()

    def _key_pressed(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self._close()
            return True
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._launch_selected()
            return True
        if event.keyval == Gdk.KEY_Down and self.search.has_focus():
            self.listbox.grab_focus()
            row = self.listbox.get_selected_row() or self.listbox.get_row_at_index(0)
            if row:
                self.listbox.select_row(row)
            return True
        if event.keyval == Gdk.KEY_Up and self.listbox.has_focus():
            self.search.grab_focus()
            return True
        return False

    def _close(self, *_args):
        self.hide()
        self.get_application().quit()
        return True


class LauncherApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="org.ultimadesk.AppLauncher",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.window = None

    def do_command_line(self, _command_line):
        if self.window and self.window.get_visible():
            self.window.hide()
            self.quit()
            return 0
        self.window = AppLauncher(self)
        self.window.present()
        return 0


def load_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


if __name__ == "__main__":
    load_css()
    raise SystemExit(LauncherApplication().run(sys.argv))
