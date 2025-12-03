"""Traductions françaises pour Ghost Supply."""

FR = {
    # Interface principale
    "title": "👻 Ghost Supply 2.0",
    "subtitle": "Optimiseur Logistique Tactique pour Environnements Contestés",

    # Sidebar
    "mission_config": "⚙️ Configuration de Mission",
    "route_params": "Paramètres de Route",
    "origin_depot": "Dépôt d'Origine",
    "destination": "Destination",
    "cargo_details": "Détails du Chargement",
    "cargo_type": "Type de Cargo",
    "strategic_value": "Valeur Stratégique",
    "conditions": "Conditions",
    "weather": "Météo",
    "departure_hour": "Heure de Départ",
    "cvar_confidence": "Niveau de Confiance CVaR",
    "optimize_button": "🎯 Optimiser la Route",

    # Cargo types
    "munitions": "Munitions",
    "medical": "Médical",
    "fuel": "Carburant",
    "food": "Nourriture",
    "equipment": "Équipement",
    "personnel": "Personnel",

    # Weather
    "clear": "Dégagé",
    "fog": "Brouillard",
    "rain": "Pluie",
    "snow": "Neige",
    "rasputitsa": "Rasputitsa (Boue)",

    # Tabs
    "tactical_map": "📍 Carte Tactique",
    "terrain_3d": "🗻 Terrain 3D",
    "risk_analysis": "📊 Analyse de Risque",
    "comparison": "⚖️ Comparaison",
    "game_theory": "🎲 Théorie des Jeux",

    # Metrics
    "distance": "Distance",
    "duration": "Durée",
    "survival_prob": "Prob. Survie",

    # Units
    "km": "km",
    "min": "min",
    "percent": "%",

    # Buttons
    "download_atak": "📦 Télécharger Package ATAK",
    "download_zip": "⬇️ Télécharger ZIP",
    "generate_briefing": "📄 Générer le Briefing",
    "download_briefing": "⬇️ Télécharger Briefing",
    "generate_pareto": "Générer le Front de Pareto",
    "compute_mixed_strategy": "Calculer la Stratégie Mixte",
    "sample_new_route": "🎲 Nouvelle Route (Aléatoire)",

    # Messages
    "optimizing": "Optimisation de la route tactique...",
    "generating_data": "Génération des données synthétiques...",
    "no_dem": "Aucun MNT trouvé. Génération d'un terrain synthétique...",
    "generating_threats": "Génération des données de menace...",
    "training_model": "Entraînement du modèle Prophet...",
    "building_graph": "Construction du graphe de routage depuis OSM...",
    "computing_pareto": "Calcul des solutions optimales de Pareto...",
    "solving_game": "Résolution du jeu...",
    "generating_package": "Génération du package de mission...",

    # Instructions
    "configure_mission": "👈 Configurez les paramètres de mission et cliquez sur 'Optimiser la Route' pour commencer",

    # About section
    "about_title": "## À Propos de Ghost Supply 2.0",
    "about_text": """
**Ghost Supply** est un optimiseur logistique tactique conçu pour les environnements contestés.
Il utilise des techniques avancées de recherche opérationnelle pour planifier des routes d'approvisionnement
qui minimisent le risque d'interception plutôt que simplement la distance ou le temps.

### Fonctionnalités Clés

- **Optimisation CVaR**: Minimise le risque de queue (pires scénarios) au lieu du risque moyen
- **Modélisation de Propagation RF**: Prend en compte la couverture radio et les zones mortes de communication
- **Prédiction de Menace**: Utilise Prophet + DBSCAN pour identifier les zones à haut risque
- **Intégration Météo**: Prend en compte l'impact météo sur la mobilité et la détection
- **Analyse de Pareto**: Montre les compromis temps vs risque
- **Théorie des Jeux**: Équilibre de Stackelberg pour la randomisation des routes
- **Export ATAK**: Génère des packages de mission compatibles avec les outils de planification militaire

### Comment Ça Marche

1. Configurez vos paramètres de mission (origine, destination, cargo, météo)
2. Cliquez sur "Optimiser la Route" pour calculer le chemin le plus sûr
3. Visualisez la carte tactique avec les zones dangereuses et la route optimale
4. Comparez avec les méthodes de base (GPS le plus court, le plus rapide, etc.)
5. Téléchargez le package de mission pour une utilisation sur le terrain

---

**Construit pour**: Portfolio Défense | **Stack Technique**: Python, Pyomo, Prophet, NetworkX, Streamlit
""",

    # Tactical map
    "tactical_map_title": "Carte Tactique 2D",
    "tactical_map_legend": """
**Légende:**
- 🟢 Route optimisée (CVaR)
- 🔴 Route de référence (GPS)
- 🔴 Zones de mort (kill zones)
- 🏠 Dépôts
- ⭐ Positions de front
""",

    # 3D terrain
    "terrain_3d_title": "Vue Terrain 3D",

    # Pareto
    "pareto_title": "Analyse du Front de Pareto",
    "mixed_strategy_title": "**Distribution de Stratégie Mixte:**",
    "mixed_strategy_info": "Utilisez différentes routes pour chaque mission pour rester imprévisible",

    # Comparison
    "comparison_title": "Comparaison des Méthodes",
    "method": "Méthode",
    "time_min": "Temps (min)",
    "distance_km": "Distance (km)",
    "mean_risk": "Risque Moyen",
    "cvar_95": "CVaR 95%",

    # Method names
    "cvar_method": "CVaR 95%",
    "fastest": "Le Plus Rapide",
    "shortest": "Le Plus Court",
    "mean_risk_method": "Risque Moyen",

    # Briefing
    "mission_briefing": "Briefing de Mission",

    # Status messages
    "success": "✓",
    "warning": "⚠️",
    "error": "❌",
    "info": "ℹ️",
}
