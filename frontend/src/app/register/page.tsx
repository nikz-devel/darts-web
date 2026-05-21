'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Button, FormInput, Alert, Card, AuthLink } from '@/components/ui';
import { register as apiRegister } from '@/lib/api';
import { registerSchema, type RegisterFormData } from '@/lib/validations';

export default function RegisterPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormData) => {
    setServerError(null);
    setSuccessMessage(null);

    try {
      const result = await apiRegister(data);
      setSuccessMessage(result.message || 'Registration successful! Please check your email to confirm your account.');
      setTimeout(() => router.push('/login'), 3000);
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Registration failed. Please try again.');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <Card title="Create an account" subtitle="Join the tournament">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {serverError && (
              <Alert variant="error">{serverError}</Alert>
            )}
            {successMessage && (
              <Alert variant="success">{successMessage}</Alert>
            )}

            <FormInput
              label="Email"
              type="email"
              placeholder="you@example.com"
              error={errors.email?.message}
              {...register('email')}
            />

            <FormInput
              label="Username"
              type="text"
              placeholder="Your username"
              error={errors.username?.message}
              {...register('username')}
            />

            <FormInput
              label="Password"
              type="password"
              placeholder="Min 8 characters, letters and numbers"
              error={errors.password?.message}
              {...register('password')}
            />

            <FormInput
              label="Confirm Password"
              type="password"
              placeholder="Confirm your password"
              error={errors.password_confirm?.message}
              {...register('password_confirm')}
            />

            <Button type="submit" loading={isSubmitting} fullWidth>
              Create Account
            </Button>
          </form>

          <div className="mt-6 text-center">
            <AuthLink href="/login" text="Already have an account?">
              Sign in
            </AuthLink>
          </div>
        </Card>
      </div>
    </div>
  );
}