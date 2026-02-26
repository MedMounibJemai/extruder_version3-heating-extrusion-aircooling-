# modules/systeme_ventilation.py

from gpiozero import PWMOutputDevice
from gpiozero import DigitalOutputDevice
import time

class SystemeVentilation:
    """
    Contrôle 3 ventilateurs 4-fils via PWM (0-100%)
    """

    # Points mesurés (PWM%, RPM)
    CURVE_7500 = [
        (0, 0),
        (20, 1770),
        (40, 3506),
        (60, 5040),
        (80, 6300),
        (100, 7410),
    ]

    CURVE_7000 = [
        (0, 0),
        (20, 1918),
        (40, 2610),
        (60, 3986),
        (80, 5424),
        (100, 6720),
    ]

    def __init__(self, pin_right=23, pin_left=25, pin_center=26, pwm_freq=10000):
        self.pins = {
            "right": pin_right,
            "left": pin_left,
            "center": pin_center
        }
        self.pwm_freq = pwm_freq
        
        # Initialisation des PWM
        self.pwm = {}
        self.initialize_pwm()
        
        self.state = {
            "right":  {"power": False, "duty": 0.0, "rpm_est": 0.0},
            "left":   {"power": False, "duty": 0.0, "rpm_est": 0.0},
            "center": {"power": False, "duty": 0.0, "rpm_est": 0.0},
        }

    def initialize_pwm(self):
        """Initialise les PWM"""
        for name, pin in self.pins.items():
            try:
                pwm = PWMOutputDevice(
                    pin, 
                    frequency=self.pwm_freq, 
                    initial_value=0
                )
                self.pwm[name] = pwm
                print(f"✅ Ventilateur {name} initialisé sur pin {pin}")
            except Exception as e:
                print(f"❌ Erreur initialisation {name} (pin {pin}): {e}")
                self.pwm[name] = None

    # def close(self):
    #     """
    #     Arrête TOUS les ventilateurs de façon sécurisée
    #     """
    #     print("🔧 Arrêt sécurisé des ventilateurs...")
        
    #     # 1) Mettre tous les PWM à 0
    #     for name, pwm in self.pwm.items():
    #         try:
    #             if pwm is not None:
    #                 print(f"  → Arrêt {name}")
    #                 pwm.value = 0.0
    #                 time.sleep(0.05)
    #         except Exception as e:
    #             print(f"⚠️ Erreur arrêt {name}: {e}")
        
    #     time.sleep(0.1)
        
    #     # 2) Fermer proprement chaque PWM
    #     for name, pwm in self.pwm.items():
    #         try:
    #             if pwm is not None:
    #                 pwm.close()
    #                 print(f"  → PWM {name} fermé")
    #         except Exception as e:
    #             print(f"⚠️ Erreur fermeture {name}: {e}")
        
    #     # 3) Vider le dictionnaire
    #     self.pwm.clear()
        
    #     print("✅ Ventilateurs arrêtés")
    def close(self):
        """
        Arrête TOUS les ventilateurs de façon sécurisée (Pi 5 friendly)
        - Met PWM à 0
        - Ferme les PWM (libère les pins)
        - Re-claim les pins en sortie LOW pour éviter le fail-safe (full speed)
        """
        print("🔧 Arrêt sécurisé des ventilateurs...")

        # 1) Mettre tous les PWM à 0
        for name, pwm in self.pwm.items():
            try:
                if pwm is not None:
                    print(f"  → Arrêt {name}")
                    pwm.value = 0.0
            except Exception as e:
                print(f"⚠️ Erreur arrêt {name}: {e}")

        time.sleep(0.1)

        # 2) Fermer les PWM (ATTENTION: libère la pin)
        for name, pwm in list(self.pwm.items()):
            try:
                if pwm is not None:
                    pwm.close()
                    print(f"  → PWM {name} fermé")
            except Exception as e:
                print(f"⚠️ Erreur fermeture {name}: {e}")

        # ✅ 3) Reprendre les pins PWM et les forcer LOW (anti-full-speed)
        # IMPORTANT: garder ces objets vivants jusqu'à la fin du programme
        self._hold_low = {}
        for fan, pin in self.pins.items():
            try:
                dev = DigitalOutputDevice(pin, initial_value=False)
                dev.off()
                self._hold_low[fan] = dev
                print(f"✅ GPIO{pin} ({fan}) forcée LOW")
            except Exception as e:
                print(f"⚠️ Impossible de forcer LOW sur {fan} (GPIO{pin}): {e}")

        # 4) Vider le dictionnaire pwm
        self.pwm.clear()

        print("✅ Ventilateurs arrêtés (pins maintenues à LOW)")

    # Version simplifiée et efficace - PAS de création de nouveaux objets
    def emergency_stop(self):
        """
        Arrêt d'urgence - utilise les PWM existants pour tout arrêter
        """
        print("🚨 ARRÊT D'URGENCE DES VENTILATEURS")
        
        # Utiliser les PWM existants pour tout éteindre
        for name, pwm in self.pwm.items():
            try:
                if pwm is not None:
                    # Forcer la valeur à 0
                    pwm.value = 0.0
                    print(f"  → {name} forcé à 0")
            except Exception as e:
                print(f"    Erreur: {e}")
        
        # Mettre à jour l'état
        for fan in self.state:
            self.state[fan]["power"] = False
            self.state[fan]["duty"] = 0.0
            self.state[fan]["rpm_est"] = 0.0
        
        time.sleep(0.1)
        print("✅ Arrêt d'urgence effectué")

    def get_status(self):
        return self.state

    def process_command(self, cmd: str):
        try:
            parts = cmd.split(":")
            if len(parts) < 4 or parts[0] != "VENT":
                return

            fan = parts[1]
            action = parts[2]
            value = parts[3]

            if fan not in self.state:
                return

            if action == "POWER":
                self.set_power(fan, int(value) == 1)
            elif action == "DUTY":
                self.set_duty(fan, float(value))

        except Exception as e:
            print(f"❌ SystemeVentilation.process_command error: {e} | cmd={cmd}")

    def set_power(self, fan: str, on: bool):
        self.state[fan]["power"] = bool(on)
        if not on:
            if fan in self.pwm and self.pwm[fan] is not None:
                self.pwm[fan].value = 0.0
            self.state[fan]["rpm_est"] = 0.0
        else:
            self._apply_pwm(fan)

    def set_duty(self, fan: str, duty_percent: float):
        duty = max(0.0, min(100.0, float(duty_percent)))
        self.state[fan]["duty"] = duty

        if not self.state[fan]["power"]:
            self.state[fan]["rpm_est"] = 0.0
            if fan in self.pwm and self.pwm[fan] is not None:
                self.pwm[fan].value = 0.0
            return

        self._apply_pwm(fan)

    def _apply_pwm(self, fan: str):
        duty = self.state[fan]["duty"]
        if fan in self.pwm and self.pwm[fan] is not None:
            self.pwm[fan].value = duty / 100.0
        self.state[fan]["rpm_est"] = self.estimate_rpm(fan, duty)

    def estimate_rpm(self, fan: str, duty_percent: float) -> float:
        points = self.CURVE_7000 if fan == "center" else self.CURVE_7500
        return self._interp_piecewise(points, duty_percent)

    @staticmethod
    def _interp_piecewise(points, x):
        x = float(x)
        if x <= points[0][0]:
            return float(points[0][1])
        if x >= points[-1][0]:
            return float(points[-1][1])

        for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
            if x0 <= x <= x1:
                if x1 == x0:
                    return float(y0)
                t = (x - x0) / (x1 - x0)
                return float(y0 + t * (y1 - y0))

        return float(points[-1][1])