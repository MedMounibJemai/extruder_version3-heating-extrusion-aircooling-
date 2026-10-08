# Extruder GUI (Raspberry Pi 5 – 7" Touchscreen)

Interface graphique Python pour piloter une mini-extrudeuse basée sur **Raspberry Pi 5** avec **écran tactile 7 pouces**.  
L’application est structurée autour de **trois sous-systèmes principaux** : chauffage, extrusion et ventilation.

---

## 🧩 Présentation du projet

L’interface graphique permet :
1. **Le contrôle thermique** d’une cartouche chauffante à l’aide d’un thermocouple type K et d’un module **MAX6675**, avec une logique **PID + autotune**  
2. **Le contrôle de la vitesse (RPM)** du moteur d’extrusion :
   - **Configuration initiale :** moteur NEMA17 piloté par un driver HR8825 (Stepper Motor HAT B) ou DRV8825 (Stepper Motor Expansion Board).
   - **Nouvelle configuration :** moteur NEMA23 avec réducteur (gearbox), piloté par un driver DM860T ou DM542T.  
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
- Moteur pas à pas NEMA17 (configuration initiale)
- Stepper Motor HAT B (driver HR8825) ou DRV8825 avec Stepper Motor Expansion Board (configuration initiale)
- Moteur pas à pas NEMA23 avec réducteur (gearbox) de 1,2 N·m (nouvelle configuration)
- Driver DM860T ou DM542T pour le pilotage du NEMA23
- 3 ventilateurs 4-pins (PWM)

## ⚠️  Les alimentations de puissance (chauffage, moteur, ventilateurs) doivent être séparées de l’alimentation logique du Raspberry Pi, avec une **masse commune**.

 - La cartouche chauffante est alimentée par une **alimentation dédiée 24 V**  
 - Le moteur d’extrusion est alimenté par une alimentation dédiée selon la configuration :
    - **NEMA17 (configuration initiale) :** alimentation 12 V.
    - **NEMA23 avec gearbox (nouvelle configuration) :** alimentation 24 V – 8,8 A, connectée au driver DM860T ou DM542T. 
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
### ⚙️ Partie Moteur d’Extrusion (NEMA23 avec gearbox – DM860T ou DM542T)

La nouvelle configuration du système d’extrusion utilise un moteur pas à pas **NEMA23 avec réducteur (gearbox) de 1,2 N·m**, en remplacement du NEMA17.

Le moteur NEMA23 est piloté par un driver externe **DM860T ou DM542T**, alimenté par une alimentation dédiée de **24 V – 8,8 A**.

Les deux drivers utilisent la même distribution des broches GPIO du Raspberry Pi 5. Cependant, les configurations du courant et du microstepping diffèrent selon le driver utilisé.

#### Distribution des broches GPIO (mode BCM)

| Signal du driver | GPIO Raspberry Pi |
|------------------|-------------------|
| PUL+ | GPIO16 |
| DIR+ | GPIO22 |
| PUL- | GND |
| DIR- | GND |

- **PUL (Pulse) :** signal de commande des pas du moteur.
- **DIR (Direction) :** signal permettant de définir le sens de rotation.
- **ENA (Enable) :** non utilisé dans cette configuration.

> ⚠️ Les GPIO du Raspberry Pi 5 fonctionnent en 3,3 V. La compatibilité électrique des entrées PUL et DIR doit être vérifiée pour chaque driver. Un circuit d'adaptation peut être nécessaire. Les bornes GND indiquées correspondent à la référence des signaux de commande et non à l'alimentation de puissance du driver.

#### Configuration du courant et du microstepping

Le courant du moteur et la résolution du microstepping sont configurés matériellement à l’aide des interrupteurs DIP situés sur le driver.

Les réglages sont spécifiques au modèle utilisé :

- **DM860T :** configuration du courant et du microstepping selon les tableaux du fabricant.
- **DM542T :** configuration du courant et du microstepping selon les tableaux du fabricant.

> ⚠️ Le courant doit être réglé en fonction des caractéristiques électriques du NEMA23. Le microstepping sélectionné doit également correspondre au paramétrage utilisé dans le programme Python.

##### Driver DM860T

Le driver DM860T permet de configurer le courant du moteur à l'aide des interrupteurs SW1 à SW4 et le microstepping
à l'aide des interrupteurs SW5 à SW8.

**Configuration du courant :**

| Courant Peak (A) | Courant RMS (A) | SW1 | SW2 | SW3 |
|------------------|----------------|-----|-----|-----|
| 2.40 | 2.00 | ON | ON | ON |
| 3.08 | 2.57 | OFF | ON | ON |
| 3.77 | 3.14 | ON | OFF | ON |
| 4.45 | 3.71 | OFF | OFF | ON |
| 5.14 | 4.28 | ON | ON | OFF |
| 5.83 | 4.86 | OFF | ON | OFF |
| 6.52 | 5.43 | ON | OFF | OFF |
| 7.20 | 6.00 | OFF | OFF | OFF |

- SW4 : OFF = Half Current / ON = Full Current.

**Configuration du microstepping :**

| Pulse/rev | SW5 | SW6 | SW7 | SW8 |
|-----------|-----|-----|-----|-----|
| 400 | ON | ON | ON | ON |
| 800 | OFF | ON | ON | ON |
| 1600 | ON | OFF | ON | ON |
| 3200 | OFF | OFF | ON | ON |
| 6400 | ON | ON | OFF | ON |
| 12800 | OFF | ON | OFF | ON |
| 25600 | ON | OFF | OFF | ON |
| 51200 | OFF | OFF | OFF | ON |
| 1000 | ON | ON | ON | OFF |
| 2000 | OFF | ON | ON | OFF |
| 4000 | ON | OFF | ON | OFF |
| 5000 | OFF | OFF | ON | OFF |
| 8000 | ON | ON | OFF | OFF |
| 10000 | OFF | ON | OFF | OFF |
| 20000 | ON | OFF | OFF | OFF |
| 40000 | OFF | OFF | OFF | OFF |

- SW9 : mode de commande (CW/CCW ou PUL/DIR).
- SW10 : lissage du signal (ON = 12 ms / OFF = désactivé).

> ⚠️ Le DM860T nécessite une alimentation de 24 à 110 V DC.

##### Driver DM542T

Le driver DM542T permet de configurer le courant du moteur à l'aide des interrupteurs SW1 à SW4 et le microstepping
à l'aide des interrupteurs SW5 à SW8.

**Configuration du courant :**

| Courant Peak (A) | Courant RMS (A) | SW1 | SW2 | SW3 |
|------------------|----------------|-----|-----|-----|
| 1.00 | 0.71 | ON | ON | ON |
| 1.46 | 1.04 | OFF | ON | ON |
| 1.91 | 1.36 | ON | OFF | ON |
| 2.37 | 1.69 | OFF | OFF | ON |
| 2.84 | 2.03 | ON | ON | OFF |
| 3.31 | 2.36 | OFF | ON | OFF |
| 3.76 | 2.69 | ON | OFF | OFF |
| 4.50 | 3.20 | OFF | OFF | OFF |

- SW4 : OFF = Half Current / ON = Full Current.

**Configuration du microstepping :**

| Pulse/rev | SW5 | SW6 | SW7 | SW8 |
|-----------|-----|-----|-----|-----|
| 200 | ON | ON | ON | ON |
| 400 | OFF | ON | ON | ON |
| 800 | ON | OFF | ON | ON |
| 1600 | OFF | OFF | ON | ON |
| 3200 | ON | ON | OFF | ON |
| 6400 | OFF | ON | OFF | ON |
| 12800 | ON | OFF | OFF | ON |
| 25600 | OFF | OFF | OFF | ON |
| 1000 | ON | ON | ON | OFF |
| 2000 | OFF | ON | ON | OFF |
| 4000 | ON | OFF | ON | OFF |
| 5000 | OFF | OFF | ON | OFF |
| 8000 | ON | ON | OFF | OFF |
| 10000 | OFF | ON | OFF | OFF |
| 20000 | ON | OFF | OFF | OFF |
| 25000 | OFF | OFF | OFF | OFF |

> ⚠️ Le DM542T nécessite une alimentation de 18 à 50 V DC.

---
### 🌬️ Partie Ventilation (Ventilateurs 4-pins)

Seuls les fils **PWM** des ventilateurs sont commandés par le Raspberry Pi.

| Ventilateur | Signal | GPIO |
|------------|--------|------|
| Ventilateur droit | PWM | GPIO23 |
| Ventilateur gauche | PWM | GPIO25 |
| Ventilateur central | PWM | GPIO26 |

#### ⚠️ Résistance série PWM (IMPORTANT)
- Une **résistance de pull-down de 220 Ω** est connectée entre le **signal PWM du ventilateur** et la **masse (GND)**.
- Valeur utilisée actuellement : **220 Ω**
- Cette résistance permet :
  - d’éviter les comportements instables
  - d’empêcher les ventilateurs de passer en pleine vitesse à l’arrêt de l’interface
  - d’améliorer la stabilité du signal PWM

  ---
## 🔥 Paramètres PID des configurations testées

Les paramètres PID présentés ci-dessous correspondent aux trois configurations successives du système de chauffage
de la mini-extrudeuse.

Chaque version se distingue par la géométrie du barillet, de la vis d'extrusion et du corps de chauffe.

Les coefficients Kp, Ki et Kd sont enregistrés dans le fichier `pid_params.txt` et utilisés pour la régulation
de température.

### Version 1 — Configuration initiale

- Barillet : diamètre 12 mm
- Vis d'extrusion : diamètre 8 mm
- Corps de chauffe : modèle utilisé sur la Prusa MK3S
- Orientation de la cartouche chauffante : perpendiculaire  à l'axe du barillet
- Méthode de réglage : Ziegler-Nichols

| Kp | Ki | Kd |
|----|----|----|
| 0.6585727345838824 | 0.00577401577784015 | 18.778873466272856 |

### Version 2 — Corps de chauffe cubique

- Barillet : diamètre 25 mm
- Vis d'extrusion : diamètre 8 mm, sans compression
- Corps de chauffe : bloc cubique avec passage de
  diamètre 25 mm pour le barillet
- Orientation de la cartouche chauffante : perpendiculaire  à l'axe du barillet
- Méthode de réglage : Ziegler-Nichols

| Kp | Ki | Kd |
|----|----|----|
| 1.5670653787021611 | 0.006329719658947739 | 12.12382831232284625 |

### Version 3 — Configuration actuelle

- Barillet : diamètre 16 mm
- Vis d'extrusion : diamètre 12 mm
- Corps de chauffe : bloc cylindrique
- Orientation de la cartouche chauffante : parallèle  à l'axe du barillet
- Méthode de réglage : Tyreus-Luyben

| Kp | Ki | Kd |
|----|----|----|
| 3.3071184940143015 | 0.015685893337840328 | 50.30683836938976 |

> ⚠️ Ces paramètres PID sont propres aux configurations
> thermiques testées. Toute modification du corps de chauffe,
> du barillet, de la cartouche chauffante ou du système de
> mesure peut nécessiter un nouveau réglage du PID.

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
```
