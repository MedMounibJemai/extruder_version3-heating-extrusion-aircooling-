# modules/moteur_extrusion.py

import time
import threading
import queue
from Bib.HR8825 import HR8825

MotorDir = ['forward', 'backward']


class MoteurExtrusion:
    """
    Classe de haut niveau pour le contrôle du moteur d'extrusion.
    Version corrigée avec la même logique que test_stepper.py
    """

    def __init__(
        self,
        dir_pin,
        step_pin,
        enable_pin,
        mode_pins,
        motor_ui=None,  # <--- default = None
        steps_per_rev=200,
        microstep_mode='1/16step',
        max_rpm=75.0,
        default_rpm=10.0,
        control_enabled=True,
        ramp_rpm_per_sec=200.0
    ):
        self.motor_ui = motor_ui
        self.max_rpm = max_rpm
        self.target_rpm = default_rpm
        self.current_rpm = 0.0
        self.measured_rpm = 0.0   # RPM estimée à partir des pulses STEP réellement générés
        self.direction = MotorDir[0]  # 'forward'
        self.enabled = False
        self.running = True
        self.ramp_rpm_per_sec = ramp_rpm_per_sec

        self.steps_per_rev = steps_per_rev
        self.microstep_mode = microstep_mode
        self.microstep_factor = self._microstep_factor_from_mode(microstep_mode)
        self.control_enabled = control_enabled

        # Références température
        self.temp_value = None
        self.temp_target = None

        # Driver HR8825 - MÊME INITIALISATION que test_stepper.py
        self.driver = HR8825(
            dir_pin=dir_pin,
            step_pin=step_pin,
            enable_pin=enable_pin,
            mode_pins=mode_pins,
        )
        self.driver.SetMicroStep('hardward', microstep_mode)
        
        # Direction par défaut - COMME test_stepper.py
        self.driver.digital_write(self.driver.dir_pin, 0)

        # UI seulement si dispo
        if self.motor_ui is not None:
            self.motor_ui.control_enabled = self.control_enabled    

        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def process_command(self, command: str):
        """
        Gère les commandes reçues de l'UI.
        CORRECTION : Ne met pas enabled=True immédiatement pour EXTRUDER:ON
        """
        try:
            if command == 'EXTRUDER:ON':
                # Juste activer le flag, le thread gère l'ENABLE
                with self._lock:
                    self.enabled = True
                    print("🟢 Moteur activé (attente vitesse > 0)")

            elif command == 'EXTRUDER:OFF':
                with self._lock:
                    self.enabled = False
                    self.target_rpm = 0.0
                    self.current_rpm = 0.0
                print("🔴 Moteur désactivé")

            elif command.startswith('EXTRUDER:'):
                rpm = float(command.split(':')[1])
                rpm = max(0.0, min(self.max_rpm, rpm))
                with self._lock:
                    self.target_rpm = rpm
                # Mise à jour UI (si elle existe)
                if self.motor_ui is not None:
                    self.motor_ui.target_value = rpm
                    self.motor_ui.update_display()
                print(f"🎯 Consigne vitesse: {rpm} rpm")

        except Exception as e:
            print(f'❌ Erreur process_command moteur: {e}')

    def update_temperature(self, temp_value, temp_target):
        """Identique à votre version originale"""
        self.temp_value = temp_value
        self.temp_target = temp_target
        if self.motor_ui is not None:
            self.motor_ui.temp_value = temp_value
            self.motor_ui.temp_target = temp_target
            self.motor_ui.control_enabled = self.control_enabled

    def get_status(self):
        with self._lock:
            return {
                'enabled': self.enabled,
                'target_rpm': self.target_rpm,
                'current_rpm': self.current_rpm,
                'direction': self.direction,
                'temp_value': self.temp_value,
                'temp_target': self.temp_target,
                'measured_rpm': self.measured_rpm,
            }

    def close(self):
            self.running = False
            with self._lock:
                self.enabled = False
            try:
                self.driver.Stop()
            except Exception:
                pass

    def _microstep_factor_from_mode(self, mode: str) -> int:
        mapping = {
            'fullstep': 1, 'halfstep': 2, '1/4step': 4,
            '1/8step': 8, '1/16step': 16, '1/32step': 32,
        }
        return mapping.get(mode, 1)

    def _compute_stepdelay(self, rpm: float) -> float:
        """
        Version basée sur ton script fluide : on calcule la PÉRIODE entre deux steps.
        """
        if rpm <= 0:
            return 0.0
        
        steps_per_rev_effective = self.steps_per_rev * self.microstep_factor
        step_freq = rpm * steps_per_rev_effective / 60.0
        
        if step_freq <= 0:
            return 0.0
            
        # 🔥 Période = 1 / fréquence (temps entre le début de chaque step)
        period = 1.0 / step_freq
        
        # 🔥 LIMITE : ne pas descendre en dessous de 100 µs à très haute vitesse
        min_period = 0.0001  # 100 µs =0.0001
        return max(min_period, period)

    def _run(self):
        """
        Boucle temps réel inspirée de ton script fluide :
        - rampe d'accélération
        - contrôle fin du timing entre steps (step_period)
        - pulses très courts sur STEP
        """
        ramp_rpm_per_sec = 200.0
        last_time = time.time()
        hw_enabled = False  

        # Timing fin des steps
        last_step_time = time.time()
        pulse_duration = 0.000002  # 2 µs
        #measured rpm
        step_count = 0
        rpm_window_start = time.perf_counter()

        while self.running:
            now = time.time()
            dt = now - last_time
            last_time = now

            # Lecture de l'état demandé (protégé par le lock)
            with self._lock:
                enabled = self.enabled
                target = self.target_rpm
                direction = self.direction

            # --- Gestion ENABLE du driver ---
            if enabled and not hw_enabled:
                self.driver.digital_write(self.driver.enable_pin, 1)
                if direction == MotorDir[0]:
                    self.driver.digital_write(self.driver.dir_pin, 0)
                else:
                    self.driver.digital_write(self.driver.dir_pin, 1)
                hw_enabled = True

            if not enabled or target <= 0:
                self.current_rpm = 0.0
                #Remettre measured_rpm à 0 quand moteur OFF
                with self._lock:
                    self.measured_rpm = 0.0
                if hw_enabled:
                    self.driver.Stop()
                    hw_enabled = False
                time.sleep(0.01)
                continue

            # --- Rampe d’accélération / décélération ---
            max_delta = ramp_rpm_per_sec * dt
            if self.current_rpm < target:
                self.current_rpm = min(target, self.current_rpm + max_delta)
            elif self.current_rpm > target:
                self.current_rpm = max(target, self.current_rpm - max_delta)

            rpm = self.current_rpm
            step_period = self._compute_stepdelay(rpm)

            if step_period <= 0:
                time.sleep(0.005)
                continue

            # Temps écoulé depuis le dernier step
            time_since_last_step = now - last_step_time

            if time_since_last_step >= step_period:
                # On génère un step
                try:
                    self.driver.digital_write(self.driver.step_pin, 1)
                    #time.sleep(pulse_duration)
                    self.driver.digital_write(self.driver.step_pin, 0)
                    step_count += 1 #compteur nombre de step
                    last_step_time = time.time()
                    #calcul de la RPM toutes les 1sec 
                    now_perf = time.perf_counter()
                    dt_window = now_perf - rpm_window_start
                    if dt_window >= 1.0:
                        steps_per_rev_effective = self.steps_per_rev * self.microstep_factor  # 200 * 16 = 3200
                        step_freq = step_count / dt_window  # steps/sec
                        rpm_meas = (step_freq / steps_per_rev_effective) * 60.0
                        #print(f"[RPM] dt={dt_window:.3f}s steps={step_count} f={step_freq:.1f}Hz rpm={rpm_meas:.2f} target={self.target_rpm:.2f}")

                        with self._lock:
                            self.measured_rpm = rpm_meas

                        step_count = 0
                        rpm_window_start = now_perf

                except Exception as e:
                    print(f"❌ Erreur génération step: {e}")
                    time.sleep(0.01)
            else:
                # 🔥 Attente adaptative pour garder un timing précis
                time_remaining = step_period - time_since_last_step

                if time_remaining > 0.0005:  # > 500 µs
                    if rpm < 50:      # Basse vitesse → on peut dormir plus
                        time.sleep(time_remaining * 0.9)
                    else:             # Haute vitesse → moins de sleep pour rester précis
                        time.sleep(time_remaining * 0.3)

def run_motor_process(cmd_queue, status_queue):
        """
        Fonction exécutée dans un PROCESSUS séparé.
        - Reçoit les commandes de la GUI via cmd_queue (EXTRUDER:ON/OFF/NN).
        - Met à jour le moteur via MoteurExtrusion.
        - Envoie régulièrement l'état via status_queue.
        """
        # ⚠️ Importer ici tout ce qui dépend du hardware est déjà fait en haut du module (HR8825)

        # Création de l'objet moteur SANS interface graphique
        moteur = MoteurExtrusion(
            motor_ui=None,           # Très important : aucun widget Tkinter ici
            dir_pin=13,
            step_pin=19,
            enable_pin=12,
            mode_pins=(16, 27, 20),
            steps_per_rev=200,
            microstep_mode='1/16step',
            max_rpm=250.0,
            default_rpm=10.0,
            control_enabled=True,
        )

        last_status_time = time.time()

        try:
            while True:
                # 1) Lecture des commandes venant de la GUI
                try:
                    cmd = cmd_queue.get(timeout=0.01)
                    if cmd == "QUIT":
                        print("🔚 Commande QUIT reçue, arrêt du processus moteur.")
                        moteur.close()
                        break
                    else:
                        moteur.process_command(cmd)
                except queue.Empty:
                    pass

                # 2) Envoi périodique de l'état du moteur à la GUI
                now = time.time()
                if now - last_status_time >= 0.1:  # toutes les 100 ms
                    status = moteur.get_status()
                    try:
                        status_queue.put_nowait(status)
                    except queue.Full:
                        # Si jamais la queue est pleine, on ignore (la GUI rattrapera plus tard)
                        pass
                    last_status_time = now

                # 3) Petite pause pour ne pas saturer le CPU
                time.sleep(0.001)
        except KeyboardInterrupt:
            moteur.close()
