// API types shared across the app

export type Category = 'all' | 'academic' | 'admissions';

export interface Source {
  file: string;
  page: number | string;
  preview: string;
}

export interface ChatRequest {
  conversation_id: string | null;
  message: string;
  web_search?: boolean;
  category?: Category;
}

export interface ChatApiResponse {
  conversation_id: string;
  answer: string;
  sources: Source[];
  elapsed_seconds: number;
  web_search_used: boolean;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  elapsed_seconds?: number;
  web_search_used?: boolean;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  created_at: string;
  category?: Category;
}
