# Ghost Supply - Méthodologie Technique

## Formulation Mathématique

### 1. Énoncé du Problème

**Données** :
- **G = (V, E)** : Graphe du réseau routier
- **s, t ∈ V** : Nœuds origine et destination
- **Ω** : Ensemble des scénarios de risque (|Ω| = N)
- **p(ω)** : Probabilité du scénario ω (uniforme : 1/N)
- **c_temps(e)** : Temps de trajet sur l'arc e
- **r(e, ω)** : Risque sur l'arc e dans le scénario ω
- **α ∈ [0,1]** : Niveau de confiance (ex: 0.95)

**Objectif** :
- **x** : Vecteur binaire indiquant le chemin sélectionné
- Minimiser : **w_temps · Temps(x) + w_risque · CVaR_α(Risque(x))**

**Contraintes** :
- Conservation du flot
- x ∈ {0,1}^|E|

---

## 2. Formulation CVaR

### Définition

**Value-at-Risk (VaR)** : Le quantile α de la distribution du risque.

**Conditional Value-at-Risk (CVaR)** : L'espérance du risque dans la queue (1-α) la plus défavorable de la distribution.

Mathématiquement :

```
VaR_α(X) = inf{x : P(X ≤ x) ≥ α}

CVaR_α(X) = E[X | X ≥ VaR_α(X)]
```

### Reformulation Programmation Linéaire

Le CVaR peut être formulé comme :

```
CVaR_α(X) = min_η { η + (1/(1-α)) · E[max(X - η, 0)] }
```

Dans mon MILP :

```python
# Variables de décision
x[e] ∈ {0,1}  # = 1 si l'arc e est emprunté
η ∈ ℝ+         # Seuil VaR
z[ω] ∈ ℝ+      # Excès de risque dans le scénario ω

# Objectif CVaR
minimize: w_temps · ∑ c_temps(e) · x[e] +
          w_risque · (η + 1/(1-α) · 1/N · ∑ z[ω])

# Contraintes CVaR
∀ω: z[ω] ≥ ∑ r(e,ω) · x[e] - η
∀ω: z[ω] ≥ 0
```

---

## 3. Génération de Scénarios de Risque

Pour chaque scénario ω, je génère des variations aléatoires des facteurs de risque :

```python
scénarios = []
for i in range(N):
    ω = {
        'mult_visibilité': uniform(0.7, 1.3),
        'mult_détection': uniform(0.8, 1.2),
        'présence_patrouilles': choix([0.8, 1.0, 1.2, 1.5])
    }
    scénarios.append(ω)
```

Le risque sur un arc dans un scénario devient :

```python
r(e, ω) = détection_base(e) · ω['mult_détection'] ·
          (1 + visibilité(e) · ω['mult_visibilité'] · 0.5) ·
          ω['présence_patrouilles'] ·
          pénalité_killzone(e)
```

---

## 4. Pénalité Exponentielle Kill Zones

Au lieu d'un coût linéaire, j'applique une pénalité exponentielle basée sur la distance aux kill zones :

```python
def pénalité_killzone(lat, lon, kill_zones):
    pénalité_max = 1.0

    for kz in kill_zones:
        distance = haversine(lat, lon, kz.centre)

        if distance < kz.rayon:
            # DANS la zone = quasi-interdit
            pénalité = 1000.0
        elif distance < kz.rayon * 1.5:
            # PROCHE = très dangereux (exponentiel)
            proximité = 1 - (distance - kz.rayon) / (kz.rayon * 0.5)
            pénalité = 50 · exp(3 · proximité)  # 50-200
        elif distance < kz.rayon * 2.0:
            # BUFFER = zone de prudence
            pénalité = 10.0
        else:
            # LOIN = risque de base
            pénalité = 1.0

        pénalité_max = max(pénalité_max, pénalité)

    return pénalité_max
```

Cette approche garantit que :
- Les routes **traversant** une kill zone sont quasi-interdites (coût × 1000)
- Les routes **proches** subissent une forte pénalité exponentielle
- L'optimiseur est **forcé** de contourner largement

---

## 5. Calcul de la Probabilité de Survie

Le score CVaR brut peut dépasser 1, donc je le transforme en probabilité via une décroissance exponentielle :

```python
def probabilité_survie(score_cvar, λ=0.1):
    """
    Transforme le score brut CVaR en probabilité de survie.

    Calibration (λ=0.1):
    - score ~5  → 60% survie
    - score ~15 → 22% survie
    - score ~30 → 5% survie
    """
    return exp(-λ · score_cvar)
```

Ça garantit :
- P_survie ∈ [0, 1] (toujours valide)
- Plus le score CVaR est élevé, plus P_survie diminue
- Les routes "sûres" ont un score faible → haute P_survie

---

## 6. Extraction de Géométrie OSM

**Problème** : OSMnx simplifie les graphes en retirant les nœuds intermédiaires, mais stocke la géométrie des courbes dans l'attribut `geometry` des arcs.

**Solution** : Extraire cette géométrie pour afficher les vraies courbes de routes :

```python
def construire_chemin(node_path, graphe):
    coords_chemin = []

    for i in range(len(node_path) - 1):
        u, v = node_path[i], node_path[i+1]
        edge_data = graphe.edges[u, v]

        if 'geometry' in edge_data:
            # Extraire les points intermédiaires de la LineString
            geom = edge_data['geometry']
            lons, lats = geom.xy
            segment = list(zip(lats, lons))

            if i == 0:
                coords_chemin.extend(segment)
            else:
                # Éviter les doublons de point de jonction
                coords_chemin.extend(segment[1:])
        else:
            # Pas de géométrie : ligne droite
            coords_chemin.append((graphe.nodes[u]['y'], graphe.nodes[u]['x']))
            if i == len(node_path) - 2:
                coords_chemin.append((graphe.nodes[v]['y'], graphe.nodes[v]['x']))

    return coords_chemin
```

---

## 7. Algorithmes Baseline

Pour valider l'approche CVaR, je compare avec des méthodes classiques :

### Plus Court (GPS naïf)
```python
chemin = nx.shortest_path(G, s, t, weight='distance_km')
```
Ignore complètement le risque → traverse les kill zones.

### Plus Rapide
```python
chemin = nx.shortest_path(G, s, t, weight='travel_time_hours')
```
Optimise le temps mais ignore le risque.

### Risque Moyen
```python
for (u, v) in G.edges():
    G[u][v]['risk_weight'] = détection_base · pénalité_killzone

chemin = nx.shortest_path(G, s, t, weight='risk_weight')
```
Minimise le risque moyen, mais peut avoir des segments très dangereux.

### CVaR 95% (Ghost Supply)
```python
chemin = optimiser_cvar(G, s, t, alpha=0.95)
```
Minimise le **95ème percentile** du risque → évite les segments catastrophiques.

---

## 8. Complexité Algorithmique

- **Graphe** : |V| ≈ 5000 nœuds, |E| ≈ 12000 arcs (zone 50km × 50km)
- **MILP** : 12000 variables binaires + N variables continues (scénarios)
- **Temps de résolution** :
  - Dijkstra : < 1s
  - CVaR MILP : 5-30s (selon solveur et N)

Solveurs utilisés :
- **HiGHS** : Rapide, open-source
- **CBC** : Fallback si HiGHS indisponible
- **Gurobi** : Optimal mais licence commerciale

---

## 9. Théorie des Jeux - Stackelberg

Pour éviter la prévisibilité, je calcule une **stratégie mixte** sur K routes alternatives :

1. Générer K routes Pareto-optimales (compromis temps/risque)
2. Construire la matrice de gain :
   ```
   U[k, m] = -P(interception | route k, config ennemi m)
   ```
3. Résoudre le jeu :
   ```python
   équilibre = nashpy.Game(U).support_enumeration()
   ```
4. Obtenir la distribution de probabilité sur les routes

**Résultat** : Chaque mission emprunte une route différente selon la stratégie mixte → ennemi ne peut pas prédire.

---

## 10. Validation des Résultats

### Tests de Cohérence
```python
# CVaR ≥ Risque Moyen (propriété mathématique)
assert route_cvar.cvar_95 >= route_cvar.mean_risk

# Probabilité de survie ∈ [0, 1]
assert 0 <= route.survival_probability <= 1

# Route optimisée plus sûre que GPS
assert route_cvar.cvar_95 < route_gps.cvar_95
```

### Visualisation
- Carte 2D : Routes suivent les courbes OSM ✓
- Kill zones : Route optimisée contourne largement ✓
- Métriques : P_survie cohérente avec CVaR ✓

---

**En résumé** : Ghost Supply combine optimisation CVaR, pénalités exponentielles kill zones, extraction géométrie OSM et stratégies mixtes pour générer des routes tactiques imprévisibles et sûres.
