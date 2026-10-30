import time
import threading
import queue
from gpiozero import DigitalOutputDevice

from gpiozero.pins.lgpio import LGPIOFactory
from gpiozero import Device
Device.pin_factory = LGPIOFactory()

MotorDir = ['forward', 'backward']


class DM860T_Driver:

    def __init__(self, dir_pin: int, step_pin: int, enable_pin=None, mode_pins=None):
        self.dir_pin = dir_pin
        self.step_pin = step_pin
        self.enable_pin = enable_pin  # non cablé
        self.mode_pins = mode_pins    # non utilisé (microstep reglé via DIP switch)

        self._dir = DigitalOutputDevice(self.dir_pin, initial_value=False)
        self._step = DigitalOutputDevice(self.step_pin, initial_value=False)

        self._en = None
        if self.enable_pin is not None:
            self._en = DigitalOutputDevice(self.enable_pin, initial_value=False)

    def SetMicroStep(self, *_args, **_kwargs):
        # Microstep reglé par DIP switch sur le DM860T -> rien a faire coté logiciel
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
 
    def __init__(
        self,
        dir_pin=22,             
        step_pin=16,
        enable_pin=None,        
        mode_pins=None,
        motor_ui=None,
        steps_per_rev=200,      # NEMA34 typique: 1.8deg/pas -> 200 pas/tour
        microstep_mode='1/4step',  # DOIT correspondre au reglage DIP switch du DM860T   
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

        self.direction = MotorDir[1]
        self.enabled = False
        self.running = True

        self.ramp_rpm_per_sec = float(ramp_rpm_per_sec)

        self.steps_per_rev = int(steps_per_rev)
        self.microstep_mode = microstep_mode
        self.microstep_factor = self._microstep_factor_from_mode(microstep_mode)

        self.control_enabled = bool(control_enabled)

        self.temp_value = None
        self.temp_target = None

        # --- Driver DM860T ---
        self.driver = DM860T_Driver(
            dir_pin=dir_pin,
            step_pin=step_pin,
            enable_pin=enable_pin,
            mode_pins=mode_pins
        )
        self.driver.SetMicroStep('hardware', microstep_mode)  

        self.driver.digital_write(self.driver.dir_pin, 0)

        if self.motor_ui is not None:
            self.motor_ui.control_enabled = self.control_enabled

        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def process_command(self, command: str):
       
        try:
            if command == 'EXTRUDER:ON':
                with self._lock:
                    self.enabled = True
                print("Moteur active (attente vitesse > 0)")

            elif command == 'EXTRUDER:OFF':
                with self._lock:
                    self.enabled = False
                    self.current_rpm = 0.0
                    self.measured_rpm = 0.0
                print("Moteur desactive")

            elif command == 'EXTRUDER:REVERSE':
                with self._lock:
                    self.direction = MotorDir[0] if self.direction == MotorDir[1] else MotorDir[1]
                    nouvelle_direction = self.direction
                print(f"Sens de rotation inverse: {nouvelle_direction}")

            elif command.startswith('EXTRUDER:'):
                rpm = float(command.split(':')[1])
                rpm = max(0.0, min(self.max_rpm, rpm))
                with self._lock:
                    self.target_rpm = rpm

                if self.motor_ui is not None:
                    self.motor_ui.target_value = rpm
                    self.motor_ui.update_display()

                print(f"Consigne vitesse: {rpm} rpm")

        except Exception as e:
            print(f'Erreur process_command moteur: {e}')

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
        step_freq = rpm * steps_per_rev_effective / 60.0  # pas/s

        if step_freq <= 0:
            return 0.0

        period = 1.0 / step_freq

        min_period = 0.0001  # 100 us
        return max(min_period, period)

    def _run(self):
        last_time = time.time()
        hw_enabled = False

        last_step_time = time.time()
        step_count = 0
        rpm_window_start = time.perf_counter()
        direction_appliquee = None  

        while self.running:
            now = time.time()
            dt = now - last_time
            last_time = now

            with self._lock:
                enabled = self.enabled
                target = self.target_rpm
                direction = self.direction

            if enabled and not hw_enabled:
                self.driver.digital_write(self.driver.enable_pin, 1)
                hw_enabled = True

            
            if direction != direction_appliquee:
                if direction == MotorDir[1]:
                    self.driver.digital_write(self.driver.dir_pin, 0)
                else:
                    self.driver.digital_write(self.driver.dir_pin, 1)
                direction_appliquee = direction

            if (not enabled) or target <= 0:
                self.current_rpm = 0.0
                with self._lock:
                    self.measured_rpm = 0.0

                if hw_enabled:
                    self.driver.Stop()
                    hw_enabled = False

                time.sleep(0.01)
                continue

            
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
                    self.driver.digital_write(self.driver.step_pin, 1)
                    self.driver.digital_write(self.driver.step_pin, 0)

                    step_count += 1
                    last_step_time = time.time()

                    # --- Calcul de measured_rpm 
                    # comptage des pas reellement envoyes sur une fenetre 1s) ---
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
                    print(f"Erreur generation step: {e}")
                    time.sleep(0.01)

            else:
                time_remaining = step_period - time_since_last_step
                if time_remaining > 0.0005:
                    if rpm < 50:
                        time.sleep(time_remaining * 0.9)
                    else:
                        time.sleep(time_remaining * 0.3)


def run_motor_process(cmd_queue, status_queue):
    
    moteur = MoteurExtrusion(
        motor_ui=None,
        dir_pin=22,
        step_pin=16,
        enable_pin=None,
        mode_pins=None,
        steps_per_rev=200,
        microstep_mode='1/4step',  # DOIT matcher avec DIP switch DM860T 
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
                    print("Commande QUIT recue, arret du processus moteur.")
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