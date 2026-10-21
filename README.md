# Bataille de cubes 8-bit — générateur de vidéos TikTok

Génère des vidéos verticales « satisfaisantes » prêtes à publier : 2 à 4 cubes colorés peignent
une arène en rebondissant, ramassent des objets, et la couleur qui couvre le plus de surface gagne.

| Objet | Effet |
|---|---|
| Fusil | Tire une balle de peinture sur l'adversaire le plus proche : touché, il est assommé 5 s |
| Gros pinceau | Coup circulaire qui peint une large zone et repousse/ralentit les cubes touchés |
| Potion | Le cube grandit (x2) pendant 5 s |
| Sablier | +3 s au chrono (3 max par partie) |
| Bombe | Posée au sol, clignote 1,5 s puis explose : grosse éclaboussure, cubes proches projetés, écran qui tremble |
| Rouleau | Pendant 5 s, la traînée du cube devient presque 3 fois plus large |
| Seau arc-en-ciel | Une vague de peinture traverse toute l'arène, dans la direction où elle recouvre le plus de peinture adverse |
| Glace | Gèle tous les adversaires 2 s |
| Aimant | Attire tous les objets vers le cube pendant 4 s |
| Bottes | Le cube va 1,8 fois plus vite pendant 5 s (traînée de fantômes) |
| Cœur | +1 vie au cube qui le ramasse (jusqu'à 2 vies de plus qu'au départ) ; n'apparaît pas si les vies sont désactivées |

**Modes de jeu** (réglage « Mode ») : un mode impose ses probabilités d'objets, l'accélération des cubes,
le rythme d'apparition des bonus (qui peut s'accélérer jusqu'à la fin du chrono) et parfois une partie plus
longue ; son nom s'affiche dans un bandeau pendant le compte à rebours et figure dans le nom du fichier.
« classique » garde vos réglages, « aléatoire » tire un mode différent pour chaque vidéo (selon la seed).
La règle des vidéos de plus d'1 minute passe avant tout : aucun mode ne raccourcit la vidéo.

| Mode | Objets | Bataille | Vitesse finale | Bonus (GO → fin) | Caractère |
|------|--------|----------|----------------|------------------|-----------|
| *classique* | vos curseurs | 51 s | ×1,8 | 5 s | vos réglages, sans escalade |
| KABOOM | Bombes, fusils, un peu de cœurs | 51 s | ×1,8 | 3 s → 1,5 s | Mèche courte, grosses explosions, final en pluie de bombes |
| GOGO PAINT | Rouleaux, seaux, pinceaux, potions | 51 s | ×1,6 | 2 s → 1,4 s | Vies illimitées : course à la peinture pure |
| BLIZZARD | Glace, fusils, bottes, un peu de cœurs | 55 s | ×1,5 | 3,5 s | Partie lente : la glace fige tout le monde, les fusils achèvent |
| TURBO | Bottes, rouleaux, aimants | 51 s | ×2,3 | 3 s → 1,8 s | Nerveuse, cubes plus rapides dès le départ |
| TITANS | Potions, pinceaux, rouleaux | 60 s | ×1,4 | 4 s | Géants lents, potions de 9 s et grand pinceau |
| LOOT RAIN | Tous | 51 s | ×1,8 | 1,2 s → 1 s | Jusqu'à 8 objets à la fois, aimants en bonus |
| ALL-OUT WAR (Escalade) | Tous | 51 s | ×1,8 | 5 s → 1,4 s | Plus le temps passe, plus c'est la guerre : jusqu'à 6 objets, balles plus rapides, slashs et images d'impact |
| SUDDEN DEATH | Fusils, bombes, pinceaux, seaux | 51 s | ×2 | 3 s → 1,8 s | Une seule vie, même en duel : le premier touché est K.O. (mais sa peinture reste !) |

Le réglage « Rythme final » (APPARITION) fait la même chose en mode classique : ×0,5 = les bonus
tombent deux fois plus souvent à la fin du chrono ; ×1 = rythme constant.

- 1080x1920, 60 fps, MP4 H.264 + AAC, rendu pixel-perfect (135x240 agrandi x8 sans lissage)
- Tout est généré par le code : graphismes, police pixel, bruitages et musique chiptune (aucun droit d'auteur tiers)
- Chaque vidéo correspond à une **seed** inscrite dans son nom : la même seed avec les mêmes réglages redonne exactement la même partie

## Installation (Windows)

1. Installer **Python 3.10 ou plus récent** depuis https://www.python.org/downloads/
   en cochant **« Add python.exe to PATH »** pendant l'installation.
2. Double-cliquer sur **`Lancer.bat`**.
   Au premier lancement, il installe automatiquement les dépendances (pygame, numpy, imageio-ffmpeg,
   qui fournit ffmpeg, et textual pour l'interface). RIPaint s'ouvre ensuite dans le terminal.

Pour le meilleur rendu, utilisez **Windows Terminal** (par défaut sur Windows 11), en plein écran
ou au moins 100 x 30 caractères.

Installation manuelle équivalente :

```bash
python -m pip install -r requirements.txt
```

## Utilisation

Au lancement (`Lancer.bat` ou `python main.py`), RIPaint demande quelle interface ouvrir :
`1` (ou `ENTRÉE`) pour l'**application terminal**, `2` pour le **panneau de contrôle** en fenêtre.
Pour sauter la question : `python main.py --terminal` ou `python main.py --gui`.
Les deux interfaces partagent les mêmes réglages (`config.json`).

### Application terminal (`python main.py --terminal`)

Au lancement, le logo se peint pendant que RIPaint vérifie ses dépendances (pygame, numpy, ffmpeg,
dossier de sortie) ; `ENTRÉE` passe l'animation. On arrive ensuite dans l'atelier : les réglages à
gauche (partie, objets, apparition, son, génération), et à droite une mini-bataille animée, l'avancement de la génération et le journal.

| Touche | Action |
|---|---|
| `↑` `↓` / `TAB` | Changer de ligne |
| `←` `→` | Régler la valeur (`MAJ` + flèche : par 10 ; `DÉBUT` / `FIN` : 0 / 100 sur un curseur) |
| `ESPACE` | Basculer un interrupteur |
| `G` | Générer les vidéos |
| `P` | Aperçu en temps réel avec le son (fenêtre séparée, sans enregistrer) |
| `ÉCHAP` | Annuler la génération en cours |
| `O` | Ouvrir le dossier des vidéos |
| `C` | Ouvrir `config.json` (réglages avancés) |
| `R` | Recharger `config.json` après l'avoir modifié |
| `Q` | Quitter (confirmation si une génération est en cours) |

La souris fonctionne aussi : clic ou glisser sur les curseurs, clic sur `◀` `▶`.

| Réglage | Effet |
|---|---|
| Nombre de joueurs | « Aléatoire (2 à 4) » ou 2, 3, 4 cubes fixes. |
| Taille des cubes | En pixels logiques (13 par défaut ; 5 à 16). Plus gros = plus de chocs et d'interactions. |
| Vies par cube | 3 petits points sous chaque cube (0 = désactivé, jusqu'à 5). Chaque objet adverse qui touche un cube (balle, pinceau, bombe, glace, vague) lui retire une vie, avec 0,75 s d'invulnérabilité ensuite. À 0 : K.O., yeux en croix, il se grise et rapetisse, glisse en ralentissant puis ne peint plus. Les cœurs redonnent une vie. La glace, qui touche tous les adversaires d'un coup, ne peut pas achever un cube. |
| Carte | « Aléatoire (toutes) » : une des 9 cartes dessinées (OPEN, PILLARS, CROSS, TEETH, CORRIDOR, DIAMOND, ZIGZAG, RING, S-WALLS), orientée au hasard ; ou une carte précise ; ou « Obstacles au hasard ». Le nom s'affiche pendant le compte à rebours. |
| Mode de jeu | Classique, aléatoire ou l'un des 8 modes ci-dessus (voir « Modes de jeu »). L'escalade est le mode « Escalade » : plus la partie avance, plus c'est la guerre : un objet toutes les 5 s au début puis toutes les ~1,4 s, jusqu'à 6 objets en même temps, cubes et balles qui accélèrent, et des coups de plus en plus marqués (slashs blancs/noirs, images d'impact façon manga, secousses). Environ 56 % des parties ont au moins un K.O. (25 % sans). |
| Obstacles (mode « au hasard ») | 0 à 4 petits blocs de pierre disposés en miroir (3 par défaut). Les cubes rebondissent dessus, les balles s'y écrasent, la peinture ne les recouvre pas et ils ne comptent pas dans le score. |
| Vitesse à la fin (x) | Les cubes accélèrent progressivement du GO jusqu'à la fin du chrono (1.8 = 80 % plus vite à la fin ; 1.0 = vitesse constante). « SPEED UP! » est annoncé au tiers et aux deux tiers. |
| Probabilité des objets | Un curseur par objet ; le pourcentage **réel** après normalisation est affiché. À 0 : l'objet n'apparaît jamais. |
| Intervalle | Temps entre deux apparitions d'objets (5 s par défaut). |
| Objets max / Sabliers max | Limites (3 / 3 par défaut). |
| Volume général / musique | Volume final de la vidéo et niveau de la musique de fond. |
| Nombre de vidéos | « Générer » crée X parties différentes = X vidéos. |
| Seed (optionnelle) | Si remplie, l'aperçu et la génération utilisent cette seed (puis seed+1, seed+2… pour plusieurs vidéos). |
| Sous-titres .srt | Exporte aussi un fichier de sous-titres .srt (textes + horaires) à côté de chaque vidéo, à importer sur TikTok ou dans un logiciel de montage. |
| Aperçu | Lance une partie en temps réel avec le son, sans enregistrer. |
| Ouvrir le dossier des vidéos | Ouvre `videos/`. |
| Réglages avancés… | Ouvre `config.json` (phrases d'accroche, zones de sécurité, durées, vitesses…). |

Les réglages sont enregistrés automatiquement dans `config.json` ; les clés avancées modifiées à la
main (accroches, durées…) sont conservées.

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

Les vidéos sont enregistrées dans `videos/`, nommées avec la date, la légende TikTok et la seed :
`2026-10-21_10h41m58s - Which cube will win the PaintRace #satisfying #paintrace #whowillwin #minigame #fyp - seed43362402.mp4`
(le « ? » est retiré du nom car Windows l'interdit). À côté : un `.txt` contenant la légende exacte,
à copier-coller au moment de publier (TikTok ne lit pas le nom du fichier), et le `.srt` si l'option
est cochée. La légende et les hashtags se modifient dans le panneau (section Génération).

Déroulé d'une vidéo (réglages par défaut) :

1. **Teaser (0,8 s)** : l'arène telle qu'elle sera à la fin, « WHO WINS? », puis un « rembobinage ».
2. **Compte à rebours 3-2-1** : les cubes trépignent, leur surnom s'affiche (« SHADOW », « FROST »…).
   Animation « abonne-toi » : un avatar-cube avec un badge « + », une main-curseur appuie dessus,
   le « + » devient une coche (« FOLLOW FOR MORE! » → « THANKS! »). Style 8-bit, sans logo TikTok.
3. **Bataille** : allongée automatiquement pour que la vidéo dépasse toujours 1 minute (51,2 s),
   +3 s par sablier. Annonces « X LEADS! » quand un cube prend nettement la tête, ralentis sur les
   K.O. et explosions, pourcentages cachés (« ??% ») pendant les 5 dernières secondes.
4. **Fin (7 s)** : « END! », révélation des scores un par un avec roulement de tambour, écran du
   gagnant (surnom, score, puis classement de la ligue), et retour à l'image d'ouverture : la
   dernière image est identique à la première, la vidéo boucle sans couture.

Durée : 62 s minimum (68 à 71 s avec des sabliers). Une vidéo se génère en 15 à 30 s environ.

### Rémunération TikTok (Creator Rewards Program)

L'option « Toujours plus d'1 minute » garantit la condition de durée (vidéo > 1 minute) et tout
le contenu est original (graphismes, police, musique et sons générés par le code). Les autres
conditions dépendent du compte et pas des vidéos : au moins 10 000 abonnés, 100 000 vues sur
30 jours, 18 ans, compte personnel dans un pays éligible (dont la France). Vérifiez votre
éligibilité dans l'application (Outils pour les créateurs), les règles pouvant évoluer.

### Ligue

Chaque vidéo générée compte comme une journée de ligue : le gagnant marque une victoire et le
classement s'affiche à la fin (« LEAGUE DAY 12 »). Il est stocké dans `league.json` et se remet à
zéro depuis le panneau. L'aperçu ne compte pas.

## Réglages avancés (`config.json`)

| Clé | Défaut | Rôle |
|---|---|---|
| `players` | 0 | Nombre de cubes : 0 = aléatoire (2 à 4), sinon 2, 3 ou 4 |
| `cube_size` | 13 | Taille des cubes en pixels logiques (x2 avec la potion) |
| `lives` | 3 | Vies par cube (0 = illimitées) |
| `max_bonus_lives` | 2 | Vies gagnées avec les cœurs au-delà du départ |
| `duel_lives` | 4 | Vies quand il n'y a que 2 cubes (un K.O. en duel laisse un seul cube repeindre l'arène) |
| `death_shrink` | true | Un cube K.O. se grise et rapetisse |
| `arena_centered` | true | Arène centrée sur l'écran (false = ancienne mise en page, décalée à gauche) |
| `map` | random | `random`, un nom de carte (ex. `CROSS`) ou `generated` (obstacles au hasard) |
| `mode` | classic | `classic`, `random` ou un mode (`kaboom`, `gogopaint`, `blizzard`, `turbo`, `titans`, `lootrain`, `escalation`, `suddendeath`) |
| `item_ramp` | 1.0 | Intervalle des bonus à la fin du chrono (×, 1 = constant) |
| `obstacles` | 3 | Nombre d'obstacles en mode `generated` |
| `speed_ramp` | 1.8 | Multiplicateur de vitesse atteint à la fin du chrono de base |
| `hooks` | 7 phrases | Phrases d'accroche tirées au hasard pendant l'intro |
| `safe_top` / `safe_bottom` / `safe_right` | 130 / 400 / 140 | Zones de sécurité TikTok en pixels de la vidéo finale |
| `intro_duration` / `battle_duration` / `outro_duration` | 3 / 50 / 7 | Durées en secondes (bataille allongée si besoin pour dépasser `min_video_duration`) |
| `tiktok_rewards` / `min_video_duration` | true / 62 | Vidéo toujours plus longue que 1 minute |
| `teaser` | true | Fin montrée en ouverture + boucle sans couture |
| `hide_final_scores` | 5 | Secondes de fin où les % sont cachés (0 = jamais) |
| `comeback` | 0.5 | Probabilité qu'un objet apparaisse près du cube en dernière place |
| `lead_announce` / `slowmo` / `nicknames` / `league` | true | Annonces de leader, ralentis, surnoms, ligue |
| `follow_prompt` | true | Animation « abonne-toi » pendant le compte à rebours (aucun cube ne démarre sous l'encadré) |
| `hourglass_bonus` | 3 | Secondes ajoutées par sablier |
| `aim_duration` | 0.3 | Durée de la ligne de visée du fusil |
| `stun_duration` / `slow_duration` / `potion_duration` | 5 / 3 / 5 | Durées des effets |
| `bomb_fuse` / `bomb_radius` | 1.5 / 18 | Délai et rayon de l'explosion de la bombe |
| `roller_duration` / `roller_width` | 5 / 2.8 | Durée du rouleau et largeur de la traînée (x la taille du cube) |
| `bucket_width` | 1.6 | Épaisseur de la vague du seau (x la taille du cube) |
| `ice_duration` | 2 | Durée du gel |
| `magnet_duration` / `magnet_speed` | 4 / 70 | Durée de l'aimant et vitesse d'attraction des objets |
| `boots_duration` / `boots_factor` | 5 / 1.8 | Durée des bottes et multiplicateur de vitesse |
| `cube_speed` / `bullet_speed` | 54 / 170 | Vitesses en pixels logiques par seconde |
| `brush_radius` | 30 | Rayon du coup de gros pinceau |
| `paint_sound` | false | Léger souffle continu pendant la peinture |
| `music_enabled` | true | Musique de fond |
| `crf` / `x264_preset` | 18 / medium | Qualité d'encodage (plus petit = meilleure qualité) |
| `output_dir` | videos | Dossier de sortie |
| `caption` / `hashtags` | « Which cube will win the PaintRace? » / satisfying, paintrace, whowillwin, minigame, fyp | Légende TikTok (nom des vidéos + fichier .txt) |
| `caption_file` | true | Écrire la légende dans un .txt à côté de chaque vidéo |

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
main.py               point d'entrée (interface / --generate / --preview)
engine8bit/           MOTEUR RÉUTILISABLE : surface logique, palette NES, police pixel, sprites ASCII, zones de sécurité
audio/                SYNTHÉ RÉUTILISABLE : oscillateurs + ADSR, bruitages, musique procédurale, mixage
game/                 LE CONCEPT : réglages, scénario (seed), physique, objets, simulation, dessin
output/               export MP4 via ffmpeg, sous-titres .srt, aperçu temps réel
ui/app.py ...         application terminal (Textual) : démarrage animé, atelier, logo, mini-bataille
ui/control_panel.py   panneau de contrôle tkinter
tools/verify_video.py vérification des vidéos produites
tests/                tests automatiques (pytest)
```

La simulation (`game/battle.py`) est indépendante du rendu et du son : elle avance à pas fixe de
1/60 s et produit un état + des événements sonores horodatés. L'export assemble l'audio au sample
près à partir de ces événements, d'où une synchronisation exacte. Pour un nouveau concept
(ex. simulation de créature), on réutilise `engine8bit/`, `audio/` et `output/`, et on remplace `game/`.
