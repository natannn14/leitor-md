"""
Leitor Markdown Moderno (md_reader.py)
Um leitor e editor desktop para arquivos Markdown (.md) no Windows.
Desenvolvido com PyQt6, PyQt6-WebEngine, markdown-it-py e pygments.
Versão v1.1.0 "Conforto Diário":
- Múltiplas abas independentes (QTabWidget) com atalhos e persistência de sessão
- Drag & Drop de arquivos (.md, .markdown, .txt) com feedback visual
- Zoom dinâmico (50% a 300%) no visualizador e editor com persistência por arquivo
- Contador de palavras, caracteres e estimativa de leitura na barra de status
- Indicador visual de alterações não salvas (●)
- Preservação total de atalhos, modo Leitura/Edição, busca em tempo real e exportação para PDF
"""

import importlib.util
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRect, QSettings, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import (
    QCloseEvent,
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplashScreen,
    QStackedWidget,
    QStatusBar,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.lexers.special import TextLexer


def resource_path(relative_path: str) -> str:
    """Retorna o caminho absoluto do recurso, compatível com PyInstaller (_MEIPASS) e modo dev."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def highlight_code(code: str, lang: str, *args) -> str:
    """
    Realiza o syntax highlighting de blocos de código usando o Pygments.
    Faz fallback para TextLexer caso a linguagem não seja reconhecida.
    Retorna apenas o conteúdo interno para que o markdown-it construa
    a tag <pre><code class="language-..."> sem tags <pre> aninhadas.
    """
    lang_name = (lang or "").strip().lower()
    try:
        lexer = get_lexer_by_name(lang_name, stripall=True) if lang_name else TextLexer()
    except Exception:
        lexer = TextLexer()

    formatter = HtmlFormatter(nowrap=True)
    return highlight(code, lexer, formatter)


class MarkdownTab(QWidget):
    """
    Representa uma aba individual contendo um documento Markdown.
    Gerencia seu próprio arquivo, editor de texto bruto, visualizador WebEngine,
    autosave com debounce (400ms), zoom independente e renderização HTML.
    """

    state_changed = pyqtSignal()
    load_finished = pyqtSignal(bool)
    status_message = pyqtSignal(str)

    def __init__(self, file_path: str, md_parser: MarkdownIt, initial_content: str = "", is_new: bool = False, parent=None):
        super().__init__(parent)

        self.md = md_parser
        self.file_path = str(Path(file_path).resolve())
        self.has_unsaved_changes = False
        self.current_zoom = 1.0

        # Criação do arquivo inicial se não existir
        file_obj = Path(self.file_path)
        if not file_obj.exists():
            if file_obj.parent:
                file_obj.parent.mkdir(parents=True, exist_ok=True)
            content = initial_content if initial_content else "# Novo Documento\nComece a escrever...\n"
            file_obj.write_text(content, encoding="utf-8")
            self.current_content = content
        else:
            self.current_content = file_obj.read_text(encoding="utf-8", errors="replace")

        # Timer para autosave com debounce (400ms)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(self._persist_to_disk)

        # Construção dos componentes da aba
        self._build_tab_ui()

        # Restaura zoom persistido para este arquivo (se houver)
        settings = QSettings("LeitorMD", "ModernMDReader")
        saved_zoom = float(settings.value(f"zoom/{self.file_path}", 1.0))
        self.set_zoom(saved_zoom, save=False)

        # Renderização inicial em modo leitura
        self._load_rendered_view()

    def _build_tab_ui(self):
        """Monta o stack com modo Leitura (QWebEngineView) e modo Edição (QPlainTextEdit)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget(self)

        # Modo Leitura: QWebEngineView
        self.web_view = QWebEngineView(self)
        self.web_view.setStyleSheet("background-color: #ffffff;")
        self.web_view.setAcceptDrops(False)
        page = self.web_view.page()
        if page is not None:
            page.setBackgroundColor(QColor("#ffffff"))
            page.pdfPrintingFinished.connect(self._on_pdf_printed)

        self.web_view.loadFinished.connect(lambda ok: self.load_finished.emit(ok))
        self.stack.addWidget(self.web_view)

        # Modo Edição: QPlainTextEdit
        self.editor = QPlainTextEdit(self)
        self.editor.setAcceptDrops(False)
        editor_font = QFont("Consolas", 14)
        editor_font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(editor_font)
        self.editor.setPlainText(self.current_content)
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #ffffff;
                color: #24292f;
                border: none;
                padding: 20px;
                selection-background-color: #b6e3ff;
                selection-color: #24292f;
            }
        """)
        self.editor.textChanged.connect(self._on_text_edited)
        self.stack.addWidget(self.editor)

        self.stack.setCurrentIndex(0)
        layout.addWidget(self.stack)

    def _render_html(self, markdown_text: str) -> str:
        """Renderiza Markdown em HTML completo com tema GitHub e Pygments."""
        rendered_body = self.md.render(markdown_text)

        pygments_css = HtmlFormatter().get_style_defs("pre code")
        pygments_css += "\n" + HtmlFormatter().get_style_defs("pre")
        pygments_css += "\n" + HtmlFormatter().get_style_defs(".highlight")

        full_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
    * {{
        box-sizing: border-box;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
        font-size: 15px;
        line-height: 1.6;
        padding: 24px;
        color: #24292f;
        background-color: #ffffff;
        margin: 0;
    }}
    .markdown-body {{
        max-width: 900px;
        margin: 0 auto;
        word-wrap: break-word;
    }}
    h1, h2, h3, h4, h5, h6 {{
        margin-top: 24px;
        margin-bottom: 16px;
        font-weight: 600;
        line-height: 1.25;
        color: #1f2328;
    }}
    h1 {{
        font-size: 2em;
        padding-bottom: 0.3em;
        border-bottom: 1px solid #d0d7de;
    }}
    h2 {{
        font-size: 1.5em;
        padding-bottom: 0.3em;
        border-bottom: 1px solid #d0d7de;
    }}
    h3 {{ font-size: 1.25em; }}
    h4 {{ font-size: 1em; }}
    h5 {{ font-size: 0.875em; }}
    h6 {{ font-size: 0.85em; color: #656d76; }}
    p {{
        margin-top: 0;
        margin-bottom: 16px;
    }}
    a {{
        color: #0969da;
        text-decoration: none;
    }}
    a:hover {{
        text-decoration: underline;
    }}
    table {{
        border-collapse: collapse;
        width: 100%;
        margin-top: 0;
        margin-bottom: 16px;
        display: block;
        overflow-x: auto;
    }}
    th, td {{
        border: 1px solid #d0d7de;
        padding: 6px 13px;
    }}
    th {{
        font-weight: 600;
        background-color: #f6f8fa;
    }}
    tr:nth-child(2n) {{
        background-color: #f6f8fa;
    }}
    pre {{
        background-color: #f6f8fa;
        padding: 16px;
        border-radius: 6px;
        overflow-x: auto;
        font-size: 85%;
        line-height: 1.45;
        margin-top: 0;
        margin-bottom: 16px;
        border: 1px solid #d0d7de;
    }}
    code {{
        font-family: Consolas, "Liberation Mono", Menlo, Courier, monospace;
        font-size: 85%;
    }}
    p code, li code, td code {{
        padding: 0.2em 0.4em;
        margin: 0;
        background-color: rgba(175, 184, 193, 0.2);
        border-radius: 6px;
    }}
    pre code {{
        padding: 0;
        background: transparent;
        border: 0;
        font-size: 100%;
    }}
    blockquote {{
        padding: 0 1em;
        color: #57606a;
        border-left: 0.25em solid #d0d7de;
        margin: 0 0 16px 0;
    }}
    hr {{
        height: 0.25em;
        padding: 0;
        margin: 24px 0;
        background-color: #d0d7de;
        border: 0;
    }}
    ul, ol {{
        padding-left: 2em;
        margin-top: 0;
        margin-bottom: 16px;
    }}
    li + li {{
        margin-top: 0.25em;
    }}
    img {{
        max-width: 100%;
        box-sizing: content-box;
        border-radius: 6px;
    }}
    li.task-list-item {{
        list-style-type: none;
    }}
    input.task-list-item-checkbox, input[type="checkbox"] {{
        margin: 0 0.35em 0.25em -1.4em;
        vertical-align: middle;
    }}
    {pygments_css}
</style>
</head>
<body>
<div class="markdown-body">
{rendered_body}
</div>
</body>
</html>
"""
        return full_html

    def _load_rendered_view(self):
        """Carrega o HTML renderizado no QWebEngineView usando o diretório do arquivo."""
        html_content = self._render_html(self.current_content)
        base_dir = os.path.dirname(self.file_path)
        base_url = QUrl.fromLocalFile(base_dir + os.sep)
        self.web_view.setHtml(html_content, base_url)

    def _on_text_edited(self):
        """Acionado ao alterar o texto bruto no editor."""
        self.has_unsaved_changes = True
        self.current_content = self.editor.toPlainText()
        self.status_message.emit("Digitando...")
        self.state_changed.emit()
        self.save_timer.start(400)

    def _persist_to_disk(self):
        """Grava o conteúdo atual em disco em UTF-8."""
        if self.save_timer.isActive():
            self.save_timer.stop()

        content = self.editor.toPlainText()
        try:
            Path(self.file_path).write_text(content, encoding="utf-8")
            self.current_content = content
            self.has_unsaved_changes = False

            if self.stack.currentIndex() == 1:
                self.status_message.emit("Salvo automaticamente")
            else:
                self.status_message.emit("Modo: Leitura")
            self.state_changed.emit()
        except Exception as e:
            self.status_message.emit(f"Erro ao salvar: {e}")

    def toggle_mode(self) -> int:
        """Alterna entre Leitura (0) e Edição (1). Retorna o novo índice."""
        if self.stack.currentIndex() == 0:
            self.stack.setCurrentIndex(1)
            self.editor.setFocus()
            self.status_message.emit("Modo: Edição")
        else:
            if self.has_unsaved_changes:
                self._persist_to_disk()
            else:
                self.current_content = self.editor.toPlainText()

            self._load_rendered_view()
            self.stack.setCurrentIndex(0)
            self.status_message.emit("Modo: Leitura")

        self.state_changed.emit()
        return self.stack.currentIndex()

    def save_manual(self):
        """Força a gravação imediata no disco (Ctrl+S)."""
        self._persist_to_disk()
        self.status_message.emit("Arquivo salvo com sucesso!")

    def save_as(self, new_path: str):
        """Salva como novo arquivo (Ctrl+Shift+S)."""
        self.file_path = str(Path(new_path).resolve())
        self._persist_to_disk()
        self._load_rendered_view()
        self.status_message.emit("Arquivo salvo como novo documento!")
        self.state_changed.emit()

    def rename_file(self, new_path: str):
        """Renomeia o arquivo atual no disco e atualiza os apontamentos."""
        new_resolved = str(Path(new_path).resolve())
        if self.has_unsaved_changes:
            self._persist_to_disk()

        old_file = Path(self.file_path)
        if old_file.exists() and old_file != Path(new_resolved):
            old_file.rename(new_resolved)

        self.file_path = new_resolved
        self._persist_to_disk()
        self._load_rendered_view()
        self.status_message.emit(f"Renomeado para: {Path(new_resolved).name}")
        self.state_changed.emit()

    def load_file(self, new_path: str):
        """Carrega outro arquivo diretamente nesta aba."""
        if self.has_unsaved_changes:
            self._persist_to_disk()

        self.file_path = str(Path(new_path).resolve())
        target = Path(self.file_path)
        if target.exists():
            self.current_content = target.read_text(encoding="utf-8", errors="replace")
        else:
            self.current_content = "# Novo Documento\nComece a escrever...\n"
            target.write_text(self.current_content, encoding="utf-8")

        self.editor.blockSignals(True)
        self.editor.setPlainText(self.current_content)
        self.editor.blockSignals(False)

        self.has_unsaved_changes = False
        self._load_rendered_view()

        settings = QSettings("LeitorMD", "ModernMDReader")
        saved_zoom = float(settings.value(f"zoom/{self.file_path}", 1.0))
        self.set_zoom(saved_zoom, save=False)

        self.status_message.emit("Arquivo carregado com sucesso!")
        self.state_changed.emit()

    def export_pdf(self, pdf_path: str):
        """Exporta o documento formatado para PDF."""
        if self.has_unsaved_changes:
            self._persist_to_disk()
            self._load_rendered_view()

        page = self.web_view.page()
        if page is not None:
            page.printToPdf(pdf_path)
        else:
            self.status_message.emit("Erro: Página WebEngine indisponível.")

    def _on_pdf_printed(self, file_path: str, success: bool):
        if success:
            self.status_message.emit(f"PDF exportado: {Path(file_path).name}")
        else:
            self.status_message.emit("Erro ao exportar PDF.")

    def find_text(self, query: str, backward: bool = False):
        """Busca texto no modo ativo (WebEngine ou Editor)."""
        if not query:
            self.web_view.findText("")
            return

        if self.stack.currentIndex() == 0:
            flag = QWebEnginePage.FindFlag.FindBackward if backward else QWebEnginePage.FindFlag(0)
            self.web_view.findText(query, flag)
        else:
            flag = QTextDocument.FindFlag.FindBackward if backward else QTextDocument.FindFlag(0)
            found = self.editor.find(query, flag)
            if not found:
                cursor = self.editor.textCursor()
                if backward:
                    cursor.movePosition(cursor.MoveOperation.End)
                else:
                    cursor.movePosition(cursor.MoveOperation.Start)
                self.editor.setTextCursor(cursor)
                self.editor.find(query, flag)

    def set_zoom(self, factor: float, save: bool = True):
        """Ajusta o nível de zoom proporcional no visualizador e no editor (50% a 300%)."""
        self.current_zoom = round(max(0.5, min(3.0, factor)), 2)
        self.web_view.setZoomFactor(self.current_zoom)

        base_pt = 14
        new_pt = max(8, round(base_pt * self.current_zoom))
        font = QFont("Consolas", new_pt)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)

        if save:
            settings = QSettings("LeitorMD", "ModernMDReader")
            settings.setValue(f"zoom/{self.file_path}", self.current_zoom)

        self.state_changed.emit()


class ModernMDReader(QMainWindow):
    """
    Janela Principal do Leitor Markdown Moderno (v1.1.0).
    Gerencia múltiplas abas independentes (QTabWidget), atalhos globais,
    drag & drop de arquivos, busca integrada, zoom e estatísticas de leitura.
    """

    def __init__(self, initial_files: list[str] | str | None = None):
        super().__init__()

        self.resize(1050, 780)
        self.setAcceptDrops(True)

        # Ícone da aplicação compatível com PyInstaller
        icon_file = resource_path("app.ico")
        if os.path.exists(icon_file):
            self.setWindowIcon(QIcon(icon_file))

        # Parser Markdown compartilhado
        has_linkify = importlib.util.find_spec("linkify_it") is not None
        self.md = MarkdownIt(
            "gfm-like",
            {
                "highlight": highlight_code,
                "breaks": True,
                "linkify": has_linkify,
            },
        )
        try:
            self.md.enable("table").enable("tasklists")
        except Exception:
            try:
                self.md.enable("table", ignoreInvalid=True).enable("tasklists", ignoreInvalid=True)
            except Exception:
                pass

        self.untitled_counter = 0

        # Montagem da interface gráfica
        self._build_ui()
        self._setup_shortcuts()

        # Resolução dos arquivos iniciais a abrir
        files_to_open: list[str] = []
        if isinstance(initial_files, str):
            files_to_open = [initial_files]
        elif isinstance(initial_files, list) and initial_files:
            files_to_open = initial_files

        if not files_to_open:
            files_to_open = ["documento_exemplo.md"]

        # Abertura das abas
        for f in files_to_open:
            self.add_tab_for_file(f, switch_to=False)

        if self.tab_widget.count() > 0:
            self.tab_widget.setCurrentIndex(0)

        self._on_tab_changed(self.tab_widget.currentIndex())

    def _build_ui(self):
        """Constrói Top Bar, Search Bar, Tab Widget e Status Bar."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Bar
        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setStyleSheet("""
            QWidget#topBar {
                background-color: #ffffff;
                border-bottom: 1px solid #d0d7de;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 8, 16, 8)
        top_layout.setSpacing(8)

        # Botão alternar Leitura / Edição
        self.btn_toggle = QPushButton("Alternar para Edição (Ctrl+E)")
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet(self._button_style(primary=True))
        self.btn_toggle.clicked.connect(self.toggle_mode)
        top_layout.addWidget(self.btn_toggle)

        # Botão Buscar
        self.btn_search = QPushButton("Buscar (Ctrl+F)")
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.setStyleSheet(self._button_style(primary=False))
        self.btn_search.clicked.connect(self.toggle_search_bar)
        top_layout.addWidget(self.btn_search)

        # Botão Exportar PDF
        self.btn_pdf = QPushButton("Exportar PDF (Ctrl+P)")
        self.btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf.setStyleSheet(self._button_style(primary=False))
        self.btn_pdf.clicked.connect(self.export_pdf)
        top_layout.addWidget(self.btn_pdf)

        # Controles de Zoom
        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setToolTip("Diminuir Zoom (Ctrl+ -)")
        btn_zoom_out.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_zoom_out.setStyleSheet(self._button_style(primary=False, compact=True))
        btn_zoom_out.clicked.connect(self.zoom_out)
        top_layout.addWidget(btn_zoom_out)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setToolTip("Zoom atual (Ctrl+0 para restaurar)")
        self.lbl_zoom.setStyleSheet("""
            QLabel {
                color: #24292f;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                font-size: 12px;
                font-weight: 600;
                padding: 0 4px;
            }
        """)
        top_layout.addWidget(self.lbl_zoom)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setToolTip("Aumentar Zoom (Ctrl+ +)")
        btn_zoom_in.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_zoom_in.setStyleSheet(self._button_style(primary=False, compact=True))
        btn_zoom_in.clicked.connect(self.zoom_in)
        top_layout.addWidget(btn_zoom_in)

        top_layout.addStretch()

        # Status de modo na extremidade direita
        self.lbl_status = QLabel("Modo: Leitura")
        self.lbl_status.setStyleSheet("""
            QLabel {
                color: #57606a;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        top_layout.addWidget(self.lbl_status)

        main_layout.addWidget(top_bar)

        # 2. Barra de Busca integrada
        self.search_bar = QWidget()
        self.search_bar.setObjectName("searchBar")
        self.search_bar.setVisible(False)
        self.search_bar.setStyleSheet("""
            QWidget#searchBar {
                background-color: #f6f8fa;
                border-bottom: 1px solid #d0d7de;
            }
        """)
        search_layout = QHBoxLayout(self.search_bar)
        search_layout.setContentsMargins(16, 6, 16, 6)
        search_layout.setSpacing(8)

        search_label = QLabel("Buscar:")
        search_label.setStyleSheet("color: #24292f; font-size: 13px; font-weight: 500;")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Digite o termo e pressione Enter...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #24292f;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #0969da;
            }
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(lambda: self.find_next(backward=False))
        QShortcut(QKeySequence("Shift+Return"), self.search_input).activated.connect(
            lambda: self.find_next(backward=True)
        )
        search_layout.addWidget(self.search_input)

        btn_prev = QPushButton("▲")
        btn_prev.setToolTip("Ocorrência anterior (Shift+Enter)")
        btn_prev.setStyleSheet(self._button_style(primary=False, compact=True))
        btn_prev.clicked.connect(lambda: self.find_next(backward=True))
        search_layout.addWidget(btn_prev)

        btn_next = QPushButton("▼")
        btn_next.setToolTip("Próxima ocorrência (Enter)")
        btn_next.setStyleSheet(self._button_style(primary=False, compact=True))
        btn_next.clicked.connect(lambda: self.find_next(backward=False))
        search_layout.addWidget(btn_next)

        btn_close_search = QPushButton("✕")
        btn_close_search.setToolTip("Fechar busca (Esc)")
        btn_close_search.setStyleSheet(self._button_style(primary=False, compact=True))
        btn_close_search.clicked.connect(self.close_search_bar)
        search_layout.addWidget(btn_close_search)

        main_layout.addWidget(self.search_bar)

        # 3. Gerenciador de Abas (QTabWidget)
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setStyleSheet(self._tab_widget_style(drag_active=False))

        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.tab_widget.tabBarDoubleClicked.connect(self._on_tab_double_clicked)

        # Botão "+" para nova aba no canto direito da barra de abas
        btn_add_tab = QPushButton("+")
        btn_add_tab.setToolTip("Nova Aba (Ctrl+T)")
        btn_add_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_tab.setStyleSheet("""
            QPushButton {
                background-color: #f6f8fa;
                color: #24292f;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 14px;
                font-weight: bold;
                margin-right: 8px;
            }
            QPushButton:hover {
                background-color: #eaeef2;
            }
        """)
        btn_add_tab.clicked.connect(self.new_tab)
        self.tab_widget.setCornerWidget(btn_add_tab, Qt.Corner.TopRightCorner)

        main_layout.addWidget(self.tab_widget)

        # 4. Status Bar com contador de palavras
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #f6f8fa;
                color: #57606a;
                border-top: 1px solid #d0d7de;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                font-size: 12px;
                padding: 2px 12px;
            }
        """)

        self.lbl_stats = QLabel("Palavras: 0 | Caracteres: 0 | Tempo de leitura: < 1 min")
        self.lbl_stats.setStyleSheet("color: #57606a; font-weight: 500;")
        self.status_bar.addWidget(self.lbl_stats)

        self.lbl_file_path = QLabel("")
        self.lbl_file_path.setStyleSheet("color: #8c959f; font-size: 11px;")
        self.status_bar.addPermanentWidget(self.lbl_file_path)

    def _setup_shortcuts(self):
        """Registra todos os atalhos de teclado do aplicativo."""
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self.new_tab)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(lambda: self.close_tab(self.tab_widget.currentIndex()))
        QShortcut(QKeySequence("Ctrl+Tab"), self).activated.connect(self.next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self).activated.connect(self.prev_tab)

        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.toggle_mode)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.toggle_search_bar)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self.export_pdf)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_manual)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.save_as)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close_search_bar)

        # Atalhos de Zoom
        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(self.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(self.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(self.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(self.zoom_reset)

    def _button_style(self, primary: bool = False, compact: bool = False) -> str:
        """Retorna o estilo QSS padronizado para os botões do cabeçalho."""
        bg = "#f6f8fa" if not primary else "#0969da"
        color = "#24292f" if not primary else "#ffffff"
        hover_bg = "#f3f4f6" if not primary else "#0860ca"
        border = "#d0d7de" if not primary else "#0969da"
        padding = "3px 8px" if compact else "6px 12px"

        return f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: 1px solid {border};
                border-radius: 6px;
                padding: {padding};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton:pressed {{
                background-color: #ebecf0;
            }}
        """

    def _tab_widget_style(self, drag_active: bool = False) -> str:
        """Estilo das abas com suporte a feedback visual de Drag & Drop."""
        border_pane = "2px dashed #0969da" if drag_active else "none"
        bg_pane = "#f0f7ff" if drag_active else "#ffffff"
        return f"""
            QTabWidget::pane {{
                border: {border_pane};
                background-color: {bg_pane};
            }}
            QTabBar {{
                background-color: #f6f8fa;
                border-bottom: 1px solid #d0d7de;
            }}
            QTabBar::tab {{
                background-color: #f6f8fa;
                color: #57606a;
                border: 1px solid #d0d7de;
                border-bottom: none;
                padding: 7px 16px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                font-size: 13px;
                font-weight: 500;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                margin-top: 3px;
            }}
            QTabBar::tab:selected {{
                background-color: #ffffff;
                color: #0969da;
                font-weight: 600;
                border-color: #d0d7de;
                border-bottom: 2px solid #0969da;
                margin-top: 1px;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #eaeef2;
                color: #24292f;
            }}
            QTabBar::close-button {{
                subcontrol-position: right;
                padding: 2px;
                border-radius: 4px;
            }}
            QTabBar::close-button:hover {{
                background-color: #d0d7de;
            }}
        """

    # Gerenciamento de Abas
    def current_tab(self) -> MarkdownTab | None:
        widget = self.tab_widget.currentWidget()
        return widget if isinstance(widget, MarkdownTab) else None

    def get_tab(self, index: int) -> MarkdownTab | None:
        widget = self.tab_widget.widget(index)
        return widget if isinstance(widget, MarkdownTab) else None

    def add_tab_for_file(self, file_path: str, initial_content: str = "", is_new: bool = False, switch_to: bool = True) -> MarkdownTab:
        tab = MarkdownTab(file_path, self.md, initial_content=initial_content, is_new=is_new, parent=self.tab_widget)
        tab.state_changed.connect(self._on_tab_state_changed)
        tab.status_message.connect(self.lbl_status.setText)

        file_name = Path(tab.file_path).name
        index = self.tab_widget.addTab(tab, file_name)
        self.tab_widget.setTabToolTip(index, tab.file_path)

        if switch_to:
            self.tab_widget.setCurrentIndex(index)
        return tab

    def open_file_in_tab(self, file_path: str, in_new_tab: bool = True):
        abs_path = str(Path(file_path).resolve())

        # Se o arquivo já estiver aberto, foca na aba correspondente
        for i in range(self.tab_widget.count()):
            tab = self.get_tab(i)
            if tab and tab.file_path == abs_path:
                self.tab_widget.setCurrentIndex(i)
                return

        if in_new_tab:
            self.add_tab_for_file(abs_path, switch_to=True)
        else:
            tab = self.current_tab()
            if tab:
                tab.load_file(abs_path)
                self._update_tab_title(self.tab_widget.currentIndex())
                self._update_window_title()
                self._update_word_stats()
                self._update_zoom_label()
            else:
                self.add_tab_for_file(abs_path, switch_to=True)

    def new_tab(self):
        """Cria um novo documento Markdown em branco (Ctrl+T)."""
        self.untitled_counter += 1
        default_dir = Path.home() / "Documents"
        if not default_dir.exists():
            default_dir = Path.home()
        new_path = default_dir / f"Sem título {self.untitled_counter}.md"
        initial_content = f"# Sem título {self.untitled_counter}\n\nComece a escrever aqui...\n"
        tab = self.add_tab_for_file(str(new_path), initial_content=initial_content, is_new=True, switch_to=True)
        if tab:
            tab.toggle_mode()

    def close_tab(self, index: int):
        """Fecha a aba indicada, solicitando salvamento se houver alterações (Ctrl+W)."""
        if index < 0 or index >= self.tab_widget.count():
            return
        tab = self.get_tab(index)
        if not tab:
            return

        if tab.has_unsaved_changes:
            file_name = Path(tab.file_path).name
            msg_box = QMessageBox(
                QMessageBox.Icon.Question,
                "Salvar alterações",
                f"O documento '{file_name}' possui alterações não salvas.\nDeseja salvar antes de fechar?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                self,
            )
            msg_box.button(QMessageBox.StandardButton.Save).setText("Salvar")
            msg_box.button(QMessageBox.StandardButton.Discard).setText("Descartar")
            msg_box.button(QMessageBox.StandardButton.Cancel).setText("Cancelar")
            res = msg_box.exec()
            if res == QMessageBox.StandardButton.Save:
                tab._persist_to_disk()
            elif res == QMessageBox.StandardButton.Cancel:
                return

        if tab.save_timer.isActive():
            tab.save_timer.stop()

        self.tab_widget.removeTab(index)
        tab.deleteLater()

        # Ao fechar a última aba, mantém a janela aberta com uma nova aba em branco
        if self.tab_widget.count() == 0:
            self.new_tab()
        else:
            self._on_tab_changed(self.tab_widget.currentIndex())

    def next_tab(self):
        count = self.tab_widget.count()
        if count > 1:
            self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() + 1) % count)

    def prev_tab(self):
        count = self.tab_widget.count()
        if count > 1:
            self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() - 1) % count)

    def _on_tab_double_clicked(self, index: int):
        """Duplo clique no título da aba para renomear o arquivo via QInputDialog."""
        if index < 0 or index >= self.tab_widget.count():
            return
        tab = self.get_tab(index)
        if not tab:
            return

        old_name = Path(tab.file_path).name
        new_name, ok = QInputDialog.getText(
            self,
            "Renomear Documento",
            "Novo nome para o arquivo:",
            QLineEdit.EchoMode.Normal,
            old_name,
        )
        if ok and new_name and new_name.strip():
            clean_name = new_name.strip()
            if not clean_name.lower().endswith((".md", ".markdown", ".txt")):
                clean_name += ".md"
            parent_dir = Path(tab.file_path).parent
            new_path = parent_dir / clean_name
            tab.rename_file(str(new_path))
            self._update_tab_title(index)
            self._update_window_title()

    def _on_tab_changed(self, index: int):
        """Sincroniza botões da barra superior, zoom, estatísticas e títulos."""
        tab = self.get_tab(index)
        if not tab:
            return

        # Sincroniza estado de Leitura / Edição
        if tab.stack.currentIndex() == 0:
            self.btn_toggle.setText("Alternar para Edição (Ctrl+E)")
            self.lbl_status.setText("Modo: Leitura")
        else:
            self.btn_toggle.setText("Voltar para Leitura (Ctrl+E)")
            self.lbl_status.setText("Modo: Edição")

        self._update_zoom_label()
        self._update_word_stats()
        self._update_window_title()
        self.lbl_file_path.setText(tab.file_path)

        # Se a barra de pesquisa estiver aberta, reflete o termo na nova aba
        if self.search_bar.isVisible() and self.search_input.text():
            tab.find_text(self.search_input.text(), backward=False)

    def _on_tab_state_changed(self):
        """Disparado quando o conteúdo, salvamento ou zoom de uma aba muda."""
        idx = self.tab_widget.currentIndex()
        self._update_tab_title(idx)
        self._update_window_title()
        self._update_word_stats()
        self._update_zoom_label()

    def _update_tab_title(self, index: int):
        tab = self.get_tab(index)
        if not tab:
            return
        file_name = Path(tab.file_path).name
        title = f"● {file_name}" if tab.has_unsaved_changes else file_name
        self.tab_widget.setTabText(index, title)
        self.tab_widget.setTabToolTip(index, tab.file_path)

    def _update_window_title(self):
        tab = self.current_tab()
        if not tab:
            self.setWindowTitle("Leitor Markdown Moderno")
            return
        file_name = Path(tab.file_path).name
        prefix = "[●] " if tab.has_unsaved_changes else ""
        self.setWindowTitle(f"Leitor Markdown Moderno - {prefix}{file_name}")

    def _update_word_stats(self):
        tab = self.current_tab()
        if not tab:
            self.lbl_stats.setText("Palavras: 0 | Caracteres: 0 | Tempo de leitura: < 1 min")
            return
        text = tab.current_content or ""
        words = len(text.split())
        chars = len(text)
        minutes = max(1, round(words / 200))
        time_str = "< 1 min" if words < 150 else f"~{minutes} min"
        self.lbl_stats.setText(f"Palavras: {words:,} | Caracteres: {chars:,} | Tempo de leitura: {time_str}")

    def _update_zoom_label(self):
        tab = self.current_tab()
        if tab:
            self.lbl_zoom.setText(f"{int(tab.current_zoom * 100)}%")

    # Ações na Aba Ativa
    def toggle_mode(self):
        tab = self.current_tab()
        if tab:
            new_mode = tab.toggle_mode()
            if new_mode == 0:
                self.btn_toggle.setText("Alternar para Edição (Ctrl+E)")
                self.lbl_status.setText("Modo: Leitura")
            else:
                self.btn_toggle.setText("Voltar para Leitura (Ctrl+E)")
                self.lbl_status.setText("Modo: Edição")
            if self.search_bar.isVisible() and self.search_input.text():
                tab.find_text(self.search_input.text(), backward=False)

    def save_manual(self):
        tab = self.current_tab()
        if tab:
            tab.save_manual()

    def save_as(self):
        tab = self.current_tab()
        if not tab:
            return
        new_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Como...",
            tab.file_path,
            "Documentos Markdown (*.md);;Todos os Arquivos (*.*)",
        )
        if new_path:
            tab.save_as(new_path)
            self._update_tab_title(self.tab_widget.currentIndex())
            self._update_window_title()

    def export_pdf(self):
        tab = self.current_tab()
        if not tab:
            return
        default_pdf = os.path.splitext(tab.file_path)[0] + ".pdf"
        pdf_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Documento para PDF",
            default_pdf,
            "Documento PDF (*.pdf)",
        )
        if pdf_path:
            self.lbl_status.setText("Gerando PDF...")
            tab.export_pdf(pdf_path)

    # Zoom
    def zoom_in(self):
        tab = self.current_tab()
        if tab:
            tab.set_zoom(tab.current_zoom + 0.1)
            self._update_zoom_label()

    def zoom_out(self):
        tab = self.current_tab()
        if tab:
            tab.set_zoom(tab.current_zoom - 0.1)
            self._update_zoom_label()

    def zoom_reset(self):
        tab = self.current_tab()
        if tab:
            tab.set_zoom(1.0)
            self._update_zoom_label()

    # Busca
    def toggle_search_bar(self):
        if not self.search_bar.isVisible():
            self.search_bar.setVisible(True)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def close_search_bar(self):
        self.search_bar.setVisible(False)
        self.search_input.clear()
        tab = self.current_tab()
        if tab:
            tab.web_view.findText("")
            if tab.stack.currentIndex() == 0:
                tab.web_view.setFocus()
            else:
                tab.editor.setFocus()

    def _on_search_text_changed(self, text: str):
        tab = self.current_tab()
        if tab:
            if not text:
                tab.web_view.findText("")
            else:
                self.find_next(backward=False)

    def find_next(self, backward: bool = False):
        query = self.search_input.text()
        if not query:
            return
        tab = self.current_tab()
        if tab:
            tab.find_text(query, backward=backward)

    # Drag & Drop de Arquivos
    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0 and a0.mimeData().hasUrls():
            urls = a0.mimeData().urls()
            has_supported = any(url.toLocalFile().lower().endswith((".md", ".markdown", ".txt")) for url in urls)
            if has_supported:
                a0.acceptProposedAction()
                self.tab_widget.setStyleSheet(self._tab_widget_style(drag_active=True))
                return
        if a0:
            a0.ignore()

    def dragLeaveEvent(self, a0: QDragLeaveEvent | None) -> None:
        self.tab_widget.setStyleSheet(self._tab_widget_style(drag_active=False))

    def dropEvent(self, a0: QDropEvent | None) -> None:
        self.tab_widget.setStyleSheet(self._tab_widget_style(drag_active=False))
        if not a0 or not a0.mimeData().hasUrls():
            return

        urls = a0.mimeData().urls()
        valid_paths = [
            url.toLocalFile() for url in urls
            if url.toLocalFile().lower().endswith((".md", ".markdown", ".txt"))
        ]
        if not valid_paths:
            return

        a0.acceptProposedAction()

        # Múltiplos arquivos -> abre todos em novas abas
        if len(valid_paths) > 1:
            for p in valid_paths:
                self.open_file_in_tab(p, in_new_tab=True)
        else:
            # Um arquivo: verifica se foi solto na barra de abas ou no corpo
            single_path = valid_paths[0]
            tab_bar = self.tab_widget.tabBar()
            tab_bar_pos = tab_bar.mapFrom(self, a0.position().toPoint())
            if tab_bar.rect().contains(tab_bar_pos):
                self.open_file_in_tab(single_path, in_new_tab=True)
            else:
                self.open_file_in_tab(single_path, in_new_tab=False)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Garante a gravação de alterações pendentes e salva a sessão de abas no QSettings."""
        settings = QSettings("LeitorMD", "ModernMDReader")
        open_paths: list[str] = []

        for i in range(self.tab_widget.count()):
            tab = self.get_tab(i)
            if tab:
                if tab.has_unsaved_changes:
                    if tab.save_timer.isActive():
                        tab.save_timer.stop()
                    tab._persist_to_disk()
                if os.path.exists(tab.file_path):
                    open_paths.append(tab.file_path)

        settings.setValue("recent_files", open_paths)
        settings.setValue("active_tab_index", self.tab_widget.currentIndex())

        if a0 is not None:
            super().closeEvent(a0)


def create_splash_screen() -> QSplashScreen:
    """Cria e retorna uma tela de splash moderna e elegante (Dark Card flutuante com cantos arredondados)."""
    width, height = 380, 220
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Fundo estilo Dark Card
    painter.setBrush(QColor("#0f172a"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, width, height, 16, 16)

    # Borda sutil
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QColor("#1e293b"))
    painter.drawRoundedRect(0, 0, width - 1, height - 1, 16, 16)

    # Ícone da aplicação
    icon_path = resource_path("app.ico")
    if os.path.exists(icon_path):
        icon_pixmap = QPixmap(icon_path).scaled(
            64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap((width - 64) // 2, 26, icon_pixmap)

    # Título do aplicativo
    painter.setPen(QColor("#ffffff"))
    title_font = QFont("Segoe UI", 13, QFont.Weight.Bold)
    painter.setFont(title_font)
    painter.drawText(QRect(0, 102, width, 30), Qt.AlignmentFlag.AlignCenter, "Leitor Markdown Moderno")

    painter.end()

    splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
    splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    splash.setStyleSheet("QSplashScreen { padding-bottom: 26px; }")
    splash.setFont(QFont("Segoe UI", 10))
    splash.showMessage(
        "Inicializando ambiente de leitura...",
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
        QColor("#94a3b8"),
    )
    return splash


def main():
    app = QApplication(sys.argv)

    # 1. Exibe o Splash Screen elegante imediatamente enquanto o runtime sobe
    splash = create_splash_screen()
    splash.show()
    app.processEvents()

    # Rotação dinâmica de mensagens no splash
    messages = [
        "Inicializando ambiente de leitura...",
        "Carregando componentes gráficos...",
        "Restaurando documentos e abas...",
        "Quase pronto...",
    ]
    msg_idx = 0

    def rotate_msg():
        nonlocal msg_idx
        msg_idx = (msg_idx + 1) % len(messages)
        splash.showMessage(
            messages[msg_idx],
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter,
            QColor("#94a3b8"),
        )

    msg_timer = QTimer()
    msg_timer.timeout.connect(rotate_msg)
    msg_timer.start(1200)

    # 2. Resolução dos arquivos a abrir (linha de comando ou sessão anterior via QSettings)
    cli_files = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    settings = QSettings("LeitorMD", "ModernMDReader")
    saved_files = settings.value("recent_files", [])
    if isinstance(saved_files, str):
        saved_files = [saved_files] if saved_files else []

    files_to_open: list[str] = []
    if cli_files:
        files_to_open = [str(Path(f).resolve()) for f in cli_files]
    elif saved_files:
        files_to_open = [f for f in saved_files if os.path.exists(f)]

    if not files_to_open:
        files_to_open = [str(Path("documento_exemplo.md").resolve())]

    # 3. Pré-carregamento em background da janela principal
    window = ModernMDReader(files_to_open)

    # 4. Transição segura: fecha o splash e exibe a janela quando a renderização estiver pronta
    is_ready = False

    def on_ready(_ok: bool = True):
        nonlocal is_ready
        if not is_ready:
            is_ready = True
            msg_timer.stop()
            if fallback_timer.isActive():
                fallback_timer.stop()
            splash.finish(window)
            window.show()
            window.raise_()
            window.activateWindow()

    initial_tab = window.current_tab()
    if initial_tab:
        initial_tab.load_finished.connect(on_ready)
    else:
        on_ready()

    # Timer de segurança (fallback de 6s): garante que o app nunca trave no splash
    fallback_timer = QTimer()
    fallback_timer.setSingleShot(True)
    fallback_timer.setInterval(6000)
    fallback_timer.timeout.connect(lambda: on_ready(False))
    fallback_timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
