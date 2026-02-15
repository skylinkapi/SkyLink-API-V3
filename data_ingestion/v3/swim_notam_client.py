"""
SWIM FNS NOTAM Client — Real-time NOTAMs via FAA SWIM Solace messaging.

Connects to FAA's System Wide Information Management (SWIM) Flight Information
Notification Service (FNS) which delivers NOTAMs in AIXM 5.1 XML format via
Solace messaging. Runs as a background thread (same pattern as ADS-B client).

Pure in-memory store — fills up from the SWIM feed on each start.
Cancel (type=C) and Replace (type=R) messages keep the store accurate.
"""

import os
import logging
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)


class SWIMNotamClient:
    """Background client for FAA SWIM FNS NOTAM feed via Solace messaging."""

    AIRPORTS_CSV_URL = (
        "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"
    )

    def __init__(self):
        self.notams: Dict[str, List[dict]] = {}  # ICAO -> list of NOTAM dicts
        self.lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._messages_received = 0
        self._last_message_time: Optional[datetime] = None
        self._iata_to_icao: Dict[str, str] = {}  # IATA 3-letter -> ICAO 4-letter

        # Solace connection config from env
        self._host = os.getenv("SWIM_FNS_HOST", "")
        self._vpn = os.getenv("SWIM_FNS_VPN", "")
        self._username = os.getenv("SWIM_FNS_USERNAME", "")
        self._password = os.getenv("SWIM_FNS_PASSWORD", "")
        self._queue_name = os.getenv("SWIM_FNS_QUEUE", "")

    @property
    def configured(self) -> bool:
        """Check if SWIM FNS credentials are configured."""
        return bool(
            self._host
            and self._vpn
            and self._username
            and self._password
            and self._queue_name
        )

    def _build_iata_to_icao(self):
        """Build IATA→ICAO lookup from OurAirports CSV (synchronous, called once at start)."""
        try:
            resp = httpx.get(self.AIRPORTS_CSV_URL, timeout=30.0)
            resp.raise_for_status()
            from io import StringIO
            df = pd.read_csv(StringIO(resp.text), usecols=["ident", "iata_code"])
            mapping: Dict[str, str] = {}
            for _, row in df.iterrows():
                iata = row.get("iata_code")
                icao = row.get("ident")
                if (
                    pd.notna(iata) and pd.notna(icao)
                    and isinstance(iata, str) and isinstance(icao, str)
                    and len(iata.strip()) == 3 and len(icao.strip()) >= 3
                ):
                    mapping[iata.strip().upper()] = icao.strip().upper()
            self._iata_to_icao = mapping
            logger.info(f"SWIM FNS: loaded {len(mapping)} IATA→ICAO mappings")
        except Exception as e:
            logger.warning(f"SWIM FNS: failed to load IATA→ICAO mapping, falling back to K-prefix: {e}")

    def start(self):
        """Start the SWIM consumer thread."""
        if self._running:
            return
        if not self.configured:
            logger.warning(
                "SWIM FNS not configured - NOTAM feed disabled (set SWIM_FNS_* env vars)"
            )
            return

        self._build_iata_to_icao()
        self._running = True
        self._thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._thread.start()
        self._cleanup_thread = threading.Thread(target=self._run_cleanup, daemon=True)
        self._cleanup_thread.start()
        logger.info("SWIM FNS NOTAM client started")

    def stop(self):
        """Stop the SWIM consumer and disconnect."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        self._connected = False
        logger.info("SWIM FNS NOTAM client stopped")

    def get_notams(self, icao: str) -> List[dict]:
        """Get active NOTAMs for an ICAO code (thread-safe).

        Filters out expired NOTAMs (expiration date in the past).
        NOTAMs with no expiration (permanent) are always included.
        """
        icao = icao.upper().strip()
        now = datetime.now(timezone.utc).isoformat()
        with self.lock:
            return [
                n for n in self.notams.get(icao, [])
                if not n.get("expiration") or n["expiration"] >= now
            ]

    def get_all_notams(self) -> Dict[str, List[dict]]:
        """Get full snapshot of all NOTAMs by ICAO (for stats)."""
        with self.lock:
            return {k: list(v) for k, v in self.notams.items()}

    def get_status(self) -> dict:
        """Connection health and stats."""
        with self.lock:
            total_notams = sum(len(v) for v in self.notams.values())
            airports_covered = len(self.notams)
        return {
            "running": self._running,
            "connected": self._connected,
            "configured": self.configured,
            "messages_received": self._messages_received,
            "total_notams": total_notams,
            "airports_covered": airports_covered,
            "last_message": (
                self._last_message_time.isoformat()
                if self._last_message_time
                else None
            ),
        }

    # -- Expired cleanup -------------------------------------------------------

    def _run_cleanup(self):
        """Periodically remove expired NOTAMs from memory."""
        while self._running:
            time.sleep(300)  # every 5 minutes
            if not self._running:
                break
            now = datetime.now(timezone.utc).isoformat()
            removed = 0
            with self.lock:
                for icao in list(self.notams):
                    before = len(self.notams[icao])
                    self.notams[icao] = [
                        n for n in self.notams[icao]
                        if not n.get("expiration") or n["expiration"] >= now
                    ]
                    removed += before - len(self.notams[icao])
                    if not self.notams[icao]:
                        del self.notams[icao]
            if removed:
                logger.info(f"SWIM FNS cleanup: purged {removed} expired NOTAMs")

    # -- Consumer loop ---------------------------------------------------------

    def _run_consumer(self):
        """Main consumer loop with reconnection logic."""
        retry_count = 0

        while self._running:
            try:
                self._connect_and_consume()
                retry_count = 0
            except Exception as e:
                self._connected = False
                retry_count += 1
                if retry_count % 5 == 1:
                    logger.warning(
                        f"SWIM FNS connection error (attempt {retry_count}): {e}"
                    )
                if self._running:
                    wait = min(5 + retry_count * 2, 60)  # 5s-60s backoff
                    time.sleep(wait)

    def _connect_and_consume(self):
        """Connect to Solace and consume messages until disconnected."""
        from solace.messaging.messaging_service import MessagingService
        from solace.messaging.resources.queue import Queue

        props = {
            "solace.messaging.transport.host": self._host,
            "solace.messaging.service.vpn-name": self._vpn,
            "solace.messaging.authentication.basic.username": self._username,
            "solace.messaging.authentication.basic.password": self._password,
            "solace.messaging.tls.cert-validated": False,
        }

        service = MessagingService.builder().from_properties(props).build()
        service.connect()
        logger.info(f"SWIM FNS connected to {self._host}")

        queue = Queue.durable_exclusive_queue(self._queue_name)
        receiver = (
            service.create_persistent_message_receiver_builder().build(queue)
        )
        receiver.start()
        self._connected = True
        logger.info(f"SWIM FNS receiving from queue: {self._queue_name}")

        try:
            while self._running:
                message = receiver.receive_message(timeout=5000)
                if message is None:
                    continue

                try:
                    payload = message.get_payload_as_string()
                    if payload is None:
                        payload_bytes = message.get_payload_as_bytes()
                        if payload_bytes:
                            payload = payload_bytes.decode("utf-8", errors="replace")

                    if payload:
                        notam = self._parse_aixm_message(payload)
                        if notam:
                            self._store_notam(notam)
                            self._messages_received += 1
                            self._last_message_time = datetime.utcnow()
                            if self._messages_received <= 5 or self._messages_received % 500 == 0:
                                with self.lock:
                                    total = sum(len(v) for v in self.notams.values())
                                    airports = len(self.notams)
                                logger.info(
                                    f"SWIM FNS msg #{self._messages_received}: "
                                    f"{notam.get('notam_id')} @ {notam.get('location')} "
                                    f"({total} NOTAMs / {airports} airports)"
                                )

                    receiver.ack(message)

                except Exception as e:
                    logger.warning(f"SWIM FNS message processing error: {e}")
                    try:
                        receiver.ack(message)
                    except Exception:
                        pass
        finally:
            try:
                receiver.terminate(grace_period=2000)
            except Exception:
                pass
            try:
                service.disconnect()
            except Exception:
                pass
            self._connected = False
            logger.info("SWIM FNS disconnected")

    # -- AIXM 5.1 XML parsing -------------------------------------------------

    @staticmethod
    def _local(tag: str) -> str:
        """Strip namespace from an ElementTree tag, returning local name."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _parse_aixm_message(self, xml_text: str) -> Optional[dict]:
        """Parse an AIXM 5.1 NOTAM message into a dict.

        Uses namespace-agnostic matching ({*}tag) since SWIM FNS messages
        may use aixm: or event: prefixes depending on the schema version.
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.debug(f"SWIM FNS XML parse error: {e}")
            return None

        # Find the NOTAM element — namespace-agnostic wildcard search
        notam_el = root.find(".//{*}NOTAM")
        if notam_el is None:
            return None

        def _text(tag: str) -> Optional[str]:
            """Extract text from a child element by local name."""
            for child in notam_el:
                if self._local(child.tag) == tag:
                    return child.text.strip() if child.text else None
            return None

        series = _text("series") or ""
        number = _text("number") or ""
        year = _text("year") or ""
        notam_id = f"{series}{number}/{year}" if number else None

        notam_type = _text("type")  # N, R, C
        location = _text("location")  # 3-letter or 4-letter
        effective = _text("effectiveStart") or _text("issued")
        expiration = _text("effectiveEnd")
        body = _text("text")  # E field

        # Build raw text approximation
        raw_parts = []
        if notam_id:
            raw_parts.append(f"!{location or '???'} {notam_id}")
        if body:
            raw_parts.append(body)
        if effective:
            raw_parts.append(effective)
        if expiration:
            raw_parts.append(expiration)
        raw = " ".join(raw_parts) if raw_parts else xml_text[:500]

        # Resolve ICAO from location
        icao = self._resolve_icao(location)
        if not icao:
            return None

        return {
            "raw": raw,
            "notam_id": notam_id,
            "type": notam_type,
            "location": icao,
            "effective": effective,
            "expiration": expiration,
            "body": body,
        }

    def _resolve_icao(self, location: Optional[str]) -> Optional[str]:
        """Convert NOTAM location to ICAO code.

        FAA SWIM locations are often 3-letter US codes. Uses the airport
        database IATA→ICAO mapping for accurate resolution (handles Alaska
        P-prefix, Hawaii PH-prefix, etc.). Falls back to K-prefix only if
        the airport isn't in the database.
        """
        if not location:
            return None
        loc = location.upper().strip()
        if len(loc) == 4:
            return loc
        if len(loc) == 3:
            icao = self._iata_to_icao.get(loc)
            if icao:
                return icao
            return "K" + loc  # fallback for codes not in DB
        return None

    # -- NOTAM storage ---------------------------------------------------------

    def _store_notam(self, notam: dict):
        """Thread-safe insert/replace/cancel of a NOTAM."""
        icao = notam["location"]
        notam_type = (notam.get("type") or "N").upper()
        notam_id = notam.get("notam_id")

        with self.lock:
            if notam_type == "C" and notam_id:
                # Cancel - remove matching NOTAM
                if icao in self.notams:
                    self.notams[icao] = [
                        n
                        for n in self.notams[icao]
                        if n.get("notam_id") != notam_id
                    ]
                    if not self.notams[icao]:
                        del self.notams[icao]

            elif notam_type == "R" and notam_id:
                # Replace - remove old then insert new
                if icao in self.notams:
                    self.notams[icao] = [
                        n
                        for n in self.notams[icao]
                        if n.get("notam_id") != notam_id
                    ]
                self.notams.setdefault(icao, []).append(notam)

            else:
                # New (or unknown type) - append
                self.notams.setdefault(icao, []).append(notam)


# -- Singleton -----------------------------------------------------------------

_swim_client = SWIMNotamClient()


def get_swim_notam_client() -> SWIMNotamClient:
    """Get the global SWIM NOTAM client instance."""
    return _swim_client
