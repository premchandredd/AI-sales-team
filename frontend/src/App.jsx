import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import AgentBuilder from './pages/AgentBuilder';
import VoiceTest from './pages/VoiceTest';
import Callback from './pages/Callback';
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import { supabase } from './supabase';

function ProtectedRoute() {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check both hash and query parameters for active OAuth or PKCE flow codes
    const hasAuthParams = window.location.hash.includes('access_token=') || 
                          window.location.hash.includes('id_token=') ||
                          window.location.hash.includes('error=') ||
                          window.location.search.includes('code=') ||
                          window.location.search.includes('error=');

    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      if (session) {
        localStorage.setItem('supabase_token', session.access_token);
      } else {
        localStorage.removeItem('supabase_token');
      }
      if (!hasAuthParams) {
        setLoading(false);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (session) {
        localStorage.setItem('supabase_token', session.access_token);
        setLoading(false);
      } else {
        localStorage.removeItem('supabase_token');
        if (!hasAuthParams) {
          setLoading(false);
        }
      }
    });

    // Fallback timeout in case OAuth parsing fails/errors
    let timeoutId;
    if (hasAuthParams) {
      timeoutId = setTimeout(() => {
        setLoading(false);
      }, 2000); // 2 second safety fallback
    }

    return () => {
      subscription.unsubscribe();
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', backgroundColor: 'var(--bg-primary)' }}>
        <div className="pulse-active" style={{ width: '40px', height: '40px', borderRadius: '50%', backgroundColor: 'var(--accent-transparent)', border: '2px solid var(--accent)' }} />
      </div>
    );
  }

  return session ? <Outlet /> : <Navigate to="/login" replace />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/auth-callback" element={<AuthCallback />} />
        
        {/* Protected layout routing */}
        <Route element={<ProtectedRoute />}>
          <Route element={
            <div className="app-container">
              <Sidebar />
              <main className="main-content">
                <Outlet />
              </main>
            </div>
          }>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/build" element={<AgentBuilder />} />
            <Route path="/agent/:id" element={<VoiceTest />} />
            <Route path="/callback" element={<Callback />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
