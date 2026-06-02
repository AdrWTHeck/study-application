"""CardListView — browse cards in a deck; launch review session or CRUD."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from services.cards.audio_service import AudioService
from services.cards.card_service import CardService
from services.cards.deck_service import DeckService
from ui.components.deck_selector import DeckSelector


class CardListView(QWidget):
    """Shows all cards for the selected deck with CRUD actions.

    Emits start_session(deck_id) to notify the parent to switch
    to CardReviewView.
    """

    start_session = pyqtSignal(int)       # deck_id
    promote_requested = pyqtSignal(int)   # card_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._svc = CardService()
        self._audio_svc = AudioService()
        self._deck_id: int = -1
        self._card_ids: list[int] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._deck_sel = DeckSelector("card", label="Deck:")
        self._deck_sel.deck_changed.connect(self._on_deck_changed)
        layout.addWidget(self._deck_sel)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("New",     self._new_card),
            ("Edit",    self._edit_card),
            ("Delete",  self._delete_card),
            ("Move",    self._move_card),
            ("Promote", self._promote_card),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
            setattr(self, f"_btn_{label.lower()}", btn)

        layout.addLayout(btn_row)

        self._start_btn = QPushButton("Start Review Session")
        self._start_btn.clicked.connect(self._start_session)
        layout.addWidget(self._start_btn)

        self._status = QLabel("")
        layout.addWidget(self._status)

    # ------------------------------------------------------------------
    # Deck change
    # ------------------------------------------------------------------

    def _on_deck_changed(self, deck_id: int) -> None:
        self._deck_id = deck_id
        self._refresh()

    def _refresh(self) -> None:
        self._list.clear()
        self._card_ids = []
        if self._deck_id < 0:
            return
        db = __import__("models.base", fromlist=["get_session"]).get_session()
        try:
            from repositories.card_repository import CardRepository
            cards = CardRepository(db).get_by_deck(self._deck_id)
            for card in cards:
                item = QListWidgetItem(
                    f"[{card.category.upper()}] "
                    f"{(card.front_text or '')[:60]}"
                )
                self._list.addItem(item)
                self._card_ids.append(card.id)
        finally:
            db.close()
        self._status.setText(f"{len(self._card_ids)} cards")

    def _selected_card_id(self) -> int | None:
        idx = self._list.currentRow()
        return self._card_ids[idx] if 0 <= idx < len(self._card_ids) else None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _new_card(self) -> None:
        if self._deck_id < 0:
            return
        from ui.views.card_form_view import CardFormView
        dlg = CardFormView(self._deck_id, self._svc, self._audio_svc, parent=self)
        dlg.card_saved.connect(lambda _: self._refresh())
        dlg.exec()

    def _edit_card(self) -> None:
        cid = self._selected_card_id()
        if cid is None:
            return
        from ui.views.card_form_view import CardFormView
        dlg = CardFormView(self._deck_id, self._svc, self._audio_svc,
                           card_id=cid, parent=self)
        dlg.card_saved.connect(lambda _: self._refresh())
        dlg.exec()

    def _delete_card(self) -> None:
        cid = self._selected_card_id()
        if cid is None:
            return
        ans = QMessageBox.question(self, "Delete Card",
                                   "Delete this card permanently?")
        if ans == QMessageBox.StandardButton.Yes:
            self._svc.delete(cid)
            self._refresh()

    def _move_card(self) -> None:
        cid = self._selected_card_id()
        if cid is None:
            return
        from PyQt6.QtWidgets import QInputDialog
        decks = DeckService().get_all("card")
        names = [d.name for d in decks]
        name, ok = QInputDialog.getItem(self, "Move Card", "Target deck:", names, 0, False)
        if ok:
            target = next((d.id for d in decks if d.name == name), None)
            if target:
                self._svc.move(cid, target)
                self._refresh()

    def _promote_card(self) -> None:
        cid = self._selected_card_id()
        if cid is None:
            return
        q = self._svc.promote_to_question(cid)
        if q:
            QMessageBox.information(self, "Promoted",
                                    f"Card promoted to question #{q.id}.")
            self.promote_requested.emit(cid)
        else:
            QMessageBox.warning(self, "Promote Failed",
                                "Card must have both front and back text.")

    def _start_session(self) -> None:
        if self._deck_id >= 0:
            self.start_session.emit(self._deck_id)

    def refresh_deck_list(self) -> None:
        self._deck_sel.refresh()
