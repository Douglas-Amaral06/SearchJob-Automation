import { useState } from 'react';

export default function JobCard({ vaga, onMarcarCandidatado, onRemoverCandidatura }) {
  const [salvando, setSalvando] = useState(false);
  const [removendo, setRemovendo] = useState(false);
  const [mensagem, setMensagem] = useState(null);

  const handleMarcarCandidatado = async () => {
    setSalvando(true);
    setMensagem(null);
    
    try {
      await onMarcarCandidatado(vaga);
      setMensagem({ tipo: 'sucesso', texto: 'Candidatura salva!' });
      setTimeout(() => setMensagem(null), 3000);
    } catch (erro) {
      setMensagem({
        tipo: 'erro',
        texto: erro.message || 'Erro ao salvar candidatura',
      });
    } finally {
      setSalvando(false);
    }
  };

  const handleRemover = async () => {
    if (!window.confirm('Remover candidatura?')) return;
    
    setRemovendo(true);
    setMensagem(null);
    
    try {
      await onRemoverCandidatura(vaga);
      setMensagem({ tipo: 'sucesso', texto: 'Candidatura removida' });
      setTimeout(() => setMensagem(null), 3000);
    } catch (erro) {
      const mensagem = erro.message || 'Erro ao remover candidatura';
      setMensagem({ tipo: 'erro', texto: mensagem });
    } finally {
      setRemovendo(false);
    }
  };

  return (
    <div
      className={`border rounded-2xl p-5 shadow-sm transition ${
        vaga.ja_candidatado
          ? "bg-green-50 border-green-200 opacity-80"
          : "bg-white border-gray-200 hover:shadow-md"
      }`}
    >
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div className="flex-1">
          <h2 className="text-lg font-semibold text-gray-900">
            {vaga.titulo}
          </h2>

          <p className="text-gray-700 mt-1">{vaga.empresa}</p>

          <p className="text-sm text-gray-500 mt-2">
            {vaga.local} • {vaga.modalidade}
          </p>

          {vaga.data_publicacao && (
            <p className="text-xs text-gray-400 mt-1">
              Publicada em: {new Date(vaga.data_publicacao).toLocaleDateString("pt-BR")}
            </p>
          )}

          <div className="flex gap-2 mt-3 flex-wrap">
            <span className="text-xs bg-gray-100 text-gray-700 px-3 py-1 rounded-full">
              {vaga.fonte}
            </span>

            {vaga.candidatura_simplificada && (
              <span className="text-xs bg-green-100 text-green-700 px-3 py-1 rounded-full">
                Candidatura simplificada
              </span>
            )}

            {vaga.ja_candidatado && (
              <span className="text-xs bg-green-600 text-white px-3 py-1 rounded-full">
                Já candidatado
              </span>
            )}
          </div>

          {mensagem && (
            <div className={`mt-3 text-sm px-3 py-2 rounded ${
              mensagem.tipo === 'sucesso' 
                ? 'bg-green-100 text-green-700' 
                : 'bg-red-100 text-red-700'
            }`}>
              {mensagem.texto}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2 min-w-[170px]">
          <a
            href={vaga.url_candidatura}
            target="_blank"
            rel="noreferrer"
            className="text-center bg-gray-900 text-white rounded-xl px-5 py-3 text-sm font-medium hover:bg-gray-700 transition"
          >
            Candidatar-se →
          </a>

          {!vaga.ja_candidatado ? (
            <button
              onClick={handleMarcarCandidatado}
              disabled={salvando}
              className="text-center border border-green-600 text-green-700 rounded-xl px-5 py-3 text-sm font-medium hover:bg-green-50 transition disabled:opacity-50"
            >
              {salvando ? 'Salvando...' : 'Já me candidatei'}
            </button>
          ) : (
            <button
              onClick={handleRemover}
              disabled={removendo}
              className="text-center border border-red-600 text-red-700 rounded-xl px-5 py-3 text-sm font-medium hover:bg-red-50 transition disabled:opacity-50"
            >
              {removendo ? 'Removendo...' : 'Desfazer'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
