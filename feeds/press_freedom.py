"""Libertad de prensa por país (tabla estática, sin red ni claves).

Tramos orientativos basados en RSF / Freedom House: free | partly_free | not_free.
Es una señal informativa (badges + guía de síntesis), no una verdad absoluta.
"""
from __future__ import annotations

# ISO-3166 alpha-2 → tramo
PRESS_FREEDOM = {
    # Libre
    "NO": "free", "DK": "free", "SE": "free", "FI": "free", "NL": "free", "IE": "free",
    "PT": "free", "CH": "free", "DE": "free", "BE": "free", "AT": "free", "IS": "free",
    "EE": "free", "LU": "free", "NZ": "free", "CA": "free", "CR": "free", "JM": "free",
    "ES": "free", "GB": "free", "FR": "free", "IT": "free", "US": "free", "UY": "free",
    "AU": "free", "JP": "free", "CL": "free", "ZA": "free", "TW": "free", "CZ": "free",
    "SI": "free", "LT": "free", "LV": "free",
    # Parcialmente libre
    "PL": "partly_free", "HU": "partly_free", "GR": "partly_free", "AR": "partly_free",
    "BR": "partly_free", "MX": "partly_free", "CO": "partly_free", "PE": "partly_free",
    "EC": "partly_free", "BO": "partly_free", "PA": "partly_free", "DO": "partly_free",
    "IN": "partly_free", "ID": "partly_free", "PH": "partly_free", "MY": "partly_free",
    "KR": "partly_free", "IL": "partly_free", "UA": "partly_free", "RS": "partly_free",
    "TR": "partly_free", "TN": "partly_free", "NG": "partly_free", "KE": "partly_free",
    "GH": "partly_free", "MA": "partly_free", "PK": "partly_free", "LK": "partly_free",
    "GT": "partly_free", "HN": "partly_free", "PY": "partly_free", "BG": "partly_free",
    # No libre
    "VE": "not_free", "CU": "not_free", "NI": "not_free", "RU": "not_free", "BY": "not_free",
    "CN": "not_free", "KP": "not_free", "VN": "not_free", "LA": "not_free", "IR": "not_free",
    "SA": "not_free", "AE": "not_free", "EG": "not_free", "SY": "not_free", "IQ": "not_free",
    "QA": "not_free", "BH": "not_free", "YE": "not_free", "AF": "not_free", "MM": "not_free",
    "TH": "not_free", "KZ": "not_free", "UZ": "not_free", "TM": "not_free", "AZ": "not_free",
    "ET": "not_free", "ER": "not_free", "SD": "not_free", "DZ": "not_free", "ZW": "not_free",
    "RW": "not_free", "TD": "not_free", "SS": "not_free", "HK": "not_free",
}

_LABEL = {"free": "prensa libre", "partly_free": "prensa parcialmente libre",
          "not_free": "baja libertad de prensa", "unknown": ""}


def tier(country):
    return PRESS_FREEDOM.get((country or "").upper(), "unknown")


def label(country):
    return _LABEL.get(tier(country), "")
