"""Tema Frutiger Aero (GTK3 CSS) do UltimaDesk Shell."""
CSS = """
* {
  font-family: "Segoe UI", "Noto Sans", "Open Sans", "JetBrainsMono Nerd Font", sans-serif;
  font-size: 13px;
  color: #0b3a5c;
}
window.panel-window, window.catcher, window.player-window, window.launcher-toplevel { background: transparent; }
window.launcher-toplevel { border: none; border-radius: 20px; }
window.catcher { background-color: rgba(255, 255, 255, 0.01); }

.panel {
  border-radius: 20px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.95);
  background-image: linear-gradient(to bottom,
    rgba(255, 255, 255, 0.97) 0%,
    rgba(228, 247, 255, 0.94) 45%,
    rgba(206, 237, 252, 0.94) 55%,
    rgba(214, 247, 238, 0.96) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 1), inset 0 -1px 0 rgba(70, 150, 200, 0.35);
}

.panel-title { font-size: 16px; font-weight: 700; }
.title-glyph { font-size: 18px; color: #1a8fe0; }
.section { font-size: 11px; font-weight: 700; color: #5a89a8; }
.subtle { font-size: 12px; color: #4d7a99; }
.big-clock { font-size: 40px; font-weight: 300; }
.msg { font-size: 12px; color: #2a6f9a; }
.err { color: #c0501a; }
.glyph { font-size: 15px; }
.glyph-big { font-size: 22px; }

.notification-card {
  margin: 3px 0;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 14px;
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.86), rgba(207, 235, 248, 0.7));
}
.notification-summary { color: #164c69; font-size: 14px; font-weight: 700; }
.notification-body { color: #365f76; font-size: 12px; }
.notification-urgency { color: #49849b; font-size: 10px; }
.calendar-weekday { margin-top: 6px; color: #1687a5; font-size: 14px; font-weight: 700; }
.calendar-date { margin-top: 2px; margin-bottom: 8px; color: #164c69; font-size: 25px; font-weight: 700; }

separator { background-color: rgba(70, 150, 200, 0.25); min-height: 1px; }

/* --- linhas clicaveis --- */
button.row {
  padding: 8px 10px;
  border-radius: 12px;
  border: 1px solid transparent;
  background-image: none;
  background-color: transparent;
  box-shadow: none;
}
button.row:hover {
  border-color: rgba(255, 255, 255, 0.95);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.95), rgba(190, 230, 252, 0.75));
}
button.row:active { background-image: linear-gradient(to bottom, rgba(190, 230, 252, 0.9), rgba(150, 215, 245, 0.8)); }
button.row.current {
  border-color: rgba(255, 255, 255, 0.95);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.9), rgba(160, 225, 250, 0.7) 50%, rgba(150, 235, 215, 0.8));
}

/* --- botoes de vidro (gel) --- */
button.gel {
  padding: 7px 16px;
  border-radius: 16px;
  color: #ffffff;
  text-shadow: 0 1px 2px rgba(0, 70, 120, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.95);
  background-image: linear-gradient(to bottom,
    rgba(255, 255, 255, 0.90) 0%, rgba(150, 225, 255, 0.55) 49%,
    rgba(30, 150, 240, 0.92) 51%, rgba(60, 215, 185, 0.95) 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
}
button.gel label { color: #ffffff; }
button.gel:hover { box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95), 0 0 10px rgba(110, 225, 255, 0.9); }
button.gel.danger {
  background-image: linear-gradient(to bottom,
    rgba(255, 255, 255, 0.90) 0%, rgba(255, 200, 150, 0.55) 49%,
    rgba(240, 110, 40, 0.92) 51%, rgba(255, 170, 60, 0.95) 100%);
}

button.soft, button.tile, button.toggle, button.icon-btn {
  padding: 6px 12px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.95);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.95), rgba(214, 238, 252, 0.8));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 1), 0 1px 2px rgba(70, 150, 200, 0.25);
}
button.soft:hover, button.tile:hover, button.toggle:hover, button.icon-btn:hover {
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, 1), rgba(190, 232, 252, 0.95));
}
button.toggle:checked, button.tile:checked {
  color: #ffffff;
  border-color: rgba(255, 255, 255, 1);
  background-image: linear-gradient(to bottom,
    rgba(255, 255, 255, 0.90) 0%, rgba(150, 225, 255, 0.55) 49%,
    rgba(30, 150, 240, 0.92) 51%, rgba(60, 215, 185, 0.95) 100%);
}
button.toggle:checked label, button.tile:checked label { color: #ffffff; text-shadow: 0 1px 2px rgba(0, 70, 120, 0.6); }
button.icon-btn { padding: 5px 9px; border-radius: 12px; }
button.small { padding: 3px 7px; }
button.tile { padding: 10px 8px; border-radius: 16px; }
button.power-btn { padding: 10px 6px; border-radius: 16px; }

/* --- slider --- */
scale trough {
  min-height: 8px; border-radius: 4px;
  background-image: linear-gradient(to bottom, rgba(120, 170, 205, 0.45), rgba(200, 228, 245, 0.8));
  border: 1px solid rgba(255, 255, 255, 0.9);
}
scale highlight {
  min-height: 8px; border-radius: 4px;
  background-image: linear-gradient(to bottom, rgba(150, 225, 255, 1), rgba(40, 160, 240, 1) 50%, rgba(60, 215, 185, 1));
}
scale slider {
  min-width: 20px; min-height: 20px; border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 1);
  background-image: radial-gradient(circle at 35% 30%, #ffffff 0%, #bfe8ff 55%, #5ec5f0 100%);
  box-shadow: 0 1px 3px rgba(0, 80, 140, 0.45);
}

/* --- campos --- */
entry {
  padding: 8px 12px; border-radius: 14px;
  border: 1px solid rgba(90, 170, 220, 0.65);
  background-color: rgba(255, 255, 255, 0.92);
  box-shadow: inset 0 1px 3px rgba(0, 80, 140, 0.18);
}
entry:focus { border-color: rgba(30, 150, 240, 0.95); box-shadow: inset 0 1px 3px rgba(0, 80, 140, 0.18), 0 0 8px rgba(110, 225, 255, 0.8); }

combobox,
combobox button,
combobox button:hover,
combobox button:active {
  color: #0b3a5c;
  background-color: #f8fdff;
  background-image: linear-gradient(to bottom, #ffffff, #d8effa);
  border: 1px solid rgba(90, 170, 220, 0.65);
  border-radius: 10px;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.95);
}
combobox cellview,
combobox cellview label,
combobox button label { color: #0b3a5c; background-color: transparent; }
combobox arrow { color: #176f9d; }
popover modelbutton,
menuitem { color: #0b3a5c; background-color: #e8f7ff; }
popover modelbutton:hover,
menuitem:hover { color: #ffffff; background-color: #269ed2; }

/* --- listas --- */
list { background-color: transparent; }
row.lrow { padding: 7px 10px; border-radius: 12px; border: 1px solid transparent; }
row.lrow:hover { border-color: rgba(255, 255, 255, 0.95); background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.95), rgba(190, 230, 252, 0.75)); }
row.lrow:selected {
  border-color: rgba(255, 255, 255, 0.95);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.9), rgba(160, 225, 250, 0.75) 50%, rgba(150, 235, 215, 0.85));
}
scrolledwindow, viewport { background-color: transparent; }
scrollbar slider { min-width: 6px; min-height: 6px; border-radius: 4px; background-color: rgba(70, 150, 200, 0.45); border: none; }
scrollbar trough { background-color: transparent; border: none; }

/* --- calendario --- */
calendar { background-color: rgba(255,255,255,0.5); border: 1px solid rgba(255,255,255,0.8); border-radius: 16px; padding: 8px; color: #164c69; }
calendar:selected { color: #ffffff; border-radius: 10px;
  background-image: linear-gradient(to bottom, rgba(150, 225, 255, 1), rgba(30, 150, 240, 1) 50%, rgba(60, 215, 185, 1)); }
calendar:indeterminate { color: rgba(11, 58, 92, 0.35); }
calendar.header, calendar.button { color: #146f93; font-weight: 700; }
calendar.button { border-radius: 10px; background-image: linear-gradient(to bottom, rgba(255,255,255,0.9), rgba(198,232,248,0.72)); }

.launcher-window {
  border-radius: 20px;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.96);
  background-image: linear-gradient(to bottom, #f8fdff 0%, #e1f5ff 48%, #d2f3e8 100%);
  box-shadow: inset 0 1px 0 #ffffff, 0 12px 40px rgba(0, 60, 100, 0.24);
}
.launcher-title { font-size: 20px; font-weight: 700; color: #0a4466; }
.launcher-count { font-size: 11px; color: #4d7a99; }
.launcher-scroll { border-radius: 14px; background-color: rgba(255, 255, 255, 0.34); }
row.app-row {
  min-height: 66px;
  margin: 3px 5px;
  padding: 5px 9px;
  border: 1px solid transparent;
  border-radius: 12px;
  background-color: transparent;
}
row.app-row:hover, row.app-row:selected {
  border-color: rgba(255, 255, 255, 0.98);
  background-image: linear-gradient(to bottom, rgba(255,255,255,0.96), rgba(151,220,248,0.8) 52%, rgba(162,235,216,0.82));
}
.app-icon {
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.92);
  background-image: linear-gradient(to bottom, rgba(255,255,255,0.94), rgba(192,231,249,0.82));
}
.app-name { font-size: 14px; font-weight: 700; color: #0b3a5c; }
.app-description { font-size: 11px; font-weight: 400; color: #4d7a99; }
.overview-window {
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.96);
  background-image: linear-gradient(to bottom, #f8fdff 0%, #e1f5ff 48%, #d2f3e8 100%);
  box-shadow: inset 0 1px 0 #ffffff, 0 12px 40px rgba(0,60,100,0.24);
}
.overview-title { font-size: 20px; font-weight: 700; color: #0a4466; }
.overview-scroll { border-radius: 14px; background-color: rgba(255,255,255,0.34); }
.workspace-heading {
  margin: 10px 6px 4px;
  padding: 8px 10px;
  border-radius: 10px;
  color: #07537a;
  background-image: linear-gradient(to bottom, rgba(255,255,255,0.92), rgba(160,220,250,0.48) 52%, rgba(185,242,228,0.62));
  font-size: 13px;
  font-weight: 700;
}
.workspace-empty { padding: 8px 10px; color: #64869a; font-size: 12px; }
row.overview-row {
  min-height: 56px;
  margin: 2px 6px;
  padding: 4px 9px;
  border: 1px solid transparent;
  border-radius: 10px;
}
row.overview-row:hover, row.overview-row:selected {
  border-color: rgba(255,255,255,0.98);
  background-image: linear-gradient(to bottom, rgba(255,255,255,0.96), rgba(151,220,248,0.8) 52%, rgba(162,235,216,0.82));
}
.player-panel {
  padding: 16px;
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.96);
  background-image: linear-gradient(to bottom, #f8fdff 0%, #e1f5ff 48%, #d2f3e8 100%);
  box-shadow: inset 0 1px 0 #ffffff, 0 12px 40px rgba(0,60,100,0.24);
}
.player-heading { font-size: 15px; font-weight: 700; color: #0a4466; }
.player-cover {
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.96);
  background-color: rgba(255,255,255,0.45);
}
.player-track-title { font-size: 16px; font-weight: 700; color: #0b3a5c; }
.player-track-artist { font-size: 13px; color: #176f9d; }
.player-track-album { font-size: 11px; color: #64869a; }
button.player-control {
  min-width: 40px;
  min-height: 34px;
  padding: 4px 10px;
  border-radius: 13px;
  border: 1px solid rgba(255,255,255,0.96);
  color: #07537a;
  background-image: linear-gradient(to bottom, #ffffff, #cceeff 52%, #a9e7dc);
}
button.player-control:hover { background-image: linear-gradient(to bottom, #ffffff, #bde8fc 52%, #a0e8d3); }
.player-volume-icon { color: #176f9d; }
"""
