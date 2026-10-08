"""
Test isole du moteur NEMA23/DM860T, sans Tkinter ni multiprocessing -
juste la classe MoteurExtrusion, pilotee directement depuis le terminal.

But: valider que le moteur repond correctement (demarrage, vitesse,
inversion de sens, arret) avant de le rebrancher a l'application complete.

Commandes disponibles (tapees au clavier, Entree pour valider):
    on          -> active le moteur
    off         -> desactive le moteur
    <nombre>    -> regle la vitesse cible en tr/min (ex: 10, 50, 100)
    r           -> inverse le sens de rotation
    s           -> affiche le statut actuel
    q           -> quitte proprement (coupe le moteur avant de sortir)
"""

import time
from modules.motor_dm860t import MoteurExtrusion

if __name__ == "__main__":
    print("=== Test isole moteur NEMA23/DM860T ===")
    print("Broches: DIR=GPIO22, STEP=GPIO23, EN=non cablee")
    print("Microstepping: 1/8 (verifie DIP switch SW5-8 = ON,OFF,ON,ON)\n")

    moteur = MoteurExtrusion(
        dir_pin=22,
        step_pin=16,
        enable_pin=None,
        mode_pins=None,
        steps_per_rev=200,
        microstep_mode='1/4step',
        max_rpm=250.0,
        default_rpm=10.0,
        ramp_rpm_per_sec=200.0,
    )

    print("Commandes: on | off | <rpm> | r (inverser sens) | s (statut) | q (quitter)\n")

    try:
        while True:
            cmd = input(">> ").strip().lower()

            if cmd == "q":
                break
            elif cmd == "on":
                moteur.process_command("EXTRUDER:ON")
            elif cmd == "off":
                moteur.process_command("EXTRUDER:OFF")
            elif cmd == "r":
                moteur.process_command("EXTRUDER:REVERSE")
            elif cmd == "s":
                statut = moteur.get_status()
                print(f"  Actif: {statut['enabled']} | "
                      f"Consigne: {statut['target_rpm']:.1f} tr/min | "
                      f"Vitesse actuelle: {statut['current_rpm']:.1f} tr/min | "
                      f"Vitesse mesuree: {statut['measured_rpm']:.1f} tr/min | "
                      f"Sens: {statut['direction']}")
            else:
                try:
                    rpm = float(cmd)
                    moteur.process_command(f"EXTRUDER:{rpm}")
                except ValueError:
                    print("  Commande non reconnue. Utilisez: on | off | <rpm> | r | s | q")

    except KeyboardInterrupt:
        print("\nInterruption utilisateur.")
    finally:
        moteur.close()
        print("Moteur arrete proprement.")