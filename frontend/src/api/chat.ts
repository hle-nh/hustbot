import axios from 'axios';
import type { ChatApiResponse, ChatRequest } from '../types';

export const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000,
});

export async function sendMessage(payload: ChatRequest): Promise<ChatApiResponse> {
  const { data } = await api.post<ChatApiResponse>('/chat', payload);
  return data;
}
