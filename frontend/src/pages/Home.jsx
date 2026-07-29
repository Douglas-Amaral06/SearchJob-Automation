import { useState } from "react";
import SearchBar from "../components/SearchBar";
import JobList from "../components/JobList";
import ApplicationHistory from "../components/ApplicationHistory";
import { buscarVagas } from "../api/vagas";
import candidaturasAPI from "../api/candidaturas";

function getVagaId(vaga) {
  return `${vaga.fonte}-${vaga.id_externo || vaga.url_candidatura}`;
}

export default function Home() {
  const [vagas, setVagas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");
  const [pagina, setPagina] = useState(1);
  const [ultimosFiltros, setUltimosFiltros] = useState(null);
  const [totalVagas, setTotalVagas] = useState(0);
  const [showHistory, setShowHistory] = useState(false);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  async function executarBusca(filtros, paginaBusca = 1) {
    try {
      setLoading(true);
      setErro("");

      const data = await buscarVagas({
        ...filtros,
        pagina: paginaBusca,
      });

      setVagas(data.vagas || []);
      setPagina(data.pagina_atual || paginaBusca);
      setTotalVagas(data.total_vagas || 0);
      setUltimosFiltros(filtros);
    } catch (error) {
      console.error(error);
      setErro("Não foi possível buscar as vagas. Verifique se o backend está rodando.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(filtros) {
    await executarBusca(filtros, 1);
  }

  async function proximaPagina() {
    if (!ultimosFiltros) return;
    await executarBusca(ultimosFiltros, pagina + 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function paginaAnterior() {
    if (!ultimosFiltros || pagina <= 1) return;
    await executarBusca(ultimosFiltros, pagina - 1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function marcarComoCandidatado(vaga) {
    const resultado = await candidaturasAPI.salvar({
      fonte: vaga.fonte,
      id_externo: vaga.id_externo,
      titulo: vaga.titulo,
      empresa: vaga.empresa,
      local: vaga.local,
      url_candidatura: vaga.url_candidatura,
    });

    if (resultado.success) {
      setVagas((prev) =>
        prev.map((item) =>
          getVagaId(item) === getVagaId(vaga)
            ? { ...item, ja_candidatado: true }
            : item
        )
      );
      setHistoryRefreshKey((valor) => valor + 1);
    } else {
      throw new Error(resultado.error);
    }
  }

  async function removerCandidatura(vaga) {
    const resultado = await candidaturasAPI.remover(
      vaga.fonte,
      vaga.id_externo
    );

    if (resultado.success && resultado.removed) {
      setVagas((prev) =>
        prev.map((item) =>
          getVagaId(item) === getVagaId(vaga)
            ? { ...item, ja_candidatado: false }
            : item
        )
      );
      setHistoryRefreshKey((valor) => valor + 1);
    } else if (!resultado.removed) {
      // Vaga não foi removida (não existia)
      throw new Error('Candidatura não encontrada');
    } else {
      throw new Error(resultado.error);
    }
  }

  function sincronizarRemocaoDoHistorico(candidatura) {
    setVagas((prev) =>
      prev.map((vaga) =>
        getVagaId(vaga) === getVagaId(candidatura)
          ? { ...vaga, ja_candidatado: false }
          : vaga
      )
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-12 flex flex-col items-center">
      <section className="text-center mb-8">
        <h1 className="text-4xl font-bold text-gray-900">
          SearchJob Automation
        </h1>

        <p className="text-gray-500 mt-3">
          Busque vagas em vários portais com poucos cliques.
        </p>

        <button
          onClick={() => setShowHistory(true)}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm"
        >
          📋 Minhas Candidaturas
        </button>
      </section>

      <SearchBar onSearch={handleSearch} loading={loading} />

      {erro && (
        <div className="w-full max-w-4xl mt-6 bg-red-50 text-red-700 border border-red-200 rounded-xl p-4">
          {erro}
        </div>
      )}

      {ultimosFiltros && !erro && vagas.length > 0 && (
        <div className="w-full max-w-4xl mt-6 flex justify-between items-center text-sm text-gray-500">
          <span>
            Página {pagina} • {totalVagas} vagas exibidas
          </span>

          {ultimosFiltros.max_dias && (
            <span>
              Filtro: últimos {ultimosFiltros.max_dias} dias
            </span>
          )}
        </div>
      )}

      {!ultimosFiltros && vagas.length === 0 && !loading && (
        <div className="w-full max-w-4xl mt-6 text-center text-gray-500 py-12">
          <p className="text-lg">Nenhuma busca realizada ainda.</p>
          <p className="text-sm mt-2">Use a barra de busca acima para começar.</p>
        </div>
      )}

      <JobList
        vagas={vagas}
        onMarcarCandidatado={marcarComoCandidatado}
        onRemoverCandidatura={removerCandidatura}
      />

      {ultimosFiltros && vagas.length > 0 && (
        <div className="w-full max-w-4xl mt-8 flex justify-between">
          <button
            onClick={paginaAnterior}
            disabled={loading || pagina <= 1}
            className="px-5 py-3 rounded-xl border border-gray-300 bg-white text-gray-700 disabled:opacity-40 hover:bg-gray-100 transition"
          >
            ← Página anterior
          </button>

          <button
            onClick={proximaPagina}
            disabled={loading}
            className="px-5 py-3 rounded-xl bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition"
          >
            Próxima página →
          </button>
        </div>
      )}

      <ApplicationHistory 
        isOpen={showHistory} 
        onClose={() => setShowHistory(false)}
        refreshKey={historyRefreshKey}
        onCandidaturaRemovida={sincronizarRemocaoDoHistorico}
      />
    </main>
  );
}
