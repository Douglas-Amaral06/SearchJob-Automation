/**
 * Histórico de candidaturas - Minhas candidaturas.
 */
import { useCallback, useEffect, useState } from 'react';
import candidaturasAPI from '../api/candidaturas';

export default function ApplicationHistory({
  isOpen,
  onClose,
  refreshKey = 0,
  onCandidaturaRemovida,
}) {
  const [candidaturas, setCandidaturas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pagina, setPagina] = useState(1);
  const [total, setTotal] = useState(0);

  const LIMITE = 10;

  const carregarCandidaturas = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    const resultado = await candidaturasAPI.listar({
      pagina,
      limite: LIMITE,
    });

    if (resultado.success) {
      setCandidaturas(resultado.data.candidaturas || []);
      setTotal(resultado.data.total || 0);
    } else {
      setError('Erro ao carregar histórico de candidaturas');
      setCandidaturas([]);
    }
    
    setLoading(false);
  }, [pagina]);

  useEffect(() => {
    if (isOpen) {
      carregarCandidaturas();
    }
  }, [isOpen, refreshKey, carregarCandidaturas]);

  const removerCandidatura = async (candidatura) => {
    if (!window.confirm(`Remover candidatura em ${candidatura.empresa}?`)) {
      return;
    }

    const resultado = await candidaturasAPI.remover(
      candidatura.fonte,
      candidatura.id_externo
    );

    if (resultado.success && resultado.removed) {
      onCandidaturaRemovida?.(candidatura);

      if (candidaturas.length === 1 && pagina > 1) {
        setPagina((paginaAtual) => paginaAtual - 1);
      } else {
        await carregarCandidaturas();
      }
    } else if (!resultado.removed) {
      setError('Candidatura não encontrada');
    } else {
      setError('Erro ao remover candidatura');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-blue-700 text-white p-6 flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold">Minhas Candidaturas</h2>
            <p className="text-blue-100 mt-1">
              Total: <span className="font-semibold">{total}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-white hover:bg-blue-800 rounded-full p-2 transition"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
              <p className="text-gray-600 mt-2">Carregando...</p>
            </div>
          ) : candidaturas.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500">Nenhuma candidatura realizada ainda.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {candidaturas.map((candidatura) => (
                <div
                  key={candidatura.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="font-bold text-lg text-gray-900">
                        {candidatura.titulo}
                      </h3>
                      <p className="text-gray-600 text-sm mt-1">
                        <span className="font-semibold">{candidatura.empresa}</span>
                        {candidatura.local && ` • ${candidatura.local}`}
                      </p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="inline-block px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
                          {candidatura.fonte}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(candidatura.candidatado_em.replace('Z', '+00:00')).toLocaleDateString('pt-BR')}
                        </span>
                      </div>
                    </div>
                    <div className="flex gap-2 ml-4">
                      <a
                        href={candidatura.url_candidatura}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition"
                      >
                        Abrir
                      </a>
                      <button
                        onClick={() => removerCandidatura(candidatura)}
                        className="px-3 py-2 bg-red-100 text-red-700 text-sm rounded hover:bg-red-200 transition"
                      >
                        Remover
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {!loading && total > LIMITE && (
            <div className="flex justify-center gap-2 mt-6">
              <button
                onClick={() => setPagina(Math.max(1, pagina - 1))}
                disabled={pagina === 1}
                className="px-4 py-2 border border-gray-300 rounded disabled:opacity-50 hover:bg-gray-50"
              >
                Anterior
              </button>
              <span className="px-4 py-2 text-gray-700">
                Página {pagina} de {Math.ceil(total / LIMITE)}
              </span>
              <button
                onClick={() => setPagina(Math.min(Math.ceil(total / LIMITE), pagina + 1))}
                disabled={pagina >= Math.ceil(total / LIMITE)}
                className="px-4 py-2 border border-gray-300 rounded disabled:opacity-50 hover:bg-gray-50"
              >
                Próxima
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
