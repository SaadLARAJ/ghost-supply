# Sources de Données et Acquisition

## Vue d'ensemble

Ghost Supply utilise une combinaison de données géospatiales publiques et de données de menace synthétiques pour démontrer les capacités d'optimisation tactique de routes.

---

## 1. Modèle Numérique de Terrain (MNT)

### Source : NASA SRTM (Shuttle Radar Topography Mission)

**Description** : Données d'élévation mondiales avec une résolution de 30 mètres.

**Couverture** : Région de Pokrovsk, Donbass, Ukraine
- Latitude : 48.1°N à 48.5°N
- Longitude : 37.0°E à 37.5°E

### Acquisition

```python
# Option 1 : Téléchargement manuel
# Visiter : https://earthexplorer.usgs.gov/
# Rechercher : Pokrovsk, Ukraine
# Dataset : SRTM 1 Arc-Second Global
# Télécharger les tuiles : N48E037, N48E038

# Option 2 : Automatisé (nécessite un compte USGS)
from elevation import clip

bounds = (37.0, 48.1, 37.5, 48.5)  # O, S, E, N
output = 'data/dem/pokrovsk_srtm.tif'

clip(bounds=bounds, output=output, product='SRTM3')
```

### Format de Fichier
- **Format** : GeoTIFF
- **Projection** : WGS84 (EPSG:4326)
- **Datum Vertical** : EGM96
- **Résolution** : ~30m à l'équateur

---

## 2. Réseau Routier

### Source : OpenStreetMap (OSM)

**Description** : Réseau routier mondial collaboratif.

**Licence** : ODbL (Open Database License)

### Acquisition

```python
import osmnx as ox

# Définir la zone
north, south = 48.5, 48.1
east, west = 37.5, 37.0

# Télécharger le réseau routier
G = ox.graph_from_bbox(
    north, south, east, west,
    network_type='drive',
    simplify=True
)

# Sauvegarder pour usage hors ligne
ox.save_graphml(G, 'data/osm/pokrovsk_roads.graphml')
```

### Classification des Routes

Tags OSM mappés vers des catégories tactiques :

| Tag OSM | Type Ghost Supply | Vitesse Base | Risque Visibilité |
|---------|-------------------|--------------|-------------------|
| motorway, trunk, primary | primaire | 60 km/h | Élevé |
| secondary | secondaire | 40 km/h | Moyen |
| tertiary, unclassified | tertiaire | 35 km/h | Moyen |
| track, service | piste | 30 km/h | Faible |
| path, footway | sentier | 20 km/h | Très Faible |

---

## 3. Données de Menace (Synthétiques)

**Note** : Pour ce projet de portfolio, les données de menace sont **générées synthétiquement** pour préserver l'OPSEC et démontrer la méthodologie.

### Méthode de Génération

```python
from ghost_supply.perception.threat_model import ThreatPredictor

predictor = ThreatPredictor()

# Générer 6 mois de données d'incidents
incidents = predictor.generate_synthetic_incidents(
    num_incidents=500,
    days_history=180,
    seed=42  # Reproductible
)
```

### Attributs des Incidents

| Champ | Type | Description |
|-------|------|-------------|
| timestamp | datetime | Heure de l'incident |
| type | string | frappe_drone, artillerie, embuscade, mine, sniper |
| latitude | float | Latitude |
| longitude | float | Longitude |
| casualties | int | Nombre de victimes (0-5) |

### Patterns Réalistes Modélisés

1. **Temporel** :
   - Ratio Jour/Nuit : 3:1 (plus dangereux le jour)
   - Heures de pointe : 6h-8h (matin), 16h-18h (soir)
   - Variation hebdomadaire : Plus calme le week-end

2. **Spatial** :
   - Concentration près des routes principales (50% des incidents)
   - Concentration sur la ligne de front (30%)
   - Bruit de fond aléatoire (20%)

3. **Corrélation Météo** :
   - 50% de réduction sous la pluie
   - 70% de réduction dans le brouillard
   - Ciel dégagé = activité maximale

---

## 4. Données Météo

### Implémentation Actuelle : Scénarios Prédéfinis

```python
WEATHER_CONDITIONS = [
    "clear",      # Dégagé
    "fog",        # Brouillard
    "rain",       # Pluie
    "snow",       # Neige
    "rasputitsa"  # Saison des boues
]
```

---

## 5. Couverture Radio (RF)

### Méthode : Modèle Computationnel

La couverture RF est **calculée** en utilisant le terrain et la physique de propagation, pas des données préexistantes.

**Positions Stations** : Dépôts définis par l'utilisateur ou auto-sélectionnés.

**Modèle** : Longley-Rice ITM Simplifié
- Perte en espace libre
- Diffraction sur les crêtes (Knife-edge)
- Facteur d'irrégularité du terrain

**Sortie** : Heatmap 2D de la puissance du signal reçu (dBm).

---

## 6. Emplacements des Dépôts (Synthétiques)

Générés algorithmiquement basés sur :

```python
from ghost_supply.decision.facility_location import generate_candidate_depots

candidates = generate_candidate_depots(
    bounds=STUDY_AREA_BOUNDS,
    frontline_lat=48.3,
    num_candidates=20
)
```

### Types d'Installations Simulées

- Bunkers souterrains (haute protection, faible accessibilité)
- Entrepôts (protection moyenne, haute accessibilité)
- Usines (moyen/moyen)
- Grottes (haute protection, très faible accessibilité)
- Parkings (faible protection, très haute accessibilité)

---

## 7. Positions de la Ligne de Front

**Source** : Approximation basée sur des cartes publiques (ISW, LiveUAMap).

**Méthode** : Placement manuel ou extraction automatisée.

```python
frontline_positions = [
    (48.32, 37.28),  # Position A
    (48.31, 37.25),  # Position B
    (48.29, 37.31),  # Position C
]
```

---

## 8. Structure de Stockage des Données

```
data/
├── dem/
│   └── pokrovsk_srtm.tif          (50 MB)
│
├── osm/
│   └── pokrovsk_roads.graphml     (5 MB)
│
├── scenarios/
│   ├── pokrovsk_winter.json       (1 KB)
│   ├── pokrovsk_mud_season.json   (1 KB)
│   └── pokrovsk_night_op.json     (1 KB)
│
└── synthetic/
    └── incidents.csv               (100 KB)
```

**Taille Totale** : ~60 MB

---

## 9. Licences et Éthique

### Licences

- **SRTM DEM** : Domaine Public (NASA)
- **OpenStreetMap** : ODbL (Open Database License)
- **Données Synthétiques** : MIT (générées par ce projet)

### Considérations Éthiques

1. **Pas de Données Opérationnelles** : Toutes les coordonnées réelles sont des approximations.
2. **OPSEC Préservée** : Aucune position ou plan militaire réel.
3. **But Éducatif** : Démontre une méthodologie, pas pour usage opérationnel direct.
4. **Menaces Synthétiques** : Les données générées empêchent toute fuite de renseignement.

---

**Version du Document** : 2.0
**Dernière Mise à Jour** : 03/12/2025
**Contact** : Saad LARAJ
