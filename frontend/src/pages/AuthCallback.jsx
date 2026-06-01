import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../supabase';
import { Loader2 } from 'lucide-react';

export default function AuthCallback() {
  const navigate = useNavigate();
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const syncTokens = async (session) => {
      if (session.provider_token) {
        try {
          await fetch('http://localhost:8000/api/google/sync-provider-tokens', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${session.access_token}`
            },
            body: JSON.stringify({
              provider_token: session.provider_token,
              provider_refresh_token: session.provider_refresh_token,
              expires_in: session.expires_in
            })
          });
          console.log('[AuthCallback] Google provider credentials synced successfully.');
        } catch (err) {
          console.error('[AuthCallback] Failed to sync Google provider credentials:', err);
        }
      }
    };

    // Listen for auth state change
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      console.log('AuthCallback event:', event, session);
      if (session) {
        localStorage.setItem('supabase_token', session.access_token);
        await syncTokens(session);
        navigate('/dashboard');
      } else if (event === 'SIGNED_OUT') {
        navigate('/login');
      }
    });

    // Check current session immediately
    supabase.auth.getSession().then(async ({ data: { session }, error }) => {
      if (error) {
        setErrorMsg(error.message);
      } else if (session) {
        localStorage.setItem('supabase_token', session.access_token);
        await syncTokens(session);
        navigate('/dashboard');
      }
    });

    // Timeout fallback (4 seconds)
    const timeoutId = setTimeout(() => {
      supabase.auth.getSession().then(async ({ data: { session } }) => {
        if (session) {
          localStorage.setItem('supabase_token', session.access_token);
          await syncTokens(session);
          navigate('/dashboard');
        } else {
          setErrorMsg('Authentication timed out or failed. Please check your credentials and try again.');
        }
      });
    }, 4000);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timeoutId);
    };
  }, [navigate]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      backgroundColor: 'var(--bg-primary)',
      color: 'var(--text-primary)',
      padding: '2.5rem'
    }}>
      <div style={{
        padding: '2.5rem',
        borderRadius: 'var(--radius-md)',
        backgroundColor: 'rgba(20, 20, 20, 0.65)',
        border: '1px solid rgba(63, 63, 70, 0.4)',
        backdropFilter: 'blur(16px)',
        textAlign: 'center',
        maxWidth: '400px',
        width: '100%'
      }}>
        {errorMsg ? (
          <>
            <h2 style={{ fontSize: '1.25rem', color: '#ef4444', marginBottom: '1rem', fontWeight: 600 }}>Login Failed</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', lineHeight: 1.5 }}>{errorMsg}</p>
            <button className="btn btn-primary" onClick={() => navigate('/login')} style={{ width: '100%', padding: '0.6rem' }}>
              Back to Login
            </button>
          </>
        ) : (
          <>
            <Loader2 className="spin-active" size={40} style={{ color: 'var(--accent)', margin: '0 auto 1.25rem' }} />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>Completing Sign In</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Please wait while we establish your secure session...
            </p>
          </>
        )}
      </div>
    </div>
  );
}
