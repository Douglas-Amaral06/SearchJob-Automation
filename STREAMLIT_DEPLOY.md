# Deploy no Streamlit Community Cloud

O projeto agora possui uma interface Streamlit paralela. Ela reutiliza o
agregador, os conectores, os filtros, a deduplicação e o SQLite existentes.
O FastAPI e o frontend React não foram removidos.

## Executar localmente

No PowerShell, a partir da raiz do projeto:

```powershell
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m streamlit run backend\streamlit_app.py
```

O navegador abrirá normalmente em `http://localhost:8501`.

## Configurar a criação de currículo com Gemini

Use uma chave nova, criada após revogar qualquer chave que tenha sido exposta.
Para desenvolvimento local, adicione em `backend/.env`:

```env
GEMINI_API_KEY=sua_nova_chave
```

No Streamlit Community Cloud, adicione a mesma variável na área **Secrets**:

```toml
GEMINI_API_KEY = "sua_nova_chave"
```

O aplicativo usa o modelo `gemini-2.5-flash`. Nunca envie a chave real para o
Git.

## Publicar

1. Envie o projeto para um repositório GitHub privado ou público.
2. Acesse o Streamlit Community Cloud e escolha **Create app**.
3. Selecione o repositório, branch e o arquivo principal:
   `backend/streamlit_app.py`.
4. Em **Advanced settings**, use Python 3.11 e cole as configurações de
   `.streamlit/secrets.toml.example` na área **Secrets**, preenchendo suas
   credenciais reais.
5. Clique em **Deploy**.

Não faça commit de `.env` nem de `.streamlit/secrets.toml`.

## Fontes de vagas

O agregador suporta Adzuna, Gupy, Jooble, Greenhouse, Jobicy e Remotive.
Jobicy e Remotive usam APIs públicas sem credenciais e retornam vagas remotas
compatíveis com candidatos no Brasil. Ambas ficam habilitadas por padrão.

Para desativá-las ou ajustar o cache no Streamlit Community Cloud:

```toml
JOBICY_ENABLED = "true"
JOBICY_CACHE_TTL_SECONDS = "3600"
REMOTIVE_ENABLED = "true"
REMOTIVE_CACHE_TTL_SECONDS = "21600"
```

Não reduza os tempos de cache: eles respeitam o uso justo das APIs e evitam
bloqueio temporário do aplicativo. Os links de candidatura continuam
direcionando para a página original da fonte.

## Checklist obrigatório antes do GitHub

Execute na raiz:

```powershell
python scripts\pre_publish_check.py
git status --short --ignored
```

O resultado da auditoria deve terminar com `Auditoria aprovada`. Os itens
abaixo devem aparecer como ignorados (`!!`) e nunca como arquivos novos:

- `backend/.env`
- `.streamlit/secrets.toml`
- `data/`
- qualquer arquivo `.db`, `.sqlite`, `.pem` ou `.key`

O repositório usa o hook seguro em `.githooks/pre-commit`. Ative-o uma vez:

```powershell
git config core.hooksPath .githooks
```

No GitHub, ative **Settings → Code security → Push protection**. Não use a
opção de contornar o bloqueio para enviar uma chave real.

## Administrador no Community Cloud

O banco local com a conta administrativa não será enviado ao GitHub. Para
criar a conta no primeiro início do Streamlit, configure somente na área
**Secrets**:

```toml
ADMIN_BOOTSTRAP_LOGIN = "seu-login-administrativo"
ADMIN_BOOTSTRAP_PASSWORD = "uma-senha-nova-e-forte"
```

Não reutilize a senha que já apareceu em conversas, arquivos ou capturas de
tela. O aplicativo cria a conta somente se ela ainda não existir e armazena
apenas `scrypt` + salt.

## Estruturas preservadas

- API FastAPI: `backend/main.py`
- Frontend React: `frontend/`
- Interface Streamlit: `backend/streamlit_app.py`
- Regras de negócio compartilhadas: `backend/app/`

## Limitação do SQLite no Community Cloud

O SQLite continua funcional, porém fica no armazenamento local da instância.
Em um aplicativo público, o histórico é compartilhado entre visitantes e pode
ser perdido após reinicialização ou reconstrução do app. Para contas de usuário
e persistência permanente, a evolução recomendada é um banco externo
gerenciado, mantendo o SQLite para desenvolvimento local.
