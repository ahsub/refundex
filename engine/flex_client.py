"""
flex_client.py — Automatisierter IBKR/CapTrader Flex Web Service Pull
======================================================================
Refundex Engine · v1.0.0 · 06.08.2026

Zwei-Schritt-Protokoll des IBKR Flex Web Service:
  1. SendRequest  → erhält ReferenceCode (Report wird serverseitig generiert)
  2. GetStatement → liefert das fertige XML mit dem ReferenceCode

Credentials:
  IB_FLEX_TOKEN    = Flex Web Service Token (aus IBKR Account Management)
  IB_FLEX_QUERY_ID = Query-ID der konfigurierten Flex Query

Ablage: engine/flex_client.py
Verwendung: von build_report.py oder eigenständig via CLI (python -m engine.flex_client)

SICHERHEIT:
  - Credentials NUR aus .env oder Umgebungsvariablen — nie im Code
  - .env ist in .gitignore gelistet — nie committen
  - Token wird nicht geloggt (nur maskierte Form in Debug-Output)
"""

import os
import time
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# ── Konfiguration ─────────────────────────────────────────────────────────────

# .env aus Repo-Root laden (engine/../.env)
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)

# IBKR Flex Web Service Endpunkte (v3, Stand 2026)
_BASE_URL    = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
_SEND_PATH   = "/SendRequest"
_FETCH_PATH  = "/GetStatement"
_FLEX_VERSION = "3"

# Retry-Verhalten (IBKR generiert Reports asynchron, typisch 10–30s)
_MAX_RETRIES     = 10
_RETRY_DELAY_S   = 8   # Sekunden zwischen GetStatement-Versuchen
_REQUEST_TIMEOUT = 30  # HTTP-Timeout in Sekunden

log = logging.getLogger(__name__)


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _mask(token: str) -> str:
    """Token für Logging maskieren — zeigt nur die ersten 4 Zeichen."""
    if not token or len(token) < 6:
        return "***"
    return token[:4] + "***" + token[-2:]


def _parse_send_response(xml_text: str) -> tuple[str, str]:
    """
    Parst die SendRequest-Antwort.
    Gibt (status, reference_code_or_error) zurück.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise FlexClientError(f"SendRequest-Antwort kein gültiges XML: {e}\nAntwort: {xml_text[:200]}")

    status = root.findtext("Status") or root.get("status", "")
    if status.lower() == "success":
        ref = root.findtext("ReferenceCode") or ""
        if not ref:
            raise FlexClientError("SendRequest erfolgreich, aber kein ReferenceCode in Antwort")
        return "success", ref
    else:
        error_code = root.findtext("ErrorCode") or ""
        error_msg  = root.findtext("ErrorMessage") or xml_text[:300]
        raise FlexClientError(f"SendRequest fehlgeschlagen — Code {error_code}: {error_msg}")


def _is_still_generating(xml_text: str) -> bool:
    """
    Erkennt IBKR-Fehlercode 1019 ('Statement generation in progress').
    GetStatement gibt diesen Code zurück, solange der Report noch erstellt wird.
    """
    try:
        root = ET.fromstring(xml_text)
        code = root.findtext("ErrorCode") or ""
        return code == "1019"
    except ET.ParseError:
        return False


def _is_flex_data(xml_text: str) -> bool:
    """Prüft ob die Antwort ein echtes FlexQueryResponse-Dokument ist."""
    return "<FlexQueryResponse" in xml_text or "<FlexStatement" in xml_text


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

class FlexClientError(Exception):
    """Wird bei Fehlern im Flex-Web-Service-Ablauf geworfen."""
    pass


def fetch_flex_xml(
    token: Optional[str] = None,
    query_id: Optional[str] = None,
    date_from: Optional[str] = None,   # YYYYMMDD, überschreibt Query-Einstellung
    date_to: Optional[str] = None,     # YYYYMMDD
    max_retries: int = _MAX_RETRIES,
    retry_delay: float = _RETRY_DELAY_S,
) -> str:
    """
    Holt das Flex-Query-XML automatisiert vom IBKR Flex Web Service.

    Parameter:
        token     : Flex Web Service Token. Fallback: Umgebungsvariable IB_FLEX_TOKEN.
        query_id  : Flex Query ID.          Fallback: Umgebungsvariable IB_FLEX_QUERY_ID.
        date_from : Optional. Datumsbereich überschreiben (YYYYMMDD).
        date_to   : Optional. Datumsbereich überschreiben (YYYYMMDD).
        max_retries: Anzahl GetStatement-Versuche bevor Abbruch.
        retry_delay: Wartezeit in Sekunden zwischen Versuchen.

    Rückgabe:
        XML-String (identisch mit manuellem Download).

    Wirft:
        FlexClientError bei Authentifizierungs-, Netzwerk- oder Parsing-Fehlern.
        EnvironmentError wenn Credentials fehlen.
    """
    # ── Credentials laden ────────────────────────────────────────────────────
    token    = token    or os.environ.get("IB_FLEX_TOKEN", "").strip()
    query_id = query_id or os.environ.get("IB_FLEX_QUERY_ID", "").strip()

    if not token:
        raise EnvironmentError(
            "IB_FLEX_TOKEN nicht gesetzt. "
            "Bitte in .env oder als Umgebungsvariable setzen.\n"
            f"  Gesuchte .env-Datei: {_ENV_PATH}"
        )
    if not query_id:
        raise EnvironmentError(
            "IB_FLEX_QUERY_ID nicht gesetzt. "
            "Bitte in .env oder als Umgebungsvariable setzen."
        )

    log.info("Flex-Pull gestartet — Token: %s, QueryID: %s", _mask(token), query_id)

    session = requests.Session()
    session.headers.update({"User-Agent": "Refundex/1.0 flex_client.py"})

    # ── Schritt 1: SendRequest ────────────────────────────────────────────────
    send_params: dict = {"t": token, "q": query_id, "v": _FLEX_VERSION}
    if date_from:
        send_params["from"] = date_from
    if date_to:
        send_params["to"] = date_to

    log.debug("SendRequest an %s%s", _BASE_URL, _SEND_PATH)
    try:
        resp = session.get(
            _BASE_URL + _SEND_PATH,
            params=send_params,
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise FlexClientError(f"SendRequest HTTP-Fehler: {e}") from e

    _, reference_code = _parse_send_response(resp.text)
    log.info("SendRequest OK — ReferenceCode: %s", reference_code)

    # ── Schritt 2: GetStatement (mit Retry) ──────────────────────────────────
    fetch_params = {"t": token, "q": reference_code, "v": _FLEX_VERSION}

    for attempt in range(1, max_retries + 1):
        log.debug("GetStatement Versuch %d/%d …", attempt, max_retries)
        time.sleep(retry_delay if attempt > 1 else 3)  # Erster Versuch nach 3s

        try:
            resp = session.get(
                _BASE_URL + _FETCH_PATH,
                params=fetch_params,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning("GetStatement Versuch %d Netzwerkfehler: %s", attempt, e)
            continue

        xml_text = resp.text

        if _is_flex_data(xml_text):
            log.info("Flex-XML erhalten — %d Zeichen", len(xml_text))
            return xml_text

        if _is_still_generating(xml_text):
            log.debug("Report wird noch generiert (Code 1019) — warte %ds …", retry_delay)
            continue

        # Anderer Fehlercode
        try:
            root = ET.fromstring(xml_text)
            code = root.findtext("ErrorCode") or "?"
            msg  = root.findtext("ErrorMessage") or xml_text[:200]
            raise FlexClientError(f"GetStatement Fehler Code {code}: {msg}")
        except ET.ParseError:
            raise FlexClientError(f"GetStatement unerwartete Antwort: {xml_text[:200]}")

    raise FlexClientError(
        f"Flex-XML nach {max_retries} Versuchen nicht erhalten. "
        "IBKR-Server möglicherweise überlastet oder Query-Konfiguration prüfen."
    )


def fetch_and_save(
    output_path: Path,
    token: Optional[str] = None,
    query_id: Optional[str] = None,
    **kwargs,
) -> Path:
    """
    Flex-XML holen und in Datei speichern.

    Verwendung in build_report.py:
        xml_path = fetch_and_save(Path("data/flex_latest.xml"))
        # dann: mit open(xml_path) as f: xml_text = f.read()

    Rückgabe: Path zur gespeicherten Datei.
    """
    xml_text = fetch_flex_xml(token=token, query_id=query_id, **kwargs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml_text, encoding="utf-8")
    log.info("Flex-XML gespeichert: %s", output_path)
    return output_path


# ── CLI-Modus ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="IBKR Flex Web Service Pull — Refundex flex_client.py"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("data/flex_latest.xml"),
        help="Ausgabedatei für das XML (default: data/flex_latest.xml)",
    )
    parser.add_argument(
        "--from-date",
        metavar="YYYYMMDD",
        help="Datumsbereich überschreiben: Von (optional)",
    )
    parser.add_argument(
        "--to-date",
        metavar="YYYYMMDD",
        help="Datumsbereich überschreiben: Bis (optional)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=_MAX_RETRIES,
        help=f"Max. GetStatement-Versuche (default: {_MAX_RETRIES})",
    )
    args = parser.parse_args()

    print(f"Refundex · flex_client.py v1.0.0")
    print(f"Flex-Query Pull → {args.output}")
    print("-" * 50)

    try:
        path = fetch_and_save(
            output_path=args.output,
            date_from=args.from_date,
            date_to=args.to_date,
            max_retries=args.retries,
        )
        print(f"✅ XML gespeichert: {path} ({path.stat().st_size:,} Bytes)")
        sys.exit(0)
    except EnvironmentError as e:
        print(f"❌ Credentials fehlen:\n  {e}")
        sys.exit(1)
    except FlexClientError as e:
        print(f"❌ Flex-Fehler:\n  {e}")
        sys.exit(2)
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
        sys.exit(3)
