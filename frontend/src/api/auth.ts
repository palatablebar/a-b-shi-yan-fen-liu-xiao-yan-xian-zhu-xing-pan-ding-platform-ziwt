import { api } from './client';
import type { LoginResponse } from '../types/api';
import type { User } from '../types/models';

export const loginRequest = (email: string, password: string): Promise<LoginResponse> =>
  api.post<LoginResponse>('/auth/login', { email, password });

export const meRequest = (): Promise<User> => api.get<User>('/auth/me');
