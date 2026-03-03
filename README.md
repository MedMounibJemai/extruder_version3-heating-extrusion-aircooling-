# Extruder GUI (Raspberry Pi 5 – 7" Touchscreen)

Interface graphique Python pour piloter une mini-extrudeuse basée sur **Raspberry Pi 5** avec **écran tactile 7 pouces**.  
L’application est structurée autour de **trois sous-systèmes principaux** : chauffage, extrusion et ventilation.

---

## 🧩 Présentation du projet

L’interface graphique permet :
1. **Le contrôle thermique** d’une cartouche chauffante à l’aide d’un thermocouple type K et d’un module **MAX6675**, avec une logique **PID + autotune**  
2. **Le contrôle de la vitesse (RPM)** du moteur d’extrusion **NEMA17** via un driver **HR8825** monté sur un **Stepper Motor HAT B**  
3. **Le contrôle de la vitesse (PWM)** de **trois ventilateurs 4-pins** dédiés au refroidissement

L’interface est optimisée pour un usage tactile sur écran 7".

---

## ⚙️ Fonctionnalités
- Interface graphique tactile (Raspberry Pi 5)
- Régulation de température avec PID et autotune
- Commande du moteur d’extrusion (RPM)
- Commande indépendante de trois ventilateurs 4-pins
- Paramétrage via fichiers externes
- Architecture modulaire (chauffage / moteur / ventilation)

---

## 🧱 Matériel utilisé (référence)
- Raspberry Pi 5 + écran tactile 7"
- Cartouche chauffante
- Thermocouple type K + MAX6675 (SPI)
- Moteur pas à pas NEMA17
- Stepper Motor HAT B (driver HR8825) OR DRV8825 avec Stepper Motor Expansion Board
- 3 ventilateurs 4-pins (PWM)

## ⚠️  Les alimentations de puissance (chauffage, moteur, ventilateurs) doivent être séparées de l’alimentation logique du Raspberry Pi, avec une **masse commune**.

 - La cartouche chauffante est alimentée par une **alimentation dédiée 24 V**  
 - Le moteur d’extrusion est alimenté par une **alimentation dédiée 12 V**  
 - Les ventilateurs sont alimentés par une **alimentation dédiée 12 V**  
 
 - Les trois alimentations sont **séparées** afin d’assurer la stabilité du système, de limiter les perturbations électriques et d’améliorer la sécurité.  
 - Les signaux de commande (GPIO) du Raspberry Pi restent **isolés de la puissance**, avec une **masse commune** pour la référence logique.

## 🔌 Wiring / Distribution des GPIO (Raspberry Pi 5)

Cette section résume la distribution des broches GPIO utilisées pour chaque sous-système.

---

### 🔥 Partie Chauffage

| Fonction | Composant | GPIO / Pin Raspberry Pi |
|--------|----------|--------------------------|
| Commande cartouche chauffante | MOSFET (Gate) | GPIO6 |
| MAX6675 – CS | Chip Select | CE0 (GPIO8) |
| MAX6675 – SO | MISO | GPIO9 |
| MAX6675 – SCK | SCLK | GPIO11 |

Le MAX6675 communique via **SPI**.  
L’interface SPI doit être activée dans le système Raspberry Pi.

---

### ⚙️ Partie Moteur d’Extrusion (en cas d'utilisation du Stepper Motor HAT B)

Le moteur d’extrusion **NEMA17** est piloté via un **Stepper Motor HAT B**.

- Le HAT permet de connecter **deux moteurs**
- Dans ce projet, **un seul moteur est utilisé**
- Chaque moteur utilise **6 broches dédiées**
- Les autres broches du HAT ne sont pas disponibles car elles sont déjà utilisées par le driver

#### Distribution des broches (mode BCM)

| Stepper Motor HAT | Fonction | Raspberry Pi (BCM) |
|------------------|----------|--------------------|
| A1A2B1B2 | DIR | GPIO13 |
| A1A2B1B2 | STEP | GPIO19 |
| A1A2B1B2 | ENABLE | GPIO12 |
| A1A2B1B2 | MODE | GPIO16, GPIO17, GPIO20 |
| A3A4B3B4 | DIR | GPIO24 |
| A3A4B3B4 | STEP | GPIO18 |
| A3A4B3B4 | ENABLE | GPIO4 |
| A3A4B3B4 | MODE | GPIO21, GPIO22, GPIO27 |

> ℹ️ Les GPIO utilisés par le Stepper Motor HAT B sont **réservés** et ne doivent pas être utilisés ailleurs dans le projet.

---
### ⚙️ Partie Moteur d’Extrusion (en cas d'utilisation du DRV8825 avec un Stepper Motor Driver Expansion Board)

Les moteurs d’extrusion sont pilotés via des drivers **DRV8825** montés sur une **Stepper Motor Driver Expansion Board**.

Cette configuration permet :
- de réduire le nombre de GPIO utilisés (**2 GPIO par moteur**)
- de simplifier le câblage
- de déléguer la gestion du microstepping au **hardware**

Le signal **ENABLE** du DRV8825 est connecté directement au **GND**, ce qui maintient le driver **toujours actif**.

---

#### Distribution des broches GPIO (mode BCM)

##### 🔹 Moteur 1
| Signal | GPIO Raspberry Pi |
|------|-------------------|
| STEP | GPIO16 |
| DIR  | GPIO20 |
| ENABLE | GND (toujours actif) |

##### 🔹 Moteur 2
| Signal | GPIO Raspberry Pi |
|------|-------------------|
| STEP | GPIO24 |
| DIR  | GPIO12 |
| ENABLE | GND (toujours actif) |

> ℹ️ Les signaux **STEP** et **DIR** sont générés par le Raspberry Pi.  
> Le signal **ENABLE** étant relié au GND, le driver DRV8825 reste activé en permanence.

### 🧮 Microstepping – DRV8825 (Configuration matérielle)

Le microstepping du driver **DRV8825** est configuré **uniquement par hardware** à l’aide des broches **MODE0, MODE1 et MODE2**.

#### Table de configuration du microstepping

| MODE0 | MODE1 | MODE2 | Résolution |
|------|------|------|------------|
| Low  | Low  | Low  | Full step |
| High | Low  | Low  | Half step |
| Low  | High | Low  | 1/4 step |
| High | High | Low  | 1/8 step |
| Low  | Low  | High | 1/16 step |
| High | Low  | High | 1/32 step |
| Low  | High | High | 1/32 step |
| High | High | High | 1/32 step |

> ⚠️ La résolution du microstepping est définie par le câblage des broches MODE0, MODE1 et MODE2 et **ne peut pas être modifiée par logiciel**.
---

### 🌬️ Partie Ventilation (Ventilateurs 4-pins)

Seuls les fils **PWM** des ventilateurs sont commandés par le Raspberry Pi.

| Ventilateur | Signal | GPIO |
|------------|--------|------|
| Ventilateur droit | PWM | GPIO23 |
| Ventilateur gauche | PWM | GPIO25 |
| Ventilateur central | PWM | GPIO26 |

#### ⚠️ Résistance série PWM (IMPORTANT)
- Une **résistance en série** est insérée entre le **fil PWM du ventilateur** et la **masse (GND)**
- Valeur utilisée actuellement : **220 Ω**
- Cette résistance permet :
  - d’éviter les comportements instables
  - d’empêcher les ventilateurs de passer en pleine vitesse à l’arrêt de l’interface
  - d’améliorer la stabilité du signal PWM

---

## 🗂️ Structure du dépôt
extruder_version3/
├─ Bib/ # Bibliothèques et drivers (HR8825, PID autotune, etc.)
├─ modules/ # Logique principale (chauffage, moteur, ventilation)
├─ pages/ # Pages de l’interface graphique
├─ main_multiprocessing_ventilation.py
├─ parameters.json
├─ pid_params.txt
├─ requirements.txt
└─ .gitignore

---

## 🛠️ Installation (Raspberry Pi)

Cloner le dépôt :
```bash
git clone git@github.com:MedMounibJemai/extruder_version3-heating-extrusion-aircooling-.git
cd extruder_version3

---

## 🛠️ Création et activation de l'environnement virtuel 
python3 -m venv venv
source venv/bin/activate

---

## Installation des dépendances du projet 
pip install --upgrade pip
pip install -r requirements.txt

---

## Lancement de l'application 
python main_multiprocessing_ventilation.py
