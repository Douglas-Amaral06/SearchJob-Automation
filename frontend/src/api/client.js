/**
 * Cliente Axios centralizado para comunicação com API.
 */
import axios from 'axios';

const API_PADRAO = 'http://localhost:8000';
const VITE_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || API_PADRAO;

function validarApiBaseUrl(valor) {
  const url = new URL(valor);
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('VITE_API_BASE_URL precisa usar HTTP ou HTTPS.');
  }
  if (import.meta.env.PROD && url.protocol !== 'https:') {
    throw new Error('A API precisa usar HTTPS em produção.');
  }
  return url.toString().replace(/\/$/, '');
}

const client = axios.create({
  baseURL: validarApiBaseUrl(VITE_API_BASE_URL),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default client;
