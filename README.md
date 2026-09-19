# Simulateur de rentabilité immobilière

Application locale (FastAPI + JS vanilla) qui combine :

1. **Étude de marché automatique** : à partir d'une adresse, l'app géocode le
   bien (API Adresse / Base Adresse Nationale), récupère les prix de vente
   comparables dans le secteur (DVF géolocalisé) et le loyer de marché estimé
   pour la commune ("Carte des loyers", DHUP/ANIL).
2. **Simulateur de rentabilité** : cash-flow prévisionnel, fiscalité détaillée
   (micro-foncier, foncier réel, micro-BIC LMNP, LMNP réel avec amortissement),
   TRI et simulation de revente avec plus-value immobilière.

## Lancer en local

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Puis ouvrir http://localhost:8000

Les données de marché (DVF par département, indicateurs de loyers) sont
téléchargées à la demande depuis data.gouv.fr et mises en cache dans
`backend/app/data_cache/` (peut prendre quelques secondes au premier appel
pour un département donné).

## Hypothèses et sources fiscales (à vérifier avant toute décision réelle)

- Barème IR 2026 sur les revenus 2025 (5 tranches : 0 / 11 / 30 / 41 / 45 %).
- Prélèvements sociaux : 17,2 % en location nue, 18,6 % en LMNP (LFSS 2026,
  hausse de la CSG sur les revenus meublés non professionnels).
- Plafonds micro : 15 000 €/an (micro-foncier), 77 700 €/an (micro-BIC LMNP
  longue durée). Abattements forfaitaires : 30 % et 50 %.
- Déficit foncier (régime réel, location nue) : la part liée aux intérêts
  d'emprunt n'est imputable que sur des revenus fonciers futurs ; le reste est
  imputable sur le revenu global dans la limite de 10 700 €/an.
- LMNP réel : amortissement linéaire du bâti (hors quote-part de terrain), des
  travaux capitalisés et du mobilier. L'amortissement ne peut pas créer ou
  aggraver un déficit (report illimité de l'amortissement non utilisé, dans
  l'esprit du mécanisme réel).
- Plus-value à la revente : régime des particuliers, abattements pour durée
  de détention (exonération IR à 22 ans, PS à 30 ans), surtaxe sur les
  plus-values > 50 000 €. Depuis la loi de finances 2025 (article 84), les
  amortissements déduits en LMNP réel sont réintégrés dans le calcul de la
  plus-value (base d'acquisition réduite d'autant), ce qui n'est **pas** le
  cas en foncier réel/micro-foncier.
- Les charges (hors loyers) sont supposées constantes sur la durée de
  projection (pas d'inflation appliquée), par simplification.
- La fiscalité est calculée à partir d'une TMI saisie par l'utilisateur, pas
  d'un calcul complet du foyer fiscal — c'est une approximation standard mais
  qui ignore les effets de seuil précis (changement de tranche en cours
  d'année, autres revenus, décote, etc.).

**Ceci reste un outil de simulation pédagogique.** Pour une décision réelle,
faites valider les hypothèses fiscales par un professionnel (notaire,
comptable, CGP).

## Limites connues de l'étude de marché

- DVF ne couvre pas l'Alsace-Moselle (67, 68, 57) ni Mayotte, et les ventes
  très récentes (< quelques mois) peuvent être absentes de l'export.
- L'indicateur de loyer est un modèle statistique (annonces leboncoin/SeLoger)
  avec un intervalle de confiance ; il est peu fiable pour les communes ayant
  peu d'annonces (`nb_observations_commune` faible) — l'app affiche un
  avertissement dans ce cas.

## Architecture

```
backend/
  app/
    main.py          FastAPI : endpoints /api/simulate, /api/market-study
    schemas.py        Modèles Pydantic (entrées)
    finance.py         Emprunt, TRI/VAN génériques
    fiscalite.py        Barème IR + 4 régimes fiscaux locatifs
    simulation.py       Moteur pluriannuel (cash-flow, fiscalité, revente)
    market_data.py      Géocodage + DVF + loyers (téléchargement/cache)
frontend/
  index.html, static/app.js, static/style.css   SPA vanilla JS (aucun build)
```

## Prochaines étapes possibles

- Déploiement (Docker/Render/Railway) une fois le prototype validé.
- Comptes utilisateurs + sauvegarde de plusieurs projets.
- Comparateur multi-biens.
- Calcul IR précis du foyer (au lieu d'une TMI) si l'utilisateur fournit son
  revenu imposable global.
