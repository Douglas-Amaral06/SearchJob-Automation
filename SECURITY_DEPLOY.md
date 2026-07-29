# Segurança e publicação

## Controles implementados no aplicativo

- SQL SQLite executado com parâmetros, sem concatenar entradas do usuário.
- Senhas armazenadas como `scrypt` + salt aleatório único.
- Sessões com tokens opacos; somente SHA-256 do token fica no banco.
- Tokens com expiração e revogação no logout.
- Bloqueio temporário após tentativas repetidas de login.
- Erros de autenticação genéricos para dificultar enumeração de usuários.
- Magic links aleatórios, temporários, de uso único e armazenados como hash.
- Validação de perfil por código individual de seis dígitos enviado por e-mail.
- Código armazenado somente como PBKDF2-HMAC com salt e segredo externo.
- Código expira em 10 minutos e bloqueia após cinco tentativas incorretas.
- Bloqueio acumulado da conta após tentativas incorretas em códigos diferentes.
- No máximo cinco envios de código por conta a cada hora.
- Intervalo mínimo entre solicitações para reduzir spam e automação por bots.
- Administradores protegidos por TOTP em aplicativo autenticador.
- Segredo TOTP criptografado com uma chave externa ao banco.
- Proteções XSRF e CORS do Streamlit explicitamente habilitadas.
- Credenciais lidas somente de `.env` ou Streamlit Secrets.

## Variáveis obrigatórias

Gere uma chave independente para criptografar o segredo do 2FA:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Adicione o resultado em `backend/.env` localmente ou em **Secrets** no
Streamlit Community Cloud:

```env
APP_ENCRYPTION_KEY=resultado_do_comando
APP_BASE_URL=http://localhost:8501
ADMIN_EMAILS=seu-email-administrativo@example.com
```

Em produção, `APP_BASE_URL` deve usar `https://` e apontar para a URL pública
exata do aplicativo. Nunca reutilize `GEMINI_API_KEY` como chave de
criptografia.

## E-mail para magic links

Configure uma única conta remetente do sistema no provedor de e-mail. Essa
configuração é feita uma vez pelo responsável pelo site; os usuários não
precisam configurar SMTP. Cada usuário receberá o próprio código no endereço
informado no cadastro.

Configure a conta remetente:

```env
SMTP_HOST=smtp.seu-provedor.example
SMTP_PORT=587
SMTP_USER=usuario_smtp
SMTP_PASSWORD=senha_smtp
SMTP_FROM=SearchJob <nao-responda@seu-dominio.example>
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

Use uma senha de aplicativo ou credencial SMTP dedicada. Não use a senha
pessoal da sua conta de e-mail.

Exemplo para uma conta Google com senha de aplicativo:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=sua_senha_de_aplicativo
SMTP_FROM=seu-email@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

Depois de alterar essas variáveis, encerre e inicie o Streamlit novamente.
O botão **Perfil → Validar perfil → Enviar código de validação** enviará um
código diferente para cada solicitação e informará explicitamente se o envio
foi aceito ou se a configuração continua incompleta.

## Ativar o administrador e o 2FA

1. Inclua o e-mail administrativo em `ADMIN_EMAILS`.
2. Crie a conta usando exatamente esse endereço.
3. Solicite um link mágico e entre pelo link recebido.
4. O endereço será verificado e o perfil será promovido para `admin`.
5. Abra a aba **Segurança**.
6. Adicione o segredo no aplicativo autenticador e confirme o código.
7. Nos próximos logins administrativos, senha e TOTP serão obrigatórios.

## Cloudflare

Cloudflare depende de um domínio controlado por você e não pode ser ativado
somente por uma alteração de código.

Para uma hospedagem com domínio próprio:

1. Adicione o domínio à sua conta Cloudflare.
2. Aponte o registro DNS para a hospedagem que serve o aplicativo.
3. Mantenha o proxy laranja ativado.
4. Em **SSL/TLS**, selecione `Full (strict)` e habilite `Always Use HTTPS`.
5. Ative as regras gerenciadas do WAF.
6. Crie rate limiting para o caminho do aplicativo, especialmente acessos de
   login e links mágicos.
7. Bloqueie métodos HTTP desnecessários e países somente quando isso fizer
   sentido para seu público.
8. Para um painel administrativo separado, proteja a rota com Cloudflare
   Access além do TOTP da aplicação.

No Streamlit Community Cloud, a URL padrão pertence a `streamlit.app`.
Cloudflare só poderá ficar na frente do aplicativo quando houver uma
arquitetura de domínio/origem compatível. Não altere DNS antes de definir essa
origem, pois isso pode interromper WebSockets do Streamlit.

Se Cloudflare Turnstile for adicionado futuramente ao frontend React/FastAPI,
o token deve obrigatoriamente ser validado no backend pelo endpoint
`/siteverify`; validar apenas no navegador não oferece proteção.

## Observação sobre SQLite

SQLite é adequado para desenvolvimento e MVP de uma única instância. No
Streamlit Community Cloud, dados locais podem desaparecer em reinicializações
e múltiplas instâncias não compartilham sessões. Para produção com usuários
reais, migre usuários, sessões, currículos e candidaturas para PostgreSQL
gerenciado.
