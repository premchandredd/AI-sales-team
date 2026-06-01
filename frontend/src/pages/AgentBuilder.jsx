import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, Send, CheckCircle2, Loader2, Mic, ArrowRight, Pencil } from 'lucide-react';

/*
 * AgentBuilder — Chat-style conversational wizard (like Vapi).
 * Left: Chat with bot questions + clickable options + free text input
 * Right: Agent Configuration panel that updates in real-time
 */

export default function AgentBuilder() {
  const navigate = useNavigate();
  const [steps, setSteps] = useState([]);
  const [currentStepIndex, setCurrentStepIndex] = useState(-1); // -1 = intro message
  const [answers, setAnswers] = useState({});
  const [messages, setMessages] = useState([]);
  const [customText, setCustomText] = useState('');
  const [creating, setCreating] = useState(false);
  const [agentReady, setAgentReady] = useState(null); // created agent
  const [hoveredMsgIndex, setHoveredMsgIndex] = useState(null);
  const chatEndRef = useRef(null);

  // Load wizard steps from backend
  useEffect(() => {
    const token = localStorage.getItem('supabase_token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

    fetch('http://localhost:8000/api/wizard/steps', { headers })
      .then(res => res.json())
      .then(data => {
        setSteps(data.steps);
        // Start with intro message
        setMessages([
          {
            role: 'assistant',
            content: "Hey there! 👋 Let's build your voice agent. I'll ask you a few quick questions to configure it perfectly. Ready? Let's go!",
          }
        ]);
        // Show the first question after a brief pause
        setTimeout(() => {
          setCurrentStepIndex(0);
        }, 600);
      })
      .catch(err => console.error(err));
  }, []);

  // When step index changes, add the bot's question as a message
  useEffect(() => {
    if (currentStepIndex >= 0 && currentStepIndex < steps.length) {
      const step = steps[currentStepIndex];
      setMessages(prev => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg && lastMsg.role === 'assistant' && lastMsg.step && lastMsg.step.id === step.id) {
          return prev;
        }
        return [
          ...prev,
          {
            role: 'assistant',
            content: step.question,
            step: step, // attach step data so we can render options
          }
        ];
      });
    }
  }, [currentStepIndex, steps]);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle option click
  const handleOptionSelect = (stepId, value, isMulti) => {
    if (isMulti) {
      setAnswers(prev => {
        const current = prev[stepId] || [];
        return {
          ...prev,
          [stepId]: current.includes(value)
            ? current.filter(v => v !== value)
            : [...current, value],
        };
      });
    } else {
      // Single select: immediately record and advance
      setAnswers(prev => ({ ...prev, [stepId]: value }));
      // Add user message — show clean label (strip "|code" suffix if present)
      const displayValue = value.includes('|') ? value.split('|')[0] : value;
      setMessages(prev => [...prev, { role: 'user', content: displayValue, stepId }]);
      // Advance after a beat
      setTimeout(() => advanceStep(), 400);
    }
  };

  // Confirm multi-select and advance
  const confirmMultiSelect = () => {
    const step = steps[currentStepIndex];
    const selected = answers[step.id] || [];
    if (selected.length === 0) return;
    setMessages(prev => [...prev, { role: 'user', content: selected.join(', '), stepId: step.id }]);
    setTimeout(() => advanceStep(), 400);
  };

  // Handle free text submission
  const handleTextSubmit = (e) => {
    e?.preventDefault();
    if (!customText.trim()) return;

    const step = steps[currentStepIndex];
    setAnswers(prev => ({ ...prev, [step.id]: customText.trim() }));
    setMessages(prev => [...prev, { role: 'user', content: customText.trim(), stepId: step.id }]);
    setCustomText('');
    setTimeout(() => advanceStep(), 400);
  };

  // Roll back the conversation wizard to a previous step
  const handleEditStep = (stepId) => {
    const targetIdx = steps.findIndex(s => s.id === stepId);
    if (targetIdx === -1) return;

    setCurrentStepIndex(targetIdx);

    // Purge future answers
    setAnswers(prev => {
      const updated = { ...prev };
      for (let i = targetIdx; i < steps.length; i++) {
        delete updated[steps[i].id];
      }
      return updated;
    });

    // Rollback message history
    setMessages(prev => {
      const idx = prev.findIndex(msg => msg.role === 'assistant' && msg.step && msg.step.id === stepId);
      if (idx !== -1) {
        return prev.slice(0, idx + 1);
      }
      return prev;
    });
  };

  // Advance to next step or create agent
  const advanceStep = async () => {
    if (currentStepIndex < steps.length - 1) {
      setCurrentStepIndex(curr => curr + 1);
    } else {
      // All steps done — create the agent
      setCreating(true);
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: '⚡ Building your agent now...' }
      ]);

      try {
        const payload = {
          name: answers.agent_name || 'My Agent',
          type: answers.type || 'inbound',
          language: answers.language || 'English',
          tasks: Array.isArray(answers.tasks) ? answers.tasks : [answers.tasks].filter(Boolean),
          tone: answers.tone || 'Professional',
          business_name: answers.business_info || '',
          custom_instructions: answers.custom_instructions || '',
          voice_gender: answers.voice_gender || 'female',
          google_meet_enabled: false,
          email_notifications_enabled: false,
          email_integration_enabled: false,
          email_integration_instructions: '',
        };

        const token = localStorage.getItem('supabase_token');
        const headers = {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };

        const res = await fetch('http://localhost:8000/api/agents', {
          method: 'POST',
          headers,
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        setAgentReady(data.agent);
        setCreating(false);

        setMessages(prev => [
          ...prev.slice(0, -1), // remove "building" message
          {
            role: 'assistant',
            content: `✅ Your agent "${data.agent.name}" is ready! You can now speak with it or view the dashboard.`,
            agentReady: data.agent,
          }
        ]);
      } catch (err) {
        console.error(err);
        setCreating(false);
        setMessages(prev => [...prev, { role: 'assistant', content: '❌ Something went wrong. Please try again.' }]);
      }
    }
  };

  // Skip optional step
  const skipStep = () => {
    const step = steps[currentStepIndex];
    setMessages(prev => [...prev, { role: 'user', content: '(skipped)', stepId: step.id }]);
    setTimeout(() => advanceStep(), 400);
  };

  // Helper: strip language code suffix for display (e.g. "English + Tamil|ta-IN" → "English + Tamil")
  const displayLang = (val) => val ? val.split('|')[0] : '—';

  // Derive config summary for right panel
  const configSummary = {
    Type: answers.type || '—',
    Language: displayLang(answers.language),
    Voice: answers.voice_gender ? answers.voice_gender.charAt(0).toUpperCase() + answers.voice_gender.slice(1) : '—',
    Tasks: Array.isArray(answers.tasks) ? answers.tasks.join(', ') : (answers.tasks || '—'),
    Tone: answers.tone || '—',
    Business: answers.business_info || '—',
    'Agent Name': answers.agent_name || '—',
  };

  const currentStep = steps[currentStepIndex];
  const isLastMessageAQuestion = messages.length > 0 && messages[messages.length - 1].step;

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

      {/* ─── LEFT: Chat Interface ─── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--border)' }}>

        {/* Header */}
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent), #065f46)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Sparkles size={18} color="white" />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Agent Builder</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Step {Math.max(1, currentStepIndex + 1)} of {steps.length}
            </div>
          </div>
        </div>

        {/* Chat Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {messages.map((msg, i) => (
            <div
              key={i}
              className="animate-fade-in"
              onMouseEnter={() => setHoveredMsgIndex(i)}
              onMouseLeave={() => setHoveredMsgIndex(null)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                gap: '0.75rem',
              }}
            >

              {/* Message bubble wrapper */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                maxWidth: '80%',
              }}>
                {msg.role === 'user' && msg.stepId && !agentReady && hoveredMsgIndex === i && (
                  <button
                    type="button"
                    onClick={() => handleEditStep(msg.stepId)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                      padding: '0.25rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      borderRadius: '50%',
                      backgroundColor: 'var(--bg-tertiary)',
                      border: '1px solid var(--border)',
                      transition: 'all 0.15s ease',
                      width: 24,
                      height: 24,
                    }}
                    title="Edit selection"
                  >
                    <Pencil size={12} />
                  </button>
                )}

                <div style={{
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: msg.role === 'user' ? 'var(--accent)' : 'var(--bg-secondary)',
                  color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
                  border: msg.role === 'user' ? 'none' : '1px solid var(--border)',
                  fontSize: '0.9rem',
                  lineHeight: 1.6,
                }}>
                  {msg.content}
                </div>
              </div>

              {/* Options (only show for the LAST assistant message that has a step) */}
              {msg.step && i === messages.length - 1 && !agentReady && (
                <div style={{ maxWidth: '85%', display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '100%' }}>
                  {msg.step.options?.map(opt => {
                    const isMulti = msg.step.multi_select;
                    const isSelected = isMulti
                      ? (answers[msg.step.id] || []).includes(opt.value)
                      : answers[msg.step.id] === opt.value;

                    return (
                      <button
                        key={opt.value}
                        onClick={() => handleOptionSelect(msg.step.id, opt.value, isMulti)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '0.75rem',
                          padding: '0.75rem 1rem',
                          backgroundColor: isSelected ? 'var(--accent-transparent)' : 'var(--bg-tertiary)',
                          border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                          textAlign: 'left',
                          color: isSelected ? 'var(--accent)' : 'var(--text-primary)',
                          transition: 'all 0.15s ease',
                          width: '100%',
                        }}
                      >
                        <span style={{ fontSize: '1.25rem', flexShrink: 0 }}>{opt.icon}</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{opt.label}</div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.1rem' }}>{opt.description}</div>
                        </div>
                        {isSelected && <CheckCircle2 size={18} color="var(--accent)" />}
                      </button>
                    );
                  })}

                  {/* Multi-select confirm button */}
                  {isLastMessageAQuestion && msg.step.multi_select && (
                    <button
                      className="btn btn-primary"
                      style={{ alignSelf: 'flex-end', marginTop: '0.5rem' }}
                      onClick={confirmMultiSelect}
                      disabled={(answers[msg.step.id] || []).length === 0}
                    >
                      Confirm <ArrowRight size={14} />
                    </button>
                  )}

                  {/* Skip for optional steps */}
                  {msg.step.optional && (
                    <button
                      className="btn btn-ghost"
                      style={{ alignSelf: 'flex-start', fontSize: '0.8rem' }}
                      onClick={skipStep}
                    >
                      Skip this step →
                    </button>
                  )}
                </div>
              )}

              {/* Agent Ready Actions */}
              {msg.agentReady && (
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                  <button
                    className="btn btn-primary"
                    style={{ padding: '0.75rem 1.5rem' }}
                    onClick={() => navigate(`/agent/${msg.agentReady.id}`)}
                  >
                    <Mic size={16} /> Speak with Agent
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => navigate('/dashboard')}
                  >
                    View Dashboard
                  </button>
                </div>
              )}
            </div>
          ))}

          {creating && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent)', padding: '1rem' }}>
              <Loader2 size={18} className="spin-active" /> Building your agent...
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* ─── Bottom Input Bar ─── */}
        {isLastMessageAQuestion && currentStep && !agentReady && (
          <form
            onSubmit={handleTextSubmit}
            style={{
              padding: '1rem 1.5rem',
              borderTop: '1px solid var(--border)',
              display: 'flex',
              gap: '0.75rem',
              alignItems: 'center',
              backgroundColor: 'var(--bg-secondary)',
            }}
          >
            <input
              className="input"
              type="text"
              placeholder={currentStep.custom_placeholder || currentStep.placeholder || "Type something else..."}
              value={customText}
              onChange={e => setCustomText(e.target.value)}
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn btn-primary" disabled={!customText.trim()}>
              <Send size={16} />
            </button>
          </form>
        )}
      </div>

      {/* ─── RIGHT: Agent Configuration Panel ─── */}
      <div style={{ width: 320, backgroundColor: 'var(--bg-secondary)', borderLeft: '1px solid var(--border)', padding: '1.5rem', overflowY: 'auto' }}>
        <h3 style={{ fontSize: '1rem', marginBottom: '1.5rem', color: 'var(--text-primary)' }}>Agent Configuration</h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {Object.entries(configSummary).map(([key, value]) => (
            <div key={key}>
              <div style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                {key}
              </div>
              <div style={{
                fontSize: '0.875rem',
                color: value === '—' ? 'var(--text-muted)' : 'var(--text-primary)',
                backgroundColor: 'var(--bg-tertiary)',
                padding: '0.5rem 0.75rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
              }}>
                {value}
              </div>
            </div>
          ))}
        </div>

        {agentReady && (
          <div style={{ marginTop: '2rem', padding: '1rem', backgroundColor: 'var(--accent-transparent)', borderRadius: 'var(--radius-md)', border: '1px solid var(--accent)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent)', fontWeight: 600, marginBottom: '0.5rem' }}>
              <CheckCircle2 size={16} /> Agent Created
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              ID: {agentReady.id}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
