"""MainWindow — sidebar navigation + stacked pages for all views."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QDockWidget, QHBoxLayout, QLabel, QListWidget,
    QMainWindow, QMessageBox, QSplitter,
    QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from services.core.app_settings import AppSettings
from services.accessibility.dictionary_service import DictionaryService
from services.accessibility.tts_service import TTSService
from services.cards.audio_service import AudioService
from ui.components.dictionary_panel import DictionaryPanel
from ui.theme.style_manager import StyleManager
from ui.views.card_list_view import CardListView
from ui.views.card_review_view import CardReviewView
from ui.views.preferences_view import PreferencesView
from ui.views.question_list_view import QuestionListView
from ui.views.quiz_session_view import QuizSessionView
from ui.views.source_library_view import SourceLibraryView
from ui.views.test_results_view import TestResultsView

# Page indices in the stacked widget
_PAGE_LIBRARY  = 0
_PAGE_CARDS    = 1
_PAGE_TESTS    = 2
_PAGE_PREFS    = 3

_NAV_LABELS = ["Library", "Cards", "Tests", "Settings"]


class _CardsPage(QWidget):
    """Cards sub-navigator: list ↔ review session."""

    def __init__(self, tts: TTSService, audio_svc: AudioService,
                 parent=None) -> None:
        super().__init__(parent)
        self._stack = QStackedWidget()
        self._list_view = CardListView()
        self._review_view = CardReviewView(tts, audio_svc)

        self._stack.addWidget(self._list_view)   # 0
        self._stack.addWidget(self._review_view) # 1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._list_view.start_session.connect(self._start_review)
        self._review_view.session_finished.connect(self._on_session_done)

    def _start_review(self, deck_id: int) -> None:
        self._review_view.start_session(deck_id)
        self._stack.setCurrentIndex(1)

    def _on_session_done(self) -> None:
        self._list_view._refresh()
        self._stack.setCurrentIndex(0)


class _TestsPage(QWidget):
    """Tests sub-navigator: question list → session → results."""

    def __init__(self, tts: TTSService, parent=None) -> None:
        super().__init__(parent)
        self._stack = QStackedWidget()
        self._list_view = QuestionListView()
        self._session_view = QuizSessionView(tts)
        self._results_view = TestResultsView()

        self._stack.addWidget(self._list_view)    # 0
        self._stack.addWidget(self._session_view) # 1
        self._stack.addWidget(self._results_view) # 2

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

        self._list_view.start_session.connect(self._start_session)
        self._session_view.session_finished.connect(self._on_session_done)
        self._results_view.back_requested.connect(self._back_to_list)
        self._results_view.drill_down_started.connect(self._resume_session)

    def _start_session(self, deck_id: int, count: int) -> None:
        self._session_view.start_session(deck_id, count)
        self._stack.setCurrentIndex(1)

    def _resume_session(self, session_id: int) -> None:
        self._session_view.resume_session(session_id)
        self._stack.setCurrentIndex(1)

    def _on_session_done(self, session_id: int) -> None:
        self._results_view.show_results(session_id)
        self._stack.setCurrentIndex(2)

    def _back_to_list(self) -> None:
        self._list_view._refresh()
        self._stack.setCurrentIndex(0)


class MainWindow(QMainWindow):
    """Application main window.

    Layout:
        ┌──────────────┬─────────────────────────────┐
        │  Nav sidebar │  Page stack                 │
        │  (QListWidget│  Library / Cards / Tests /  │
        │   ~180 px)   │  Settings                   │
        └──────────────┴─────────────────────────────┘
        Status bar at bottom.
        Dictionary panel as a right QDockWidget (Ctrl+D).
    """

    def __init__(self, style_manager: StyleManager,
                 pending_sessions: list | None = None) -> None:
        super().__init__()
        self._settings = AppSettings.get_instance()
        self._style_mgr = style_manager
        self._tts = TTSService()
        self._audio_svc = AudioService()
        self._dict_svc = DictionaryService()

        self.setWindowTitle("Study App")
        self.setMinimumSize(900, 620)
        self.resize(1100, 700)

        self._build_ui()
        self._build_menu()
        self._build_dict_panel()
        self._apply_shortcut()

        self._settings.register(self._on_settings_changed)

        if pending_sessions:
            self._offer_resume(pending_sessions)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self._nav = QListWidget()
        self._nav.setFixedWidth(160)
        self._nav.setFrameShape(QListWidget.Shape.NoFrame)
        for label in _NAV_LABELS:
            self._nav.addItem(label)
        self._nav.currentRowChanged.connect(self._switch_page)

        # Page stack
        self._stack = QStackedWidget()
        self._library_page = SourceLibraryView()
        self._cards_page   = _CardsPage(self._tts, self._audio_svc)
        self._tests_page   = _TestsPage(self._tts)
        self._prefs_page   = PreferencesView(self._tts)

        for page in (self._library_page, self._cards_page,
                     self._tests_page, self._prefs_page):
            self._stack.addWidget(page)

        root.addWidget(self._nav)
        root.addWidget(self._stack)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        self._nav.setCurrentRow(0)

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        # View menu
        view_menu = menu_bar.addMenu("View")
        self._dict_action = QAction("Dictionary Panel", self, checkable=True)
        self._dict_action.setShortcut(
            QKeySequence(self._settings.dictionary_shortcut)
        )
        self._dict_action.triggered.connect(self._toggle_dict_panel)
        view_menu.addAction(self._dict_action)

        view_menu.addSeparator()
        for i, label in enumerate(_NAV_LABELS):
            act = QAction(label, self)
            act.triggered.connect(lambda _, idx=i: self._nav.setCurrentRow(idx))
            view_menu.addAction(act)

        # Help menu
        help_menu = menu_bar.addMenu("Help")
        about_act = QAction("About", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_dict_panel(self) -> None:
        self._dict_panel = DictionaryPanel(self._dict_svc, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dict_panel)
        self._dict_panel.hide()
        self._dict_panel.visibilityChanged.connect(
            lambda v: self._dict_action.setChecked(v)
        )

    def _apply_shortcut(self) -> None:
        self._dict_action.setShortcut(
            QKeySequence(self._settings.dictionary_shortcut)
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _switch_page(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        self._status_bar.showMessage(_NAV_LABELS[idx] if 0 <= idx < len(_NAV_LABELS) else "")

    # ------------------------------------------------------------------
    # Dictionary
    # ------------------------------------------------------------------

    def _toggle_dict_panel(self, checked: bool) -> None:
        if checked:
            self._dict_panel.show()
        else:
            self._dict_panel.hide()

    def look_up_word(self, word: str) -> None:
        self._dict_panel.look_up(word)
        self._dict_panel.show()
        self._dict_action.setChecked(True)

    # ------------------------------------------------------------------
    # Settings observer
    # ------------------------------------------------------------------

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._apply_shortcut()

    # ------------------------------------------------------------------
    # Pending session offer
    # ------------------------------------------------------------------

    def _offer_resume(self, sessions: list) -> None:
        if not sessions:
            return
        msg = (
            f"{len(sessions)} in-progress session(s) found.\n"
            "Discard them and start fresh?"
        )
        ans = QMessageBox.question(self, "Resume Sessions", msg,
                                   QMessageBox.StandardButton.Yes
                                   | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            from services.quiz.test_session_controller import TestSessionController
            ctrl = TestSessionController()
            for s in sessions:
                ctrl.discard(s.id)

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "About Study App",
            "Study App — offline-first flashcard & quiz application.\n"
            "Built with PyQt6 + SQLAlchemy + NLTK."
        )
