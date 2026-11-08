"""
GRUB Forge - Modern Workstation Design System (Catppuccin Mocha Dark)
Engineered for clean rendering across all DPI settings, eliminating glitchy textures,
dithering artifacts, and layout jumping.
"""

from __future__ import annotations

MAIN_STYLESHEET = """
/* ==============================================================================
   1. GLOBAL RESET & BASE WORKSPACE
   ============================================================================== */
QWidget {
    background-color: #11111b;
    color: #cdd6f4;
    font-family: -apple-system, BlinkMacSystemFont, "Cantarell", "Inter", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    outline: none;
    selection-background-color: #89b4fa;
    selection-color: #11111b;
}

QMainWindow {
    background-color: #11111b;
}

/* ==============================================================================
   2. SCROLLBARS (Slim Modern Floating Track)
   ============================================================================== */
QScrollBar:vertical {
    border: none;
    background: #11111b;
    width: 6px;
    margin: 0px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #313244;
    min-height: 24px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #45475a;
}

QScrollBar::handle:vertical:pressed {
    background: #89b4fa;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: #11111b;
    height: 6px;
    margin: 0px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal {
    background: #313244;
    min-width: 24px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal:hover {
    background: #45475a;
}

QScrollBar::handle:horizontal:pressed {
    background: #89b4fa;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

/* ==============================================================================
   3. PANELS, SURFACES & FRAMES
   ============================================================================== */
QFrame#topNavFrame {
    background-color: #181825;
    border-bottom: 1px solid #313244;
}

QFrame#inspectorPanel {
    background-color: #181825;
    border-right: 1px solid #313244;
}

QFrame#viewportContainer {
    background-color: #0c0c14;
    border: none;
}

QFrame#drawerHeader {
    background-color: #181825;
    border-top: 1px solid #313244;
}

QFrame#drawerBody {
    background-color: #0c0c14;
    border-top: 1px solid #232338;
}

/* Tooltip */
QToolTip {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 11px;
}

/* ==============================================================================
   4. BUTTONS & INTERACTIVE CONTROLS (CRISP & GLITCH-FREE)
   ============================================================================== */
QPushButton {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
    min-height: 22px;
    outline: none;
}

QPushButton:hover {
    background-color: #28293d;
    border-color: #45475a;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #313244;
    border-color: #89b4fa;
}

QPushButton:disabled {
    background-color: #181825;
    color: #585b70;
    border-color: #232338;
}

/* Primary Action Button (Solid Vibrant Accent, Crisp on all DPIs) */
QPushButton#primaryActionBtn {
    background-color: #89b4fa;
    color: #11111b;
    border: 1px solid #74c7ec;
    border-radius: 6px;
    font-weight: 700;
    font-size: 13px;
    padding: 8px 18px;
    letter-spacing: 0.3px;
    outline: none;
}

QPushButton#primaryActionBtn:hover {
    background-color: #b4befe;
    border-color: #cdd6f4;
    color: #11111b;
}

QPushButton#primaryActionBtn:pressed {
    background-color: #74c7ec;
    border-color: #89b4fa;
}

QPushButton#primaryActionBtn:disabled {
    background-color: #313244;
    color: #6c7086;
    border-color: #313244;
}

/* Secondary Button */
QPushButton#secondaryBtn {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    outline: none;
}

QPushButton#secondaryBtn:hover {
    background-color: #1e1e2e;
    border-color: #89b4fa;
    color: #89b4fa;
}

QPushButton#secondaryBtn:pressed {
    background-color: #313244;
    border-color: #89b4fa;
}

/* Danger Button */
QPushButton#dangerBtn {
    background-color: #181825;
    color: #f38ba8;
    border: 1px solid #45323a;
    border-radius: 6px;
    outline: none;
}

QPushButton#dangerBtn:hover {
    background-color: #3e2029;
    border-color: #f38ba8;
    color: #ffffff;
}

QPushButton#dangerBtn:pressed {
    background-color: #4a2430;
    border-color: #f38ba8;
}

/* Studio Workspace Navigation Tabs */
QPushButton#studioTabBtn {
    background-color: #181825;
    color: #a6adc8;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0px;
    padding: 10px 14px;
    font-weight: 600;
    font-size: 12px;
    outline: none;
}

QPushButton#studioTabBtn:hover {
    color: #cdd6f4;
    background-color: #1e1e2e;
}

QPushButton#studioTabBtn:checked, QPushButton#studioTabBtn[checked="true"] {
    color: #89b4fa;
    background-color: #1e1e2e;
    border-bottom: 2px solid #89b4fa;
}

/* Subtle Icon Buttons */
QPushButton#iconBtn {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px;
    color: #a6adc8;
    outline: none;
}

QPushButton#iconBtn:hover {
    background-color: #313244;
    color: #cdd6f4;
}

/* ==============================================================================
   5. INPUTS: LINE EDIT, SPINBOX, COMBOBOX
   ============================================================================== */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #11111b;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #89b4fa;
    background-color: #1e1e2e;
}

/* ComboBox */
QComboBox::drop-down {
    border: none;
    width: 24px;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    color: #89b4fa;
}

QComboBox QAbstractItemView {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    color: #cdd6f4;
    selection-background-color: #313244;
    selection-color: #89b4fa;
    padding: 4px;
    outline: none;
}

/* SpinBox Buttons */
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: #1e1e2e;
    border: none;
    width: 18px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background: #313244;
}

/* ==============================================================================
   6. SLIDERS (Precision Workstation Track)
   ============================================================================== */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #313244;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #89b4fa;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #cdd6f4;
    border: 2px solid #89b4fa;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #ffffff;
    border-color: #b4befe;
}

/* Checkbox */
QCheckBox {
    spacing: 8px;
    color: #cdd6f4;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #45475a;
    border-radius: 4px;
    background-color: #181825;
}

QCheckBox::indicator:hover {
    border-color: #89b4fa;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

/* ==============================================================================
   7. COLLAPSIBLE ACCORDION & CARDS
   ============================================================================== */
QFrame#accordionCard {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
}

QPushButton#accordionToggle {
    background-color: #181825;
    color: #cdd6f4;
    border: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.3px;
    outline: none;
}

QPushButton#accordionToggle:hover {
    background-color: #1e1e2e;
    color: #89b4fa;
}

QFrame#accordionContent {
    background-color: #181825;
    border-top: 1px solid #28293d;
    padding: 12px;
}

/* ==============================================================================
   8. TERMINAL CONSOLE
   ============================================================================== */
QPlainTextEdit#terminalView {
    background-color: #0c0c14;
    color: #a6adc8;
    border: none;
    font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
    font-size: 12px;
    line-height: 1.5;
    padding: 10px 14px;
}

/* Splitter */
QSplitter::handle {
    background-color: #232338;
}

QSplitter::handle:hover {
    background-color: #89b4fa;
}
"""
