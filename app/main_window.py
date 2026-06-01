"""The application shell: sidebar navigation + top bar + routed content stack.

This is intentionally mode-aware and token-driven — the sidebar width, spacing,
and every color/size come from the active :class:`Tokens`, so switching theme,
font scale, or mode reflows the whole shell with no per-widget hardcoding.
Every interactive element carries an accessible name (SR-01) and is reachable by
keyboard (KBD-01).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.context import AppContext
from app.navigation import DESCRIPTION, ICON, PRIMARY, TOOLS, Destination
from core.paths import AppPaths
from core.settings import Settings
from data.db import Database
from domain.accessibility.tts_service import TTSService
from domain.srs import Sm2Engine
from ui.theme.theme_controller import ThemeController
from ui.views.cards_view import CardsView
from ui.views.settings_view import SettingsView


class _NavButton(QPushButton):
    """A sidebar navigation button styled via the ``nav``/``active`` properties."""

    def __init__(self, destination: Destination) -> None:
        super().__init__(f"  {ICON[destination]}   {destination.title}")
        self.destination = destination
        self.setProperty("nav", True)
        self.setProperty("active", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"{destination.title} section")
        self.setAccessibleDescription(DESCRIPTION[destination])

    def set_active(self, active: bool) -> None:
        if self.property("active") == active:
            return
        self.setProperty("active", active)
        # Re-evaluate the stylesheet for the changed dynamic property.
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: Settings,
        theme: ThemeController,
        paths: AppPaths,
        db: Database | None = None,
        tts: TTSService | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._theme = theme
        self._paths = paths
        self._db = db
        self._tts = tts
        self._context = AppContext(db=db, engine=Sm2Engine(), settings=settings, tts=tts)
        self._nav_buttons: dict[Destination, _NavButton] = {}
        self._pages: dict[Destination, int] = {}

        self.setWindowTitle("StudyApp")
        self.resize(1040, 720)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._sidebar = self._build_sidebar()
        root.addWidget(self._sidebar)
        root.addWidget(self._build_main_area(), 1)
        self.setCentralWidget(central)

        theme.changed.connect(self._apply_density)
        self._apply_density()
        self._navigate(Destination.DASHBOARD)

    # -- construction -------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setAccessibleName("Primary navigation")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo = QLabel("📖  StudyApp")
        logo.setObjectName("Logo")
        layout.addWidget(logo)

        layout.addWidget(self._section_label("Main"))
        for dest in PRIMARY:
            layout.addWidget(self._nav_button(dest))

        layout.addWidget(self._section_label("Tools"))
        for dest in TOOLS:
            layout.addWidget(self._nav_button(dest))

        layout.addStretch(1)
        layout.addWidget(self._nav_button(Destination.SETTINGS))
        return sidebar

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("NavSection")
        return label

    def _nav_button(self, dest: Destination) -> _NavButton:
        button = _NavButton(dest)
        button.clicked.connect(lambda _=False, d=dest: self._navigate(d))
        self._nav_buttons[dest] = button
        return button

    def _build_main_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        topbar = QWidget()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(56)
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        self._title = QLabel(Destination.DASHBOARD.title)
        self._title.setObjectName("TopTitle")
        top_layout.addWidget(self._title)
        top_layout.addStretch(1)
        layout.addWidget(topbar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("Content")
        for dest in (*PRIMARY, *TOOLS, Destination.SETTINGS):
            self._pages[dest] = self._stack.addWidget(self._make_page(dest))
        layout.addWidget(self._stack, 1)
        return container

    def _make_page(self, dest: Destination) -> QWidget:
        if dest is Destination.SETTINGS:
            return SettingsView(self._settings, self._tts)
        if dest is Destination.CARDS:
            return CardsView(self._context)
        return self._placeholder_page(dest)

    def _placeholder_page(self, dest: Destination) -> QWidget:
        """A single-focus, generously spaced placeholder until the real view lands."""
        page = QWidget()
        page.setObjectName("Page")
        page.setAccessibleName(f"{dest.title} page")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(48, 48, 48, 48)
        outer.addStretch(1)

        title = QLabel(dest.title)
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel(f"{DESCRIPTION[dest]}\n\nComing in a later phase.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)

        outer.addWidget(title)
        outer.addSpacing(12)
        outer.addWidget(subtitle)
        outer.addStretch(2)
        return page

    # -- behavior -----------------------------------------------------------

    def _navigate(self, dest: Destination) -> None:
        self._stack.setCurrentIndex(self._pages[dest])
        self._title.setText(dest.title)
        for d, button in self._nav_buttons.items():
            button.set_active(d is dest)

    def _apply_density(self) -> None:
        self._sidebar.setFixedWidth(self._theme.tokens.density.sidebar_width)
