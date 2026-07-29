# Política de segurança

Não publique vulnerabilidades, credenciais, dados pessoais ou bancos de dados
em issues públicas.

Use **Security → Advisories → New draft security advisory** no GitHub para
relatar uma vulnerabilidade de forma privada.

Se uma credencial for exposta:

1. revogue ou rotacione a credencial imediatamente;
2. remova-a dos arquivos e do histórico Git;
3. execute `python scripts/pre_publish_check.py`;
4. verifique os alertas de Secret Scanning no GitHub.
