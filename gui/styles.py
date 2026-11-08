"""
GRUB Forge - Production-Grade QSS Design System
Catppuccin Mocha & Slate Dark Mode aesthetic tailored for professional workstation UIs
(Blender / DaVinci Resolve inspired dark theme).
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
   4. BUTTONS & INTERACTIVE CONTROLS
   ============================================================================== */
QPushButton {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #313244;
    border-color: #45475a;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #45475a;
    border-color: #585b70;
}

QPushButton:disabled {
    background-color: #181825;
    color: #585b70;
    border-color: #232338;
}

/* Primary Action Button (Workstation Accent) */
QPushButton#primaryActionBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #89b4fa, stop:1 #74c7ec);
    color: #11111b;
    border: 1px solid #89b4fa;
    border-radius: 6px;
    font-weight: 700;
    font-size: 13px;
    padding: 8px 20px;
    letter-spacing: 0.3px;
}

QPushButton#primaryActionBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b4befe, stop:1 #89b4fa);
    border-color: #b4befe;
}

QPushButton#primaryActionBtn:pressed {
    background-color: #74c7ec;
}

QPushButton#primaryActionBtn:disabled {
    background: #313244;
    color: #6c7086;
    border-color: #313244;
}

/* Secondary & Danger Buttons */
QPushButton#secondaryBtn {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
}

QPushButton#secondaryBtn:hover {
    background-color: #1e1e2e;
    border-color: #89b4fa;
    color: #89b4fa;
}

QPushButton#dangerBtn {
    background-color: #181825;
    color: #f38ba8;
    border: 1px solid #45323a;
}

QPushButton#dangerBtn:hover {
    background-color: #3e2029;
    border-color: #f38ba8;
    color: #ffffff;
}

/* Subtle Icon Buttons */
QPushButton#iconBtn {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px;
    color: #a6adc8;
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

/* ComboBox Custom Arrow */
QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #89b4fa;
    width: 0px;
    height: 0px;
    margin-right: 8px;
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
    width: 16px;
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
    box-shadow: 0 0 6px #89b4fa;
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
