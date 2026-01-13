#!/usr/bin/env bash
set -euo pipefail

########################################
#  Deploy automatizado LOTOFÁCIL
#  - Ativa venv lotofacil-312
#  - Atualiza base da Caixa
#  - Gera base_limpa
#  - Gera combinacoes.csv
#  - Faz commit + push (opcional, interativo)
#  - Gera log em logs/deploy_YYYY-MM-DD_HH-MM-SS.log
########################################

# Descobrir diretório do projeto (onde está o deploy.sh)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# -----------------------------
# Logs
# -----------------------------
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy_$(date +%Y-%m-%d_%H-%M-%S).log"

# Tudo que for impresso vai também para o arquivo de log
exec > >(tee -a "$LOG_FILE") 2>&1

echo "========================================"
echo "   DEPLOY LOTOFÁCIL - $(date)"
echo "   Projeto: $PROJECT_DIR"
echo "   Log: $LOG_FILE"
echo "========================================"
echo

# -----------------------------
# Ativar ambiente virtual
# -----------------------------
echo "🔹 Ativando ambiente virtual (lotofacil-312)..."

if [ -f "$PROJECT_DIR/lotofacil-312/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "$PROJECT_DIR/lotofacil-312/bin/activate"
    echo "✅ Ambiente virtual ativado."
else
    echo "❌ Não encontrei $PROJECT_DIR/lotofacil-312/bin/activate"
    echo "   Crie o ambiente com:"
    echo "   python3 -m venv lotofacil-312"
    exit 1
fi

echo "Versão do Python:"
python --version
echo

# -----------------------------
# Atualizar base da Caixa
# -----------------------------
if [ -f "$PROJECT_DIR/scripts/atualizar_base.py" ]; then
    echo "📥 Atualizando base de concursos a partir da API da Caixa..."
    python scripts/atualizar_base.py
    echo
else
    echo "⚠️  scripts/atualizar_base.py não encontrado. Pulando esta etapa."
fi

# -----------------------------
# Gerar base limpa
# -----------------------------
if [ -f "$PROJECT_DIR/scripts/gerar_base_limpa.py" ]; then
    echo "🧹 Gerando base limpa (base/base_limpa.xlsx)..."
    python scripts/gerar_base_limpa.py
    echo
else
    echo "⚠️  scripts/gerar_base_limpa.py não encontrado. Pulando esta etapa."
fi

# -----------------------------
# Gerar combinacoes.csv
# -----------------------------
if [ -f "$PROJECT_DIR/scripts/gerar_combinacoes.py" ]; then
    echo "🎲 Gerando combinacoes/combinacoes.csv..."
    python scripts/gerar_combinacoes.py
    echo
else
    echo "⚠️  scripts/gerar_combinacoes.py não encontrado. Pulando esta etapa."
fi

# -----------------------------
# Status do Git
# -----------------------------
echo "========================================"
echo "📊 Status do Git após gerar tudo:"
git status
echo "========================================"
echo

# Ver se há algo para commitar
if git diff --quiet && git diff --cached --quiet; then
    echo "ℹ️  Nenhuma alteração detectada. Nada para commitar."
    echo "✅ Deploy finalizado (sem commit/push)."
    exit 0
fi

# -----------------------------
# Commit + Push (interativo)
# -----------------------------
read -rp "💾 Deseja fazer commit e push dessas alterações? [s/N] " RESP
RESP="${RESP:-N}"

if [[ "$RESP" =~ ^[sS]$ ]]; then
    read -rp "✏️  Mensagem do commit: " MSG
    if [ -z "${MSG// }" ]; then
        MSG="Atualização automática (deploy.sh)"
    fi

    echo "➕ git add ."
    git add .

    echo "✅ git commit -m \"$MSG\""
    git commit -m "$MSG"

    echo "🚀 Enviando para o GitHub (origin main)..."
    git push origin main

    echo "✅ Commit e push concluídos."
else
    echo "⏭  Commit/push pulados a pedido do usuário."
fi

echo
echo "========================================"
echo "✅ Deploy finalizado com sucesso."
echo "📂 Log salvo em: $LOG_FILE"
echo "========================================"
