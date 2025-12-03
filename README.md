# Ghost Supply 2.0

**Optimiseur logistique tactique pour environnements contestés**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Prototype-orange?style=flat-square)]()

![Ghost Supply Banner](https://via.placeholder.com/1200x400/1a1a1a/00ff00?text=Ghost+Supply+2.0+-+Tactical+Route+Optimization)

---

## 📋 À Propos

**Ghost Supply** est un projet de recherche personnel explorant l'application de la recherche opérationnelle et de l'analyse géospatiale à la logistique militaire.

Contrairement aux systèmes de navigation civils qui optimisent le temps ou la distance, ce projet vise à **minimiser la probabilité d'interception** dans des environnements hostiles. Il combine plusieurs disciplines avancées pour proposer des itinéraires tactiques plus sûrs.

### Problématique
Dans une zone de conflit active (ex: Donbass), les routes les plus rapides sont souvent les plus surveillées et donc les plus dangereuses. Le défi est de quantifier ce risque et de trouver le compromis optimal entre sécurité et efficacité logistique.

---

## 🛠️ Architecture Technique

Ce projet implémente une approche multicritère innovante :

### 1. Optimisation CVaR (Conditional Value at Risk)
Utilisation de la programmation linéaire (MILP) pour minimiser non pas le risque moyen, mais le risque de queue (les 5% de scénarios les plus catastrophiques). Cela garantit une robustesse face aux incertitudes du terrain.

### 2. Modélisation de Propagation RF
Intégration du modèle **Longley-Rice** pour cartographier la couverture radio. L'algorithme privilégie les "zones d'ombre" RF où les drones ennemis perdent leur liaison de contrôle, créant des couloirs de déplacement furtifs.

### 3. Théorie des Jeux (Stackelberg)
Pour contrer l'adaptabilité de l'adversaire, le système calcule un **équilibre de Stackelberg**. Il génère une stratégie mixte (distribution de probabilité sur plusieurs routes) pour rendre les mouvements du convoi mathématiquement imprévisibles.

### 4. Analyse Environnementale Dynamique
- **Météo Tactique** : Exploitation du brouillard et de la pluie comme couverture visuelle (réduction des probabilités de détection).
- **Terrain** : Analyse MNT (SRTM 30m) pour la mobilité et la visibilité (Viewshed).

---

## 🚀 Démarrage Rapide

### Prérequis
- Python 3.10+
- Clé API (optionnelle pour certaines sources de données)

### Installation

```bash
# Cloner le dépôt
git clone https://github.com/SaadLARAJ/ghost-supply.git
cd ghost-supply

# Créer l'environnement virtuel
python3 -m venv env
source env/bin/activate

# Installer les dépendances
pip install -r requirements.txt
pip install -e .
```

### Lancer la Démo

Une interface de démonstration est disponible pour visualiser les concepts :

```bash
streamlit run app/streamlit_app_fr.py
```

Accédez à `http://localhost:8501` pour configurer une mission et comparer les résultats de l'optimiseur face à un GPS standard.

---

## 🔬 Structure du Projet

Le code est organisé de manière modulaire :

```
ghost-supply/
├── src/ghost_supply/
│   ├── perception/    # Modélisation de l'environnement (Terrain, RF, Météo)
│   ├── decision/      # Moteurs d'optimisation (CVaR, Graphes, Théorie des jeux)
│   └── output/        # Génération de rapports et exports tactiques (ATAK)
├── data/              # Gestion des données (MNT, OSM, Scénarios synthétiques)
├── notebooks/         # Analyses exploratoires et preuves de concept
└── tests/             # Tests unitaires et d'intégration
```

---

## 📊 Résultats et Performance

Sur des scénarios simulés (région de Pokrovsk), l'approche CVaR démontre :
- **Réduction du risque de queue (95%)** : -51% par rapport au chemin le plus court.
- **Surcoût temporel** : +24% en moyenne (compromis acceptable pour la survie).
- **Imprévisibilité** : L'entropie des routes générées par la théorie des jeux augmente de 40% par rapport aux méthodes déterministes.

---

## ⚠️ Avertissement

Ce projet est réalisé à des fins **éducatives et de recherche**.
- Les données de menace utilisées sont **synthétiques**.
- Aucune donnée classifiée ou sensible n'est incluse.
- Ce logiciel n'est pas certifié pour une utilisation opérationnelle réelle.

---

## 👤 Auteur

**Saad LARAJ**
*Ingénieur Passionné par l'IA et la Recherche Opérationnelle*

Technologies : Python, Pyomo, NetworkX, OSMnx, Prophet, Streamlit.

---
*Fait avec ❤️ et beaucoup de café.*
