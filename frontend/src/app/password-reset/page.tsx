'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { Button, FormInput, Alert, Card, AuthLink } from '@/components/ui';
import { requestPasswordReset } from '@/lib/api';
import { passwordResetRequestSchema, type PasswordResetRequestFormData } from '@/lib/validations';

export default function PasswordResetPage() {
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetRequestFormData>({
    resolver: zodResolver(passwordResetRequestSchema),
  });

  const onSubmit = async (data: PasswordResetRequestFormData) => {
    setServerError(null);
    setSuccessMessage(null);

    try {
      const result = await requestPasswordReset(data);
      setSuccessMessage(result.message || 'Check your email for password reset instructions.');
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Password reset request failed.');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <Card title="Reset your password" subtitle="We&apos;ll send you reset instructions">
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
              helperText="Enter your registered email address"
              {...register('email')}
            />

            <Button type="submit" loading={isSubmitting} fullWidth>
              Send Reset Instructions
            </Button>
          </form>

          <div className="mt-6 text-center">
            <AuthLink href="/login" text="Remember your password?">
              Sign in
            </AuthLink>
          </div>
        </Card>
      </div>
    </div>
  );
}