"""UltimaDesk Shell - backend (sem GTK): le/controla audio, rede, bluetooth, notificacoes etc.
Tudo via comandos do sistema (pactl, nmcli, bluetoothctl, dunstctl, cliphist, brightnessctl)."""
import json
import os
import re
import subprocess

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def sh(args, timeout=8, stdin=None):
    """Roda um comando. Retorna (rc, stdout, stderr); rc=127 se o programa nao existe."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=stdin)
        return p.returncode, ANSI.sub("", p.stdout), ANSI.sub("", p.stderr)
    except FileNotFoundError:
        return 127, "", "%s: nao encontrado" % args[0]
    except subprocess.TimeoutExpired:
        return 124, "", "tempo esgotado"
    except Exception as e:  # noqa
        return 1, "", str(e)


def spawn(args):
    """Dispara um programa e esquece (sem esperar)."""
    try:
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception:
        return False


def have(cmd):
    from shutil import which
    return which(cmd) is not None


# ---------------------------------------------------------------- AUDIO
def _vol_pct(v):
    """Media dos canais de um objeto 'volume' do pactl JSON -> inteiro 0..150."""
    try:
        vals = []
        for ch in (v or {}).values():
            p = str(ch.get("value_percent", "0%")).strip().rstrip("%")
            vals.append(int(float(p)))
        return int(sum(vals) / len(vals)) if vals else 0
    except Exception:
        return 0


def _pactl_json(kind):
    rc, out, _ = sh(["pactl", "--format=json", "list", kind])
    if rc != 0 or not out.strip():
        return []
    try:
        return json.loads(out)
    except Exception:
        return []


class Audio:
    @staticmethod
    def _description(device, name):
        description = device.get("description")
        if not description or description.strip().lower() in ("(null)", "null"):
            props = device.get("properties") or {}
            description = (props.get("node.nick") or props.get("device.product.name")
                           or props.get("alsa.name") or name)
        return description

    @staticmethod
    def default(kind):  # kind: sink | source
        rc, out, _ = sh(["pactl", "get-default-" + kind])
        return out.strip() if rc == 0 else ""

    @staticmethod
    def sinks():
        d = Audio.default("sink")
        res = []
        for s in _pactl_json("sinks"):
            name = s.get("name") or ""
            res.append({"name": name, "desc": Audio._description(s, name),
                        "vol": _vol_pct(s.get("volume")), "mute": bool(s.get("mute")),
                        "default": s.get("name") == d})
        return res

    @staticmethod
    def sources():
        d = Audio.default("source")
        res = []
        for s in _pactl_json("sources"):
            name = s.get("name", "")
            props = s.get("properties") or {}
            if name.endswith(".monitor") or props.get("device.class") == "monitor":
                continue
            res.append({"name": name, "desc": Audio._description(s, name),
                        "vol": _vol_pct(s.get("volume")), "mute": bool(s.get("mute")),
                        "default": name == d})
        return res

    @staticmethod
    def streams():
        res = []
        for s in _pactl_json("sink-inputs"):
            p = s.get("properties") or {}
            name = p.get("application.name") or p.get("application.process.binary") or p.get("media.name") or "Aplicativo"
            res.append({"id": s.get("index"), "name": name, "title": p.get("media.name", ""),
                        "vol": _vol_pct(s.get("volume")), "mute": bool(s.get("mute"))})
        return res

    @staticmethod
    def set_volume(kind, name, pct):
        sh(["pactl", "set-%s-volume" % kind, name, "%d%%" % max(0, min(150, int(pct)))])

    @staticmethod
    def toggle_mute(kind, name):
        sh(["pactl", "set-%s-mute" % kind, name, "toggle"])

    @staticmethod
    def set_default(kind, name):
        sh(["pactl", "set-default-" + kind, name])
        if kind == "sink":                       # move os apps que ja estao tocando
            for s in _pactl_json("sink-inputs"):
                sh(["pactl", "move-sink-input", str(s.get("index")), name])

    @staticmethod
    def set_stream_volume(sid, pct):
        sh(["pactl", "set-sink-input-volume", str(sid), "%d%%" % max(0, min(150, int(pct)))])


# ---------------------------------------------------------------- REDE (NetworkManager)
def split_terse(line):
    """Divide uma linha do 'nmcli -t' respeitando o escape '\\:'."""
    parts, cur, i = [], [], 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            cur.append(line[i + 1]); i += 2; continue
        if c == ":":
            parts.append("".join(cur)); cur = []; i += 1; continue
        cur.append(c); i += 1
    parts.append("".join(cur))
    return parts


class Net:
    @staticmethod
    def available():
        return have("nmcli")

    @staticmethod
    def wifi_enabled():
        rc, out, _ = sh(["nmcli", "radio", "wifi"])
        return rc == 0 and out.strip().lower().startswith("enabled")

    @staticmethod
    def set_wifi(on):
        sh(["nmcli", "radio", "wifi", "on" if on else "off"])

    @staticmethod
    def rescan():
        sh(["nmcli", "device", "wifi", "rescan"], timeout=15)

    @staticmethod
    def known_wifi():
        rc, out, _ = sh(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
        names = set()
        for ln in out.splitlines():
            p = split_terse(ln)
            if len(p) >= 2 and "wireless" in p[1]:
                names.add(p[0])
        return names

    @staticmethod
    def wifi_list():
        rc, out, _ = sh(["nmcli", "-t", "-f", "IN-USE,SIGNAL,SECURITY,SSID", "device", "wifi", "list"])
        known = Net.known_wifi()
        best = {}
        for ln in out.splitlines():
            p = split_terse(ln)
            if len(p) < 4:
                continue
            inuse, sig, sec, ssid = p[0].strip() == "*", p[1], p[2].strip(), ":".join(p[3:])
            if not ssid:
                continue
            try:
                sig = int(sig)
            except ValueError:
                sig = 0
            secured = sec not in ("", "--")
            cur = {"ssid": ssid, "signal": sig, "secured": secured, "sec": sec if secured else "",
                   "in_use": inuse, "known": ssid in known}
            old = best.get(ssid)
            if old is None or inuse or (not old["in_use"] and sig > old["signal"]):
                best[ssid] = cur
        lst = list(best.values())
        lst.sort(key=lambda n: (not n["in_use"], not n["known"], -n["signal"]))
        return lst

    @staticmethod
    def status():
        """{'wifi': {dev,conn,ip}|None, 'eth': {dev,conn,ip}|None}"""
        rc, out, _ = sh(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
        res = {"wifi": None, "eth": None}
        for ln in out.splitlines():
            p = split_terse(ln)
            if len(p) < 4:
                continue
            dev, typ, state, conn = p[0], p[1], p[2], ":".join(p[3:])
            if state != "connected":
                continue
            key = "wifi" if typ == "wifi" else ("eth" if typ == "ethernet" else None)
            if key and res[key] is None:
                _, ipout, _ = sh(["nmcli", "-g", "IP4.ADDRESS", "device", "show", dev])
                ip = ipout.strip().split("\n")[0].split("|")[0].split("/")[0] if ipout.strip() else ""
                res[key] = {"dev": dev, "conn": conn, "ip": ip}
        return res

    @staticmethod
    def connect(ssid, password=None):
        """Retorna (ok, precisa_senha, mensagem)."""
        if password:
            args = ["nmcli", "--wait", "30", "device", "wifi", "connect", ssid, "password", password]
        elif ssid in Net.known_wifi():
            args = ["nmcli", "--wait", "30", "connection", "up", "id", ssid]
        else:
            args = ["nmcli", "--wait", "30", "device", "wifi", "connect", ssid]
        rc, out, err = sh(args, timeout=45)
        if rc == 0:
            return True, False, "Conectado a %s" % ssid
        low = (err + out).lower()
        need = any(k in low for k in ("secrets", "password", "senha", "no suitable", "802-1x"))
        return False, need, (err or out).strip().split("\n")[-1] or "Falha ao conectar"

    @staticmethod
    def disconnect(dev):
        sh(["nmcli", "device", "disconnect", dev])

    @staticmethod
    def forget(ssid):
        sh(["nmcli", "connection", "delete", "id", ssid])


# ---------------------------------------------------------------- BLUETOOTH
MAC = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _kv(text):
    d = {}
    for ln in text.splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            d[k.strip()] = v.strip()
    return d


class Bluetooth:
    @staticmethod
    def state():
        """None se nao ha controlador; senao {'powered':bool,'discovering':bool}"""
        rc, out, _ = sh(["bluetoothctl", "show"], timeout=5)
        if rc != 0 or "Powered" not in out:
            return None
        kv = _kv(out)
        return {"powered": kv.get("Powered", "no") == "yes", "discovering": kv.get("Discovering", "no") == "yes"}

    @staticmethod
    def set_power(on):
        sh(["bluetoothctl", "power", "on" if on else "off"])

    @staticmethod
    def devices():
        rc, out, _ = sh(["bluetoothctl", "devices"], timeout=5)
        res = []
        for ln in out.splitlines():
            p = ln.strip().split(" ", 2)
            if len(p) < 2 or p[0] != "Device" or not MAC.match(p[1]):
                continue
            mac, name = p[1], (p[2] if len(p) > 2 else p[1])
            _, info, _ = sh(["bluetoothctl", "info", mac], timeout=5)
            kv = _kv(info)
            bat = None
            m = re.search(r"\((\d+)\)", kv.get("Battery Percentage", ""))
            if m:
                bat = int(m.group(1))
            paired = kv.get("Paired") == "yes"
            if not paired and name.replace("-", ":").upper() == mac.upper():
                continue                        # dispositivo sem nome, ainda nao pareado: esconde
            res.append({"mac": mac, "name": kv.get("Alias") or kv.get("Name") or name,
                        "icon": kv.get("Icon", ""), "paired": paired, "trusted": kv.get("Trusted") == "yes",
                        "connected": kv.get("Connected") == "yes", "battery": bat})
        res.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
        return res

    @staticmethod
    def connect(mac):
        rc, out, err = sh(["bluetoothctl", "connect", mac], timeout=25)
        return rc == 0 and "Failed" not in out + err

    @staticmethod
    def disconnect(mac):
        sh(["bluetoothctl", "disconnect", mac], timeout=10)

    @staticmethod
    def pair(mac):
        rc, out, err = sh(["bluetoothctl", "--agent", "NoInputNoOutput", "pair", mac], timeout=40)
        if rc != 0 and "Paired: yes" not in out:
            rc, out, err = sh(["bluetoothctl", "pair", mac], timeout=40)
        sh(["bluetoothctl", "trust", mac], timeout=8)
        return rc == 0

    @staticmethod
    def remove(mac):
        sh(["bluetoothctl", "remove", mac], timeout=10)

    @staticmethod
    def scan_process(seconds=15):
        try:
            return subprocess.Popen(["bluetoothctl", "--timeout", str(seconds), "scan", "on"],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            return None


# ---------------------------------------------------------------- NOTIFICACOES (dunst)
def _val(x):
    return x.get("data") if isinstance(x, dict) else x


class Notif:
    @staticmethod
    def history():
        rc, out, _ = sh(["dunstctl", "history"])
        if rc != 0 or not out.strip():
            return []
        try:
            data = json.loads(out).get("data", [[]])
            items = data[0] if data else []
        except Exception:
            return []
        res = []
        for it in items:
            res.append({"id": _val(it.get("id")), "app": _val(it.get("appname")) or "",
                        "summary": _val(it.get("summary")) or "", "body": _val(it.get("body")) or "",
                        "urgency": _val(it.get("urgency")) or "NORMAL",
                        "timestamp": _val(it.get("timestamp")) or 0,
                        "icon": _val(it.get("icon_path")) or ""})
        return res

    @staticmethod
    def clear():
        sh(["dunstctl", "history-clear"])

    @staticmethod
    def clear_all():
        sh(["dunstctl", "close-all"])
        sh(["dunstctl", "history-clear"])

    @staticmethod
    def replay(notification_id):
        if str(notification_id).isdigit():
            sh(["dunstctl", "history-pop", str(notification_id)])

    @staticmethod
    def remove(notification_id):
        if str(notification_id).isdigit():
            sh(["dunstctl", "history-rm", str(notification_id)])

    @staticmethod
    def paused():
        rc, out, _ = sh(["dunstctl", "is-paused"])
        return rc == 0 and out.strip() == "true"

    @staticmethod
    def set_paused(on):
        sh(["dunstctl", "set-paused", "true" if on else "false"])


# ---------------------------------------------------------------- AREA DE TRANSFERENCIA
class Clip:
    @staticmethod
    def entries(limit=80):
        rc, out, _ = sh(["cliphist", "list"])
        res = []
        for ln in out.splitlines()[:limit]:
            if "\t" not in ln:
                continue
            cid, prev = ln.split("\t", 1)
            if cid.strip().isdigit():
                res.append({"id": cid.strip(), "text": prev, "line": ln,
                            "image": prev.startswith("[[ binary data")})
        return res

    @staticmethod
    def copy(entry_line):
        rc, out, _ = sh(["cliphist", "decode"], stdin=entry_line + "\n")
        if rc == 0:
            try:
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                p.communicate(out.encode(), timeout=3)
            except Exception:
                pass

    @staticmethod
    def delete(entry_line):
        sh(["cliphist", "delete"], stdin=entry_line + "\n")

    @staticmethod
    def wipe():
        sh(["cliphist", "wipe"])


# ---------------------------------------------------------------- TELA / ENERGIA
class Display:
    @staticmethod
    def brightness():
        """% de brilho ou None se nao ha backlight."""
        rc, out, _ = sh(["brightnessctl", "-m", "-c", "backlight", "info"])
        if rc != 0 or not out.strip():
            rc, out, _ = sh(["brightnessctl", "-m"])
        for ln in out.splitlines():
            p = ln.split(",")
            if len(p) >= 4 and p[1] == "backlight" and p[3].endswith("%"):
                try:
                    return int(p[3].rstrip("%"))
                except ValueError:
                    pass
        return None

    @staticmethod
    def set_brightness(pct):
        sh(["brightnessctl", "-c", "backlight", "set", "%d%%" % max(1, min(100, int(pct)))])

    @staticmethod
    def nightlight_on():
        return sh(["pgrep", "-x", "hyprsunset"])[0] == 0

    @staticmethod
    def set_nightlight(on):
        if on:
            if not Display.nightlight_on():
                spawn(["hyprsunset", "-t", "4300"])
        else:
            sh(["pkill", "-x", "hyprsunset"])


def uptime_text():
    try:
        s = int(float(open("/proc/uptime").read().split()[0]))
    except Exception:
        return ""
    h, m = s // 3600, (s % 3600) // 60
    return ("%dh %02dmin" % (h, m)) if h else ("%d min" % m)
