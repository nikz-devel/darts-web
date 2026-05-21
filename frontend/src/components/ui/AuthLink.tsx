'use client';

import Link from 'next/link';

interface AuthLinkProps {
  href: string;
  children: React.ReactNode;
  text?: string;
}

export function AuthLink({ href, children, text }: AuthLinkProps) {
  return (
    <p className="text-sm text-gray-600">
      {text}
      <Link
        href={href}
        className="font-medium text-blue-600 hover:text-blue-500 ml-1"
      >
        {children}
      </Link>
    </p>
  );
}