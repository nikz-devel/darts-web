export interface User {
  id: string;
  email: string;
  username: string;
  created_at?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
  password_confirm: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ConfirmEmailRequest {
  token: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirmRequest {
  token: string;
  new_password: string;
  new_password_confirm: string;
}

export interface ApiError {
  detail?: string;
  message?: string;
  [key: string]: unknown;
}