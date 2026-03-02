import json
import time
import re
import tkinter as tk
from PIL import Image, ImageTk
import tkinter.messagebox as msg
import multiprocessing

from gpiozero.pins.lgpio import LGPIOFactory
from gpiozero import Device
Device.pin_factory = LGPIOFactory()

# Import des pages modifiées qui intègrent le nom du cadran à l'extérieur
from pages.parameter_page_ventilation import ParameterPage
from pages.curve_temp_ui import CurveTempUI
from pages.serial_log_page import SerialLogPage
from pages.config_window import ConfigWindow

# Import des modules associés à chaque cadran
from modules.systemchauffageMAX6675 import SystemeChauffageMAX6675  
from modules.motor_extrusion_drv8825_class_multiprocessing import MoteurExtrusion
from modules.motor_extrusion_drv8825_class_multiprocessing import run_motor_process  # à ajouter en haut, à côté de MoteurExtrusion
from modules.systeme_ventilation import SystemeVentilation

class PageManager(tk.Frame):
    def __init__(self, parent, cmd_queue_moteur=None, status_queue_moteur=None, **kwargs):
        # On enlève cmd_queue_moteur et status_queue_moteur de kwargs
        super().__init__(parent, **kwargs)

        # --- Queues pour le moteur (communication inter-processus) ---
        self.cmd_queue_moteur = cmd_queue_moteur
        self.status_queue_moteur = status_queue_moteur

        self.last_motor_status = {
            'enabled': False,
            'target_rpm': 0.0,
            'current_rpm': 0.0,
            'direction': 'forward',
            'temp_value': None,
            'temp_target': None,
        }
        #####
        self.last_measured_rpm = 0.0
        #####
        self.config_data = self.load_config()

        # Modules
        self.chauffage = SystemeChauffageMAX6675()
        self.ventilation = SystemeVentilation(pin_right=23, pin_left=25, pin_center=26)


        # Barre supérieure
        self.top_bar = tk.Frame(self, bg="#FFFFFF", height=60)
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)
        self.left_frame = tk.Frame(self.top_bar, bg="#FFFFFF")
        self.left_frame.pack(side="left", padx=10)
        self.center_frame = tk.Frame(self.top_bar, bg="#FFFFFF")
        self.center_frame.pack(side="left", expand=True)
        self.right_frame = tk.Frame(self.top_bar, bg="#FFFFFF")
        self.right_frame.pack(side="right", padx=10)
        
        self.home_btn = tk.Button(self.left_frame, text="🏠", font=("Helvetica", 20, "bold"),
                                  fg="#000000", bg="#FFFFFF", relief="flat",
                                  command=lambda: self._show_page(0))
        self.home_btn.pack(side="left", padx=(0,5))
        self.flame_btn = tk.Button(self.left_frame, text="🔥", font=("Helvetica", 20, "bold"),
                                   fg="#000000", bg="#FFFFFF", relief="flat",
                                   command=lambda: self._show_page(1))
        self.flame_btn.pack(side="left")
        
        try:
            gear_img = Image.open("gear_icon.png").resize((40,40))
            self.gear_icon = ImageTk.PhotoImage(gear_img)
        except Exception:
            self.gear_icon = None
        try:
            serial_img = Image.open("serial_icon.png").resize((40,40))
            self.serial_icon = ImageTk.PhotoImage(serial_img)
        except Exception:
            self.serial_icon = None
        self.btn_gear = tk.Button(self.right_frame, image=self.gear_icon,
                                  text="⚙️" if self.gear_icon is None else "",
                                  command=self.open_config_window,
                                  bg="#FFFFFF", relief="flat", cursor="hand2", font=("Helvetica",20))
        self.btn_serial = tk.Button(self.right_frame, image=self.serial_icon,
                                    text="🔌" if self.serial_icon is None else "",
                                    command=self.show_serial_log,
                                    bg="#FFFFFF", relief="flat", cursor="hand2", font=("Helvetica",20))
        self.btn_gear.pack(side="right", padx=5)
        self.btn_serial.pack(side="right", padx=5)
        
        self.content_frame = tk.Frame(self, bg="#FFFFFF")
        self.content_frame.pack(side="top", fill="both", expand=True)
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)
        
        # Création des pages (les modules ParameterPage, CurveTempUI et SerialLogPage doivent être adaptés)
        page0 = ParameterPage(self.content_frame, config_data=self.config_data,
                              serial_callback=self.handle_ui_action, bg="#FFFFFF")
        page0.update_config(self.config_data)

        page1 = CurveTempUI(self.content_frame, bg="#EEEEEE")
        page2 = SerialLogPage(self.content_frame, bg="#EEEEEE")
        self.pages = [page0, page1, page2]
        for p in self.pages:
            p.grid(row=0, column=0, sticky="nsew")

        self.current_page = 0
        self._show_page(0)

        # # 🔗 Connecter le chauffage à la page Serial Log
        # try:
        # # Si SystemeChauffage a un attribut ou un paramètre serial_callback
        #     self.chauffage.serial_callback = page2.append_message
        # except Exception as e:
        #     print("⚠️ Impossible d'attacher serial_callback au chauffage :", e)

        initial_setpoint = self.pages[0].temp_ui.target_value
        self.handle_ui_action(f"SETPOINT:{initial_setpoint}")
        pid_params = self.config_data["Température"]
        self.handle_ui_action(f"SETPID:{pid_params['Kp']},{pid_params['Ki']},{pid_params['Kd']}")
    
        self.after(1000, self.update_chauffage)
    
    def _show_page(self, index):
        for p in self.pages:
            p.grid_remove()
        self.pages[index].grid(row=0, column=0, sticky="nsew")
        self.current_page = index
        if index == 0:  # Page paramètres
            self.right_frame.pack(side="right", padx=10)
        else:  # Autres pages
            self.right_frame.pack_forget()
        self.update_idletasks()  # Force la mise à jour de l'interface

    def show_serial_log(self):
        self._show_page(2)
    
    def open_config_window(self):
        from pages.config_window import ConfigWindow
        ConfigWindow(self, self.config_data, self.update_config, serial_callback=self.handle_ui_action)
    
    def update_config(self, new_config):
        merge_config(self.config_data, new_config)
        if hasattr(self.pages[0], "update_config"):
            self.pages[0].update_config(self.config_data)
        pid_params = self.config_data["Température"]
        self.handle_ui_action(f"SETPID:{pid_params['Kp']},{pid_params['Ki']},{pid_params['Kd']}")
    
    def handle_ui_action(self, action_str): #donc cette méthode va coopler le back avec le front ??
        print(f"[Action reçue] → {action_str}")

        try:
            if  action_str in ["AUTOTUNE", "DEMARRER", "STOP"] or \
                action_str.startswith("SETPOINT:") or \
                action_str.startswith("SETPID:"):
                self.chauffage.process_command(action_str)   

            elif action_str.startswith("EXTRUDER:"):
                # On n'appelle plus la classe moteur directement : on envoie la commande au process moteur
                if self.cmd_queue_moteur is not None:
                    self.cmd_queue_moteur.put(action_str)
                else:
                    print("⚠️ cmd_queue_moteur est None, impossible d'envoyer la commande moteur.")

            elif action_str.startswith("VENT:"):
                self.ventilation.process_command(action_str)

            else:
                print("Commande inconnue ou non gérée.")
        except Exception as e:
            print(f"Erreur lors du traitement de la commande : {e}")

    def update_chauffage(self):
        try:
            # --- Partie chauffage inchangée ---
            data = self.chauffage.update()

            temperature = data['temperature']
            setpoint = data['setpoint']
            pwm = data['pwm']

            # 🔴 Affiche température réelle dans la jauge
            self.pages[0].temp_ui.current_value = temperature
            self.pages[0].temp_ui.pwm_value = pwm
            self.pages[0].temp_ui.update_display()

            # --- Récupération de l'état moteur depuis la queue ---
            if self.status_queue_moteur is not None:
                try:
                    # On lit tous les messages disponibles pour garder le plus récent
                    import queue
                    while True:
                        msg = self.status_queue_moteur.get_nowait()
                        self.last_motor_status = msg
                except queue.Empty:
                    pass

            status_moteur = self.last_motor_status
            
            # 🔄 Mise à jour de l'interface moteur avec la vitesse actuelle
            # current_rpm = status_moteur.get('current_rpm', 0.0)
            # self.pages[0].motor_ui.current_value = current_rpm
            measured_rpm = status_moteur.get('measured_rpm', 0.0)
            self.pages[0].motor_ui.current_value = measured_rpm

            # 🔄 Synchronisation température pour l'affichage "Température Limite"
            self.pages[0].motor_ui.temp_value = temperature
            self.pages[0].motor_ui.temp_target = setpoint
            self.pages[0].motor_ui.control_enabled = True   

            # 📊 Récupération de l'état des ventilateurs
            vent_status = self.ventilation.get_status()

            # 📊 LOG SERIAL : Ajouter RPM mesuré
            if self.pages[2]:  # Vérifier que SerialLogPage existe
                # Format: "Température: XX.X°C | Consigne: XX.X°C | PWM: XX.X% | RPM EXTRUDER: XX.Xtr/min"
                log_message = f"Température: {temperature:6.1f}°C | Consigne: {setpoint:6.1f}°C | PWM: {pwm:5.1f}% | RPM EXTR: {measured_rpm:6.1f}tr/min | RPM LF: {vent_status['left']['rpm_est']:6.1f}tr/min | RPM CF: {vent_status['center']['rpm_est']:6.1f}tr/min | RPM RF: {vent_status['right']['rpm_est']:6.1f}tr/min"
                self.pages[2].append_message(log_message)

           # 📊 Envoie les données à la courbe SEULEMENT si le chauffage est actif
            status_chauffage = self.chauffage.get_status()
            if status_chauffage.get("active", False):
                self.pages[1].add_data(temperature, setpoint, pwm)

            # Rafraîchir les cadrans moteur et température
            self.pages[0].motor_ui.update_display()
           

        except Exception as e:
            print("Erreur update_chauffage:", e)

        # Rappel dans 1 seconde
        self.after(1000, self.update_chauffage)


    def load_config(self):
        path = "parameters.json"
        default_config = {
            "Température": {"min": 30.0, "max": 300.0, "step": 1.0, "Kp": 2.0, "Ki": 0.5, "Kd": 1.0, "target_value": 30.0},
            "Moteur": {"min": 10.0, "max": 250.0, "step": 10.0, "target_value": 100.0},
            "Refroidissement": {"min": 0.0, "max": 100.0, "step": 5.0},
            "Options": {"demarrage_moteur_faible_temperature_controle": 1}
        }
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, default in default_config.items():
                if key not in data:
                    data[key] = default
                elif isinstance(default, dict):
                    for subkey, subdefault in default.items():
                        if subkey not in data[key]:
                            data[key][subkey] = subdefault
            return data
        except Exception as e:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            return default_config

def merge_config(original, new):
    for key, value in new.items():
        if key in original and isinstance(original[key], dict) and isinstance(value, dict):
            merge_config(original[key], value)
        else:
            original[key] = value
            
# def on_closing(root, manager=None, motor_process=None):
#     """
#     Callback appelé quand on ferme la fenêtre.
#     - Arrête proprement le chauffage (si présent)
#     - Termine le process moteur (si présent)
#     - Ferme la fenêtre Tkinter
#     """
#     print("Fermeture de l'application...")

#     # 1) Arrêt du chauffage
#     try:
#         if manager is not None and hasattr(manager, "chauffage"):
#             manager.chauffage.close()
#     except Exception as e:
#         print(f"Erreur lors de l'arrêt du chauffage : {e}")

#     # 2) Arrêt du processus moteur
#     try:
#         if motor_process is not None and motor_process.is_alive():
#             print("Arrêt du process moteur...")
#             motor_process.terminate()
#             motor_process.join(timeout=1.0)
#     except Exception as e:
#         print(f"Erreur lors de l'arrêt du moteur (processus) : {e}")

#     # 3) Arrêt de ventilation - CORRECTION : utiliser 'manager' au lieu de 'self'
#     try:
#         if manager is not None and hasattr(manager, "ventilation"):
#             manager.ventilation.close()
#             print("Ventilation arrêtée avec succès")
#     except Exception as e:
#         print(f"⚠️ ventilation.close() failed: {e}")

#     # 4) Fermeture de la fenêtre Tkinter
#     root.destroy()
def on_closing(root, manager=None, motor_process=None):
    """
    Callback appelé quand on ferme la fenêtre.
    """
    print("Fermeture de l'application...")

    # 1) D'abord la ventilation - ARRÊT DIRECT
    if manager is not None and hasattr(manager, "ventilation"):
        try:
            print("🔄 Arrêt ventilation...")
            # Appeler emergency_stop qui utilise les PWM existants
            manager.ventilation.emergency_stop()
            # Puis close pour nettoyer
            manager.ventilation.close()
            print("✅ Ventilation arrêtée")
        except Exception as e:
            print(f"⚠️ Erreur ventilation: {e}")
    
    # 2) Ensuite le chauffage
    if manager is not None and hasattr(manager, "chauffage"):
        try:
            manager.chauffage.close()
            print("✅ Chauffage arrêté")
        except Exception as e:
            print(f"⚠️ Erreur chauffage: {e}")

    # 3) Processus moteur
    if motor_process is not None and motor_process.is_alive():
        try:
            print("Arrêt du process moteur...")
            motor_process.terminate()
            motor_process.join(timeout=2.0)
            print("✅ Moteur arrêté")
        except Exception as e:
            print(f"⚠️ Erreur moteur: {e}")

    # 4) Petit délai
    time.sleep(0.5)

    # 5) Fermeture de la fenêtre
    try:
        root.destroy()
        print("✅ Interface fermée")
    except Exception as e:
        print(f"⚠️ Erreur fermeture interface: {e}")


def main():

    # Création des queues pour la communication GUI ↔ moteur
    cmd_queue_moteur = multiprocessing.Queue()
    status_queue_moteur = multiprocessing.Queue()

    # Création du processus moteur
    motor_process = multiprocessing.Process(
        target=run_motor_process,
        args=(cmd_queue_moteur, status_queue_moteur),
        daemon=True   # le process se ferme avec le process principal
    )
    motor_process.start()

     # --- GUI / Tkinter ---
    root = tk.Tk()
    root.title("CFR-X3D")
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{screen_width}x{screen_height}")
    
    # On ajuste éventuellement le scaling
    root.tk.call('tk', 'scaling', 1.25)
    root.resizable(True, True)

    manager = PageManager(root, bg="#FFFFFF", cmd_queue_moteur=cmd_queue_moteur, status_queue_moteur=status_queue_moteur)
    manager.pack(fill=tk.BOTH, expand=True)
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, manager, motor_process))
    root.mainloop()


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    main()
