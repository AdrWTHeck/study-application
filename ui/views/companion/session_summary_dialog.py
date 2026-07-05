"""End-of-session summary: XP gained, companion state, encouragement."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from data.models.companion import CompanionState, XP_PER_LEVEL


class SessionSummaryDialog(QDialog):
    def __init__(
        self,
        companion: CompanionState,
        xp_gained: int,
        encouragement: str,
        before_avg: float | None = None,
        after_avg: float | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Session complete!")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 24, 28, 24)

        # Companion glyph + state.
        glyph = QLabel(companion.glyph)
        glyph.setObjectName("CompanionGlyph")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(glyph)

        name = companion.name or ("Your tree" if companion.kind == "tree" else "Your companion")
        state_lbl = QLabel(f"{name}  ·  Level {companion.level}  ·  {companion.growth_state.title()}")
        state_lbl.setObjectName("PageSubtitle")
        state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(state_lbl)

        # XP bar.
        xp_lbl = QLabel(f"+{xp_gained} XP this session")
        xp_lbl.setObjectName("FieldLabel")
        xp_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(xp_lbl)

        bar = QProgressBar()
        bar.setRange(0, companion.level * XP_PER_LEVEL)
        bar.setValue(companion.xp_in_current_level)
        bar.setFormat(f"{companion.xp_in_current_level} / {companion.level * XP_PER_LEVEL} XP")
        bar.setAccessibleName(
            f"XP progress: {companion.xp_in_current_level} of {companion.level * XP_PER_LEVEL}"
        )
        layout.addWidget(bar)

        # Confidence delta.
        if before_avg is not None and after_avg is not None:
            delta = after_avg - before_avg
            sign = "+" if delta >= 0 else ""
            conf_lbl = QLabel(
                f"Confidence: {before_avg:.1f} → {after_avg:.1f}  ({sign}{delta:.1f})"
            )
            conf_lbl.setObjectName("SettingsHint")
            conf_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(conf_lbl)

        # Encouragement message.
        enc_lbl = QLabel(encouragement)
        enc_lbl.setObjectName("PageSubtitle")
        enc_lbl.setWordWrap(True)
        enc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(enc_lbl)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
