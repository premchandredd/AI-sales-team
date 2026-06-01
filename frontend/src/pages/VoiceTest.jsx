import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Phone,
  PhoneOff,
  Mic,
  MicOff,
  Activity,
  Loader2,
  ArrowLeft,
  Volume2,
  Calendar,
  FileSpreadsheet,
  Save,
  RefreshCw,
  Plus,
  CheckCircle,
  HelpCircle,
  ExternalLink,
  Clock,
  Repeat,
  Shuffle,
  PhoneIncoming,
  PhoneOutgoing,
  Settings,
  ToggleLeft,
  ToggleRight,
  AlertCircle,
  Users,
  Zap,
  Play,
  Pause,
  PhoneForwarded,
  MessageSquare,
  Shield,
} from 'lucide-react';
import { useVoiceStream } from '../hooks/useVoiceStream';


// Custom authenticated fetch helper
const authFetch = (url, options = {}) => {
  const token = localStorage.getItem('supabase_token');
  const headers = {
    ...options.headers,
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
  return fetch(url, { ...options, headers });
};

export default function VoiceTest() {
  const { id } = useParams();
  // Twilio Telephony State
  const [twilioSid, setTwilioSid] = useState('');
  const [twilioToken, setTwilioToken] = useState('');
  const [twilioPhone, setTwilioPhone] = useState('');
  const [loadingTwilio, setLoadingTwilio] = useState(false);
  const [savingTwilio, setSavingTwilio] = useState(false);
  const [targetPhoneNumber, setTargetPhoneNumber] = useState('');
  const [dialingStatus, setDialingStatus] = useState(''); // '', 'calling', 'ringing', 'in-progress', 'completed', 'failed'
  const [activeCallSid, setActiveCallSid] = useState('');

  const navigate = useNavigate();

  // Agent State
  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(true);

  // Google Integration State
  const [googleStatus, setGoogleStatus] = useState({ authenticated: false });
  const [calendars, setCalendars] = useState([]);
  const [spreadsheets, setSpreadsheets] = useState([]);
  const [sheetTabs, setSheetTabs] = useState([]);
  const [leads, setLeads] = useState([]);
  
  // UI Loading States
  const [loadingCalendars, setLoadingCalendars] = useState(false);
  const [loadingSheets, setLoadingSheets] = useState(false);
  const [loadingTabs, setLoadingTabs] = useState(false);
  const [loadingLeads, setLoadingLeads] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [creatingTemplate, setCreatingTemplate] = useState(false);

  // Connection config inputs (mirrors agent fields)
  const [calendarEnabled, setCalendarEnabled] = useState(false);
  const [calendarId, setCalendarId] = useState('primary');
  const [meetEnabled, setMeetEnabled] = useState(false);
  const [emailNotificationsEnabled, setEmailNotificationsEnabled] = useState(false);
  const [sheetsEnabled, setSheetsEnabled] = useState(false);
  const [sheetsId, setSheetsId] = useState('');
  const [sheetsName, setSheetsName] = useState('');
  const [integrationInstructions, setIntegrationInstructions] = useState('');
  const [emailIntegrationEnabled, setEmailIntegrationEnabled] = useState(false);
  const [emailIntegrationInstructions, setEmailIntegrationInstructions] = useState('');
  const [whatsappEnabled, setWhatsappEnabled] = useState(false);
  const [whatsappPhoneNumberId, setWhatsappPhoneNumberId] = useState('');
  const [whatsappWabaId, setWhatsappWabaId] = useState('');
  const [whatsappAccessToken, setWhatsappAccessToken] = useState('');
  const [whatsappTemplateName, setWhatsappTemplateName] = useState('hello_world');
  const [whatsappTemplateLanguage, setWhatsappTemplateLanguage] = useState('en_US');
  const [whatsappIntegrationInstructions, setWhatsappIntegrationInstructions] = useState('');

  // Live Agent Transfer State
  const [liveTransferEnabled, setLiveTransferEnabled] = useState(false);
  const [liveTransferNumber, setLiveTransferNumber] = useState('');

  // Call Logs & Analytics State
  const [leftTab, setLeftTab] = useState('settings');
  const [calls, setCalls] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [selectedCallLog, setSelectedCallLog] = useState(null);

  // WebRTC Stream State
  const [useWebRTC, setUseWebRTC] = useState(false);

  // Campaign Dialer State
  const [campaigns, setCampaigns] = useState([]);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  const [campName, setCampName] = useState('');
  const [campSpreadsheetId, setCampSpreadsheetId] = useState('');
  const [campSheetName, setCampSheetName] = useState('');
  const [showCreateCamp, setShowCreateCamp] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [campStartTime, setCampStartTime] = useState('09:00');
  const [campEndTime, setCampEndTime] = useState('18:00');
  const [campMaxConcurrency, setCampMaxConcurrency] = useState(1);
  const [campRetryCount, setCampRetryCount] = useState(0);
  const [campRetryDelay, setCampRetryDelay] = useState(15);
  const [campCallOrder, setCampCallOrder] = useState('sequential');
  const [campAfterHoursAction, setCampAfterHoursAction] = useState('none');
  const [campAfterHoursMessage, setCampAfterHoursMessage] = useState('');
  const [campAfterHoursTransferNumber, setCampAfterHoursTransferNumber] = useState('');

  const [campLeads, setCampLeads] = useState([]);
  const [loadingCampLeads, setLoadingCampLeads] = useState(false);

  // Knowledge Base RAG State
  const [kbFiles, setKbFiles] = useState([]);
  const [loadingKb, setLoadingKb] = useState(false);
  const [uploadingKb, setUploadingKb] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [fileToUpload, setFileToUpload] = useState(null);

  // Editable Script State
  const [firstMessage, setFirstMessage] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [savingFirstMessage, setSavingFirstMessage] = useState(false);
  const [savingSystemPrompt, setSavingSystemPrompt] = useState(false);

  // Editable Voice / Language Settings State
  const [selectedLanguage, setSelectedLanguage] = useState('English (Indian)|en-IN');
  const [selectedVoiceGender, setSelectedVoiceGender] = useState('female');
  const [savingVoiceSettings, setSavingVoiceSettings] = useState(false);

  // Smart Column Proposer State
  const [proposedColumns, setProposedColumns] = useState([]);
  const [loadingColumns, setLoadingColumns] = useState(false);
  const [newColumnText, setNewColumnText] = useState('');

  // Columns Editor State for Selected Sheet
  const [activeColumns, setActiveColumns] = useState([]);
  const [originalColumns, setOriginalColumns] = useState([]);
  const [updatingColumns, setUpdatingColumns] = useState(false);
  const [newActiveColText, setNewActiveColText] = useState('');

  // Call / Active Lead State
  const [activeLead, setActiveLead] = useState(null);
  const [callDuration, setCallDuration] = useState(0);
  const timerRef = useRef(null);
  const scrollRef = useRef(null);

  // Initialize voice stream hook
  const {
    connect,
    disconnect,
    isConnected,
    isSpeaking,
    isListening,
    transcripts,
    error,
  } = useVoiceStream(id, {
    ...(activeLead ? {
      spreadsheetId: activeLead.spreadsheetId,
      sheetName: activeLead.sheetName,
      leadRow: activeLead.leadRow
    } : {}),
    onCallTransfer: (toPhone) => {
      alert(`[Call Transfer] Agent initiated call transfer to live representative at ${toPhone}. Browser session ending.`);
      disconnect();
    }
  });

  const fetchCampaigns = async () => {
    setLoadingCampaigns(true);
    try {
      const res = await authFetch(`http://localhost:8000/api/campaigns?agent_id=${id}`);
      const data = await res.json();
      setCampaigns(data.campaigns || []);
    } catch (err) {
      console.error('Failed to fetch campaigns:', err);
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const handleCreateCampaign = async (e) => {
    e.preventDefault();
    if (!campName.trim()) {
      alert('Please enter a campaign name');
      return;
    }
    const isOutbound = agent.type === 'outbound';
    try {
      const res = await authFetch('http://localhost:8000/api/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: campName,
          agent_id: id,
          campaign_type: isOutbound ? 'outbound' : 'inbound',
          spreadsheet_id: isOutbound ? (campSpreadsheetId || null) : null,
          sheet_name: isOutbound ? (campSheetName || null) : null,
          start_time: campStartTime || '09:00',
          end_time: campEndTime || '18:00',
          max_concurrent_calls: parseInt(campMaxConcurrency) || 1,
          retry_count: isOutbound ? parseInt(campRetryCount) || 0 : 0,
          retry_delay_minutes: isOutbound ? parseInt(campRetryDelay) || 15 : 15,
          call_order: isOutbound ? campCallOrder : 'sequential',
          after_hours_action: !isOutbound ? campAfterHoursAction : 'none',
          after_hours_message: !isOutbound ? campAfterHoursMessage : '',
          after_hours_transfer_number: !isOutbound ? campAfterHoursTransferNumber : '',
        })
      });
      const data = await res.json();
      if (data.success) {
        const msg = isOutbound 
          ? `Campaign launched! ${data.leads_imported} leads imported from your connected sheet.`
          : 'Availability configuration saved successfully!';
        alert(msg);
        setCampName('');
        setCampSpreadsheetId('');
        setCampSheetName('');
        setCampStartTime('09:00');
        setCampEndTime('18:00');
        setCampMaxConcurrency(1);
        setCampRetryCount(0);
        setCampRetryDelay(15);
        setCampCallOrder('sequential');
        setCampAfterHoursAction('none');
        setCampAfterHoursMessage('');
        setCampAfterHoursTransferNumber('');
        setShowCreateCamp(false);
        fetchCampaigns();
      } else {
        alert('Failed to create campaign: ' + (data.detail || 'Unknown error'));
      }
    } catch (err) {
      console.error('Error creating campaign:', err);
      alert('Error creating campaign');
    }
  };

  const handleStartCampaign = async (campId) => {
    try {
      const res = await authFetch(`http://localhost:8000/api/campaigns/${campId}/start`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        fetchCampaigns();
      }
    } catch (err) {
      console.error('Error starting campaign:', err);
    }
  };

  const handlePauseCampaign = async (campId) => {
    try {
      const res = await authFetch(`http://localhost:8000/api/campaigns/${campId}/pause`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        fetchCampaigns();
      }
    } catch (err) {
      console.error('Error pausing campaign:', err);
    }
  };

  const fetchCampaignLeads = async (campId) => {
    setLoadingCampLeads(true);
    try {
      const res = await authFetch(`http://localhost:8000/api/campaigns/${campId}/leads`);
      const data = await res.json();
      setCampLeads(data.leads || []);
    } catch (err) {
      console.error('Error fetching campaign leads:', err);
    } finally {
      setLoadingCampLeads(false);
    }
  };

  const fetchKnowledgeBase = async () => {
    setLoadingKb(true);
    try {
      const res = await authFetch(`http://localhost:8000/api/knowledge-base?agent_id=${id}`);
      const data = await res.json();
      setKbFiles(data.documents || []);
    } catch (err) {
      console.error('Failed to fetch knowledge base:', err);
    } finally {
      setLoadingKb(false);
    }
  };

  const handleUploadKBFile = (e) => {
    e.preventDefault();
    if (!fileToUpload) {
      alert('Please select a file to upload first.');
      return;
    }
    
    setUploadingKb(true);
    setUploadProgress(0);
    const formData = new FormData();
    formData.append('agent_id', id);
    formData.append('file', fileToUpload);

    const xhr = new XMLHttpRequest();
    
    // Track upload progress
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        const percentComplete = Math.round((event.loaded / event.total) * 100);
        setUploadProgress(percentComplete);
      }
    });

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          if (data.success) {
            alert('File uploaded and indexed successfully!');
            setFileToUpload(null);
            const fileInput = document.getElementById('kb-file-input');
            if (fileInput) fileInput.value = '';
            fetchKnowledgeBase();
          } else {
            alert('Upload failed: ' + (data.detail || 'Unknown error'));
          }
        } catch (e) {
          alert('Upload failed: Invalid response from server');
        }
      } else {
        alert('Upload failed: Server error ' + xhr.status);
      }
      setUploadingKb(false);
      setUploadProgress(0);
    };

    xhr.onerror = () => {
      alert('Error uploading file');
      setUploadingKb(false);
      setUploadProgress(0);
    };

    xhr.open('POST', 'http://localhost:8000/api/knowledge-base/upload');
    
    const token = localStorage.getItem('supabase_token');
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    
    xhr.send(formData);
  };

  const handleDeleteKBFile = async (fileId) => {
    if (!confirm('Are you sure you want to delete this document from the agent\'s knowledge base?')) return;
    try {
      const res = await authFetch(`http://localhost:8000/api/knowledge-base/${fileId}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (data.success) {
        alert('Document deleted successfully.');
        fetchKnowledgeBase();
      } else {
        alert('Failed to delete document.');
      }
    } catch (err) {
      console.error('Error deleting KB file:', err);
    }
  };

  useEffect(() => {
    if (leftTab === 'campaign') {
      fetchCampaigns();
    }
  }, [leftTab, id]);

  useEffect(() => {
    if (leftTab === 'knowledge_base') {
      fetchKnowledgeBase();
    }
  }, [leftTab, id]);

  useEffect(() => {
    if (selectedCampaign) {
      fetchCampaignLeads(selectedCampaign.id);
      
      let interval = null;
      if (selectedCampaign.status === 'active') {
        interval = setInterval(() => {
          fetchCampaignLeads(selectedCampaign.id);
          authFetch(`http://localhost:8000/api/campaigns?agent_id=${id}`)
            .then(res => res.json())
            .then(data => {
              setCampaigns(data.campaigns || []);
              const updated = (data.campaigns || []).find(c => c.id === selectedCampaign.id);
              if (updated) setSelectedCampaign(updated);
            });
        }, 5000);
      }
      return () => {
        if (interval) clearInterval(interval);
      };
    }
  }, [selectedCampaign, id]);

  // Fetch Agent details & Google authentication status
  
  const loadTwilioSettings = () => {
    setLoadingTwilio(true);
    authFetch('http://localhost:8000/api/settings/twilio')
      .then(res => res.json())
      .then(data => {
        setTwilioSid(data.twilio_account_sid || '');
        setTwilioToken(data.twilio_auth_token || '');
        setTwilioPhone(data.twilio_phone_number || '');
        setLoadingTwilio(false);
      })
      .catch(err => {
        console.error('Failed to load Twilio settings:', err);
        setLoadingTwilio(false);
      });
  };

  const handleSaveTwilioSettings = async (e) => {
    e.preventDefault();
    setSavingTwilio(true);
    try {
      const res = await authFetch('http://localhost:8000/api/settings/twilio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          twilio_account_sid: twilioSid,
          twilio_auth_token: twilioToken,
          twilio_phone_number: twilioPhone
        })
      });
      const data = await res.json();
      if (data.success) {
        alert('Twilio settings saved successfully!');
        loadTwilioSettings();
      } else {
        alert('Failed to save Twilio settings: ' + (data.message || data.detail || 'Unknown error'));
      }
    } catch (err) {
      console.error('Failed to save Twilio settings:', err);
      alert('Error saving settings');
    } finally {
      setSavingTwilio(false);
    }
  };

  const triggerOutboundCall = async (phoneNum, leadRow = null) => {
    const toPhone = phoneNum || targetPhoneNumber;
    if (!toPhone) {
      alert('Please specify a destination phone number.');
      return;
    }
    setDialingStatus('calling');
    try {
      const payload = {
        agent_id: id,
        to_phone: toPhone,
        spreadsheet_id: sheetsId,
        sheet_name: sheetsName,
        lead_row: leadRow
      };
      
      const res = await authFetch('http://localhost:8000/api/telephony/call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      if (data.success) {
        setActiveCallSid(data.call_sid);
        setDialingStatus('ringing');
        alert(`Outbound call placed successfully! Call SID: ${data.call_sid}`);
      } else {
        setDialingStatus('failed');
        alert('Failed to place outbound call: ' + (data.detail || 'Unknown error'));
      }
    } catch (err) {
      setDialingStatus('failed');
      console.error('Telephony dial error:', err);
      alert('Error placing Twilio call');
    }
  };

  const loadAgent = () => {
    setLoading(true);
    authFetch(`http://localhost:8000/api/agents/${id}`)
      .then((res) => res.json())
      .then((data) => {
        const a = data.agent;
        setAgent(a);
        
        // Sync toggles and settings
        setCalendarEnabled(a.google_calendar_enabled || false);
        setCalendarId(a.google_calendar_id || 'primary');
        setMeetEnabled(a.google_meet_enabled || false);
        setEmailNotificationsEnabled(a.email_notifications_enabled || false);
        setEmailIntegrationEnabled(a.email_integration_enabled || false);
        setEmailIntegrationInstructions(a.email_integration_instructions || '');
        setSheetsEnabled(a.google_sheets_enabled || false);
        setSheetsId(a.google_sheets_id || '');
        setSheetsName(a.google_sheets_name || '');
        setIntegrationInstructions(a.google_integration_instructions || '');
        setWhatsappEnabled(a.whatsapp_enabled || false);
        setWhatsappPhoneNumberId(a.whatsapp_phone_number_id || '');
        setWhatsappWabaId(a.whatsapp_waba_id || '');
        setWhatsappAccessToken(a.whatsapp_access_token || '');
        setWhatsappTemplateName(a.whatsapp_template_name || 'hello_world');
        setWhatsappTemplateLanguage(a.whatsapp_template_language || 'en_US');
        setWhatsappIntegrationInstructions(a.whatsapp_integration_instructions || '');
        setLiveTransferEnabled(a.live_transfer_enabled || false);
        setLiveTransferNumber(a.live_transfer_number || '');
        setFirstMessage(a.first_message || '');
        setSystemPrompt(a.system_prompt || '');
        setSelectedLanguage(a.language || 'English (Indian)|en-IN');
        setSelectedVoiceGender(a.voice_gender || 'female');
        
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadAgent();
    loadTwilioSettings();

    authFetch('http://localhost:8000/api/google/status')
      .then((res) => res.json())
      .then((data) => {
        setGoogleStatus(data);
      })
      .catch((err) => console.error('Google status fetch error:', err));
  }, [id]);

  // Load integration resources (calendars/sheets) dynamically
  useEffect(() => {
    if (googleStatus.authenticated) {
      if (calendarEnabled && calendars.length === 0) {
        setLoadingCalendars(true);
        authFetch('http://localhost:8000/api/google/calendars')
          .then((res) => res.json())
          .then((data) => {
            setCalendars(data.calendars || []);
            setLoadingCalendars(false);
          })
          .catch((err) => {
            console.error('Failed to load calendars', err);
            setLoadingCalendars(false);
          });
      }

      if (sheetsEnabled && spreadsheets.length === 0) {
        setLoadingSheets(true);
        authFetch('http://localhost:8000/api/google/sheets')
          .then((res) => res.json())
          .then((data) => {
            setSpreadsheets(data.spreadsheets || []);
            setLoadingSheets(false);
          })
          .catch((err) => {
            console.error('Failed to load sheets', err);
            setLoadingSheets(false);
          });
      }
    }
  }, [googleStatus.authenticated, calendarEnabled, sheetsEnabled]);

  // Fetch sheet tabs when selected sheet changes
  useEffect(() => {
    if (sheetsId && googleStatus.authenticated) {
      setLoadingTabs(true);
      authFetch(`http://localhost:8000/api/google/sheets/${sheetsId}/sheets`)
        .then((res) => res.json())
        .then((data) => {
          setSheetTabs(data.sheets || []);
          setLoadingTabs(false);
        })
        .catch((err) => {
          console.error('Failed to load sheet tabs', err);
          setLoadingTabs(false);
        });
    } else {
      setSheetTabs([]);
    }
  }, [sheetsId, googleStatus.authenticated]);

  // Fetch lead data rows when sheet selection stabilizes
  const fetchLeadData = () => {
    if (sheetsId && sheetsName && googleStatus.authenticated) {
      setLoadingLeads(true);
      authFetch(`http://localhost:8000/api/google/sheets/${sheetsId}/${sheetsName}/data`)
        .then((res) => res.json())
        .then((data) => {
          setLeads(data.data || []);
          setLoadingLeads(false);
        })
        .catch((err) => {
          console.error('Failed to load leads data', err);
          setLoadingLeads(false);
        });
    } else {
      setLeads([]);
    }
  };

  useEffect(() => {
    fetchLeadData();
  }, [sheetsId, sheetsName, googleStatus.authenticated]);

  const fetchAnalytics = () => {
    setLoadingAnalytics(true);
    authFetch(`http://localhost:8000/api/analytics?agent_id=${id}`)
      .then(res => res.json())
      .then(data => {
        setAnalytics(data);
        setLoadingAnalytics(false);
      })
      .catch(err => {
        console.error('Failed to fetch analytics:', err);
        setLoadingAnalytics(false);
      });
      
    authFetch(`http://localhost:8000/api/calls?agent_id=${id}`)
      .then(res => res.json())
      .then(data => {
        setCalls(data.calls || []);
      })
      .catch(err => console.error('Failed to fetch calls:', err));
  };

  useEffect(() => {
    if (leftTab === 'analytics') {
      fetchAnalytics();
    }
  }, [leftTab]);

  // Fetch active column headers when spreadsheet and tab are selected
  useEffect(() => {
    if (sheetsId && sheetsName && googleStatus.authenticated) {
      authFetch(`http://localhost:8000/api/google/sheets/${sheetsId}/${sheetsName}/columns`)
        .then((res) => {
          if (!res.ok) throw new Error('Failed to fetch columns');
          return res.json();
        })
        .then((data) => {
          setActiveColumns(data.columns || []);
          setOriginalColumns(data.columns || []);
        })
        .catch((err) => {
          console.error('Error fetching sheet columns:', err);
          setActiveColumns([]);
          setOriginalColumns([]);
        });
    } else {
      setActiveColumns([]);
      setOriginalColumns([]);
    }
  }, [sheetsId, sheetsName, googleStatus.authenticated]);

  // Timer logic for call duration
  useEffect(() => {
    if (isConnected) {
      setCallDuration(0);
      timerRef.current = setInterval(() => {
        setCallDuration((d) => d + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      // Auto refresh leads table after call ends to fetch status changes
      if (activeLead) {
        setTimeout(() => {
          fetchLeadData();
          fetchAnalytics();
          setActiveLead(null);
        }, 2000);
      } else {
        setTimeout(() => {
          fetchAnalytics();
        }, 2000);
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isConnected]);

  // Auto-scroll transcript window
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcripts]);

  // Save Config Changes
  const handleSaveConfig = async () => {
    setSavingConfig(true);
    try {
      const payload = {
        google_calendar_enabled: calendarEnabled,
        google_calendar_id: calendarId,
        google_meet_enabled: meetEnabled,
        email_notifications_enabled: emailNotificationsEnabled,
        email_integration_enabled: emailIntegrationEnabled,
        email_integration_instructions: emailIntegrationInstructions,
        google_sheets_enabled: sheetsEnabled,
        google_sheets_id: sheetsId,
        google_sheets_name: sheetsName,
        google_integration_instructions: integrationInstructions,
        first_message: firstMessage,
        system_prompt: systemPrompt,
        whatsapp_enabled: whatsappEnabled,
        whatsapp_phone_number_id: whatsappPhoneNumberId,
        whatsapp_waba_id: whatsappWabaId,
        whatsapp_access_token: whatsappAccessToken,
        whatsapp_template_name: whatsappTemplateName,
        whatsapp_template_language: whatsappTemplateLanguage,
        whatsapp_integration_instructions: whatsappIntegrationInstructions,
        live_transfer_enabled: liveTransferEnabled,
        live_transfer_number: liveTransferNumber,
      };

      const res = await authFetch(`http://localhost:8000/api/agents/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error('Failed to update config');
      const data = await res.json();
      setAgent(data.agent);
      alert('Integration settings saved successfully!');
    } catch (err) {
      console.error(err);
      alert('Failed to save settings: ' + err.message);
    } finally {
      setSavingConfig(false);
    }
  };

  // Save First Message separately
  const handleSaveFirstMessage = async () => {
    setSavingFirstMessage(true);
    try {
      const res = await authFetch(`http://localhost:8000/api/agents/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ first_message: firstMessage }),
      });
      if (!res.ok) throw new Error('Failed to update first message');
      const data = await res.json();
      setAgent(data.agent);
      alert('First message saved successfully!');
    } catch (err) {
      console.error(err);
      alert('Failed to save first message: ' + err.message);
    } finally {
      setSavingFirstMessage(false);
    }
  };

  // Save System Instructions separately
  const handleSaveSystemPrompt = async () => {
    setSavingSystemPrompt(true);
    try {
      const res = await authFetch(`http://localhost:8000/api/agents/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_prompt: systemPrompt }),
      });
      if (!res.ok) throw new Error('Failed to update system instructions');
      const data = await res.json();
      setAgent(data.agent);
      alert('System instructions saved successfully!');
    } catch (err) {
      console.error(err);
      alert('Failed to save system instructions: ' + err.message);
    } finally {
      setSavingSystemPrompt(false);
    }
  };

  // Save Voice & Language settings
  const handleSaveVoiceSettings = async () => {
    setSavingVoiceSettings(true);
    try {
      const res = await authFetch(`http://localhost:8000/api/agents/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          language: selectedLanguage,
          voice_gender: selectedVoiceGender,
        }),
      });
      if (!res.ok) throw new Error('Failed to update voice settings');
      const data = await res.json();
      setAgent(data.agent);
      alert('Voice and language settings saved successfully!');
    } catch (err) {
      console.error(err);
      alert('Failed to save voice settings: ' + err.message);
    } finally {
      setSavingVoiceSettings(false);
    }
  };

  // AI-Powered column proposal for smart sheet creation
  const handleProposeColumns = async () => {
    setLoadingColumns(true);
    try {
      const res = await authFetch('http://localhost:8000/api/google/sheets/propose-columns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_prompt: agent.system_prompt || '',
          integration_instructions: integrationInstructions,
          agent_type: agent.type,
        }),
      });
      const data = await res.json();
      setProposedColumns(data.columns || ['Name', 'Phone', 'Status', 'Notes']);
    } catch (err) {
      console.error(err);
      setProposedColumns(['Name', 'Phone', 'Status', 'Notes']);
    } finally {
      setLoadingColumns(false);
    }
  };

  // Save modifications to the active spreadsheet's column headers
  const handleUpdateSheetColumns = async () => {
    if (activeColumns.length === 0) return;
    setUpdatingColumns(true);
    try {
      const res = await authFetch(`http://localhost:8000/api/google/sheets/${sheetsId}/${sheetsName}/columns`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ columns: activeColumns }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to update sheet columns.');
      }
      setOriginalColumns([...activeColumns]);
      alert('Columns updated successfully on the Google Sheet!');
      fetchLeadData(); // refresh table with new headers
    } catch (err) {
      console.error(err);
      alert('Error updating columns: ' + err.message);
    } finally {
      setUpdatingColumns(false);
    }
  };

  // Create sheet with user-approved custom columns
  const handleCreateCustomSheet = async () => {
    if (proposedColumns.length === 0) return;
    setCreatingTemplate(true);
    try {
      const res = await authFetch('http://localhost:8000/api/google/sheets/create-custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ columns: proposedColumns }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Sheet creation failed.');
      }
      const data = await res.json();

      // Refresh sheets list
      const sheetsRes = await authFetch('http://localhost:8000/api/google/sheets');
      const sheetsData = await sheetsRes.json();
      setSpreadsheets(sheetsData.spreadsheets || []);

      setSheetsId(data.id);
      setSheetsName('Leads');
      setProposedColumns([]);
      alert(`Created sheet "${data.name}" with custom columns!`);
    } catch (err) {
      console.error(err);
      alert('Error creating sheet: ' + err.message);
    } finally {
      setCreatingTemplate(false);
    }
  };

  // Handle Call Specific Lead Row
  const handleCallLead = (lead) => {
    if (isConnected) return;
    const callOptions = {
      spreadsheetId: agent.google_sheets_id || sheetsId,
      sheetName: agent.google_sheets_name || sheetsName,
      leadRow: lead.__row__,
    };
    setActiveLead({
      spreadsheetId: callOptions.spreadsheetId,
      sheetName: callOptions.sheetName,
      leadRow: callOptions.leadRow,
      name: lead.Name || lead.name || 'Customer',
    });
    connect(callOptions);
  };

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  if (loading) {
    return (
      <div className="page-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Loader2 className="spin-active" size={32} style={{ color: 'var(--accent)' }} />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="page-container" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100vh', gap: '1.5rem', textAlign: 'center' }}>
        <Activity size={48} style={{ color: '#ef4444' }} />
        <div>
          <h2 style={{ marginBottom: '0.5rem' }}>Failed to Load Agent</h2>
          <p style={{ color: 'var(--text-secondary)', maxWidth: 400 }}>
            Unable to communicate with the backend server. Please make sure the backend server is running and reload the page.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>
          Retry Connection
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

      {/* ─── LEFT PANEL: Agent Config, Integrations & Leads Table ─── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--border)', overflowY: 'auto' }}>
        
        {/* Top Header */}
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '0.75rem', backgroundColor: 'var(--bg-secondary)' }}>
          <button className="btn-ghost" onClick={() => navigate('/dashboard')} style={{ padding: '0.5rem' }}>
            <ArrowLeft size={18} />
          </button>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600 }}>{agent.name}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ID: {agent.id}</div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <span className="badge" style={{ backgroundColor: 'var(--accent-transparent)', color: 'var(--accent)' }}>{agent.type}</span>
            <span className="badge">{agent.language.split('|')[0]}</span>
          </div>
        </div>

        {/* Tab Selection */}
        <div style={{ display: 'flex', flexWrap: 'wrap', borderBottom: '1px solid var(--border)', backgroundColor: 'var(--bg-secondary)', padding: '0 0.75rem', gap: '0' }}>
          {[
            { key: 'settings', label: 'Integrations' },
            { key: 'campaign', label: 'Campaign' },
            { key: 'knowledge_base', label: 'Knowledge Base' },
            { key: 'analytics', label: 'Analytics' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setLeftTab(tab.key)}
              style={{
                padding: '0.65rem 0.75rem',
                fontWeight: 600,
                fontSize: '0.8rem',
                color: leftTab === tab.key ? 'var(--accent)' : 'var(--text-secondary)',
                borderBottom: leftTab === tab.key ? '2px solid var(--accent)' : '2px solid transparent',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                transition: 'all 0.2s',
                whiteSpace: 'nowrap',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {leftTab === 'settings' && (
          /* Dashboard Content */
          <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Section 1: Dynamic Integrations Setup */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '1.5rem',
            backdropFilter: 'blur(5px)',
          }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Calendar size={18} style={{ color: 'var(--accent)' }} />
              Google App Integrations
            </h3>

            {!googleStatus.authenticated ? (
              <div style={{ padding: '1rem', textAlign: 'center', border: '1px dashed var(--border)', borderRadius: '6px' }}>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  Connect your Google Account to authorize Calendar and Sheets tool usage.
                </p>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={async () => {
                    const res = await authFetch('http://localhost:8000/api/google/auth-url');
                    const d = await res.json();
                    if (d.auth_url) window.location.href = d.auth_url;
                  }}
                >
                  Connect Google Account
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                
                {/* Google Calendar Row */}
                <div style={{ paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 500, fontSize: '0.9rem' }}>
                    <input
                      type="checkbox"
                      checked={calendarEnabled}
                      onChange={(e) => setCalendarEnabled(e.target.checked)}
                      style={{ cursor: 'pointer' }}
                    />
                    Enable Google Calendar booking
                  </label>
                  {calendarEnabled && (
                    <div style={{ marginTop: '0.75rem', paddingLeft: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      <div>
                        <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem' }}>
                          Target Calendar
                        </label>
                        {loadingCalendars ? (
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}><Loader2 size={12} className="spin-active inline" /> Loading calendars...</div>
                        ) : (
                          <select
                            className="input"
                            value={calendarId}
                            onChange={(e) => setCalendarId(e.target.value)}
                            style={{ maxWidth: '360px', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
                          >
                            {calendars.map((cal) => (
                              <option key={cal.id} value={cal.id}>
                                {cal.summary} {cal.primary ? '(Primary)' : ''}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>

                      <div>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          <input
                            type="checkbox"
                            checked={meetEnabled}
                            onChange={(e) => setMeetEnabled(e.target.checked)}
                            style={{ cursor: 'pointer' }}
                          />
                          Create Google Meet link for online appointments
                        </label>
                      </div>

                      <div>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          <input
                            type="checkbox"
                            checked={emailNotificationsEnabled}
                            onChange={(e) => setEmailNotificationsEnabled(e.target.checked)}
                            style={{ cursor: 'pointer' }}
                          />
                          Send confirmation email via Gmail after scheduling
                        </label>
                      </div>

                      {emailNotificationsEnabled && googleStatus.scopes && !googleStatus.scopes.includes("https://www.googleapis.com/auth/gmail.send") && (
                        <div style={{
                          marginTop: '0.25rem',
                          padding: '0.75rem',
                          backgroundColor: '#f59e0b15',
                          border: '1px solid #f59e0b50',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.8rem',
                          color: '#d97706',
                          lineHeight: 1.5,
                          maxWidth: '480px',
                        }}>
                          ⚠️ <strong>Gmail permissions missing</strong>: Please click <strong>Connect Google Account</strong> above to authorize sending emails.
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Email Follow-up Integration Row */}
                <div style={{ paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 500, fontSize: '0.9rem' }}>
                    <input
                      type="checkbox"
                      checked={emailIntegrationEnabled}
                      onChange={(e) => setEmailIntegrationEnabled(e.target.checked)}
                      style={{ cursor: 'pointer' }}
                    />
                    Enable Email Follow-up Integration
                  </label>
                  {emailIntegrationEnabled && (
                    <div style={{ marginTop: '0.75rem', paddingLeft: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.35rem' }}>
                          <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
                            Email Follow-up Instructions
                          </label>
                          <HelpCircle size={12} style={{ color: 'var(--text-muted)' }} title="Describe when to send emails and what the subject/body should be based on the call outcome." />
                        </div>
                        <textarea
                          className="input"
                          style={{
                            minHeight: '80px',
                            fontSize: '0.8rem',
                            lineHeight: 1.5,
                            backgroundColor: 'var(--bg-primary)',
                            maxWidth: '480px',
                          }}
                          placeholder="e.g. 'If the client asks for pricing or a brochure, send a brochure link (example.com/brochure.pdf). Otherwise, send a polite thank you email.'"
                          value={emailIntegrationInstructions}
                          onChange={(e) => setEmailIntegrationInstructions(e.target.value)}
                        />
                      </div>

                      {googleStatus.scopes && !googleStatus.scopes.includes("https://www.googleapis.com/auth/gmail.send") && (
                        <div style={{
                          marginTop: '0.25rem',
                          padding: '0.75rem',
                          backgroundColor: '#f59e0b15',
                          border: '1px solid #f59e0b50',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.8rem',
                          color: '#d97706',
                          lineHeight: 1.5,
                          maxWidth: '480px',
                        }}>
                          ⚠️ <strong>Gmail permissions missing</strong>: Please click <strong>Connect Google Account</strong> above to authorize sending emails.
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Google Sheets Row */}
                <div style={{ paddingBottom: '0.5rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 500, fontSize: '0.9rem' }}>
                    <input
                      type="checkbox"
                      checked={sheetsEnabled}
                      onChange={(e) => setSheetsEnabled(e.target.checked)}
                      style={{ cursor: 'pointer' }}
                    />
                    Enable Google Sheets CRM integration (Lead qualification / Data logging)
                  </label>
                  {sheetsEnabled && (
                    <div style={{ marginTop: '0.75rem', paddingLeft: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      
                      {/* Select Spreadsheet */}
                      <div>
                        <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem' }}>
                          Select Spreadsheet
                        </label>
                        {loadingSheets ? (
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}><Loader2 size={12} className="spin-active inline" /> Loading sheets...</div>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: '480px' }}>
                            <select
                              className="input"
                              value={sheetsId}
                              onChange={(e) => setSheetsId(e.target.value)}
                              style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
                            >
                              <option value="">-- Choose Spreadsheet --</option>
                              {spreadsheets.map((sheet) => (
                                <option key={sheet.id} value={sheet.id}>
                                  {sheet.name}
                                </option>
                              ))}
                            </select>
                            {/* Smart Sheet Creator — only for inbound/support agents */}
                            {agent.type !== 'outbound' && (
                              <div>
                                {proposedColumns.length === 0 ? (
                                  <button
                                    className="btn btn-secondary btn-sm"
                                    style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.4rem 0.75rem' }}
                                    onClick={handleProposeColumns}
                                    disabled={loadingColumns}
                                  >
                                    {loadingColumns ? <Loader2 size={14} className="spin-active" /> : <Plus size={14} />}
                                    {loadingColumns ? 'Generating Columns...' : '+ Create New Sheet'}
                                  </button>
                                ) : (
                                  <div style={{
                                    padding: '1rem',
                                    backgroundColor: 'var(--bg-tertiary)',
                                    border: '1px solid var(--border)',
                                    borderRadius: 'var(--radius-sm)',
                                  }}>
                                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                                      Proposed Columns (click × to remove, type to add)
                                    </div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.75rem' }}>
                                      {proposedColumns.map((col, i) => (
                                        <span
                                          key={i}
                                          onClick={() => setProposedColumns(prev => prev.filter((_, idx) => idx !== i))}
                                          style={{
                                            padding: '0.3rem 0.6rem',
                                            backgroundColor: 'var(--accent-transparent)',
                                            color: 'var(--accent)',
                                            borderRadius: '12px',
                                            fontSize: '0.8rem',
                                            fontWeight: 500,
                                            cursor: 'pointer',
                                            border: '1px solid var(--accent)',
                                            transition: 'opacity 0.15s',
                                          }}
                                          title="Click to remove"
                                        >
                                          {col} ×
                                        </span>
                                      ))}
                                    </div>
                                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                                      <input
                                        className="input"
                                        type="text"
                                        placeholder="Add column..."
                                        value={newColumnText}
                                        onChange={e => setNewColumnText(e.target.value)}
                                        onKeyDown={e => {
                                          if (e.key === 'Enter' && newColumnText.trim()) {
                                            setProposedColumns(prev => [...prev, newColumnText.trim()]);
                                            setNewColumnText('');
                                          }
                                        }}
                                        style={{ flex: 1, padding: '0.35rem 0.6rem', fontSize: '0.8rem' }}
                                      />
                                      <button
                                        className="btn btn-secondary btn-sm"
                                        onClick={() => {
                                          if (newColumnText.trim()) {
                                            setProposedColumns(prev => [...prev, newColumnText.trim()]);
                                            setNewColumnText('');
                                          }
                                        }}
                                        style={{ padding: '0.35rem 0.6rem' }}
                                      >
                                        <Plus size={14} />
                                      </button>
                                    </div>
                                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                                      <button
                                        className="btn btn-primary btn-sm"
                                        onClick={handleCreateCustomSheet}
                                        disabled={creatingTemplate || proposedColumns.length === 0}
                                        style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                                      >
                                        {creatingTemplate ? <Loader2 size={14} className="spin-active" /> : <FileSpreadsheet size={14} />}
                                        Create Sheet with These Columns
                                      </button>
                                      <button
                                        className="btn btn-ghost btn-sm"
                                        onClick={() => setProposedColumns([])}
                                      >
                                        Cancel
                                      </button>
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Select Sheet Tab */}
                      {sheetsId && (
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem' }}>
                            Select Sheet Tab (Table Name)
                          </label>
                          {loadingTabs ? (
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}><Loader2 size={12} className="spin-active" /> Loading tabs...</div>
                          ) : (
                            <select
                              className="input"
                              value={sheetsName}
                              onChange={(e) => setSheetsName(e.target.value)}
                              style={{ maxWidth: '360px', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
                            >
                              <option value="">-- Choose Sheet Tab --</option>
                              {sheetTabs.map((tab) => (
                                <option key={tab} value={tab}>
                                  {tab}
                                </option>
                              ))}
                            </select>
                          )}
                        </div>
                      )}

                      {/* Column Manager for the Selected Sheet */}
                      {sheetsId && sheetsName && (
                        <div style={{
                          padding: '1rem',
                          backgroundColor: 'var(--bg-tertiary)',
                          border: '1px solid var(--border)',
                          borderRadius: 'var(--radius-sm)',
                          maxWidth: '480px',
                          marginTop: '0.5rem',
                        }}>
                          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            Columns in Selected Sheet (click × to remove, type to add)
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.75rem' }}>
                            {activeColumns.map((col, i) => (
                              <span
                                key={i}
                                onClick={() => setActiveColumns(prev => prev.filter((_, idx) => idx !== i))}
                                style={{
                                  padding: '0.3rem 0.6rem',
                                  backgroundColor: 'var(--accent-transparent)',
                                  color: 'var(--accent)',
                                  borderRadius: '12px',
                                  fontSize: '0.8rem',
                                  fontWeight: 500,
                                  cursor: 'pointer',
                                  border: '1px solid var(--accent)',
                                  transition: 'opacity 0.15s',
                                }}
                                title="Click to remove"
                              >
                                {col} ×
                              </span>
                            ))}
                          </div>
                          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                            <input
                              className="input"
                              type="text"
                              placeholder="Add column to existing sheet..."
                              value={newActiveColText}
                              onChange={e => setNewActiveColText(e.target.value)}
                              onKeyDown={e => {
                                if (e.key === 'Enter' && newActiveColText.trim()) {
                                  setActiveColumns(prev => [...prev, newActiveColText.trim()]);
                                  setNewActiveColText('');
                                }
                              }}
                              style={{ flex: 1, padding: '0.35rem 0.6rem', fontSize: '0.8rem' }}
                            />
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => {
                                if (newActiveColText.trim()) {
                                  setActiveColumns(prev => [...prev, newActiveColText.trim()]);
                                  setNewActiveColText('');
                                }
                              }}
                              style={{ padding: '0.35rem 0.6rem' }}
                            >
                              <Plus size={14} />
                            </button>
                          </div>
                          {JSON.stringify(activeColumns) !== JSON.stringify(originalColumns) && (
                            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                              <button
                                className="btn btn-ghost btn-sm"
                                onClick={() => setActiveColumns([...originalColumns])}
                                disabled={updatingColumns}
                              >
                                Cancel
                              </button>
                              <button
                                className="btn btn-primary btn-sm"
                                onClick={handleUpdateSheetColumns}
                                disabled={updatingColumns || activeColumns.length === 0}
                                style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                              >
                                {updatingColumns ? <Loader2 size={14} className="spin-active" /> : <Save size={14} />}
                                Update Sheet Columns
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Connections instructions prompt box */}
                {(calendarEnabled || sheetsEnabled) && (
                  <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.5rem' }}>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
                        What should the agent do with these connections?
                      </label>
                      <HelpCircle size={12} style={{ color: 'var(--text-muted)' }} title="Describe how the agent should use sheets and calendar. (e.g. qualify the lead and update sheets, or book appointment if they accept)" />
                    </div>
                    <textarea
                      className="input"
                      style={{
                        minHeight: '80px',
                        fontSize: '0.8rem',
                        lineHeight: 1.5,
                        backgroundColor: 'var(--bg-primary)',
                      }}
                      placeholder="e.g. 'For outbound leads in my sheet, call them to qualify their home purchasing requirements (asking Name, Budget, Location). If they qualify, set an appointment in Google Calendar and mark status as Qualified in Sheets. Otherwise, mark them Not Qualified.'"
                      value={integrationInstructions}
                      onChange={(e) => setIntegrationInstructions(e.target.value)}
                    />
                  </div>
                )}

                {/* Save Integrations Config */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                    onClick={handleSaveConfig}
                    disabled={savingConfig}
                  >
                    {savingConfig ? (
                      <Loader2 size={14} className="spin-active" />
                    ) : (
                      <Save size={14} />
                    )}
                    Save Integration Settings
                  </button>
                </div>

              </div>
            )}
          </div>

          {/* WhatsApp Business API Integration Card */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '1.5rem',
            backdropFilter: 'blur(5px)',
          }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '1.2rem' }}>💬</span>
              WhatsApp Business API Integration
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 500, fontSize: '0.9rem' }}>
                <input
                  type="checkbox"
                  checked={whatsappEnabled}
                  onChange={(e) => setWhatsappEnabled(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                Enable WhatsApp Business messaging
              </label>

              {whatsappEnabled && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', paddingLeft: '1.5rem' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                    <div>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                        Phone Number ID
                      </label>
                      <input
                        className="input"
                        type="text"
                        placeholder="e.g. 109283746561928"
                        value={whatsappPhoneNumberId}
                        onChange={(e) => setWhatsappPhoneNumberId(e.target.value)}
                        style={{ fontSize: '0.85rem', padding: '0.4rem 0.6rem' }}
                      />
                    </div>
                    
                    <div>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                        WhatsApp Business Account (WABA) ID
                      </label>
                      <input
                        className="input"
                        type="text"
                        placeholder="e.g. 987654321098765"
                        value={whatsappWabaId}
                        onChange={(e) => setWhatsappWabaId(e.target.value)}
                        style={{ fontSize: '0.85rem', padding: '0.4rem 0.6rem' }}
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                      Permanent System User Access Token
                    </label>
                    <input
                      className="input"
                      type="password"
                      placeholder="EAAG..."
                      value={whatsappAccessToken}
                      onChange={(e) => setWhatsappAccessToken(e.target.value)}
                      style={{ fontSize: '0.85rem', padding: '0.4rem 0.6rem' }}
                    />
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                    <div>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                        Approved Template Name
                      </label>
                      <input
                        className="input"
                        type="text"
                        placeholder="e.g. hello_world"
                        value={whatsappTemplateName}
                        onChange={(e) => setWhatsappTemplateName(e.target.value)}
                        style={{ fontSize: '0.85rem', padding: '0.4rem 0.6rem' }}
                      />
                    </div>

                    <div>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                        Template Language Code
                      </label>
                      <input
                        className="input"
                        type="text"
                        placeholder="e.g. en_US"
                        value={whatsappTemplateLanguage}
                        onChange={(e) => setWhatsappTemplateLanguage(e.target.value)}
                        style={{ fontSize: '0.85rem', padding: '0.4rem 0.6rem' }}
                      />
                    </div>
                  </div>

                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.35rem' }}>
                      <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>
                        WhatsApp Template Parameters Guide
                      </label>
                      <HelpCircle size={12} style={{ color: 'var(--text-muted)' }} title="Explain what information to populate in the template variables {{1}}, {{2}}, etc." />
                    </div>
                    <textarea
                      className="input"
                      style={{
                        minHeight: '80px',
                        fontSize: '0.8rem',
                        lineHeight: 1.5,
                        backgroundColor: 'var(--bg-primary)',
                      }}
                      placeholder="e.g. 'Parameter {{1}} is the customer's name. Parameter {{2}} is the confirmed appointment date and time. Parameter {{3}} is the Google Meet link.'"
                      value={whatsappIntegrationInstructions}
                      onChange={(e) => setWhatsappIntegrationInstructions(e.target.value)}
                    />
                  </div>
                </div>
              )}

              {/* Show save button if modified */}
              {(whatsappEnabled !== (agent.whatsapp_enabled || false) ||
                whatsappPhoneNumberId !== (agent.whatsapp_phone_number_id || '') ||
                whatsappWabaId !== (agent.whatsapp_waba_id || '') ||
                whatsappAccessToken !== (agent.whatsapp_access_token || '') ||
                whatsappTemplateName !== (agent.whatsapp_template_name || 'hello_world') ||
                whatsappTemplateLanguage !== (agent.whatsapp_template_language || 'en_US') ||
                whatsappIntegrationInstructions !== (agent.whatsapp_integration_instructions || '')) && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }} className="animate-fade-in">
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
                    onClick={() => {
                      setWhatsappEnabled(agent.whatsapp_enabled || false);
                      setWhatsappPhoneNumberId(agent.whatsapp_phone_number_id || '');
                      setWhatsappWabaId(agent.whatsapp_waba_id || '');
                      setWhatsappAccessToken(agent.whatsapp_access_token || '');
                      setWhatsappTemplateName(agent.whatsapp_template_name || 'hello_world');
                      setWhatsappTemplateLanguage(agent.whatsapp_template_language || 'en_US');
                      setWhatsappIntegrationInstructions(agent.whatsapp_integration_instructions || '');
                    }}
                    disabled={savingConfig}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    onClick={handleSaveConfig}
                    disabled={savingConfig}
                  >
                    {savingConfig ? <Loader2 size={12} className="spin-active" /> : <Save size={12} />}
                    Save WhatsApp Settings
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Live Agent Escalation / Call Transfer Card */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '1.5rem',
            backdropFilter: 'blur(5px)',
          }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '1.2rem' }}>📞</span>
              Live Agent Escalation (Transfer Call)
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 500, fontSize: '0.9rem' }}>
                <input
                  type="checkbox"
                  checked={liveTransferEnabled}
                  onChange={(e) => setLiveTransferEnabled(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                Enable Live Agent Transfer
              </label>

              {liveTransferEnabled && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', paddingLeft: '1.5rem' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                      Transfer Destination Phone Number
                    </label>
                    <input
                      className="input"
                      type="text"
                      placeholder="e.g. +919876543210 (E.164 format)"
                      value={liveTransferNumber}
                      onChange={(e) => setLiveTransferNumber(e.target.value)}
                      style={{ fontSize: '0.85rem', padding: '0.4rem 0.6rem', maxWidth: '360px' }}
                    />
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                      When the caller asks to talk to a human or manager, the AI will trigger a function to redirect the active Twilio call to this number.
                    </div>
                  </div>
                </div>
              )}

              {/* Show save button if modified */}
              {(liveTransferEnabled !== (agent.live_transfer_enabled || false) ||
                liveTransferNumber !== (agent.live_transfer_number || '')) && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }} className="animate-fade-in">
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
                    onClick={() => {
                      setLiveTransferEnabled(agent.live_transfer_enabled || false);
                      setLiveTransferNumber(agent.live_transfer_number || '');
                    }}
                    disabled={savingConfig}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    onClick={handleSaveConfig}
                    disabled={savingConfig}
                  >
                    {savingConfig ? <Loader2 size={12} className="spin-active" /> : <Save size={12} />}
                    Save Escalation Settings
                  </button>
                </div>
              )}
            </div>
          </div>

          
          {/* Twilio Telephony Integration Card */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '1.5rem',
            backdropFilter: 'blur(5px)',
          }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Phone size={18} style={{ color: 'var(--accent)' }} />
              Twilio Telephony Settings
            </h3>
            
            <form onSubmit={handleSaveTwilioSettings} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                  Twilio Account SID
                </label>
                <input
                  className="input"
                  type="text"
                  placeholder="AC..."
                  value={twilioSid}
                  onChange={(e) => setTwilioSid(e.target.value)}
                  style={{ fontSize: '0.85rem', padding: '0.4rem 0.6rem' }}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                  Twilio Auth Token
                </label>
                <input
                  className="input"
                  type="password"
                  placeholder="Insert Token..."
                  value={twilioToken}
                  onChange={(e) => setTwilioToken(e.target.value)}
                  style={{ fontSize: '0.85rem', padding: '0.4rem 0.6rem' }}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                  Twilio Outbound Phone Number (from)
                </label>
                <input
                  className="input"
                  type="text"
                  placeholder="e.g. +18776669999"
                  value={twilioPhone}
                  onChange={(e) => setTwilioPhone(e.target.value)}
                  style={{ fontSize: '0.85rem', padding: '0.4rem 0.6rem' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                <button
                  type="submit"
                  className="btn btn-primary btn-sm"
                  disabled={savingTwilio}
                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                >
                  {savingTwilio ? <Loader2 size={12} className="spin-active" /> : <Save size={12} />}
                  Save Twilio Settings
                </button>
              </div>
            </form>
          </div>

          {/* Agent Voice & Language Settings Card */}
          <div style={{
            backgroundColor: 'var(--bg-secondary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-md)',
            padding: '1.5rem',
            backdropFilter: 'blur(5px)',
          }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Volume2 size={18} style={{ color: 'var(--accent)' }} />
              Agent Voice & Language Settings
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Language Selection */}
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                  Language (Powered by Sarvam AI)
                </label>
                <select
                  className="input"
                  value={selectedLanguage}
                  onChange={(e) => setSelectedLanguage(e.target.value)}
                  style={{ maxWidth: '360px', padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
                >
                  <option value="English (Indian)|en-IN">English (Indian)</option>
                  <option value="Hinglish|hi-IN">Hinglish (Hindi/English mix)</option>
                  <option value="Hindi|hi-IN">Hindi (हिन्दी)</option>
                  <option value="Tamil|ta-IN">Tamil (தமிழ்)</option>
                  <option value="Telugu|te-IN">Telugu (తెలుగు)</option>
                  <option value="Bengali|bn-IN">Bengali (বাংলা)</option>
                  <option value="Kannada|kn-IN">Kannada (ಕನ್ನಡ)</option>
                  <option value="Malayalam|ml-IN">Malayalam (മലയാളം)</option>
                  <option value="Marathi|mr-IN">Marathi (மराठी)</option>
                  <option value="Gujarati|gu-IN">Gujarati (ગુજરાતી)</option>
                  <option value="Punjabi|pa-IN">Punjabi (ਪੰਜਾਬੀ)</option>
                  <option value="Odia|od-IN">Odia (ଓଡ଼ିଆ)</option>
                </select>
              </div>

              {/* Voice Gender Selection */}
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', letterSpacing: '0.05em' }}>
                  Voice Gender
                </label>
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.25rem' }}>
                  {['female', 'male'].map((gender) => {
                    const isSelected = selectedVoiceGender === gender;
                    return (
                      <button
                        key={gender}
                        type="button"
                        onClick={() => setSelectedVoiceGender(gender)}
                        style={{
                          padding: '0.5rem 1rem',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.85rem',
                          fontWeight: 500,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                          backgroundColor: isSelected ? 'var(--accent-transparent)' : 'var(--bg-tertiary)',
                          border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                          color: isSelected ? 'var(--accent)' : 'var(--text-primary)',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <span>{gender === 'female' ? '👩' : '👨'}</span>
                        <span>{gender.charAt(0).toUpperCase() + gender.slice(1)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Save / Cancel buttons when changed */}
              {(selectedLanguage !== agent.language || selectedVoiceGender !== agent.voice_gender) && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }} className="animate-fade-in">
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
                    onClick={() => {
                      setSelectedLanguage(agent.language);
                      setSelectedVoiceGender(agent.voice_gender);
                    }}
                    disabled={savingVoiceSettings}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    onClick={handleSaveVoiceSettings}
                    disabled={savingVoiceSettings}
                  >
                    {savingVoiceSettings ? <Loader2 size={12} className="spin-active" /> : <Save size={12} />}
                    Save Voice Settings
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Section 2: Outbound CRM Campaign Leads List */}
          {sheetsEnabled && agent.google_sheets_id && agent.google_sheets_name && (
            <div style={{
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-md)',
              padding: '1.5rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
                  <FileSpreadsheet size={18} style={{ color: '#10b981' }} />
                  Campaign Leads CRM Board
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <a
                    href={`https://docs.google.com/spreadsheets/d/${agent.google_sheets_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-secondary btn-sm"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                      padding: '0.3rem 0.65rem',
                      fontSize: '0.75rem',
                      textDecoration: 'none',
                    }}
                  >
                    <ExternalLink size={12} /> Open Sheet
                  </a>
                  <button
                    className="btn-ghost"
                    onClick={fetchLeadData}
                    disabled={loadingLeads}
                    style={{ padding: '0.35rem', borderRadius: '50%' }}
                  >
                    <RefreshCw size={14} className={loadingLeads ? 'spin-active' : ''} />
                  </button>
                </div>
              </div>

              {loadingLeads ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                  <Loader2 size={24} className="spin-active" style={{ color: 'var(--accent)' }} />
                </div>
              ) : leads.length === 0 ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                  No lead rows found in the selected sheet. Ensure headers "Name", "Phone", "Status", and "Notes" exist.
                </div>
              ) : (
                <div style={{ overflowX: 'auto', borderRadius: '6px', border: '1px solid var(--border)' }}>
                  {(() => {
                    const leadHeaders = leads.length > 0
                      ? Object.keys(leads[0]).filter(k => k !== '__row__')
                      : [];
                    const showActions = agent.type !== 'inbound';
                    return (
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
                        <thead>
                          <tr style={{ backgroundColor: 'var(--bg-tertiary)', borderBottom: '1px solid var(--border)' }}>
                            {leadHeaders.map(h => (
                              <th key={h} style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>{h}</th>
                            ))}
                            {showActions && (
                              <th style={{ padding: '0.5rem 0.75rem', fontWeight: 600, textAlign: 'center' }}>Action</th>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {leads.map((lead, idx) => {
                            const isActiveRow = activeLead && activeLead.leadRow === lead.__row__;
                            return (
                              <tr
                                key={idx}
                                style={{
                                  borderBottom: '1px solid var(--border)',
                                  backgroundColor: isActiveRow ? 'var(--accent-transparent)' : 'transparent',
                                  transition: 'background-color 0.2s',
                                }}
                              >
                                {leadHeaders.map(h => {
                                  const val = lead[h] || '—';
                                  const isStatus = h.toLowerCase() === 'status';
                                  return (
                                    <td key={h} style={{
                                      padding: '0.6rem 0.75rem',
                                      color: 'var(--text-primary)',
                                      maxWidth: '200px',
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                      whiteSpace: 'nowrap',
                                    }}>
                                      {isStatus ? (
                                        <span style={{
                                          padding: '0.2rem 0.4rem',
                                          borderRadius: '4px',
                                          fontSize: '0.7rem',
                                          fontWeight: 600,
                                          backgroundColor: val.toLowerCase().includes('qualified') && !val.toLowerCase().includes('not') ? '#10b98120' : val.toLowerCase().includes('not') ? '#ef444420' : 'var(--bg-hover)',
                                          color: val.toLowerCase().includes('qualified') && !val.toLowerCase().includes('not') ? '#10b981' : val.toLowerCase().includes('not') ? '#ef4444' : 'var(--text-primary)',
                                        }}>
                                          {val || 'New'}
                                        </span>
                                      ) : val}
                                    </td>
                                  );
                                })}
                                {showActions && (
                                  <td style={{ padding: '0.6rem 0.75rem', textAlign: 'center' }}>
                                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                                      <button
                                        className="btn btn-sm"
                                        style={{
                                          padding: '0.25rem 0.5rem',
                                          fontSize: '0.75rem',
                                          backgroundColor: isActiveRow ? 'var(--accent-transparent)' : 'var(--accent)',
                                          color: isActiveRow ? 'var(--accent)' : 'white',
                                          border: isActiveRow ? '1px solid var(--accent)' : 'none',
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: '0.25rem',
                                        }}
                                        onClick={() => handleCallLead(lead)}
                                        disabled={isConnected || dialingStatus === 'calling' || dialingStatus === 'ringing'}
                                      >
                                        {isActiveRow ? (
                                          <>
                                            <Activity size={10} className="pulse-active" /> Active
                                          </>
                                        ) : (
                                          <>
                                            <Mic size={10} /> Browser Test
                                          </>
                                        )}
                                      </button>
                                      
                                      <button
                                        className="btn btn-sm"
                                        style={{
                                          padding: '0.25rem 0.5rem',
                                          fontSize: '0.75rem',
                                          backgroundColor: dialingStatus === 'calling' || dialingStatus === 'ringing' ? 'var(--bg-hover)' : '#2563eb',
                                          color: 'white',
                                          border: 'none',
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          gap: '0.25rem',
                                        }}
                                        onClick={() => triggerOutboundCall(lead.Phone || lead.phone, lead.__row__)}
                                        disabled={isConnected || dialingStatus === 'calling' || dialingStatus === 'ringing'}
                                      >
                                        <Phone size={10} /> Call Phone
                                      </button>
                                    </div>
                                  </td>
                                )}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    );
                  })()}
                </div>
              )}
            </div>
          )}

          {/* Section 3: Base Agent Script details */}
          <div>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.05em', display: 'block', marginBottom: '0.35rem' }}>
                First Message — Agent speaks first
              </label>
              <textarea
                className="input"
                style={{
                  minHeight: '60px',
                  resize: 'vertical',
                  fontSize: '0.875rem',
                  lineHeight: 1.6,
                  backgroundColor: 'var(--bg-secondary)',
                }}
                value={firstMessage}
                onChange={(e) => setFirstMessage(e.target.value)}
              />
              {firstMessage !== (agent?.first_message || '') && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }} className="animate-fade-in">
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
                    onClick={() => setFirstMessage(agent.first_message || '')}
                    disabled={savingFirstMessage}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    onClick={handleSaveFirstMessage}
                    disabled={savingFirstMessage}
                  >
                    {savingFirstMessage ? <Loader2 size={12} className="spin-active" /> : <Save size={12} />}
                    Save First Message
                  </button>
                </div>
              )}
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.05em', display: 'block', marginBottom: '0.35rem' }}>
                Base System Instructions
              </label>
              <textarea
                className="input"
                style={{
                  minHeight: '200px',
                  resize: 'vertical',
                  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                  fontSize: '0.8rem',
                  lineHeight: 1.6,
                  backgroundColor: 'var(--bg-secondary)',
                }}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
              />
              {systemPrompt !== (agent?.system_prompt || '') && (
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }} className="animate-fade-in">
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
                    onClick={() => setSystemPrompt(agent.system_prompt || '')}
                    disabled={savingSystemPrompt}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    onClick={handleSaveSystemPrompt}
                    disabled={savingSystemPrompt}
                  >
                    {savingSystemPrompt ? <Loader2 size={12} className="spin-active" /> : <Save size={12} />}
                    Save System Instructions
                  </button>
                </div>
              )}
            </div>
          </div>

        </div>
        )}

        {/* ─── TAB: CAMPAIGN ─── */}
        {leftTab === 'campaign' && (
          <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>

            {/* ═══ OUTBOUND AGENT: Campaign Auto-Dialer ═══ */}
            {agent.type === 'outbound' ? (
              <>
                {/* Header + Create Button */}
                <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
                      <PhoneOutgoing size={18} style={{ color: '#f59e0b' }} />
                      Outbound Campaigns
                    </h3>
                    {!showCreateCamp && (
                      <button className="btn btn-sm" onClick={() => setShowCreateCamp(true)} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', backgroundColor: '#f59e0b20', color: '#f59e0b', border: '1px solid #f59e0b40', fontWeight: 600 }}>
                        <Plus size={14} /> New Campaign
                      </button>
                    )}
                  </div>

                  {/* Auto-sheet info banner */}
                  {!showCreateCamp && agent.google_sheets_enabled && agent.google_sheets_id && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 0.85rem', backgroundColor: '#10b98110', border: '1px solid #10b98130', borderRadius: '6px', marginBottom: '1rem', fontSize: '0.8rem', color: '#10b981' }}>
                      <CheckCircle size={14} />
                      Leads auto-imported from your connected Google Sheet: <strong>{agent.google_sheets_name || 'Sheet1'}</strong>
                    </div>
                  )}
                  {!showCreateCamp && (!agent.google_sheets_enabled || !agent.google_sheets_id) && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 0.85rem', backgroundColor: '#f59e0b10', border: '1px solid #f59e0b30', borderRadius: '6px', marginBottom: '1rem', fontSize: '0.8rem', color: '#f59e0b' }}>
                      <AlertCircle size={14} />
                      Connect a Google Sheet in the <strong>Integrations</strong> tab first, or enter a Sheet ID manually when creating a campaign.
                    </div>
                  )}

                  {/* ── Create Outbound Campaign Form ── */}
                  {showCreateCamp && (
                    <form onSubmit={handleCreateCampaign} style={{ display: 'flex', flexDirection: 'column', gap: '1.15rem', border: '1px solid #f59e0b30', padding: '1.25rem', borderRadius: '8px', marginBottom: '1rem', background: 'linear-gradient(135deg, #f59e0b08, transparent)' }}>
                      <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-primary)' }}>
                        <Zap size={15} style={{ color: '#f59e0b' }} /> Launch Outbound Campaign
                      </h4>

                      {/* Campaign Name */}
                      <div>
                        <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.3rem', fontWeight: 500 }}>Campaign Name</label>
                        <input className="input" type="text" placeholder="e.g. Q4 Lead Outreach" value={campName} onChange={(e) => setCampName(e.target.value)} required />
                      </div>

                      {/* Sheet Source Info */}
                      {agent.google_sheets_enabled && agent.google_sheets_id ? (
                        <div style={{ padding: '0.65rem 0.85rem', backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <FileSpreadsheet size={14} style={{ color: '#10b981' }} />
                          <span>Leads from: <strong style={{ color: 'var(--text-primary)' }}>{agent.google_sheets_name || 'Sheet1'}</strong> (auto-connected)</span>
                        </div>
                      ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                          <div>
                            <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.3rem', fontWeight: 500 }}>Spreadsheet ID (manual)</label>
                            <input className="input" type="text" placeholder="1aBCd...xyz" value={campSpreadsheetId} onChange={(e) => setCampSpreadsheetId(e.target.value)} />
                          </div>
                          <div>
                            <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.3rem', fontWeight: 500 }}>Tab Name</label>
                            <input className="input" type="text" placeholder="Sheet1" value={campSheetName} onChange={(e) => setCampSheetName(e.target.value)} />
                          </div>
                        </div>
                      )}

                      {/* Operating Hours + Concurrency */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><Clock size={12} /> Start Time</label>
                          <input className="input" type="time" value={campStartTime} onChange={(e) => setCampStartTime(e.target.value)} />
                        </div>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><Clock size={12} /> End Time</label>
                          <input className="input" type="time" value={campEndTime} onChange={(e) => setCampEndTime(e.target.value)} />
                        </div>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><Users size={12} /> Concurrent Calls</label>
                          <input className="input" type="number" min="1" max="10" value={campMaxConcurrency} onChange={(e) => setCampMaxConcurrency(e.target.value)} />
                        </div>
                      </div>

                      {/* Retry Settings + Call Order */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><Repeat size={12} /> Retries</label>
                          <select className="input" value={campRetryCount} onChange={(e) => setCampRetryCount(e.target.value)} style={{ cursor: 'pointer' }}>
                            <option value={0}>No retries</option>
                            <option value={1}>1 retry</option>
                            <option value={2}>2 retries</option>
                            <option value={3}>3 retries</option>
                          </select>
                        </div>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><Clock size={12} /> Retry Delay</label>
                          <select className="input" value={campRetryDelay} onChange={(e) => setCampRetryDelay(e.target.value)} style={{ cursor: 'pointer' }}>
                            <option value={5}>5 minutes</option>
                            <option value={15}>15 minutes</option>
                            <option value={30}>30 minutes</option>
                            <option value={60}>1 hour</option>
                          </select>
                        </div>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><Shuffle size={12} /> Call Order</label>
                          <select className="input" value={campCallOrder} onChange={(e) => setCampCallOrder(e.target.value)} style={{ cursor: 'pointer' }}>
                            <option value="sequential">Top to Bottom</option>
                            <option value="random">Random</option>
                          </select>
                        </div>
                      </div>

                      {/* Actions */}
                      <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.25rem' }}>
                        <button type="button" className="btn btn-sm" onClick={() => setShowCreateCamp(false)} style={{ backgroundColor: 'var(--bg-hover)', color: 'var(--text-primary)' }}>Cancel</button>
                        <button type="submit" className="btn btn-sm" style={{ backgroundColor: '#f59e0b', color: '#fff', border: 'none', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <Zap size={13} /> Launch Campaign
                        </button>
                      </div>
                    </form>
                  )}

                  {/* ── Outbound Campaign List ── */}
                  {loadingCampaigns ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                      <Loader2 size={24} className="spin-active" style={{ color: '#f59e0b' }} />
                    </div>
                  ) : campaigns.length === 0 ? (
                    <div style={{ padding: '2.5rem 1.5rem', textAlign: 'center', border: '1px dashed var(--border)', borderRadius: '8px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      <PhoneOutgoing size={28} style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }} />
                      <div>No campaigns yet. Click <strong>"New Campaign"</strong> to start auto-dialing leads from your sheet.</div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {campaigns.map((camp) => {
                        const progress = camp.total_leads > 0 ? ((camp.completed_leads / camp.total_leads) * 100).toFixed(0) : 0;
                        return (
                          <div
                            key={camp.id}
                            style={{
                              padding: '1rem 1.15rem',
                              backgroundColor: 'var(--bg-primary)',
                              border: '1px solid var(--border)',
                              borderRadius: '8px',
                              cursor: 'pointer',
                              borderColor: selectedCampaign?.id === camp.id ? '#f59e0b' : 'var(--border)',
                              boxShadow: selectedCampaign?.id === camp.id ? '0 0 12px rgba(245, 158, 11, 0.12)' : 'none',
                              transition: 'all 0.2s',
                            }}
                            onClick={() => setSelectedCampaign(camp)}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                              <div>
                                <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                  <PhoneOutgoing size={14} style={{ color: '#f59e0b' }} />
                                  {camp.name}
                                </div>
                                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>Created: {new Date(camp.created_at).toLocaleDateString()}</div>
                              </div>
                              <span style={{
                                padding: '0.15rem 0.55rem', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.03em',
                                backgroundColor: camp.status === 'active' ? '#10b98115' : camp.status === 'completed' ? '#3b82f615' : '#f59e0b15',
                                color: camp.status === 'active' ? '#10b981' : camp.status === 'completed' ? '#3b82f6' : '#f59e0b',
                                border: `1px solid ${camp.status === 'active' ? '#10b98130' : camp.status === 'completed' ? '#3b82f630' : '#f59e0b30'}`,
                              }}>
                                {camp.status}
                              </span>
                            </div>

                            {/* Settings chips */}
                            <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.6rem', flexWrap: 'wrap' }}>
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', backgroundColor: 'var(--bg-hover)', padding: '0.15rem 0.45rem', borderRadius: '4px' }}>
                                <Clock size={10} /> {camp.start_time || '09:00'} – {camp.end_time || '18:00'}
                              </span>
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', backgroundColor: 'var(--bg-hover)', padding: '0.15rem 0.45rem', borderRadius: '4px' }}>
                                <Users size={10} /> {camp.max_concurrent_calls || 1} concurrent
                              </span>
                              {(camp.retry_count || 0) > 0 && (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', backgroundColor: 'var(--bg-hover)', padding: '0.15rem 0.45rem', borderRadius: '4px' }}>
                                  <Repeat size={10} /> {camp.retry_count}× retry
                                </span>
                              )}
                              {camp.call_order === 'random' && (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', backgroundColor: 'var(--bg-hover)', padding: '0.15rem 0.45rem', borderRadius: '4px' }}>
                                  <Shuffle size={10} /> Random
                                </span>
                              )}
                            </div>

                            {/* Progress */}
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                              <span>{camp.total_leads} leads</span>
                              <span style={{ display: 'flex', gap: '0.6rem' }}>
                                <span style={{ color: '#10b981' }}>✓ {camp.completed_leads}</span>
                                <span style={{ color: '#ef4444' }}>✗ {camp.failed_leads}</span>
                                <span style={{ color: '#f59e0b' }}>⏳ {camp.pending_leads}</span>
                              </span>
                            </div>
                            <div style={{ width: '100%', height: '5px', backgroundColor: 'var(--bg-hover)', borderRadius: '3px', overflow: 'hidden', display: 'flex' }}>
                              <div style={{ width: `${camp.total_leads > 0 ? (camp.completed_leads / camp.total_leads) * 100 : 0}%`, height: '100%', backgroundColor: '#10b981', transition: 'width 0.3s' }} />
                              <div style={{ width: `${camp.total_leads > 0 ? (camp.failed_leads / camp.total_leads) * 100 : 0}%`, height: '100%', backgroundColor: '#ef4444', transition: 'width 0.3s' }} />
                            </div>

                            {/* Controls */}
                            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.75rem' }} onClick={(e) => e.stopPropagation()}>
                              {camp.status !== 'completed' && (
                                camp.status === 'active' ? (
                                  <button className="btn btn-sm" onClick={() => handlePauseCampaign(camp.id)} style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem', backgroundColor: '#f59e0b15', color: '#f59e0b', border: '1px solid #f59e0b30', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                    <Pause size={12} /> Pause
                                  </button>
                                ) : (
                                  <button className="btn btn-sm" onClick={() => handleStartCampaign(camp.id)} style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem', backgroundColor: '#10b98115', color: '#10b981', border: '1px solid #10b98130', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                    <Play size={12} /> Start Dialer
                                  </button>
                                )
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Campaign Leads Table (when a campaign is selected) */}
                {selectedCampaign && (
                  <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1.5rem' }}>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <FileSpreadsheet size={16} style={{ color: '#f59e0b' }} />
                      Leads — {selectedCampaign.name}
                    </h3>

                    {loadingCampLeads ? (
                      <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                        <Loader2 size={24} className="spin-active" style={{ color: '#f59e0b' }} />
                      </div>
                    ) : campLeads.length === 0 ? (
                      <div style={{ padding: '1.5rem', textAlign: 'center', border: '1px dashed var(--border)', borderRadius: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        No leads in this campaign.
                      </div>
                    ) : (
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left' }}>
                              <th style={{ padding: '0.5rem', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.75rem' }}>Name</th>
                              <th style={{ padding: '0.5rem', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.75rem' }}>Phone</th>
                              <th style={{ padding: '0.5rem', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.75rem' }}>Status</th>
                              <th style={{ padding: '0.5rem', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.75rem' }}>Attempts</th>
                              <th style={{ padding: '0.5rem', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '0.75rem' }}>Notes</th>
                            </tr>
                          </thead>
                          <tbody>
                            {campLeads.map((lead) => (
                              <tr key={lead.id} style={{ borderBottom: '1px solid var(--border)', opacity: lead.status === 'completed' ? 0.65 : 1, transition: 'opacity 0.2s' }}>
                                <td style={{ padding: '0.5rem', fontWeight: 500, color: 'var(--text-primary)' }}>{lead.name}</td>
                                <td style={{ padding: '0.5rem', color: 'var(--text-secondary)', fontFamily: 'monospace', fontSize: '0.8rem' }}>{lead.phone}</td>
                                <td style={{ padding: '0.5rem' }}>
                                  <span style={{
                                    padding: '0.12rem 0.4rem', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600,
                                    backgroundColor: lead.status === 'completed' ? '#10b98115' : lead.status === 'failed' ? '#ef444415' : lead.status === 'calling' ? '#3b82f615' : lead.status === 'retry_pending' ? '#8b5cf615' : '#f59e0b15',
                                    color: lead.status === 'completed' ? '#10b981' : lead.status === 'failed' ? '#ef4444' : lead.status === 'calling' ? '#3b82f6' : lead.status === 'retry_pending' ? '#8b5cf6' : '#f59e0b',
                                  }}>
                                    {lead.status === 'retry_pending' ? 'retry queued' : lead.status}
                                  </span>
                                </td>
                                <td style={{ padding: '0.5rem', color: 'var(--text-muted)', fontSize: '0.78rem', textAlign: 'center' }}>{lead.attempt_count || 0}</td>
                                <td style={{ padding: '0.5rem', color: 'var(--text-muted)', fontSize: '0.78rem', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{lead.notes || '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </>

            ) : (

              /* ═══ INBOUND AGENT: Availability Configuration ═══ */
              <>
                <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
                      <PhoneIncoming size={18} style={{ color: '#06b6d4' }} />
                      Inbound Availability
                    </h3>
                    {!showCreateCamp && (
                      <button className="btn btn-sm" onClick={() => setShowCreateCamp(true)} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', backgroundColor: '#06b6d420', color: '#06b6d4', border: '1px solid #06b6d440', fontWeight: 600 }}>
                        <Settings size={14} /> Configure
                      </button>
                    )}
                  </div>

                  {/* ── Inbound Availability Config Form ── */}
                  {showCreateCamp && (
                    <form onSubmit={handleCreateCampaign} style={{ display: 'flex', flexDirection: 'column', gap: '1.15rem', border: '1px solid #06b6d430', padding: '1.25rem', borderRadius: '8px', marginBottom: '1rem', background: 'linear-gradient(135deg, #06b6d408, transparent)' }}>
                      <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-primary)' }}>
                        <Shield size={15} style={{ color: '#06b6d4' }} /> Availability Settings
                      </h4>

                      {/* Config Name */}
                      <div>
                        <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.3rem', fontWeight: 500 }}>Configuration Name</label>
                        <input className="input" type="text" placeholder="e.g. Business Hours Config" value={campName} onChange={(e) => setCampName(e.target.value)} required />
                      </div>

                      {/* Operating Hours */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem' }}>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><Clock size={12} /> Available From</label>
                          <input className="input" type="time" value={campStartTime} onChange={(e) => setCampStartTime(e.target.value)} />
                        </div>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><Clock size={12} /> Available Until</label>
                          <input className="input" type="time" value={campEndTime} onChange={(e) => setCampEndTime(e.target.value)} />
                        </div>
                        <div>
                          <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><Users size={12} /> Max Concurrent</label>
                          <input className="input" type="number" min="1" max="50" placeholder="Unlimited" value={campMaxConcurrency} onChange={(e) => setCampMaxConcurrency(e.target.value)} />
                        </div>
                      </div>

                      {/* After-Hours Behavior */}
                      <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                        <label style={{ fontSize: '0.8rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.6rem', fontWeight: 600 }}>
                          <MessageSquare size={14} style={{ color: '#06b6d4' }} /> After-Hours Behavior
                        </label>
                        <select className="input" value={campAfterHoursAction} onChange={(e) => setCampAfterHoursAction(e.target.value)} style={{ cursor: 'pointer', marginBottom: '0.75rem' }}>
                          <option value="none">Keep accepting calls (no limit)</option>
                          <option value="voicemail">Send to voicemail</option>
                          <option value="message">Play a custom message & hang up</option>
                          <option value="transfer">Transfer to another number</option>
                        </select>

                        {campAfterHoursAction === 'message' && (
                          <div>
                            <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.3rem', fontWeight: 500 }}>After-Hours Message</label>
                            <textarea className="input" rows={2} placeholder="e.g. Thank you for calling. Our business hours are 9 AM to 6 PM..." value={campAfterHoursMessage} onChange={(e) => setCampAfterHoursMessage(e.target.value)} style={{ resize: 'vertical', minHeight: '50px' }} />
                          </div>
                        )}
                        {campAfterHoursAction === 'transfer' && (
                          <div>
                            <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginBottom: '0.3rem', fontWeight: 500 }}><PhoneForwarded size={12} /> Transfer Number</label>
                            <input className="input" type="tel" placeholder="+1 (555) 123-4567" value={campAfterHoursTransferNumber} onChange={(e) => setCampAfterHoursTransferNumber(e.target.value)} />
                          </div>
                        )}
                      </div>

                      {/* Actions */}
                      <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.25rem' }}>
                        <button type="button" className="btn btn-sm" onClick={() => setShowCreateCamp(false)} style={{ backgroundColor: 'var(--bg-hover)', color: 'var(--text-primary)' }}>Cancel</button>
                        <button type="submit" className="btn btn-sm" style={{ backgroundColor: '#06b6d4', color: '#fff', border: 'none', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <Save size={13} /> Save Configuration
                        </button>
                      </div>
                    </form>
                  )}

                  {/* ── Inbound Availability Cards ── */}
                  {loadingCampaigns ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                      <Loader2 size={24} className="spin-active" style={{ color: '#06b6d4' }} />
                    </div>
                  ) : campaigns.length === 0 ? (
                    <div style={{ padding: '2.5rem 1.5rem', textAlign: 'center', border: '1px dashed var(--border)', borderRadius: '8px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      <PhoneIncoming size={28} style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }} />
                      <div>No availability configured. Click <strong>"Configure"</strong> to set business hours and after-hours behavior.</div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {campaigns.map((camp) => (
                        <div
                          key={camp.id}
                          style={{
                            padding: '1rem 1.15rem',
                            backgroundColor: 'var(--bg-primary)',
                            border: '1px solid var(--border)',
                            borderRadius: '8px',
                            borderColor: selectedCampaign?.id === camp.id ? '#06b6d4' : 'var(--border)',
                            boxShadow: selectedCampaign?.id === camp.id ? '0 0 12px rgba(6, 182, 212, 0.1)' : 'none',
                            transition: 'all 0.2s',
                            cursor: 'pointer',
                          }}
                          onClick={() => setSelectedCampaign(camp)}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <PhoneIncoming size={14} style={{ color: '#06b6d4' }} />
                                {camp.name}
                              </div>
                              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>Created: {new Date(camp.created_at).toLocaleDateString()}</div>
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }} onClick={(e) => e.stopPropagation()}>
                              <span style={{
                                padding: '0.15rem 0.55rem', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.03em',
                                backgroundColor: camp.status === 'active' ? '#10b98115' : '#f59e0b15',
                                color: camp.status === 'active' ? '#10b981' : '#f59e0b',
                                border: `1px solid ${camp.status === 'active' ? '#10b98130' : '#f59e0b30'}`,
                              }}>
                                {camp.status === 'active' ? 'Live' : 'Inactive'}
                              </span>
                              {camp.status === 'active' ? (
                                <button className="btn btn-sm" onClick={() => handlePauseCampaign(camp.id)} style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem', backgroundColor: '#f59e0b15', color: '#f59e0b', border: '1px solid #f59e0b30' }}>
                                  <Pause size={11} />
                                </button>
                              ) : (
                                <button className="btn btn-sm" onClick={() => handleStartCampaign(camp.id)} style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem', backgroundColor: '#10b98115', color: '#10b981', border: '1px solid #10b98130' }}>
                                  <Play size={11} />
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Settings chips */}
                          <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.72rem', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', backgroundColor: 'var(--bg-hover)', padding: '0.15rem 0.45rem', borderRadius: '4px' }}>
                              <Clock size={10} /> {camp.start_time || '09:00'} – {camp.end_time || '18:00'}
                            </span>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', backgroundColor: 'var(--bg-hover)', padding: '0.15rem 0.45rem', borderRadius: '4px' }}>
                              <Users size={10} /> {camp.max_concurrent_calls || 1} concurrent
                            </span>
                            {camp.after_hours_action && camp.after_hours_action !== 'none' && (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', backgroundColor: '#06b6d410', padding: '0.15rem 0.45rem', borderRadius: '4px', color: '#06b6d4' }}>
                                <MessageSquare size={10} /> After hours: {camp.after_hours_action}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* ─── TAB: KNOWLEDGE BASE (RAG) ─── */}
        {leftTab === 'knowledge_base' && (
          <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '1.5rem' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <HelpCircle size={18} style={{ color: 'var(--accent)' }} />
                RAG Knowledge Base
              </h3>
              
              {/* File Uploader */}
              <form onSubmit={handleUploadKBFile} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', border: '1px dashed var(--accent)', padding: '1.5rem', borderRadius: '6px', backgroundColor: 'var(--bg-primary)', marginBottom: '1.5rem', textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  Upload custom document files (.txt, .pdf, or .csv) to the agent. The agent will retrieve facts from these documents in real-time during voice calls.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem', margin: '0.5rem 0' }}>
                  <input
                    type="file"
                    id="kb-file-input"
                    accept=".txt,.pdf,.csv"
                    onChange={(e) => setFileToUpload(e.target.files[0])}
                    style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}
                  />
                </div>
                <button type="submit" className="btn btn-primary btn-sm" style={{ alignSelf: 'center', padding: '0.5rem 2rem' }} disabled={uploadingKb || !fileToUpload}>
                  {uploadingKb ? (
                    <>
                      <Loader2 size={14} className="spin-active inline" style={{ marginRight: '0.5rem' }} /> 
                      {uploadProgress < 100 ? `Uploading (${uploadProgress}%)...` : 'Parsing & Indexing...'}
                    </>
                  ) : (
                    'Upload & Index Document'
                  )}
                </button>
              </form>

              {/* Active Documents List */}
              <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.9rem', fontWeight: 600 }}>Active Documents</h4>
              {loadingKb ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                  <Loader2 size={24} className="spin-active" style={{ color: 'var(--accent)' }} />
                </div>
              ) : kbFiles.length === 0 ? (
                <div style={{ padding: '1.5rem', textAlign: 'center', border: '1px dashed var(--border)', borderRadius: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  No documents uploaded yet. Upload a text, PDF, or CSV file to build the agent's brain.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {kbFiles.map((doc) => (
                    <div key={doc.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem', border: '1px solid var(--border)', borderRadius: '6px', backgroundColor: 'var(--bg-primary)' }}>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>{doc.filename}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Uploaded: {new Date(doc.created_at).toLocaleString()}</div>
                      </div>
                      <button className="btn btn-ghost btn-sm" onClick={() => handleDeleteKBFile(doc.id)} style={{ color: '#ef4444', padding: '0.35rem 0.5rem', fontSize: '0.8rem' }}>
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── TAB: ANALYTICS & LOGS ─── */}
        {leftTab === 'analytics' && (
          <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {loadingAnalytics ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
                <Loader2 size={36} className="spin-active" style={{ color: 'var(--accent)' }} />
              </div>
            ) : !analytics || analytics.total_calls === 0 ? (
              <div style={{ padding: '3rem 1rem', textAlign: 'center', backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}>
                <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>No Analytics Data Yet</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', maxWidth: '320px', margin: '0 auto' }}>
                  Make some browser test calls or outbound phone calls to populate analytics charts.
                </p>
              </div>
            ) : (
              <>
                {/* Stat cards row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1.25rem' }}>
                  <div style={{
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.25rem',
                    backdropFilter: 'blur(5px)',
                  }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>Total Calls</div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>{analytics.total_calls}</div>
                  </div>

                  <div style={{
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.25rem',
                    backdropFilter: 'blur(5px)',
                  }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>Total Minutes</div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>{analytics.total_duration}m</div>
                  </div>

                  <div style={{
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.25rem',
                    backdropFilter: 'blur(5px)',
                  }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>Avg Duration</div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {analytics.total_calls > 0 ? (analytics.total_duration / analytics.total_calls).toFixed(1) : 0}m
                    </div>
                  </div>
                </div>

                {/* Charts Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
                  {/* Sentiment distribution donut chart */}
                  <div style={{
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.5rem',
                  }}>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1.25rem', color: 'var(--text-primary)' }}>Customer Sentiment</h4>
                    {(() => {
                      const pos = analytics.sentiment_counts?.Positive || 0;
                      const neu = analytics.sentiment_counts?.Neutral || 0;
                      const neg = analytics.sentiment_counts?.Negative || 0;
                      const tot = pos + neu + neg;
                      if (tot === 0) return <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No sentiment data</div>;

                      // Donut SVG parameters
                      const radius = 50;
                      const circumference = 2 * Math.PI * radius;
                      const posPct = pos / tot;
                      const neuPct = neu / tot;
                      const negPct = neg / tot;

                      const posStroke = circumference * posPct;
                      const neuStroke = circumference * neuPct;
                      const negStroke = circumference * negPct;

                      const posOffset = circumference;
                      const neuOffset = circumference - posStroke;
                      const negOffset = circumference - posStroke - neuStroke;

                      return (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', justifyContent: 'center' }}>
                          <svg width="140" height="140" viewBox="0 0 140 140" style={{ transform: 'rotate(-90deg)' }}>
                            <circle cx="70" cy="70" r={radius} fill="none" stroke="var(--border)" strokeWidth="16" />
                            {/* Positive segment */}
                            {posStroke > 0 && (
                              <circle
                                cx="70"
                                cy="70"
                                r={radius}
                                fill="none"
                                stroke="#10b981"
                                strokeWidth="16"
                                strokeDasharray={`${posStroke} ${circumference - posStroke}`}
                                strokeDashoffset={posOffset}
                                strokeLinecap="round"
                              />
                            )}
                            {/* Neutral segment */}
                            {neuStroke > 0 && (
                              <circle
                                cx="70"
                                cy="70"
                                r={radius}
                                fill="none"
                                stroke="#f59e0b"
                                strokeWidth="16"
                                strokeDasharray={`${neuStroke} ${circumference - neuStroke}`}
                                strokeDashoffset={neuOffset}
                                strokeLinecap="round"
                              />
                            )}
                            {/* Negative segment */}
                            {negStroke > 0 && (
                              <circle
                                cx="70"
                                cy="70"
                                r={radius}
                                fill="none"
                                stroke="#ef4444"
                                strokeWidth="16"
                                strokeDasharray={`${negStroke} ${circumference - negStroke}`}
                                strokeDashoffset={negOffset}
                                strokeLinecap="round"
                              />
                            )}
                          </svg>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span style={{ width: 12, height: 12, borderRadius: '3px', backgroundColor: '#10b981', display: 'inline-block' }}></span>
                              <span>Positive: {pos} ({Math.round(posPct * 100)}%)</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span style={{ width: 12, height: 12, borderRadius: '3px', backgroundColor: '#f59e0b', display: 'inline-block' }}></span>
                              <span>Neutral: {neu} ({Math.round(neuPct * 100)}%)</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span style={{ width: 12, height: 12, borderRadius: '3px', backgroundColor: '#ef4444', display: 'inline-block' }}></span>
                              <span>Negative: {neg} ({Math.round(negPct * 100)}%)</span>
                            </div>
                          </div>
                        </div>
                      );
                    })()}
                  </div>

                  {/* Outcomes bar chart card */}
                  <div style={{
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.5rem',
                  }}>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1.25rem', color: 'var(--text-primary)' }}>Call Outcomes</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxHeight: '180px', overflowY: 'auto' }}>
                      {Object.entries(analytics.outcome_counts || {}).length === 0 ? (
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No outcomes logged yet</div>
                      ) : (
                        Object.entries(analytics.outcome_counts || {})
                          .sort((a, b) => b[1] - a[1])
                          .map(([outcome, count]) => {
                            const pct = Math.max(5, Math.round((count / analytics.total_calls) * 100));
                            return (
                              <div key={outcome} style={{ fontSize: '0.85rem' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                                  <span style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '80%' }}>{outcome}</span>
                                  <span style={{ color: 'var(--text-secondary)' }}>{count} ({pct})</span>
                                </div>
                                <div style={{ width: '100%', height: '8px', backgroundColor: 'var(--bg-tertiary)', borderRadius: '4px', overflow: 'hidden' }}>
                                  <div style={{
                                    width: `${pct}%`,
                                    height: '100%',
                                    background: 'linear-gradient(90deg, var(--accent), #10b981)',
                                    borderRadius: '4px'
                                  }}></div>
                                </div>
                              </div>
                            );
                          })
                      )}
                    </div>
                  </div>
                </div>

                {/* Daily volume line chart */}
                {analytics.daily_volume?.length > 0 && (
                  <div style={{
                    backgroundColor: 'var(--bg-secondary)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    padding: '1.5rem',
                  }}>
                    <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1.25rem', color: 'var(--text-primary)' }}>Daily Call Volume</h4>
                    {(() => {
                      const data = analytics.daily_volume;
                      const maxVal = Math.max(...data.map(d => d.calls), 4);
                      const width = 500;
                      const height = 120;
                      const padding = 20;

                      // Map data to points
                      const points = data.map((d, index) => {
                        const x = padding + (index / Math.max(1, data.length - 1)) * (width - 2 * padding);
                        const y = height - padding - (d.calls / maxVal) * (height - 2 * padding);
                        return { x, y, calls: d.calls, date: d.date };
                      });

                      const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
                      const areaD = points.length > 0
                        ? `${pathD} L ${points[points.length - 1].x} ${height - padding} L ${points[0].x} ${height - padding} Z`
                        : '';

                      return (
                        <div style={{ overflowX: 'auto' }}>
                          <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ overflow: 'visible' }}>
                            <defs>
                              <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.3" />
                                <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
                              </linearGradient>
                            </defs>
                            {/* Horizontal Grid lines */}
                            {[0, 0.5, 1].map((r, i) => {
                              const y = padding + r * (height - 2 * padding);
                              return (
                                <line key={i} x1={padding} y1={y} x2={width - padding} y2={y} stroke="var(--border)" strokeWidth="1" strokeDasharray="4 4" />
                              );
                            })}
                            {/* Filled Area */}
                            {areaD && <path d={areaD} fill="url(#chartGradient)" />}
                            {/* Stroke Path */}
                            {pathD && <path d={pathD} fill="none" stroke="var(--accent)" strokeWidth="2.5" />}
                            {/* Data points dots */}
                            {points.map((p, i) => (
                              <g key={i}>
                                <circle cx={p.x} cy={p.y} r="4" fill="var(--bg-secondary)" stroke="var(--accent)" strokeWidth="2" />
                                <text x={p.x} y={p.y - 8} fontSize="8" fill="var(--text-secondary)" textAnchor="middle" fontWeight="600">{p.calls}</text>
                                <text x={p.x} y={height - 4} fontSize="8" fill="var(--text-muted)" textAnchor="middle">
                                  {p.date.split('-').slice(1).join('/')}
                                </text>
                              </g>
                            ))}
                          </svg>
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* Call History list */}
                <div style={{
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '1.5rem',
                }}>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '1rem', color: 'var(--text-primary)' }}>Call History Logs</h4>
                  {calls.length === 0 ? (
                    <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                      No calls recorded yet.
                    </div>
                  ) : (
                    <div style={{ overflowX: 'auto', borderRadius: '6px', border: '1px solid var(--border)' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
                        <thead>
                          <tr style={{ backgroundColor: 'var(--bg-tertiary)', borderBottom: '1px solid var(--border)' }}>
                            <th style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>Date/Time</th>
                            <th style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>Duration</th>
                            <th style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>Sentiment</th>
                            <th style={{ padding: '0.5rem 0.75rem', fontWeight: 600 }}>Outcome</th>
                          </tr>
                        </thead>
                        <tbody>
                          {calls.map((c) => {
                            const date = new Date(c.created_at).toLocaleString();
                            const sent = c.sentiment || 'Neutral';
                            const badgeColor = sent === 'Positive' ? '#10b981' : sent === 'Negative' ? '#ef4444' : '#f59e0b';
                            return (
                              <tr
                                key={c.id}
                                onClick={() => setSelectedCallLog(c)}
                                style={{
                                  borderBottom: '1px solid var(--border)',
                                  cursor: 'pointer',
                                  transition: 'background-color 0.2s',
                                }}
                                className="row-hover"
                              >
                                <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-primary)' }}>{date}</td>
                                <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-primary)' }}>{c.duration} mins</td>
                                <td style={{ padding: '0.6rem 0.75rem' }}>
                                  <span style={{
                                    padding: '0.15rem 0.4rem',
                                    borderRadius: '4px',
                                    fontSize: '0.7rem',
                                    fontWeight: 600,
                                    backgroundColor: `${badgeColor}20`,
                                    color: badgeColor,
                                  }}>
                                    {sent}
                                  </span>
                                </td>
                                <td style={{ padding: '0.6rem 0.75rem', color: 'var(--text-secondary)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {c.outcome || '—'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* ─── RIGHT PANEL: Live Voice testing transcript ─── */}
      <div style={{ width: 420, display: 'flex', flexDirection: 'column', backgroundColor: 'var(--bg-primary)' }}>

        {/* Header */}
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'var(--bg-secondary)' }}>
          <div style={{ fontWeight: 600 }}>Active Voice Transcript</div>
          {isConnected && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>{formatTime(callDuration)}</span>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '0.35rem',
                color: isSpeaking ? 'var(--accent)' : isListening ? '#3b82f6' : 'var(--text-muted)',
              }}>
                {isSpeaking ? (
                  <><Volume2 size={14} className="pulse-active" /> Speaking</>
                ) : (
                  <><Mic size={14} /> Listening</>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Call context summary if speaking to a CRM lead */}
        {isConnected && activeLead && (
          <div style={{
            padding: '0.5rem 1.5rem',
            backgroundColor: 'var(--accent-transparent)',
            borderBottom: '1px solid var(--border)',
            fontSize: '0.8rem',
            color: 'var(--text-primary)',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}>
            <Activity size={12} className="pulse-active" style={{ color: 'var(--accent)' }} />
            Connected to lead: <strong style={{ color: 'var(--accent)' }}>{activeLead.name}</strong> (Row {activeLead.leadRow})
          </div>
        )}

        {/* Chat Transcript Window */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '1rem 1.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem',
          }}
        >
          {!isConnected && transcripts.length === 0 && (
            <div style={{
              margin: 'auto',
              textAlign: 'center',
              padding: '2rem',
            }}>
              <div style={{
                width: 64, height: 64, borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--accent-transparent), transparent)',
                border: '2px solid var(--accent)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                margin: '0 auto 1.5rem',
              }}>
                <Phone size={28} color="var(--accent)" />
              </div>
              <h3 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>Ready to Call</h3>
              <p style={{ fontSize: '0.875rem', maxWidth: 260, color: 'var(--text-secondary)', margin: '0 auto' }}>
                {sheetsEnabled && agent.google_sheets_id ? (
                  "Select a lead from the Campaign table and click 'Call' to start qualify session."
                ) : (
                  `Click "Start Call" below to begin a live voice test with ${agent.name}.`
                )}
              </p>
            </div>
          )}

          {transcripts.filter(m => m.is_final).map((msg, i) => (
            <div
              key={i}
              className="animate-fade-in"
              style={{
                display: 'flex',
                gap: '0.75rem',
                alignItems: 'flex-start',
              }}
            >
              <div style={{
                width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                backgroundColor: msg.role === 'assistant' ? 'var(--accent)' : 'var(--bg-hover)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.7rem', fontWeight: 700, color: 'white',
                marginTop: 2,
              }}>
                {msg.role === 'assistant' ? 'AI' : 'U'}
              </div>

              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: msg.role === 'assistant' ? 'var(--accent)' : 'var(--text-secondary)', marginBottom: '0.2rem' }}>
                  {msg.role === 'assistant' ? agent.name : 'You'}
                </div>
                <div style={{
                  fontSize: '0.875rem',
                  lineHeight: 1.6,
                  color: 'var(--text-primary)',
                }}>
                  {msg.text}
                </div>
              </div>
            </div>
          ))}

          {/* Show interim (live) transcript */}
          {transcripts.length > 0 && !transcripts[transcripts.length - 1].is_final && (
            <div style={{
              display: 'flex', gap: '0.75rem', alignItems: 'flex-start', opacity: 0.6,
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                backgroundColor: 'var(--bg-hover)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '0.7rem', fontWeight: 700, color: 'white', marginTop: 2,
              }}>U</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.2rem' }}>You (speaking...)</div>
                <div style={{ fontSize: '0.875rem', lineHeight: 1.6, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                  {transcripts[transcripts.length - 1].text}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Call Action Panel */}
        <div style={{
          padding: '1.25rem',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '0.75rem',
          backgroundColor: 'var(--bg-secondary)',
        }}>
          {error && (
            <div style={{ fontSize: '0.8rem', color: '#ef4444', textAlign: 'center', maxWidth: 300 }}>
              {error}
            </div>
          )}
          {!isConnected && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={useWebRTC}
                  onChange={(e) => setUseWebRTC(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                Use Low-Latency WebRTC Stream
              </label>
            </div>
          )}
          {!isConnected ? (
            <button
              className="btn btn-primary"
              style={{
                padding: '0.875rem 2.5rem',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.9rem',
                fontWeight: 600,
              }}
              onClick={() => connect({ useWebRTC })}
            >
              <Phone size={18} /> Start Call
            </button>
          ) : (
            <button
              className="btn"
              style={{
                padding: '0.875rem 2.5rem',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.9rem',
                fontWeight: 600,
                backgroundColor: '#ef4444',
                color: 'white',
              }}
              onClick={disconnect}
            >
              <PhoneOff size={18} /> End Call
            </button>
          )}
        </div>
      </div>

      {/* ─── CALL HISTORY LOG DETAILS MODAL DRAWER ─── */}
      {selectedCallLog && (
        <div style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          left: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          justifyContent: 'flex-end',
          zIndex: 999,
        }} onClick={() => setSelectedCallLog(null)}>
          <div style={{
            width: '500px',
            height: '100%',
            backgroundColor: 'var(--bg-primary)',
            borderLeft: '1px solid var(--border)',
            boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }} onClick={(e) => e.stopPropagation()}>
            {/* Modal Header */}
            <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'var(--bg-secondary)' }}>
              <div>
                <h3 style={{ fontWeight: 600, fontSize: '1rem', margin: 0 }}>Call Log Details</h3>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>{new Date(selectedCallLog.created_at).toLocaleString()}</div>
              </div>
              <button className="btn-ghost" onClick={() => setSelectedCallLog(null)} style={{ padding: '0.35rem', borderRadius: '50%', fontSize: '1.2rem', lineHeight: 1, border: 'none', background: 'none', cursor: 'pointer' }}>
                ×
              </button>
            </div>

            {/* Modal Content */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Duration and Sentiment Row */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Duration</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600, marginTop: '0.25rem' }}>{selectedCallLog.duration} minutes</div>
                </div>
                <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '0.75rem', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Sentiment</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600, marginTop: '0.25rem', color: selectedCallLog.sentiment === 'Positive' ? '#10b981' : selectedCallLog.sentiment === 'Negative' ? '#ef4444' : '#f59e0b' }}>
                    {selectedCallLog.sentiment}
                  </div>
                </div>
              </div>

              {/* Call Outcome */}
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.5rem' }}>Outcome</div>
                <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '0.75rem 1rem', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                  {selectedCallLog.outcome || 'No outcome classified'}
                </div>
              </div>

              {/* Call Summary */}
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.5rem' }}>AI Summary</div>
                <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border)', padding: '1rem', borderRadius: '6px', fontSize: '0.85rem', lineHeight: 1.5, color: 'var(--text-secondary)' }}>
                  {selectedCallLog.summary || 'No summary available.'}
                </div>
              </div>

              {/* Call Transcript */}
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.5rem' }}>Full Transcript</div>
                <div style={{
                  flex: 1,
                  backgroundColor: 'var(--bg-secondary)',
                  border: '1px solid var(--border)',
                  padding: '1rem',
                  borderRadius: '6px',
                  fontSize: '0.85rem',
                  lineHeight: 1.6,
                  color: 'var(--text-primary)',
                  fontFamily: 'monospace',
                  whiteSpace: 'pre-wrap',
                  maxHeight: '300px',
                  overflowY: 'auto'
                }}>
                  {selectedCallLog.transcript || 'No transcript generated.'}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
