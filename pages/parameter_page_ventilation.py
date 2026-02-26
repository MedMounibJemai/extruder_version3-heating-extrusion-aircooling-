import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageTk
import sys

from pages.parameter_ui_ventilation import ParameterUI

# --- Police (comme dans ton UI) ---
if sys.platform.startswith('win'):
    FONT_PATH = "C:/Windows/Fonts/arial.ttf"
else:
    FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


class AAFanSelector(tk.Canvas):
    """
    Sélecteur 3 positions LF/RF/CF style 'pill' (arrondi + anti-aliasing via PIL),
    sans séparateurs visibles. Click = change selected + callback(value)
    """
    def __init__(self, parent, items, command=None,
                 width=220, height=28,
                 radius=14,
                 bg="#FFFFFF",
                 idle_fill="#F2F2F2",
                 idle_text="#222222",
                 border="#D0D0D0",
                 active_fill="#0B5ED7",
                 active_text="#FFFFFF",
                 font_size=11,
                 **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=bg, highlightthickness=0, **kwargs)

        self.items = items              # [("LF","left"), ("RF","right"), ("CF","center")]
        self.command = command
        self.bg = bg
        self.idle_fill = idle_fill
        self.idle_text = idle_text
        self.border = border
        self.active_fill = active_fill
        self.active_text = active_text
        self.radius = radius
        self.font_size = font_size

        self.selected = items[0][1]     # valeur par défaut
        self._photo = None
        self._hit = []                  # zones cliquables (x0,x1,value)

        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda e: self._redraw())
        self._redraw()

    def set(self, value: str):
        self.selected = value
        self._redraw()

    def _rounded_rect(self, draw, x1, y1, x2, y2, r, fill, outline=None, outline_w=1):
        # Rectangle arrondi PIL
        draw.rounded_rectangle((x1, y1, x2, y2), radius=r, fill=fill,
                               outline=outline, width=outline_w)

    def _redraw(self):
        self.delete("all")

        w = self.winfo_width() or int(self["width"])
        h = self.winfo_height() or int(self["height"])

        scale = 4
        big_w, big_h = w * scale, h * scale
        r_big = min(self.radius, h // 2) * scale

        # image AA
        img = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # conteneur pill
        self._rounded_rect(
            draw, 2, 2, big_w - 2, big_h - 2, r_big,
            fill=self.idle_fill, outline=self.border, outline_w=2
        )

        n = len(self.items)
        seg_w = big_w / n

        # segment actif (dessiné par-dessus) -> pas de lignes internes
        for i, (label, value) in enumerate(self.items):
            if value != self.selected:
                continue

            x0 = int(i * seg_w)
            x1 = int((i + 1) * seg_w)

            # padding adaptatif : si segment trop petit, pad=0
            pad = 2
            if (x1 - x0) <= (pad * 2 + 4):
                pad = 0

            x0 = max(2, x0 + pad)
            x1 = min(big_w - 2, x1 - pad)

            # sécurité absolue : éviter x1 < x0
            if x1 <= x0:
                x0 = max(2, int(i * seg_w))
                x1 = min(big_w - 2, int((i + 1) * seg_w))
                if x1 <= x0:
                    return  # rien à dessiner, widget trop petit

            if i == 0:
                # gauche arrondi
                self._rounded_rect(draw, 2, 2, x1, big_h - 2, r_big,
                                   fill=self.active_fill, outline=None, outline_w=0)
            elif i == n - 1:
                # droite arrondi
                self._rounded_rect(draw, x0, 2, big_w - 2, big_h - 2, r_big,
                                   fill=self.active_fill, outline=None, outline_w=0)
            else:
                # milieu rectangle
                draw.rectangle((x0, 2, x1, big_h - 2), fill=self.active_fill)


        # texte
        try:
            font = ImageFont.truetype(FONT_PATH, int(self.font_size * scale))
        except Exception:
            font = ImageFont.load_default()

        self._hit = []
        for i, (label, value) in enumerate(self.items):
            x0 = int(i * seg_w)
            x1 = int((i + 1) * seg_w)

            is_active = (value == self.selected)
            color = self.active_text if is_active else self.idle_text

            bbox = font.getbbox(label)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = int((x0 + x1) / 2 - tw / 2)
            ty = int(big_h / 2 - th / 2)

            draw.text((tx, ty), label, fill=color, font=font)

            # hitbox en coords canvas
            self._hit.append((int(x0 / scale), int(x1 / scale), value))

        # resize -> canvas
        final_img = img.resize((w, h), Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(final_img)
        self.create_image(0, 0, anchor=tk.NW, image=self._photo)

    def _on_click(self, event):
        x = event.x
        for x0, x1, value in self._hit:
            if x0 <= x <= x1:
                if value != self.selected:
                    self.selected = value
                    self._redraw()
                    if self.command:
                        self.command(value)
                return


class ParameterPage(tk.Frame):
    def __init__(self, parent, config_data, serial_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.config_data = config_data
        self.serial_callback = serial_callback

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.container = tk.Frame(self, bg="#FFFFFF")
        self.container.grid(row=0, column=0, sticky="nsew")
        for i in range(3):
            self.container.columnconfigure(i, weight=1)

        # ---------- configs ----------
        temp_conf = self.config_data.get("Température", {})
        motor_conf = self.config_data.get("Moteur", {})
        vent_conf = self.config_data.get("Ventilation", {})

        init_temp = temp_conf.get("min", 30)
        init_motor = motor_conf.get("min", 10)
        init_vent = vent_conf.get("min", 0)

        max_temp = temp_conf.get("max", 300)
        max_motor = motor_conf.get("max", 250)
        max_vent = vent_conf.get("max", 100)

        # ================== TEMP ==================
        frame_temp = tk.Frame(self.container, bg="#FFFFFF")
        frame_temp.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        label_temp = tk.Label(frame_temp, text="Température",
                              font=("Helvetica", 18, "bold"), bg="#FFFFFF")
        label_temp.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        self.temp_ui = ParameterUI(
            frame_temp,
            max_value=max_temp, unit="°C",
            full_color=(184, 57, 46), pale_color=(255, 220, 220),
            parameter_name="Température",
            initial_target=init_temp, current_value=init_temp,
            indicator_emoji="🔥",
            button_color=(184, 57, 46),
            serial_callback=self.serial_callback,
            bg="#FFFFFF"
        )
        self.temp_ui.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ================== MOTOR ==================
        frame_motor = tk.Frame(self.container, bg="#FFFFFF")
        frame_motor.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        label_motor = tk.Label(frame_motor, text="Moteur Extrusion",
                               font=("Helvetica", 18, "bold"), bg="#FFFFFF")
        label_motor.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        self.motor_ui = ParameterUI(
            frame_motor,
            max_value=max_motor, unit="rpm",
            full_color=(0, 153, 76), pale_color=(200, 255, 200),
            parameter_name="Vitesse Moteur",
            initial_target=init_motor, current_value=init_motor,
            indicator_emoji="⚙️",
            button_color=(0, 153, 76),
            serial_callback=self.serial_callback,
            bg="#FFFFFF",
            temp_widget=self.temp_ui
        )
        self.motor_ui.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ================== VENT ==================
        frame_vent = tk.Frame(self.container, bg="#FFFFFF")
        frame_vent.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        # Titre (comme les autres colonnes)
        label_vent = tk.Label(frame_vent, text="Ventilation",
                            font=("Helvetica", 18, "bold"), bg="#FFFFFF")
        label_vent.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        # ---- Etat mémorisé par fan ----
        self.vent_selected = tk.StringVar(value="center")
        self.vent_state = {
            "left":   {"duty": 0, "on": False, "rpm": 0.0},
            "right":  {"duty": 0, "on": False, "rpm": 0.0},
            "center": {"duty": 0, "on": False, "rpm": 0.0},
        }
        self._last_selected = self.vent_selected.get()

        # ---- Cadran ----
        self.vent_ui = ParameterUI(
            frame_vent,
            max_value=max_vent,
            unit="%",
            full_color=(0, 102, 204),
            pale_color=(200, 220, 255),
            parameter_name="Ventilation",
            initial_target=init_vent,
            current_value=0,
            indicator_emoji="💨",
            button_color=(0, 102, 204),
            serial_callback=self._vent_serial_callback,
            bg="#FFFFFF"
        )
        self.vent_ui.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ---- Sélecteur (dans le cadran, pas dans frame_vent) ----
        def on_pick(value):
            self._set_vent_selected(value)

        self.sel_frame = tk.Frame(self.vent_ui, bg="#FFFFFF")  # IMPORTANT: parent = self.vent_ui
        self.vent_selector = AAFanSelector(
            self.sel_frame,
            items=[("LF", "left"), ("CF", "center"), ("RF", "right")],
            command=on_pick,
            width=190, height=24,  # tu peux ajuster
            bg="#FFFFFF"
        )
        self.vent_selector.pack()

        # Placement initial + reposition auto
        self.sel_frame.place(relx=0.5, rely=0.76, anchor="center")
        #self.vent_ui.bind("<Configure>", lambda e: self._place_vent_selector())

        # Sync état initial
        self.vent_selector.set(self.vent_selected.get())


    # -----------------------------------------------------------------
    # CONFIG UPDATE
    def update_config(self, new_config):
        current_temp_target = self.temp_ui.target_value
        current_motor_target = self.motor_ui.target_value
        current_vent_target = self.vent_ui.target_value

        self.config_data = new_config
        temp_conf = self.config_data.get("Température", {})
        motor_conf = self.config_data.get("Moteur", {})
        vent_conf = self.config_data.get("Ventilation", {})

        self.temp_ui.max_value = temp_conf.get("max", 300)
        self.motor_ui.max_value = motor_conf.get("max", 250)
        self.vent_ui.max_value = vent_conf.get("max", 100)

        self.temp_ui.target_value = current_temp_target
        self.motor_ui.target_value = current_motor_target
        self.vent_ui.target_value = current_vent_target

        self.temp_ui.update_display()
        self.motor_ui.update_display()
        self.vent_ui.update_display()

    # -----------------------------------------------------------------
    # VENT : utilitaires état / sélection
    def get_selected_fan(self) -> str:
        return self.vent_selected.get()

    def _save_current_vent_state(self):
        fan = self._last_selected
        self.vent_state[fan]["duty"] = int(self.vent_ui.target_value)
        self.vent_state[fan]["on"] = bool(self.vent_ui.power_on)
        self.vent_state[fan]["rpm"] = float(getattr(self.vent_ui, "rpm_est_value", 0.0))

    def _load_vent_state(self, fan: str):
        st = self.vent_state[fan]
        self.vent_ui.target_value = st["duty"]
        self.vent_ui.power_on = st["on"]
        self.vent_ui.power_button.state = st["on"]
        # ✅ restaurer RPM affiché
        self.vent_ui.rpm_est_value = st.get("rpm", 0.0)
        self.vent_ui.update_display()

    def _set_vent_selected(self, fan_key: str):
        # sauvegarde état ancien
        self._save_current_vent_state()

        # change sélection
        self.vent_selected.set(fan_key)
        self._last_selected = fan_key

        # charge état nouveau
        self._load_vent_state(fan_key)

        # sync visuel selector
        self.vent_selector.set(fan_key)

        # info optionnelle vers main
        # if self.serial_callback:
        #     self.serial_callback(f"VENTILATION_SELECT:{fan_key}")
    
    def _estimate_rpm(self, fan: str, duty: float) -> float:
        curve_7500 = [(0,0),(20,1770),(40,3506),(60,5040),(80,6300),(100,7410)]
        curve_7000 = [(0,0),(20,1918),(40,2610),(60,3986),(80,5424),(100,6720)]
        pts = curve_7000 if fan == "center" else curve_7500

        duty = max(0.0, min(100.0, float(duty)))
        if duty <= pts[0][0]:
            return float(pts[0][1])
        if duty >= pts[-1][0]:
            return float(pts[-1][1])

        for (x0,y0),(x1,y1) in zip(pts[:-1], pts[1:]):
            if x0 <= duty <= x1:
                t = (duty-x0)/(x1-x0) if x1!=x0 else 0.0
                return float(y0 + t*(y1-y0))
        return float(pts[-1][1])


    # -----------------------------------------------------------------
    # VENT : callback vers main (ajoute le fan)
    # def _vent_serial_callback(self, msg: str):
    #     """
    #     msg venant du cadran: ex 'POWER:1' ou 'DUTY:45'
    #     -> VENT:<fan>:POWER:1  ou VENT:<fan>:DUTY:45
    #     """
    #     fan = self.vent_selected.get()  # "left" | "center" | "right"
    #     # Update immédiat du RPM estimé dans le cadran (quand duty change)
    #     if msg.startswith("DUTY:"):
    #         try:
    #             duty = float(msg.split(":")[1])
    #             self.vent_ui.rpm_est_value = self._estimate_rpm(fan, duty) if self.vent_ui.power_on else 0.0
    #             self.vent_ui.update_display()
    #         except Exception:
    #             pass

    #     # POWER OFF -> rpm=0 immédiat
    #     if msg == "POWER:0":
    #         self.vent_ui.rpm_est_value = 0.0
    #         self.vent_ui.update_display()

    #     if self.serial_callback:
    #         self.serial_callback(f"VENT:{fan}:{msg}")
    def _vent_serial_callback(self, msg: str):
        """
        msg venant du cadran Ventilation: ex 'POWER:1' ou 'DUTY:45'
        => on convertit en 'VENT:<fan>:<action>:<value>'
        """
        fan = self.vent_selected.get()

        try:
            action, value = msg.split(":", 1)   # "POWER","1" ou "DUTY","45"
        except ValueError:
            return

        # Update immédiat du RPM estimé dans le cadran (quand duty change)
        if msg.startswith("DUTY:"):
            try:
                duty = float(msg.split(":")[1])
                self.vent_ui.rpm_est_value = self._estimate_rpm(fan, duty) if self.vent_ui.power_on else 0.0
                self.vent_ui.update_display()
            except Exception:
                pass

        # POWER OFF -> rpm=0 immédiat
        if msg == "POWER:0":
            self.vent_ui.rpm_est_value = 0.0
            self.vent_ui.update_display()

        if self.serial_callback:
            self.serial_callback(f"VENT:{fan}:{action}:{value}")


    

