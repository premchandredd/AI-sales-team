import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = import.meta.env?.VITE_SUPABASE_URL || 'https://oylogkjuzvchooftacja.supabase.co';
const SUPABASE_ANON_KEY = import.meta.env?.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im95bG9na2p1enZjaG9vZnRhY2phIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk5MzMzOTYsImV4cCI6MjA5NTUwOTM5Nn0.BV-W2Ogzqjwvi6kvlMShILypwdlQBdi0fkgI07UkBX0';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
