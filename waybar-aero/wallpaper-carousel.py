#!/usr/bin/env python3
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk


WALLPAPER_DIR = Path.home() / "Imagens" / "wallpapers"
STATE_FILE = Path.home() / ".local" / "state" / "ultimadesk" / "wallpaper-selected"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
CARD_WIDTH = 194
CARD_HEIGHT = 154
CARD_GAP = 16
STEP = CARD_WIDTH + CARD_GAP


def active_workspace_is_empty():
    try:
        workspace = json.loads(subprocess.check_output(
            ["hyprctl", "activeworkspace", "-j"], text=True
        ))
        clients = json.loads(subprocess.check_output(
            ["hyprctl", "clients", "-j"], text=True
        ))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return False
    workspace_id = workspace.get("id")
    return not any(client.get("workspace", {}).get("id") == workspace_id for client in clients)


def wallpaper_files():
    if not WALLPAPER_DIR.is_dir():
        return []
    return sorted(
        (path for path in WALLPAPER_DIR.iterdir()
         if path.is_file() and path.suffix.lower() in EXTENSIONS),
        key=lambda path: path.name.casefold(),
    )


def rounded_rectangle(context, x, y, width, height, radius):
    context.new_sub_path()
    context.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    context.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    context.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    context.arc(x + radius, y + radius, radius, math.pi, math.pi * 1.5)
    context.close_path()


class WallpaperCarousel(Gtk.Window):
    def __init__(self, wallpapers):
        super().__init__(title="UltimaDesk Wallpapers")
        self.wallpapers = wallpapers
        self.position = self._initial_position()
        self.drag_origin = None
        self.drag_start_position = 0.0
        self.dragged = False
        self.cards = []
        self.status = "Clique em uma imagem para aplicar"
        self.thumbnails = {
            path: self._thumbnail(path) for path in self.wallpapers
        }

        self.set_decorated(False)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_default_size(1120, 286)
        self.set_position(Gtk.WindowPosition.CENTER)
        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
            self.set_app_paintable(True)

        self.canvas = Gtk.DrawingArea()
        self.canvas.set_size_request(1120, 286)
        self.canvas.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.SMOOTH_SCROLL_MASK
        )
        self.canvas.connect("draw", self._draw)
        self.canvas.connect("button-press-event", self._press)
        self.canvas.connect("button-release-event", self._release)
        self.canvas.connect("motion-notify-event", self._motion)
        self.canvas.connect("scroll-event", self._scroll)
        self.add(self.canvas)
        self.connect("key-press-event", self._key_press)
        self.connect("destroy", Gtk.main_quit)

    def _initial_position(self):
        try:
            selected = STATE_FILE.read_text(encoding="utf-8").strip()
            for index, path in enumerate(self.wallpapers):
                if str(path) == selected:
                    return float(index)
        except OSError:
            pass
        return 0.0

    def _wrapped_index(self, index):
        return index % len(self.wallpapers)

    def _draw(self, _widget, context):
        width = self.canvas.get_allocated_width()
        height = self.canvas.get_allocated_height()
        rounded_rectangle(context, 0, 0, width, height, 18)
        glass = cairo.LinearGradient(0, 0, 0, height)
        glass.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.92)
        glass.add_color_stop_rgba(0.49, 214 / 255, 243 / 255, 1.0, 0.78)
        glass.add_color_stop_rgba(0.51, 160 / 255, 220 / 255, 250 / 255, 0.72)
        glass.add_color_stop_rgba(1.0, 185 / 255, 242 / 255, 228 / 255, 0.78)
        context.set_source(glass)
        context.fill_preserve()
        context.set_line_width(1)
        context.set_source_rgba(1.0, 1.0, 1.0, 0.82)
        context.stroke()

        context.set_source_rgba(0.04, 0.23, 0.35, 0.98)
        context.select_font_face("Noto Sans", 0, 1)
        context.set_font_size(15)
        context.move_to(26, 34)
        context.show_text("PAPEIS DE PAREDE")

        context.set_source_rgba(0.04, 0.23, 0.35, 0.82)
        context.set_font_size(12)
        context.move_to(width - 360, 34)
        context.show_text("Arraste / roda para navegar   |   ESC fecha")

        center = round(self.position)
        fraction = self.position - center
        self.cards = []
        row_center = width / 2
        card_y = 58
        for offset in range(-2, 3):
            index = self._wrapped_index(center + offset)
            relative = offset - fraction
            card_x = row_center + relative * STEP - CARD_WIDTH / 2
            self.cards.append((card_x, card_y, CARD_WIDTH, CARD_HEIGHT, index))
            active = offset == 0 and abs(fraction) < 0.5

            rounded_rectangle(context, card_x, card_y, CARD_WIDTH, CARD_HEIGHT, 12)
            card_glass = cairo.LinearGradient(0, card_y, 0, card_y + CARD_HEIGHT)
            card_glass.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.68)
            card_glass.add_color_stop_rgba(0.49, 214 / 255, 243 / 255, 1.0, 0.36)
            card_glass.add_color_stop_rgba(0.51, 160 / 255, 220 / 255, 250 / 255, 0.34)
            card_glass.add_color_stop_rgba(1.0, 185 / 255, 242 / 255, 228 / 255, 0.48)
            context.set_source(card_glass)
            context.fill()

            pixbuf = self.thumbnails[self.wallpapers[index]]
            if pixbuf:
                image_width = pixbuf.get_width()
                image_height = pixbuf.get_height()
                image_x = card_x + (CARD_WIDTH - image_width) / 2
                image_y = card_y + 8 + (108 - image_height) / 2
                rounded_rectangle(context, card_x + 7, card_y + 7, CARD_WIDTH - 14, 110, 8)
                context.save()
                context.clip()
                Gdk.cairo_set_source_pixbuf(context, pixbuf, image_x, image_y)
                context.paint()
                context.restore()

            label = self.wallpapers[index].stem
            if len(label) > 24:
                label = label[:21] + "..."
            context.set_source_rgba(0.04, 0.23, 0.35, 0.98)
            context.set_font_size(11)
            context.move_to(card_x + 10, card_y + 137)
            context.show_text(label)

            rounded_rectangle(context, card_x, card_y, CARD_WIDTH, CARD_HEIGHT, 12)
            if active:
                context.set_line_width(2.5)
                context.set_source_rgba(0.16, 0.62, 0.58, 0.98)
            else:
                context.set_line_width(1)
                context.set_source_rgba(1.0, 1.0, 1.0, 0.68)
            context.stroke()

        selected = self.wallpapers[self._wrapped_index(round(self.position))].name
        context.set_source_rgba(0.04, 0.23, 0.35, 0.84)
        context.set_font_size(11)
        context.move_to(26, height - 14)
        context.show_text(f"{self.status}  |  {selected}")
        return False

    @staticmethod
    def _thumbnail(path):
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 176, 106, True)
        except (GLib.Error, OSError):
            return None

    def _press(self, _widget, event):
        if event.button == 1:
            self.drag_origin = event.x
            self.drag_start_position = self.position
            self.dragged = False
        return True

    def _motion(self, _widget, event):
        if self.drag_origin is not None:
            delta = event.x - self.drag_origin
            if abs(delta) > 5:
                self.dragged = True
            self.position = self.drag_start_position - delta / STEP
            self.canvas.queue_draw()
        return True

    def _release(self, _widget, event):
        if event.button != 1:
            return False
        if self.drag_origin is not None and not self.dragged:
            for x, y, width, height, index in self.cards:
                if x <= event.x <= x + width and y <= event.y <= y + height:
                    self.position = float(index)
                    self._apply(self.wallpapers[index])
                    break
        self.drag_origin = None
        self.dragged = False
        self.canvas.queue_draw()
        return True

    def _scroll(self, _widget, event):
        if event.direction == Gdk.ScrollDirection.UP:
            self.position -= 1
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.position += 1
        elif event.direction == Gdk.ScrollDirection.LEFT:
            self.position += 1
        elif event.direction == Gdk.ScrollDirection.RIGHT:
            self.position -= 1
        else:
            _success, _delta_x, delta_y = event.get_scroll_deltas()
            self.position += delta_y
        self.canvas.queue_draw()
        return True

    def _key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def _apply(self, path):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = STATE_FILE.with_suffix(".tmp")
        temporary.write_text(str(path) + "\n", encoding="utf-8")
        temporary.replace(STATE_FILE)
        subprocess.run(["pkill", "-x", "swaybg"], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.Popen(["swaybg", "-i", str(path), "-m", "fill"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        self.status = "Wallpaper aplicado"
        self.canvas.queue_draw()


def main():
    if not active_workspace_is_empty():
        subprocess.run(["notify-send", "Wallpaper", "Disponivel apenas em um workspace vazio"],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0

    wallpapers = wallpaper_files()
    if not wallpapers:
        subprocess.run(["notify-send", "Wallpaper", f"Nenhuma imagem em {WALLPAPER_DIR}"],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 1

    window = WallpaperCarousel(wallpapers)
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())