"""Code editor and center panel widgets."""

from __future__ import annotations

import json
import os

from PyQt6.QtCore import QThread, Qt, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QDoubleSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from kronos.native import create_python_highlighter
from kronos.ui.center.simulink.canvas import SimulinkCanvas
from kronos.ui.center.simulink.simulator import DiagramSimulator
from kronos.ui.center.simulink.block_param_dialog import BlockParamDialog

try:
    from PyQt6.Qsci import QsciLexerPython, QsciScintilla
    _QSCI_AVAILABLE = True
except Exception:
    QsciLexerPython = None
    QsciScintilla = None
    _QSCI_AVAILABLE = False

DEFAULT_CODE = ""


if _QSCI_AVAILABLE:

    class CodeEditor(QsciScintilla):
        """Python code editor with syntax highlighting."""

        def __init__(self) -> None:
            super().__init__()
            self._lexer: QsciLexerPython | None = None
            self._configure_editor()
            self.setText(DEFAULT_CODE)

        def _configure_editor(self) -> None:
            font = self._select_font()
            self.setFont(font)
            self.setMarginsFont(font)

            # Keep a strong reference so lexer survives GC and can be rethemed.
            self._lexer = QsciLexerPython(self)
            self.setLexer(self._lexer)
            self.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
            self.setMarginWidth(0, "0000")
            self.setCaretLineVisible(True)
            self.set_theme(True)
            self.setCaretLineBackgroundColor(QColor("#13192a"))

            self.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)
            self.setAutoCompletionThreshold(2)

            self.setIndentationsUseTabs(False)
            self.setIndentationWidth(4)
            self.setTabWidth(4)
            self.setIndentationGuides(True)
            self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
            self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle)
            self.setFoldMarginColors(QColor("#161b22"), QColor("#161b22"))
            self.setCaretWidth(2)
            self.setEdgeMode(QsciScintilla.EdgeMode.EdgeLine)
            self.setEdgeColumn(100)
            self.setEdgeColor(QColor("#30363d"))

        @staticmethod
        def _to_scintilla_color(color: QColor) -> int:
            """Convert QColor to Scintilla packed color integer."""
            return color.red() | (color.green() << 8) | (color.blue() << 16)

        @staticmethod
        def _set_lexer_style_color(lexer: QsciLexerPython | None, style_name: str, hex_color: str) -> None:
            if lexer is None:
                return
            style_id = getattr(QsciLexerPython, style_name, None)
            if style_id is None:
                return
            lexer.setColor(QColor(hex_color), style_id)

        def _apply_scintilla_defaults(self, fg_hex: str, bg_hex: str) -> None:
            fg = QColor(fg_hex)
            bg = QColor(bg_hex)
            self.SendScintilla(
                QsciScintilla.SCI_STYLESETFORE,
                QsciScintilla.STYLE_DEFAULT,
                self._to_scintilla_color(fg),
            )
            self.SendScintilla(
                QsciScintilla.SCI_STYLESETBACK,
                QsciScintilla.STYLE_DEFAULT,
                self._to_scintilla_color(bg),
            )
            self.SendScintilla(QsciScintilla.SCI_STYLECLEARALL)

        def set_theme(self, is_dark: bool) -> None:
            lexer = self._lexer or self.lexer()
            if is_dark:
                self._apply_scintilla_defaults("#c8ccd4", "#0e1117")
                if lexer:
                    lexer.setDefaultColor(QColor("#c8ccd4"))
                    lexer.setDefaultPaper(QColor("#0e1117"))
                    lexer.setPaper(QColor("#0e1117"), -1)
                    self._set_lexer_style_color(lexer, "Default", "#c8ccd4")
                    self._set_lexer_style_color(lexer, "Identifier", "#c8ccd4")
                    self._set_lexer_style_color(lexer, "Keyword", "#c678dd")
                    self._set_lexer_style_color(lexer, "ClassName", "#61afef")
                    self._set_lexer_style_color(lexer, "FunctionMethodName", "#61afef")
                    self._set_lexer_style_color(lexer, "DoubleQuotedString", "#98c379")
                    self._set_lexer_style_color(lexer, "SingleQuotedString", "#98c379")
                    self._set_lexer_style_color(lexer, "TripleSingleQuotedString", "#98c379")
                    self._set_lexer_style_color(lexer, "TripleDoubleQuotedString", "#98c379")
                    self._set_lexer_style_color(lexer, "DoubleQuotedFString", "#98c379")
                    self._set_lexer_style_color(lexer, "SingleQuotedFString", "#98c379")
                    self._set_lexer_style_color(lexer, "TripleSingleQuotedFString", "#98c379")
                    self._set_lexer_style_color(lexer, "TripleDoubleQuotedFString", "#98c379")
                    self._set_lexer_style_color(lexer, "Number", "#e5c07b")
                    self._set_lexer_style_color(lexer, "Comment", "#6b7280")
                    self._set_lexer_style_color(lexer, "CommentBlock", "#6b7280")
                    self._set_lexer_style_color(lexer, "Operator", "#56b6c2")
                    self._set_lexer_style_color(lexer, "Decorator", "#d946ef")
                    self._set_lexer_style_color(lexer, "HighlightedIdentifier", "#f59e0b")
                    self._set_lexer_style_color(lexer, "UnclosedString", "#ef4444")
                if hasattr(self, "setPaper"):
                    self.setPaper(QColor("#0e1117"))
                if hasattr(self, "setColor"):
                    self.setColor(QColor("#c8ccd4"))
                self.setMarginsBackgroundColor(QColor("#0b0e15"))
                self.setMarginsForegroundColor(QColor("#3a4050"))
                self.setCaretForegroundColor(QColor("#c8ccd4"))
                self.setCaretLineBackgroundColor(QColor("#13192a"))
                self.setFoldMarginColors(QColor("#161b22"), QColor("#161b22"))
                self.setEdgeColor(QColor("#30363d"))
                if hasattr(self, "setSelectionBackgroundColor"):
                    self.setSelectionBackgroundColor(QColor("#264f78"))
                if hasattr(self, "setSelectionForegroundColor"):
                    self.setSelectionForegroundColor(QColor("#ffffff"))
            else:
                self._apply_scintilla_defaults("#111827", "#ffffff")
                if lexer:
                    lexer.setDefaultColor(QColor("#111827"))
                    lexer.setDefaultPaper(QColor("#ffffff"))
                    lexer.setPaper(QColor("#ffffff"), -1)
                    self._set_lexer_style_color(lexer, "Default", "#111827")
                    self._set_lexer_style_color(lexer, "Identifier", "#111827")
                    self._set_lexer_style_color(lexer, "Keyword", "#7c3aed")
                    self._set_lexer_style_color(lexer, "ClassName", "#2563eb")
                    self._set_lexer_style_color(lexer, "FunctionMethodName", "#0369a1")
                    self._set_lexer_style_color(lexer, "DoubleQuotedString", "#166534")
                    self._set_lexer_style_color(lexer, "SingleQuotedString", "#166534")
                    self._set_lexer_style_color(lexer, "TripleSingleQuotedString", "#166534")
                    self._set_lexer_style_color(lexer, "TripleDoubleQuotedString", "#166534")
                    self._set_lexer_style_color(lexer, "DoubleQuotedFString", "#166534")
                    self._set_lexer_style_color(lexer, "SingleQuotedFString", "#166534")
                    self._set_lexer_style_color(lexer, "TripleSingleQuotedFString", "#166534")
                    self._set_lexer_style_color(lexer, "TripleDoubleQuotedFString", "#166534")
                    self._set_lexer_style_color(lexer, "Number", "#b45309")
                    self._set_lexer_style_color(lexer, "Comment", "#64748b")
                    self._set_lexer_style_color(lexer, "CommentBlock", "#64748b")
                    self._set_lexer_style_color(lexer, "Operator", "#334155")
                    self._set_lexer_style_color(lexer, "Decorator", "#be185d")
                    self._set_lexer_style_color(lexer, "HighlightedIdentifier", "#7c3aed")
                    self._set_lexer_style_color(lexer, "UnclosedString", "#b91c1c")
                if hasattr(self, "setPaper"):
                    self.setPaper(QColor("#ffffff"))
                if hasattr(self, "setColor"):
                    self.setColor(QColor("#111827"))
                self.setMarginsBackgroundColor(QColor("#eef3fa"))
                self.setMarginsForegroundColor(QColor("#64748b"))
                self.setCaretForegroundColor(QColor("#111827"))
                self.setCaretLineBackgroundColor(QColor("#f3f7fd"))
                self.setFoldMarginColors(QColor("#e6eef9"), QColor("#e6eef9"))
                self.setEdgeColor(QColor("#d6dee9"))
                if hasattr(self, "setSelectionBackgroundColor"):
                    self.setSelectionBackgroundColor(QColor("#cfe5ff"))
                if hasattr(self, "setSelectionForegroundColor"):
                    self.setSelectionForegroundColor(QColor("#0f172a"))
            if hasattr(self, "recolor"):
                self.recolor()

        @staticmethod
        def _select_font() -> QFont:
            candidates = ["JetBrains Mono", "Fira Code", "Courier New"]
            available = QFontDatabase.families()
            for family in candidates:
                if family in available:
                    font = QFont(family, 13)
                    font.setFixedPitch(True)
                    return font
            return QFont("Courier New", 13)

        def get_code(self) -> str:
            """Return the editor contents."""
            return self.text()

        def set_code(self, code: str) -> None:
            """Replace the editor contents."""
            self.setText(code)

        def get_cursor_position(self) -> tuple[int, int]:
            """Return the current cursor position."""
            line, col = self.getCursorPosition()
            return line, col

else:

    class CodeEditor(QPlainTextEdit):
        """Fallback code editor without QScintilla."""

        def __init__(self) -> None:
            super().__init__()
            font = QFont("Courier New", 13)
            font.setFixedPitch(True)
            self.setFont(font)
            self.setPlainText(DEFAULT_CODE)
            self._native_highlighter = create_python_highlighter(self.document())

        def get_code(self) -> str:
            """Return the editor contents."""
            return self.toPlainText()

        def set_theme(self, is_dark: bool) -> None:
            """Apply fallback text editor theme."""
            if is_dark:
                self.setStyleSheet(
                    "QPlainTextEdit {"
                    " background: #0e1117;"
                    " color: #c8ccd4;"
                    " selection-background-color: #264f78;"
                    " selection-color: #ffffff;"
                    "}"
                )
            else:
                self.setStyleSheet(
                    "QPlainTextEdit {"
                    " background: #ffffff;"
                    " color: #1f2937;"
                    " selection-background-color: #cfe5ff;"
                    " selection-color: #0f172a;"
                    "}"
                )

        def set_code(self, code: str) -> None:
            """Replace the editor contents."""
            self.setPlainText(code)

        def get_cursor_position(self) -> tuple[int, int]:
            """Return the current cursor position."""
            cursor = self.textCursor()
            return cursor.blockNumber(), cursor.columnNumber()


class EditorMinimap(QPlainTextEdit):
    """Read-only minimap mirroring the active editor content."""

    def __init__(self) -> None:
        super().__init__()
        self._editor = None
        self.setReadOnly(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mini_font = QFont("JetBrains Mono", 3)
        mini_font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(mini_font)
        self.setFixedWidth(120)
        self._native_highlighter = create_python_highlighter(self.document())
        self.setObjectName("editor_minimap")
        self.setStyleSheet(
            "QPlainTextEdit#editor_minimap {"
            " background: #0d1117;"
            " border-left: 1px solid #30363d;"
            " color: #8b949e;"
            "}"
        )

    def bind_editor(self, editor) -> None:
        self._editor = editor
        if hasattr(editor, "textChanged"):
            editor.textChanged.connect(self._sync_from_editor)
        if hasattr(editor, "verticalScrollBar"):
            editor.verticalScrollBar().valueChanged.connect(self._sync_scroll)
        self._sync_from_editor()

    def mousePressEvent(self, event) -> None:
        if self._editor is None:
            return super().mousePressEvent(event)
        ratio = event.position().y() / max(1.0, float(self.viewport().height()))
        bar = self._editor.verticalScrollBar()
        target = int(bar.minimum() + ratio * (bar.maximum() - bar.minimum()))
        bar.setValue(target)
        super().mousePressEvent(event)

    def _sync_from_editor(self) -> None:
        if self._editor is None:
            return
        if hasattr(self._editor, "text"):
            source_text = self._editor.text()
        else:
            source_text = self._editor.toPlainText()
        self.blockSignals(True)
        self.setPlainText(source_text)
        self.blockSignals(False)
        self._sync_scroll()

    def _sync_scroll(self) -> None:
        if self._editor is None:
            return
        src_bar = self._editor.verticalScrollBar()
        dst_bar = self.verticalScrollBar()
        if src_bar.maximum() <= src_bar.minimum():
            dst_bar.setValue(dst_bar.minimum())
            return
        ratio = (src_bar.value() - src_bar.minimum()) / (src_bar.maximum() - src_bar.minimum())
        target = int(dst_bar.minimum() + ratio * max(1, dst_bar.maximum() - dst_bar.minimum()))
        dst_bar.setValue(target)


class CenterPanel(QWidget):
    """Tabbed center panel for code and future modes."""

    run_requested = pyqtSignal()
    simulation_complete = pyqtSignal(dict)
    editor_cursor_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_editor_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.editor: CodeEditor | QPlainTextEdit
        self._embedded_simulink_enabled = False
        self._is_dark_theme = True
        self.simulink_canvas = SimulinkCanvas()
        self.simulink_canvas.load_demo_diagram()
        self._simulator = DiagramSimulator()
        self._sim_thread: QThread | None = None
        self._new_file_button = QToolButton()
        self._new_file_button.setText("+")
        self._new_file_button.setToolTip("New file tab")
        self._new_file_button.clicked.connect(self.new_file)
        self.tabs.setCornerWidget(self._new_file_button, Qt.Corner.TopRightCorner)

        self._add_editor_tab("untitle.py", DEFAULT_CODE)
        if self._embedded_simulink_enabled:
            self.tabs.addTab(self._build_simulink_tab(), "Simulink")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)
        self._on_tab_changed(self.tabs.currentIndex())

    def _add_editor_tab(self, title: str, code: str, path: str | None = None) -> int:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        editor_row = QWidget()
        editor_row_layout = QHBoxLayout(editor_row)
        editor_row_layout.setContentsMargins(0, 0, 0, 0)
        editor_row_layout.setSpacing(0)
        editor = CodeEditor()
        if hasattr(editor, "set_theme"):
            editor.set_theme(self._is_dark_theme)
        editor.set_code(code)
        editor_row_layout.addWidget(editor, 1)
        page_layout.addWidget(editor_row)

        page.setProperty("editor_ref", editor)
        page.setProperty("file_path", path or "")
        index = self.tabs.addTab(page, title)

        if hasattr(editor, "cursorPositionChanged"):
            editor.cursorPositionChanged.connect(
                lambda *_args, ed=editor: self._emit_cursor_if_active(ed)
            )
        return index

    def _current_editor(self):
        page = self.tabs.currentWidget()
        if page is None:
            return None
        return page.property("editor_ref")

    def _emit_cursor_if_active(self, editor_obj) -> None:
        if editor_obj is self._current_editor():
            self.editor_cursor_changed.emit()

    def _on_tab_changed(self, index: int) -> None:
        del index
        current = self._current_editor()
        if current is not None:
            self.editor = current
            self.editor_cursor_changed.emit()

    def _close_editor_tab(self, index: int) -> None:
        if self.tabs.count() <= 1:
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        self._on_tab_changed(self.tabs.currentIndex())

    def new_file(self) -> None:
        idx = self._add_editor_tab("untitle.py", DEFAULT_CODE)
        self.tabs.setCurrentIndex(idx)

    def open_document(self, path: str, code: str) -> None:
        filename = os.path.basename(path) or "untitle.py"
        current_page = self.tabs.currentWidget()
        current_editor = self._current_editor()
        current_path = ""
        if current_page is not None:
            current_path = str(current_page.property("file_path") or "")
        current_text = ""
        if current_editor is not None and hasattr(current_editor, "get_code"):
            current_text = current_editor.get_code()

        # Reuse the current tab if it is a fresh untitled tab.
        if current_page is not None and not current_path and not current_text.strip():
            current_page.setProperty("file_path", path)
            self.tabs.setTabText(self.tabs.currentIndex(), filename)
            if current_editor is not None:
                current_editor.set_code(code)
            self._on_tab_changed(self.tabs.currentIndex())
            return

        # If already open, switch to it.
        for idx in range(self.tabs.count()):
            page = self.tabs.widget(idx)
            if page is None:
                continue
            opened_path = str(page.property("file_path") or "")
            if opened_path == path:
                self.tabs.setCurrentIndex(idx)
                editor = page.property("editor_ref")
                if editor is not None and hasattr(editor, "set_code"):
                    editor.set_code(code)
                return

        idx = self._add_editor_tab(filename, code, path)
        self.tabs.setCurrentIndex(idx)

    def get_current_code(self) -> str:
        """Return the current code from the editor."""
        editor = self._current_editor()
        return editor.get_code() if editor is not None else ""

    def set_theme(self, is_dark: bool) -> None:
        """Apply theme to all opened editor tabs."""
        self._is_dark_theme = is_dark
        for idx in range(self.tabs.count()):
            page = self.tabs.widget(idx)
            if page is None:
                continue
            editor = page.property("editor_ref")
            if editor is not None and hasattr(editor, "set_theme"):
                editor.set_theme(is_dark)

    def set_code(self, code: str) -> None:
        """Set editor contents."""
        editor = self._current_editor()
        if editor is not None:
            editor.set_code(code)

    def insert_snippet(self, code: str) -> None:
        """Insert code snippet at cursor position."""
        editor = self._current_editor()
        if editor is None:
            return
        if hasattr(editor, "insert"):
            editor.insert(code)
        else:
            cursor = editor.textCursor()
            cursor.insertText(code)

    def _build_simulink_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(6, 6, 6, 6)
        toolbar_layout.setSpacing(6)

        simulate_btn = QPushButton("▶ Simulate")
        simulate_btn.setStyleSheet("background: #1f3b2b; color: #98c379; border: 1px solid #315c42;")
        stop_btn = QPushButton("■ Stop Sim")
        stop_btn.setStyleSheet("background: #2b1f1f; color: #e06c75; border: 1px solid #614040;")
        validate_btn = QPushButton("✓ Validate")
        arrange_btn = QPushButton("↔ Auto Arrange")
        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setStyleSheet("background: #2a2e3a; color: #c8ccd4;")
        save_btn = QPushButton("💾 Save .sim")
        load_btn = QPushButton("📂 Load .sim")

        self.t_end_spin = QDoubleSpinBox()
        self.t_end_spin.setRange(0.0, 1000.0)
        self.t_end_spin.setValue(10.0)
        self.t_end_spin.setSingleStep(0.5)
        self.dt_spin = QDoubleSpinBox()
        self.dt_spin.setRange(0.001, 1.0)
        self.dt_spin.setDecimals(3)
        self.dt_spin.setValue(0.01)
        self.dt_spin.setSingleStep(0.001)

        self.connect_mode = QCheckBox("Connect")
        self.connect_mode.setChecked(True)
        self.snap_mode = QCheckBox("Snap")
        self.snap_mode.setChecked(True)

        fit_btn = QPushButton("🔲 Fit View")
        self.sim_status = QLabel("Ready")
        self.sim_status.setObjectName("sim_status")

        toolbar_layout.addWidget(simulate_btn)
        toolbar_layout.addWidget(stop_btn)
        toolbar_layout.addWidget(validate_btn)
        toolbar_layout.addWidget(arrange_btn)
        toolbar_layout.addWidget(clear_btn)
        toolbar_layout.addWidget(save_btn)
        toolbar_layout.addWidget(load_btn)
        toolbar_layout.addWidget(QLabel("⏱ t_end:"))
        toolbar_layout.addWidget(self.t_end_spin)
        toolbar_layout.addWidget(QLabel("dt:"))
        toolbar_layout.addWidget(self.dt_spin)
        toolbar_layout.addWidget(self.connect_mode)
        toolbar_layout.addWidget(self.snap_mode)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.sim_status)
        toolbar_layout.addWidget(fit_btn)

        simulate_btn.clicked.connect(self._simulate_diagram)
        stop_btn.clicked.connect(self._stop_simulation)
        validate_btn.clicked.connect(self._validate_diagram)
        arrange_btn.clicked.connect(self._auto_arrange)
        clear_btn.clicked.connect(self.simulink_canvas.clear_canvas)
        save_btn.clicked.connect(self._save_diagram)
        load_btn.clicked.connect(self._load_diagram)
        fit_btn.clicked.connect(self._fit_view)
        self.connect_mode.toggled.connect(self.simulink_canvas.set_connect_mode)
        self.snap_mode.toggled.connect(self.simulink_canvas.set_snap_to_grid)
        self.simulink_canvas.diagram_changed.connect(lambda: self.sim_status.setText("Modified"))

        self.simulink_canvas.block_double_clicked.connect(self._on_block_double_clicked)

        layout.addWidget(toolbar)
        layout.addWidget(self.simulink_canvas, 1)
        return container

    def _simulate_diagram(self) -> None:
        if self._sim_thread is not None and self._sim_thread.isRunning():
            self.sim_status.setText("Simulation already running")
            return
        issues = self.simulink_canvas.validate_diagram()
        if issues:
            preview = "\n".join(f"• {issue}" for issue in issues[:6])
            if len(issues) > 6:
                preview += "\n• ..."
            answer = QMessageBox.question(
                self,
                "Model validation",
                f"Model has validation warnings:\n\n{preview}\n\nContinue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.sim_status.setText("Validation failed")
                return
        diagram = self.simulink_canvas.get_diagram()
        t_end = float(self.t_end_spin.value())
        dt = float(self.dt_spin.value())
        self.sim_status.setText("Running simulation…")
        self.simulink_canvas.set_wire_animation(True)
        self.simulink_canvas.set_runtime_status(0.0, 0, 0)

        worker = _SimulationWorker(self._simulator, diagram, t_end, dt)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_simulation_result)
        worker.error.connect(self._on_simulation_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_sim_thread", None))
        
        self._sim_worker = worker
        self._sim_thread = thread
        thread.start()

    def _stop_simulation(self) -> None:
        if self._sim_thread is not None and self._sim_thread.isRunning():
            self._sim_thread.requestInterruption()
            self.sim_status.setText("Stop requested")
            self.simulink_canvas.set_wire_animation(False)

    def _save_diagram(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Diagram", "", "Simulink Files (*.sim)")
        if not path:
            return
        data = self.simulink_canvas.get_diagram()
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self.sim_status.setText("Saved")

    def _load_diagram(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load Diagram", "", "Simulink Files (*.sim)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.simulink_canvas.load_diagram(data)
            self.sim_status.setText("Loaded")
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Load failed", str(exc))

    def _validate_diagram(self) -> None:
        issues = self.simulink_canvas.validate_diagram()
        if not issues:
            self.sim_status.setText("Model valid")
            QMessageBox.information(self, "Validation", "No issues found.")
            return
        self.sim_status.setText(f"{len(issues)} issue(s)")
        QMessageBox.warning(self, "Validation issues", "\n".join(issues))

    def _auto_arrange(self) -> None:
        self.simulink_canvas.auto_arrange_left_to_right()
        self.sim_status.setText("Auto-arranged")

    def _fit_view(self) -> None:
        items_rect = self.simulink_canvas.scene().itemsBoundingRect()
        if not items_rect.isNull():
            self.simulink_canvas.fitInView(items_rect.adjusted(-40, -40, 40, 40), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self.simulink_canvas.fitInView(self.simulink_canvas.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _on_simulation_result(self, result: dict) -> None:
        self.simulink_canvas.set_wire_animation(False)
        if result.get("success"):
            self.sim_status.setText("Simulation complete")
            sim_time = float(result.get("time", [0.0])[-1]) if result.get("time") else 0.0
            self.simulink_canvas.set_runtime_status(
                sim_time=sim_time,
                step_count=max(0, len(result.get("time", [])) - 1),
                error_count=0,
            )
            self.simulation_complete.emit(result)
        else:
            self.sim_status.setText("Simulation failed")
            self.simulink_canvas.set_runtime_status(0.0, 0, 1)
            QMessageBox.warning(self, "Simulation Error", result.get("error", "Unknown error"))

    def _on_simulation_error(self, error: str) -> None:
        self.sim_status.setText("Simulation error")
        self.simulink_canvas.set_wire_animation(False)
        self.simulink_canvas.set_runtime_status(0.0, 0, 1)
        QMessageBox.warning(self, "Simulation Error", error)

    def _on_block_double_clicked(self, block_id: str, params: dict) -> None:
        block = self.simulink_canvas._blocks.get(block_id)
        if block is None:
            return
        dlg = BlockParamDialog(block.block_type, params, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            block.params = dlg.get_params()
            block.update()
            self.simulink_canvas.diagram_changed.emit()


class _SimulationWorker(QObject):
    """Worker object to run simulations off the UI thread."""

    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, simulator: DiagramSimulator, diagram: dict, t_end: float, dt: float) -> None:
        super().__init__()
        self._simulator = simulator
        self._diagram = diagram
        self._t_end = t_end
        self._dt = dt

    def run(self) -> None:
        try:
            result = self._simulator.simulate(self._diagram, self._t_end, self._dt)
            if result.get("success"):
                self.finished.emit(result)
            else:
                self.error.emit(result.get("error", "Simulation failed"))
        except (ValueError, RuntimeError) as exc:
            self.error.emit(str(exc))
