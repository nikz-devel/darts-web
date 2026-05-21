import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, TokenResponse } from '@/types/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (tokens: TokenResponse) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setUser: (user: User | null) => void;
  setError: (error: string | null) => void;
}

async function fetchRefresh(refreshToken: string): Promise<TokenResponse> {
  const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  
  if (!response.ok) {
    throw new Error('Token refresh failed');
  }
  
  return response.json();
}

async function fetchLogout(refreshToken: string): Promise<void> {
  try {
    await fetch(`${API_URL}/api/v1/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch {
    // Ignore logout errors
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (tokens: TokenResponse) => {
        set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, isAuthenticated: true });
      },

      logout: async () => {
        const { refreshToken } = get();
        if (refreshToken) {
          await fetchLogout(refreshToken);
        }
        set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false });
      },

      refresh: async () => {
        const { refreshToken } = get();
        if (!refreshToken) {
          set({ isAuthenticated: false });
          return;
        }

        set({ isLoading: true });
        try {
          const tokens = await fetchRefresh(refreshToken);
          set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
        } catch {
          set({ accessToken: null, refreshToken: null, isAuthenticated: false });
        } finally {
          set({ isLoading: false });
        }
      },

      setUser: (user: User | null) => set({ user }),
      setError: (error: string | null) => set({ error }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);