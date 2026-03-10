import tkinter as tk
from tkinter import scrolledtext, filedialog
import csv
import time
import re

class SerialLogPage(tk.Frame):
    """
    Affiche en temps réel les messages du port série et permet d'exporter les données dans un CSV.
    Les étiquettes "Température:", "Consigne:" et "PWM:" sont colorées (bleu, rouge, vert),
    le reste est en noir. On limite l'affichage à 200 lignes.
    """
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bg", "white")
        super().__init__(parent, **kwargs)

        # Configurer la grille avec deux lignes : 
        # - row 0 pour le ScrolledText qui prendra tout l'espace restant
        # - row 1 pour le bouton d'export
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.text_widget = scrolledtext.ScrolledText(
            self, state="normal", wrap="word",
            font=("Helvetica", 8), bg="white", fg="black"
        )
        self.text_widget.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.export_btn = tk.Button(
            self,
            text="💾 Export CSV",
            command=self.export_to_csv,
            font=("Segoe UI Emoji", 12),
            bg="white", fg="black", relief="flat",
            activebackground="white", activeforeground="black"
        )
        # Le bouton s'étend horizontalement, et sa hauteur reste fixée :
        self.export_btn.grid(row=1, column=0, sticky="ew", pady=(0,10))

        # Configuration des tags pour la coloration
        self.text_widget.tag_config("default", foreground="black")
        self.text_widget.tag_config("temp_label", foreground="blue")
        self.text_widget.tag_config("cons_label", foreground="red")
        self.text_widget.tag_config("pwm_label", foreground="green")
        self.text_widget.tag_config("rpm_extruder_label", foreground="purple") #nouveau
        
        
        self.data_log = []  # Stocke les données pour l'export CSV
        self.logging_enabled = True
        self.max_lines = 200

    def append_message(self, message):
        message = message.rstrip("\n")
        if not message.strip():
            return
        message = message + "\n"
        self.text_widget.configure(state="normal")
        for line in message.splitlines():
            if not line.strip():
                continue
            #AJOUT DE "RPM:" DANS LA REGEX
            pattern = r"(Température:|Consigne:|PWM:|RPM EXTR:|RPM LF:|RPM CF:|RPM RF:)"
            start_idx = 0
            for match in re.finditer(pattern, line):
                self.text_widget.insert(tk.END, line[start_idx:match.start()], "default")
                label = match.group(1)
                # Attribution des couleurs
                if label == "Température:":
                    self.text_widget.insert(tk.END, label, "temp_label")
                elif label == "Consigne:":
                    self.text_widget.insert(tk.END, label, "cons_label")
                elif label == "PWM:":
                    self.text_widget.insert(tk.END, label, "pwm_label")
                elif label == "RPM EXTR:": #nouveau
                    self.text_widget.insert(tk.END, label, "rpm_extruder_label")
                elif label in ["RPM LF:", "RPM CF:", "RPM RF:"]:
                    # Créer un nouveau tag pour les ventilateurs si vous voulez une couleur spécifique
                    # Par défaut, on utilise "default" ou on peut créer un tag "vent_label"
                    self.text_widget.insert(tk.END, label, "default")
                
                start_idx = match.end()
            self.text_widget.insert(tk.END, line[start_idx:], "default")
            self.text_widget.insert(tk.END, "\n", "default")
        content = self.text_widget.get("1.0", tk.END)
        lines = content.splitlines()
        if len(lines) > self.max_lines:
            new_content = "\n".join(lines[-self.max_lines:])
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert(tk.END, new_content + "\n", "default")
        self.text_widget.configure(state="disabled")
        self.text_widget.see(tk.END)
        #EXTRACTION DES DONNÉES POUR CSV (avec RPM)
        val_pattern = r"Température:\s*([\d\.]+).*Consigne:\s*([\d\.]+).*PWM:\s*([\d\.]+).*RPM EXTR:\s*([\d\.]+).*RPM LF:\s*([\d\.]+).*RPM CF:\s*([\d\.]+).*RPM RF:\s*([\d\.]+)"
        match_val = re.search(val_pattern, message)
        if match_val:
            try:
                temp = float(match_val.group(1))
                cons = float(match_val.group(2))
                pwm = float(match_val.group(3))
                rpm_ext = float(match_val.group(4))
                rpm_g = float(match_val.group(5))
                rpm_c = float(match_val.group(6))
                rpm_d = float(match_val.group(7))
                
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                self.data_log.append((current_time, temp, cons, pwm, rpm_ext, rpm_g, rpm_c, rpm_d))
            except Exception as e:
                print("Erreur lors de l'extraction des données:", e)
        else:
            # ESSAYER UN PATTERN ALTERNATIF (au cas où)
            alt_pattern = r"Température:\s*([\d\.]+).*Consigne:\s*([\d\.]+).*PWM:\s*([\d\.]+)"
            match_alt = re.search(alt_pattern, message)
            if match_alt:
                try:
                    temp = float(match_alt.group(1))
                    cons = float(match_alt.group(2))
                    pwm = float(match_alt.group(3))
                    
                    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    self.data_log.append((current_time, temp, cons, pwm, 0.0, 0.0, 0.0, 0.0))
                except Exception as e:
                    print("Erreur lors de l'extraction des données (pattern alternatif):", e)

    def export_to_csv(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            title="Sauvegarder les données CSV"
        )
        if file_path:
            try:
                with open(file_path, mode="w", newline="") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(["Temps", "Température (°C)", "Consigne (°C)", "PWM (%)", "RPM EXTR (tr/min)", "RPM LF (tr/min)", "RPM CF (tr/min)", "RPM RF (tr/min)"])
                    for row in self.data_log:
                        writer.writerow(row)
                print("Export CSV réussi:", file_path)
            except Exception as e:
                print("Erreur lors de l'export CSV:", e)
