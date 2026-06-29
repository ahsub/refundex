"""
config.py — Refundex Engine Konfiguration
Pfade und Parameter hier anpassen, nicht in den Engine-Modulen.
"""
import os

# ── Steuerjahr ────────────────────────────────────────────────────────────────
STEUERJAHR = 2025
KONTO_ID   = 'U12074449'

# ── XML-Dateipfade (IBKR Flex Query Exporte) ─────────────────────────────────
# Mindestens 3 Jahre für korrekten FIFO-Stack (Vorjahresdaten für offene Positionen)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

XML_PFADE = [
    os.path.join(BASE_DIR, 'data', 'Steuerauswertung_2023.xml'),   # ältestes Jahr
    os.path.join(BASE_DIR, 'data', 'Steuerauswertung_2024.xml'),   # Vorjahr
    os.path.join(BASE_DIR, 'data', 'Steuerauswertung_2025.xml'),   # Steuerjahr
]

# ── Output-Verzeichnis ────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# ── Sparer-Pauschbetrag ───────────────────────────────────────────────────────
SPARER_PAUSCHBETRAG = 1000.0   # EUR je Person (2025: 1.000 EUR)

# ── DBA-Quellensteuersätze ────────────────────────────────────────────────────
DBA_SAETZE = {
    'US': 0.15,   # USA: 15 % DBA-Höchstsatz
    'BR': 0.15,   # Brasilien: 15 %
    'DK': 0.15,   # Dänemark: 15 %
    'GB': 0.00,   # Großbritannien: 0 % (keine QST auf Dividenden)
    'NL': 0.15,   # Niederlande: 15 %
    'DE': 0.00,   # Deutschland: wird durch KapESt-Abzug abgegolten
}

# ── Ländernamen für Report ────────────────────────────────────────────────────
LAENDER = {
    'US': '🇺🇸 USA',
    'GB': '🇬🇧 Großbritannien',
    'BR': '🇧🇷 Brasilien',
    'DK': '🇩🇰 Dänemark',
    'SE': '🇸🇪 Schweden',
    'NL': '🇳🇱 Niederlande',
    'DE': '🇩🇪 Deutschland',
    'IE': '🇮🇪 Irland',
}
