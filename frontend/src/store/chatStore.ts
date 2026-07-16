import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { v4 as uuidv4 } from 'uuid';
import { sendMessage } from '../api/chat';
import type { Category, Conversation, Message } from '../types';

interface ChatStore {
  conversations: Conversation[];
  activeConversationId: string | null;
  isLoading: boolean;
  error: string | null;
  webSearchEnabled: boolean;

  // Actions
  newConversation: () => string;
  selectConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  clearError: () => void;
  toggleWebSearch: () => void;
  setConversationCategory: (id: string, category: Category) => void;
  sendMessage: (text: string) => Promise<void>;
  activeConversation: () => Conversation | undefined;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeConversationId: null,
      isLoading: false,
      error: null,
      webSearchEnabled: false,

      activeConversation: () => {
        const { conversations, activeConversationId } = get();
        return conversations.find((c) => c.id === activeConversationId);
      },

      newConversation: () => {
        const id = uuidv4();
        const now = new Date().toISOString();
        const newConv: Conversation = {
          id,
          title: 'Cuộc trò chuyện mới',
          messages: [],
          created_at: now,
          category: 'all',
        };
        set((state) => ({
          conversations: [newConv, ...state.conversations],
          activeConversationId: id,
          error: null,
        }));
        return id;
      },

      selectConversation: (id) => {
        set({ activeConversationId: id, error: null });
      },

      deleteConversation: (id) => {
        set((state) => {
          const remaining = state.conversations.filter((c) => c.id !== id);
          const nextActive =
            state.activeConversationId === id
              ? (remaining[0]?.id ?? null)
              : state.activeConversationId;
          return { conversations: remaining, activeConversationId: nextActive };
        });
      },

      clearError: () => set({ error: null }),

      toggleWebSearch: () => set((state) => ({ webSearchEnabled: !state.webSearchEnabled })),

      setConversationCategory: (id: string, category: Category) => {
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, category } : c
          ),
        }));
      },

      sendMessage: async (text: string) => {
        const store = get();
        // Get or create an active conversation
        let convId = store.activeConversationId;
        if (!convId) {
          convId = store.newConversation();
        }

        const userMsg: Message = {
          id: uuidv4(),
          role: 'user',
          content: text,
          created_at: new Date().toISOString(),
        };

        // Append user message immediately
        set((state) => ({
          conversations: state.conversations.map((c) =>
            c.id === convId
              ? { ...c, messages: [...c.messages, userMsg] }
              : c
          ),
          isLoading: true,
          error: null,
        }));

        // Get current conversation category
        const conv = get().conversations.find((c) => c.id === convId);
        const category = conv?.category ?? 'all';

        try {
          const response = await sendMessage({
            conversation_id: convId,
            message: text,
            web_search: get().webSearchEnabled || undefined,
            category,
          });

          const assistantMsg: Message = {
            id: uuidv4(),
            role: 'assistant',
            content: response.answer,
            sources: response.sources,
            elapsed_seconds: response.elapsed_seconds,
            web_search_used: response.web_search_used,
            created_at: new Date().toISOString(),
          };

          // Derive a title from the first user message
          set((state) => ({
            isLoading: false,
            conversations: state.conversations.map((c) => {
              if (c.id !== convId) return c;
              const isFirst = c.messages.length === 1; // only the user message so far
              return {
                ...c,
                title: isFirst ? text.slice(0, 60) : c.title,
                messages: [...c.messages, assistantMsg],
              };
            }),
          }));
        } catch (err: unknown) {
          const msg =
            err instanceof Error
              ? err.message
              : 'Đã có lỗi xảy ra, vui lòng thử lại.';
          set({ isLoading: false, error: msg });
        }
      },
    }),
    {
      name: 'hustbot-store',
      // Only persist conversations list, not loading state
      partialize: (state) => ({
        conversations: state.conversations,
        activeConversationId: state.activeConversationId,
      }),
    }
  )
);
