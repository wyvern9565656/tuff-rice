#!/usr/bin/env python3
import os
import subprocess
import sys
import threading
from shutil import which
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from aero_backend import Audio, Bluetooth, Display, Net, Notif, spawn, uptime_text
from aero_css import CSS


PANEL_PROFILES = {
    "shortcuts": ("UltimaDesk", 420, 340),
    "control": ("Centro de controle", 460, 520),
    "notifications": ("Notificacoes", 480, 560),
    "calendar": ("Calendario", 366, 410),
    "wifi": ("UltimaDesk Wi-Fi", 420, 420),
    "bluetooth": ("UltimaDesk Bluetooth", 420, 420),
    "audio": ("UltimaDesk Audio", 420, 400),
}

GLOBE_SETTINGS_PATH = Path.home() / ".config" / "waybar-aero" / "globe.conf"


class ControlCenter(Gtk.ApplicationWindow):
    def __init__(self, application, section):
        title, width, height = PANEL_PROFILES[section]
        super().__init__(application=application, title=title)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
            self.set_app_paintable(True)
        self.get_style_context().add_class("panel-window")
        self.section = section
        self.loading = False
        self.refreshing = False
        self.refresh_pending = False
        self.output_id = ""
        self.input_id = ""
        self.output_devices = []
        self.input_devices = []
        self.network_status = None
        self.toggles = {}
        self.volume_timeouts = {}
        self.globe_save_timeout = None
        self.set_default_size(width, height)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.connect("delete-event", self._hide_on_close)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.get_style_context().add_class("panel")
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(outer)
        self.add(scroll)
        self.content = outer

        self._build_header()
        {
            "shortcuts": self._build_shortcuts,
            "control": self._build_display,
            "notifications": self._build_notifications,
            "calendar": self._build_calendar,
            "wifi": self._build_network,
            "bluetooth": self._build_bluetooth,
            "audio": self._build_audio,
        }[section]()
        if section != "shortcuts":
            self.refresh_section()

    def _hide_on_close(self, *_args):
        self._close_panel()
        return True

    def _close_panel(self):
        for source_id in self.volume_timeouts.values():
            GLib.source_remove(source_id)
        self.volume_timeouts.clear()
        self.hide()

    def _section(self, title):
        label = Gtk.Label(label=title.upper(), xalign=0)
        label.get_style_context().add_class("section")
        label.set_margin_top(12)
        label.set_margin_bottom(5)
        self.content.pack_start(label, False, False, 0)

    def _separator(self):
        line = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        line.set_margin_top(8)
        self.content.pack_start(line, False, False, 0)

    def _build_header(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label=PANEL_PROFILES[self.section][0], xalign=0)
        title.get_style_context().add_class("panel-title")
        title.set_hexpand(True)
        close = Gtk.Button.new_with_label("X")
        close.set_tooltip_text("Fechar centro de controle")
        close.get_style_context().add_class("icon-btn")
        close.connect("clicked", lambda *_: self._close_panel())
        row.pack_start(title, True, True, 0)
        row.pack_start(close, False, False, 0)
        self.content.pack_start(row, False, False, 0)
        self.feedback = Gtk.Label(xalign=0)
        self.feedback.get_style_context().add_class("msg")
        self.content.pack_start(self.feedback, False, False, 0)

    def _build_audio(self):
        self._separator()
        self._section("Som")
        self.output_combo = Gtk.ComboBoxText()
        self.output_combo.set_hexpand(True)
        self.output_combo.set_tooltip_text("Dispositivo de saida")
        self.output_combo.connect("changed", self._output_changed)
        self.content.pack_start(self._labeled_row("Saida", self.output_combo), False, False, 0)
        self.output_scale, self.output_value = self._volume_row()
        self.output_mute = Gtk.Button.new_with_label("Silenciar saida")
        self.output_mute.get_style_context().add_class("soft")
        self.output_mute.connect("clicked", lambda *_: self._toggle_mute("sink"))
        self.content.pack_start(self.output_mute, False, False, 0)

        self.input_combo = Gtk.ComboBoxText()
        self.input_combo.set_hexpand(True)
        self.input_combo.set_tooltip_text("Dispositivo de entrada")
        self.input_combo.connect("changed", self._input_changed)
        self.content.pack_start(self._labeled_row("Microfone", self.input_combo), False, False, 0)
        self.input_scale, self.input_value = self._volume_row()
        self.input_mute = Gtk.Button.new_with_label("Silenciar microfone")
        self.input_mute.get_style_context().add_class("soft")
        self.input_mute.connect("clicked", lambda *_: self._toggle_mute("source"))
        self.content.pack_start(self.input_mute, False, False, 0)

    def _labeled_row(self, label, widget):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        caption = Gtk.Label(label=label, xalign=0)
        caption.set_size_request(78, -1)
        row.pack_start(caption, False, False, 0)
        row.pack_start(widget, True, True, 0)
        return row

    def _volume_row(self):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        value = Gtk.Label(label="0%")
        value.set_size_request(42, -1)
        scale.connect("value-changed", self._volume_changed)
        row.pack_start(scale, True, True, 0)
        row.pack_start(value, False, False, 0)
        self.content.pack_start(row, False, False, 0)
        return scale, value

    def _build_network(self):
        self._separator()
        self._section("Redes Wi-Fi")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.wifi_state = Gtk.Label(xalign=0)
        self.wifi_state.get_style_context().add_class("subtle")
        self.wifi_state.set_hexpand(True)
        wifi_toggle = Gtk.ToggleButton.new_with_label("Wi-Fi")
        wifi_toggle.get_style_context().add_class("toggle")
        wifi_toggle.connect("toggled", self._toggle_wifi)
        self.toggles["wifi"] = wifi_toggle
        scan = Gtk.Button.new_with_label("Atualizar")
        scan.get_style_context().add_class("icon-btn")
        scan.set_tooltip_text("Procurar redes")
        scan.connect("clicked", self._scan_wifi)
        row.pack_start(self.wifi_state, True, True, 0)
        row.pack_start(wifi_toggle, False, False, 0)
        row.pack_start(scan, False, False, 0)
        self.content.pack_start(row, False, False, 0)
        self.network_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.content.pack_start(self.network_list, False, False, 0)

    def _build_bluetooth(self):
        self._separator()
        self._section("Dispositivos Bluetooth")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.bluetooth_state = Gtk.Label(xalign=0)
        self.bluetooth_state.get_style_context().add_class("subtle")
        self.bluetooth_state.set_hexpand(True)
        bluetooth_toggle = Gtk.ToggleButton.new_with_label("Bluetooth")
        bluetooth_toggle.get_style_context().add_class("toggle")
        bluetooth_toggle.connect("toggled", self._toggle_bluetooth)
        self.toggles["bluetooth"] = bluetooth_toggle
        scan = Gtk.Button.new_with_label("Procurar")
        scan.get_style_context().add_class("icon-btn")
        scan.set_tooltip_text("Procurar dispositivos por 15 segundos")
        scan.connect("clicked", self._scan_bluetooth)
        row.pack_start(self.bluetooth_state, True, True, 0)
        row.pack_start(bluetooth_toggle, False, False, 0)
        row.pack_start(scan, False, False, 0)
        self.content.pack_start(row, False, False, 0)
        self.bluetooth_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.content.pack_start(self.bluetooth_list, False, False, 0)

    def _build_display(self):
        self._separator()
        self._section("Tela")
        toggle_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for key, label, callback in (
            ("night", "Luz noturna", self._toggle_night),
            ("dnd", "Nao perturbe", self._toggle_dnd),
        ):
            button = Gtk.ToggleButton.new_with_label(label)
            button.get_style_context().add_class("toggle")
            button.set_hexpand(True)
            button.connect("toggled", callback)
            self.toggles[key] = button
            toggle_row.pack_start(button, True, True, 0)
        self.content.pack_start(toggle_row, False, False, 0)
        self.brightness_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.brightness_row.pack_start(Gtk.Label(label="Brilho", xalign=0), False, False, 0)
        self.brightness_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.brightness_scale.set_draw_value(False)
        self.brightness_scale.set_hexpand(True)
        self.brightness_value = Gtk.Label(label="--")
        self.brightness_value.set_size_request(42, -1)
        self.brightness_scale.connect("value-changed", self._brightness_changed)
        self.brightness_row.pack_start(self.brightness_scale, True, True, 0)
        self.brightness_row.pack_start(self.brightness_value, False, False, 0)
        self.content.pack_start(self.brightness_row, False, False, 0)

        self._separator()
        self._section("Conectividade")
        connectivity = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for key, label, callback in (
            ("wifi", "Wi-Fi", self._toggle_wifi),
            ("bluetooth", "Bluetooth", self._toggle_bluetooth),
        ):
            button = Gtk.ToggleButton.new_with_label(label)
            button.get_style_context().add_class("toggle")
            button.set_hexpand(True)
            button.connect("toggled", callback)
            self.toggles[key] = button
            connectivity.pack_start(button, True, True, 0)
        self.content.pack_start(connectivity, False, False, 0)

        self._separator()
        self._section("Configuracao detalhada")
        details = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for label, section in (("Rede", "wifi"), ("Bluetooth", "bluetooth"), ("Som", "audio")):
            button = Gtk.Button.new_with_label(label)
            button.get_style_context().add_class("soft")
            button.set_hexpand(True)
            button.connect("clicked", lambda _button, target=section: self._open_control_section(target))
            details.pack_start(button, True, True, 0)
        self.content.pack_start(details, False, False, 0)
        self._build_globe()

    def _read_globe_settings(self):
        settings = {
            "speed": 12.0,
            "opacity": 100,
            "color": "62b9e8",
            "land_color": "ffffff",
        }
        try:
            for line in GLOBE_SETTINGS_PATH.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key in settings:
                    settings[key] = value.strip()
        except OSError:
            pass
        try:
            settings["speed"] = min(40.0, max(0.0, float(settings["speed"])))
        except (TypeError, ValueError):
            settings["speed"] = 12.0
        try:
            settings["opacity"] = min(100, max(20, int(float(settings["opacity"]))))
        except (TypeError, ValueError):
            settings["opacity"] = 100
        for key, fallback in (("color", "62b9e8"), ("land_color", "ffffff")):
            color = str(settings[key]).strip().lstrip("#")
            try:
                if len(color) != 6:
                    raise ValueError
                int(color, 16)
                settings[key] = color.lower()
            except ValueError:
                settings[key] = fallback
        return settings

    def _build_globe(self):
        self._section("Aparencia e movimento")
        settings = self._read_globe_settings()

        self.globe_speed_value = Gtk.Label(label="%.0f°/s" % settings["speed"])
        self.globe_speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 40, 1)
        self.globe_speed_scale.set_draw_value(False)
        self.globe_speed_scale.set_hexpand(True)
        self.globe_speed_scale.set_value(settings["speed"])
        self.globe_speed_scale.connect("value-changed", self._globe_speed_changed)
        speed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        speed_row.pack_start(self.globe_speed_scale, True, True, 0)
        self.globe_speed_value.set_size_request(48, -1)
        speed_row.pack_start(self.globe_speed_value, False, False, 0)
        self.content.pack_start(self._labeled_row("Velocidade", speed_row), False, False, 0)

        self.globe_opacity_value = Gtk.Label(label="%d%%" % settings["opacity"])
        self.globe_opacity_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 20, 100, 1)
        self.globe_opacity_scale.set_draw_value(False)
        self.globe_opacity_scale.set_hexpand(True)
        self.globe_opacity_scale.set_value(settings["opacity"])
        self.globe_opacity_scale.connect("value-changed", self._globe_opacity_changed)
        opacity_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        opacity_row.pack_start(self.globe_opacity_scale, True, True, 0)
        self.globe_opacity_value.set_size_request(48, -1)
        opacity_row.pack_start(self.globe_opacity_value, False, False, 0)
        self.content.pack_start(self._labeled_row("Opacidade", opacity_row), False, False, 0)

        color = Gdk.RGBA()
        color.parse("#" + settings["color"])
        self.globe_color_button = Gtk.ColorButton()
        self.globe_color_button.set_use_alpha(False)
        self.globe_color_button.set_rgba(color)
        self.globe_color_button.set_title("Cor do globo")
        self.globe_color_button.set_tooltip_text("Escolher qualquer cor para o globo")
        self.globe_color_button.connect("color-set", self._globe_color_changed)
        self.content.pack_start(self._labeled_row("Cor", self.globe_color_button), False, False, 0)

        land_color = Gdk.RGBA()
        land_color.parse("#" + settings["land_color"])
        self.globe_land_color_button = Gtk.ColorButton()
        self.globe_land_color_button.set_use_alpha(False)
        self.globe_land_color_button.set_rgba(land_color)
        self.globe_land_color_button.set_title("Cor dos continentes e paises")
        self.globe_land_color_button.set_tooltip_text("Escolher a cor dos continentes e paises")
        self.globe_land_color_button.connect("color-set", self._globe_color_changed)
        self.content.pack_start(self._labeled_row("Paises", self.globe_land_color_button), False, False, 0)

        self.globe_feedback = Gtk.Label(label="Aplicacao ao vivo", xalign=0)
        self.globe_feedback.get_style_context().add_class("subtle")
        self.globe_feedback.set_margin_top(8)
        self.content.pack_start(self.globe_feedback, False, False, 0)

    def _globe_speed_changed(self, scale):
        self.globe_speed_value.set_text("%.0f°/s" % scale.get_value())
        self._schedule_globe_save()

    def _globe_opacity_changed(self, scale):
        self.globe_opacity_value.set_text("%d%%" % scale.get_value())
        self._schedule_globe_save()

    def _globe_color_changed(self, _button):
        self._schedule_globe_save()

    def _schedule_globe_save(self):
        if self.globe_save_timeout:
            GLib.source_remove(self.globe_save_timeout)
        self.globe_save_timeout = GLib.timeout_add(180, self._save_globe_settings)

    def _save_globe_settings(self):
        self.globe_save_timeout = None
        def color_hex(button):
            color = button.get_rgba()
            return "%02x%02x%02x" % tuple(
                int(max(0.0, min(1.0, channel)) * 255 + 0.5)
                for channel in (color.red, color.green, color.blue)
            )

        values = (
            "speed=%.1f\n" % self.globe_speed_scale.get_value()
            + "opacity=%d\n" % self.globe_opacity_scale.get_value()
            + "color=%s\n" % color_hex(self.globe_color_button)
            + "land_color=%s\n" % color_hex(self.globe_land_color_button)
        )
        try:
            GLOBE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = GLOBE_SETTINGS_PATH.with_suffix(".tmp")
            temporary.write_text(values, encoding="utf-8")
            temporary.replace(GLOBE_SETTINGS_PATH)
            result = subprocess.run(
                ["pkill", "-USR1", "-x", "globo-layer"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
            self.globe_feedback.set_text(
                "Aplicado ao vivo" if result.returncode == 0 else "Salvo para a proxima inicializacao"
            )
        except OSError as error:
            self.globe_feedback.set_text("Nao foi possivel salvar: %s" % error)
        return GLib.SOURCE_REMOVE

    def _build_notifications(self):
        self._section("Central de notificacoes")
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.notification_pause = Gtk.ToggleButton.new_with_label("Nao perturbe")
        self.notification_pause.get_style_context().add_class("toggle")
        self.notification_pause.connect("toggled", self._toggle_dnd)
        self.toggles["dnd"] = self.notification_pause
        actions.pack_start(self.notification_pause, True, True, 0)

        refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        refresh.get_style_context().add_class("icon-btn")
        refresh.set_tooltip_text("Atualizar historico")
        refresh.connect("clicked", lambda *_: self.refresh_section())
        actions.pack_start(refresh, False, False, 0)

        clear = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
        clear.get_style_context().add_class("icon-btn")
        clear.set_tooltip_text("Limpar notificacoes e historico")
        clear.connect("clicked", self._clear_notifications)
        actions.pack_start(clear, False, False, 0)
        self.content.pack_start(actions, False, False, 0)

        self.notification_count = Gtk.Label(xalign=0)
        self.notification_count.get_style_context().add_class("subtle")
        self.notification_count.set_margin_top(6)
        self.notification_count.set_margin_bottom(4)
        self.content.pack_start(self.notification_count, False, False, 0)

        self.notification_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.content.pack_start(self.notification_list, False, False, 0)

    def _build_calendar(self):
        now = GLib.DateTime.new_now_local()
        self.calendar_weekday = Gtk.Label(xalign=0)
        self.calendar_weekday.get_style_context().add_class("calendar-weekday")
        self.content.pack_start(self.calendar_weekday, False, False, 0)

        self.calendar_date = Gtk.Label(xalign=0)
        self.calendar_date.get_style_context().add_class("calendar-date")
        self.content.pack_start(self.calendar_date, False, False, 0)

        self.calendar = Gtk.Calendar()
        self.calendar.set_display_options(
            Gtk.CalendarDisplayOptions.SHOW_HEADING | Gtk.CalendarDisplayOptions.SHOW_DAY_NAMES
        )
        self.calendar.select_month(now.get_month() - 1, now.get_year())
        self.calendar.select_day(now.get_day_of_month())
        self.calendar.connect("day-selected", self._calendar_day_selected)
        self.content.pack_start(self.calendar, True, True, 8)
        self._set_calendar_date(now.get_year(), now.get_month(), now.get_day_of_month())

    def _set_calendar_date(self, year, month, day):
        selected = GLib.DateTime.new_local(year, month, day, 12, 0, 0)
        self.calendar_weekday.set_text(selected.format("%A").capitalize())
        self.calendar_date.set_text(selected.format("%d %B %Y"))

    def _calendar_day_selected(self, calendar):
        year, month, day = calendar.get_date()
        self._set_calendar_date(year, month + 1, day)

    def _notification_card(self, notification):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.get_style_context().add_class("notification-card")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon_path = notification.get("icon", "")
        if icon_path and os.path.isfile(icon_path):
            app_icon = Gtk.Image.new_from_file(icon_path)
            app_icon.set_pixel_size(24)
            header.pack_start(app_icon, False, False, 0)
        app = Gtk.Label(label=notification.get("app") or "Notificacao", xalign=0)
        app.get_style_context().add_class("subtle")
        app.set_hexpand(True)
        header.pack_start(app, True, True, 0)
        urgency = Gtk.Label(label=str(notification.get("urgency", "NORMAL")).capitalize())
        urgency.get_style_context().add_class("notification-urgency")
        header.pack_start(urgency, False, False, 0)
        card.pack_start(header, False, False, 0)

        summary = Gtk.Label(label=notification.get("summary") or "Sem titulo", xalign=0)
        summary.get_style_context().add_class("notification-summary")
        summary.set_line_wrap(True)
        summary.set_max_width_chars(54)
        card.pack_start(summary, False, False, 0)

        body_text = notification.get("body", "")
        if body_text:
            body = Gtk.Label(label=body_text, xalign=0)
            body.get_style_context().add_class("notification-body")
            body.set_line_wrap(True)
            body.set_max_width_chars(58)
            card.pack_start(body, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        replay = Gtk.Button.new_with_label("Reexibir")
        replay.get_style_context().add_class("soft")
        replay.connect("clicked", self._replay_notification, notification)
        buttons.pack_end(replay, False, False, 0)
        remove = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
        remove.get_style_context().add_class("icon-btn")
        remove.set_tooltip_text("Remover do historico")
        remove.connect("clicked", self._remove_notification, notification)
        buttons.pack_end(remove, False, False, 0)
        card.pack_start(buttons, False, False, 0)
        return card

    def _replay_notification(self, _button, notification):
        Notif.replay(notification.get("id"))
        self.refresh_section()

    def _remove_notification(self, _button, notification):
        Notif.remove(notification.get("id"))
        self.refresh_section()

    def _clear_notifications(self, *_args):
        Notif.clear_all()
        self.feedback.set_text("Historico limpo")
        self.refresh_section()

    def _apply_notifications(self, snapshot):
        self._set_toggle("dnd", snapshot["paused"])
        notifications = snapshot["notifications"]
        total = len(notifications)
        self.notification_count.set_text("%d notificacao(oes) no historico" % total)
        self._clear_box(self.notification_list)
        if not notifications:
            empty = Gtk.Label(label="Tudo em dia. Nenhuma notificacao guardada.", xalign=0)
            empty.get_style_context().add_class("subtle")
            empty.set_margin_top(12)
            self.notification_list.pack_start(empty, False, False, 0)
        else:
            for notification in reversed(notifications):
                self.notification_list.pack_start(self._notification_card(notification), False, False, 0)
        self.notification_list.show_all()

    def _apply_control(self, snapshot):
        self._set_toggle("night", snapshot["nightlight"])
        self._set_toggle("dnd", snapshot["paused"])
        self._set_toggle("wifi", snapshot["wifi_enabled"])
        self._set_toggle("bluetooth", snapshot["bluetooth_enabled"])
        self._apply_display(snapshot["brightness"])

    def _open_control_section(self, section):
        script = os.path.expanduser("~/.config/waybar-aero/aero-control.sh")
        if os.path.isfile(script):
            spawn([script, section])

    def _build_shortcuts(self):
        self._separator()
        self._section("Atalhos")
        grid = Gtk.Grid(column_spacing=8, row_spacing=8)
        actions = [
            ("\uf120  Terminal", self._open_terminal),
            ("\uf07b  Arquivos", self._open_files),
            ("\uf009  Aplicativos", self._open_launcher),
            ("\uf030  Captura de tela", self._screenshot),
            ("\uf0ea  Historico clipboard", self._clipboard),
            ("\uf04b  Reproduzir / pausar", lambda: self._run(["playerctl", "play-pause"])),
            ("\uf023  Bloquear", lambda: self._run([os.path.expanduser("~/.config/waybar-aero/lock-screen.sh")])),
            ("\uf011  Energia", self._power_menu),
        ]
        for index, (label, callback) in enumerate(actions):
            button = Gtk.Button.new_with_label(label)
            button.get_style_context().add_class("soft")
            button.set_hexpand(True)
            button.connect("clicked", lambda _button, cb=callback: cb())
            grid.attach(button, index % 2, index // 2, 1, 1)
        self.content.pack_start(grid, False, False, 0)

    def _build_footer(self):
        self._separator()
        self.footer = Gtk.Label(xalign=0)
        self.footer.get_style_context().add_class("subtle")
        self.footer.set_margin_top(5)
        self.content.pack_start(self.footer, False, False, 0)

    def _clock_tick(self):
        self.clock.set_text(GLib.DateTime.new_now_local().format("%H:%M  %a, %d %b"))
        return True

    def _run(self, args):
        if which(args[0]):
            spawn(args)

    def _run_async(self, work, done=None):
        def worker():
            try:
                result = work()
            except Exception as error:
                result = error
            GLib.idle_add(self._finish_async, done, result)

        threading.Thread(target=worker, daemon=True).start()

    def _finish_async(self, done, result):
        if done:
            done(result)
        self.refresh_section()
        return False

    def _set_toggle(self, key, value):
        self.loading = True
        self.toggles[key].set_active(bool(value))
        self.loading = False

    def _toggle_wifi(self, button):
        if not self.loading:
            enabled = button.get_active()
            self._run_async(lambda: Net.set_wifi(enabled))

    def _toggle_bluetooth(self, button):
        if not self.loading:
            enabled = button.get_active()
            self._run_async(lambda: Bluetooth.set_power(enabled))

    def _toggle_night(self, button):
        if not self.loading:
            Display.set_nightlight(button.get_active())

    def _toggle_dnd(self, button):
        if not self.loading:
            Notif.set_paused(button.get_active())

    def _update_combo(self, combo, devices, active_name):
        device_ids = [item["name"] for item in devices]
        attr = "output_devices" if combo is self.output_combo else "input_devices"
        if getattr(self, attr) != device_ids:
            combo.remove_all()
            for item in devices:
                combo.append(item["name"], item["desc"])
            setattr(self, attr, device_ids)
        combo.set_active_id(active_name if active_name in device_ids else (device_ids[0] if device_ids else None))

    def _apply_audio(self, snapshot):
        sinks, sources = snapshot["sinks"], snapshot["sources"]
        self.loading = True
        self._update_combo(self.output_combo, sinks, snapshot["default_sink"])
        self._update_combo(self.input_combo, sources, snapshot["default_source"])
        sink = next((item for item in sinks if item["default"]), sinks[0] if sinks else None)
        source = next((item for item in sources if item["default"]), sources[0] if sources else None)
        self.output_id = sink["name"] if sink else ""
        self.input_id = source["name"] if source else ""
        if sink:
            self.output_scale.set_value(min(100, sink["vol"]))
            self.output_value.set_text("%d%%" % sink["vol"])
            self.output_mute.set_label("Desmutar saida" if sink["mute"] else "Silenciar saida")
        if source:
            self.input_scale.set_value(min(100, source["vol"]))
            self.input_value.set_text("%d%%" % source["vol"])
            self.input_mute.set_label("Ativar microfone" if source["mute"] else "Silenciar microfone")
        self.loading = False

    def _volume_changed(self, scale):
        if self.loading:
            return
        kind = "sink" if scale is self.output_scale else "source"
        name = self.output_id if kind == "sink" else self.input_id
        if name:
            value = int(scale.get_value())
            (self.output_value if kind == "sink" else self.input_value).set_text("%d%%" % value)
            previous = self.volume_timeouts.get(kind)
            if previous:
                GLib.source_remove(previous)
            self.volume_timeouts[kind] = GLib.timeout_add(180, self._apply_volume_change, kind, name, value)

    def _apply_volume_change(self, kind, name, value):
        self.volume_timeouts.pop(kind, None)
        Audio.set_volume(kind, name, value)
        return GLib.SOURCE_REMOVE

    def _toggle_mute(self, kind):
        name = self.output_id if kind == "sink" else self.input_id
        if name:
            Audio.toggle_mute(kind, name)
            self.refresh_section()

    def _output_changed(self, combo):
        name = combo.get_active_id()
        if name and not self.loading:
            Audio.set_default("sink", name)
            self.output_id = name
            self.refresh_section()

    def _input_changed(self, combo):
        name = combo.get_active_id()
        if name and not self.loading:
            Audio.set_default("source", name)
            self.input_id = name
            self.refresh_section()

    def _scan_wifi(self, *_args):
        self.wifi_state.set_text("Procurando redes...")
        self._run_async(Net.rescan, lambda _result: self.feedback.set_text("Busca de redes concluida"))

    def _clear_box(self, box):
        for child in box.get_children():
            box.remove(child)
            child.destroy()

    def _apply_networks(self, snapshot):
        self.network_status = snapshot["network_status"]
        wifi = self.network_status["wifi"]
        self.wifi_state.set_text(("Conectado: " + wifi["conn"]) if wifi else "Selecione uma rede para conectar")
        self._clear_box(self.network_list)
        networks = snapshot["networks"]
        for network in networks[:8]:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lock = "Protegida" if network["secured"] else "Aberta"
            label = Gtk.Label(label="%s  %s  %d%%" % (lock, network["ssid"], network["signal"]), xalign=0)
            label.set_ellipsize(3)
            label.set_hexpand(True)
            button = Gtk.Button.new_with_label("Conectado" if network["in_use"] else ("Conectar" if network["known"] or not network["secured"] else "Senha"))
            button.get_style_context().add_class("soft")
            button.set_sensitive(not network["in_use"])
            button.connect("clicked", self._connect_wifi, network)
            row.pack_start(label, True, True, 0)
            row.pack_start(button, False, False, 0)
            self.network_list.pack_start(row, False, False, 0)
        self.network_list.show_all()

    def _connect_wifi(self, _button, network):
        password = None
        if network["secured"] and not network["known"]:
            dialog = Gtk.Dialog(title="Conectar a " + network["ssid"], transient_for=self, modal=True)
            dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
            dialog.add_button("Conectar", Gtk.ResponseType.OK)
            entry = Gtk.Entry()
            entry.set_visibility(False)
            entry.set_placeholder_text("Senha da rede")
            entry.set_activates_default(True)
            dialog.get_content_area().pack_start(entry, True, True, 12)
            dialog.set_default_response(Gtk.ResponseType.OK)
            dialog.show_all()
            if dialog.run() == Gtk.ResponseType.OK:
                password = entry.get_text()
            dialog.destroy()
            if not password:
                return
        self.wifi_state.set_text("Conectando...")
        self._run_async(
            lambda: Net.connect(network["ssid"], password),
            lambda result: self.feedback.set_text(result[2] if isinstance(result, tuple) else str(result)),
        )

    def _scan_bluetooth(self, *_args):
        if not Bluetooth.state():
            self.bluetooth_state.set_text("Nenhum controlador Bluetooth disponivel")
            return
        self.bluetooth_state.set_text("Procurando por 15 segundos...")
        Bluetooth.scan_process(15)
        GLib.timeout_add_seconds(3, self._refresh_after_scan)

    def _refresh_after_scan(self):
        self.refresh_section()
        return False

    def _apply_bluetooth(self, snapshot):
        state = snapshot["bluetooth_state"]
        self._set_toggle("bluetooth", state["powered"] if state else False)
        self.bluetooth_state.set_text("Ativo" if state and state["powered"] else ("Desativado" if state else "Controlador indisponivel"))
        self._clear_box(self.bluetooth_list)
        if state and state["powered"]:
            for device in snapshot["bluetooth_devices"][:8]:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                details = device["name"]
                if device["battery"] is not None:
                    details += "  %d%%" % device["battery"]
                label = Gtk.Label(label=details, xalign=0)
                label.set_ellipsize(3)
                label.set_hexpand(True)
                action = "Desconectar" if device["connected"] else ("Conectar" if device["paired"] else "Parear")
                button = Gtk.Button.new_with_label(action)
                button.get_style_context().add_class("soft")
                button.connect("clicked", self._bluetooth_action, device)
                row.pack_start(label, True, True, 0)
                row.pack_start(button, False, False, 0)
                self.bluetooth_list.pack_start(row, False, False, 0)
        self.bluetooth_list.show_all()

    def _bluetooth_action(self, _button, device):
        def action():
            if device["connected"]:
                Bluetooth.disconnect(device["mac"])
                return True
            if device["paired"]:
                return Bluetooth.connect(device["mac"])
            if Bluetooth.pair(device["mac"]):
                return Bluetooth.connect(device["mac"])
            return False

        self._run_async(action, lambda result: self.feedback.set_text("Bluetooth atualizado" if result else "Nao foi possivel conectar ao dispositivo"))

    def _brightness_changed(self, scale, *_args):
        if self.loading:
            return
        value = int(scale.get_value())
        self.brightness_value.set_text("%d%%" % value)
        Display.set_brightness(value)

    def _apply_display(self, brightness):
        self.brightness_row.set_visible(brightness is not None)
        if brightness is not None:
            self.loading = True
            self.brightness_scale.set_value(brightness)
            self.brightness_value.set_text("%d%%" % brightness)
            self.loading = False

    def _open_terminal(self):
        for name in ("kitty", "foot", "alacritty", "xterm"):
            if which(name):
                self._run([name])
                return

    def _open_files(self):
        for name in ("thunar", "dolphin", "nautilus"):
            if which(name):
                self._run([name])
                return

    def _open_launcher(self):
        launcher = os.path.expanduser("~/.config/waybar-aero/aero-launcher.sh")
        if os.path.isfile(launcher):
            spawn([launcher])

    def _screenshot(self):
        script = os.path.expanduser("~/.config/waybar-aero/screenshot-menu.sh")
        if os.path.isfile(script):
            spawn([script])

    def _power_menu(self):
        script = os.path.expanduser("~/.config/waybar-aero/power-menu.sh")
        if os.path.isfile(script):
            spawn([script])

    def _clipboard(self):
        if which("cliphist") and which("rofi") and which("wl-copy"):
            spawn(["sh", "-c", "cliphist list | rofi -theme \"$HOME/.local/share/ultimadesk/rofi.rasi\" -dmenu -p Clipboard | cliphist decode | wl-copy"])

    def refresh_section(self):
        if self.section not in ("audio", "wifi", "bluetooth", "control", "notifications"):
            return False
        if self.refreshing:
            self.refresh_pending = True
            return True
        self.refreshing = True

        def collect():
            try:
                if self.section == "audio":
                    snapshot = {
                        "sinks": Audio.sinks(),
                        "sources": Audio.sources(),
                        "default_sink": Audio.default("sink"),
                        "default_source": Audio.default("source"),
                    }
                elif self.section == "wifi":
                    wifi_enabled = Net.wifi_enabled()
                    snapshot = {
                        "wifi_enabled": wifi_enabled,
                        "network_status": Net.status(),
                        "networks": Net.wifi_list() if wifi_enabled else [],
                    }
                elif self.section == "bluetooth":
                    bluetooth_state = Bluetooth.state()
                    snapshot = {
                        "bluetooth_state": bluetooth_state,
                        "bluetooth_devices": Bluetooth.devices()
                        if bluetooth_state and bluetooth_state["powered"] else [],
                    }
                elif self.section == "control":
                    bluetooth_state = Bluetooth.state()
                    snapshot = {
                        "wifi_enabled": Net.wifi_enabled(),
                        "bluetooth_enabled": bool(bluetooth_state and bluetooth_state["powered"]),
                        "nightlight": Display.nightlight_on(),
                        "paused": Notif.paused(),
                        "brightness": Display.brightness(),
                    }
                else:
                    snapshot = {"notifications": Notif.history(), "paused": Notif.paused()}
                GLib.idle_add(self._apply_section_snapshot, snapshot, None)
            except Exception as error:
                GLib.idle_add(self._apply_section_snapshot, None, error)

        threading.Thread(target=collect, daemon=True).start()
        return True

    def _apply_section_snapshot(self, snapshot, error):
        self.refreshing = False
        if error:
            self.feedback.set_text("Algum servico nao respondeu: %s" % error)
        elif self.section == "audio":
            self._apply_audio(snapshot)
        elif self.section == "wifi":
            self._apply_networks(snapshot)
            self._set_toggle("wifi", snapshot["wifi_enabled"])
        elif self.section == "bluetooth":
            self._apply_bluetooth(snapshot)
        elif self.section == "control":
            self._apply_control(snapshot)
        else:
            self._apply_notifications(snapshot)
        if self.refresh_pending:
            self.refresh_pending = False
            self.refresh_section()
        return False


class AeroApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="org.ultimadesk.ControlCenterV2",
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.window = None
        self.prewarmed = False

    def do_command_line(self, command_line):
        args = command_line.get_arguments()
        if "--prewarm" in args:
            if not self.prewarmed:
                self.hold()
                self.prewarmed = True
            return 0

        section = "shortcuts"
        if "--section" in args:
            index = args.index("--section")
            if index + 1 < len(args):
                section = args[index + 1]
        if section not in PANEL_PROFILES:
            section = "shortcuts"
        if self.window and self.window.get_visible():
            if self.window.section == section:
                self.window._close_panel()
                return 0
            self.window.destroy()
            self.window = None
        elif self.window and self.window.section == section:
            self.window.present()
            self.window.refresh_section()
            return 0
        elif self.window:
            self.window.destroy()
            self.window = None
        self.window = ControlCenter(self, section)
        self.window.show_all()
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
    raise SystemExit(AeroApplication().run(sys.argv))