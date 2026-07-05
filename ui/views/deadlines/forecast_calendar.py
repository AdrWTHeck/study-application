"""Calendar pressure map widget for the deadline forecast panel."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPaintEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.theme.tokens import Palette
from ui.views.deadlines.view_models import ForecastCalendarDay
from ui.views.deadlines.forecast_builder import completion_band

_DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_CELL_H = 52
_CELL_MIN_W = 52


def _cell_bg_color(day: ForecastCalendarDay, palette: Palette) -> QColor | None:
    """Return the fill color for a calendar cell, or None for transparent."""
    if not day.is_current_month:
        return None

    if day.is_rest:
        c = QColor(palette.info)
        c.setAlphaF(0.15)
        return c

    band = completion_band(day.planned_cards, day.completed_cards)
    if band == "none":
        return QColor(palette.bg_surface)
    if band == "empty":
        return QColor(palette.bg_raised)

    success = QColor(palette.success)
    alphas = {"low": 0.18, "medium": 0.38, "high": 0.62, "full": 0.85}
    success.setAlphaF(alphas.get(band, 0.18))
    return success


class ForecastCalendarDayCell(QWidget):
    """One calendar cell: custom paintEvent background + text labels."""

    _RADIUS = 6

    def __init__(
        self,
        day: ForecastCalendarDay,
        palette: Palette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._day = day
        self._palette = palette
        self.setMinimumSize(_CELL_MIN_W, _CELL_H)
        self.setMaximumHeight(_CELL_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        names = ", ".join(day.deadline_names) if day.deadline_names else ""
        access = f"{day.day.strftime('%A, %B')} {day.day.day}"
        if day.is_today:
            access += " — today"
        if day.is_deadline:
            access += f" — deadline: {names}"
        if day.planned_cards > 0:
            access += f" — {day.completed_cards} of {day.planned_cards} cards"
        self.setAccessibleName(access)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 4, 5, 3)
        layout.setSpacing(1)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(3)

        day_num = QLabel(str(day.day.day))
        if day.is_today:
            day_num.setObjectName("ForecastCalDayNumToday")
        elif not day.is_current_month:
            day_num.setObjectName("ForecastCalDayNumOtherMonth")
        else:
            day_num.setObjectName("ForecastCalDayNum")
        top_row.addWidget(day_num)

        if day.is_deadline:
            due_lbl = QLabel("Due")
            due_lbl.setObjectName("ForecastCalDue")
            top_row.addWidget(due_lbl)

        top_row.addStretch(1)
        top_wrapper = QWidget()
        top_wrapper.setLayout(top_row)
        top_wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout.addWidget(top_wrapper)

        band = completion_band(day.planned_cards, day.completed_cards)
        if day.is_rest:
            marker_text = "☕"
        elif band == "full":
            marker_text = "✓"
        elif day.planned_cards > 0 and day.is_current_month:
            marker_text = f"{day.completed_cards}/{day.planned_cards}"
        else:
            marker_text = ""

        if marker_text:
            marker = QLabel(marker_text)
            marker.setObjectName(
                "ForecastCalMarkerSuccess" if band == "full" else "ForecastCalMarker"
            )
            marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(marker)

        layout.addStretch(1)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        bg = _cell_bg_color(self._day, self._palette)

        if bg is not None:
            painter.setBrush(QBrush(bg))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, self._RADIUS, self._RADIUS)

        if self._day.is_today:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(self._palette.accent), 2))
            painter.drawRoundedRect(rect, self._RADIUS, self._RADIUS)
        elif self._day.is_deadline and self._day.is_current_month:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(self._palette.warning), 1))
            painter.drawRoundedRect(rect, self._RADIUS, self._RADIUS)

        painter.end()


class ForecastCalendarWidget(QWidget):
    """7-column Mon-Sun calendar grid with Month / 2-weeks / To-next-deadline toggle."""

    def __init__(
        self,
        days: list[ForecastCalendarDay],
        soonest_deadline: date | None,
        today: date,
        palette: Palette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._all_days = days
        self._soonest = soonest_deadline
        self._today = today
        self._palette = palette
        self._mode = "month"

        self.setObjectName("ForecastCalendarWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(6)

        # Toggle bar
        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(4)

        self._toggle_btns: dict[str, QPushButton] = {}
        for mode, label in (("month", "Month"), ("2weeks", "2 weeks"), ("next_deadline", "To next deadline")):
            btn = QPushButton(label)
            btn.setAccessibleName(f"Calendar view: {label}")
            btn.setCheckable(True)
            btn.setChecked(mode == "month")
            btn.setObjectName("CalToggleActive" if mode == "month" else "CalToggleInactive")
            btn.clicked.connect(lambda _=False, m=mode: self._set_mode(m))
            toggle_row.addWidget(btn)
            self._toggle_btns[mode] = btn
        toggle_row.addStretch(1)
        self._root.addLayout(toggle_row)

        # Day-of-week header
        header_grid = QGridLayout()
        header_grid.setContentsMargins(0, 0, 0, 0)
        header_grid.setSpacing(2)
        for col, label in enumerate(_DOW_LABELS):
            lbl = QLabel(label)
            lbl.setObjectName("ForecastCalDayOfWeek")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            header_grid.addWidget(lbl, 0, col)
            header_grid.setColumnStretch(col, 1)
        self._root.addLayout(header_grid)

        # Cell grid container
        self._grid_widget = QWidget()
        self._grid_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(2)
        for col in range(7):
            self._grid_layout.setColumnStretch(col, 1)
        self._root.addWidget(self._grid_widget)

        self._rebuild_grid()

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        for m, btn in self._toggle_btns.items():
            btn.setChecked(m == mode)
            btn.setObjectName("CalToggleActive" if m == mode else "CalToggleInactive")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._rebuild_grid()

    def _visible_days(self) -> list[ForecastCalendarDay]:
        if self._mode == "month":
            return [d for d in self._all_days if d.is_current_month or (
                # Include padding weeks at grid start/end
                d.day < self._today.replace(day=1) or
                d.day > self._today.replace(
                    day=calendar.monthrange(self._today.year, self._today.month)[1]
                )
            )]

        if self._mode == "2weeks":
            end = self._today + timedelta(days=13)
        elif self._mode == "next_deadline" and self._soonest:
            end = self._soonest
        else:
            # fallback: month view
            return self._all_days

        start_mon = self._today - timedelta(days=self._today.weekday())
        end_sun = end + timedelta(days=(6 - end.weekday()))
        return [d for d in self._all_days if start_mon <= d.day <= end_sun]

    def _rebuild_grid(self) -> None:
        from ui.utils.layouts import clear_layout
        clear_layout(self._grid_layout)

        visible = self._visible_days()
        if not visible:
            return

        for row_idx, chunk_start in enumerate(range(0, len(visible), 7)):
            week = visible[chunk_start:chunk_start + 7]
            for col, day_info in enumerate(week):
                cell = ForecastCalendarDayCell(day_info, self._palette)
                self._grid_layout.addWidget(cell, row_idx, col)

        # Refresh the grid widget's size hint
        self._grid_widget.adjustSize()
