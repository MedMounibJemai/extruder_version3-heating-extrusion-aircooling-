import tkinter as tk
import json
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk

# Une version simplifiée d'une frame défilable avec uniquement une scrollbar verticale.
class ScrollableFrame(tk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.v_scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)
        
        # Ce frame contiendra tout le contenu de la fenêtre de configuration.
        self.scrollable_frame = tk.Frame(self.canvas, bg="white")
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.v_scrollbar.pack(side="right", fill="y")

class ConfigWindow(tk.Toplevel):
    def __init__(self, parent, config_data, callback, serial_callback=None):
        super().__init__(parent)
        self.title("Configuration des paramètres")
        self.config_data = config_data
        self.callback = callback
        self.serial_callback = serial_callback

        # Pour éviter une largeur excessive et insuffisante hauteur, on choisit une géométrie initiale plus étroite et haute
        self.geometry("500x600")
        self.resizable(True, True)
        self.configure(bg="white")
        self.transient(parent)
        self.grab_set()
        self.focus_force()

        # Utiliser le ScrollableFrame pour activer le défilement vertical
        scroll_frame = ScrollableFrame(self)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        main_frame = scroll_frame.scrollable_frame

        self.entries = {}
        row = 0

        # Pour chaque paramètre, on affiche son nom et ses champs standards
        for param in self.config_data:
            label_param = tk.Label(main_frame, text=param, font=("Helvetica", 14, "bold"), bg="white")
            label_param.grid(row=row, column=0, columnspan=4, pady=5, sticky="w")
            row += 1

            for col, attr in enumerate(["min", "max", "step"]):
                label_attr = tk.Label(main_frame, text=f"{attr}:", font=("Helvetica", 12), bg="white")
                label_attr.grid(row=row, column=col*2, sticky="e", padx=(5,0), pady=2)
                entry = tk.Entry(main_frame, width=8, font=("Helvetica", 12), bg="white")
                entry.grid(row=row, column=col*2+1, sticky="w", padx=(0,5), pady=2)
                entry.insert(0, str(self.config_data[param].get(attr, "")))
                self.entries[(param, attr)] = entry

            # Si le paramètre est "Température", on ajoute les paramètres PID et le bouton Autotune
            if param == "Température":
                row += 1
                label_pid = tk.Label(main_frame, text="Paramètres PID:", font=("Helvetica", 14, "bold"), bg="white")
                label_pid.grid(row=row, column=0, columnspan=4, pady=5, sticky="w")
                row += 1
                for i, attr in enumerate(["Kp", "Ki", "Kd"]):
                    label_attr = tk.Label(main_frame, text=f"{attr}:", font=("Helvetica", 12), bg="white")
                    label_attr.grid(row=row, column=i*2, sticky="e", padx=(5,0), pady=2)
                    entry = tk.Entry(main_frame, width=8, font=("Helvetica", 12), bg="white")
                    entry.grid(row=row, column=i*2+1, sticky="w", padx=(0,5), pady=2)
                    default_val = self.config_data[param].get(attr, "")
                    if default_val == "":
                        if attr == "Kp":
                            default_val = 2.0
                        elif attr == "Ki":
                            default_val = 0.5
                        elif attr == "Kd":
                            default_val = 1.0
                    entry.insert(0, str(default_val))
                    self.entries[(param, attr)] = entry
                row += 1
                self.autotune_btn = self.create_autotune_button(main_frame)
                self.autotune_btn.grid(row=row, column=0, columnspan=4, pady=5)
            
            row += 1
            # Séparateur (ligne vide)
            tk.Label(main_frame, text="", bg="white").grid(row=row, column=0, columnspan=4)
            row += 1

        # Checkbox pour l'option de démarrage moteur à température contrôlée
        self.demarrage_var = tk.IntVar()
        options = self.config_data.setdefault("Options", {})
        self.demarrage_var.set(options.get("demarrage_moteur_faible_temperature_controle", 0))
        self.checkbox = tk.Checkbutton(main_frame,
                                       text="Activation du démarrage moteur sous température contrôlée",
                                       variable=self.demarrage_var, bg="white",
                                       font=("Helvetica", 10), command=self.checkbox_changed)
        self.checkbox.grid(row=row, column=0, columnspan=4, pady=5, sticky="w")
        
        row += 1
        self.save_btn = self.create_save_button(main_frame)
        self.save_btn.grid(row=row, column=0, columnspan=4, pady=10)

    def checkbox_changed(self):
        if self.demarrage_var.get() == 0:
            messagebox.showwarning("Attention", "Le moteur peut être endommagé si la température n'est pas adéquate.")

    def create_save_button(self, parent):
        try:
            save_img = Image.open("save_icon.png").resize((24,24))
            self.save_icon = ImageTk.PhotoImage(save_img)
            btn = tk.Button(parent, image=self.save_icon, text="", compound="left",
                            command=self.save_config, bg="white", font=("Helvetica", 10))
        except Exception:
            btn = tk.Button(parent, text="💾 Sauvegarder", command=self.save_config,
                            bg="white", font=("Helvetica", 10))
        return btn

    def create_autotune_button(self, parent):
        def do_autotune():
            if self.serial_callback:
                self.serial_callback("AUTOTUNE")
        try:
            wrench_img = Image.open("wrench_icon.png").resize((24,24))
            self.wrench_icon = ImageTk.PhotoImage(wrench_img)
            btn = tk.Button(parent, image=self.wrench_icon, text="", compound="left",
                            command=do_autotune, bg="white", font=("Helvetica", 10))
        except Exception:
            btn = tk.Button(parent, text="🔧 Lancer Autotune", command=do_autotune,
                            bg="white", font=("Helvetica", 10))
        return btn

    def save_config(self):
        for (param, attr) in self.entries:
            try:
                self.config_data[param][attr] = float(self.entries[(param, attr)].get())
            except ValueError:
                self.config_data[param][attr] = 0
        self.config_data.setdefault("Options", {})["demarrage_moteur_faible_temperature_controle"] = self.demarrage_var.get()
        with open("parameters.json", "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, indent=4)
        if self.callback:
            self.callback(self.config_data)
        self.destroy()
