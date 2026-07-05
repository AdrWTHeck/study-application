"""Pure-Python Pomodoro timer state machine (§6.3).

No Qt dependency — driven by QTimer ticks from the UI layer so it is fully
testable without a display.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class TimerState(Enum):
    IDLE = auto()
    FOCUS = auto()
    BREAK = auto()
    LONG_BREAK = auto()
    PAUSED = auto()


@dataclass
class PomodoroEvent:
    kind: str  # "focus_started" | "focus_done" | "break_done" | "long_break_done" | "reset"


@dataclass
class PomodoroService:
    """Configurable Pomodoro state machine.

    Call ``tick()`` every second from a QTimer. Collect the returned events
    and react in the UI (show dialogs, award XP, etc.).
    """

    focus_minutes: int = 25
    break_minutes: int = 5
    long_break_minutes: int = 15
    long_break_after: int = 4       # sessions before a long break

    _state: TimerState = field(default=TimerState.IDLE, init=False)
    _seconds_remaining: int = field(default=0, init=False)
    _completed_sessions: int = field(default=0, init=False)
    _paused_state: TimerState = field(default=TimerState.IDLE, init=False)

    # -- queries -------------------------------------------------------------

    @property
    def state(self) -> TimerState:
        return self._state

    @property
    def seconds_remaining(self) -> int:
        return self._seconds_remaining

    @property
    def completed_sessions(self) -> int:
        return self._completed_sessions

    @property
    def is_running(self) -> bool:
        return self._state in (TimerState.FOCUS, TimerState.BREAK, TimerState.LONG_BREAK)

    @property
    def display_time(self) -> str:
        m, s = divmod(self._seconds_remaining, 60)
        return f"{m:02d}:{s:02d}"

    # -- commands ------------------------------------------------------------

    def start_focus(self) -> list[PomodoroEvent]:
        self._state = TimerState.FOCUS
        self._seconds_remaining = self.focus_minutes * 60
        return [PomodoroEvent("focus_started")]

    def pause(self) -> None:
        if self._state in (TimerState.FOCUS, TimerState.BREAK, TimerState.LONG_BREAK):
            self._paused_state = self._state
            self._state = TimerState.PAUSED

    def resume(self) -> None:
        if self._state is TimerState.PAUSED:
            self._state = self._paused_state

    def reset(self) -> list[PomodoroEvent]:
        self._state = TimerState.IDLE
        self._seconds_remaining = 0
        self._completed_sessions = 0
        return [PomodoroEvent("reset")]

    def tick(self) -> list[PomodoroEvent]:
        """Advance one second. Returns a list of events that occurred."""
        if not self.is_running:
            return []

        self._seconds_remaining -= 1
        if self._seconds_remaining > 0:
            return []

        # Timer expired — transition to the next phase.
        if self._state is TimerState.FOCUS:
            self._completed_sessions += 1
            if self._completed_sessions % self.long_break_after == 0:
                self._state = TimerState.LONG_BREAK
                self._seconds_remaining = self.long_break_minutes * 60
                return [PomodoroEvent("focus_done")]
            else:
                self._state = TimerState.BREAK
                self._seconds_remaining = self.break_minutes * 60
                return [PomodoroEvent("focus_done")]

        if self._state is TimerState.BREAK:
            self._state = TimerState.IDLE
            return [PomodoroEvent("break_done")]

        if self._state is TimerState.LONG_BREAK:
            self._state = TimerState.IDLE
            return [PomodoroEvent("long_break_done")]

        return []
