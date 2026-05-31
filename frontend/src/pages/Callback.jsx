import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2, CheckCircle2, XCircle } from 'lucide-react';

export default function Callback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('authenticating'); // 'authenticating', 'success', 'error'
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const code = searchParams.get('code');
    if (!code) {
      setStatus('error');
      setErrorMsg('No authorization code found in redirect URL.');
      return;
    }

    const token = localStorage.getItem('supabase_token');
    const headers = {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };

    // Call backend to authenticate
    fetch('http://localhost:8000/api/google/authenticate', {
      method: 'POST',
      headers,
      body: JSON.stringify({ code }),
    })
      .then((res) => {
        if (!res.ok) {
          throw new Error('Failed to authenticate with backend.');
        }
        return res.json();
      })
      .then((data) => {
        setStatus('success');
        // Redirect to dashboard after 1.5 seconds
        setTimeout(() => {
          navigate('/dashboard');
        }, 1500);
      })
      .catch((err) => {
        console.error(err);
        setStatus('error');
        setErrorMsg(err.message || 'An error occurred during authentication.');
      });
  }, [searchParams, navigate]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '80vh',
      padding: '2rem',
      textAlign: 'center',
      color: 'var(--text-primary)',
    }}>
      <div style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-md)',
        padding: '3rem',
        maxWidth: '480px',
        width: '100%',
        boxShadow: 'var(--shadow-lg)',
        backdropFilter: 'blur(10px)',
      }}>
        {status === 'authenticating' && (
          <>
            <Loader2 className="pulse-active" size={48} style={{ color: 'var(--accent)', margin: '0 auto 1.5rem' }} />
            <h2 style={{ fontSize: '1.5rem', marginBottom: '0.75rem', fontWeight: 600 }}>Connecting Google Account</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
              Please wait while we complete the secure handshake with Google...
            </p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle2 size={48} style={{ color: '#10b981', margin: '0 auto 1.5rem' }} />
            <h2 style={{ fontSize: '1.5rem', marginBottom: '0.75rem', fontWeight: 600 }}>Connection Successful!</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
              Your Google account is now connected. Redirecting you to the dashboard...
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle size={48} style={{ color: '#ef4444', margin: '0 auto 1.5rem' }} />
            <h2 style={{ fontSize: '1.5rem', marginBottom: '0.75rem', fontWeight: 600 }}>Connection Failed</h2>
            <p style={{ color: '#ef4444', fontSize: '0.9rem', marginBottom: '1.5rem', lineHeight: 1.6 }}>
              {errorMsg}
            </p>
            <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
              Back to Dashboard
            </button>
          </>
        )}
      </div>
    </div>
  );
}
