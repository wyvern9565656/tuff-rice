#!/usr/bin/env python3
import json
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from aero_css import CSS
from aero_window import float_current_window


WORKSPACES = 9
UTILITY_CLASSES = {"aero-shell.py", "aero-launcher.py", "aero-workspaces.py"}


def hyprctl(*args):
    result = subprocess.run(
        ["hyprctl", *args], capture_output=True, text=True, check=True, timeout=3
    )
    return result.stdout


class WorkspaceOverview(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Janelas e workspaces")
        self.set_default_size(700, 680)
        self.set_resizable(True)
        self.set_decorated(False)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.connect("key-press-event", self._key_pressed)
        self.connect("delete-event", self._close)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        panel.get_style_context().add_class("overview-window")
        panel.set_border_width(18)
        self.add(panel)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        heading = Gtk.Label(label="Janelas abertas", xalign=0)
        heading.get_style_context().add_class("overview-title")
        heading.set_hexpand(True)
        self.count = Gtk.Label()
        self.count.get_style_context().add_class("launcher-count")
        close = Gtk.Button.new_with_label("Fechar")
        close.get_style_context().add_class("icon-btn")
        close.connect("clicked", self._close)
        header.pack_start(heading, True, True, 0)
        header.pack_start(self.count, False, False, 0)
        header.pack_start(close, False, False, 0)
        panel.pack_start(header, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.get_style_context().add_class("overview-scroll")
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", self._activate_row)
        scroller.add(self.listbox)
        panel.pack_start(scroller, True, True, 0)

        self._populate()
        self.show_all()
        GLib.timeout_add(180, float_current_window, "aero-workspaces.py")

    def _populate(self):
        active = json.loads(hyprctl("activeworkspace", "-j"))["id"]
        clients = [
            client for client in json.loads(hyprctl("clients", "-j"))
            if client.get("class") not in UTILITY_CLASSES
        ]
        grouped = {workspace: [] for workspace in range(1, WORKSPACES + 1)}
        for client in clients:
            workspace = client.get("workspace", {}).get("id")
            if isinstance(workspace, int):
                grouped.setdefault(workspace, []).append(client)

        for workspace in sorted(grouped):
            windows = grouped[workspace]
            heading = Gtk.Label(label="Workspace %d%s  |  %d janelas" % (
                workspace, "  -  atual" if workspace == active else "", len(windows)
            ), xalign=0)
            heading.get_style_context().add_class("workspace-heading")
            header_row = Gtk.ListBoxRow()
            header_row.set_selectable(False)
            header_row.set_activatable(False)
            header_row.add(heading)
            self.listbox.add(header_row)

            if not windows:
                empty = Gtk.Label(label="Vazio", xalign=0)
                empty.get_style_context().add_class("workspace-empty")
                empty.set_margin_start(12)
                empty_row = Gtk.ListBoxRow()
                empty_row.set_selectable(False)
                empty_row.set_activatable(False)
                empty_row.add(empty)
                self.listbox.add(empty_row)
                continue

            for client in sorted(windows, key=lambda item: (not item.get("focusHistoryID", 0), item.get("title", "").casefold())):
                title = client.get("title") or client.get("class") or "Janela"
                app_class = client.get("class") or "Aplicativo"
                icon = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DIALOG)
                icon.set_pixel_size(28)
                labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                title_label = Gtk.Label(label=title, xalign=0)
                title_label.get_style_context().add_class("app-name")
                title_label.set_ellipsize(3)
                app_label = Gtk.Label(label=app_class, xalign=0)
                app_label.get_style_context().add_class("app-description")
                labels.pack_start(title_label, False, False, 0)
                labels.pack_start(app_label, False, False, 0)
                content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                content.get_style_context().add_class("overview-row-content")
                content.pack_start(icon, False, False, 0)
                content.pack_start(labels, True, True, 0)
                row = Gtk.ListBoxRow()
                row.get_style_context().add_class("overview-row")
                row.add(content)
                row.workspace_id = workspace
                row.address = client.get("address", "")
                self.listbox.add(row)

        self.count.set_text("%d janelas abertas" % len(clients))

    def _activate_row(self, _listbox, row):
        workspace = getattr(row, "workspace_id", None)
        if workspace is None:
            return
        self.listbox.set_sensitive(False)
        GLib.timeout_add(180, self._finish_activation, workspace, getattr(row, "address", ""))

    def _finish_activation(self, workspace, address):
        subprocess.run(["hyprctl", "dispatch", "workspace", str(workspace)], check=True, timeout=2)
        if address:
            subprocess.run(["hyprctl", "dispatch", "focuswindow", "address:" + address], check=True, timeout=2)
        self._close()
        return GLib.SOURCE_REMOVE

    def _key_pressed(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self._close()
            return True
        return False

    def _close(self, *_args):
        self.hide()
        self.get_application().quit()
        return True


class OverviewApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="org.ultimadesk.WorkspaceOverview",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.window = None

    def do_command_line(self, _command_line):
        if self.window and self.window.get_visible():
            self.window.hide()
            self.quit()
            return 0
        self.window = WorkspaceOverview(self)
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
    raise SystemExit(OverviewApplication().run(sys.argv))
