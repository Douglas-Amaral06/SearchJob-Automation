import { useState } from "react";

export default function SearchBar({ onSearch, loading }) {
  const [form, setForm] = useState({
    cargo: "Auxiliar Administrativo",
    cidade: "Guarulhos",
    estado: "SP",
    modalidade: "Presencial",
    max_dias: "",
    incluir_pcd: false,
  });

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    onSearch(form);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-4xl bg-white rounded-2xl shadow-sm border border-gray-200 p-4"
    >
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <input
          name="cargo"
          value={form.cargo}
          onChange={handleChange}
          placeholder="Cargo"
          className="md:col-span-2 border border-gray-300 rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500"
        />

        <input
          name="cidade"
          value={form.cidade}
          onChange={handleChange}
          placeholder="Cidade"
          className="border border-gray-300 rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500"
        />

        <input
          name="estado"
          value={form.estado}
          onChange={handleChange}
          placeholder="UF"
          maxLength={2}
          className="border border-gray-300 rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500 uppercase"
        />

        <select
          name="modalidade"
          value={form.modalidade}
          onChange={handleChange}
          className="border border-gray-300 rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option>Presencial</option>
          <option>Híbrido</option>
          <option>Remoto</option>
        </select>

        <select
          name="max_dias"
          value={form.max_dias}
          onChange={handleChange}
          className="md:col-span-2 border border-gray-300 rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Qualquer data</option>
          <option value="1">Últimas 24 horas</option>
          <option value="3">Últimas 72 horas</option>
          <option value="7">Últimos 7 dias</option>
          <option value="15">Últimos 15 dias</option>
          <option value="30">Últimos 30 dias</option>
        </select>

        <div className="md:col-span-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3">
          <p className="text-sm font-medium text-gray-700 mb-2">
            Você é PCD?
          </p>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() =>
                setForm((prev) => ({ ...prev, incluir_pcd: true }))
              }
              className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition ${
                form.incluir_pcd
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-100"
              }`}
            >
              Sim
            </button>

            <button
              type="button"
              onClick={() =>
                setForm((prev) => ({ ...prev, incluir_pcd: false }))
              }
              className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition ${
                !form.incluir_pcd
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-100"
              }`}
            >
              Não
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="md:col-span-1 bg-blue-600 text-white rounded-xl px-6 py-3 font-medium hover:bg-blue-700 disabled:bg-blue-300 transition"
        >
          {loading ? "Buscando..." : "Buscar vagas"}
        </button>
      </div>
    </form>
  );
}