"""
Leitor Markdown Moderno (md_reader.py)
Um leitor e editor desktop para arquivos Markdown (.md) no Windows.
Desenvolvido com Python, PyQt6, PyQt6-WebEngine, markdown-it-py e pygments.

Versão v1.3.0 "Navegação e Produtividade":
- Sumário lateral (TOC) colapsável (Ctrl+Shift+L) com árvore de cabeçalhos H1-H3 e rolagem suave
- Botão "Copiar" automático nos blocos de código com feedback visual e fallback
- Modo Foco (Ctrl+Shift+F) e Tela Cheia (F11) com saída rápida via Esc
- Recarregar arquivo do disco (F5) com diálogo de confirmação amigável
- Atalho para abrir pasta do arquivo no Windows Explorer (Ctrl+Enter)
- Tema Escuro completo inspirado no GitHub Dark (Ctrl+D) e tela inicial com recentes
- Atalho global de abertura de arquivos (Ctrl+O) e persistência robusta de preferências
- Suporte a múltiplas abas (Ctrl+T, Ctrl+W, Ctrl+Tab), Drag & Drop, Zoom e contador
"""

import importlib.util
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

from PyQt6.QtCore import QByteArray, QPointF, QRect, QSettings, QTimer, QUrl, Qt, pyqtSignal
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
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplashScreen,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
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


# Variável global para guiar a formatação Pygments de acordo com o tema ativo
CURRENT_THEME = "light"


def resource_path(relative_path: str) -> str:
    """Retorna o caminho absoluto do recurso, compatível com PyInstaller (_MEIPASS) e modo dev."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def slugify(text: str) -> str:
    """Gera um slug HTML limpo e único a partir do texto do cabeçalho."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w\s-]", "", normalized).strip().lower()
    slug = re.sub(r"[-\s]+", "-", cleaned).strip("-")
    return slug if slug else "section"


def highlight_code(code: str, lang: str, *args) -> str:
    """
    Realiza o syntax highlighting de blocos de código usando o Pygments.
    Utiliza estilo 'monokai' para tema escuro e 'default' para tema claro.
    Faz fallback para TextLexer caso a linguagem não seja reconhecida.
    """
    lang_name = (lang or "").strip().lower()
    try:
        lexer = get_lexer_by_name(lang_name, stripall=True) if lang_name else TextLexer()
    except Exception:
        lexer = TextLexer()

    style = "monokai" if CURRENT_THEME == "dark" else "default"
    formatter = HtmlFormatter(style=style, nowrap=True)
    return highlight(code, lexer, formatter)


class WelcomeView(QWidget):
    """
    Tela inicial do aplicativo, exibida ao abrir o programa sem documentos ou
    quando todas as abas forem fechadas. Contém atalhos rápidos e lista dos
    últimos 10 arquivos recentes abertos.
    """

    open_file_requested = pyqtSignal(str)
    new_doc_requested = pyqtSignal()
    open_dialog_requested = pyqtSignal()

    def __init__(self, recent_files: list[str], theme: str = "light", parent=None):
        super().__init__(parent)
        self.theme = theme
        self.recent_files = recent_files
        self._build_ui()
        self.apply_theme(theme)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Área de rolagem para telas menores
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area = scroll

        container = QWidget()
        self.container = container
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(40, 40, 40, 40)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        container_layout.setSpacing(24)

        # 1. Cabeçalho da Tela Inicial
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.setSpacing(12)

        icon_label = QLabel()
        icon_path = resource_path("app.ico")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(
                72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(icon_label)

        self.title_label = QLabel("Leitor Markdown Moderno")
        title_font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Escolha um documento recente ou inicie uma nova leitura")
        subtitle_font = QFont("Segoe UI", 12)
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.subtitle_label)

        container_layout.addLayout(header_layout)

        # 2. Botões de Ações Rápidas
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(16)
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_open_file = QPushButton("📂 Abrir Arquivo (Ctrl+O)")
        self.btn_open_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_file.clicked.connect(self.open_dialog_requested.emit)
        actions_layout.addWidget(self.btn_open_file)

        self.btn_new_file = QPushButton("📄 Novo Documento (Ctrl+T)")
        self.btn_new_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_file.clicked.connect(self.new_doc_requested.emit)
        actions_layout.addWidget(self.btn_new_file)

        container_layout.addLayout(actions_layout)

        # 3. Seção de Arquivos Recentes
        self.recents_card = QFrame()
        self.recents_card.setMaximumWidth(700)
        self.recents_card_layout = QVBoxLayout(self.recents_card)
        self.recents_card_layout.setContentsMargins(20, 20, 20, 20)
        self.recents_card_layout.setSpacing(12)

        self.recents_header = QLabel("🕒 Arquivos Recentes")
        self.recents_header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.recents_card_layout.addWidget(self.recents_header)

        self.recents_list_layout = QVBoxLayout()
        self.recents_list_layout.setSpacing(8)
        self.recents_card_layout.addLayout(self.recents_list_layout)

        container_layout.addWidget(self.recents_card)
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        self.render_recents_list()

    def render_recents_list(self):
        """Limpa e redesenha a lista dos últimos arquivos abertos."""
        while self.recents_list_layout.count():
            item = self.recents_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        valid_files = [f for f in self.recent_files if os.path.exists(f)]

        if not valid_files:
            empty_lbl = QLabel("Nenhum documento recente encontrado.")
            empty_lbl.setStyleSheet("color: #8c959f; font-size: 13px; font-style: italic; padding: 10px 0;")
            self.recents_list_layout.addWidget(empty_lbl)
            return

        for path in valid_files[:10]:
            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_layout = QVBoxLayout(btn)
            btn_layout.setContentsMargins(12, 8, 12, 8)
            btn_layout.setSpacing(2)

            name_lbl = QLabel(Path(path).name)
            name_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            path_lbl = QLabel(path)
            path_lbl.setFont(QFont("Segoe UI", 10))
            path_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            btn_layout.addWidget(name_lbl)
            btn_layout.addWidget(path_lbl)

            btn.clicked.connect(lambda checked, p=path: self.open_file_requested.emit(p))
            self.recents_list_layout.addWidget(btn)

    def set_recent_files(self, recent_files: list[str]):
        """Atualiza a lista de arquivos recentes na visualização."""
        self.recent_files = recent_files
        self.render_recents_list()
        self.apply_theme(self.theme)

    def apply_theme(self, theme: str):
        """Aplica os estilos visuais de acordo com o tema claro ou escuro."""
        self.theme = theme
        if theme == "dark":
            bg = "#0d1117"
            card_bg = "#161b22"
            card_border = "#30363d"
            title_color = "#f0f6fc"
            sub_color = "#8b949e"
            btn_bg = "#21262d"
            btn_hover = "#30363d"
            btn_text = "#c9d1d9"
            btn_border = "#30363d"
            item_hover = "#1f242c"
        else:
            bg = "#f6f8fa"
            card_bg = "#ffffff"
            card_border = "#d0d7de"
            title_color = "#1f2328"
            sub_color = "#57606a"
            btn_bg = "#ffffff"
            btn_hover = "#f3f4f6"
            btn_text = "#24292f"
            btn_border = "#d0d7de"
            item_hover = "#f6f8fa"

        self.setStyleSheet(f"background-color: {bg};")
        self.container.setStyleSheet(f"background-color: {bg};")
        self.title_label.setStyleSheet(f"color: {title_color};")
        self.subtitle_label.setStyleSheet(f"color: {sub_color};")
        self.recents_header.setStyleSheet(f"color: {title_color};")

        btn_style = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {btn_border};
                border-radius: 6px;
                padding: 10px 20px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
        """
        self.btn_open_file.setStyleSheet(btn_style)
        self.btn_new_file.setStyleSheet(btn_style)

        self.recents_card.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
            }}
        """)

        # Atualiza estilo dos itens recentes
        for i in range(self.recents_list_layout.count()):
            widget = self.recents_list_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton):
                widget.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: 1px solid transparent;
                        border-radius: 6px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background-color: {item_hover};
                        border-color: {card_border};
                    }}
                """)
                # Atualiza labels internos
                labels = widget.findChildren(QLabel)
                if len(labels) >= 2:
                    labels[0].setStyleSheet(f"color: {btn_text};")
                    labels[1].setStyleSheet(f"color: {sub_color};")


class MarkdownTab(QWidget):
    """
    Representa uma aba individual contendo um documento Markdown.
    Gerencia seu próprio arquivo, editor de texto bruto, visualizador WebEngine,
    autosave com debounce (400ms), zoom independente e renderização HTML dinâmica.
    """

    state_changed = pyqtSignal()
    load_finished = pyqtSignal(bool)
    status_message = pyqtSignal(str)

    def __init__(self, file_path: str, md_parser: MarkdownIt, theme: str = "light", initial_content: str = "", parent=None):
        super().__init__(parent)

        self.md = md_parser
        self.theme = theme
        self.file_path = str(Path(file_path).resolve())
        self.has_unsaved_changes = False
        self.current_zoom = 1.0
        self.toc_items: list[tuple[int, str, str]] = []

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

        # Construção da interface da aba
        self._build_tab_ui()

        # Restaura zoom persistido para este arquivo (se houver)
        settings = QSettings("LeitorMD", "ModernMDReader")
        saved_zoom = float(settings.value(f"zoom/{self.file_path}", 1.0))
        self.set_zoom(saved_zoom, save=False)

        # Aplica o tema inicial
        self.apply_theme(self.theme, reload_view=False)

        # Renderização inicial em modo leitura
        self._load_rendered_view()

    def _build_tab_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget(self)

        # Modo Leitura: QWebEngineView
        self.web_view = QWebEngineView(self)
        self.web_view.setAcceptDrops(False)
        page = self.web_view.page()
        if page is not None:
            page.setBackgroundColor(QColor("#0d1117" if self.theme == "dark" else "#ffffff"))
            page.pdfPrintingFinished.connect(self._on_pdf_printed)

        self.web_view.loadFinished.connect(self._on_web_view_loaded)
        self.stack.addWidget(self.web_view)

        # Modo Edição: QPlainTextEdit
        self.editor = QPlainTextEdit(self)
        self.editor.setAcceptDrops(False)
        editor_font = QFont("Consolas", 14)
        editor_font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(editor_font)
        self.editor.setPlainText(self.current_content)
        self.editor.textChanged.connect(self._on_text_edited)
        self.stack.addWidget(self.editor)

        self.stack.setCurrentIndex(0)
        layout.addWidget(self.stack)

    def _on_web_view_loaded(self, ok: bool):
        """Injeta o botão 'Copiar' nos blocos <pre> após o carregamento da página."""
        if ok:
            js_copy = """
            (function() {
                document.querySelectorAll('pre').forEach(function(pre) {
                    if (pre.querySelector('.copy-btn')) return;
                    var btn = document.createElement('button');
                    btn.className = 'copy-btn';
                    btn.textContent = 'Copiar';
                    btn.setAttribute('type', 'button');
                    btn.setAttribute('aria-label', 'Copiar código');
                    btn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        var codeEl = pre.querySelector('code');
                        var text = codeEl ? codeEl.innerText : pre.innerText;
                        function setSuccess() {
                            btn.textContent = 'Copiado!';
                            setTimeout(function() {
                                btn.textContent = 'Copiar';
                            }, 1500);
                        }
                        function fallbackCopy(val) {
                            var ta = document.createElement('textarea');
                            ta.value = val;
                            ta.style.position = 'fixed';
                            ta.style.left = '-9999px';
                            ta.style.opacity = '0';
                            document.body.appendChild(ta);
                            ta.focus();
                            ta.select();
                            try { document.execCommand('copy'); } catch(err) {}
                            document.body.removeChild(ta);
                        }
                        if (navigator.clipboard && navigator.clipboard.writeText) {
                            navigator.clipboard.writeText(text).then(setSuccess).catch(function() {
                                fallbackCopy(text);
                                setSuccess();
                            });
                        } else {
                            fallbackCopy(text);
                            setSuccess();
                        }
                    });
                    pre.appendChild(btn);
                });
            })();
            """
            page = self.web_view.page()
            if page is not None:
                page.runJavaScript(js_copy)
        self.load_finished.emit(ok)

    def apply_theme(self, theme: str, reload_view: bool = True):
        """Aplica estilos claros ou escuros ao visualizador e ao editor."""
        self.theme = theme
        if theme == "dark":
            bg = "#0d1117"
            text = "#c9d1d9"
            sel_bg = "#1f6feb"
            sel_fg = "#f0f6fc"
        else:
            bg = "#ffffff"
            text = "#24292f"
            sel_bg = "#b6e3ff"
            sel_fg = "#24292f"

        page = self.web_view.page()
        if page is not None:
            page.setBackgroundColor(QColor(bg))
        self.web_view.setStyleSheet(f"background-color: {bg};")

        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {bg};
                color: {text};
                border: none;
                padding: 20px;
                selection-background-color: {sel_bg};
                selection-color: {sel_fg};
            }}
        """)

        if reload_view:
            self._load_rendered_view()

    def _render_html(self, markdown_text: str) -> str:
        """Renderiza Markdown em HTML completo suportando temas claro e escuro, IDs de cabeçalhos e botão copiar."""
        tokens = self.md.parse(markdown_text)
        slug_counts: dict[str, int] = {}
        toc_items: list[tuple[int, str, str]] = []

        for i, token in enumerate(tokens):
            if token.type == "heading_open":
                tag = token.tag.lower()
                level = int(tag[1:]) if len(tag) > 1 and tag[1:].isdigit() else 1
                inline_token = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
                title = inline_token.content if inline_token else ""
                base_slug = slugify(title)
                count = slug_counts.get(base_slug, 0)
                slug_counts[base_slug] = count + 1
                final_slug = base_slug if count == 0 else f"{base_slug}-{count}"
                token.attrs = {"id": final_slug}
                if level in (1, 2, 3):
                    toc_items.append((level, title, final_slug))

        self.toc_items = toc_items
        rendered_body = self.md.renderer.render(tokens, self.md.options, {})

        # Suporte a listas de tarefas (tasklists) no HTML gerado
        rendered_body = re.sub(
            r"<li>\[ \]\s*",
            '<li class="task-list-item"><input type="checkbox" class="task-list-item-checkbox" disabled> ',
            rendered_body,
        )
        rendered_body = re.sub(
            r"<li>\[x\]\s*",
            '<li class="task-list-item"><input type="checkbox" class="task-list-item-checkbox" checked disabled> ',
            rendered_body,
        )

        pygments_style = "monokai" if self.theme == "dark" else "default"
        formatter = HtmlFormatter(style=pygments_style)
        pygments_css = formatter.get_style_defs("pre code")
        pygments_css += "\n" + formatter.get_style_defs("pre")
        pygments_css += "\n" + formatter.get_style_defs(".highlight")

        if self.theme == "dark":
            bg_color = "#0d1117"
            text_color = "#c9d1d9"
            border_color = "#30363d"
            link_color = "#58a6ff"
            code_bg = "#161b22"
            inline_code_bg = "rgba(110, 118, 129, 0.4)"
            blockquote_color = "#8b949e"
            header_color = "#f0f6fc"
            table_row_alt = "#161b22"
            copy_btn_bg = "#21262d"
            copy_btn_hover = "#30363d"
            copy_btn_text = "#c9d1d9"
        else:
            bg_color = "#ffffff"
            text_color = "#24292f"
            border_color = "#d0d7de"
            link_color = "#0969da"
            code_bg = "#f6f8fa"
            inline_code_bg = "rgba(175, 184, 193, 0.2)"
            blockquote_color = "#57606a"
            header_color = "#1f2328"
            table_row_alt = "#f6f8fa"
            copy_btn_bg = "#f6f8fa"
            copy_btn_hover = "#eaeef2"
            copy_btn_text = "#24292f"

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
        color: {text_color};
        background-color: {bg_color};
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
        color: {header_color};
    }}
    h1 {{
        font-size: 2em;
        padding-bottom: 0.3em;
        border-bottom: 1px solid {border_color};
    }}
    h2 {{
        font-size: 1.5em;
        padding-bottom: 0.3em;
        border-bottom: 1px solid {border_color};
    }}
    h3 {{ font-size: 1.25em; }}
    h4 {{ font-size: 1em; }}
    h5 {{ font-size: 0.875em; }}
    h6 {{ font-size: 0.85em; color: {blockquote_color}; }}
    p {{
        margin-top: 0;
        margin-bottom: 16px;
    }}
    a {{
        color: {link_color};
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
        border: 1px solid {border_color};
        padding: 6px 13px;
    }}
    th {{
        font-weight: 600;
        background-color: {code_bg};
        color: {header_color};
    }}
    tr:nth-child(2n) {{
        background-color: {table_row_alt};
    }}
    pre {{
        position: relative;
        background-color: {code_bg};
        padding: 16px;
        border-radius: 6px;
        overflow-x: auto;
        font-size: 85%;
        line-height: 1.45;
        margin-top: 0;
        margin-bottom: 16px;
        border: 1px solid {border_color};
    }}
    .copy-btn {{
        position: absolute;
        top: 8px;
        right: 8px;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s ease, background-color 0.2s;
        background-color: {copy_btn_bg};
        color: {copy_btn_text};
        border: 1px solid {border_color};
        border-radius: 4px;
        padding: 4px 8px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 11px;
        font-weight: 500;
        cursor: pointer;
        user-select: none;
        z-index: 10;
    }}
    pre:hover .copy-btn {{
        opacity: 1;
        pointer-events: auto;
    }}
    .copy-btn:hover {{
        background-color: {copy_btn_hover};
    }}
    code {{
        font-family: Consolas, "Liberation Mono", Menlo, Courier, monospace;
        font-size: 85%;
    }}
    p code, li code, td code {{
        padding: 0.2em 0.4em;
        margin: 0;
        background-color: {inline_code_bg};
        border-radius: 6px;
        color: {text_color};
    }}
    pre code {{
        padding: 0;
        background: transparent;
        border: 0;
        font-size: 100%;
    }}
    blockquote {{
        padding: 0 1em;
        color: {blockquote_color};
        border-left: 0.25em solid {border_color};
        margin: 0 0 16px 0;
    }}
    hr {{
        height: 0.25em;
        padding: 0;
        margin: 24px 0;
        background-color: {border_color};
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
        """Carrega o HTML renderizado no QWebEngineView."""
        html_content = self._render_html(self.current_content)
        base_dir = os.path.dirname(self.file_path)
        base_url = QUrl.fromLocalFile(base_dir + os.sep)
        self.web_view.setHtml(html_content, base_url)

    def get_toc_items(self) -> list[tuple[int, str, str]]:
        """Retorna a lista de cabeçalhos (nível, título, slug) do documento atual."""
        return list(self.toc_items)

    def reload_from_disk(self, parent=None):
        """Relê o arquivo atual do disco e re-renderiza (F5)."""
        if self.has_unsaved_changes:
            file_name = Path(self.file_path).name
            msg_box = QMessageBox(
                QMessageBox.Icon.Question,
                "Recarregar do Disco",
                f"O documento '{file_name}' possui alterações não salvas.\n"
                "Deseja descartar as alterações e recarregar do disco?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                parent or self,
            )
            msg_box.button(QMessageBox.StandardButton.Yes).setText("Descartar e Recarregar")
            msg_box.button(QMessageBox.StandardButton.No).setText("Cancelar")
            res = msg_box.exec()
            if res != QMessageBox.StandardButton.Yes:
                return

        if self.save_timer.isActive():
            self.save_timer.stop()

        target = Path(self.file_path)
        if target.exists():
            self.current_content = target.read_text(encoding="utf-8", errors="replace")
        else:
            self.status_message.emit("Arquivo não encontrado no disco.")
            return

        self.editor.blockSignals(True)
        self.editor.setPlainText(self.current_content)
        self.editor.blockSignals(False)

        self.has_unsaved_changes = False
        self._load_rendered_view()
        self.status_message.emit("Arquivo recarregado do disco com sucesso!")
        self.state_changed.emit()

    def _on_text_edited(self):
        self.has_unsaved_changes = True
        self.current_content = self.editor.toPlainText()
        self.status_message.emit("Digitando...")
        self.state_changed.emit()
        self.save_timer.start(400)

    def _persist_to_disk(self):
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
        self._persist_to_disk()
        self.status_message.emit("Arquivo salvo com sucesso!")

    def save_as(self, new_path: str):
        self.file_path = str(Path(new_path).resolve())
        self._persist_to_disk()
        self._load_rendered_view()
        self.status_message.emit("Arquivo salvo como novo documento!")
        self.state_changed.emit()

    def rename_file(self, new_path: str):
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
    Gerenciador de Abas e Janela Principal do Leitor Markdown Moderno (v1.2.0).
    Suporta tema claro/escuro, tela inicial com arquivos recentes, atalho Ctrl+O,
    restauração de sessão, zoom e contador em tempo real.
    """

    def __init__(self, initial_files: list[str] | str | None = None):
        super().__init__()

        global CURRENT_THEME
        settings = QSettings("LeitorMD", "ModernMDReader")

        # Restaura tema salvo
        self.theme = settings.value("theme", "light")
        CURRENT_THEME = self.theme

        # Restaura geometria da janela se disponível
        saved_geo = settings.value("geometry")
        if isinstance(saved_geo, QByteArray) and not saved_geo.isEmpty():
            self.restoreGeometry(saved_geo)
        else:
            self.resize(1050, 780)

        self.setAcceptDrops(True)

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
        self.is_focus_mode = False
        self._focus_prev_state: dict[str, bool] = {}

        # Montagem da interface
        self._build_ui()
        self._setup_shortcuts()
        self._apply_app_theme()

        # Restaura estado do sumário (TOC) e largura persistidos
        saved_toc_visible = settings.value("toc_visible", True, type=bool)
        saved_toc_width = int(settings.value("toc_width", 240))
        self.toggle_toc(saved_toc_visible)
        cur_sizes = self.splitter.sizes()
        total_w = sum(cur_sizes) if cur_sizes else self.width()
        self.splitter.setSizes([saved_toc_width, max(200, total_w - saved_toc_width)])

        # Restaura modo foco se estava ativo
        saved_focus = settings.value("focus_mode", False, type=bool)
        if saved_focus:
            self.toggle_focus_mode(True)

        # Resolução dos arquivos a abrir
        files_to_open: list[str] = []
        if isinstance(initial_files, str):
            files_to_open = [initial_files]
        elif isinstance(initial_files, list):
            files_to_open = initial_files

        if files_to_open:
            for f in files_to_open:
                self.add_tab_for_file(f, switch_to=False)
            saved_active = settings.value("active_tab_index", 0)
            try:
                saved_active_idx = int(saved_active)
            except (ValueError, TypeError):
                saved_active_idx = 0
            if 0 <= saved_active_idx < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(saved_active_idx)
            elif self.tab_widget.count() > 0:
                self.tab_widget.setCurrentIndex(0)
            self._on_tab_changed(self.tab_widget.currentIndex())
        else:
            # Sem arquivos solicitados: exibe a Tela Inicial
            self.show_welcome_tab()

    def _build_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Bar
        self.top_bar = QWidget()
        self.top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(16, 8, 16, 8)
        top_layout.setSpacing(8)

        # Botão Abrir Arquivo (Ctrl+O)
        self.btn_open = QPushButton("Abrir (Ctrl+O)")
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.clicked.connect(self.open_file_dialog)
        top_layout.addWidget(self.btn_open)

        # Botão Alternar Leitura/Edição (Ctrl+E)
        self.btn_toggle = QPushButton("Alternar para Edição (Ctrl+E)")
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.clicked.connect(self.toggle_mode)
        top_layout.addWidget(self.btn_toggle)

        # Botão Sumário (Ctrl+Shift+L)
        self.btn_toc = QPushButton("Sumário (Ctrl+Shift+L)")
        self.btn_toc.setToolTip("Exibir ou ocultar o Sumário lateral (Ctrl+Shift+L)")
        self.btn_toc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toc.clicked.connect(lambda: self.toggle_toc())
        top_layout.addWidget(self.btn_toc)

        # Botão Buscar (Ctrl+F)
        self.btn_search = QPushButton("Buscar (Ctrl+F)")
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.clicked.connect(self.toggle_search_bar)
        top_layout.addWidget(self.btn_search)

        # Botão Exportar PDF (Ctrl+P)
        self.btn_pdf = QPushButton("Exportar PDF (Ctrl+P)")
        self.btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf.clicked.connect(self.export_pdf)
        top_layout.addWidget(self.btn_pdf)

        # Botão Alternar Tema (Ctrl+D)
        self.btn_theme = QPushButton("Tema (Ctrl+D)")
        self.btn_theme.setToolTip("Alternar entre Tema Claro e Escuro (Ctrl+D)")
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        top_layout.addWidget(self.btn_theme)

        # Controles de Zoom
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setToolTip("Diminuir Zoom (Ctrl+ -)")
        self.btn_zoom_out.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        top_layout.addWidget(self.btn_zoom_out)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setToolTip("Zoom atual (Ctrl+0 para restaurar)")
        top_layout.addWidget(self.lbl_zoom)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setToolTip("Aumentar Zoom (Ctrl+ +)")
        self.btn_zoom_in.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        top_layout.addWidget(self.btn_zoom_in)

        top_layout.addStretch()

        self.lbl_status = QLabel("Modo: Leitura")
        top_layout.addWidget(self.lbl_status)

        main_layout.addWidget(self.top_bar)

        # 2. Barra de Busca Integrada
        self.search_bar = QWidget()
        self.search_bar.setObjectName("searchBar")
        self.search_bar.setVisible(False)
        search_layout = QHBoxLayout(self.search_bar)
        search_layout.setContentsMargins(16, 6, 16, 6)
        search_layout.setSpacing(8)

        self.search_label = QLabel("Buscar:")
        search_layout.addWidget(self.search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Digite o termo e pressione Enter...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(lambda: self.find_next(backward=False))
        QShortcut(QKeySequence("Shift+Return"), self.search_input).activated.connect(
            lambda: self.find_next(backward=True)
        )
        search_layout.addWidget(self.search_input)

        self.btn_prev = QPushButton("▲")
        self.btn_prev.setToolTip("Ocorrência anterior (Shift+Enter)")
        self.btn_prev.clicked.connect(lambda: self.find_next(backward=True))
        search_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("▼")
        self.btn_next.setToolTip("Próxima ocorrência (Enter)")
        self.btn_next.clicked.connect(lambda: self.find_next(backward=False))
        search_layout.addWidget(self.btn_next)

        self.btn_close_search = QPushButton("✕")
        self.btn_close_search.setToolTip("Fechar busca (Esc)")
        self.btn_close_search.clicked.connect(self.close_search_bar)
        search_layout.addWidget(self.btn_close_search)

        main_layout.addWidget(self.search_bar)

        # 3. Gerenciador de Abas (QTabWidget)
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)

        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.tab_widget.tabBarDoubleClicked.connect(self._on_tab_double_clicked)

        # Botão "+" para nova aba no canto direito
        self.btn_add_tab = QPushButton("+")
        self.btn_add_tab.setToolTip("Nova Aba (Ctrl+T)")
        self.btn_add_tab.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_tab.clicked.connect(self.new_tab)
        self.tab_widget.setCornerWidget(self.btn_add_tab, Qt.Corner.TopRightCorner)

        # 4. Painel Lateral de Sumário (TOC) e Splitter Horizontal
        self.toc_panel = QWidget()
        self.toc_panel.setObjectName("tocPanel")
        toc_layout = QVBoxLayout(self.toc_panel)
        toc_layout.setContentsMargins(0, 0, 0, 0)
        toc_layout.setSpacing(0)

        self.toc_header = QWidget()
        self.toc_header.setObjectName("tocHeader")
        toc_header_layout = QHBoxLayout(self.toc_header)
        toc_header_layout.setContentsMargins(12, 8, 8, 8)
        toc_header_layout.setSpacing(6)

        self.lbl_toc_title = QLabel("📑 Sumário")
        self.lbl_toc_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        toc_header_layout.addWidget(self.lbl_toc_title)
        toc_header_layout.addStretch()

        self.btn_close_toc = QPushButton("✕")
        self.btn_close_toc.setToolTip("Fechar Sumário (Ctrl+Shift+L)")
        self.btn_close_toc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close_toc.clicked.connect(lambda: self.toggle_toc(False))
        toc_header_layout.addWidget(self.btn_close_toc)

        toc_layout.addWidget(self.toc_header)

        self.toc_tree = QTreeWidget()
        self.toc_tree.setHeaderHidden(True)
        self.toc_tree.setIndentation(14)
        self.toc_tree.setAnimated(True)
        self.toc_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toc_tree.itemClicked.connect(self._on_toc_item_clicked)
        toc_layout.addWidget(self.toc_tree)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, central_widget)
        self.splitter.setObjectName("mainSplitter")
        self.splitter.addWidget(self.toc_panel)
        self.splitter.addWidget(self.tab_widget)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

        main_layout.addWidget(self.splitter)

        # 5. Status Bar com contador de palavras
        self.status_bar = self.statusBar()
        self.lbl_stats = QLabel("Palavras: 0 | Caracteres: 0 | Tempo de leitura: < 1 min")
        self.status_bar.addWidget(self.lbl_stats)

        self.lbl_file_path = QLabel("")
        self.status_bar.addPermanentWidget(self.lbl_file_path)

    def _setup_shortcuts(self):
        """Registra os atalhos de teclado do aplicativo."""
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_file_dialog)
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self.new_tab)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(lambda: self.close_tab(self.tab_widget.currentIndex()))
        QShortcut(QKeySequence("Ctrl+Tab"), self).activated.connect(self.next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self).activated.connect(self.prev_tab)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.toggle_theme)

        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.toggle_mode)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.toggle_search_bar)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self.export_pdf)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_manual)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.save_as)
        QShortcut(QKeySequence("Ctrl+Shift+L"), self).activated.connect(self.toggle_toc)
        QShortcut(QKeySequence("F11"), self).activated.connect(self.toggle_fullscreen)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self).activated.connect(self.toggle_focus_mode)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.reload_current_file)
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.open_file_folder)
        QShortcut(QKeySequence("Ctrl+Enter"), self).activated.connect(self.open_file_folder)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.handle_escape)

        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(self.zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(self.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(self.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(self.zoom_reset)

    def _apply_app_theme(self):
        """Atualiza a folha de estilos da janela principal, abas, barra de busca e status bar."""
        is_dark = self.theme == "dark"

        if is_dark:
            top_bg = "#161b22"
            border = "#30363d"
            text_color = "#c9d1d9"
            sub_text = "#8b949e"
            btn_bg = "#21262d"
            btn_hover = "#30363d"
            btn_border = "#30363d"
            primary_bg = "#1f6feb"
            primary_hover = "#388bfd"
            search_bg = "#0d1117"
            input_bg = "#161b22"
            status_bg = "#161b22"
            self.btn_theme.setText("☀️ Claro (Ctrl+D)")
        else:
            top_bg = "#ffffff"
            border = "#d0d7de"
            text_color = "#24292f"
            sub_text = "#57606a"
            btn_bg = "#f6f8fa"
            btn_hover = "#f3f4f6"
            btn_border = "#d0d7de"
            primary_bg = "#0969da"
            primary_hover = "#0860ca"
            search_bg = "#f6f8fa"
            input_bg = "#ffffff"
            status_bg = "#f6f8fa"
            self.btn_theme.setText("🌙 Escuro (Ctrl+D)")

        self.top_bar.setStyleSheet(f"""
            QWidget#topBar {{
                background-color: {top_bg};
                border-bottom: 1px solid {border};
            }}
        """)

        btn_common = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text_color};
                border: 1px solid {btn_border};
                border-radius: 6px;
                padding: 6px 12px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
        """

        btn_compact = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text_color};
                border: 1px solid {btn_border};
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
        """

        btn_primary = f"""
            QPushButton {{
                background-color: {primary_bg};
                color: #ffffff;
                border: 1px solid {primary_bg};
                border-radius: 6px;
                padding: 6px 12px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {primary_hover};
            }}
        """

        self.btn_open.setStyleSheet(btn_common)
        self.btn_toggle.setStyleSheet(btn_primary)
        self.btn_toc.setStyleSheet(btn_common)
        self.btn_search.setStyleSheet(btn_common)
        self.btn_pdf.setStyleSheet(btn_common)
        self.btn_theme.setStyleSheet(btn_common)
        self.btn_zoom_out.setStyleSheet(btn_compact)
        self.btn_zoom_in.setStyleSheet(btn_compact)

        self.lbl_zoom.setStyleSheet(f"color: {text_color}; font-size: 12px; font-weight: 600; padding: 0 4px;")
        self.lbl_status.setStyleSheet(f"color: {sub_text}; font-size: 13px; font-weight: 500;")

        # Barra de Busca
        self.search_bar.setStyleSheet(f"QWidget#searchBar {{ background-color: {search_bg}; border-bottom: 1px solid {border}; }}")
        self.search_label.setStyleSheet(f"color: {text_color}; font-size: 13px; font-weight: 500;")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {primary_bg};
            }}
        """)
        self.btn_prev.setStyleSheet(btn_compact)
        self.btn_next.setStyleSheet(btn_compact)
        self.btn_close_search.setStyleSheet(btn_compact)

        # Tab Widget e Corner Button
        self.tab_widget.setStyleSheet(self._tab_widget_style(drag_active=False))
        self.btn_add_tab.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text_color};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 14px;
                font-weight: bold;
                margin-right: 8px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover};
            }}
        """)

        # Painel Lateral de Sumário (TOC) e Splitter
        self.toc_panel.setStyleSheet(f"""
            QWidget#tocPanel {{
                background-color: {top_bg};
                border-right: 1px solid {border};
            }}
        """)
        self.toc_header.setStyleSheet(f"""
            QWidget#tocHeader {{
                background-color: {top_bg};
                border-bottom: 1px solid {border};
            }}
        """)
        self.lbl_toc_title.setStyleSheet(f"color: {text_color};")
        self.btn_close_toc.setStyleSheet(btn_compact)
        self.toc_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {top_bg};
                color: {text_color};
                border: none;
                padding: 6px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 13px;
            }}
            QTreeWidget::item {{
                padding: 4px 6px;
                border-radius: 4px;
            }}
            QTreeWidget::item:hover {{
                background-color: {btn_hover};
            }}
            QTreeWidget::item:selected {{
                background-color: {'#1f242c' if is_dark else '#eaeef2'};
                color: {'#58a6ff' if is_dark else '#0969da'};
                font-weight: 600;
            }}
        """)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {border};
            }}
            QSplitter::handle:horizontal {{
                width: 1px;
            }}
        """)

        # Status Bar
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {status_bg};
                color: {sub_text};
                border-top: 1px solid {border};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 12px;
                padding: 2px 12px;
            }}
        """)
        self.lbl_stats.setStyleSheet(f"color: {sub_text}; font-weight: 500;")
        self.lbl_file_path.setStyleSheet(f"color: {sub_text}; font-size: 11px;")

    def _tab_widget_style(self, drag_active: bool = False) -> str:
        is_dark = self.theme == "dark"

        if is_dark:
            border = "#30363d"
            tab_bg = "#161b22"
            tab_selected_bg = "#0d1117"
            tab_hover_bg = "#21262d"
            text_color = "#8b949e"
            text_selected = "#58a6ff"
            accent_line = "#1f6feb"
            close_hover = "#30363d"
            pane_bg = "#0d1117"
            drag_border = "2px dashed #58a6ff"
        else:
            border = "#d0d7de"
            tab_bg = "#f6f8fa"
            tab_selected_bg = "#ffffff"
            tab_hover_bg = "#eaeef2"
            text_color = "#57606a"
            text_selected = "#0969da"
            accent_line = "#0969da"
            close_hover = "#d0d7de"
            pane_bg = "#ffffff"
            drag_border = "2px dashed #0969da"

        pane_border = drag_border if drag_active else "none"

        return f"""
            QTabWidget::pane {{
                border: {pane_border};
                background-color: {pane_bg};
            }}
            QTabBar {{
                background-color: {tab_bg};
                border-bottom: 1px solid {border};
            }}
            QTabBar::tab {{
                background-color: {tab_bg};
                color: {text_color};
                border: 1px solid {border};
                border-bottom: none;
                padding: 7px 16px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 13px;
                font-weight: 500;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                margin-top: 3px;
            }}
            QTabBar::tab:selected {{
                background-color: {tab_selected_bg};
                color: {text_selected};
                font-weight: 600;
                border-color: {border};
                border-bottom: 2px solid {accent_line};
                margin-top: 1px;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {tab_hover_bg};
            }}
            QTabBar::close-button {{
                subcontrol-position: right;
                padding: 2px;
                border-radius: 4px;
            }}
            QTabBar::close-button:hover {{
                background-color: {close_hover};
            }}
        """

    def toggle_theme(self):
        """Alterna o tema entre Claro e Escuro para todo o aplicativo e todas as abas (Ctrl+D)."""
        global CURRENT_THEME
        self.theme = "dark" if self.theme == "light" else "light"
        CURRENT_THEME = self.theme

        settings = QSettings("LeitorMD", "ModernMDReader")
        settings.setValue("theme", self.theme)

        self._apply_app_theme()

        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, MarkdownTab):
                widget.apply_theme(self.theme)
            elif isinstance(widget, WelcomeView):
                widget.apply_theme(self.theme)

    # Persistência de Arquivos Recentes
    def get_recent_files(self) -> list[str]:
        settings = QSettings("LeitorMD", "ModernMDReader")
        raw = settings.value("recent_files", [])
        if isinstance(raw, str):
            raw = [raw] if raw else []
        return [f for f in raw if os.path.exists(f)][:10]

    def add_recent_file(self, file_path: str):
        resolved = str(Path(file_path).resolve())
        settings = QSettings("LeitorMD", "ModernMDReader")
        recents = self.get_recent_files()

        if resolved in recents:
            recents.remove(resolved)
        recents.insert(0, resolved)
        recents = recents[:10]

        settings.setValue("recent_files", recents)

        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, WelcomeView):
                widget.set_recent_files(recents)

    # Gerenciamento de Abas
    def current_tab(self) -> MarkdownTab | None:
        widget = self.tab_widget.currentWidget()
        return widget if isinstance(widget, MarkdownTab) else None

    def get_tab(self, index: int) -> MarkdownTab | None:
        widget = self.tab_widget.widget(index)
        return widget if isinstance(widget, MarkdownTab) else None

    def show_welcome_tab(self):
        """Exibe a tela inicial/boas-vindas com arquivos recentes."""
        welcome = WelcomeView(self.get_recent_files(), theme=self.theme, parent=self.tab_widget)
        welcome.open_file_requested.connect(lambda path: self.open_file_in_tab(path, in_new_tab=True))
        welcome.new_doc_requested.connect(self.new_tab)
        welcome.open_dialog_requested.connect(self.open_file_dialog)

        idx = self.tab_widget.addTab(welcome, "Início")
        self.tab_widget.setCurrentIndex(idx)
        self._on_tab_changed(idx)

    def add_tab_for_file(self, file_path: str, initial_content: str = "", switch_to: bool = True) -> MarkdownTab:
        tab = MarkdownTab(file_path, self.md, theme=self.theme, initial_content=initial_content, parent=self.tab_widget)
        tab.state_changed.connect(self._on_tab_state_changed)
        tab.status_message.connect(self.lbl_status.setText)
        tab.load_finished.connect(lambda ok: self.update_toc())

        file_name = Path(tab.file_path).name
        index = self.tab_widget.addTab(tab, file_name)
        self.tab_widget.setTabToolTip(index, tab.file_path)

        self.add_recent_file(tab.file_path)

        if switch_to:
            self.tab_widget.setCurrentIndex(index)
        return tab

    def open_file_dialog(self):
        """Abre o diálogo do sistema para selecionar um ou mais arquivos Markdown (Ctrl+O)."""
        settings = QSettings("LeitorMD", "ModernMDReader")
        default_dir = settings.value("last_directory", str(Path.home() / "Documents"))
        if not os.path.exists(default_dir):
            default_dir = str(Path.home())

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Abrir Arquivos Markdown",
            default_dir,
            "Documentos Markdown (*.md *.markdown *.txt);;Todos os Arquivos (*.*)",
        )
        if files:
            settings.setValue("last_directory", str(Path(files[0]).parent))
            for f in files:
                self.open_file_in_tab(f, in_new_tab=True)

    def open_file_in_tab(self, file_path: str, in_new_tab: bool = True):
        abs_path = str(Path(file_path).resolve())

        # Se a única aba for a tela inicial, fecha ela para dar lugar ao arquivo
        if self.tab_widget.count() == 1 and isinstance(self.tab_widget.widget(0), WelcomeView):
            self.tab_widget.removeTab(0)

        # Se o arquivo já estiver aberto, foca na aba
        for i in range(self.tab_widget.count()):
            tab = self.get_tab(i)
            if tab and tab.file_path == abs_path:
                self.tab_widget.setCurrentIndex(i)
                return

        if in_new_tab or self.current_tab() is None:
            self.add_tab_for_file(abs_path, switch_to=True)
        else:
            tab = self.current_tab()
            if tab:
                tab.load_file(abs_path)
                self.add_recent_file(abs_path)
                self._update_tab_title(self.tab_widget.currentIndex())
                self._update_window_title()
                self._update_word_stats()
                self._update_zoom_label()

    def new_tab(self):
        """Cria um novo documento Markdown em branco (Ctrl+T)."""
        if self.tab_widget.count() == 1 and isinstance(self.tab_widget.widget(0), WelcomeView):
            self.tab_widget.removeTab(0)

        self.untitled_counter += 1
        settings = QSettings("LeitorMD", "ModernMDReader")
        default_dir = settings.value("last_directory", str(Path.home() / "Documents"))
        if not os.path.exists(default_dir):
            default_dir = str(Path.home())

        new_path = Path(default_dir) / f"Sem título {self.untitled_counter}.md"
        initial_content = f"# Sem título {self.untitled_counter}\n\nComece a escrever aqui...\n"
        tab = self.add_tab_for_file(str(new_path), initial_content=initial_content, switch_to=True)
        if tab:
            tab.toggle_mode()

    def close_tab(self, index: int):
        """Fecha a aba indicada, solicitando salvamento se houver alterações (Ctrl+W)."""
        if index < 0 or index >= self.tab_widget.count():
            return

        widget = self.tab_widget.widget(index)
        if isinstance(widget, WelcomeView):
            self.tab_widget.removeTab(index)
            widget.deleteLater()
            if self.tab_widget.count() == 0:
                self.new_tab()
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

        # Ao fechar todas as abas, exibe a Tela Inicial
        if self.tab_widget.count() == 0:
            self.show_welcome_tab()
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
            self.add_recent_file(str(new_path))
            self._update_tab_title(index)
            self._update_window_title()

    def _on_tab_changed(self, index: int):
        widget = self.tab_widget.widget(index)
        if isinstance(widget, WelcomeView):
            self.btn_toggle.setEnabled(False)
            self.btn_pdf.setEnabled(False)
            self.btn_search.setEnabled(False)
            self.btn_toc.setEnabled(False)
            self.lbl_status.setText("Início")
            self.lbl_stats.setText("Bem-vindo ao Leitor Markdown Moderno")
            self.lbl_file_path.setText("")
            self.setWindowTitle("Leitor Markdown Moderno - Início")
            self.update_toc()
            return

        tab = self.get_tab(index)
        if not tab:
            self.btn_toc.setEnabled(False)
            self.update_toc()
            return

        self.btn_toggle.setEnabled(True)
        self.btn_pdf.setEnabled(True)
        self.btn_search.setEnabled(True)
        self.btn_toc.setEnabled(True)

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
        self.update_toc()

        if self.search_bar.isVisible() and self.search_input.text():
            tab.find_text(self.search_input.text(), backward=False)

    def _on_tab_state_changed(self):
        idx = self.tab_widget.currentIndex()
        self._update_tab_title(idx)
        self._update_window_title()
        self._update_word_stats()
        self._update_zoom_label()
        self.update_toc()

    def _update_tab_title(self, index: int):
        widget = self.tab_widget.widget(index)
        if isinstance(widget, WelcomeView):
            self.tab_widget.setTabText(index, "Início")
            return

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
            self.add_recent_file(new_path)
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

    # Sumário Lateral (TOC)
    def toggle_toc(self, visible: bool | None = None):
        """Alterna ou define a visibilidade do painel de sumário lateral (Ctrl+Shift+L)."""
        if visible is None:
            visible = not self.toc_panel.isVisible()
        self.toc_panel.setVisible(visible)

        settings = QSettings("LeitorMD", "ModernMDReader")
        settings.setValue("toc_visible", visible)

        if visible:
            saved_width = int(settings.value("toc_width", 240))
            cur_sizes = self.splitter.sizes()
            total_w = sum(cur_sizes) if cur_sizes else self.width()
            self.splitter.setSizes([saved_width, max(200, total_w - saved_width)])
            self.update_toc()

    def _on_splitter_moved(self, pos: int, index: int):
        """Salva a largura do painel lateral quando o usuário redimensiona o splitter."""
        if self.toc_panel.isVisible() and pos > 50:
            settings = QSettings("LeitorMD", "ModernMDReader")
            settings.setValue("toc_width", pos)

    def update_toc(self):
        """Atualiza a árvore de cabeçalhos H1, H2, H3 do documento ativo."""
        self.toc_tree.clear()
        tab = self.current_tab()
        if not tab:
            item = QTreeWidgetItem(["Nenhum documento aberto"])
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.toc_tree.addTopLevelItem(item)
            return

        toc_items = tab.get_toc_items()
        if not toc_items:
            item = QTreeWidgetItem(["Nenhum cabeçalho encontrado"])
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.toc_tree.addTopLevelItem(item)
            return

        last_h1: QTreeWidgetItem | None = None
        last_h2: QTreeWidgetItem | None = None

        for level, title, slug in toc_items:
            clean_title = title.strip()
            item = QTreeWidgetItem([clean_title])
            item.setData(0, Qt.ItemDataRole.UserRole, slug)
            item.setToolTip(0, clean_title)

            font = QFont("Segoe UI", 10)
            if level == 1:
                font.setBold(True)
                item.setFont(0, font)
                self.toc_tree.addTopLevelItem(item)
                last_h1 = item
                last_h2 = None
            elif level == 2:
                font.setWeight(QFont.Weight.DemiBold)
                item.setFont(0, font)
                if last_h1:
                    last_h1.addChild(item)
                else:
                    self.toc_tree.addTopLevelItem(item)
                last_h2 = item
            else:
                item.setFont(0, font)
                if last_h2:
                    last_h2.addChild(item)
                elif last_h1:
                    last_h1.addChild(item)
                else:
                    self.toc_tree.addTopLevelItem(item)

        self.toc_tree.expandAll()

    def _on_toc_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Rola a página no modo leitura ou move o cursor no modo edição até o cabeçalho."""
        slug = item.data(0, Qt.ItemDataRole.UserRole)
        if not slug:
            return
        tab = self.current_tab()
        if not tab:
            return

        if tab.stack.currentIndex() == 0:
            js = f"""
            (function() {{
                var el = document.getElementById({json.dumps(slug)});
                if (el) {{
                    el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
                }}
            }})();
            """
            page = tab.web_view.page()
            if page is not None:
                page.runJavaScript(js)
        else:
            title = item.text(0).strip().lower()
            text = tab.editor.toPlainText()
            pos = 0
            for line in text.splitlines(keepends=True):
                stripped = line.strip()
                if stripped.startswith("#") and title in stripped.lower():
                    cursor = tab.editor.textCursor()
                    cursor.setPosition(pos)
                    tab.editor.setTextCursor(cursor)
                    tab.editor.centerCursor()
                    tab.editor.setFocus()
                    break
                pos += len(line)

    # Modo Foco e Tela Cheia
    def toggle_fullscreen(self):
        """Alterna entre Tela Cheia e modo normal de janela (F11)."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def toggle_focus_mode(self, active: bool | None = None):
        """Alterna ou define o Modo Foco (Ctrl+Shift+F), ocultando barras e abas para leitura imersiva."""
        if active is None:
            active = not self.is_focus_mode
        self.is_focus_mode = active

        settings = QSettings("LeitorMD", "ModernMDReader")
        settings.setValue("focus_mode", self.is_focus_mode)

        if self.is_focus_mode:
            self._focus_prev_state = {
                "top_bar": self.top_bar.isVisible(),
                "search_bar": self.search_bar.isVisible(),
                "status_bar": self.status_bar.isVisible(),
                "toc_panel": self.toc_panel.isVisible(),
            }
            self.top_bar.setVisible(False)
            self.search_bar.setVisible(False)
            self.status_bar.setVisible(False)
            self.toc_panel.setVisible(False)
            self.tab_widget.tabBar().setVisible(False)
        else:
            prev = getattr(self, "_focus_prev_state", {})
            self.top_bar.setVisible(prev.get("top_bar", True))
            self.search_bar.setVisible(prev.get("search_bar", False))
            self.status_bar.setVisible(prev.get("status_bar", True))
            self.tab_widget.tabBar().setVisible(True)
            saved_toc = settings.value("toc_visible", True, type=bool)
            self.toggle_toc(saved_toc)

    def handle_escape(self):
        """Trata o pressionamento da tecla Escape (fecha busca ou sai do modo foco)."""
        if self.search_bar.isVisible():
            self.close_search_bar()
        elif self.is_focus_mode:
            self.toggle_focus_mode(False)

    def reload_current_file(self):
        """Recarrega o arquivo atual diretamente do disco (F5)."""
        tab = self.current_tab()
        if tab:
            tab.reload_from_disk(parent=self)
            self._update_tab_title(self.tab_widget.currentIndex())
            self._update_window_title()
            self._update_word_stats()
            self._update_zoom_label()
            self.update_toc()

    def open_file_folder(self):
        """Abre o Windows Explorer na pasta contendo o arquivo ativo (Ctrl+Enter)."""
        tab = self.current_tab()
        if not tab:
            return
        folder = os.path.dirname(tab.file_path)
        if os.path.exists(folder):
            try:
                os.startfile(folder)
                self.lbl_status.setText(f"Pasta aberta no Explorer: {folder}")
            except Exception as e:
                self.lbl_status.setText(f"Erro ao abrir pasta: {e}")

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

        if len(valid_paths) > 1:
            for p in valid_paths:
                self.open_file_in_tab(p, in_new_tab=True)
        else:
            single_path = valid_paths[0]
            tab_bar = self.tab_widget.tabBar()
            tab_bar_pos = tab_bar.mapFrom(self, a0.position().toPoint())
            if tab_bar.rect().contains(tab_bar_pos):
                self.open_file_in_tab(single_path, in_new_tab=True)
            else:
                self.open_file_in_tab(single_path, in_new_tab=False)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Salva todas as preferências e estados em QSettings ao fechar o programa."""
        settings = QSettings("LeitorMD", "ModernMDReader")

        # 1. Salva geometria da janela
        settings.setValue("geometry", self.saveGeometry())

        # 2. Salva tema ativo
        settings.setValue("theme", self.theme)

        # 3. Salva arquivos abertos e aba ativa
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

        settings.setValue("open_tabs", open_paths)
        settings.setValue("active_tab_index", self.tab_widget.currentIndex())

        # 4. Salva estado do sumário (TOC), largura e modo foco
        is_toc_vis = self.toc_panel.isVisible() if not self.is_focus_mode else self._focus_prev_state.get("toc_panel", True)
        settings.setValue("toc_visible", is_toc_vis)
        sizes = self.splitter.sizes()
        if sizes and sizes[0] > 50:
            settings.setValue("toc_width", sizes[0])
        settings.setValue("focus_mode", self.is_focus_mode)

        if a0 is not None:
            super().closeEvent(a0)


def create_splash_screen() -> QSplashScreen:
    """Cria e retorna tela de splash profissional Dark Card."""
    width, height = 380, 220
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setBrush(QColor("#0f172a"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, width, height, 16, 16)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QColor("#1e293b"))
    painter.drawRoundedRect(0, 0, width - 1, height - 1, 16, 16)

    icon_path = resource_path("app.ico")
    if os.path.exists(icon_path):
        icon_pixmap = QPixmap(icon_path).scaled(
            64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap((width - 64) // 2, 26, icon_pixmap)

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

    # 1. Splash Screen profissional imediato
    splash = create_splash_screen()
    splash.show()
    app.processEvents()

    messages = [
        "Inicializando ambiente de leitura...",
        "Carregando componentes gráficos...",
        "Restaurando preferências e abas...",
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

    # 2. Resolução dos arquivos a abrir
    cli_files = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    settings = QSettings("LeitorMD", "ModernMDReader")
    saved_tabs = settings.value("open_tabs", [])
    if isinstance(saved_tabs, str):
        saved_tabs = [saved_tabs] if saved_tabs else []

    files_to_open: list[str] = []
    if cli_files:
        files_to_open = [str(Path(f).resolve()) for f in cli_files]
    elif saved_tabs:
        files_to_open = [f for f in saved_tabs if os.path.exists(f)]

    # 3. Inicialização da janela principal
    # Se houver arquivos a abrir, passa a lista; senão, ModernMDReader abre a tela inicial
    window = ModernMDReader(files_to_open if files_to_open else None)

    # 4. Transição segura para exibição da janela
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
        # Se for tela de Início, exibe sem aguardar WebEngine
        on_ready()

    fallback_timer = QTimer()
    fallback_timer.setSingleShot(True)
    fallback_timer.setInterval(6000)
    fallback_timer.timeout.connect(lambda: on_ready(False))
    fallback_timer.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
