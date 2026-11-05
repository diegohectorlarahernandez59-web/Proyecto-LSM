"""
modes/conversation.py: alumno <-> alumno, cada uno con su canal (voz, texto o señas).

Cada participante declara cómo envía y cómo recibe:
    ana  = conv.join("Ana",  send={Channel.SENAS, Channel.TEXTO}, receive={Channel.TEXTO, Channel.SENAS})
    luis = conv.join("Luis", send={Channel.VOZ},                  receive={Channel.VOZ})

Todo llega a este módulo ya como texto (voz -> speech_to_text, señas -> sign_to_text) y se
adapta para cada destinatario:
    texto -> show_text=True      voz -> speak=True (para text_to_speech)
    señas -> clips de utils/glossary.py, con deletreo para lo que no esté en el glosario

Las señas llegan una por una del reconocedor. Se juntan en una frase que se envía tras una
pausa (tick) o al confirmar, para que quien firma pueda revisarla (pending) o descartarla
(discard) antes de que la reciba el otro alumno.

La interfaz recibe las entregas por la cola de cada participante (drain) o con on_delivery.
"""
from __future__ import annotations

import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable

from utils.glossary import VALIDADA, GlossaryManager, SignItem


class Channel(str, Enum):
    VOZ = "voz"
    TEXTO = "texto"
    SENAS = "senas"


_DEFAULT_VIA_ORDER = (Channel.TEXTO, Channel.VOZ, Channel.SENAS)


def drain(q: queue.Queue) -> list:
    """Saca todo lo que haya en la cola sin bloquear (para el hilo de la interfaz)."""
    out = []
    while True:
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            return out


def default_gloss_to_text(glosas: Iterable[str]) -> str:
    """Une las glosas reconocidas en una frase. Sustitúyelo (gloss_to_text=...) por una llamada
    a Gemini si quieres convertir la glosa LSM en español con gramática completa."""
    text = " ".join(g.strip().lower() for g in glosas if g.strip())
    return text[:1].upper() + text[1:]


def unvalidated_glosas(signs: Iterable[SignItem]) -> tuple[str, ...]:
    """Señas mostradas cuyo clip aún no revisó una persona sorda o un intérprete."""
    return tuple(i.text for i in signs if i.kind == "sign" and i.estado != VALIDADA)


@dataclass(frozen=True)
class Message:
    sender: str
    text: str
    via: Channel
    t: float


@dataclass(frozen=True)
class Delivery:
    """Un mensaje ya adaptado a los canales de recepción de un destinatario."""
    to: str
    sender: str
    text: str
    via: Channel                      # canal con el que lo envió el remitente
    show_text: bool                   # mostrarlo escrito
    speak: bool                       # leerlo en voz alta
    signs: tuple[SignItem, ...] = ()  # clips en orden; vacío si no recibe señas
    t: float = 0.0

    @property
    def unvalidated(self) -> tuple[str, ...]:
        return unvalidated_glosas(self.signs)


class SignAccumulator:
    """Junta las señas sueltas que reconoce la cámara en una frase."""

    def __init__(self, pause: float = 1.5, repeat_gap: float = 1.0, clock: Callable[[], float] = time.monotonic):
        self.pause, self.repeat_gap, self.clock = pause, repeat_gap, clock
        self.words: list[str] = []
        self._last_t = 0.0

    def add(self, glosa: str, t: float | None = None) -> bool:
        """True si se agregó. La misma seña sostenida (reconocida varias veces seguidas)
        no se repite, pero sí renueva la pausa porque la persona sigue firmando."""
        glosa = glosa.strip()
        if not glosa:
            return False
        t = self.clock() if t is None else t
        sostenida = bool(self.words) and glosa == self.words[-1] and t - self._last_t < self.repeat_gap
        self._last_t = t
        if sostenida:
            return False
        self.words.append(glosa)
        return True

    def due(self, now: float | None = None) -> bool:
        """True si hay palabras y ya pasó la pausa sin señas nuevas."""
        now = self.clock() if now is None else now
        return bool(self.words) and now - self._last_t >= self.pause

    def flush(self) -> list[str]:
        words, self.words = self.words, []
        return words

    def discard(self) -> None:
        self.words = []


@dataclass
class Participant:
    name: str
    send: frozenset
    receive: frozenset
    signs: SignAccumulator | None = None   # solo si puede enviar por señas


class Conversation:
    def __init__(self, glossary: GlossaryManager, *, pause: float = 1.5,
                 gloss_to_text: Callable[[list[str]], str] | None = None,
                 on_delivery: Callable[[Delivery], None] | None = None,
                 clock: Callable[[], float] = time.monotonic, history_size: int = 1000):
        """
        on_delivery: si se da, recibe cada entrega (en el hilo que envía) en lugar de
        ponerla en la cola del destinatario.
        """
        self.glossary = glossary
        self.pause = pause
        self.gloss_to_text = gloss_to_text or default_gloss_to_text
        self.on_delivery = on_delivery
        self.clock = clock
        self.history: deque[Message] = deque(maxlen=history_size)
        self._people: dict[str, Participant] = {}
        self._inbox: dict[str, queue.Queue] = {}
        self._lock = threading.RLock()

    # ---------- Participantes ----------
    def join(self, name: str, send: Iterable, receive: Iterable) -> Participant:
        name = name.strip()
        if not name:
            raise ValueError("El participante necesita un nombre")
        send, receive = frozenset(Channel(c) for c in send), frozenset(Channel(c) for c in receive)
        if not send or not receive:
            raise ValueError("Cada participante necesita al menos un canal para enviar y uno para recibir")
        with self._lock:
            if name in self._people:
                raise ValueError(f"{name!r} ya está en la conversación")
            acc = SignAccumulator(self.pause, clock=self.clock) if Channel.SENAS in send else None
            self._people[name] = person = Participant(name, send, receive, acc)
            self._inbox[name] = queue.Queue()
        return person

    def leave(self, name: str) -> None:
        with self._lock:
            self._people.pop(name, None)
            self._inbox.pop(name, None)

    @property
    def participants(self) -> list[str]:
        with self._lock:
            return list(self._people)

    def _get(self, name: str) -> Participant:
        try:
            return self._people[name]
        except KeyError:
            raise KeyError(f"{name!r} no está en la conversación") from None

    # ---------- Enviar ----------
    def send(self, sender: str, text: str, via: Channel | str | None = None) -> list[Delivery]:
        """Entrega el texto a todos los demás, adaptado a cómo recibe cada uno."""
        text = " ".join(text.split())
        if not text:
            return []
        with self._lock:
            me = self._get(sender)
            if via is None:
                via = next(c for c in _DEFAULT_VIA_ORDER if c in me.send)
            else:
                via = Channel(via)
                if via not in me.send:
                    raise ValueError(f"{sender} no envía por {via.value}")
            now = self.clock()
            self.history.append(Message(sender, text, via, now))
            recipients = [p for p in self._people.values() if p.name != sender]

        signs: tuple[SignItem, ...] | None = None   # se calcula una sola vez y solo si alguien lo necesita
        deliveries = []
        for r in recipients:
            if Channel.SENAS in r.receive:
                signs = tuple(self.glossary.resolve(text)) if signs is None else signs
            deliveries.append(Delivery(
                to=r.name, sender=sender, text=text, via=via,
                show_text=Channel.TEXTO in r.receive, speak=Channel.VOZ in r.receive,
                signs=signs if Channel.SENAS in r.receive and signs else (), t=now))
        for d in deliveries:
            self._dispatch(d)
        return deliveries

    def _dispatch(self, d: Delivery) -> None:
        if self.on_delivery:
            self.on_delivery(d)
        else:
            box = self._inbox.get(d.to)
            if box is not None:
                box.put(d)

    # ---------- Señas reconocidas ----------
    def sign(self, sender: str, glosa: str, t: float | None = None) -> bool:
        """Una seña reconocida por la cámara. True si se agregó a la frase en curso."""
        with self._lock:
            me = self._get(sender)
            if me.signs is None:
                raise ValueError(f"{sender} no envía por señas")
            return me.signs.add(glosa, t)

    def pending(self, sender: str) -> str:
        """La frase que se está armando con señas, para que quien firma la revise."""
        with self._lock:
            acc = self._get(sender).signs
            return self.gloss_to_text(list(acc.words)) if acc and acc.words else ""

    def confirm(self, sender: str) -> list[Delivery]:
        """Envía ahora la frase pendiente."""
        with self._lock:
            acc = self._get(sender).signs
            words = acc.flush() if acc else []
        return self.send(sender, self.gloss_to_text(words), via=Channel.SENAS) if words else []

    def discard(self, sender: str) -> None:
        """Descarta la frase pendiente (por ejemplo, si el reconocedor se equivocó)."""
        with self._lock:
            acc = self._get(sender).signs
            if acc:
                acc.discard()

    def tick(self, now: float | None = None) -> list[Delivery]:
        """Envía las frases cuya pausa ya terminó. La interfaz lo llama unas veces por segundo."""
        with self._lock:
            due = [p.name for p in self._people.values() if p.signs and p.signs.due(now)]
        out: list[Delivery] = []
        for name in due:
            out += self.confirm(name)
        return out

    # ---------- Recibir ----------
    def inbox(self, name: str) -> queue.Queue:
        with self._lock:
            self._get(name)
            return self._inbox[name]

    def drain(self, name: str) -> list[Delivery]:
        return drain(self.inbox(name))