#!/usr/bin/env python3
import os
import subprocess
import sys
import threading
from urllib.request import Request, urlopen

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from aero_css import CSS


class PlayerWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="UltimaDesk Player")
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
            self.set_app_paintable(True)
        self.get_style_context().add_class("player-window")
        self.set_default_size(342, 470)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.connect("delete-event", self._close)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        panel.get_style_context().add_class("player-panel")
        panel.set_border_width(0)
        self.add(panel)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        heading = Gtk.Label(label="Reproduzindo agora", xalign=0)
        heading.get_style_context().add_class("player-heading")
        heading.set_hexpand(True)
        close = Gtk.Button.new_with_label("\uf00d")
        close.get_style_context().add_class("icon-btn")
        close.set_tooltip_text("Fechar player")
        close.connect("clicked", self._close)
        header.pack_start(heading, True, True, 0)
        header.pack_start(close, False, False, 0)
        panel.pack_start(header, False, False, 0)

        self.title = self._track_label("player-track-title")
        self.artist = self._track_label("player-track-artist")
        self.album = self._track_label("player-track-album")
        panel.pack_start(self.title, False, False, 0)
        panel.pack_start(self.artist, False, False, 0)
        panel.pack_start(self.album, False, False, 0)

        self.cover = Gtk.Image.new_from_icon_name("audio-x-generic", Gtk.IconSize.DIALOG)
        self.cover.set_pixel_size(176)
        self.cover_frame = Gtk.Frame()
        self.cover_frame.get_style_context().add_class("player-cover")
        self.cover_frame.set_size_request(190, 190)
        self.cover_frame.set_halign(Gtk.Align.CENTER)
        self.cover_frame.add(self.cover)
        panel.pack_start(self.cover_frame, False, False, 2)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls.set_halign(Gtk.Align.CENTER)
        self.previous = self._control_button("\uf04a", "Faixa anterior", "previous")
        self.toggle = self._control_button("\uf04c", "Reproduzir ou pausar", "play-pause")
        self.next = self._control_button("\uf04e", "Proxima faixa", "next")
        for button in (self.previous, self.toggle, self.next):
            controls.pack_start(button, False, False, 0)
        panel.pack_start(controls, False, False, 2)

        volume_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        volume_icon = Gtk.Label(label="\uf028")
        volume_icon.get_style_context().add_class("player-volume-icon")
        self.volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume.set_draw_value(False)
        self.volume.set_hexpand(True)
        self.volume.connect("value-changed", self._volume_changed)
        self.volume_value = Gtk.Label(label="--%")
        self.volume_value.set_size_request(38, -1)
        volume_row.pack_start(volume_icon, False, False, 0)
        volume_row.pack_start(self.volume, True, True, 0)
        volume_row.pack_start(self.volume_value, False, False, 0)
        panel.pack_start(volume_row, False, False, 0)

        self.art_url = None
        self.updating = False
        self.volume_timeout = 0
        self.refresh_source = 0
        self._open()

    def _open(self):
        self.show_all()
        self.present()
        self.refresh()
        if not self.refresh_source:
            self.refresh_source = GLib.timeout_add_seconds(5, self.refresh)

    def _track_label(self, style_class):
        label = Gtk.Label(xalign=0.5)
        label.set_ellipsize(3)
        label.set_width_chars(24)
        label.set_max_width_chars(28)
        label.get_style_context().add_class(style_class)
        return label

    def _control_button(self, icon, tooltip, action):
        button = Gtk.Button.new_with_label(icon)
        button.get_style_context().add_class("player-control")
        button.set_tooltip_text(tooltip)
        button.connect("clicked", lambda *_args: self._run_player(action))
        return button

    def _player(self, *args):
        return subprocess.run(
            ["playerctl", *args], capture_output=True, text=True, check=True, timeout=2
        ).stdout.strip()

    def _run_player(self, action):
        try:
            subprocess.run(["playerctl", action], check=False, timeout=2)
        except (OSError, subprocess.SubprocessError):
            pass
        self.refresh()

    def _volume_changed(self, scale):
        if self.updating:
            return
        value = int(scale.get_value())
        self.volume_value.set_text("%d%%" % value)

        if self.volume_timeout:
            GLib.source_remove(self.volume_timeout)
        self.volume_timeout = GLib.timeout_add(180, self._apply_volume, value)

    def _apply_volume(self, value):
        self.volume_timeout = 0
        try:
            subprocess.run(["playerctl", "volume", "%.2f" % (value / 100)], check=False, timeout=2)
        except (OSError, subprocess.SubprocessError):
            pass
        return GLib.SOURCE_REMOVE

    def _load_cover(self, url):
        try:
            request = Request(url, headers={"User-Agent": "UltimaDesk/1.0"})
            with urlopen(request, timeout=5) as response:
                image_data = response.read(8 * 1024 * 1024)
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf().scale_simple(176, 176, GdkPixbuf.InterpType.BILINEAR)
            GLib.idle_add(self._apply_cover, url, pixbuf)
        except Exception:
            GLib.idle_add(self._apply_cover, url, None)

    def _apply_cover(self, url, pixbuf):
        if self.art_url == url:
            if pixbuf:
                self.cover.set_from_pixbuf(pixbuf)
            else:
                self.cover.set_from_icon_name("audio-x-generic", Gtk.IconSize.DIALOG)
                self.cover.set_pixel_size(176)
        return GLib.SOURCE_REMOVE

    def refresh(self):
        try:
            status = self._player("status")
            metadata = self._player(
                "metadata", "--format", "{{title}}\n{{artist}}\n{{album}}\n{{mpris:artUrl}}"
            ).split("\n", 3)
            title, artist, album, art_url = (metadata + [""] * 4)[:4]
            self.title.set_text(title or "Faixa sem titulo")
            self.artist.set_text(artist or "Artista desconhecido")
            self.album.set_text(album or status)
            for button in (self.previous, self.toggle, self.next):
                button.set_sensitive(True)
            self.toggle.set_label("\uf04b" if status == "Paused" else "\uf04c")
            self.toggle.set_tooltip_text("Reproduzir" if status == "Paused" else "Pausar")
            try:
                volume = max(0, min(100, round(float(self._player("volume")) * 100)))
                self.volume.set_sensitive(True)
                self.updating = True
                self.volume.set_value(volume)
                self.volume_value.set_text("%d%%" % volume)
                self.updating = False
            except (OSError, ValueError, subprocess.SubprocessError):
                self.volume.set_sensitive(False)
                self.volume_value.set_text("N/D")
        except (OSError, subprocess.SubprocessError):
            self.title.set_text("Nenhuma faixa ativa")
            self.artist.set_text("")
            self.album.set_text("")
            for button in (self.previous, self.toggle, self.next):
                button.set_sensitive(False)
            self.volume.set_sensitive(False)
            self.volume_value.set_text("--%")
            art_url = ""

        if art_url != self.art_url:
            self.art_url = art_url
            if art_url:
                threading.Thread(target=self._load_cover, args=(art_url,), daemon=True).start()
            else:
                self.cover.set_from_icon_name("audio-x-generic", Gtk.IconSize.DIALOG)
                self.cover.set_pixel_size(176)
        return True

    def _close(self, *_args):
        if self.refresh_source:
            GLib.source_remove(self.refresh_source)
            self.refresh_source = 0
        if self.volume_timeout:
            GLib.source_remove(self.volume_timeout)
            self.volume_timeout = 0
        self.hide()
        return True


class PlayerApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="org.ultimadesk.Player",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.window = None
        self.prewarmed = False

    def do_command_line(self, command_line):
        if "--prewarm" in command_line.get_arguments():
            if not self.prewarmed:
                self.hold()
                self.prewarmed = True
            return 0
        if self.window and self.window.get_visible():
            self.window._close()
            return 0
        if self.window:
            self.window._open()
        else:
            self.window = PlayerWindow(self)
        return 0


def load_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


if __name__ == "__main__":
    load_css()
    raise SystemExit(PlayerApplication().run(sys.argv))
