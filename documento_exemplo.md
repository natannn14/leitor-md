# Bem-vindo ao Leitor Markdown Moderno 🚀

Este é um documento de demonstração pronto para validar todas as capacidades do leitor e editor desktop para Windows.

---

## 📋 Lista de Tarefas (GFM Tasklists)

- [x] Renderização de títulos e formatação básica
- [x] Tabelas estilizadas compatíveis com GitHub Flavored Markdown
- [x] Syntax highlighting com Pygments
- [ ] Edição em tempo real com atalho `Ctrl+E`
- [ ] Salvamento automático com debounce de 400ms

---

## 📊 Tabelas GFM (Geradas comumente por IA)

| Recurso | Status | Descrição Técnica |
| :--- | :---: | :--- |
| **QWebEngineView** | Ativo | Renderização rica baseada no Chromium |
| **Pygments** | Ativo | Realce sintático de dezenas de linguagens |
| **Debounce I/O** | Ativo | QTimer de 400ms para evitar gargalo de disco |
| **Suporte Windows** | Ativo | Associação via "Abrir com..." e duplo clique |

---

## 💻 Blocos de Código com Syntax Highlighting

### Python
```python
def saudacao(nome: str) -> str:
    """Retorna uma mensagem de boas-vindas formatada."""
    mensagem = f"Olá, {nome}! Seu leitor Markdown está funcionando perfeitamente."
    print(mensagem)
    return mensagem

if __name__ == "__main__":
    saudacao("Usuário")
```

### JavaScript / TypeScript
```javascript
async function fetchMarkdownData(url) {
    try {
        const response = await fetch(url);
        const data = await response.text();
        console.log("Conteúdo carregado com sucesso:", data.length, "caracteres");
        return data;
    } catch (error) {
        console.error("Falha na requisição:", error);
    }
}
```

### Linguagem Genérica / Desconhecida
```customlang
CONFIG_SERVER_PORT = 8080
ENABLE_FEATURE_FLAG = true
RUN_MODE = "production"
```

---

## 💬 Citações e Notas (Blockquotes)

> **Dica Importante:**
> Você pode alternar a qualquer momento para o modo de edição pressionando o atalho **`Ctrl+E`** ou clicando no botão superior. Suas alterações são salvas automaticamente assim que você para de digitar.

---

## 🔤 Formatação de Texto & Quebras de Linha

Texto em **negrito**, texto em *itálico*, texto com ~~tachado~~ e `código inline`.
Quebra de linha configurada diretamente pelo Markdown-It.

---
*Leitor Markdown Moderno — Feito para o Windows 10/11.*
