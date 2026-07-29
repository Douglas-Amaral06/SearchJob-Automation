"""
Módulo de gerenciamento de banco de dados SQLite.
Não mantém conexões globais - abre/fecha por operação.
"""
import sqlite3
import hashlib
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit
from app.config import DATABASE_PATH, DATABASE_DIR

logger = logging.getLogger(__name__)


def validar_url_candidatura(url: str) -> bool:
    """Valida defensivamente URLs HTTP(S) antes da persistência."""
    if not isinstance(url, str) or not url.strip():
        return False

    try:
        partes = urlsplit(url.strip())
        return (
            partes.scheme.lower() in {"http", "https"}
            and bool(partes.netloc)
            and partes.username is None
            and partes.password is None
        )
    except ValueError:
        return False


def gerar_chave_vaga(fonte: str, id_externo: str | None, url_candidatura: str) -> str:
    """
    Gera chave única para uma vaga baseada em fonte e id_externo ou URL.
    Prioridade:
    1. fonte normalizada + id_externo (se existir)
    2. fonte normalizada + URL normalizada (fallback)
    """
    fonte_norm = fonte.lower().strip()
    
    if id_externo:
        id_norm = str(id_externo).lower().strip()
        chave = f"{fonte_norm}:{id_norm}"
    else:
        url_norm = url_candidatura.lower().strip()
        url_hash = hashlib.sha256(url_norm.encode()).hexdigest()[:16]
        chave = f"{fonte_norm}:{url_hash}"
    
    return chave


def criar_conexao() -> sqlite3.Connection:
    """
    Cria nova conexão com o banco SQLite.
    Cada operação abre sua própria conexão.
    """
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")  # 5 segundos
    return conn


def inicializar_banco() -> None:
    """
    Inicializa o banco de dados criando esquema se necessário.
    Chamada uma vez ao iniciar a aplicação.
    """
    # Criar diretório se não existir
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = criar_conexao()
    try:
        # Ativar WAL mode para melhor concorrência
        conn.execute("PRAGMA journal_mode = WAL")
        
        cursor = conn.cursor()
        
        # Tabela de candidaturas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidaturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave_vaga TEXT NOT NULL UNIQUE,
                fonte TEXT NOT NULL,
                id_externo TEXT NOT NULL,
                titulo TEXT NOT NULL,
                empresa TEXT NOT NULL,
                local TEXT,
                url_candidatura TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidatado',
                candidatado_em TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
        """)
        
        # Índices para performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fonte_id 
            ON candidaturas(fonte, id_externo)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_candidatado_em 
            ON candidaturas(candidatado_em DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status 
            ON candidaturas(status)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                login TEXT COLLATE NOCASE UNIQUE,
                senha_hash TEXT NOT NULL,
                senha_salt TEXT NOT NULL,
                papel TEXT NOT NULL DEFAULT 'usuario',
                email_verificado INTEGER NOT NULL DEFAULT 0,
                totp_segredo_criptografado TEXT,
                totp_habilitado INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
        """)

        # Migração segura para bancos criados antes dos recursos de segurança.
        colunas_usuarios = {
            linha["name"]
            for linha in cursor.execute("PRAGMA table_info(usuarios)").fetchall()
        }
        migracoes_usuarios = {
            "login": "ALTER TABLE usuarios ADD COLUMN login TEXT COLLATE NOCASE",
            "papel": "ALTER TABLE usuarios ADD COLUMN papel TEXT NOT NULL DEFAULT 'usuario'",
            "email_verificado": (
                "ALTER TABLE usuarios ADD COLUMN email_verificado "
                "INTEGER NOT NULL DEFAULT 0"
            ),
            "totp_segredo_criptografado": (
                "ALTER TABLE usuarios ADD COLUMN totp_segredo_criptografado TEXT"
            ),
            "totp_habilitado": (
                "ALTER TABLE usuarios ADD COLUMN totp_habilitado "
                "INTEGER NOT NULL DEFAULT 0"
            ),
        }
        for coluna, comando in migracoes_usuarios.items():
            if coluna not in colunas_usuarios:
                cursor.execute(comando)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS curriculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL UNIQUE,
                dados_json TEXT NOT NULL,
                curriculo_gerado_json TEXT,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_curriculos_usuario
            ON curriculos(usuario_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessoes_usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                criado_em TEXT NOT NULL,
                expira_em TEXT NOT NULL,
                ultimo_uso_em TEXT NOT NULL,
                revogado_em TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessoes_usuario
            ON sessoes_usuario(usuario_id, expira_em)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tentativas_login (
                identidade_hash TEXT PRIMARY KEY,
                falhas INTEGER NOT NULL DEFAULT 0,
                bloqueado_ate TEXT,
                atualizado_em TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS magic_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                finalidade TEXT NOT NULL DEFAULT 'login',
                criado_em TEXT NOT NULL,
                expira_em TEXT NOT NULL,
                usado_em TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_magic_links_usuario
            ON magic_links(usuario_id, expira_em)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS codigos_validacao_email (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                codigo_hash TEXT NOT NULL,
                codigo_salt TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                expira_em TEXT NOT NULL,
                tentativas INTEGER NOT NULL DEFAULT 0,
                usado_em TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_codigos_validacao_usuario
            ON codigos_validacao_email(usuario_id, expira_em)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS limites_validacao_email (
                usuario_id INTEGER PRIMARY KEY,
                falhas_acumuladas INTEGER NOT NULL DEFAULT 0,
                envios_na_janela INTEGER NOT NULL DEFAULT 0,
                janela_iniciada_em TEXT NOT NULL,
                bloqueado_ate TEXT,
                atualizado_em TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_login
            ON usuarios(login)
            WHERE login IS NOT NULL
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS desafios_admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                finalidade TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                expira_em TEXT NOT NULL,
                usado_em TEXT,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_desafios_admin_usuario
            ON desafios_admin(usuario_id, expira_em)
        """)
        
        conn.commit()
        logger.info(f"Banco de dados inicializado em: {DATABASE_PATH}")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco: {e}")
        raise
    finally:
        conn.close()


def obter_chaves_candidatadas(fonte: str | None = None) -> set[str]:
    """
    Obtém todas as chaves de vagas candidatadas.
    Útil para preencher ja_candidatado nas vagas.
    """
    conn = None
    try:
        conn = criar_conexao()
        cursor = conn.cursor()
        
        if fonte:
            cursor.execute(
                "SELECT chave_vaga FROM candidaturas WHERE fonte = ? AND status = 'candidatado'",
                (fonte,)
            )
        else:
            cursor.execute(
                "SELECT chave_vaga FROM candidaturas WHERE status = 'candidatado'"
            )
        
        chaves = {row[0] for row in cursor.fetchall()}
        return chaves
    except Exception as e:
        logger.error(f"Erro ao obter chaves candidatadas: {e}")
        return set()
    finally:
        if conn:
            conn.close()


def salvar_candidatura(
    fonte: str,
    id_externo: str,
    titulo: str,
    empresa: str,
    local: str | None,
    url_candidatura: str,
) -> dict:
    """
    Salva uma candidatura no banco.
    Idempotente: se já existir, atualiza, caso contrário insere.
    """
    conn = None
    try:
        if not validar_url_candidatura(url_candidatura):
            return {"status": "erro", "mensagem": "URL de candidatura inválida"}

        chave_vaga = gerar_chave_vaga(fonte, id_externo, url_candidatura)
        agora_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        conn = criar_conexao()
        cursor = conn.cursor()
        
        # Verificar se já existe
        cursor.execute("SELECT id FROM candidaturas WHERE chave_vaga = ?", (chave_vaga,))
        existe = cursor.fetchone()
        
        if existe:
            # Atualizar
            cursor.execute("""
                UPDATE candidaturas
                SET status = 'candidatado', atualizado_em = ?
                WHERE chave_vaga = ?
            """, (agora_utc, chave_vaga))
            resultado = "atualizado"
        else:
            # Inserir
            cursor.execute("""
                INSERT INTO candidaturas
                (chave_vaga, fonte, id_externo, titulo, empresa, local, url_candidatura, 
                 status, candidatado_em, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chave_vaga, fonte, id_externo, titulo, empresa, local,
                url_candidatura, "candidatado", agora_utc, agora_utc, agora_utc
            ))
            resultado = "criado"
        
        conn.commit()
        
        return {"status": "sucesso", "resultado": resultado}
    except sqlite3.IntegrityError as e:
        logger.error(f"Erro de integridade ao salvar candidatura: {e}")
        return {"status": "erro", "mensagem": "Chave de vaga duplicada"}
    except Exception as e:
        logger.error(f"Erro ao salvar candidatura: {e}")
        return {
            "status": "erro",
            "mensagem": "Não foi possível salvar a candidatura.",
        }
    finally:
        if conn:
            conn.close()


def listar_candidaturas(
    pagina: int = 1,
    limite: int = 20,
    fonte: str | None = None,
    status: str | None = None,
) -> dict:
    """
    Lista candidaturas com paginação.
    """
    conn = None
    try:
        conn = criar_conexao()
        cursor = conn.cursor()
        
        # Montar query
        query = "SELECT * FROM candidaturas WHERE 1=1"
        params = []
        
        if fonte:
            query += " AND fonte = ?"
            params.append(fonte)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        # Contar total
        query_count = query.replace("SELECT *", "SELECT COUNT(*)")
        cursor.execute(query_count, params)
        total = cursor.fetchone()[0]
        
        # Paginação
        offset = (pagina - 1) * limite
        query += " ORDER BY candidatado_em DESC LIMIT ? OFFSET ?"
        params.extend([limite, offset])
        
        cursor.execute(query, params)
        candidaturas = [dict(row) for row in cursor.fetchall()]
        
        return {
            "status": "sucesso",
            "pagina_atual": pagina,
            "total": total,
            "candidaturas": candidaturas,
        }
    except Exception as e:
        logger.error(f"Erro ao listar candidaturas: {e}")
        return {
            "status": "erro",
            "pagina_atual": pagina,
            "total": 0,
            "candidaturas": [],
        }
    finally:
        if conn:
            conn.close()


def remover_candidatura(
    fonte: str,
    id_externo: str | None = None,
    url_candidatura: str | None = None,
) -> dict:
    """
    Remove uma candidatura pelo fonte e id_externo ou URL.
    Usa chave exata - sem LIKE.
    Idempotente: não retorna erro se não existir.
    """
    conn = None
    try:
        if not id_externo and not url_candidatura:
            return {"status": "erro", "mensagem": "id_externo ou url_candidatura obrigatório"}
        
        conn = criar_conexao()
        cursor = conn.cursor()
        
        # Gerar chave exata
        if id_externo:
            chave_vaga = gerar_chave_vaga(fonte, id_externo, url_candidatura or "")
        else:
            # Fallback: usar URL, mas gerar chave normalizada
            chave_vaga = gerar_chave_vaga(fonte, None, url_candidatura or "")
        
        # Verificar se existe
        cursor.execute(
            "SELECT id FROM candidaturas WHERE chave_vaga = ?",
            (chave_vaga,)
        )
        existe = cursor.fetchone() is not None
        
        # Remover se existe
        if existe:
            cursor.execute(
                "DELETE FROM candidaturas WHERE chave_vaga = ?",
                (chave_vaga,)
            )
            conn.commit()
        
        return {"status": "sucesso", "removida": existe}
    
    except Exception as e:
        logger.error(f"Erro ao remover candidatura: {e}")
        return {"status": "erro", "mensagem": "Erro ao remover candidatura", "removida": False}
    
    finally:
        if conn:
            conn.close()


async def salvar_candidatura_async(
    fonte: str,
    id_externo: str,
    titulo: str,
    empresa: str,
    local: str | None,
    url_candidatura: str,
) -> dict:
    """Versão async de salvar_candidatura."""
    return await asyncio.to_thread(
        salvar_candidatura, fonte, id_externo, titulo, empresa, local, url_candidatura
    )


async def listar_candidaturas_async(
    pagina: int = 1,
    limite: int = 20,
    fonte: str | None = None,
    status: str | None = None,
) -> dict:
    """Versão async de listar_candidaturas."""
    return await asyncio.to_thread(
        listar_candidaturas, pagina, limite, fonte, status
    )


async def remover_candidatura_async(
    fonte: str,
    id_externo: str | None = None,
    url_candidatura: str | None = None,
) -> dict:
    """Versão async de remover_candidatura."""
    return await asyncio.to_thread(
        remover_candidatura, fonte, id_externo, url_candidatura
    )


async def obter_chaves_candidatadas_async(fonte: str | None = None) -> set[str]:
    """Versão async de obter_chaves_candidatadas."""
    return await asyncio.to_thread(obter_chaves_candidatadas, fonte)
