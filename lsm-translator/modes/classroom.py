"""
modes/classroom.py: el docente habla; el estudiante lee, ve señas y pregunta.

    clase = ClassroomSession(GlossaryManager())
    clase.teacher_says("Hola", final=False)        # voz en curso -> subtítulo parcial
    clase.teacher_says("Hola, buenos días")        # frase final -> texto + clips de señas
    clase.show_lesson("Fotosíntesis", "Las plantas ...")
    clase.quick_reply("Repite, por favor")         # el estudiante avisa con un botón
    clase.ask("¿Qué es el dióxido de carbono?")    # o escribe su pregunta
    clase.student_sign("PREGUNTA"); clase.tick()   # o firma (las señas se juntan en una frase)

La interfaz lee dos colas sin bloquearse:
    clase.student_events -> StudentView    (lo que ve el estudiante)
    clase.teacher_events -> StudentMessage (lo que ve el docente)

Internamente es una Conversation de dos personas (docente y estudiante), así que la adaptación
a voz/texto/señas y la acumulación de señas son las mismas que en modes/conversation.py.
"""
from __future__ import annotations

import dataclasses
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable

from utils.glossary import GlossaryManager, SignItem

from .conversation import Channel, Conversation, Delivery, drain, unvalidated_glosas

DOCENTE, ESTUDIANTE = "docente", "estudiante"
RAISE_HAND = "Tengo una pregunta"
QUICK_REPLIES = ("Entendí", "Repite, por favor", "Más despacio", RAISE_HAND)


@dataclass(frozen=True)
class StudentView:
    """Lo que se le muestra al estudiante."""
    kind: str                          # "parcial" | "final" | "leccion"
    text: str
    titulo: str = ""                   # solo en "leccion"
    signs: tuple[SignItem, ...] = ()   # clips en orden; vacío en parciales
    unvalidated: tuple[str, ...] = ()  # glosas cuyo clip aún no está validado (para avisarlo)
    show_text: bool = True
    repetida: bool = False
    t: float = 0.0


@dataclass(frozen=True)
class StudentMessage:
    """Lo que le llega al docente."""
    kind: str    # "pregunta" | "respuesta_rapida"
    text: str
    via: str     # "texto" | "senas" | "boton"
    t: float


class ClassroomSession:
    def __init__(self, glossary: GlossaryManager, *,
                 student_receives: Iterable[Channel | str] = (Channel.TEXTO, Channel.SENAS),
                 pause: float = 2.0, gloss_to_text: Callable[[list[str]], str] | None = None,
                 clock: Callable[[], float] = time.monotonic):
        """student_receives: canales del estudiante. Con solo TEXTO no se calculan clips."""
        self.glossary = glossary
        self.clock = clock
        self.student_receives = frozenset(Channel(c) for c in student_receives)
        self.student_events: queue.Queue = queue.Queue()
        self.teacher_events: queue.Queue = queue.Queue()
        self.hand_raised = False
        self._last_final: StudentView | None = None
        self._transcript: list[str] = []
        self._lock = threading.Lock()
        self.conversation = Conversation(glossary, pause=pause, gloss_to_text=gloss_to_text,
                                         on_delivery=self._route, clock=clock)
        self.conversation.join(DOCENTE, send={Channel.VOZ, Channel.TEXTO}, receive={Channel.TEXTO})
        self.conversation.join(ESTUDIANTE, send={Channel.TEXTO, Channel.SENAS}, receive=self.student_receives)

    # ---------- Docente ----------
    def teacher_says(self, text: str, final: bool = True, via: Channel = Channel.VOZ) -> None:
        """
        Voz del docente ya transcrita. final=False es la transcripción parcial mientras habla:
        se muestra como subtítulo pero no se traduce a señas ni se guarda. Con final=True
        se traduce y queda en la transcripción de la clase.
        """
        text = " ".join(text.split())
        if not text:
            return
        if final:
            self.conversation.send(DOCENTE, text, via=via)
        else:
            self.student_events.put(StudentView("parcial", text, show_text=True, t=self.clock()))

    def teacher_types(self, text: str) -> None:
        self.teacher_says(text, final=True, via=Channel.TEXTO)

    def show_lesson(self, title: str, definition: str, signs_for_definition: bool = False) -> StudentView:
        """Tarjeta de lección: término y definición. Por defecto solo el término se muestra en señas
        (una lista corta de clips); con signs_for_definition=True también la definición."""
        title, definition = " ".join(title.split()), " ".join(definition.split())
        signs: tuple[SignItem, ...] = ()
        if Channel.SENAS in self.student_receives:
            signs = tuple(self.glossary.resolve(f"{title} {definition}" if signs_for_definition else title))
        view = StudentView("leccion", definition, titulo=title, signs=signs,
                           unvalidated=unvalidated_glosas(signs),
                           show_text=Channel.TEXTO in self.student_receives, t=self.clock())
        with self._lock:
            self._transcript.append(f"{title}: {definition}")
        self.student_events.put(view)
        return view

    def repeat_last(self) -> bool:
        """Vuelve a mostrar la última frase final (marcada como repetida). False si aún no hay."""
        with self._lock:
            view = self._last_final
        if view is None:
            return False
        self.student_events.put(dataclasses.replace(view, repetida=True, t=self.clock()))
        return True

    def teacher_acknowledges(self) -> None:
        """El docente vio la mano levantada."""
        self.hand_raised = False

    # ---------- Estudiante ----------
    def quick_reply(self, reply: str) -> None:
        """Botones rápidos (QUICK_REPLIES). «Tengo una pregunta» levanta la mano."""
        if reply not in QUICK_REPLIES:
            raise ValueError(f"Respuesta desconocida: {reply!r}. Opciones: {QUICK_REPLIES}")
        if reply == RAISE_HAND:
            self.hand_raised = True
        self.teacher_events.put(StudentMessage("respuesta_rapida", reply, "boton", self.clock()))

    def ask(self, text: str) -> bool:
        """Pregunta escrita. False si estaba vacía."""
        return bool(self.conversation.send(ESTUDIANTE, text, via=Channel.TEXTO))

    def student_sign(self, glosa: str) -> bool:
        """Una seña reconocida por la cámara; se junta con las anteriores en una frase."""
        return self.conversation.sign(ESTUDIANTE, glosa)

    def pending_question(self) -> str:
        """La pregunta que se está armando con señas, para que el estudiante la revise."""
        return self.conversation.pending(ESTUDIANTE)

    def confirm_question(self) -> None:
        self.conversation.confirm(ESTUDIANTE)

    def discard_question(self) -> None:
        self.conversation.discard(ESTUDIANTE)

    def tick(self) -> None:
        """Envía la pregunta en señas cuando el estudiante hace una pausa. Llamar varias veces por segundo."""
        self.conversation.tick()

    # ---------- Salidas ----------
    @property
    def transcript(self) -> list[str]:
        """Frases finales y lecciones de la clase, para que el estudiante las repase después."""
        with self._lock:
            return list(self._transcript)

    def drain_student(self) -> list[StudentView]:
        return drain(self.student_events)

    def drain_teacher(self) -> list[StudentMessage]:
        return drain(self.teacher_events)

    def _route(self, d: Delivery) -> None:
        if d.to == ESTUDIANTE:
            view = StudentView("final", d.text, signs=d.signs, unvalidated=d.unvalidated,
                               show_text=d.show_text, t=d.t)
            with self._lock:
                self._last_final = view
                self._transcript.append(d.text)
            self.student_events.put(view)
        else:
            self.hand_raised = True
            self.teacher_events.put(StudentMessage("pregunta", d.text, d.via.value, d.t))