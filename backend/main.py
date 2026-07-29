import asyncio
import sys
import logging
from contextlib import asynccontextmanager

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field, field_validator

from app.services.job_aggregator import buscar_vagas_agregadas
from app.database import (
    inicializar_banco,
    salvar_candidatura_async,
    listar_candidaturas_async,
    remover_candidatura_async,
    obter_chaves_candidatadas_async,
)


# Models Pydantic
class CandidaturaRequest(BaseModel):
    fonte: str = Field(..., min_length=1, max_length=100)
    id_externo: str = Field(..., min_length=1, max_length=500)
    titulo: str = Field(..., min_length=1, max_length=500)
    empresa: str = Field(..., min_length=1, max_length=500)
    local: str | None = Field(None, max_length=500)
    url_candidatura: HttpUrl
    
    @field_validator("fonte", "id_externo", "titulo", "empresa", "local", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Não pode ser apenas espaços")
        return v


class CandidaturaResponse(BaseModel):
    status: str
    resultado: str | None = None
    mensagem: str | None = None


# Lifespan para inicialização
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    inicializar_banco()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="JobHunter Automation API",
    description="API para agregação e automação de links de candidaturas.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def adicionar_cabecalhos_seguranca(request: Request, call_next):
    resposta = await call_next(request)
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    resposta.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


@app.get("/api/vagas")
async def buscar_vagas(
    cargo: str = Query(...),
    cidade: str = Query(...),
    estado: str = Query(...),
    modalidade: str = Query("Presencial"),
    pagina: int = Query(1, ge=1),
    max_dias: int | None = Query(None, ge=1, le=30),
    incluir_pcd: bool = Query(False),
):
    from app.database import gerar_chave_vaga
    
    resultado = await buscar_vagas_agregadas(
        cargo=cargo,
        cidade=cidade,
        estado=estado,
        modalidade=modalidade,
        pagina=pagina,
        max_dias=max_dias,
        incluir_pcd=incluir_pcd,
    )

    vagas = resultado["vagas"]
    
    # Obter chaves de candidaturas já realizadas
    try:
        chaves_candidatadas = await obter_chaves_candidatadas_async()
        
        # Preencher ja_candidatado para cada vaga usando chave exata
        for vaga in vagas:
            fonte = vaga.get("fonte", "").strip()
            id_externo = str(vaga.get("id_externo", "")).strip()
            url_candidatura = vaga.get("url_candidatura", "").strip()
            
            # Gerar chave exata da vaga
            chave_vaga = gerar_chave_vaga(fonte, id_externo, url_candidatura)
            
            # Verificar correspondência exata
            vaga["ja_candidatado"] = chave_vaga in chaves_candidatadas
    except Exception as e:
        logging.error(f"Erro ao consultar candidaturas: {e}")
        # Não derrubar a busca - continuar com ja_candidatado padrão (false)

    return {
        "status": "sucesso",
        "pagina_atual": pagina,
        "total_vagas": len(vagas),
        "filtros_usados": {
            "cargo": cargo,
            "cidade": cidade,
            "estado": estado,
            "modalidade": modalidade,
            "max_dias": max_dias,
            "incluir_pcd": incluir_pcd,
        },
        "fontes": resultado["fontes"],
        "vagas": vagas,
    }


@app.post("/api/candidaturas", status_code=201)
async def salvar_candidatura_endpoint(req: CandidaturaRequest):
    """Salva uma candidatura."""
    try:
        resultado = await salvar_candidatura_async(
            fonte=req.fonte,
            id_externo=req.id_externo,
            titulo=req.titulo,
            empresa=req.empresa,
            local=req.local,
            url_candidatura=str(req.url_candidatura),
        )
        
        # Se falhou no banco, retornar 503
        if resultado["status"] != "sucesso":
            raise HTTPException(
                status_code=503,
                detail="Não foi possível salvar a candidatura"
            )
        
        return {
            "status": resultado["status"],
            "resultado": resultado.get("resultado"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Erro ao salvar candidatura: {e}")
        raise HTTPException(
            status_code=503,
            detail="Erro ao salvar candidatura"
        )


@app.get("/api/candidaturas")
async def listar_candidaturas_endpoint(
    pagina: int = Query(1, ge=1),
    limite: int = Query(20, ge=1, le=100),
    fonte: str | None = Query(None),
    status: str | None = Query(None),
):
    """Lista candidaturas."""
    try:
        resultado = await listar_candidaturas_async(
            pagina=pagina,
            limite=limite,
            fonte=fonte,
            status=status,
        )
        
        if resultado["status"] != "sucesso":
            raise HTTPException(
                status_code=503,
                detail="Erro ao listar candidaturas"
            )
        
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Erro ao listar candidaturas: {e}")
        raise HTTPException(
            status_code=503,
            detail="Erro ao listar candidaturas"
        )


@app.delete("/api/candidaturas")
async def remover_candidatura_endpoint(
    fonte: str = Query(...),
    id_externo: str | None = Query(None),
    url_candidatura: str | None = Query(None),
):
    """Remove uma candidatura."""
    try:
        if not id_externo and not url_candidatura:
            raise HTTPException(
                status_code=400,
                detail="id_externo ou url_candidatura obrigatório"
            )
        
        resultado = await remover_candidatura_async(
            fonte=fonte,
            id_externo=id_externo,
            url_candidatura=url_candidatura,
        )
        
        # Se houve erro real, retornar 503
        if resultado["status"] != "sucesso":
            raise HTTPException(
                status_code=503,
                detail="Erro ao remover candidatura"
            )
        
        return resultado
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Erro ao remover candidatura: {e}")
        raise HTTPException(
            status_code=503,
            detail="Erro ao remover candidatura"
        )
