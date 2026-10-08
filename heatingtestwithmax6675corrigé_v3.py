import time
import spidev
from gpiozero import PWMOutputDevice  # Remplace pigpio
from simple_pid import PID
import tkinter as tk
from tkinter import ttk, scrolledtext
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
from Bib.PID_AutoTune_Control import PID_ATune
import os
 
# --- Valeurs PID par défaut ---
DEFAULT_PID = "1.567,0.006,12.123"  # Valeurs PID par défaut
pid_filename = "pid_params.txt"  # Nom du fichier pour stocker les valeurs PID
 
# Créer le fichier pid_params.txt s'il n'existe pas
if not os.path.exists(pid_filename):
    with open(pid_filename, "w") as f:
        f.write(DEFAULT_PID)
    print(f"✅ Fichier '{pid_filename}' créé avec les valeurs par défaut.")
 
# --- Configuration des broches GPIO ---
MOSFET_PIN = 6  # Broche GPIO pour le mosfet (PWM)
mosfet = PWMOutputDevice(MOSFET_PIN, frequency=100, initial_value=0)
 
# --- Configuration du MAX6675 via SPI (CE0 = GPIO8) ---
# Câblage:
#   SCK  -> GPIO11 (pin 23)
#   SO   -> GPIO9  (pin 21 / MISO)
#   CS   -> CE0 = GPIO8 (pin 24)
#   MOSI -> GPIO10 (pin 19) non utilisé par MAX6675
 
SPI_BUS = 0
SPI_DEVICE = 0  # 0 => CE0 (/dev/spidev0.0)
 
spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEVICE)
spi.max_speed_hz = 1000000  # 1 MHz
spi.mode = 0                # SPI mode 0 (CPOL=0, CPHA=0)
 
# --- Paramètres PID ---
setpoint = 100.0  # Consigne en °C
current_temp = 25.0  # Température actuelle en °C
output_pwm = 0  # Sortie PWM (0-100)
autotune_mode = False  # Mode autotune
chauffage_active = False  # Chauffage activé
autotune_start_time = None  # Horodatage de lancement de l'autotune (pour calculer la durée)
 
# --- Initialisation du PID ---
# Lire les valeurs PID depuis le fichier
with open(pid_filename, "r") as f:
    pid_values = f.read().strip().split(",")
    kp, ki, kd = float(pid_values[0]), float(pid_values[1]), float(pid_values[2])
 
pid = PID(kp, ki, kd, setpoint=setpoint)
pid.output_limits = (0, 100)  # Limite la sortie entre 0% et 100%
pid.sample_time = 1.0
#pid.set_auto_mode(True, last_output=output_pwm)  # Démarrer avec la dernière sortie PWM
pid.set_auto_mode(False, last_output=0)
 
def autotune_output_writer(x):
    global output_pwm
    output_pwm = x
 
# --- Initialisation de l'autotune ---
pid_atune = PID_ATune(lambda: current_temp, autotune_output_writer)
 
# --- Lecture MAX6675 via spidev ---
def max6675_read_celsius():
    """
    MAX6675 retourne 16 bits.
    - D2 = 1 => thermocouple ouvert
    - D15..D3 => température * 4 (pas de 0.25°C)
    """
    data = spi.xfer2([0x00, 0x00])  # lire 16 bits
    value = (data[0] << 8) | data[1]
 
    # Thermocouple open
    if value & 0x0004:
        raise RuntimeError("Thermocouple ouvert/débranché (MAX6675 D2=1)")
 
    temp_c = ((value >> 3) & 0x1FFF) * 0.25
    return temp_c
 
# --- Fonction pour lire la température via MAX6675 ---
def read_temperature():
    try:
        temp = max6675_read_celsius()
        return temp
    except Exception as e:
        append_flux(f"❌ Erreur lecture température (MAX6675/spidev): {e}")
        #return 25.0
        return None
 
# --- Fonction pour appliquer le PWM au mosfet ---
def set_pwm(value):
    """Applique une valeur PWM entre 0 et 100%"""
    try:
        # Convertir 0-100% en 0.0-1.0 et limiter
        pwm_value = max(0, min(1, value / 100.0))
        mosfet.value = pwm_value
    except Exception as e:
        append_flux(f"❌ Erreur PWM: {e}")
 
# --- Fonction utilitaire pour formater une durée en secondes ---
def format_duration(seconds):
    """Formate une durée en secondes -> '12.3s' ou '2min 05.3s'"""
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes}min {secs:04.1f}s"
    return f"{secs:.1f}s"
 
# --- Fonction pour traiter les commandes ---
def process_command(command):
    global setpoint, autotune_mode, chauffage_active, pid, output_pwm, autotune_start_time
 
    if command == "AUTOTUNE":
        autotune_mode = True
        chauffage_active = True
        output_pwm = 0
        pid.auto_mode = False
        pid_atune.SetControlType(1)  # Mode PID
        pid_atune.SetOutputStep(50)  # Étape pour provoquer les oscillations
        pid_atune.SetNoiseBand(0.5)  # Bande de bruit en °C
        pid_atune.SetLookbackSec(20)  # Durée d'observation en secondes
        autotune_start_time = datetime.now()
        append_flux(f"🔄 Lancement de l'autotune PID... (début: {autotune_start_time.strftime('%H:%M:%S')}, T={current_temp:.1f}°C)")
    elif command.startswith("SETPOINT:"):
        setpoint = float(command.split(":")[1])
        pid.setpoint = setpoint
        append_flux(f"🎯 Nouvelle consigne : {setpoint} °C")
    elif command.startswith("SETPID:"):
        params = command.split(":")[1].split(",")
        kp, ki, kd = float(params[0]), float(params[1]), float(params[2])
        pid.tunings = (kp, ki, kd)
        append_flux(f"🔧 Paramètres PID mis à jour : Kp={kp}, Ki={ki}, Kd={kd}")
    elif command == "DEMARRER":
        chauffage_active = True
        pid.auto_mode = True
        append_flux("🔥 Chauffage ACTIVÉ !")
    elif command == "STOP":
        if autotune_mode and autotune_start_time is not None:
            duree = (datetime.now() - autotune_start_time).total_seconds()
            append_flux(f"⏹️ Autotune interrompu manuellement après {format_duration(duree)}")
        autotune_mode = False
        chauffage_active = False
        pid.auto_mode = False
        output_pwm = 0
        autotune_start_time = None
        set_pwm(0)
        append_flux("🛑 Chauffage ARRÊTÉ !")
 
# --- Fonction pour appliquer les paramètres PID depuis le fichier ---
def appliquer_pid_depuis_fichier():
    try:
        with open(pid_filename, "r") as f:
            content = f.read().strip()  # Format attendu: "Kp,Ki,Kd"
        process_command(f"SETPID:{content}")
        append_flux(f"🔧 Paramètres PID appliqués depuis le fichier : {content}")
    except Exception as e:
        append_flux(f"❌ Erreur lors de la lecture du fichier {pid_filename}: {e}")
 
# --- Interface Tkinter ---
root = tk.Tk()
root.title("Chauffage avec option PID Autotune")
 
# --- Zone de flux série (ScrolledText) ---
# flux_text = scrolledtext.ScrolledText(root, wrap=tk.WORD)
# flux_text.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)
flux_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=8)
flux_text.pack(side=tk.BOTTOM, fill=tk.X, expand=False, padx=5, pady=5)
flux_text.config(state='disabled')
 
# --- Fonction d'ajout de texte dans la zone flux ---
def append_flux(text):
    timestamp = datetime.now().strftime("%H:%M:%S")
    text = f"[{timestamp}] {text}"
    flux_text.config(state='normal')
    current = flux_text.get("1.0", tk.END).strip()
    if current:
        new_text = current + "\n" + text
    else:
        new_text = text
    lines = new_text.split("\n")
    if len(lines) > 50:
        lines = lines[-50:]
    flux_text.delete("1.0", tk.END)
    flux_text.insert(tk.END, "\n".join(lines))
    flux_text.see(tk.END)
    flux_text.config(state='disabled')
 
# --- Label d'information principale (Température, Consigne, PWM) ---
info_label = ttk.Label(root, text="Température: 0.0 °C | Consigne: 100.0 °C | PWM: 0.0")
info_label.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
 
# --- Menu ---
menubar = tk.Menu(root)
 
# Menu Réglage (pour PID et autotune)
reglage_menu = tk.Menu(menubar, tearoff=0)
reglage_menu.add_command(label="PID Autotune", command=lambda: process_command("AUTOTUNE"))
reglage_menu.add_command(label="Appliquer PID depuis fichier", command=appliquer_pid_depuis_fichier)
menubar.add_cascade(label="Réglage", menu=reglage_menu)
 
# Menu Affichage (pour afficher/masquer la zone flux série)
affichage_menu = tk.Menu(menubar, tearoff=0)
show_flux = tk.BooleanVar(value=True)
def toggle_flux():
    global show_flux
    if show_flux.get():
        flux_text.pack_forget()
        show_flux.set(False)
    else:
        #flux_text.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=5, pady=5)
        flux_text.pack(side=tk.BOTTOM, fill=tk.X, expand=False, padx=5, pady=5)
        show_flux.set(True)
affichage_menu.add_command(label="Afficher/Masquer flux série", command=toggle_flux)
menubar.add_cascade(label="Affichage", menu=affichage_menu)
 
root.config(menu=menubar)
 
# --- Cadre pour le contrôle de la consigne et commandes ---
control_frame = ttk.Frame(root)
control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
 
def decrease_setpoint():
    try:
        current_val = float(setpoint_entry.get())
    except ValueError:
        current_val = 100.0
    new_val = current_val - 1.0
    setpoint_entry.delete(0, tk.END)
    setpoint_entry.insert(0, f"{new_val:.1f}")
    process_command(f"SETPOINT:{new_val:.1f}")
 
def increase_setpoint():
    try:
        current_val = float(setpoint_entry.get())
    except ValueError:
        current_val = 100.0
    new_val = current_val + 1.0
    setpoint_entry.delete(0, tk.END)
    setpoint_entry.insert(0, f"{new_val:.1f}")
    process_command(f"SETPOINT:{new_val:.1f}")
 
minus_button = ttk.Button(control_frame, text="–", command=decrease_setpoint)
minus_button.pack(side=tk.LEFT, padx=5)
 
setpoint_var = tk.StringVar(value="100.0")
setpoint_entry = ttk.Entry(control_frame, width=6, textvariable=setpoint_var)
setpoint_entry.pack(side=tk.LEFT, padx=5)
setpoint_entry.bind("<Return>", lambda event: process_command(f"SETPOINT:{setpoint_entry.get()}"))
 
plus_button = ttk.Button(control_frame, text="+", command=increase_setpoint)
plus_button.pack(side=tk.LEFT, padx=5)
 
consigne_label = ttk.Label(control_frame, text="Consigne: 100.0 °C")
consigne_label.pack(side=tk.LEFT, padx=5)
 
def send_start():
    process_command("DEMARRER")
 
def send_stop():
    process_command("STOP")
 
start_button = ttk.Button(control_frame, text="DÉMARRER", command=send_start)
start_button.pack(side=tk.LEFT, padx=5)
stop_button = ttk.Button(control_frame, text="STOP", command=send_stop)
stop_button.pack(side=tk.LEFT, padx=5)
 
# --- Graphique Matplotlib avec double axe Y ---
fig, ax_temp = plt.subplots()
ax_pwm = ax_temp.twinx()
 
line_temp, = ax_temp.plot([], [], 'r-', label="Température (°C)")
line_setpoint, = ax_temp.plot([], [], 'g--', label="Consigne (°C)")
line_pwm, = ax_pwm.plot([], [], 'b-', label="PWM")
 
ax_temp.set_xlabel("Temps (s)")
ax_temp.set_ylabel("Température (°C)", color='r')
ax_pwm.set_ylabel("PWM", color='b')
 
ax_temp.legend(loc='upper left')
ax_pwm.legend(loc='upper right')
 
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
 
# --- Boucle principale ---
timestamps = []
temperatures = []
pwm_values = []
start_time = datetime.now()
 
def update(frame):
    global current_temp, output_pwm, autotune_mode, chauffage_active, setpoint, timestamps, temperatures, pwm_values, autotune_start_time
 
    # Lecture de la température
    current_temp = read_temperature()
    #si la lecture de temperature échoue
    if current_temp is None:
        autotune_mode = False
        chauffage_active = False
        pid.auto_mode = False
        output_pwm = 0
        set_pwm(0)
 
        info_text = f"Température: ERREUR | Consigne: {setpoint:.1f} °C | PWM: 0.0%"
        info_label.config(text=info_text)
 
        return line_temp, line_setpoint, line_pwm
 
    # Traitement de l'autotune
    if autotune_mode:
        tune_status = pid_atune.Runtime()
        output_pwm = max(0, min(100, output_pwm))
        # if output_pwm < 0:
        #     output_pwm = 0
 
        set_pwm(output_pwm)
 
        #append_flux(f"🔄 Autotune en cours... Température: {current_temp:.1f} °C | PWM: {output_pwm:.1f}%")
 
        if tune_status != 0:
            kp_classic = pid_atune.GetKp()
            ki_classic = pid_atune.GetKi()
            kd_classic = pid_atune.GetKd()
 
            # --- Reconstruction du gain ultime Ku et de la période ultime Pu ---
            # PID_ATune renvoie des gains calculés avec la règle "PID classique"
            # de Ziegler-Nichols : Kp = 0.6*Ku ; Ti = Kp/Ki = Pu/2 ; Td = Kd/Kp = Pu/8
            # On peut donc retrouver Ku et Pu à partir de ces 3 valeurs.
            Ku = kp_classic / 0.6 if kp_classic else 0
            Pu_from_ki = 2 * (kp_classic / ki_classic) if ki_classic else 0
            Pu_from_kd = 8 * (kd_classic / kp_classic) if kp_classic else 0
            if Pu_from_ki and Pu_from_kd:
                Pu = (Pu_from_ki + Pu_from_kd) / 2
            else:
                Pu = max(Pu_from_ki, Pu_from_kd)
 
            # --- Réglage Tyreus-Luyben à partir de Ku/Pu (au lieu du ZN classique) ---
            # La règle "classic PID" de Ziegler-Nichols vise une décroissance
            # d'amplitude 1/4 : c'est volontairement oscillatoire, et pour un
            # procédé lent/à forte inertie comme une cartouche chauffante, ça se
            # traduit par un cycle limite qui ne s'amortit jamais autour de la
            # consigne. Tyreus-Luyben utilise les mêmes Ku/Pu mesurés par le test
            # à relais mais avec des coefficients moins agressifs (Kp plus faible,
            # action intégrale beaucoup plus lente), ce qui stabilise la
            # température au lieu de la faire osciller en continu.
            kp = Ku / 2.2
            Ti_tl = 2.2 * Pu
            Td_tl = Pu / 6.3
            ki = kp / Ti_tl if Ti_tl else 0
            kd = kp * Td_tl
 
            pid.tunings = (kp, ki, kd)
            pid.auto_mode = True
            autotune_mode = False
 
            fin_time = datetime.now()
            if autotune_start_time is not None:
                duree_str = format_duration((fin_time - autotune_start_time).total_seconds())
            else:
                duree_str = "inconnue"
 
            append_flux(f"✅ Autotune terminé ! (fin: {fin_time.strftime('%H:%M:%S')}, durée: {duree_str}) Ku≈{Ku:.2f}, Pu≈{Pu:.1f}s")
            append_flux(f"   Ziegler-Nichols classique (référence, non appliqué) : Kp={kp_classic:.2f}, Ki={ki_classic:.3f}, Kd={kd_classic:.2f}")
            append_flux(f"   Tyreus-Luyben (appliqué) : Kp={kp:.2f}, Ki={ki:.3f}, Kd={kd:.2f}")
            autotune_start_time = None
 
            with open(pid_filename, "w") as f:
                f.write(f"{kp},{ki},{kd}")
            append_flux(f"💾 Nouvelles valeurs PID (Tyreus-Luyben) sauvegardées dans {pid_filename}")
    #changement ici 07/09/2026
    elif chauffage_active:
        output_pwm = pid(current_temp)
        output_pwm = max(0, min(100, output_pwm))
        set_pwm(output_pwm)
 
    else:
        output_pwm = 0
        set_pwm(0)
    # Affichage des informations
    timestamps.append((datetime.now() - start_time).total_seconds())
    temperatures.append(current_temp)
    pwm_values.append(output_pwm)
 
    # Mise à jour des courbes
    line_temp.set_data(timestamps, temperatures)
    line_setpoint.set_data([timestamps[0], timestamps[-1]], [setpoint, setpoint])  # Ligne de consigne
    line_pwm.set_data(timestamps, pwm_values)
 
    # Ajustement des limites du graphique
    ax_temp.set_xlim(max(0, timestamps[-1] - 250), timestamps[-1] + 5)
    ax_temp.set_ylim(min(min(temperatures), setpoint) - 5, max(max(temperatures), setpoint) + 5)
    ax_pwm.set_ylim(0, 100)
    # Affichage des informations dans le label
    info_text = f"Température: {current_temp:.1f} °C | Consigne: {setpoint:.1f} °C | PWM: {output_pwm:.1f}%"
    info_label.config(text=info_text)
 
    return line_temp, line_setpoint, line_pwm
 
ani = animation.FuncAnimation(fig, update, interval=500, blit=False)
#ani = animation.FuncAnimation(fig, update, interval=1000, blit=False)
 
# --- Fonction de fermeture ---
def on_closing():
    print("🚪 Fermeture de l'application...")
    mosfet.value = 0  # Éteindre le MOSFET
    mosfet.close()  # Libérer la ressource GPIO
    try:
        spi.close()
    except:
        pass
    root.quit()
 
root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()