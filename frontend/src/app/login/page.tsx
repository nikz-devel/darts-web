'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Button, FormInput, Alert, Card, AuthLink } from '@/components/ui';
import { login as apiLogin } from '@/lib/api';
import { useAuthStore } from '@/store/authStore';
import { loginSchema, type LoginFormData } from '@/lib/validations';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuthStore();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setServerError(null);

    try {
      const tokens = await apiLogin(data);
      await login(tokens);
      router.push('/');
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Login failed. Please try again.');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <Card title="Sign in" subtitle="Welcome back">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {serverError && (
              <Alert variant="error">{serverError}</Alert>
            )}

            <FormInput
              label="Email"
              type="email"
              placeholder="you@example.com"
              error={errors.email?.message}
              {...register('email')}
            />

            <FormInput
              label="Password"
              type="password"
              placeholder="Your password"
              error={errors.password?.message}
              {...register('password')}
            />

            <Button type="submit" loading={isSubmitting} fullWidth>
              Sign In
            </Button>
          </form>

          <div className="mt-6 flex flex-col items-center gap-3">
            <AuthLink href="/password-reset" text="Forgot your password?">
              Reset it
            </AuthLink>
            <AuthLink href="/register" text="Don&apos;t have an account?">
              Sign up
            </AuthLink>
          </div>
        </Card>
      </div>
    </div>
  );
}