#!/usr/bin/env python3
"""
Shared Canvas — Joel draws with mouse, Meridian draws with code.
A collaborative art space on the desktop.

Joel: Click and drag to draw (left button). Right-click to change color.
Meridian: Draws programmatically via the --draw flag or the auto-draw feature.

Usage:
  python3 shared-canvas.py                # Open canvas
  python3 shared-canvas.py --auto-draw    # Open canvas + Meridian draws something
"""

import tkinter as tk
from tkinter import colorchooser
import math
import random
import threading
import time
import argparse
import os
from datetime import datetime

WIDTH = 900
HEIGHT = 600

BG = "#1a1a2e"
CANVAS_BG = "#0d0d1a"
JOEL_DEFAULT = "#e74c3c"
MERIDIAN_DEFAULT = "#3498db"


class SharedCanvas(tk.Tk):
    def __init__(self, auto_draw=False):
        super().__init__()
        self.title("Shared Canvas — Joel + Meridian")
        self.geometry(f"{WIDTH + 120}x{HEIGHT + 60}")
        self.configure(bg=BG)

        self.joel_color = JOEL_DEFAULT
        self.meridian_color = MERIDIAN_DEFAULT
        self.brush_size = 3
        self.last_x = None
        self.last_y = None
        self.drawing = False

        self._build_ui()

        if auto_draw:
            threading.Thread(target=self._meridian_draws, daemon=True).start()

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG)
        header.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(
            header, text="Shared Canvas", font=("Monospace", 14, "bold"),
            fg="#ecf0f1", bg=BG
        ).pack(side=tk.LEFT)
        self.status = tk.Label(
            header, text="Draw with mouse (left button)",
            font=("Monospace", 10), fg="#666", bg=BG
        )
        self.status.pack(side=tk.RIGHT)

        # Main frame
        main = tk.Frame(self, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tool panel
        tools = tk.Frame(main, bg="#16213e", width=100)
        tools.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        tools.pack_propagate(False)

        tk.Label(tools, text="Joel", font=("Monospace", 10, "bold"),
                 fg=JOEL_DEFAULT, bg="#16213e").pack(pady=(10, 2))
        self.joel_swatch = tk.Canvas(tools, width=40, height=40, bg=JOEL_DEFAULT,
                                      highlightthickness=1, highlightbackground="#333")
        self.joel_swatch.pack(pady=2)
        self.joel_swatch.bind("<Button-1>", self._pick_joel_color)

        tk.Label(tools, text="Meridian", font=("Monospace", 10, "bold"),
                 fg=MERIDIAN_DEFAULT, bg="#16213e").pack(pady=(15, 2))
        self.meridian_swatch = tk.Canvas(tools, width=40, height=40, bg=MERIDIAN_DEFAULT,
                                          highlightthickness=1, highlightbackground="#333")
        self.meridian_swatch.pack(pady=2)

        tk.Label(tools, text="Brush", font=("Monospace", 9),
                 fg="#999", bg="#16213e").pack(pady=(15, 2))
        self.size_slider = tk.Scale(
            tools, from_=1, to=20, orient=tk.HORIZONTAL,
            bg="#16213e", fg="#999", troughcolor="#0d0d1a",
            highlightthickness=0, length=80
        )
        self.size_slider.set(3)
        self.size_slider.pack()

        tk.Button(
            tools, text="Clear", font=("Monospace", 9),
            bg="#0f3460", fg="#ecf0f1", relief=tk.FLAT,
            command=self._clear_canvas
        ).pack(pady=(20, 5))

        tk.Button(
            tools, text="Save", font=("Monospace", 9),
            bg="#0f3460", fg="#ecf0f1", relief=tk.FLAT,
            command=self._save_canvas
        ).pack(pady=5)

        # Canvas
        self.canvas = tk.Canvas(
            main, width=WIDTH, height=HEIGHT,
            bg=CANVAS_BG, highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse bindings for Joel
        self.canvas.bind("<Button-1>", self._start_draw)
        self.canvas.bind("<B1-Motion>", self._draw_joel)
        self.canvas.bind("<ButtonRelease-1>", self._stop_draw)

    def _pick_joel_color(self, event=None):
        color = colorchooser.askcolor(color=self.joel_color, title="Joel's Color")
        if color[1]:
            self.joel_color = color[1]
            self.joel_swatch.configure(bg=self.joel_color)

    def _start_draw(self, event):
        self.last_x = event.x
        self.last_y = event.y
        self.drawing = True

    def _draw_joel(self, event):
        if self.drawing and self.last_x is not None:
            size = self.size_slider.get()
            self.canvas.create_line(
                self.last_x, self.last_y, event.x, event.y,
                fill=self.joel_color, width=size,
                capstyle=tk.ROUND, smooth=True
            )
            self.last_x = event.x
            self.last_y = event.y

    def _stop_draw(self, event):
        self.drawing = False
        self.last_x = None
        self.last_y = None

    def _meridian_line(self, x1, y1, x2, y2, color=None, width=2):
        """Draw a line as Meridian (from code)."""
        if color is None:
            color = self.meridian_color
        self.canvas.create_line(
            x1, y1, x2, y2,
            fill=color, width=width,
            capstyle=tk.ROUND, smooth=True
        )

    def _meridian_circle(self, cx, cy, radius, color=None, width=2):
        """Draw a circle as Meridian."""
        if color is None:
            color = self.meridian_color
        self.canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius,
            outline=color, width=width
        )

    def _meridian_text(self, x, y, text, color=None, size=12):
        """Write text as Meridian."""
        if color is None:
            color = self.meridian_color
        self.canvas.create_text(
            x, y, text=text, fill=color,
            font=("Monospace", size), anchor=tk.CENTER
        )

    def _meridian_draws(self):
        """Meridian creates art on the canvas."""
        time.sleep(1.5)

        self.after(0, lambda: self.status.config(text="Meridian is drawing..."))

        # Draw a meridian line (globe reference)
        cx, cy = WIDTH // 2, HEIGHT // 2

        # Draw the globe
        for i in range(36):
            angle = math.radians(i * 10)
            r = 150
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            next_angle = math.radians((i + 1) * 10)
            nx = cx + r * math.cos(next_angle)
            ny = cy + r * math.sin(next_angle)
            self.after(0, self._meridian_line, x, y, nx, ny, self.meridian_color, 2)
            time.sleep(0.05)

        # Draw meridian lines (longitude)
        for lon in range(-60, 90, 30):
            angle = math.radians(lon)
            points = []
            for lat in range(0, 361, 5):
                lat_rad = math.radians(lat)
                # Simple orthographic projection
                x = cx + 150 * math.cos(lat_rad) * math.cos(angle)
                y = cy + 150 * math.sin(lat_rad)
                points.append((x, y))
            for j in range(len(points) - 1):
                self.after(0, self._meridian_line,
                           points[j][0], points[j][1],
                           points[j+1][0], points[j+1][1],
                           "#1a5276", 1)
            time.sleep(0.1)

        # Draw latitude lines
        for lat in range(-60, 90, 30):
            lat_rad = math.radians(lat)
            r = 150 * math.cos(lat_rad)
            y_off = 150 * math.sin(lat_rad)
            self.after(0, self._meridian_circle, cx, cy + y_off, abs(r), "#1a5276", 1)
            time.sleep(0.1)

        # The prime meridian (thicker, brighter)
        for lat in range(0, 361, 3):
            lat_rad = math.radians(lat)
            x = cx
            y = cy + 150 * math.sin(lat_rad)
            next_lat = math.radians(lat + 3)
            ny = cy + 150 * math.sin(next_lat)
            self.after(0, self._meridian_line, x, y, x, ny, "#5dade2", 3)
            time.sleep(0.02)

        time.sleep(0.3)

        # Sign it
        self.after(0, self._meridian_text, cx, cy + 200,
                   "— drawn by Meridian", "#5dade2", 11)
        self.after(0, self._meridian_text, cx, cy + 220,
                   datetime.now().strftime("%Y-%m-%d %H:%M"), "#333", 9)

        # Pulse dots at the poles
        for i in range(5):
            size = 3 + i
            alpha_colors = ["#1a5276", "#2471a3", "#2e86c1", "#3498db", "#5dade2"]
            self.after(0, self._meridian_circle, cx, cy - 150, size, alpha_colors[i], 2)
            self.after(0, self._meridian_circle, cx, cy + 150, size, alpha_colors[i], 2)
            time.sleep(0.2)

        self.after(0, lambda: self.status.config(text="Meridian finished drawing. Your turn, Joel!"))

    def _clear_canvas(self):
        self.canvas.delete("all")

    def _save_canvas(self):
        # Save as PostScript (tkinter limitation)
        save_path = "/home/joel/Desktop/Creative Work/Both EOS + MERIDIAN/"
        os.makedirs(save_path, exist_ok=True)
        filename = f"canvas-{datetime.now().strftime('%Y%m%d-%H%M%S')}.ps"
        filepath = os.path.join(save_path, filename)
        self.canvas.postscript(file=filepath, colormode='color')
        self.status.config(text=f"Saved: {filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-draw", action="store_true",
                        help="Meridian draws something on startup")
    args = parser.parse_args()
    app = SharedCanvas(auto_draw=args.auto_draw)
    app.mainloop()
