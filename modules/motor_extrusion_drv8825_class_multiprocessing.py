import time
import threading
import queue
from gpiozero import DigitalOutputDevice

from gpiozero.pins.lgpio import LGPIOFactory
from gpiozero import Device
Device.pin_factory = LGPIOFactory()

MotorDir = ['forward', 'backward']


class DRV8825_Driver:
    """
    Driver minimal DRV8825 (STEP/DIR) compatible Raspberry Pi 5 via gpiozero.

    Objectif: remplacer HR8825 sans changer la logique du code appelant :
    - garde digital_write(pin, value)
    - garde Stop()
    - garde SetMicroStep() (no-op, car microstep réglé physiquement)
    - enable_pin peut être None (si EN est câblé au GND -> driver toujours actif)
    """

    def __init__(self, dir_pin: int, step_pin: int, enable_pin=None, mode_pins=None):
        self.dir_pin = dir_pin
        self.step_pin = step_pin
        self.enable_pin = enable_pin  # None si EN câblé au GND
        self.mode_pins = mode_pins    # non utilisé (microstep manuel)

        self._dir = DigitalOutputDevice(self.dir_pin, initial_value=False)
        self._step = DigitalOutputDevice(self.step_pin, initial_value=False)

        self._en = None
        if self.enable_pin is not None:
            self._en = DigitalOutputDevice(self.enable_pin, initial_value=False)

    def SetMicroStep(self, *_args, **_kwargs):
        # Microstep réglé par jumpers sur le DRV8825 -> rien à faire
        return

    def digital_write(self, pin, value: int):
        if pin is None:
            return

        is_on = bool(value)

        if pin == self.step_pin:
            self._step.on() if is_on else self._step.off()
        elif pin == self.dir_pin:
            self._dir.on() if is_on else self._dir.off()
        elif self._en is not None and pin == self.enable_pin:
            self._en.on() if is_on else self._en.off()

    def Stop(self):
        # On force STEP à 0
        try:
            self._step.off()
        except Exception:
            pass

    def close(self):
        try:
            self._step.close()
            self._dir.close()
            if self._en is not None:
                self._en.close()
        except Exception:
            pass


class MoteurExtrusion:
    """
    Classe de haut niveau pour le contrôle du moteur d'extrusion.
    Logique inchangée: ramp, timing step, measured_rpm, commandes 'EXTRUDER:*', multiprocessing.
    """

    def __init__(
        self,
        dir_pin,
        step_pin,
        enable_pin,
        mode_pins,
        motor_ui=None,
        steps_per_rev=200,
        microstep_mode='1/16step',
        max_rpm=75.0,
        default_rpm=10.0,
        control_enabled=True,
        ramp_rpm_per_sec=200.0
    ):
        self.motor_ui = motor_ui
        self.max_rpm = max_rpm

        self.target_rpm = float(default_rpm)
        self.current_rpm = 0.0
        self.measured_rpm = 0.0

        self.direction = MotorDir[0]  # 'forward'
        self.enabled = False
        self.running = True

        self.ramp_rpm_per_sec = float(ramp_rpm_per_sec)

        self.steps_per_rev = int(steps_per_rev)
        self.microstep_mode = microstep_mode
        self.microstep_factor = self._microstep_factor_from_mode(microstep_mode)

        self.control_enabled = bool(control_enabled)

        # Références température (si UI les affiche)
        self.temp_value = None
        self.temp_target = None

        # --- Driver DRV8825 (gpiozero, Pi 5) ---
        self.driver = DRV8825_Driver(
            dir_pin=dir_pin,
            step_pin=step_pin,
            enable_pin=enable_pin,  # None si EN câblé GND
            mode_pins=mode_pins
        )
        self.driver.SetMicroStep('hardward', microstep_mode)  # no-op (compat)

        # Direction par défaut identique (forward -> 0)
        self.driver.digital_write(self.driver.dir_pin, 0)

        if self.motor_ui is not None:
            self.motor_ui.control_enabled = self.control_enabled

        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def process_command(self, command: str):
        """
        Commandes attendues (inchangé):
          - EXTRUDER:ON
          - EXTRUDER:OFF
          - EXTRUDER:<rpm>
        """
        try:
            if command == 'EXTRUDER:ON':
                with self._lock:
                    self.enabled = True
                print("🟢 Moteur activé (attente vitesse > 0)")

            elif command == 'EXTRUDER:OFF':
                with self._lock:
                    self.enabled = False
                    self.target_rpm = 0.0
                    self.current_rpm = 0.0
                    self.measured_rpm = 0.0
                print("🔴 Moteur désactivé")

            elif command.startswith('EXTRUDER:'):
                rpm = float(command.split(':')[1])
                rpm = max(0.0, min(self.max_rpm, rpm))
                with self._lock:
                    self.target_rpm = rpm

                if self.motor_ui is not None:
                    self.motor_ui.target_value = rpm
                    self.motor_ui.update_display()

                print(f"🎯 Consigne vitesse: {rpm} rpm")

        except Exception as e:
            print(f'❌ Erreur process_command moteur: {e}')

    def update_temperature(self, temp_value, temp_target):
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
        # Arrêt propre
        self.running = False
        with self._lock:
            self.enabled = False
            self.target_rpm = 0.0
            self.current_rpm = 0.0
            self.measured_rpm = 0.0

        try:
            self.driver.Stop()
        except Exception:
            pass

        try:
            self.driver.close()
        except Exception:
            pass

    def _microstep_factor_from_mode(self, mode: str) -> int:
        mapping = {
            'fullstep': 1,
            'halfstep': 2,
            '1/4step': 4,
            '1/8step': 8,
            '1/16step': 16,
            '1/32step': 32,
        }
        return mapping.get(mode, 1)

    def _compute_stepdelay(self, rpm: float) -> float:
        if rpm <= 0:
            return 0.0

        steps_per_rev_effective = self.steps_per_rev * self.microstep_factor
        step_freq = rpm * steps_per_rev_effective / 60.0  # steps/s

        if step_freq <= 0:
            return 0.0

        period = 1.0 / step_freq

        # garde-fou identique
        min_period = 0.0001  # 100 µs
        return max(min_period, period)

    def _run(self):
        last_time = time.time()
        hw_enabled = False

        last_step_time = time.time()
        step_count = 0
        rpm_window_start = time.perf_counter()

        while self.running:
            now = time.time()
            dt = now - last_time
            last_time = now

            with self._lock:
                enabled = self.enabled
                target = self.target_rpm
                direction = self.direction

            # "Enable" logique inchangée:
            # - si enable_pin=None (EN câblé GND), digital_write(None, ...) ne fait rien
            if enabled and not hw_enabled:
                self.driver.digital_write(self.driver.enable_pin, 1)
                if direction == MotorDir[0]:
                    self.driver.digital_write(self.driver.dir_pin, 0)
                else:
                    self.driver.digital_write(self.driver.dir_pin, 1)
                hw_enabled = True

            # Stop si off ou rpm=0
            if (not enabled) or target <= 0:
                self.current_rpm = 0.0
                with self._lock:
                    self.measured_rpm = 0.0

                if hw_enabled:
                    self.driver.Stop()
                    hw_enabled = False

                time.sleep(0.01)
                continue

            # Ramp rpm (inchangé)
            max_delta = self.ramp_rpm_per_sec * dt
            if self.current_rpm < target:
                self.current_rpm = min(target, self.current_rpm + max_delta)
            elif self.current_rpm > target:
                self.current_rpm = max(target, self.current_rpm - max_delta)

            rpm = self.current_rpm
            step_period = self._compute_stepdelay(rpm)

            if step_period <= 0:
                time.sleep(0.005)
                continue

            time_since_last_step = now - last_step_time

            if time_since_last_step >= step_period:
                try:
                    # Pulse STEP (identique)
                    self.driver.digital_write(self.driver.step_pin, 1)
                    #time.sleep(0.00002)  # 20 µs
                    self.driver.digital_write(self.driver.step_pin, 0)

                    step_count += 1
                    last_step_time = time.time()

                    # Calcul rpm_meas (identique)
                    now_perf = time.perf_counter()
                    dt_window = now_perf - rpm_window_start
                    if dt_window >= 1.0:
                        steps_per_rev_effective = self.steps_per_rev * self.microstep_factor
                        step_freq = step_count / dt_window
                        rpm_meas = (step_freq / steps_per_rev_effective) * 60.0

                        with self._lock:
                            self.measured_rpm = rpm_meas

                        step_count = 0
                        rpm_window_start = now_perf

                except Exception as e:
                    print(f"❌ Erreur génération step: {e}")
                    time.sleep(0.01)

            else:
                # Sleep adaptatif (inchangé)
                time_remaining = step_period - time_since_last_step
                if time_remaining > 0.0005:
                    if rpm < 50:
                        time.sleep(time_remaining * 0.9)
                    else:
                        time.sleep(time_remaining * 0.3)


def run_motor_process(cmd_queue, status_queue):
    """
    Process séparé (inchangé).
    Pins DRV8825 selon ta config:
      - STEP = GPIO16
      - DIR  = GPIO20
      - EN   = GND => enable_pin=None
      - Microstep réglé à la main => mode_pins=None
    """
    moteur = MoteurExtrusion(
        motor_ui=None,
        dir_pin=20,
        step_pin=16,
        enable_pin=None,
        mode_pins=None,
        steps_per_rev=200,
        microstep_mode='1/16step',  # doit matcher tes jumpers
        max_rpm=250.0,
        default_rpm=10.0,
        control_enabled=True,
        ramp_rpm_per_sec=200.0
    )

    last_status_time = time.time()

    try:
        while True:
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

            now = time.time()
            if now - last_status_time >= 0.1:
                status = moteur.get_status()
                try:
                    status_queue.put_nowait(status)
                except queue.Full:
                    pass
                last_status_time = now

            time.sleep(0.001)

    except KeyboardInterrupt:
        moteur.close()