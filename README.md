<div align="center">

# 📝 Postix

**Notas post-it flutuantes para o desktop Linux**

Simples, leve, sempre visível — com alarmes, cores, markdown e suporte a imagens.

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-blue.svg)](https://github.com/arthur-alves/postix/releases)
[![Python](https://img.shields.io/badge/python-3.6%2B-green.svg)](https://python.org)
[![Release](https://img.shields.io/github/v/release/arthur-alves/postix)](https://github.com/arthur-alves/postix/releases/latest)

---

### ⬇️ [Download do instalador .deb (Ubuntu / Debian)](https://github.com/arthur-alves/postix/releases/latest)

</div>

---

## ✨ Funcionalidades

| Recurso | Descrição |
|---|---|
| 🎨 **6 cores** | Amarelo, Rosa, Azul, Verde, Laranja, Lilás — estilo post-it real |
| 📌 **Sempre visível** | Flutua sobre todas as janelas |
| 🖱️ **Arrastar e redimensionar** | Mova pelo cabeçalho, redimensione por qualquer borda ou canto |
| 📝 **Markdown** | Escreva em markdown e visualize renderizado (negrito, listas, tabelas, código) |
| 🖼️ **Imagens** | Arraste arquivos de imagem ou cole com `Ctrl+V` direto na nota |
| 🔔 **Alarmes** | Por nota: uma vez, todo dia ou intervalo (ex: a cada 2h) |
| 🔊 **Som personalizado** | Escolha seu próprio som de alarme (MP3, WAV, OGG · máx. 15 MB) |
| 💾 **Auto-save** | Salvo automaticamente enquanto você digita |
| 🗄️ **100% local** | SQLite em `~/.local/share/postix/notes.db` — sem nuvem, sem conta |

---

## 📦 Instalação

### Opção 1 — Instalar o .deb (recomendado)

**Passo 1:** Baixe o arquivo `.deb` da [página de releases](https://github.com/arthur-alves/postix/releases/latest)

**Passo 2:** Instale

**Se a sua distro suporta clique duplo** (Ubuntu, Linux Mint, etc.):
> Clique duas vezes no arquivo `.deb` → o gerenciador de pacotes abrirá automaticamente

**Ou pelo terminal:**
```bash
# Instalar
sudo dpkg -i postix_1.0.0_all.deb

# Se faltar alguma dependência, rode em seguida:
sudo apt install -f
```

**Passo 3:** Abra o Postix
```bash
postix
# ou procure "Postix" no menu de aplicativos
```

---

### Opção 2 — Executar sem instalar (qualquer Linux)

```bash
# 1. Instalar dependências
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-notify-0.7 \
                 libnotify-bin python3-markdown

# Opcional (preview markdown):
sudo apt install gir1.2-webkit2-4.1
# ou em distros mais antigas:
sudo apt install gir1.2-webkit2-4.0

# 2. Clonar o repositório
git clone https://github.com/arthur-alves/postix.git
cd postix

# 3. Executar
python3 postix/main.py
```

---

### Opção 3 — Instalar pelo Makefile

```bash
git clone https://github.com/arthur-alves/postix.git
cd postix

# Instalar dependências
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-notify-0.7 \
                 libnotify-bin python3-markdown

# Instalar no sistema
sudo make install

# Para desinstalar:
sudo make uninstall
```

---

## 🔨 Compilar o .deb em qualquer Linux

> Funciona em qualquer distro baseada em Debian/Ubuntu. Não requer linguagem compilada — o `.deb` empacota o Python diretamente.

```bash
# 1. Clonar
git clone https://github.com/arthur-alves/postix.git
cd postix

# 2. Instalar dependência de build (apenas dpkg-deb, já incluso no Debian/Ubuntu)
# Se não tiver:
sudo apt install dpkg

# 3. Gerar o .deb
python3 build_deb.py

# O pacote será gerado em:
#   dist/postix_1.0.0_all.deb
```

**Instalar o pacote gerado:**
```bash
sudo dpkg -i dist/postix_1.0.0_all.deb
```

---

## 📋 Dependências

| Pacote | Obrigatório | Descrição |
|---|---|---|
| `python3` (≥ 3.6) | ✅ | Runtime |
| `python3-gi` | ✅ | Bindings GTK3 para Python |
| `gir1.2-gtk-3.0` | ✅ | Interface gráfica GTK3 |
| `gir1.2-notify-0.7` | ✅ | Notificações de alarme |
| `libnotify-bin` | ✅ | Daemon de notificação |
| `python3-markdown` | ✅ | Renderização markdown |
| `gir1.2-webkit2-4.1` | ⭐ Recomendado | Preview markdown visual |
| `gir1.2-appindicator3-0.1` | ⭐ Recomendado | Ícone na bandeja (Ubuntu) |
| `gstreamer1.0-plugins-good` | ⭐ Recomendado | Áudio MP3 no alarme |

---

## 🖥️ Como usar

### Controles da nota

```
┌─────────────────────────────────────────────┐
│ ✎ Post-it  [+][🎨][👁][🔔] [💾][🗑][⏻]    │  ← cabeçalho (arraste aqui)
├─────────────────────────────────────────────┤
│                                             │
│  Escreva aqui... ou use **markdown**        │
│                                             │
│  - Listas                                   │
│  - **Negrito**, _itálico_                   │
│                                             │
└─────────────────────────────────────────────┘
                                         ↖ arraste os cantos para redimensionar
```

| Botão | Ação |
|---|---|
| `+` | Nova nota |
| `🎨` | Trocar cor (6 opções) |
| `👁` / `✏` | Alternar edição / preview markdown |
| `🔔` / `🔕` | Configurar alarme |
| `💾` | Salvar manualmente |
| `🗑` | Deletar nota (pede confirmação) |
| `⏻` | Fechar o aplicativo |

### Markdown suportado

```markdown
# Título
**negrito** e _itálico_

- Item de lista
- Outro item

| Coluna 1 | Coluna 2 |
|----------|----------|
| dado     | dado     |

`código inline`

```bloco de código```
```

### Imagens na nota

- **Arrastar:** arraste um arquivo `.png`, `.jpg`, `.gif`, `.webp` etc. para dentro da nota
- **Colar:** copie uma imagem de qualquer lugar e use `Ctrl+V` na nota

As imagens aparecem renderizadas no modo preview (`👁`).

### Alarmes

Clique em `🔕` para configurar:

- **Uma vez** → data + hora específicas
- **Todo dia** → dispara todo dia no horário definido (ex: `14:00`)
- **Intervalo** → a cada N horas/minutos (ex: a cada `2h 30min`)

Cada alarme pode ter seu próprio som (MP3, WAV ou OGG, máx. 15 MB). Use `▶` para ouvir a prévia antes de salvar.

---

## 📁 Estrutura de dados

```
~/.local/share/postix/
├── notes.db          ← banco SQLite (notas + alarmes)
└── images/
    └── {id}/         ← imagens de cada nota
```

---

## 🐛 Problemas conhecidos / FAQ

**O ícone da bandeja não aparece**
> Instale: `sudo apt install gir1.2-appindicator3-0.1`

**O preview markdown não aparece**
> Instale: `sudo apt install gir1.2-webkit2-4.1`

**Som do alarme não toca**
> Instale: `sudo apt install gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly`

**Como faço backup das notas?**
> Copie `~/.local/share/postix/notes.db`

---

## 🤝 Contribuindo

Pull requests são bem-vindos!

```bash
git clone https://github.com/arthur-alves/postix.git
cd postix
python3 postix/main.py   # testar localmente
```

---

## 📄 Licença

[MIT](LICENSE) © 2026 Arthur Alves &lt;arthur.4lvevs@gmail.com&gt;
