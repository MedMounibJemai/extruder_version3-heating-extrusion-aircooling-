import os
import spidev
from gpiozero import PWMOutputDevice
from simple_pid import PID
from datetime import datetime
from Bib.PID_AutoTune_Control import PID_ATune
import time


class SystemeChauffageMAX6675:
    """
    Classe dédiée au contrôle de chauffage via:
      - Thermocouple K + MAX6675 (SPI spidev)
      - Sortie PWM via PWMOutputDevice (MOSFET / SSR DC)
      - PID simple_pid
      - PID Autotune (PID_ATune)
      - Historique (timestamps, températures, pwm)
      - Lecture/écriture des paramètres PID dans un fichier

    API principale:
      - process_command("DEMARRER" | "STOP" | "AUTOTUNE" | "SETPOINT:x" | "SETPID:kp,ki,kd")
      - appliquer_pid_depuis_fichier()
      - update() -> dict(temperature, setpoint, pwm, timestamp)
      - close()
    """

    def __init__(self) :
        # --- PWM / sortie chauffage
        self.MOSFET_PIN = 6
        self.pwm = PWMOutputDevice(self.MOSFET_PIN, frequency=100, initial_value=0)

        # --- SPI MAX6675
        self.SPI_BUS = 0
        self.SPI_DEVICE = 0
        self.spi = spidev.SpiDev()
        self.spi.open(self.SPI_BUS, self.SPI_DEVICE)
        self.spi.max_speed_hz = 1000000  # 1 MHz
        self.spi.mode = 0  # SPI mode 0 (CPOL=0, CPHA=0)
       
        # --- Paramètres de contrôle
        self.setpoint = 30 #il faut changer la valeur à 30°C pour qu'elle soit compatible avec l'interface
        self.current_temp = 25.0
        self.output_pwm = 0.0
        self.autotune_mode = False
        self.chauffage_active = False  #à changer pour false pour ne pas démarrer le chauffage dès le lancement
        self.pid_filename = "pid_params.txt"

        # --- PID init 
        self.initialize_pid()

        # --- Historique des données
        self.timestamps = []
        self.temperatures = []
        self.pwm_values = []
        self.start_time = datetime.now()

        # --- Autotune init
        # On lui donne:
        #  - une fonction de lecture T
        #  - une fonction d'écriture de sortie (ici on écrit pid.output via setattr)
        #self.pid_atune = PID_ATune(self.read_temperature, lambda x: setattr(self.pid, "output", x))
        self.pid_atune = PID_ATune(self.read_temperature, lambda x: self.set_pwm(x))
        #Envoi des logs à l'UI
    #     self.serial_callback = None
    
    # def _log(self, msg: str):
    #     """Envoie un message au Serial Monitor si callback présent, sinon print."""
    #     try:
    #         if self.serial_callback:
    #             self.serial_callback(msg)
    #         else:
    #             print(msg)
    #     except Exception as e:
    #         print("Erreur serial_callback:", e)
    #         print(msg)

  
    # PID + fichier
    def initialize_pid(self):
        """Initialise le contrôleur PID avec les paramètres du fichier ou par défaut"""
        DEFAULT_PID = "3.31,0.02,50.31" #à changer par les premières valeurs issu de l'autotune

        """Initialise le PID depuis fichier ou valeurs par défaut."""
        if not os.path.exists(self.pid_filename):
            with open(self.pid_filename, "w") as f:
                f.write(DEFAULT_PID)

        # Lire les valeurs PID    
        with open(self.pid_filename, "r") as f:
            pid_values = f.read().strip().split(",")
            kp, ki, kd = float(pid_values[0]), float(pid_values[1]), float(pid_values[2])

        self.pid = PID(kp, ki, kd, setpoint=self.setpoint)
        self.pid.output_limits = (0, 100)

        # Par défaut, on laisse auto_mode selon l'état chauffage_active (a voir en détailles)
        #self.pid.auto_mode = self.chauffage_active
        self.pid.set_auto_mode(True, last_output=self.output_pwm)  # Démarrer avec la dernière sortie PWM
    
    def appliquer_pid_depuis_fichier(self):
        """Applique les paramètres PID depuis le fichier."""
        try:
            with open(self.pid_filename, "r") as f:
                content = f.read().strip()
            self.process_command(f"SETPID:{content}")
        except Exception as e:
            print(f"Erreur lecture fichier PID: {e}")

    # Fonctions pour lire la température via MAX6675
    def max6675_read_celsius(self):
        """
        MAX6675 retourne 16 bits.
        - D2 = 1 => thermocouple ouvert
        - D15..D3 => température * 4 (pas 0.25°C)
        """
        data = self.spi.xfer2([0x00, 0x00])
        value = (data[0] << 8) | data[1]

        if value & 0x0004:
            raise RuntimeError("Thermocouple ouvert/débranché (MAX6675 D2=1)")

        temp_c = ((value >> 3) & 0x1FFF) * 0.25
        return temp_c

    def read_temperature(self):
        """Lecture température (avec gestion d'erreurs)."""
        try:
            return self.max6675_read_celsius()
        except Exception as e:
            print(f"Erreur lecture température: {e}")
            # fallback: garder dernière valeur si dispo, sinon 25
            return self.current_temp if self.current_temp is not None else 25.0

    # Fonction pour appliquer le PWM au mosfet 
    def set_pwm(self, value):
        """Applique une valeur PWM entre 0 et 100%."""
        try:
            # pwm_value = max(0, min(1, value/100.0))
            # self.pwm.value = pwm_value
            # Limiter en %
            value_percent = max(0.0, min(100.0, float(value)))

            # Sauvegarder pour PID / UI
            self.output_pwm = value_percent

            # Convertir en ratio pour gpiozero
            pwm_ratio = value_percent / 100.0
            self.pwm.value = pwm_ratio

        except Exception as e:
            print(f"❌ Erreur PWM: {e}")

    # Fonction pour traiter les commandes
    def process_command(self, command):
        """
        Commandes supportées:
          - "AUTOTUNE"
          - "SETPOINT:xxx"
          - "SETPID:kp,ki,kd"
          - "DEMARRER"
          - "STOP"
        """
        if command == "AUTOTUNE":
            self.autotune_mode = True
            self.chauffage_active = True
            self.output_pwm = 0
            self.pid.auto_mode = False
            self.pid_atune.SetControlType(1)  # Mode PID
            self.pid_atune.SetOutputStep(50)  # Étape pour provoquer les oscillations
            self.pid_atune.SetNoiseBand(0.5)  # Bande de bruit en °C
            self.pid_atune.SetLookbackSec(20)  # Durée d'observation en secondes
            self._autotune_start_time = time.time()
            print(f"[AUTOTUNE DÉMARRÉ] {datetime.now().strftime('%H:%M:%S')}")

        elif command.startswith("SETPOINT:"):
            self.setpoint = float(command.split(":")[1])
            self.pid.setpoint = self.setpoint
            
        elif command.startswith("SETPID:"):
            params = command.split(":")[1].split(",")
            kp, ki, kd = float(params[0]), float(params[1]), float(params[2])
            self.pid.tunings = (kp, ki, kd)
            
        elif command == "DEMARRER":
            self.chauffage_active = True
            self.pid.auto_mode = True

        elif command == "STOP":
            self.autotune_mode = False
            self.chauffage_active = False
            self.pid.auto_mode = False
            self.set_pwm(0)
   
    # Boucle de contrôle
    def update(self):
        # 1) lecture température
        temperature = self.read_temperature()
        self.current_temp = temperature

        # 2) autotune
        if self.autotune_mode:
            tune_status = self.pid_atune.Runtime()
            if tune_status != 0:
                kp_classic = self.pid_atune.GetKp()
                ki_classic = self.pid_atune.GetKi()
                kd_classic = self.pid_atune.GetKd()

                # Calcul des nouveaux gains avec Tyreus-Luyben
                kp, ki, kd, Ku, Pu = self.calcul_pid_tyreus_luyben(
                    kp_classic, ki_classic, kd_classic
                )

                self.pid.tunings = (kp, ki, kd)
                self.pid.auto_mode = True
                self.autotune_mode = False

                # Ajout de l'affichage du temps pour savoir combien a pris l'autotune
                duree = time.time() - self._autotune_start_time
                minutes = int(duree // 60)
                secondes = int(duree % 60)
                print(f"[AUTOTUNE TERMINÉ] {datetime.now().strftime('%H:%M:%S')}")
                print(f"[AUTOTUNE DURÉE]   {minutes}min {secondes}s")
                print(f"[AUTOTUNE Ku/Pu]   Ku≈{Ku:.4f} | Pu≈{Pu:.2f}s")
                print(
                    f"[AUTOTUNE ZN CLASSIQUE - NON APPLIQUÉ] "
                    f"Kp={kp_classic:.4f} | Ki={ki_classic:.4f} | Kd={kd_classic:.4f}"
                )
                print(
                    f"[AUTOTUNE TYREUS-LUYBEN - APPLIQUÉ] "
                    f"Kp={kp:.4f} | Ki={ki:.4f} | Kd={kd:.4f}"
                )

                self.chauffage_active = True   # reprend le contrôle PID normal après autotune

                # sauvegarde des nouveaux paramètres
                try:
                    with open(self.pid_filename, "w") as f:
                        f.write(f"{kp},{ki},{kd}")
                except Exception as e:
                    print(f"❌ Erreur sauvegarde PID: {e}")

        # 3) Contrôle PID normal 
        elif self.chauffage_active: # elif : PID normal seulement si pas d'autotune
            self.output_pwm = self.pid(temperature)
            #self.output_pwm = max(0, min(100, self.output_pwm))
            self.set_pwm(self.output_pwm)

        # 4) Mise à jour des historiques
        t = (datetime.now() - self.start_time).total_seconds()
        self.timestamps.append(t)
        self.temperatures.append(temperature)
        self.pwm_values.append(self.output_pwm)
        #######
        #self._log(f"Température: {temperature:.2f}  Consigne: {self.setpoint:.2f}  PWM: {self.output_pwm:.2f}")
        #######
        return {
            "temperature": temperature,
            "setpoint": self.setpoint,
            "pwm": self.output_pwm,
            "timestamp": t,
        }
        


    def close(self):
        """Arrêt propre: PWM=0 + close GPIO + close SPI."""
        try:
            self.set_pwm(0)
        except:
            pass
        try:
            self.pwm.close()
        except:
            pass
        try:
            self.spi.close()
        except:
            pass
    
    def get_status(self):
        """Retourne le statut actuel du système"""
        return {
            'active': self.chauffage_active,
            'autotune': self.autotune_mode,
            'setpoint': self.setpoint,
            'current_temp': self.current_temp,
            'pwm': self.output_pwm
        }

    def calcul_pid_tyreus_luyben(self, kp_classic, ki_classic, kd_classic):
        """
        Reconstruit Ku et Pu à partir des gains PID classiques retournés
        par PID_ATune, puis calcule les gains PID avec la méthode
        Tyreus-Luyben.
        """
        # PID classique de Ziegler-Nichols :
        # Kp = 0.6*Ku ; Ti = Kp/Ki = Pu/2 ; Td = Kd/Kp = Pu/8
        Ku = kp_classic / 0.6 if kp_classic else 0
        Pu_from_ki = 2 * (kp_classic / ki_classic) if ki_classic else 0
        Pu_from_kd = 8 * (kd_classic / kp_classic) if kp_classic else 0

        if Pu_from_ki and Pu_from_kd:
            Pu = (Pu_from_ki + Pu_from_kd) / 2
        else:
            Pu = max(Pu_from_ki, Pu_from_kd)

        # Réglage Tyreus-Luyben
        kp = Ku / 2.2
        Ti_tl = 2.2 * Pu
        Td_tl = Pu / 6.3
        ki = kp / Ti_tl if Ti_tl else 0
        kd = kp * Td_tl

        return kp, ki, kd, Ku, Pu

