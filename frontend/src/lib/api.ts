import type {
  TokenResponse,
  RegisterRequest,
  LoginRequest,
  ConfirmEmailRequest,
  PasswordResetRequest,
  PasswordResetConfirmRequest,
  User,
  ApiError,
} from '@/types/auth';

// Use relative URLs to route through nginx proxy
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({ detail: 'An error occurred' }));
    throw new Error(error.detail || error.message || 'An error occurred');
  }
  return response.json();
}

export async function register(data: RegisterRequest): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/api/v1/auth/register/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(response);
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(response);
}

export async function confirmEmail(data: ConfirmEmailRequest): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/api/v1/auth/confirm-email/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(response);
}

export async function refreshToken(refreshToken: string): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE}/api/v1/auth/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  return handleResponse(response);
}

export async function logout(refreshToken: string): Promise<void> {
  await fetch(`${API_BASE}/api/v1/auth/logout/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function getCurrentUser(accessToken: string): Promise<User> {
  const response = await fetch(`${API_BASE}/api/v1/auth/me/`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
  return handleResponse(response);
}

export async function requestPasswordReset(data: PasswordResetRequest): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/api/v1/auth/password-reset/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(response);
}

export async function confirmPasswordReset(data: PasswordResetConfirmRequest): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/api/v1/auth/password-reset/confirm/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return handleResponse(response);
}