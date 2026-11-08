import json
import subprocess


WINDOW_SIZES = {
    "aero-shell.py": (420, 680),
    "aero-launcher.py": (620, 680),
    "aero-workspaces.py": (700, 680),
    "aero-player.py": (342, 470),
}


def float_current_window(window_class, requested_size=None, anchor=None, click_position=None):
    try:
        result = subprocess.run(
            ["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=2, check=True
        )
        clients = json.loads(result.stdout)
        client = next((item for item in clients if item.get("class") == window_class), None)
        if client:
            address = client.get("address", "")
            subprocess.run(["hyprctl", "dispatch", "focuswindow", "address:" + address], timeout=2, check=True)
            if not client.get("floating"):
                subprocess.run(["hyprctl", "dispatch", "togglefloating"], timeout=2, check=True)
            width, height = requested_size or WINDOW_SIZES.get(window_class, (620, 680))
            monitor_index = client.get("monitor", 0)
            monitors = json.loads(subprocess.check_output(["hyprctl", "monitors", "-j"], text=True, timeout=2))
            if 0 <= monitor_index < len(monitors):
                monitor = monitors[monitor_index]
                width = min(width, max(240, monitor.get("width", width) - 40))
                height = min(height, max(280, monitor.get("height", height) - 64))
            subprocess.run(["hyprctl", "dispatch", "resizeactive", "exact", str(width), str(height)], timeout=2, check=True)
            if anchor in ("cursor", "top-center") and 0 <= monitor_index < len(monitors):
                monitor = monitors[monitor_index]
                monitor_x = monitor.get("x", 0)
                monitor_y = monitor.get("y", 0)
                monitor_width = monitor.get("width", width)
                monitor_height = monitor.get("height", height)
                if anchor == "cursor":
                    if click_position is None:
                        cursor_data = json.loads(
                            subprocess.check_output(["hyprctl", "cursorpos", "-j"], text=True, timeout=2)
                        )
                        click_position = (int(cursor_data["x"]), int(cursor_data["y"]))
                    cursor_x, _cursor_y = click_position
                    target_x = cursor_x - width // 2
                    target_y = monitor_y + 40
                else:
                    target_x = monitor_x + (monitor_width - width) // 2
                    target_y = monitor_y + 44
                target_x = min(max(target_x, monitor_x + 8), monitor_x + monitor_width - width - 8)
                top_edge = 40 if anchor == "cursor" else 44
                target_y = min(max(target_y, monitor_y + top_edge), monitor_y + monitor_height - height - 8)
                current_clients = json.loads(
                    subprocess.check_output(["hyprctl", "clients", "-j"], text=True, timeout=2)
                )
                current_client = next(
                    item for item in current_clients if item.get("address") == address
                )
                current_x, current_y = current_client.get("at", [target_x, target_y])
                delta_x = target_x - current_x
                delta_y = target_y - current_y
                if delta_x or delta_y:
                    subprocess.run(["hyprctl", "dispatch", "moveactive", str(delta_x), str(delta_y)], timeout=2, check=True)
            subprocess.run(["hyprctl", "dispatch", "focuswindow", "address:" + address], timeout=2, check=True)
    except (OSError, subprocess.SubprocessError, ValueError, StopIteration):
        pass
    return False
