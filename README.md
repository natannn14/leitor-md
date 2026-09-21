# Leitor Markdown Moderno 📄✨

Um leitor e editor desktop para arquivos Markdown (`.md`) no Windows 10/11, desenvolvido com Python, PyQt6 e PyQt6-WebEngine. Projetado com foco em produtividade, leitura limpa estilo GitHub e suporte a documentos gerados por IAs (ChatGPT, Claude, Gemini e DeepSeek).

---

## 📥 Download (Pronto para Uso — Sem precisar de Python)

Para usar o programa no seu computador, vá até a aba de **[Releases](https://github.com/natannn14/leitor-md/releases)** aqui no GitHub e escolha a opção que preferir:

| Opção | Arquivo | Descrição |
| :--- | :--- | :--- |
| **Instalador Oficial** | `LeitorMD_Setup.exe` | **Recomendado (Abertura instantânea em 1–2s).** Instalação com assistente (Avançar/Concluir). Abre imediatamente com Splash Screen dinâmico, cria atalhos e associa `.md`. |
| **Executável Portátil Único** | `LeitorMD-portable.exe` | **1 arquivo só.** Não precisa instalar nem descompactar. Basta baixar e dar duplo clique direto para rodar (ideal para pen drive). |
| **Versão Portátil (.zip)** | `LeitorMD-portable.zip` | Contém o arquivo executável único `LeitorMD.exe` limpo (sem pastas com dezenas de DLLs) e o arquivo de exemplo. |

> [!NOTE]
> **Diferença de Inicialização:**
> - O **Instalador Oficial** já mantém o Chromium pré-extraído, abrindo em **1–2 segundos** com um Splash Screen profissional.
> - A **Versão Portátil (arquivo único)** precisa descompactar o runtime na pasta temporária do Windows a cada inicialização, levando cerca de **10–15 segundos** antes de exibir o aplicativo.

---

## 📌 Funcionalidades Principais

- **Diagramas com Mermaid:** Renderização nativa de diagramas de fluxo, gráficos de sequência, classes e estados (` ```mermaid `) via Mermaid.js em ambos os temas (Claro e Escuro).
- **Exportar para HTML Standalone (`Ctrl+Shift+E`):** Salva o documento como arquivo `.html` autossuficiente com CSS e scripts embutidos para visualização ou compartilhamento independente.
- **Impressão Direta (`Ctrl+Shift+P`):** Atalho direto para a caixa de diálogo nativa de impressão do sistema integrado ao WebEngine e ao editor.
- **Estatísticas Completas em Tempo Real:** Rodapé com contagem de Linhas, Palavras, Caracteres, estimativa de tempo de leitura e horário da última modificação (`Modificado: HH:MM`).
- **Sumário Lateral / TOC (`Ctrl+Shift+L`):** Painel lateral retrátil (`QSplitter`) com árvore hierárquica dos cabeçalhos H1 a H3 e rolagem suave com um clique até a seção correspondente.
- **Botão "Copiar" nos Blocos de Código:** Botão discreto no canto superior direito dos blocos de código com feedback visual ("Copiado!") e cópia instantânea para a área de transferência.
- **Modo Foco (`Ctrl+Shift+F`) & Tela Cheia (`F11`):** Leitura sem distrações ocultando todas as barras de ferramentas e abas (saída rápida a qualquer momento com a tecla `Esc`).
- **Recarregar do Disco (`F5`):** Recarrega o conteúdo do arquivo ativo diretamente do disco com aviso preventivo se houver alterações não salvas.
- **Abrir Pasta no Windows Explorer (`Ctrl+Enter`):** Acesso rápido à pasta que contém o documento ativo com um único atalho.
- **Tema Claro e Escuro Dinâmico (`Ctrl+D`):** Alternância instantânea com paleta moderna inspirada no GitHub Dark (`#0d1117`, `#161b22`, `#c9d1d9`), syntax highlighting adaptativo com Pygments (Monokai no modo escuro e Default no claro) em todas as abas simultaneamente.
- **Tela Inicial & Arquivos Recentes:** Ao abrir sem documentos, exibe tela inicial com acesso rápido aos últimos 10 arquivos abertos, botão de novo documento e atalhos rápidos.
- **Abertura Rápida de Arquivos (`Ctrl+O`):** Diálogo nativo do sistema com suporte a múltiplos arquivos e memória da última pasta acessada.
- **Configurações e Sessão Persistentes:** Salva e restaura automaticamente a geometria da janela, tema ativo, lista de abas abertas, zoom por arquivo, último diretório de salvamento (`last_save_directory`) e histórico via `QSettings`.
- **Múltiplas Abas Independentes (`Ctrl+T` / `Ctrl+W`):** Abra e edite vários arquivos Markdown simultaneamente com abas fecháveis, ordenáveis e restauração automática da sessão ao reabrir o app.
- **Drag & Drop Inteligente:** Arraste arquivos `.md`, `.markdown` ou `.txt` do Windows Explorer diretamente para a janela (soltar na barra de abas cria nova aba; no corpo carrega no documento ativo).
- **Zoom Dinâmico Proporcional (`Ctrl++` / `Ctrl+-` / `Ctrl+0`):** Ajuste de zoom de 50% a 300% com persistência individual por documento (salvo via `QSettings`).
- **Indicador Visual de Edição Não Salva (`●`):** Destaque visual tanto no título da aba quanto na barra de título da janela enquanto houver alterações pendentes.
- **Visualização Estilo GitHub:** Renderização limpa, tipografia moderna, tabelas GFM, blockquotes e quebras de linha automáticas.
- **Syntax Highlighting Automático:** Destaque de sintaxe para Python, JavaScript, HTML, CSS, SQL, JSON e dezenas de outras linguagens com Pygments, além de fallback seguro para formatos desconhecidos.
- **Listas de Tarefas (Tasklists):** Renderização nativa de caixas de seleção interativas (`- [ ]` e `- [x]`).
- **Alternância Instantânea (Leitura / Edição):** Alternância com um clique ou através do atalho global `Ctrl+E`.
- **Busca em Tempo Real (`Ctrl+F`):** Barra de pesquisa com navegação entre ocorrências (Anterior / Próximo) tanto no modo leitura quanto no modo edição.
- **Exportação para PDF (`Ctrl+P`):** Exportação direta do documento formatado para arquivo PDF com um clique nos dois temas.
- **Salvar Como (`Ctrl+Shift+S`) e Salvar Manual (`Ctrl+S`):** Além do salvamento automático com debounce (400ms).
- **Proteção Contra Perda de Dados (`closeEvent`):** Salvamento instantâneo de todas as abas abertas caso a janela seja fechada subitamente durante a digitação.
- **Splash Screen Profissional Adaptativo:** Inicialização suave com card flutuante adaptado ao tema salvo (Dark Card ou Light Card) e feedback dinâmico de progresso.
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
| **`Ctrl + O`** | Abre o diálogo para selecionar e abrir arquivos Markdown existentes. |
| **`Ctrl + D`** | Alterna instantaneamente entre o Tema Claro e o Tema Escuro. |
| **`Ctrl + Shift + L`** | Alterna a exibição do Sumário Lateral (TOC) com árvore de cabeçalhos. |
| **`Ctrl + Shift + F`** | Ativa/desativa o Modo Foco (oculta barras de ferramentas e abas para leitura limpa). |
| **`F11`** | Alterna o Modo Tela Cheia. |
| **`F5`** | Recarrega o arquivo atual diretamente do disco (com confirmação se modificado). |
| **`Ctrl + Enter`** | Abre a pasta do arquivo atual no Windows Explorer. |
| **`Ctrl + T`** | Abre uma nova aba em branco (`Sem título N.md`). |
| **`Ctrl + W`** | Fecha a aba ativa (com aviso e opção de salvar se houver alterações). |
| **`Ctrl + Tab`** | Alterna para a próxima aba. |
| **`Ctrl + Shift + Tab`** | Alterna para a aba anterior. |
| **`Ctrl + E`** | Alterna entre o modo de Leitura (renderizado) e Edição (texto bruto). |
| **`Ctrl + F`** | Abre/foca a barra de busca no documento em tempo real. |
| **`Ctrl + P`** | Exporta o documento atual diretamente para PDF. |
| **`Ctrl + Shift + P`** | Abre o diálogo de impressão nativo do sistema para imprimir o documento. |
| **`Ctrl + Shift + E`** | Exporta o documento como arquivo HTML Standalone autossuficiente. |
| **`Ctrl + S`** | Força a gravação imediata do documento no disco. |
| **`Ctrl + Shift + S`** | Salva uma cópia do arquivo atual em novo local ("Salvar Como..."). |
| **`Ctrl + +` / `Ctrl + =`** | Aumenta o zoom da visualização e do editor (+10%). |
| **`Ctrl + -`** | Diminui o zoom da visualização e do editor (-10%). |
| **`Ctrl + 0`** | Redefine o zoom para 100%. |
| **`Escape`** | Fecha a busca ou restaura a visualização se estiver em Modo Foco / Tela Cheia. |
| **Duplo clique na aba** | Renomeia o documento via diálogo rápido. |



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
