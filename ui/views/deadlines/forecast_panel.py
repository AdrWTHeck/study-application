"""Left-side Deadline Forecast panel: word of day, signal, load rows, calendar."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.theme.tokens import Palette
from ui.utils.layouts import clear_layout
from ui.views.deadlines.view_models import DeadlineForecast, ForecastWorkItem
from ui.views.deadlines.forecast_calendar import ForecastCalendarWidget


class _ForecastWorkRow(QWidget):
    """Name label + relative-load bar + done/assigned value."""

    def __init__(
        self,
        item: ForecastWorkItem,
        max_assigned: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ForecastWorkRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(
            f"{item.name}: {item.completed_today} of {item.assigned_today} cards done today"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(12)

        name_lbl = QLabel(item.name)
        name_lbl.setObjectName("ForecastWorkName")
        name_lbl.setFixedWidth(148)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        name_lbl.setToolTip(item.name)
        layout.addWidget(name_lbl)

        bar = QProgressBar()
        bar.setObjectName("ForecastWorkBar")
        bar.setRange(0, 100)
        bar.setValue(
            round(item.assigned_today * 100 / max_assigned) if max_assigned > 0 else 0
        )
        bar.setTextVisible(False)
        bar.setAccessibleName(f"Load: {item.assigned_today} cards assigned")
        layout.addWidget(bar, 1)

        value_lbl = QLabel(f"{item.completed_today} / {item.assigned_today}")
        value_lbl.setObjectName("ForecastWorkValue")
        value_lbl.setFixedWidth(64)
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(value_lbl)


class _ForecastLegend(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        lbl = QLabel("Legend:  Study · Complete · Rest · Due · Today")
        lbl.setObjectName("ForecastLegend")
        layout.addWidget(lbl)
        layout.addStretch(1)


class DeadlineForecastPanel(QWidget):
    """Left-side deadline forecast: word, signal, workload bars, calendar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DeadlineForecastPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 24)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def refresh(self, forecast: DeadlineForecast, palette: Palette) -> None:
        clear_layout(self._layout)

        self._layout.addWidget(self._title("Deadline forecast"))
        self._layout.addSpacing(14)

        # Word of the day
        self._layout.addWidget(self._section("Word of the day"))
        wod = QLabel(f"{forecast.word}  —  {forecast.word_definition}")
        wod.setObjectName("WordOfDayText")
        wod.setWordWrap(True)
        wod.setAccessibleName(
            f"Word of the day: {forecast.word}, meaning {forecast.word_definition}"
        )
        self._layout.addWidget(wod)
        self._layout.addSpacing(16)

        # Forecast signal
        signal_lbl = QLabel(forecast.signal)
        signal_lbl.setObjectName("ForecastSignal")
        signal_lbl.setWordWrap(True)
        signal_lbl.setAccessibleName(f"Forecast: {forecast.signal}")
        self._layout.addWidget(signal_lbl)
        self._layout.addSpacing(20)

        # Today's relative load
        load_hdr = QHBoxLayout()
        load_hdr.setContentsMargins(0, 0, 0, 0)
        load_hdr.addWidget(self._section("Today's relative load"))
        load_hdr.addStretch(1)
        if forecast.total_assigned > 0:
            total_lbl = QLabel(
                f"{forecast.total_completed} / {forecast.total_assigned} cards"
            )
            total_lbl.setObjectName("ForecastWorkTotal")
            total_lbl.setAccessibleName(
                f"{forecast.total_completed} of {forecast.total_assigned} "
                "cards completed today"
            )
            load_hdr.addWidget(total_lbl)
        self._layout.addLayout(load_hdr)
        self._layout.addSpacing(8)

        max_assigned = max((w.assigned_today for w in forecast.work_items), default=0)
        display = forecast.work_items[:5]

        if not display:
            empty_lbl = QLabel("No work items today.")
            empty_lbl.setObjectName("ForecastWorkTotal")
            self._layout.addWidget(empty_lbl)
        else:
            for item in display:
                self._layout.addWidget(_ForecastWorkRow(item, max_assigned))
            hidden = forecast.work_items[5:]
            if hidden:
                also = QLabel("Also tracking: " + ", ".join(w.name for w in hidden))
                also.setObjectName("ForecastWorkTotal")
                also.setWordWrap(True)
                self._layout.addWidget(also)

        self._layout.addSpacing(24)

        # Calendar pressure map
        self._layout.addWidget(self._section("Calendar pressure map"))
        self._layout.addSpacing(8)

        soonest = next(
            (cd.day for cd in forecast.calendar_days
             if cd.is_deadline and cd.day >= date.today()),
            None,
        )
        cal = ForecastCalendarWidget(
            days=forecast.calendar_days,
            soonest_deadline=soonest,
            today=date.today(),
            palette=palette,
        )
        self._layout.addWidget(cal)
        self._layout.addSpacing(10)
        self._layout.addWidget(_ForecastLegend())
        self._layout.addStretch(1)

    @staticmethod
    def _title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("ForecastTitle")
        return lbl

    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("ForecastSectionLabel")
        return lbl
