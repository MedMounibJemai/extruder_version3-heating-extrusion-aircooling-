import math
import sys
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageFont, ImageTk

# Détection de la plateforme pour choisir le chemin de la police
if sys.platform.startswith('win'):
    font_path = "C:/Windows/Fonts/arial.ttf"
else:
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def interpolate_color(c1, c2, t):
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return (r, g, b)

def rgb_to_hex(rgb):
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

def draw_aa_ring(size, arc_width, ratio, bg_color, start_color, end_color, num_steps=150):
    scale = 4
    w, h = size
    big_w, big_h = w * scale, h * scale
    img = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = big_w // 2, big_h // 2
    radius = min(cx, cy) - (arc_width * scale) // 2 - 10
    radius = max(0, radius)
    bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
    draw.arc(bbox, start=0, end=360, fill=bg_color, width=int(arc_width * scale))
    angle_extent = ratio * 360
    start_angle = 270
    if angle_extent > 0:
        for i in range(num_steps):
            seg_start = start_angle + (i / num_steps) * angle_extent
            seg_end = start_angle + ((i + 1) / num_steps) * angle_extent
            t = i / (num_steps - 1) if num_steps > 1 else 0
            seg_color = interpolate_color(start_color, end_color, t)
            draw.arc(bbox, start=seg_start, end=seg_end, fill=seg_color, width=int(arc_width * scale))
    final_img = img.resize((w, h), Image.Resampling.LANCZOS)
    return final_img

def draw_indicator_circle(diameter, color):
    scale = 4
    d = int(diameter * scale)
    img = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, d, d), fill=color)
    img_small = img.resize((diameter, diameter), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(img_small)

class NumericKeypad(tk.Toplevel):
    def __init__(self, parent, title="Saisir la consigne", callback=None):
        super().__init__(parent)
        self.title(title)
        self.callback = callback
        self.configure(bg="#222222")
        self.resizable(False, False)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Modern.TButton",
                        font=("Helvetica", 14, "bold"),
                        foreground="#FFFFFF",
                        background="#444444",
                        padding=10,
                        borderwidth=0,
                        relief="flat")
        style.map("Modern.TButton", background=[("active", "#666666")])
        self.entry_value = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.entry_value,
                               font=("Helvetica", 20), justify="right", width=10)
        self.entry.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
        for i in range(3):
            self.columnconfigure(i, weight=1)
        for i in range(1, 5):
            self.rowconfigure(i, weight=1)
        buttons = [
            ("1", 1, 0), ("2", 1, 1), ("3", 1, 2),
            ("4", 2, 0), ("5", 2, 1), ("6", 2, 2),
            ("7", 3, 0), ("8", 3, 1), ("9", 3, 2),
            ("0", 4, 1)
        ]
        for (text, row, col) in buttons:
            btn = ttk.Button(self, text=text, style="Modern.TButton",
                             command=lambda t=text: self.append_digit(t))
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        btn_clear = ttk.Button(self, text="Effacer", style="Modern.TButton",
                               command=self.clear_entry)
        btn_clear.grid(row=4, column=0, padx=5, pady=5, sticky="nsew")
        btn_enter = ttk.Button(self, text="Enter", style="Modern.TButton",
                               command=self.validate)
        btn_enter.grid(row=4, column=2, padx=5, pady=5, sticky="nsew")
        ####################
        # --- Focus + comportement tactile ---
        self.transient(parent)     # au-dessus de la fenêtre parent
        #self.grab_set()            # modal (évite clics derrière)
        self.lift()                # ramener au premier plan
        self.entry.focus_set()     # focus sur l'entrée
        # ⚠️ grab_set() après que la fenêtre soit visible
        self.after(0, self._apply_grab)

    def _apply_grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            # Si encore pas viewable, on réessaie très vite
            self.after(10, self._apply_grab)
        ####################
    def append_digit(self, digit):
        self.entry_value.set(self.entry_value.get() + digit)

    def clear_entry(self):
        self.entry_value.set("")

    def validate(self):
        val_str = self.entry_value.get()
        try:
            val_int = int(val_str)
            if self.callback:
                self.callback(val_int)
            self.destroy()
        except ValueError:
            self.entry_value.set("")

class AAOnOffButton(tk.Canvas):
    def __init__(self, parent, width=90, height=40,
                 initial_state=False, button_color=(184,57,46),
                 command=None, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=kwargs.get("bg", "#FFFFFF"), highlightthickness=0)
        self.state = initial_state
        self.command = command
        self.bg_color_pil = button_color
        self.fg_color = (255, 255, 255)
        self.text_on_color = "#000000"
        self.text_off_color = "#000000"
        self.roundness = 15
        self._photo = None
        self.disabled = False
        self.disabled_blink = True
        self.after(500, self.toggle_disabled_blink)
        self.bind("<Button-1>", self._toggle)
        self.bind("<Configure>", lambda e: self._redraw())

    def _toggle(self, event=None):
        if self.disabled:
            return
        self.state = not self.state
        self._redraw()
        if self.command:
            self.command(self.state)

    def toggle_disabled_blink(self):
        if self.disabled:
            self.disabled_blink = not self.disabled_blink
            self._redraw()
        self.after(500, self.toggle_disabled_blink)

    def _create_round_rect(self, draw, x1, y1, x2, y2, r, fill):
        draw.pieslice((x1, y1, x1 + 2*r, y1 + 2*r), 180, 270, fill=fill)
        draw.pieslice((x2 - 2*r, y1, x2, y1 + 2*r), 270, 360, fill=fill)
        draw.pieslice((x2 - 2*r, y2 - 2*r, x2, y2), 0, 90, fill=fill)
        draw.pieslice((x1, y2 - 2*r, x1 + 2*r, y2), 90, 180, fill=fill)
        draw.rectangle((x1 + r, y1, x2 - r, y2), fill=fill)
        draw.rectangle((x1, y1 + r, x2, y2 - r), fill=fill)

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width() or 90
        h = self.winfo_height() or 40
        scale = 4
        big_w, big_h = w * scale, h * scale

        if self.disabled and not self.disabled_blink:
            fill_color = (200, 200, 200)
        else:
            fill_color = self.bg_color_pil

        img = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        r_big = min(self.roundness, h // 2, w // 4) * scale

        self._create_round_rect(draw, 0, 0, big_w, big_h, r_big, fill=fill_color)

        if self.state:
            self._create_round_rect(draw, 0, 0, big_w // 2, big_h, r_big, fill=(255,255,255))
        else:
            self._create_round_rect(draw, big_w // 2, 0, big_w, big_h, r_big, fill=(255,255,255))
        font_size = int(big_h * 0.5)
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception as e:
            print("Erreur lors du chargement de la police:", e)
            font = ImageFont.load_default()
        on_text = "ON"
        off_text = "OFF"
        bbox_on = font.getbbox(on_text)
        on_w = bbox_on[2] - bbox_on[0]
        on_h = bbox_on[3] - bbox_on[1]
        bbox_off = font.getbbox(off_text)
        off_w = bbox_off[2] - bbox_off[0]
        off_h = bbox_off[3] - bbox_off[1]
        on_x = big_w / 4
        off_x = 3 * big_w / 4
        text_y = big_h / 2
        if self.state:
            on_color = self.text_on_color
            off_color = "#FFFFFF"
        else:
            on_color = "#FFFFFF"
            off_color = self.text_off_color
        draw.text((on_x - on_w/2, text_y - on_h/2), on_text, fill=on_color, font=font)
        draw.text((off_x - off_w/2, text_y - off_h/2), off_text, fill=off_color, font=font)
        final_img = img.resize((w, h), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(final_img)
        self.create_image(0, 0, anchor=tk.NW, image=self._photo)

class ParameterUI(tk.Frame):
    """
    Cadran de paramètre (Température, Vitesse Moteur, Refroidissement).
    Le nom du cadran n'est plus dessiné dans le canvas (il est prévu à l'extérieur).
    """
    def __init__(self, parent,
                 max_value, unit,
                 full_color, pale_color,
                 parameter_name,
                 initial_target, current_value,
                 indicator_emoji,
                 button_color,
                 serial_callback=None,
                 temp_widget=None,
                 **kwargs):
        super().__init__(parent, **kwargs)
        self.max_value = max_value
        self.unit = unit
        self.full_color = full_color
        self.pale_color = pale_color
        self.parameter_name = parameter_name
        self.target_value = initial_target
        self.current_value = current_value
        self.indicator_emoji = indicator_emoji
        self.button_color = button_color
        self.power_on = False
        self.serial_callback = serial_callback
        self.pwm_value = 0
        self.rpm_est_value = 0.0  # pour Ventilation (RPM estimé)


        self.temp_value = None
        self.temp_target = None
        self.control_enabled = False

        self.temp_widget = temp_widget

        if self.parameter_name == "Vitesse Moteur":
            self.warn_visible = True
            self.after(500, self.toggle_warning)

        self.arc_width = int(20 * 1.5)
        self.canvas = tk.Canvas(self, bg=self["bg"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.power_button = AAOnOffButton(
            self, width=90, height=40,
            initial_state=False,
            button_color=self.button_color,
            command=self.on_power_toggle,
            bg=self["bg"]
        )
        self.power_button.pack(pady=20)

        self._keypad = None
        self.dragging = False

        self.led_blink = True
        self.led_visible = True
        self.after(500, self.toggle_led)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def toggle_led(self):
        if self.led_blink:
            self.led_visible = not self.led_visible
            self._redraw()
        self.after(500, self.toggle_led)

    def toggle_warning(self):
        if self.parameter_name == "Vitesse Moteur":
            if self.control_enabled and self.temp_value is not None and self.temp_target is not None:
                if self.temp_value < 0.7 * self.temp_target:
                    self.warn_visible = True
                else:
                    self.warn_visible = False
            else:
                self.warn_visible = False
        else:
            self.warn_visible = False
        self._redraw()
        self.after(500, self.toggle_warning)

    def _on_canvas_configure(self, event):
        self._redraw()

    def on_power_toggle(self, state):
        # Pour le moteur, on vérifie deux conditions :
        # 1. Le widget température (temp_widget) doit être activé.
        # 2. La température actuelle doit être au moins 70% de la consigne.
        if self.parameter_name == "Vitesse Moteur" and state:
            if self.temp_widget is None or not self.temp_widget.power_on:
                import tkinter.messagebox as messagebox
                messagebox.showwarning("Attention",
                    "Démarrer le moteur sans activer la température peut endommager le moteur !")
                self.power_on = False
                self.power_button.state = False
                self.power_button.disabled = True
                self._redraw()
                return
            if self.temp_value is not None and self.temp_target is not None:
                if self.temp_value < 0.7 * self.temp_target:
                    import tkinter.messagebox as messagebox
                    messagebox.showwarning("Température Limite",
                                           "La température est insuffisante pour démarrer le moteur.")
                    self.power_on = False
                    self.power_button.disabled = True
                    self._redraw()
                    return
        self.power_on = state
        self._redraw()
        if self.serial_callback :
            if self.parameter_name == "Température":
                if self.power_on:
                    self.serial_callback("DEMARRER")
                    self.serial_callback(f"SETPOINT:{self.target_value}")
                else:
                    self.serial_callback("STOP")

            elif self.parameter_name == "Vitesse Moteur":
                if self.power_on:
                    self.serial_callback("EXTRUDER:ON")
                    # Optionnel: pousser la vitesse courante (utile si on allume à une valeur ≠ 0)
                    self.serial_callback(f"EXTRUDER:{self.target_value}")
                else:
                    self.serial_callback("EXTRUDER:OFF")
            elif self.parameter_name == "Ventilation":
                if self.power_on:
                    self.serial_callback("POWER:1")
                    self.serial_callback(f"DUTY:{int(self.target_value)}")
                else:
                    self.serial_callback("POWER:0")


    def increase_value(self):
        if not self.power_on:
            return
        self.target_value += 1
        if self.target_value > self.max_value:
            self.target_value = self.max_value
        self._redraw()
        if self.serial_callback :
            if self.parameter_name == "Température":
                self.serial_callback(f"SETPOINT:{self.target_value}")
            elif self.parameter_name == "Vitesse Moteur":
                self.serial_callback(f"EXTRUDER:{self.target_value}")
            elif self.parameter_name == "Ventilation":
                self.serial_callback(f"DUTY:{int(self.target_value)}")


    def decrease_value(self):
        if not self.power_on:
            return
        self.target_value -= 1
        if self.target_value < 0:
            self.target_value = 0
        self._redraw()
        if self.serial_callback :
            if self.parameter_name == "Température":
                self.serial_callback(f"SETPOINT:{self.target_value}")
            elif self.parameter_name == "Vitesse Moteur":
                self.serial_callback(f"EXTRUDER:{self.target_value}")
            elif self.parameter_name == "Ventilation":
                self.serial_callback(f"DUTY:{int(self.target_value)}")



    def _open_keypad(self, event):
        # ❌ Si le cadran est OFF → on ne fait rien
        if not self.power_on:   
            return
        if self._keypad is not None and tk.Toplevel.winfo_exists(self._keypad):
            return
        

        def set_new_value(value):
            if value < 0:
                value = 0
            if value > self.max_value:
                value = self.max_value
            self.target_value = float(value)
            self._redraw()
            if self.serial_callback :
                if self.parameter_name == "Température":
                    self.serial_callback(f"SETPOINT:{self.target_value}")
                elif self.parameter_name == "Vitesse Moteur":
                    self.serial_callback(f"EXTRUDER:{self.target_value}")
                elif self.parameter_name == "Ventilation":
                    self.serial_callback(f"DUTY:{int(self.target_value)}")

        
            self._keypad = None

        self._keypad = NumericKeypad(self, title="Saisir la consigne", callback=set_new_value)

        

        self._keypad.protocol("WM_DELETE_WINDOW", lambda: (self._keypad.destroy(), setattr(self, "_keypad", None)))
        
    def _on_press(self, event):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        base = min(w, h)
        cx, cy = w / 2, h / 2
        ratio = self.target_value / self.max_value if self.max_value else 0
        angle_rad = math.radians(270 + ratio * 360)
        r_arc = base / 2 - self.arc_width / 2 - 10
        if r_arc < 0:
            r_arc = 0
        pointer_offset = base * 0.03
        pointer_radius = base * 0.03
        px = cx + (r_arc + pointer_offset) * math.cos(angle_rad)
        py = cy + (r_arc + pointer_offset) * math.sin(angle_rad)
        dist = math.hypot(event.x - px, event.y - py)
        self.dragging = (dist <= pointer_radius * 1.5)

    def _on_drag(self, event):
        if not self.dragging or not self.power_on:
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx, cy = w / 2, h / 2
        dx = event.x - cx
        dy = event.y - cy
        theta = math.degrees(math.atan2(dy, dx))
        angle_adjusted = (theta - 270) % 360
        new_ratio = angle_adjusted / 360.0
        self.target_value = new_ratio * self.max_value
        self._redraw()

    def _on_release(self, event):
        self.dragging = False
        if self.serial_callback :
            if self.parameter_name == "Température":
                self.serial_callback(f"SETPOINT:{self.target_value}")
            elif self.parameter_name == "Vitesse Moteur":
                self.serial_callback(f"EXTRUDER:{self.target_value}")
            elif self.parameter_name == "Ventilation":
                self.serial_callback(f"DUTY:{int(self.target_value)}")


    def _redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        cx, cy = w / 2, h / 2
        ratio = 0
        if self.max_value:
            ratio = self.target_value / self.max_value

        if self.power_on:
            arc_img_pil = draw_aa_ring(
                size=(w, h),
                arc_width=self.arc_width,
                ratio=ratio,
                bg_color=(238, 238, 238),
                start_color=self.pale_color,
                end_color=self.full_color
            )
        else:
            arc_img_pil = draw_aa_ring(
                size=(w, h),
                arc_width=self.arc_width,
                ratio=ratio,
                bg_color=(238, 238, 238),
                start_color=(200, 200, 200),
                end_color=(200, 200, 200)
            )
        self.arc_photo = ImageTk.PhotoImage(arc_img_pil)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.arc_photo)

        base = min(w, h)
        angle_rad = math.radians(270 + ratio * 360)
        r_arc = base / 2 - self.arc_width / 2 - 10
        if r_arc < 0:
            r_arc = 0
        pointer_offset = base * 0.03
        pointer_radius = base * 0.03
        px = cx + (r_arc + pointer_offset) * math.cos(angle_rad)
        py = cy + (r_arc + pointer_offset) * math.sin(angle_rad)
        circle_color = self.full_color if self.power_on else (170, 170, 170)
        indicator_img = draw_indicator_circle(int(pointer_radius * 2), circle_color)
        self.canvas.create_image(px, py, anchor="center", image=indicator_img)
        self.indicator_img = indicator_img

        base = min(w, h)
        main_font_size = int(base * 0.09)
        val_str = f"{self.target_value:.1f}{self.unit}"
        main_y = cy - 0.15 * base
        self.canvas.create_text(cx, main_y,
                                text=val_str,
                                fill="#333333",
                                font=("Helvetica", main_font_size, "bold"),
                                tags="main_text")
        self.canvas.tag_bind("main_text", "<Double-Button-1>", self._open_keypad)

        line_len = 0.2 * base
        line_y = main_y + 0.06 * base
        self.canvas.create_line(cx - line_len / 2, line_y,
                                cx + line_len / 2, line_y, fill="#999999")

        sec_font_size = int(base * 0.04)
        sec_y = line_y + 0.07 * base
        
        if self.parameter_name == "Ventilation":
            curr_str = f"{self.rpm_est_value:.0f}rpm"
        else:
            curr_str = f"{self.current_value:.1f}{self.unit}"

        self.canvas.create_text(cx, sec_y,
                                text=curr_str,
                                fill="#666666",
                                font=("Helvetica", sec_font_size))

        
        icon_y = sec_y + 0.10 * base
        icon_color = rgb_to_hex(self.full_color) if self.power_on else "#AAAAAA"
        self.canvas.create_text(cx, icon_y,
                                text=self.indicator_emoji,
                                fill=icon_color,
                                font=("Helvetica", int(main_font_size * 0.8), "bold"))
        
        # Affichage du warning "Température Limite" pour le moteur
        if self.parameter_name == "Vitesse Moteur" and self.temp_value is not None and self.temp_target is not None:
            if self.control_enabled and self.temp_value < 0.7 * self.temp_target:
                font_size_warning = int(sec_font_size * 0.95)
                warning_y = icon_y + 0.12 * base
                self.canvas.create_text(cx, warning_y,
                                        text="Température Limite",
                                        fill="red",
                                        font=("Helvetica", font_size_warning, "bold"))
        
        # Affichage du PWM pour le widget Température
        if self.parameter_name == "Température" and self.power_on:
            pwm_y = icon_y + 0.12 * base
            pwm_str = f"PWM: {self.pwm_value:.1f}"
            reduced_font_size = int(sec_font_size * 1)
            base_color = (0, 153, 76) if self.pwm_value != 0 else (184, 57, 46)
            if self.led_visible:
                text_color = rgb_to_hex(base_color)
                self.canvas.create_text(cx, pwm_y,
                                        text=pwm_str,
                                        fill=text_color,
                                        font=("Helvetica", reduced_font_size, "bold"))
        
        plus_minus_color = rgb_to_hex(self.full_color) if self.power_on else "#AAAAAA"
        plus_minus_font_size = int(base * 0.1)
        offset_x = 0.25 * base
        offset_y = 0.05 * base
        minus_x = cx - offset_x
        minus_y = cy + offset_y
        self.canvas.create_text(minus_x, minus_y,
                                text="–",
                                fill=plus_minus_color,
                                font=("Helvetica", plus_minus_font_size, "bold"),
                                tags="minus_text")
        self.canvas.tag_bind("minus_text", "<Button-1>", lambda e: self.decrease_value())
        plus_x = cx + offset_x
        plus_y = cy + offset_y
        self.canvas.create_text(plus_x, plus_y,
                                text="+",
                                fill=plus_minus_color,
                                font=("Helvetica", plus_minus_font_size, "bold"),
                                tags="plus_text")
        self.canvas.tag_bind("plus_text", "<Button-1>", lambda e: self.increase_value())
        
        # Mise à jour finale du bouton pour le moteur
        if self.parameter_name == "Vitesse Moteur":
            if self.control_enabled and self.temp_value is not None and self.temp_target is not None and self.temp_value < 0.7 * self.temp_target:
                self.power_on = False
                self.power_button.disabled = True
            else:
                self.power_button.disabled = False
            self.power_button._redraw()
        
        if self.parameter_name == "Ventilation":
            curr_str = f"{self.current_value:.0f}rpm"   # current_value = rpm estimée
        else:
            curr_str = f"{self.current_value:.1f}{self.unit}"

    def update_display(self):
        self._redraw()
