"""Lignes de réglage pilotables au clavier et à la souris : curseur, compteur, interrupteur.

Toutes envoient `Row.Changed` quand leur valeur change.
"""

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from . import theme

LABEL_W = 17


class Row(Widget, can_focus=True):
    DEFAULT_CSS = """
    Row { height: 1; width: 1fr; }
    Row:focus { background: $boost; }
    """

    class Changed(Message):
        def __init__(self, row: "Row") -> None:
            self.row = row
            super().__init__()

    def __init__(self, label: str, *, id: str | None = None):
        super().__init__(id=id)
        self.label = label

    def _label(self) -> Text:
        if self.has_focus:
            return Text("▸ " + self.label.ljust(LABEL_W), style=f"bold {theme.YELLOW}")
        return Text("  " + self.label.ljust(LABEL_W), style=theme.GREY_LIGHT)

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()

    def changed(self) -> None:
        self.post_message(self.Changed(self))


class PixelSlider(Row):
    """Curseur 0-100 dessiné comme une traînée de peinture."""

    BINDINGS = [
        Binding("left,minus", "nudge(-1)", show=False),
        Binding("right,plus", "nudge(1)", show=False),
        Binding("shift+left,pagedown", "nudge(-10)", show=False),
        Binding("shift+right,pageup", "nudge(10)", show=False),
        Binding("home", "nudge(-100)", show=False),
        Binding("end", "nudge(100)", show=False),
    ]

    value = reactive(0)
    note = reactive("")

    def __init__(self, label: str, value: int, color: str, *, unit: str = "", note_width: int = 0,
                 id: str | None = None):
        super().__init__(label, id=id)
        self.color = color
        self.unit = unit
        self.note_width = note_width
        self._bar = (0, 0)
        self._dragging = False
        self.set_reactive(PixelSlider.value, int(value))

    def set_value(self, value: float, notify: bool = True) -> None:
        value = max(0, min(100, int(round(value))))
        if value != self.value:
            self.value = value
            if notify:
                self.changed()

    def action_nudge(self, delta: int) -> None:
        self.set_value(self.value + delta)

    def render(self) -> Text:
        text = self._label()
        value_txt = f" {self.value:>3}{self.unit}"
        tail = len(value_txt) + (self.note_width + 2 if self.note_width else 0)
        bar_w = max(6, self.size.width - text.cell_len - tail - 2)
        self._bar = (text.cell_len + 1, bar_w)
        filled = self.value / 100 * bar_w
        full = int(filled)
        partial = " ▏▎▍▌▋▊▉"[int((filled - full) * 8)] if full < bar_w else ""
        color = self.color if self.value else theme.GREY_DARK
        text.append("▕", style=theme.GREY_DARK)
        text.append("█" * full, style=color)
        if partial.strip():
            text.append(partial, style=f"{color} on {theme.FLOOR_A}")
        else:
            partial = ""
        text.append("░" * (bar_w - full - len(partial)), style=theme.GREY_DARK)
        text.append("▏", style=theme.GREY_DARK)
        text.append(value_txt, style=f"bold {theme.WHITE}" if self.has_focus else theme.WHITE)
        if self.note_width:
            text.append("  " + self.note.ljust(self.note_width)[:self.note_width], style=theme.GREY)
        return text

    def _value_at(self, x: int) -> float | None:
        x0, w = self._bar
        if w <= 0:
            return None
        return (x - x0 + 0.5) / w * 100

    def on_mouse_down(self, event: events.MouseDown) -> None:
        v = self._value_at(event.x)
        x0, w = self._bar
        if v is not None and x0 - 1 <= event.x <= x0 + w:
            self._dragging = True
            self.capture_mouse()
            self.set_value(v)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging:
            v = self._value_at(event.x)
            if v is not None:
                self.set_value(v)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()


class Stepper(Row):
    """Valeur numérique bornée, réglée avec ◀ ▶."""

    BINDINGS = [
        Binding("left,minus", "nudge(-1)", show=False),
        Binding("right,plus", "nudge(1)", show=False),
        Binding("shift+left,pagedown", "nudge(-10)", show=False),
        Binding("shift+right,pageup", "nudge(10)", show=False),
    ]

    value = reactive(0.0)

    def __init__(self, label: str, value: float, lo: float, hi: float, step: float,
                 fmt: str = "{:g}", hint: str = "", *, id: str | None = None):
        super().__init__(label, id=id)
        self.lo, self.hi, self.step, self.fmt, self.hint = lo, hi, step, fmt, hint
        self._arrows = (0, 0)
        self.set_reactive(Stepper.value, self._clamp(value))

    def _clamp(self, v: float) -> float:
        v = round(round(v / self.step) * self.step, 6)
        return max(self.lo, min(self.hi, v))

    def set_value(self, value: float, notify: bool = True) -> None:
        value = self._clamp(value)
        if value != self.value:
            self.value = value
            if notify:
                self.changed()

    def action_nudge(self, steps: int) -> None:
        self.set_value(self.value + steps * self.step)

    def render(self) -> Text:
        text = self._label()
        left_x = text.cell_len
        at_lo, at_hi = self.value <= self.lo, self.value >= self.hi
        text.append("◀", style=theme.GREY_DARK if at_lo else theme.YELLOW)
        text.append(f" {self.fmt.format(self.value):^9} ", style=f"bold {theme.WHITE}")
        right_x = text.cell_len
        text.append("▶", style=theme.GREY_DARK if at_hi else theme.YELLOW)
        self._arrows = (left_x, right_x)
        if self.hint:
            text.append("  " + self.hint, style=theme.GREY)
        return text

    def on_click(self, event: events.Click) -> None:
        left_x, right_x = self._arrows
        if abs(event.x - left_x) <= 1:
            self.action_nudge(-1)
        elif abs(event.x - right_x) <= 1:
            self.action_nudge(1)


class Toggle(Row):
    """Interrupteur oui / non."""

    BINDINGS = [Binding("space,enter,left,right", "toggle", show=False)]

    value = reactive(False)

    def __init__(self, label: str, value: bool, *, id: str | None = None):
        super().__init__(label, id=id)
        self.set_reactive(Toggle.value, bool(value))

    def set_value(self, value: bool, notify: bool = True) -> None:
        if bool(value) != self.value:
            self.value = bool(value)
            if notify:
                self.changed()

    def action_toggle(self) -> None:
        self.set_value(not self.value)

    def render(self) -> Text:
        text = self._label()
        if self.value:
            text.append(" ● OUI ", style=f"bold {theme.BLACK} on {theme.GREEN_LIGHT}")
        else:
            text.append(" ○ NON ", style=f"bold {theme.GREY_LIGHT} on {theme.GREY_DARK}")
        return text

    def on_click(self) -> None:
        self.action_toggle()
