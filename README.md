# Leitor Markdown Moderno 📄✨

Um leitor e editor desktop para arquivos Markdown (`.md`) no Windows 10/11, desenvolvido com Python, PyQt6 e PyQt6-WebEngine. Projetado com foco em produtividade, leitura limpa estilo GitHub e suporte a documentos gerados por IAs (ChatGPT, Claude, Gemini e DeepSeek).

---

## 📥 Download (Pronto para Uso — Sem precisar de Python)

Para usar o programa no seu computador, vá até a aba de **[Releases](https://github.com/natannn14/leitor-md/releases)** aqui no GitHub e escolha a opção que preferir:

| Opção | Arquivo | Descrição |
| :--- | :--- | :--- |
| **Instalador Oficial** | `LeitorMD_Setup.exe` | **Recomendado.** Instalação com assistente (Avançar/Concluir). Cria atalhos no Menu Iniciar, Área de Trabalho e permite associar arquivos `.md` para abrir automaticamente com dois cliques. |
| **Versão Portátil** | `LeitorMD-portable.zip` | **Sem instalação.** Basta baixar o arquivo `.zip`, extrair o conteúdo em qualquer pasta e dar dois cliques direto em `LeitorMD.exe`. Ideal para pen drives ou computadores onde você não tem permissão de administrador. |

---

## 📌 Funcionalidades Principais

- **Visualização Estilo GitHub:** Renderização limpa, tipografia moderna, tabelas GFM, blockquotes e quebras de linha automáticas.
- **Syntax Highlighting Automático:** Destaque de sintaxe para Python, JavaScript, HTML, CSS, SQL, JSON e dezenas de outras linguagens com Pygments, além de fallback seguro para formatos desconhecidos.
- **Listas de Tarefas (Tasklists):** Renderização nativa de caixas de seleção interativas (`- [ ]` e `- [x]`).
- **Alternância Instantânea (Leitura / Edição):** Alternância com um clique ou através do atalho global `Ctrl+E`.
- **Busca em Tempo Real (`Ctrl+F`):** Barra de pesquisa com navegação entre ocorrências (Anterior / Próximo) tanto no modo leitura quanto no modo edição.
- **Exportação para PDF (`Ctrl+P`):** Exportação direta do documento formatado para arquivo PDF com um clique.
- **Salvar Como (`Ctrl+Shift+S`) e Salvar Manual (`Ctrl+S`):** Além do salvamento automático com debounce (400ms).
- **Proteção Contra Perda de Dados (`closeEvent`):** Salvamento instantâneo caso a janela seja fechada subitamente durante a digitação.
- **Ícone Nativo Multi-Resolução:** Ícone profissional incorporado (`app.ico`) em 6 resoluções (16×16 a 256×256).
- **Abertura Ultrarrápida (`--onedir`):** Abre em 1–2 segundos, empacotado em um único instalador com Inno Setup.

---

## 💻 Requisitos do Sistema

- **Desenvolvimento:**
  - Python 3.10 ou superior
  - Windows 10 ou Windows 11 (64 bits)
- **Execução Final (via .exe empacotado ou instalador):**
  - Windows 10/11 (64 bits)
  - Nenhuma dependência externa ou instalação de Python necessária.

---

## ⚙️ Instalação das Dependências (Ambiente de Desenvolvimento)

Execute no prompt de comando (cmd) ou PowerShell:

```bash
pip install PyQt6 PyQt6-WebEngine markdown-it-py pygments linkify-it-py pyinstaller
```

---

## 🚀 Como Executar em Desenvolvimento

Para abrir o documento de exemplo ou criar um arquivo novo caso não exista:

```bash
python md_reader.py
```

Para abrir um arquivo específico:

```bash
python md_reader.py "C:\caminho\para\seu_arquivo.md"
```

---

## ⚡ Build Automático One-Click (`build.bat`)

O projeto inclui o script [`build.bat`](file:///e:/projetos/leitor-markdonw/build.bat) que executa todo o pipeline de ponta a ponta:

1. Valida a sintaxe Python (`py_compile`).
2. Compila o projeto com PyInstaller no modo rápido (`--onedir`).
3. Localiza e executa o Inno Setup Compiler (`ISCC.exe`) gerando o instalador final:
   ```
   setup_output\LeitorMD_Setup.exe
   ```

Basta dar duplo clique em `build.bat` ou rodar no terminal:
```bat
build.bat
```

---

## ⌨️ Atalhos de Teclado

| Atalho | Ação |
| :--- | :--- |
| **`Ctrl + E`** | Alterna entre o modo de Leitura (renderizado) e Edição (texto bruto). |
| **`Ctrl + F`** | Abre/foca a barra de busca no documento em tempo real. |
| **`Ctrl + P`** | Exporta o documento atual diretamente para PDF. |
| **`Ctrl + S`** | Força a gravação imediata do documento no disco. |
| **`Ctrl + Shift + S`** | Salva uma cópia do arquivo atual em novo local ("Salvar Como..."). |
| **`Escape`** | Fecha a barra de pesquisa e limpa os destaques. |

---

## 🛠️ Detalhes da Distribuição com Inno Setup

O instalador [`installer.iss`](file:///e:/projetos/leitor-markdonw/installer.iss) foi projetado para ambientes corporativos:

- **Modo `--onedir`:** Os arquivos são instalados em `{autopf}\LeitorMD\` e o programa abre instantaneamente (sem a lentidão de descompactar o Chromium a cada inicialização).
- **Associação Opcional:** Na tela de instalação, a opção de associar arquivos `.md` vem desmarcada por padrão, evitando conflitos com VS Code, Obsidian ou Typora.
- **Privilégios Adaptáveis (`dialog`):** Funciona sem privilégios de administrador para usuários padrão ou permite instalação para todos os usuários se executado como administrador.
- **Desinstalador Limpo:** Remove completamente atalhos, arquivos e chaves de registro no Painel de Controle do Windows.

---

## 🔍 Solução de Problemas Comuns

### 1. Alerta do Windows Defender / SmartScreen
- **Causa:** O executável é novo e não possui assinatura digital comercial (EV Certificate).
- **Solução:** Clique em **"Mais informações"** → **"Executar assim mesmo"**.

### 2. Antivírus Corporativo
- **Causa:** Heurísticas corporativas podem sinalizar binários de PyInstaller recém-gerados como falso positivo.
- **Solução:** Solicite à equipe de TI a inclusão da pasta `C:\Programas\LeitorMD\` ou do instalador na lista de permissões da empresa.
