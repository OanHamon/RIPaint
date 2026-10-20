# Bataille de cubes 8-bit — générateur de vidéos TikTok

Génère des vidéos verticales « satisfaisantes » prêtes à publier : 2 à 4 cubes colorés peignent
une arène en rebondissant, ramassent des objets (Fusil, Gros pinceau, Potion, Sablier), et la
couleur qui couvre le plus de surface gagne.

- 1080x1920, 60 fps, MP4 H.264 + AAC, rendu pixel-perfect (135x240 agrandi x8 sans lissage)
- Tout est généré par le code : graphismes, police pixel, bruitages et musique chiptune (aucun droit d'auteur tiers)
- Chaque vidéo correspond à une **seed** inscrite dans son nom : la même seed avec les mêmes réglages redonne exactement la même partie

## Installation (Windows)

1. Installer **Python 3.10 ou plus récent** depuis https://www.python.org/downloads/
   en cochant **« Add python.exe to PATH »** pendant l'installation.
2. Double-cliquer sur **`Lancer.bat`**.
   Au premier lancement, il installe automatiquement les dépendances (pygame, numpy, imageio-ffmpeg,
   qui fournit ffmpeg). Le panneau de contrôle s'ouvre ensuite.

Installation manuelle équivalente :

```bash
python -m pip install -r requirements.txt
```

## Utilisation

### Panneau de contrôle (`Lancer.bat` ou `python main.py`)

| Réglage | Effet |
|---|---|
| Probabilité des objets | Un curseur par objet ; le pourcentage **réel** après normalisation est affiché. À 0 : l'objet n'apparaît jamais. |
| Intervalle | Temps entre deux apparitions d'objets (5 s par défaut). |
| Objets max en même temps / Sabliers max | Limites (3 / 3 par défaut). |
| Volume général / musique | Volume final de la vidéo et niveau de la musique de fond. |
| Nombre de vidéos (X) | « Générer » crée X parties différentes = X vidéos. |
| Seed (optionnelle) | Si remplie, l'aperçu et la génération utilisent cette seed (puis seed+1, seed+2… pour plusieurs vidéos). |
| Sous-titres .srt | Exporte aussi un fichier .srt à côté de chaque vidéo. |
| Aperçu | Lance une partie en temps réel avec le son, sans enregistrer. |
| Ouvrir le dossier des vidéos | Ouvre `videos/`. |
| Réglages avancés… | Ouvre `config.json` (phrases d'accroche, zones de sécurité, durées, vitesses…). |

Les réglages sont enregistrés automatiquement dans `config.json`.

**Touches de l'aperçu :** `ESPACE` pause · `R` nouvelle partie · `S` affiche les zones de sécurité TikTok · `ÉCHAP` quitter.

### Ligne de commande

```bash
python main.py --generate 5
```

```bash
python main.py --generate 1 --seed 1234
```

```bash
python main.py --preview --seed 1234
```

Les vidéos sont enregistrées dans `videos/combat_<seed>_<date-heure>.mp4`
(+ `.srt` si l'option est cochée). Pour refaire une partie qui vous a plu, reprenez la seed du nom
de fichier. Les réglages utilisés sont aussi inscrits dans les métadonnées du MP4.

Durée d'une vidéo : 5 s d'intro + 50 s de bataille + 3 s par sablier ramassé + 5 s de fin
(entre 60 et 69 s avec les réglages par défaut). Une vidéo se génère en 15 à 30 s environ.

## Réglages avancés (`config.json`)

| Clé | Défaut | Rôle |
|---|---|---|
| `hooks` | 7 phrases | Phrases d'accroche tirées au hasard pendant l'intro |
| `safe_top` / `safe_bottom` / `safe_right` | 130 / 400 / 140 | Zones de sécurité TikTok en pixels de la vidéo finale |
| `intro_duration` / `battle_duration` / `outro_duration` | 5 / 50 / 5 | Durées en secondes |
| `hourglass_bonus` | 3 | Secondes ajoutées par sablier |
| `aim_duration` | 0.3 | Durée de la ligne de visée du fusil |
| `stun_duration` / `slow_duration` / `potion_duration` | 5 / 3 / 5 | Durées des effets |
| `cube_speed` / `bullet_speed` | 42 / 110 | Vitesses en pixels logiques par seconde |
| `brush_radius` | 20 | Rayon du coup de gros pinceau |
| `paint_sound` | false | Léger souffle continu pendant la peinture |
| `music_enabled` | true | Musique de fond |
| `crf` / `x264_preset` | 18 / medium | Qualité d'encodage (plus petit = meilleure qualité) |
| `output_dir` | videos | Dossier de sortie |

## Vérifier les vidéos

```bash
python tools/verify_video.py videos/*.mp4
```

Contrôle la résolution, les 60 fps, les codecs, la durée attendue (en re-simulant la partie), la
synchro audio/vidéo (bip du « GO » contre l'image du « GO »), l'absence de saturation, le rendu
pixel-perfect et que les vidéos sont bien différentes.

Tests automatiques :

```bash
python -m pytest tests
```

## Architecture

```
main.py               point d'entrée (panneau / --generate / --preview)
engine8bit/           MOTEUR RÉUTILISABLE : surface logique, palette NES, police pixel, sprites ASCII, zones de sécurité
audio/                SYNTHÉ RÉUTILISABLE : oscillateurs + ADSR, bruitages, musique procédurale, mixage
game/                 LE CONCEPT : réglages, scénario (seed), physique, objets, simulation, dessin
output/               export MP4 via ffmpeg, sous-titres .srt, aperçu temps réel
ui/control_panel.py   panneau tkinter
tools/verify_video.py vérification des vidéos produites
tests/                tests automatiques (pytest)
```

La simulation (`game/battle.py`) est indépendante du rendu et du son : elle avance à pas fixe de
1/60 s et produit un état + des événements sonores horodatés. L'export assemble l'audio au sample
près à partir de ces événements, d'où une synchronisation exacte. Pour un nouveau concept
(ex. simulation de créature), on réutilise `engine8bit/`, `audio/` et `output/`, et on remplace `game/`.
