from __future__ import annotations

from pathlib import Path
from datetime import datetime
import shutil

import pandas as pd


OUT_DIR = Path("outputs")
DOCS_DIR = Path("docs")


def pegar_mais_recente(padrao: str) -> Path | None:
    arquivos = sorted(OUT_DIR.glob(padrao))
    return arquivos[-1] if arquivos else None


def tabela_html(df: pd.DataFrame, titulo: str, max_linhas: int = 10) -> str:
    if df.empty:
        return f"<h3>{titulo}</h3><p><em>Sem dados disponíveis.</em></p>"

    df2 = df.head(max_linhas).copy()
    html_table = df2.to_html(
        index=False,
        border=0,
        classes="tabela",
        justify="center",
    )
    return f"<h3>{titulo}</h3>\n{html_table}"


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # Arquivos principais
    bt_ag_csv = pegar_mais_recente("backtest_agressivo_*.csv")
    bt_co_csv = pegar_mais_recente("backtest_conservador_*.csv")
    resumo_csv = OUT_DIR / "dashboard_resumo_geral.csv"
    dist_csv = OUT_DIR / "dashboard_distribuicao_acertos.csv"

    # PNGs de gráficos
    pngs = [
        OUT_DIR / "dashboard_desempenho_e_mm.png",
        OUT_DIR / "dashboard_distribuicao_acertos.png",
    ]

    # Copia PNGs para /docs
    for src in pngs:
        if src.exists():
            shutil.copy2(src, DOCS_DIR / src.name)

    # Lê CSVs se existirem
    sec_backtest_ag = ""
    sec_backtest_co = ""
    sec_resumo = ""
    sec_dist = ""

    if bt_ag_csv and bt_ag_csv.exists():
        df_ag = pd.read_csv(bt_ag_csv)
        sec_backtest_ag = tabela_html(df_ag, "Backtest – Modo Agressivo (Top 10)")

    if bt_co_csv and bt_co_csv.exists():
        df_co = pd.read_csv(bt_co_csv)
        sec_backtest_co = tabela_html(df_co, "Backtest – Modo Conservador (Top 10)")

    if resumo_csv.exists():
        df_res = pd.read_csv(resumo_csv)
        sec_resumo = tabela_html(df_res, "Resumo Geral dos Jogos (Agressivo + Conservador)")

    if dist_csv.exists():
        df_dist = pd.read_csv(dist_csv)
        sec_dist = tabela_html(df_dist, "Distribuição de Acertos por Jogo")

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Wizard Lotofácil – Dashboard Diário</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      max-width: 1100px;
      margin: 0 auto;
      padding: 20px 10px 40px;
      background: #0f172a;
      color: #e5e7eb;
    }}
    h1, h2, h3 {{
      text-align: center;
    }}
    h1 {{
      margin-bottom: 0;
    }}
    h2 {{
      margin-top: 40px;
    }}
    .subtitulo {{
      text-align: center;
      margin-bottom: 30px;
      color: #9ca3af;
      font-size: 0.95rem;
    }}
    .tabela {{
      border-collapse: collapse;
      width: 100%;
      margin-bottom: 24px;
      background: #020617;
    }}
    .tabela th, .tabela td {{
      border: 1px solid #1f2937;
      padding: 6px 8px;
      font-size: 0.78rem;
      text-align: center;
    }}
    .tabela th {{
      background: #111827;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 18px;
      margin-top: 10px;
      margin-bottom: 30px;
    }}
    .card {{
      background: #020617;
      border-radius: 10px;
      padding: 14px 16px 18px;
      border: 1px solid #1e293b;
      box-shadow: 0 14px 30px rgba(15,23,42,0.8);
    }}
    img {{
      max-width: 100%;
      border-radius: 8px;
      border: 1px solid #1f2937;
    }}
    footer {{
      margin-top: 40px;
      text-align: center;
      font-size: 0.75rem;
      color: #6b7280;
    }}
    .pill {{
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      font-size: 0.7rem;
      border: 1px solid #374151;
      margin: 0 4px;
    }}
  </style>
</head>
<body>
  <h1>Wizard Lotofácil – Painel Diário</h1>
  <p class="subtitulo">
    Jogos gerados automaticamente (modo <strong>agressivo</strong> e <strong>conservador</strong>) + backtests e estatísticas.<br>
    Atualizado em: <strong>{agora}</strong>
  </p>

  <div class="grid">
    <div class="card">
      <h2>Gráfico – Desempenho & Média Móvel</h2>
      <p class="pill">Histórico dos backtests</p>
      <img src="dashboard_desempenho_e_mm.png" alt="Desempenho e média móvel">
    </div>
    <div class="card">
      <h2>Gráfico – Distribuição de Acertos</h2>
      <p class="pill">Frequência de 11, 12, 13, 14, 15 pts</p>
      <img src="dashboard_distribuicao_acertos.png" alt="Distribuição de acertos">
    </div>
  </div>

  <div class="card">
    {sec_resumo}
  </div>

  <div class="card">
    {sec_backtest_ag}
  </div>

  <div class="card">
    {sec_backtest_co}
  </div>

  <div class="card">
    {sec_dist}
  </div>

  <footer>
    Wizard Lotofácil – gerado automaticamente pelo GitHub Actions.
  </footer>
</body>
</html>
"""
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print("✅ Site estático gerado em docs/index.html")


if __name__ == "__main__":
    main()