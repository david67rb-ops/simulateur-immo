"""Utilitaires partagés."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass

LIBELLES_REGIMES = {
    "micro-foncier": "Micro-foncier",
    "foncier-reel": "Foncier réel",
    "LMNP-reel": "LMNP au réel",
    "SCI-IS": "SCI à l'IS",
}


def libelle_regime(regime: str) -> str:
    """Nom lisible d'un régime (les régimes micro-BIC ont déjà un nom lisible)."""
    return LIBELLES_REGIMES.get(regime, regime[:1].upper() + regime[1:])


def clean_result(obj):
    """Convertit récursivement les dataclasses en dict et neutralise les NaN
    (non sérialisables en JSON standard)."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return clean_result(asdict(obj))
    if isinstance(obj, dict):
        return {k: clean_result(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_result(v) for v in obj]
    if isinstance(obj, float):
        return None if obj != obj else obj  # NaN -> None
    return obj
