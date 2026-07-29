/**
 * API de candidaturas - Persistência no backend com SQLite.
 */
import client from './client';

export const candidaturasAPI = {
  /**
   * Salva uma candidatura.
   * POST /api/candidaturas
   * Retorna 201 on success, 503 on database error
   */
  async salvar(candidatura) {
    try {
      const response = await client.post('/api/candidaturas', {
        fonte: candidatura.fonte,
        id_externo: candidatura.id_externo,
        titulo: candidatura.titulo,
        empresa: candidatura.empresa,
        local: candidatura.local || null,
        url_candidatura: candidatura.url_candidatura,
      });
      
      // Verificar status no body
      if (response.data?.status === 'sucesso') {
        return {
          success: true,
          data: response.data,
        };
      }
      
      return {
        success: false,
        error: response.data?.mensagem || 'Erro ao salvar candidatura',
      };
    } catch (error) {
      console.error('Erro ao salvar candidatura:', error);
      return {
        success: false,
        error: error.response?.data?.detail || error.message,
      };
    }
  },

  /**
   * Lista candidaturas.
   * GET /api/candidaturas
   * Retorna 200 on success, 503 on database error
   */
  async listar({ pagina = 1, limite = 20, fonte = null, status = null } = {}) {
    try {
      const params = {
        pagina,
        limite,
      };
      if (fonte) params.fonte = fonte;
      if (status) params.status = status;

      const response = await client.get('/api/candidaturas', { params });
      
      // Verificar status no body
      if (response.data?.status === 'sucesso') {
        return {
          success: true,
          data: response.data,
        };
      }
      
      return {
        success: false,
        error: response.data?.mensagem || 'Erro ao listar candidaturas',
      };
    } catch (error) {
      console.error('Erro ao listar candidaturas:', error);
      return {
        success: false,
        error: error.response?.data?.detail || error.message,
      };
    }
  },

  /**
   * Remove uma candidatura.
   * DELETE /api/candidaturas
   * Retorna 200 on success (com removed true/false), 400 sem identifier, 503 on database error
   */
  async remover(fonte, idExterno = null, urlCandidatura = null) {
    try {
      const params = {
        fonte,
      };
      if (idExterno) params.id_externo = idExterno;
      if (urlCandidatura) params.url_candidatura = urlCandidatura;

      const response = await client.delete('/api/candidaturas', { params });
      
      // Verificar status no body
      if (response.data?.status === 'sucesso') {
        return {
          success: true,
          removed: response.data.removida,
          data: response.data,
        };
      }
      
      return {
        success: false,
        removed: false,
        error: response.data?.mensagem || 'Erro ao remover candidatura',
      };
    } catch (error) {
      console.error('Erro ao remover candidatura:', error);
      return {
        success: false,
        removed: false,
        error: error.response?.data?.detail || error.message,
      };
    }
  },
};

export default candidaturasAPI;
