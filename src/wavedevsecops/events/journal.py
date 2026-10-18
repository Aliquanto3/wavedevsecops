"""Enveloppe d'événements et journal d'un espace : `seq`, tampon circulaire, reprise (AD-17).

Le journal est sûr entre fils : la file d'un espace publie depuis son fil, le flux SSE
s'abonne depuis la boucle du serveur.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from wavedevsecops.events.catalog import Kind, ResyncRequired, validate_payload

RESYNC_BOOT_TEXT = "WaveDevSecOps a redémarré : l'affichage est rechargé depuis le serveur."
RESYNC_GAP_TEXT = "Des événements ont été manqués : l'affichage est rechargé depuis le serveur."


def now_iso() -> str:
    """Horodatage ISO 8601 à la milliseconde, avec fuseau (convention « Dates »)."""
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Envelope(BaseModel):
    """Enveloppe commune à tous les événements d'un espace (AD-17)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    boot_id: str
    seq: int
    ts: str
    workspace_id: str
    epoch: int
    op_id: str | None
    kind: Kind
    payload: dict[str, Any]

    @property
    def event_id(self) -> str:
        """Identifiant SSE : `<boot_id>:<seq>`."""
        return f"{self.boot_id}:{self.seq}"

    def to_sse(self) -> str:
        """Bloc SSE : `id` puis l'enveloppe en JSON sur une ligne `data`."""
        data = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        return f"id: {self.event_id}\ndata: {data}\n\n"


Subscriber = Callable[[Envelope], None]


class EventLog:
    """Journal d'un espace : numérotation stricte et tampon des derniers événements."""

    def __init__(self, workspace_id: str, boot_id: str, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("le tampon d'événements contient au moins un événement")
        self.workspace_id = workspace_id
        self.boot_id = boot_id
        self._buffer: deque[Envelope] = deque(maxlen=capacity)
        self._seq = 0
        self._lock = threading.Lock()
        self._subscribers: list[Subscriber] = []

    @property
    def seq(self) -> int:
        """Dernier `seq` publié (0 : aucun)."""
        with self._lock:
            return self._seq

    def publish(
        self,
        kind: Kind | str,
        payload: BaseModel | dict[str, Any],
        *,
        epoch: int,
        op_id: str | None,
    ) -> Envelope:
        """Valide la charge, numérote l'événement, le garde dans le tampon et le diffuse."""
        data = validate_payload(kind, payload)
        with self._lock:
            self._seq += 1
            envelope = Envelope(
                boot_id=self.boot_id,
                seq=self._seq,
                ts=now_iso(),
                workspace_id=self.workspace_id,
                epoch=epoch,
                op_id=op_id,
                kind=Kind(kind),
                payload=data,
            )
            self._buffer.append(envelope)
            # Sous le verrou : chaque abonné reçoit les événements dans l'ordre de `seq`.
            for subscriber in list(self._subscribers):
                try:
                    subscriber(envelope)
                except Exception:  # noqa: BLE001 - un flux fermé ne bloque pas la file
                    logging.getLogger("wavedevsecops").exception("Abonné d'événements en échec")
        return envelope

    def _missed(self, last_event_id: str | None) -> list[Envelope] | None:
        """Événements après `last_event_id` ; `None` si la reprise est impossible."""
        if last_event_id is None or not last_event_id.strip():
            return []
        boot, sep, raw_seq = last_event_id.strip().rpartition(":")
        if not sep or boot != self.boot_id or not raw_seq.isdigit():
            return None
        seen = int(raw_seq)
        if seen > self._seq:
            return None
        oldest = self._buffer[0].seq if self._buffer else self._seq + 1
        if seen < oldest - 1:
            return None  # sorti du tampon
        return [e for e in self._buffer if e.seq > seen]

    def resync_envelope(self, reason_text: str, *, epoch: int) -> Envelope:
        """`resync_required` adressé à un seul flux : hors journal, au `seq` courant."""
        with self._lock:
            seq = self._seq
        return Envelope(
            boot_id=self.boot_id,
            seq=seq,
            ts=now_iso(),
            workspace_id=self.workspace_id,
            epoch=epoch,
            op_id=None,
            kind=Kind.RESYNC_REQUIRED,
            payload=validate_payload(Kind.RESYNC_REQUIRED, ResyncRequired(reason_text=reason_text)),
        )

    def attach(
        self, last_event_id: str | None, subscriber: Subscriber
    ) -> tuple[list[Envelope] | None, Callable[[], None]]:
        """Abonne `subscriber` et rend les événements manqués, sans trou ni doublon.

        Rend `(None, …)` si la reprise est impossible (`boot_id` différent, `seq` sorti du
        tampon) : le flux doit alors émettre `resync_required`.
        """
        with self._lock:
            missed = self._missed(last_event_id)
            self._subscribers.append(subscriber)

        def detach() -> None:
            with self._lock:
                if subscriber in self._subscribers:
                    self._subscribers.remove(subscriber)

        return missed, detach

    def resync_reason(self, last_event_id: str | None) -> str:
        """Texte de `resync_required` selon la cause."""
        boot = (last_event_id or "").strip().rpartition(":")[0]
        return RESYNC_BOOT_TEXT if boot != self.boot_id else RESYNC_GAP_TEXT
