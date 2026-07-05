"""Tests for the PomodoroService state machine (§6.3)."""
import pytest

from domain.study.pomodoro_service import PomodoroService, TimerState


def _make(focus=25, brk=5, long_brk=15, long_after=4) -> PomodoroService:
    return PomodoroService(
        focus_minutes=focus,
        break_minutes=brk,
        long_break_minutes=long_brk,
        long_break_after=long_after,
    )


def test_initial_state():
    svc = _make()
    assert svc.state is TimerState.IDLE
    assert not svc.is_running
    assert svc.completed_sessions == 0


def test_start_focus():
    svc = _make(focus=1)
    events = svc.start_focus()
    assert svc.state is TimerState.FOCUS
    assert svc.seconds_remaining == 60
    assert any(e.kind == "focus_started" for e in events)


def test_tick_during_focus():
    svc = _make(focus=1)
    svc.start_focus()
    # Tick 59 times — should not transition yet.
    for _ in range(59):
        events = svc.tick()
        assert not events
    assert svc.state is TimerState.FOCUS
    assert svc.seconds_remaining == 1


def test_focus_done_transitions_to_break():
    svc = _make(focus=1, brk=5, long_after=4)
    svc.start_focus()
    # Drain focus.
    for _ in range(60):
        events = svc.tick()
    assert svc.state is TimerState.BREAK
    assert any(e.kind == "focus_done" for e in events)
    assert svc.completed_sessions == 1


def test_break_done_returns_to_idle():
    svc = _make(focus=1, brk=1, long_after=4)
    svc.start_focus()
    # Drain focus.
    for _ in range(60):
        svc.tick()
    # Drain break.
    for _ in range(60):
        events = svc.tick()
    assert svc.state is TimerState.IDLE
    assert any(e.kind == "break_done" for e in events)


def test_long_break_after_n_sessions():
    # long_after=2 means every 2nd completed session triggers a long break.
    svc = _make(focus=1, brk=1, long_brk=3, long_after=2)

    # Session 1 → short break.
    svc.start_focus()
    for _ in range(60):
        svc.tick()
    assert svc.state is TimerState.BREAK
    for _ in range(60):
        svc.tick()  # drain break → idle

    # Session 2 → long break.
    svc.start_focus()
    for _ in range(60):
        svc.tick()
    assert svc.state is TimerState.LONG_BREAK
    assert svc.completed_sessions == 2


def test_pause_and_resume():
    svc = _make(focus=5)
    svc.start_focus()
    svc.tick()
    svc.pause()
    assert svc.state is TimerState.PAUSED
    remaining = svc.seconds_remaining
    svc.tick()  # should not count down while paused
    assert svc.seconds_remaining == remaining
    svc.resume()
    assert svc.state is TimerState.FOCUS


def test_reset():
    svc = _make(focus=1)
    svc.start_focus()
    for _ in range(30):
        svc.tick()
    events = svc.reset()
    assert svc.state is TimerState.IDLE
    assert any(e.kind == "reset" for e in events)
    assert svc.completed_sessions == 0


def test_display_time_format():
    svc = _make(focus=25)
    svc.start_focus()
    assert svc.display_time == "25:00"
    svc.tick()
    assert svc.display_time == "24:59"
