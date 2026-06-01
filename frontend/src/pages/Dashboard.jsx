import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Phone, Clock, Trash2, Loader2 } from 'lucide-react';

export default function Dashboard() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadAgents = () => {
    const token = localStorage.getItem('supabase_token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

    fetch('http://localhost:8000/api/agents', { headers })
      .then(res => res.json())
      .then(data => {
        setAgents(data.agents || []);
        setLoading(false);
      })
      .catch(err => console.error(err));
  };

  useEffect(() => { loadAgents(); }, []);

  const deleteAgent = async (agentId, e) => {
    e.stopPropagation();
    if (!confirm('Delete this agent?')) return;

    const token = localStorage.getItem('supabase_token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

    await fetch(`http://localhost:8000/api/agents/${agentId}`, { 
      method: 'DELETE',
      headers
    });
    setAgents(prev => prev.filter(a => a.id !== agentId));
  };

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1>Assistants</h1>
          <p>Manage and monitor your voice agents.</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/build')}>
          <Plus size={18} /> Create Assistant
        </button>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
          <Loader2 className="spin-active" size={32} style={{ color: 'var(--accent)' }} />
        </div>
      ) : agents.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '50%', backgroundColor: 'var(--bg-tertiary)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem', color: 'var(--text-muted)' }}>
            <Phone size={24} />
          </div>
          <h3>No assistants yet</h3>
          <p style={{ marginBottom: '1.5rem' }}>Create your first voice assistant to get started.</p>
          <button className="btn btn-primary" onClick={() => navigate('/build')}>
            Start Building
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
          {agents.map(agent => (
            <div key={agent.id} className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', cursor: 'pointer' }} onClick={() => navigate(`/agent/${agent.id}`)}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                <div>
                  <h3 style={{ margin: 0 }}>{agent.name}</h3>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    ID: {agent.id}
                  </div>
                </div>
                <button className="btn-ghost" style={{ padding: '0.25rem', color: 'var(--text-muted)' }} onClick={(e) => deleteAgent(agent.id, e)} title="Delete agent">
                  <Trash2 size={16} />
                </button>
              </div>
              
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
                <span className="badge">{agent.type}</span>
                <span className="badge">{agent.language}</span>
              </div>
              
              <div style={{ marginTop: 'auto', paddingTop: '1.5rem', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: '1rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <Phone size={14} /> {agent.calls_count}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <Clock size={14} /> {agent.total_minutes.toFixed(1)}m
                  </div>
                </div>
                
                <button 
                  className="btn btn-secondary" 
                  onClick={(e) => { e.stopPropagation(); navigate(`/agent/${agent.id}`); }}
                >
                  Configure & Talk
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
