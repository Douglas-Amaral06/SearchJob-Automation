import client from "./client";

export async function buscarVagas({
  cargo,
  cidade,
  estado,
  modalidade,
  pagina = 1,
  max_dias,
  incluir_pcd = false,
}) {
  const params = {
    cargo: cargo.trim(),
    cidade: cidade.trim(),
    estado: estado.trim().toUpperCase(),
    modalidade,
    pagina,
    incluir_pcd,
  };

  if (max_dias) {
    params.max_dias = Number(max_dias);
  }

  const response = await client.get("/api/vagas", {
    params,
  });

  return response.data;
}