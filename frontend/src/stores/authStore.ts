/** 登录态：token 落 localStorage，用户信息随 /auth/me 刷新。 */
import { create } from 'zustand';
import { getToken, setToken } from '../api/client';
import { loginRequest, meRequest } from '../api/auth';
import type { User } from '../types/models';

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  loadMe: () => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: getToken(),
  loading: false,
  error: null,

  login: async (email, password) => {
    set({ loading: true, error: null });
    try {
      const response = await loginRequest(email, password);
      setToken(response.access_token);
      set({ user: response.user, token: response.access_token, loading: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : '登录失败';
      set({ loading: false, error: message });
      throw error;
    }
  },

  loadMe: async () => {
    const token = getToken();
    if (!token) {
      set({ user: null, token: null });
      return;
    }
    if (get().user) return;
    try {
      const user = await meRequest();
      set({ user, token });
    } catch {
      setToken(null);
      set({ user: null, token: null });
    }
  },

  logout: () => {
    setToken(null);
    set({ user: null, token: null, error: null });
  },
}));
