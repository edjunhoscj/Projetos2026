#!/usr/bin/env bash
set -e

PROJETO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${PROJETO_DIR}/logs"
mkdir -p "$LOG_DIR"

DATA_HUMANA=$(TZ="America/Sao_Paulo" date "+%a %d %b %Y %H:%M:%S %Z")
DATA_LOG=$(TZ="America/Sao_Paulo" date "+%Y-%m-%d_%H-%M-%S")
LOG_FILE="${LOG_DIR}/deploy_${DATA_LOG}.log"

echo "========================================"
echo "   DEPLOY LOTOFÁCIL - ${DATA_HUMANA}"
echo "   Projeto: ${PROJETO_DIR}"
echo "   Log: ${LOG_FILE}"
echo "========================================"
echo

cd "$PROJETO_DIR"

# -----------------------------------------
# 1) Ativar ambiente virtual
# -----------------------------------------
echo "🔹 Ativando ambiente virtual (lotofacil-312)..."

if [ -f "${PROJETO_DIR}/lotofacil-312/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "${PROJETO_DIR}/lotofacil-312/bin/activate"
else
  echo "❌ Ambiente virtual lotofacil-312 não encontrado."
  echo "Crie com:  python -m venv lotofacil-312"
  exit 1
fi

echo "✅ Ambiente virtual ativado."
echo "Versão do Python:"
python --version
echo

# -----------------------------------------
# 2) Atualizar base (API Caixa)
# -----------------------------------------
echo "📥 Atualizando base de concursos a partir da API da Caixa..."
python scripts/atualizar_base.py 2>&1 | tee -a "$LOG_FILE"
echo

# -----------------------------------------
# 3) Gerar base limpa
# -----------------------------------------
echo "🧹 Gerando base limpa (base/base_limpa.xlsx)..."
python scripts/gerar_base_limpa.py 2>&1 | tee -a "$LOG_FILE"
echo

# -----------------------------------------
# 4) Gerar combinações
# -----------------------------------------
echo "🎲 Gerando combinacoes/combinacoes.csv..."
python scripts/gerar_combinacoes.py 2>&1 | tee -a "$LOG_FILE"
echo

# -----------------------------------------
# 5) Status do Git + commit opcional
# -----------------------------------------
echo "========================================"
echo "📊 Status do Git após gerar tudo:"
git status
echo "========================================"
echo

read -r -p "💾 Deseja fazer commit e push dessas alterações? [s/N] " RESP

if [[ "$RESP" == "s" || "$RESP" == "S" ]]; then
  read -r -p "✏️  Mensagem do commit: " MSG
  if [ -z "$MSG" ]; then
    MSG="Atualização via deploy.sh"
  fi

  git add base/base_limpa.xlsx outputs/ scripts/ logs/ || true

  git commit -m "$MSG" || {
    echo "⚠ Nada para commitar (talvez nenhuma mudança real)."
  }

  git push origin main || {
    echo "⚠ Falha ao fazer push. Verifique as credenciais."
  }
else
  echo "ℹ Commit/push não realizados (opção do usuário)."
fi

echo
echo "✅ Deploy finalizado."
