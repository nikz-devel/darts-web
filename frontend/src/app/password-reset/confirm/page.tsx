'use client';

import { useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useState, useEffect, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { Button, FormInput, Alert, Card } from '@/components/ui';
import { confirmPasswordReset } from '@/lib/api';
import { passwordResetConfirmSchema, type PasswordResetConfirmFormData } from '@/lib/validations';

function PasswordResetConfirmContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const [serverError, setServerError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetConfirmFormData>({
    resolver: zodResolver(passwordResetConfirmSchema),
  });

  useEffect(() => {
    if (!token) {
      setServerError('Invalid reset link. Please request a new password reset.');
    }
  }, [token]);

  const onSubmit = async (data: PasswordResetConfirmFormData) => {
    if (!token) return;
    
    setServerError(null);
    setSuccessMessage(null);

    try {
      const result = await confirmPasswordReset({
        token,
        new_password: data.new_password,
        new_password_confirm: data.new_password_confirm,
      });
      setSuccessMessage(result.message || 'Your password has been reset successfully!');
      setTimeout(() => router.push('/login'), 3000);
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Password reset failed.');
    }
  };

  if (!token) {
    return (
      <Card>
        <div className="text-center">
          <Alert variant="error">Invalid reset link. Please request a new password reset.</Alert>
        </div>
      </Card>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {serverError && (
        <Alert variant="error">{serverError}</Alert>
      )}
      {successMessage && (
        <Alert variant="success">{successMessage}</Alert>
      )}

      <FormInput
        label="New Password"
        type="password"
        placeholder="Min 8 characters, letters and numbers"
        error={errors.new_password?.message}
        {...register('new_password')}
      />

      <FormInput
        label="Confirm New Password"
        type="password"
        placeholder="Confirm your new password"
        error={errors.new_password_confirm?.message}
        {...register('new_password_confirm')}
      />

      <Button type="submit" loading={isSubmitting} fullWidth>
        Reset Password
      </Button>
    </form>
  );
}

export default function PasswordResetConfirmPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <Suspense fallback={
          <Card>
            <div className="text-center">
              <div className="animate-spin mx-auto h-12 w-12 rounded-full border-4 border-blue-600 border-t-transparent mb-4" />
              <p className="text-gray-500">Loading...</p>
            </div>
          </Card>
        }>
          <Card title="Set new password" subtitle="Enter your new password below">
            <PasswordResetConfirmContent />
          </Card>
        </Suspense>
      </div>
    </div>
  );
}