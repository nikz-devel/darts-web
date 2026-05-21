'use client';

import { useSearchParams } from 'next/navigation';
import { useState, useEffect, Suspense } from 'react';
import { Card, Button, Alert } from '@/components/ui';
import { confirmEmail } from '@/lib/api';
import Link from 'next/link';

function EmailConfirmContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState<string>('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid confirmation link. Please check your email for the correct link.');
      return;
    }

    const confirm = async () => {
      try {
        const result = await confirmEmail({ token });
        setStatus('success');
        setMessage(result.message || 'Your email has been confirmed successfully!');
      } catch (error) {
        setStatus('error');
        setMessage(error instanceof Error ? error.message : 'Email confirmation failed.');
      }
    };

    confirm();
  }, [token]);

  return (
    <Card>
      <div className="text-center">
        {status === 'loading' && (
          <>
            <div className="animate-spin mx-auto h-12 w-12 rounded-full border-4 border-blue-600 border-t-transparent mb-4" />
            <h2 className="text-xl font-semibold text-gray-900">Confirming your email...</h2>
            <p className="mt-2 text-gray-500">Please wait while we verify your email.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="mx-auto h-12 w-12 rounded-full bg-green-100 flex items-center justify-center mb-4">
              <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <Alert variant="success">{message}</Alert>
            <div className="mt-6">
              <Link href="/login">
                <Button>Go to Sign In</Button>
              </Link>
            </div>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="mx-auto h-12 w-12 rounded-full bg-red-100 flex items-center justify-center mb-4">
              <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <Alert variant="error">{message}</Alert>
            <div className="mt-6">
              <Link href="/register">
                <Button variant="secondary">Go to Registration</Button>
              </Link>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

export default function EmailConfirmPage() {
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
          <EmailConfirmContent />
        </Suspense>
      </div>
    </div>
  );
}