import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Mic, PlusSquare, Settings, BookOpen, LogOut, LogIn, User } from 'lucide-react';
import { supabase } from '../supabase';

export default function Sidebar() {
  const navigate = useNavigate();
  const [googleProfile, setGoogleProfile] = useState({ authenticated: false });
  const [loading, setLoading] = useState(true);
  const [userSession, setUserSession] = useState(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUserSession(session);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const fetchStatus = () => {
    const token = localStorage.getItem('supabase_token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
    
    fetch('http://localhost:8000/api/google/status', { headers })
      .then((res) => res.json())
      .then((data) => {
        setGoogleProfile(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch google status:', err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchStatus();
    // Poll status occasionally to keep sidebar in sync
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleConnect = async () => {
    try {
      const token = localStorage.getItem('supabase_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      
      const res = await fetch('http://localhost:8000/api/google/auth-url', { headers });
      const data = await res.json();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (err) {
      console.error('Failed to get auth URL:', err);
    }
  };

  const handleDisconnect = async () => {
    try {
      const token = localStorage.getItem('supabase_token');
      const headers = token ? { 
        'Method': 'POST', 
        'Authorization': `Bearer ${token}` 
      } : { 'Method': 'POST' };

      await fetch('http://localhost:8000/api/google/logout', { 
        method: 'POST', 
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      setGoogleProfile({ authenticated: false });
    } catch (err) {
      console.error('Failed to logout:', err);
    }
  };

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    localStorage.removeItem('supabase_token');
    navigate('/login');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div style={{
          width: '32px',
          height: '32px',
          backgroundColor: 'var(--accent)',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white'
        }}>
          <Mic size={20} />
        </div>
        Your Voice Agent
      </div>

      <nav style={{ flex: 1, marginTop: '2rem' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem', paddingLeft: '0.5rem' }}>
          BUILD
        </div>
        
        <NavLink to="/dashboard" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={18} />
          Dashboard
        </NavLink>
        
        <NavLink to="/build" className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
          <PlusSquare size={18} />
          Create Agent
        </NavLink>

        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem', paddingLeft: '0.5rem', marginTop: '2rem' }}>
          RESOURCES
        </div>

        <a href="#" className="nav-item" style={{ opacity: 0.7 }}>
          <BookOpen size={18} />
          Documentation
        </a>
        <a href="#" className="nav-item" style={{ opacity: 0.7 }}>
          <Settings size={18} />
          Settings
        </a>
      </nav>



      {/* Supabase Logout Panel */}
      {userSession && (
        <div style={{ padding: '0.75rem 0.5rem 0.25rem 0.5rem', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
            <div style={{ width: '28px', height: '28px', borderRadius: '50%', backgroundColor: 'var(--bg-tertiary)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
              <User size={14} />
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '120px' }}>
              {userSession.user.email}
            </div>
          </div>
          <button 
            onClick={handleSignOut} 
            title="Sign Out"
            style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', padding: '0.25rem' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
          >
            <LogOut size={14} />
          </button>
        </div>
      )}
    </aside>
  );
}

