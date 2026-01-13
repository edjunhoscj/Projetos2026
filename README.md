🧙‍♂️ WIZARD LOTOFÁCIL — Inteligência Estatística + Automação

Projeto completo para análise, atualização e geração de jogos da Lotofácil, combinando:

✔ Rede neural (opcional)
✔ Filtros estatísticos
✔ Score probabilístico
✔ Cobertura inteligente de dezenas
✔ Geração automática diária via GitHub Actions
✔ Comparação com últimos concursos
✔ Dois modos de estratégia: agressivo e conservador

📌 INFORMAÇÕES GERAIS

Linguagem: Python 3.12
Ambiente recomendado: MacOS, Windows ou Linux
Atualização automática: GitHub Actions
Dados em tempo real: API da Caixa (não oficial)

📦 PRINCIPAIS PACOTES UTILIZADOS

pandas

numpy

requests

openpyxl

itertools

argparse

🧠 FUNCIONALIDADES DO PROJETO
🔹 1. Atualização automática da base

O script:

scripts/atualizar_base.py


🔸 Baixa os concursos via API
🔸 Salva em base/base_limpa.xlsx
🔸 Gera coluna Ciclo
🔸 Atualiza o GitHub automaticamente (GitHub Actions)

🔹 2. Geração de todas as combinações possíveis

O script:

scripts/gerar_combinacoes.py


Cria o arquivo:

combinacoes/combinacoes.csv


Com todas as 3.268.760 combinações de 15 dezenas.

⚠️ Este arquivo não vai para o GitHub (é muito grande).
Você gera localmente com:

python scripts/gerar_combinacoes.py

🔹 3. Geração de jogos Inteligentes — Wizard CLI

Arquivo:

wizard_cli.py


O Wizard:

Lê combinações em chunks (50.000 por vez)

Analisa repetição com últimos concursos

Controla sequência máxima

Pontua cobertura das dezenas

Entrega apenas jogos selecionados

Dois modos disponíveis:

Modo	Característica	Ideia
Conservador	evita repetição com últimos concursos	"Jogue seguro"
Agressivo	aceita mais sobreposição	"Jogue como o mercado aposta"
🎯 COMO UTILIZAR LOCALMENTE
▶️ 1. Instalar o interpretador Python

Baixe Python 3.12:

https://www.python.org/downloads/

▶️ 2. Criar ambiente virtual

No terminal:

python3 -m venv lotofacil-312


Ativar ambiente:

MacOS:

source lotofacil-312/bin/activate


Windows:

.\lotofacil-312\Scripts\Activate.ps1

▶️ 3. Instalar dependências

No diretório raiz do projeto:

pip install -r requirements.txt

▶️ 4. Atualizar base da Caixa
python scripts/atualizar_base.py


Resultado salvo em:

base/base_limpa.xlsx

▶️ 5. Gerar combinações
python scripts/gerar_combinacoes.py


Isto cria:

combinacoes/combinacoes.csv

▶️ 6. Rodar o Wizard manualmente

Modo conservador:

python wizard_cli.py --modo conservador --ultimos 20 --finais 5


Modo agressivo:

python wizard_cli.py --modo agressivo --ultimos 20 --finais 5

🤖 EXECUÇÃO AUTOMÁTICA (GITHUB ACTIONS)

O projeto possui automação:

📄 Arquivo:

.github/workflows/wizard.yml


A automação faz:

Baixa o repositório

Instala Python

Instala dependências

Atualiza base da Caixa

Gera base limpa

Gera combinações (se quiser habilitar)

Roda Wizard nos dois modos

Salva arquivos em /outputs/

Faz commit automático

🎯 Agendamento

Você pediu para rodar:

🕔 17h
📅 Segunda a sexta-feira
🕒 Horário de Brasília (UTC-3)

O cron configurado é:

- cron: "0 20 * * 1-5"

📂 ESTRUTURA DO PROJETO
lotofacil/
│
├── base/
│   ├── base_limpa.xlsx
│
├── combinacoes/
│   ├── combinacoes.csv   (ignorado pelo GitHub)
│
├── outputs/
│   ├── jogos_agressivo_2026-01-13_13-59-04.txt
│   ├── jogos_conservador_2026-01-13_13-59-04.txt
│
├── scripts/
│   ├── atualizar_base.py
│   ├── gerar_base_limpa.py
│   ├── gerar_combinacoes.py
│   ├── backtest.py
│
├── modelo/
│   ├── modelo.py
│
├── wizard_cli.py
├── jogar.py
├── requirements.txt
├── README.md

📌 COMO VER RESULTADOS NO GITHUB

Os jogos gerados ficam em:

outputs/


Via GitHub:

➡ Entre em Code
➡ Abra a pasta outputs/
➡ Baixe o arquivo .txt

🙋‍♂️ DÚVIDAS, BUGS E MELHORIAS

Use Issues no GitHub para:

Relatar problemas

Sugerir melhorias

Pedir novos filtros estatísticos

🤝 CONTRIBUIÇÃO

Faça fork do repositório

Crie um branch de trabalho:

git checkout -b feature-nova


Faça suas alterações

Envie para seu repositório:

git push origin feature-nova


Abra um Pull Request

📜 AVISO IMPORTANTE

Este projeto é educacional.
Nenhum algoritmo garante resultados em jogos de azar.
Use com moderação e responsabilidade. 🍀
