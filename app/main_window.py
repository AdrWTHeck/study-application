"""The application shell: sidebar navigation + top bar + routed content stack.

This is intentionally mode-aware and token-driven — the sidebar width, spacing,
and every color/size come from the active :class:`Tokens`, so switching theme,
font scale, or mode reflows the whole shell with no per-widget hardcoding.
Every interactive element carries an accessible name (SR-01) and is reachable by
keyboard (KBD-01).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
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
from domain.dictionary.service import DictionaryService
from domain.srs import make_engine
from ui.theme.theme_controller import ThemeController
from ui.views.achievements_view import AchievementsView
from ui.views.cards_view import CardsView
from ui.views.converter_view import ConverterView
from ui.views.dashboard_view import DashboardView
from ui.views.deadline_view import DeadlineView
from ui.views.library_view import LibraryView
from ui.views.search_view import SearchView
from ui.views.settings_view import SettingsView
from ui.views.tests_view import TestsView


# Per-page horizontal space policy: workspace pages fill the window, while
# reading and form pages stay a calm centred column. Pages not listed here
# default to "balanced".
_PAGE_WIDTH_CLASS: dict[Destination, str] = {
    Destination.LIBRARY: "full",
    Destination.DEADLINES: "full",
    Destination.CARDS: "wide",
    Destination.TESTS: "wide",
    Destination.SEARCH: "wide",
    Destination.DASHBOARD: "balanced",
    Destination.ACHIEVEMENTS: "balanced",
    Destination.CONVERTER: "focused",
    Destination.SETTINGS: "focused",
}


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
        _style = self.style()
        if _style is not None:
            _style.unpolish(self)
            _style.polish(self)


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
        dictionary = DictionaryService(paths.dictionary_path) if paths is not None else None
        self._context = AppContext(
            db=db, engine=make_engine(settings.get("scheduler")),
            settings=settings, tts=tts, dictionary=dictionary,
            theme=theme, palette=theme.tokens.palette,
        )
        self._nav_buttons: dict[Destination, _NavButton] = {}
        self._pages: dict[Destination, int] = {}
        self._search_view: SearchView | None = None
        self._current_dest: Destination = Destination.DASHBOARD

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

        # Global Ctrl+F → app-wide search (KBD-01 / Search destination).
        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        find_shortcut.activated.connect(self._open_search)

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
        # Add a small horizontal gutter so page content isn't flush against
        # the app edge (improves readability on startup and all pages).
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(0)

        self._topbar = QWidget()
        self._topbar.setObjectName("TopBar")
        self._topbar.setFixedHeight(self._theme.tokens.layout.topbar_height)
        top_layout = QHBoxLayout(self._topbar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        self._title = QLabel(Destination.DASHBOARD.title)
        self._title.setObjectName("TopTitle")
        top_layout.addWidget(self._title)
        top_layout.addStretch(1)
        # Mono mode badge (ACC/ADV) — quiet chrome from the clay redesign.
        self._mode_badge = QLabel("")
        self._mode_badge.setObjectName("ModeBadge")
        self._refresh_mode_badge()
        top_layout.addWidget(self._mode_badge)
        layout.addWidget(self._topbar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("Content")
        for dest in (*PRIMARY, *TOOLS, Destination.SETTINGS):  # TOOLS already includes CONVERTER
            page = self._make_page(dest)
            idx = self._stack.addWidget(page)
            self._pages[dest] = idx
            # Bind theme change to the page so views update when tokens change.
            try:
                theme_ctrl = self._context.theme
            except Exception:
                theme_ctrl = None
            if theme_ctrl is not None:
                def _on_theme_change(p=page):
                    # Prefer explicit handler if view exposes it.
                    _handler = getattr(p, "_on_theme_changed", None)
                    if _handler is not None:
                        try:
                            _handler()
                            return
                        except Exception:
                            pass
                    # Fallback to a generic update call.
                    try:
                        p.update()
                    except Exception:
                        pass
                theme_ctrl.changed.connect(_on_theme_change)

        # Center the content stack and constrain its maximum width so each
        # page reads like a centered document rather than edge-to-edge.
        center_wrap = QWidget()
        center_layout = QHBoxLayout(center_wrap)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addStretch(1)

        self._content_container = QWidget()
        self._content_container.setObjectName("ContentContainer")
        # Per-page width is applied by _apply_content_width(); start balanced so
        # the first paint is sensible before navigation runs.
        self._content_container.setMaximumWidth(self._theme.tokens.layout.width_balanced)
        content_v = QVBoxLayout(self._content_container)
        content_v.setContentsMargins(0, 0, 0, 0)
        content_v.setSpacing(0)
        content_v.addWidget(self._stack)

        center_layout.addWidget(self._content_container)
        center_layout.addStretch(1)
        layout.addWidget(center_wrap, 1)
        return container

    def _make_page(self, dest: Destination) -> QWidget:
        if dest is Destination.SETTINGS:
            return SettingsView(self._settings, self._tts, context=self._context)
        if dest is Destination.CARDS:
            return CardsView(self._context)
        if dest is Destination.LIBRARY:
            return LibraryView(self._context)
        if dest is Destination.TESTS:
            return TestsView(self._context, navigate=self._navigate)
        if dest is Destination.DASHBOARD:
            return DashboardView(self._context, navigate=self._navigate)
        if dest is Destination.DEADLINES:
            return DeadlineView(self._context, navigate=self._navigate)
        if dest is Destination.ACHIEVEMENTS:
            return AchievementsView(self._context)
        if dest is Destination.SEARCH:
            self._search_view = SearchView(self._context, navigate=self._navigate)
            return self._search_view
        if dest is Destination.CONVERTER:
            return ConverterView(self._context)
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
        self._current_dest = dest
        self._stack.setCurrentIndex(self._pages[dest])
        self._title.setText(dest.title)
        self._apply_content_width()
        for d, button in self._nav_buttons.items():
            button.set_active(d is dest)

    def _open_search(self) -> None:
        self._navigate(Destination.SEARCH)
        if self._search_view is not None:
            self._search_view.focus_search()

    def _apply_content_width(self) -> None:
        """Constrain the centred content to the current page's width class.

        Workspace pages (Library, Deadlines) fill the window; reading/form pages
        (Settings) stay a calm centred column. Re-run on navigation and on theme
        changes so a density switch reflows widths too.
        """
        width_class = _PAGE_WIDTH_CLASS.get(self._current_dest, "balanced")
        self._content_container.setMaximumWidth(
            self._theme.tokens.layout.content_width(width_class)
        )

    def _apply_density(self) -> None:
        tokens = self._theme.tokens
        self._sidebar.setFixedWidth(tokens.density.sidebar_width)
        self._topbar.setFixedHeight(tokens.layout.topbar_height)
        self._context.palette = tokens.palette
        self._refresh_mode_badge()
        self._apply_content_width()

    def _refresh_mode_badge(self) -> None:
        """Keep the topbar ACC/ADV badge in sync with the dual-mode setting."""
        if not hasattr(self, "_mode_badge"):
            return
        advanced = self._context.settings.get("mode") == "advanced"
        self._mode_badge.setText("ADV" if advanced else "ACC")
        self._mode_badge.setAccessibleName(
            "Advanced mode active" if advanced else "Accessibility mode active"
        )
