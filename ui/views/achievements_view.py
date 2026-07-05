"""Achievements screen: a compact grid of rounded square tiles.

Each tile shows a symbol + title. Earned tiles get an adjustable gold border;
normal locked tiles show their goal/progress; rare hidden tiles show only a
locked mystery box until earned. Clicking a tile opens its details.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from domain.achievements.achievement_service import AchievementService, AchievementState
from ui.components.containers import themed_scroll_area

_COLUMNS = 4
_TILE_SIZE = 132


class AchievementTile(QWidget):
    """A rounded square tile: symbol + title, with locked/unlocked/hidden styling."""

    clicked = pyqtSignal(object)  # emits the AchievementState

    def __init__(self, state: AchievementState, border_color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self.setObjectName("AchievementTile")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("unlocked", state.is_unlocked)
        self.setProperty("hidden", state.is_hidden_locked)
        self.setProperty("rarity", state.rarity)
        self.setFixedSize(_TILE_SIZE, _TILE_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if state.is_unlocked:
            # Gold (adjustable) border for earned achievements.
            self.setStyleSheet(f"#AchievementTile {{ border: 2px solid {border_color}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hidden = state.is_hidden_locked
        symbol = QLabel("🔒" if hidden else state.symbol)
        symbol.setObjectName("AchievementSymbol")
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(symbol)

        title = QLabel("Hidden" if hidden else state.title)
        title.setObjectName("AchievementTileTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        layout.addWidget(title)

        if hidden:
            self.setAccessibleName("Hidden achievement, locked")
        else:
            status = "earned" if state.is_unlocked else f"locked, {state.progress}"
            self.setAccessibleName(f"{state.title}: {status}")

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        super().mouseReleaseEvent(event)
        self.clicked.emit(self._state)


class AchievementDetailDialog(QDialog):
    def __init__(self, state: AchievementState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        hidden = state.is_hidden_locked
        self.setWindowTitle("Achievement" if hidden else state.title)
        self.setObjectName("Page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(380, 280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        symbol = QLabel("🔒" if hidden else state.symbol)
        symbol.setObjectName("AchievementSymbol")
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(symbol)

        title = QLabel("Hidden achievement" if hidden else state.title)
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        if hidden:
            body = QLabel("A rare challenge. Keep studying to discover it.")
        else:
            body = QLabel(state.description)
        body.setObjectName("SettingsHint")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body)

        if not hidden:
            if state.is_unlocked:
                when = state.unlocked_at.strftime("%b %d, %Y") if state.unlocked_at else ""
                status = QLabel(f"✓ Earned on {when}")
            else:
                status = QLabel(f"Progress: {state.progress}")
            status.setObjectName("FieldLabel")
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(status)

            cat = QLabel(f"{state.category}  ·  {state.rarity.title()}")
            cat.setObjectName("SettingsHint")
            cat.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(cat)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addStretch(1)
        layout.addWidget(buttons)


class AchievementsView(QWidget):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._context = context
        self.setObjectName("Page")
        self.setAccessibleName("Achievements")

        scroll, self._body, self._layout = themed_scroll_area(
            margins=(40, 28, 40, 28), spacing=14,
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        title = QLabel("Achievements")
        title.setObjectName("PageTitle")
        self._layout.addWidget(title)

        self._summary = QLabel("")
        self._summary.setObjectName("SettingsHint")
        self._summary.setWordWrap(True)
        self._layout.addWidget(self._summary)

        self._grid_host = QWidget()
        self._grid_host.setObjectName("Page")
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(12)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._layout.addWidget(self._grid_host)
        self._layout.addStretch(1)

        self.refresh()

    def refresh(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if self._context.db is None:
            self._summary.setText("No database available.")
            return

        with self._context.db.session() as session:
            service = AchievementService(session)
            service.evaluate()
            achievements = service.list_achievements()

        earned = sum(1 for a in achievements if a.is_unlocked)
        self._summary.setText(
            f"{earned} of {len(achievements)} earned. "
            "Click a tile for details. Some rare achievements are hidden until earned."
        )

        border = self._context.settings.get("achievement_unlocked_border_color") or "#d4af37"
        for index, state in enumerate(achievements):
            tile = AchievementTile(state, border)
            tile.clicked.connect(self._show_detail)
            self._grid.addWidget(tile, index // _COLUMNS, index % _COLUMNS)

    def _show_detail(self, state: AchievementState) -> None:
        AchievementDetailDialog(state, self).exec()

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.refresh()
