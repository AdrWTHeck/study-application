"""Generic interactive controls: buttons, inputs, checkboxes, sliders, progress bars."""
from __future__ import annotations

from ui.theme.tokens import Tokens
from ui.theme.qss.primitives import join_rules, rule


def rules(tokens: Tokens) -> str:
    p = tokens.palette
    t = tokens.typography
    d = tokens.density
    pad_v = d.space(1.0)
    pad_h = d.space(1.5)
    body_pt = f"{t.size('body')}pt"

    return join_rules([
        # Buttons
        rule("QPushButton", {
            "background-color": p.bg_raised,
            "color": p.text_primary,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"{pad_v}px {pad_h}px",
            "min-height": f"{d.min_target}px",
            "font-size": body_pt,
        }),
        rule("QPushButton:hover", {
            "background-color": p.bg_hover,
            "border-color": p.accent,
        }),
        rule("QPushButton:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),
        rule("QPushButton:default", {
            "background-color": p.accent,
            "color": p.on_accent,
            "border-color": p.accent,
        }),

        # Primary call-to-action button — accent-filled, reusable across views.
        rule("QPushButton#PrimaryButton", {
            "background-color": p.accent,
            "color": p.on_accent,
            "border": f"1px solid {p.accent}",
            "font-weight": "600",
        }),
        rule("QPushButton#PrimaryButton:hover", {
            "background-color": p.accent_hover,
            "border-color": p.accent_hover,
        }),
        rule("QPushButton#PrimaryButton:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),
        rule("QPushButton#PrimaryButton:disabled", {
            "background-color": p.bg_raised,
            "color": p.text_dim,
            "border-color": p.border,
        }),

        # Ghost button — transparent secondary action (clay redesign).
        rule("QPushButton#GhostButton", {
            "background": "transparent",
            "border": f"1px solid {p.border}",
            "color": p.text_primary,
        }),
        rule("QPushButton#GhostButton:hover", {
            "background-color": p.bg_hover,
            "border-color": p.accent,
        }),
        rule("QPushButton#GhostButton:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),

        # Quick-pass button — warning-gold tint, distinct from the primary CTA.
        rule("QPushButton#QuickPassButton", {
            "background-color": p.warning_muted,
            "color": p.warning,
            "border": f"1px solid {p.warning}",
            "font-weight": "600",
        }),
        rule("QPushButton#QuickPassButton:hover", {
            "background-color": p.bg_hover,
            "border-color": p.warning,
        }),
        rule("QPushButton#QuickPassButton:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),

        # Review rating buttons — label + interval hint stacked inside; the
        # rating name is always text (VIS-03), colour is reinforcement only.
        rule("QPushButton#RatingButton", {
            "background-color": p.bg_raised,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
            "padding": f"{d.space(1)}px",
        }),
        rule("QPushButton#RatingButton:hover", {
            "background-color": p.bg_hover,
        }),
        rule("QPushButton#RatingButton:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),
        rule('QPushButton#RatingButton[rating="again"]', {"border-left": f"3px solid {p.danger}"}),
        rule('QPushButton#RatingButton[rating="hard"]', {"border-left": f"3px solid {p.warning}"}),
        rule('QPushButton#RatingButton[rating="good"]', {"border-left": f"3px solid {p.success}"}),
        rule('QPushButton#RatingButton[rating="easy"]', {"border-left": f"3px solid {p.info}"}),
        rule("QLabel#RatingLabel", {
            "color": p.text_primary,
            "font-size": body_pt,
            "font-weight": "700",
            "background": "transparent",
        }),
        rule("QLabel#RatingInterval", {
            "color": p.text_dim,
            "font-family": f'"{t.mono_family}"',
            "font-size": f"{t.size('caption')}pt",
            "background": "transparent",
        }),

        # Full-width quiz answer buttons (the whole option is the button).
        rule("QPushButton#AnswerOption", {
            "background-color": p.bg_raised,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius}px",
            "padding": "0px",
            "text-align": "left",
        }),
        rule("QPushButton#AnswerOption:hover", {
            "background-color": p.bg_hover,
            "border-color": p.accent,
        }),
        rule("QPushButton#AnswerOption:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),
        rule("QLabel#AnswerNumber", {
            "background-color": p.accent,
            "color": p.on_accent,
            "border-radius": f"{d.radius_sm}px",
            "padding": f"0px {d.space(0.75)}px",
            "font-weight": "700",
            "min-width": f"{d.min_target}px",
            "qproperty-alignment": "AlignCenter",
        }),
        rule("QLabel#AnswerText", {
            "color": p.text_primary,
            "font-size": body_pt,
            "background-color": "transparent",
        }),

        # Text inputs
        rule(
            "QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QAbstractSpinBox, "
            "QDateEdit, QTimeEdit, QDateTimeEdit, QPlainTextEdit, QTextEdit",
            {
                "background-color": p.bg_raised,
                "color": p.text_primary,
                "border": f"1px solid {p.border}",
                "border-radius": f"{d.radius_sm}px",
                "padding": f"{d.space(0.75)}px {pad_v}px",
                "min-height": f"{d.min_target}px",
                "font-size": body_pt,
                "selection-background-color": p.accent,
                "selection-color": p.on_accent,
            },
        ),
        rule(
            "QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, "
            "QAbstractSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, "
            "QDateTimeEdit:focus, QPlainTextEdit:focus, QTextEdit:focus",
            {"border": f"{d.focus_width}px solid {p.focus}"},
        ),

        # Checkbox
        rule("QCheckBox", {
            "color": p.text_primary,
            "font-size": body_pt,
            "spacing": f"{d.space(1)}px",
            "min-height": f"{d.min_target}px",
        }),
        rule("QCheckBox:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
            "border-radius": f"{d.radius_sm}px",
        }),

        # Radio button — mirrors the checkbox treatment for consistency.
        rule("QRadioButton", {
            "color": p.text_primary,
            "font-size": body_pt,
            "spacing": f"{d.space(1)}px",
            "min-height": f"{d.min_target}px",
        }),
        rule("QRadioButton:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
            "border-radius": f"{d.radius_sm}px",
        }),

        # Converter status line — semantic colour driven by a dynamic property.
        rule("QLabel#ConverterStatus", {
            "color": p.text_secondary,
            "font-size": body_pt,
        }),
        rule('QLabel#ConverterStatus[state="running"]', {"color": p.text_secondary}),
        rule('QLabel#ConverterStatus[state="success"]', {"color": p.success, "font-weight": "600"}),
        rule('QLabel#ConverterStatus[state="error"]', {"color": p.danger, "font-weight": "600"}),

        # Reader annotation filter chip ("All" text chip; the per-colour swatch
        # chips set their own fill inline — that colour is data — but inherit
        # this rule's border/radius/checked state so they still themed correctly).
        rule("QPushButton#HlFilterChip", {
            "background-color": p.bg_raised,
            "color": p.text_secondary,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "padding": f"0px {d.space(1)}px",
            "font-size": f"{t.size('caption')}pt",
        }),
        rule("QPushButton#HlFilterChip:checked", {
            "background-color": p.accent_muted,
            "border": f"1px solid {p.accent}",
            "color": p.text_primary,
        }),
        rule("QPushButton#HlFilterChip:focus", {
            "border": f"{d.focus_width}px solid {p.focus}",
        }),

        # Progress bar (generic; page-specific bars override via object name)
        rule("QProgressBar", {
            "background-color": p.bg_raised,
            "color": p.text_primary,
            "border": f"1px solid {p.border}",
            "border-radius": f"{d.radius_sm}px",
            "text-align": "left",
            "padding-left": f"{d.space(1)}px",
            "min-height": f"{d.space(4)}px",
            "font-size": body_pt,
        }),
        rule("QProgressBar::chunk", {
            "background-color": p.accent,
            "border-radius": f"{d.radius_sm}px",
        }),

        # Slider
        rule("QSlider::groove:horizontal", {
            "border": f"1px solid {p.border}",
            "height": "6px",
            "background-color": p.bg_raised,
            "border-radius": "3px",
        }),
        rule("QSlider::handle:horizontal", {
            "background-color": p.accent,
            "border": f"1px solid {p.accent_hover}",
            "width": f"{d.space(2.5)}px",
            "height": f"{d.space(2.5)}px",
            "margin": f"-{d.space(1)}px 0px",
            "border-radius": f"{d.space(1.25)}px",
        }),
        rule("QSlider::handle:horizontal:hover", {
            "background-color": p.accent_hover,
        }),
        rule("QSlider::sub-page:horizontal", {
            "background-color": p.accent_muted,
            "border-radius": "3px",
        }),
    ])
