import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../supabase';
import { KeyRound, Mail, Sparkles, Loader2, Eye, EyeOff } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const [debugInfo, setDebugInfo] = useState({
    url: window.location.href,
    token: localStorage.getItem('supabase_token') || 'None',
    sessionStatus: 'Checking...',
    error: 'None'
  });

  useEffect(() => {
    const updateDebug = (status, err = 'None') => {
      setDebugInfo({
        url: window.location.href,
        token: localStorage.getItem('supabase_token') || 'None',
        sessionStatus: status,
        error: err
      });
    };

    supabase.auth.getSession().then(({ data: { session }, error }) => {
      if (error) {
        updateDebug('Error getting session', error.message);
      } else if (session) {
        updateDebug('Session found, navigating...');
        localStorage.setItem('supabase_token', session.access_token);
        navigate('/dashboard');
      } else {
        updateDebug('No session found in getSession');
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      console.log('Auth event in Login:', event, session);
      if (session) {
        updateDebug(`Event: ${event} - Session active`);
        localStorage.setItem('supabase_token', session.access_token);
        navigate('/dashboard');
      } else {
        updateDebug(`Event: ${event} - No session active`);
      }
    });

    return () => subscription.unsubscribe();
  }, [navigate]);

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          scopes: 'openid email profile https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/gmail.send',
          queryParams: {
            access_type: 'offline',
            prompt: 'consent'
          },
          redirectTo: window.location.origin + '/auth-callback',
        }
      });
      if (error) throw error;
    } catch (err) {
      console.error('Google auth error:', err);
      setErrorMsg(err.message || 'Google authentication failed');
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;
        
        if (data?.user && data?.session) {
          localStorage.setItem('supabase_token', data.session.access_token);
          setSuccessMsg('Account created successfully!');
          setTimeout(() => navigate('/dashboard'), 1500);
        } else if (data?.user && !data?.session) {
          setSuccessMsg('Check your email to confirm registration!');
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        
        if (data?.session) {
          localStorage.setItem('supabase_token', data.session.access_token);
          navigate('/dashboard');
        }
      }
    } catch (err) {
      console.error('Auth error:', err);
      setErrorMsg(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      width: '100%',
      backgroundColor: 'var(--bg-primary)',
      padding: '1.5rem',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Dynamic Animated background blobs */}
      <div style={{
        position: 'absolute',
        width: '300px',
        height: '300px',
        borderRadius: '50%',
        backgroundColor: 'rgba(16, 185, 129, 0.15)',
        filter: 'blur(80px)',
        top: '20%',
        left: '25%',
        pointerEvents: 'none'
      }} />
      <div style={{
        position: 'absolute',
        width: '250px',
        height: '250px',
        borderRadius: '50%',
        backgroundColor: 'rgba(5, 150, 105, 0.1)',
        filter: 'blur(70px)',
        bottom: '20%',
        right: '25%',
        pointerEvents: 'none'
      }} />

      <div className="card animate-fade-in" style={{
        width: '100%',
        maxWidth: '420px',
        padding: '2.5rem 2rem',
        backdropFilter: 'blur(16px)',
        backgroundColor: 'rgba(20, 20, 20, 0.65)',
        border: '1px solid rgba(63, 63, 70, 0.4)',
        boxShadow: '0 20px 40px rgba(0, 0, 0, 0.3)',
        zIndex: 1
      }}>
        <div style={{ textAlign: 'center', marginBottom: '2.25rem' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            backgroundColor: 'var(--accent-transparent)',
            color: 'var(--accent)',
            marginBottom: '1rem',
            border: '1px solid rgba(16, 185, 129, 0.2)'
          }}>
            <Sparkles size={22} className="pulse-active" />
          </div>
          <h2 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 700 }}>
            {isSignUp ? 'Create Account' : 'Welcome Back'}
          </h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
            {isSignUp ? 'Join the next-gen voice platform' : 'Sign in to access your dashboard'}
          </p>
        </div>

        {errorMsg && (
          <div style={{
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: 'var(--radius-sm)',
            padding: '0.75rem 1rem',
            color: '#f87171',
            fontSize: '0.875rem',
            marginBottom: '1.5rem',
            textAlign: 'center'
          }}>
            {errorMsg}
          </div>
        )}

        {successMsg && (
          <div style={{
            backgroundColor: 'var(--accent-transparent)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: 'var(--radius-sm)',
            padding: '0.75rem 1rem',
            color: 'var(--accent)',
            fontSize: '0.875rem',
            marginBottom: '1.5rem',
            textAlign: 'center'
          }}>
            {successMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Email Address
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="email"
                required
                className="input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
              <Mail size={16} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                className="input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ paddingLeft: '2.5rem', paddingRight: '2.5rem' }}
              />
              <KeyRound size={16} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{ position: 'absolute', right: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%', padding: '0.75rem 1rem', marginTop: '0.5rem' }}>
            {loading ? (
              <Loader2 size={16} className="spin-active" />
            ) : (
              isSignUp ? 'Sign Up' : 'Sign In'
            )}
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', margin: '1.5rem 0', gap: '0.75rem' }}>
          <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border)' }} />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>or</span>
          <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border)' }} />
        </div>

        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={loading}
          style={{
            width: '100%',
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'transparent',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            color: 'var(--text-primary)',
            fontSize: '0.875rem',
            fontWeight: 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.75rem',
            transition: 'background-color 0.2s, border-color 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.25)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.15)';
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
          </svg>
          {isSignUp ? 'Sign Up with Google' : 'Sign In with Google'}
        </button>

        <div style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '1.25rem', textAlign: 'center' }}>
          <button
            onClick={() => {
              setIsSignUp(!isSignUp);
              setErrorMsg('');
              setSuccessMsg('');
            }}
            style={{ color: 'var(--accent)', fontSize: '0.875rem', fontWeight: 500 }}
          >
            {isSignUp ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
          </button>
        </div>

        <div style={{
          marginTop: '1.5rem',
          padding: '0.75rem',
          backgroundColor: 'rgba(0, 0, 0, 0.4)',
          borderRadius: 'var(--radius-sm)',
          fontSize: '0.72rem',
          fontFamily: 'monospace',
          color: 'var(--text-secondary)',
          textAlign: 'left',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          wordBreak: 'break-all'
        }}>
          <div style={{ fontWeight: 'bold', color: 'var(--accent)', marginBottom: '0.25rem' }}>Auth Diagnostics:</div>
          <div>Status: {debugInfo.sessionStatus}</div>
          <div>URL: {debugInfo.url}</div>
          <div>Token: {debugInfo.token.substring(0, 20)}...</div>
          <div>Error: {debugInfo.error}</div>
        </div>
      </div>
    </div>
  );
}
