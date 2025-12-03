# 👻 Ghost Supply 2.0

**Optimiseur logistique tactique pour environnements contestés - Minimise le risque d'interception en utilisant l'optimisation CVaR, la modélisation RF et la théorie des jeux.**

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

![Ghost Supply Banner](https://via.placeholder.com/800x200/1a1a1a/00ff00?text=Ghost+Supply+2.0+-+Optimiseur+de+Routes+Tactiques)

---

## 🎯 Pourquoi ce projet ?

Les GPS classiques optimisent la **distance** ou le **temps**. Mais dans des zones de conflit comme le Donbass, ce qui compte c'est la **probabilité de survie**.

J'ai créé **Ghost Supply** pour répondre à une question simple mais critique : *Comment acheminer des provisions au front tout en minimisant le risque d'interception ?*

### Le défi technique

- Les convois sont vulnérables aux drones et à l'artillerie.
- Les routes principales sont les plus rapides, mais aussi les plus surveillées.
- La météo et le terrain offrent des couvertures naturelles qu'un GPS standard ignore.

### Ma Solution

J'ai développé un système qui ne cherche pas la route la plus rapide, mais la plus sûre, en utilisant :

1.  **CVaR (Conditional Value at Risk)** : Pour minimiser le pire scénario possible, pas juste le risque moyen.
2.  **Modélisation RF** : Pour identifier les zones d'ombre radio (invisibles aux radars ennemis).
3.  **Théorie des Jeux** : Pour randomiser les itinéraires et rester imprévisible face à l'ennemi.
4.  **Météo Tactique** : Pour exploiter le brouillard ou la pluie comme couverture visuelle.

---

## ✨ Ce que j'ai implémenté

### 🧮 **Optimisation CVaR**
J'ai choisi d'utiliser la CVaR (Conditional Value at Risk) plutôt que l'espérance classique. Cela permet de se concentrer sur les 5% des scénarios les plus catastrophiques. Concrètement, ça évite les routes qui semblent sûres "en moyenne" mais qui passent par un goulot d'étranglement mortel.

### 📡 **Propagation Radio (Longley-Rice)**
J'ai intégré un modèle simplifié de propagation des ondes (Longley-Rice) pour mapper la couverture radio. L'idée est d'identifier les zones où les drones ennemis perdent le signal, offrant ainsi un couloir de sécurité naturel.

### 🎲 **Stratégie Mixte (Théorie des Jeux)**
Pour éviter qu'un itinéraire ne devienne prévisible à force d'être utilisé, j'utilise l'équilibre de Stackelberg. Le système génère plusieurs routes viables et propose une distribution de probabilité. Chaque mission est unique.

### 📱 **Export ATAK**
Le but étant que ce soit utilisable, j'ai ajouté un export au format CoT (Cursor on Target) compatible avec ATAK, l'outil de cartographie standard utilisé sur le terrain.

---

## 🚀 Comment tester le projet

### Installation

```bash
# Cloner mon repo
git clone https://github.com/votre-username/ghost-supply.git
cd ghost-supply

# Créer un environnement virtuel
python3 -m venv env
source env/bin/activate

# Installer les dépendances
pip install -r requirements.txt
pip install -e .
```

*Note : J'ai mis `richdem` en commentaire dans les requirements car il demande une compilation C++ parfois capricieuse. J'ai codé un fallback avec numpy qui fait le job si vous n'arrivez pas à l'installer.*

### Lancer la démo

J'ai créé une interface avec Streamlit pour visualiser les résultats :

```bash
streamlit run app/streamlit_app_fr.py
```

Allez sur `http://localhost:8501`. Vous pourrez :
1.  Choisir un point de départ et une destination.
2.  Définir la météo et le type de cargaison.
3.  Lancer l'optimisation et voir la différence entre la route "GPS" et la route "Tactique".

---

## 📁 Organisation du code

```
ghost-supply/
├── src/ghost_supply/
│   ├── perception/           # Analyse de l'environnement (Terrain, RF, Météo)
│   ├── decision/             # Algorithmes d'optimisation (CVaR, Graphes, Théorie des jeux)
│   └── output/               # Génération des cartes et exports ATAK
├── app/                      # Interface Streamlit
├── data/                     # Données (MNT, OSM, Scénarios)
└── tests/                    # Tests unitaires
```

---

## 🔬 Un peu de technique

### L'algo d'optimisation

Le cœur du réacteur est un **Programme Linéaire en Nombres Entiers Mixtes (MILP)** résolu avec Pyomo.
L'objectif est de minimiser : `w_temps * T + w_risque * CVaR_α(Risque)`

### Les données

- **Terrain** : J'utilise les données SRTM de la NASA (30m de précision).
- **Routes** : OpenStreetMap via la librairie OSMnx.
- **Menaces** : Pour la démo, je génère des données synthétiques avec Prophet pour simuler des patterns d'activité ennemie réalistes.

---

## ⚠️ Disclaimer

Ce projet est un **projet personnel de recherche**. Les scénarios et les données de menace sont simulés. Il n'y a aucune donnée classifiée ou sensible dans ce dépôt. C'est une démonstration technique de l'application de la recherche opérationnelle à la logistique.

---

**Auteur** : Saad LARAJ
**Stack** : Python, OSMnx, Pyomo, Prophet, Streamlit.
