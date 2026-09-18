"""
Leitor Markdown Moderno (md_reader.py)
Um leitor e editor desktop para arquivos Markdown (.md) no Windows.
Desenvolvido com PyQt6, PyQt6-WebEngine, markdown-it-py e pygments.
Inclui suporte a busca no documento (Ctrl+F), exportação para PDF (Ctrl+P)
e salvamento com atalhos (Ctrl+S / Ctrl+Shift+S).
"""

import importlib.util
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer, QUrl, Qt
from PyQt6.QtGui import (
    QCloseEvent,
    QFont,
    QIcon,
    QKeySequence,
    QShortcut,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
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


class ModernMDReader(QMainWindow):
    """
    Janela principal do Leitor Markdown Moderno.
    Suporta alternância entre modo Leitura (QWebEngineView) e Edição (QPlainTextEdit),
    salvamento com debounce, busca em tempo real (Ctrl+F) e exportação para PDF (Ctrl+P).
    """

    def __init__(self, file_path: str):
        super().__init__()

        # Resolução e garantia de caminho absoluto
        resolved_path = Path(file_path).resolve()
        self.file_path = str(resolved_path)
        file_name = resolved_path.name

        # Configurações básicas da janela principal
        self.setWindowTitle(f"Leitor Markdown Moderno - {file_name}")
        self.resize(1000, 750)

        # Ícone da janela compatível com PyInstaller e modo dev
        icon_file = resource_path("app.ico")
        if os.path.exists(icon_file):
            self.setWindowIcon(QIcon(icon_file))

        # Criação do arquivo com conteúdo inicial padrão caso não exista
        if not resolved_path.exists():
            if resolved_path.parent:
                resolved_path.parent.mkdir(parents=True, exist_ok=True)
            initial_content = "# Novo Documento\nComece a escrever...\n"
            resolved_path.write_text(initial_content, encoding="utf-8")
            self.current_content = initial_content
        else:
            self.current_content = resolved_path.read_text(encoding="utf-8", errors="replace")

        # Flag para controle de alterações não salvas
        self.has_unsaved_changes = False

        # Timer para autosave com debounce (400ms)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(self._persist_to_disk)

        # Verificação dinâmica da biblioteca linkify-it-py sem gerar erro de import no linter da IDE
        has_linkify = importlib.util.find_spec("linkify_it") is not None

        # Inicialização do parser Markdown com GFM e extensões obrigatórias
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

        # Construção da interface gráfica
        self._build_ui()

        # Renderização inicial em modo leitura
        self._load_rendered_view()

    def _build_ui(self):
        """Constrói a interface com top bar, barra de busca, stacked widget e atalhos."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Barra superior (Top Bar)
        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setStyleSheet("""
            QWidget#topBar {
                background-color: #ffffff;
                border-bottom: 1px solid #d0d7de;
            }
        """)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 10, 16, 10)
        top_layout.setSpacing(8)

        # Botão de alternância entre Leitura e Edição
        self.btn_toggle = QPushButton("Alternar para Edição (Ctrl+E)")
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet(self._button_style(primary=True))
        self.btn_toggle.clicked.connect(self.toggle_mode)
        top_layout.addWidget(self.btn_toggle)

        # Botão de busca (Ctrl+F)
        self.btn_search = QPushButton("Buscar (Ctrl+F)")
        self.btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_search.setStyleSheet(self._button_style(primary=False))
        self.btn_search.clicked.connect(self.toggle_search_bar)
        top_layout.addWidget(self.btn_search)

        # Botão de exportar para PDF (Ctrl+P)
        self.btn_pdf = QPushButton("Exportar PDF (Ctrl+P)")
        self.btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pdf.setStyleSheet(self._button_style(primary=False))
        self.btn_pdf.clicked.connect(self.export_pdf)
        top_layout.addWidget(self.btn_pdf)

        top_layout.addStretch()

        # Label de status na extremidade direita
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

        # Barra de Busca integrada (Ctrl+F)
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
        self.search_input.setPlaceholderText("Digite o termo a pesquisar e pressione Enter...")
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

        # Stack de visualização (Índice 0: Leitura / Índice 1: Edição)
        self.stack = QStackedWidget()

        # Modo Leitura: QWebEngineView
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background-color: #ffffff;")
        page = self.web_view.page()
        if page is not None:
            page.pdfPrintingFinished.connect(self._on_pdf_printed)
        self.stack.addWidget(self.web_view)

        # Modo Edição: QPlainTextEdit
        self.editor = QPlainTextEdit()
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

        # Define índice inicial no modo Leitura (0)
        self.stack.setCurrentIndex(0)
        main_layout.addWidget(self.stack)

        # Atalhos de Teclado Globais
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self.toggle_mode)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.toggle_search_bar)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self.export_pdf)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_manual)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.save_as)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.close_search_bar)

    def _button_style(self, primary: bool = False, compact: bool = False) -> str:
        """Retorna o estilo QSS padronizado para os botões da barra superior."""
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

    def _render_html(self, markdown_text: str) -> str:
        """
        Renderiza o texto Markdown em HTML completo, incluindo estilos
        GitHub Markdown e regras do Pygments para blocos de código.
        """
        rendered_body = self.md.render(markdown_text)

        pygments_css = HtmlFormatter().get_style_defs('pre code')
        pygments_css += "\n" + HtmlFormatter().get_style_defs('pre')
        pygments_css += "\n" + HtmlFormatter().get_style_defs('.highlight')

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
        """Carrega o HTML renderizado no QWebEngineView usando o diretório base do arquivo."""
        html_content = self._render_html(self.current_content)
        base_dir = os.path.dirname(self.file_path)
        base_url = QUrl.fromLocalFile(base_dir + os.sep)
        self.web_view.setHtml(html_content, base_url)

    def _on_text_edited(self):
        """Disparado a cada alteração no editor de texto bruto."""
        self.has_unsaved_changes = True
        self.lbl_status.setText("Digitando...")
        self.save_timer.start(400)

    def _persist_to_disk(self):
        """Grava o conteúdo em disco em UTF-8 e atualiza o status."""
        if self.save_timer.isActive():
            self.save_timer.stop()

        content = self.editor.toPlainText()
        try:
            Path(self.file_path).write_text(content, encoding="utf-8")
            self.current_content = content
            self.has_unsaved_changes = False

            if self.stack.currentIndex() == 1:
                self.lbl_status.setText("Salvo automaticamente")
            else:
                self.lbl_status.setText("Modo: Leitura")
        except Exception as e:
            self.lbl_status.setText(f"Erro ao salvar: {e}")

    def toggle_mode(self):
        """Alterna entre modo Leitura e modo Edição."""
        if self.stack.currentIndex() == 0:
            # Alternar para modo Edição
            self.stack.setCurrentIndex(1)
            self.btn_toggle.setText("Voltar para Leitura (Ctrl+E)")
            self.lbl_status.setText("Modo: Edição")
            self.editor.setFocus()
        else:
            # Alternar para modo Leitura
            if self.has_unsaved_changes:
                self._persist_to_disk()
            else:
                self.current_content = self.editor.toPlainText()

            self._load_rendered_view()
            self.stack.setCurrentIndex(0)
            self.btn_toggle.setText("Alternar para Edição (Ctrl+E)")
            self.lbl_status.setText("Modo: Leitura")

        # Se a barra de busca estiver aberta, re-sincroniza o destaque no modo atual
        if self.search_bar.isVisible() and self.search_input.text():
            self.find_next(backward=False)

    def save_manual(self):
        """Salva imediatamente o arquivo ao pressionar Ctrl+S."""
        self._persist_to_disk()
        self.lbl_status.setText("Arquivo salvo com sucesso!")

    def save_as(self):
        """Salva uma cópia do arquivo atual em outro local (Ctrl+Shift+S)."""
        new_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Como...",
            self.file_path,
            "Documentos Markdown (*.md);;Todos os Arquivos (*.*)",
        )
        if new_path:
            self.file_path = str(Path(new_path).resolve())
            self.setWindowTitle(f"Leitor Markdown Moderno - {os.path.basename(self.file_path)}")
            self._persist_to_disk()
            self._load_rendered_view()  # Atualiza o baseUrl para resolver imagens relativas
            self.lbl_status.setText("Arquivo salvo como novo documento!")

    def export_pdf(self):
        """Exporta o documento renderizado para um arquivo PDF (Ctrl+P)."""
        if self.has_unsaved_changes:
            self._persist_to_disk()
            self._load_rendered_view()

        default_pdf = os.path.splitext(self.file_path)[0] + ".pdf"
        pdf_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Documento para PDF",
            default_pdf,
            "Documento PDF (*.pdf)",
        )
        if pdf_path:
            self.lbl_status.setText("Gerando PDF...")
            page = self.web_view.page()
            if page is not None:
                page.printToPdf(pdf_path)
            else:
                self.lbl_status.setText("Erro: Página WebEngine não disponível.")

    def _on_pdf_printed(self, file_path: str, success: bool):
        """Callback acionado assincronamente ao término da gravação do PDF."""
        if success:
            self.lbl_status.setText(f"PDF exportado: {os.path.basename(file_path)}")
        else:
            self.lbl_status.setText("Erro ao gerar arquivo PDF.")

    def toggle_search_bar(self):
        """Abre ou foca a barra de pesquisa (Ctrl+F)."""
        if not self.search_bar.isVisible():
            self.search_bar.setVisible(True)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def close_search_bar(self):
        """Fecha a barra de pesquisa e limpa o destaque de busca."""
        self.search_bar.setVisible(False)
        self.search_input.clear()
        self.web_view.findText("")
        if self.stack.currentIndex() == 0:
            self.web_view.setFocus()
        else:
            self.editor.setFocus()

    def _on_search_text_changed(self, text: str):
        """Executa a busca em tempo real conforme o usuário digita."""
        if not text:
            self.web_view.findText("")
        else:
            self.find_next(backward=False)

    def find_next(self, backward: bool = False):
        """Navega entre as ocorrências encontradas no modo leitura ou edição."""
        query = self.search_input.text()
        if not query:
            return

        if self.stack.currentIndex() == 0:
            # Busca na engine WebEngine
            flag = QWebEnginePage.FindFlag.FindBackward if backward else QWebEnginePage.FindFlag(0)
            self.web_view.findText(query, flag)
        else:
            # Busca no editor de texto bruto
            flag = QTextDocument.FindFlag.FindBackward if backward else QTextDocument.FindFlag(0)
            found = self.editor.find(query, flag)
            if not found:
                # Se não encontrou, reinicia do topo/fim para loop contínuo
                cursor = self.editor.textCursor()
                if backward:
                    cursor.movePosition(cursor.MoveOperation.End)
                else:
                    cursor.movePosition(cursor.MoveOperation.Start)
                self.editor.setTextCursor(cursor)
                self.editor.find(query, flag)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        """Garante que alterações pendentes sejam persistidas antes de fechar a janela."""
        if self.has_unsaved_changes:
            self.save_timer.stop()
            self._persist_to_disk()
        if a0 is not None:
            super().closeEvent(a0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    target_arg = sys.argv[1] if len(sys.argv) > 1 else "documento_exemplo.md"
    target_file = str(Path(target_arg).resolve())
    window = ModernMDReader(target_file)
    window.show()
    sys.exit(app.exec())
