"""
Prompt Builder — converts wizard answers into a polished system prompt.
This replicates Vapi's conversational agent-builder logic.
"""


def build_system_prompt(config: dict) -> str:
    """
    Generate a production-quality system prompt from wizard configuration.

    Args:
        config: dict with keys: name, type, language, tasks, tone,
                business_name, business_description, custom_instructions
    """
    name = config.get("name", "Assistant")
    agent_type = config.get("type", "inbound")
    raw_language = config.get("language", "English (Indian)|en-IN")
    # Extract display name and Sarvam language code from "Label|code" format
    if "|" in raw_language:
        language, tts_lang_code = raw_language.split("|", 1)
    else:
        language = raw_language
        tts_lang_code = "en-IN"
    tasks = config.get("tasks", [])
    tone = config.get("tone", "Professional")
    business_name = config.get("business_name", "")
    business_description = config.get("business_description", "")
    custom_instructions = config.get("custom_instructions", "")

    # ── Build the prompt sections ──
    sections = []

    # Identity
    identity = f"You are {name}"
    if business_name:
        identity += f", an AI voice assistant for {business_name}"
    if business_description:
        identity += f". {business_description}"
    else:
        identity += "."
    sections.append(f"IDENTITY:\n{identity}")

    # Language
    if "English" in language:
        sections.append(f"LANGUAGE:\nSpeak naturally in {language}. Always respond in {language} unless the caller switches languages.")
    elif "Hinglish" in language:
        sections.append(
            "LANGUAGE:\n"
            "Speak in Hinglish (a mixture of Hindi and English) as spoken in casual conversations in India.\n"
            "CRITICAL: Always output all Hinglish text using ONLY Latin/English characters (do not use Devanagari/Hindi script). For example, write 'Aapka swagat hai' or 'Maine appointment book kar diya hai' instead of Devanagari script. Use simple, conversational language.\n"
            "Keep the phrasing natural, and mix in common English words where appropriate (e.g. 'appointment', 'schedule', 'details', 'confirm', 'date', 'time').\n"
            "Sarvam AI's TTS handles English words written in Latin script mixed with Hindi words perfectly."
        )
    else:
        sections.append(f"LANGUAGE:\nSpeak in conversational {language}. Use natural, everyday {language} as spoken by locals. It is perfectly fine to naturally mix in common English words (e.g. 'time', 'date', 'ok', 'problem', 'hello'). Do NOT use overly pure, formal, or literary {language}.\n\nCRITICAL SCRIPT REQUIREMENT: You MUST output all {language} text strictly in the native {language} script (e.g., Telugu script for Telugu, Devanagari for Hindi). HOWEVER, for English abbreviations, business names, and acronyms (like KPN, VSL, BHK), you MUST keep them in English/Latin letters. Sarvam AI Text-to-Speech system handles code-mixed English acronyms perfectly when they are in Latin script.")

    # Tone mapping
    tone_map = {
        "Warm & Friendly": (
            "PERSONALITY:\n"
            "- Be warm, approachable, and genuinely caring\n"
            "- Use conversational language and occasional friendly fillers\n"
            "- Show empathy and understanding\n"
            "- Make the caller feel comfortable and welcomed"
        ),
        "Professional": (
            "PERSONALITY:\n"
            "- Be polished, clear, and efficient\n"
            "- Use precise language without being cold\n"
            "- Maintain a confident and knowledgeable demeanor\n"
            "- Respect the caller's time"
        ),
        "Empathetic": (
            "PERSONALITY:\n"
            "- Be deeply empathetic and patient\n"
            "- Listen actively and acknowledge emotions\n"
            "- Use reassuring language\n"
            "- Never rush the caller; let them express themselves fully"
        ),
        "Concise": (
            "PERSONALITY:\n"
            "- Be direct and to the point\n"
            "- Minimize filler words and unnecessary pleasantries\n"
            "- Provide clear, actionable information quickly\n"
            "- Respect that the caller wants efficiency"
        ),
    }
    sections.append(tone_map.get(tone, tone_map["Professional"]))

    # Tasks
    if tasks:
        task_details = {
            "Schedule appointments": (
                "- Help callers schedule new appointments\n"
                "- Ask for preferred date, time, and any relevant details\n"
                "- Confirm the appointment details before finalizing"
            ),
            "Reschedule/cancel": (
                "- Help callers reschedule or cancel existing appointments\n"
                "- Ask for their name or appointment reference\n"
                "- Offer alternative dates/times for rescheduling"
            ),
            "Answer FAQs": (
                "- Answer frequently asked questions accurately\n"
                "- If you don't know the answer, honestly say so\n"
                "- Offer to connect them with a human if needed"
            ),
            "Route to staff": (
                "- Determine the caller's needs and route to the appropriate department\n"
                "- Ask clarifying questions if the request is ambiguous\n"
                "- Provide estimated wait times when possible"
            ),
            "Lead qualification": (
                "- Qualify leads by asking about their needs, budget, and timeline\n"
                "- Gather contact information for follow-up\n"
                "- Prioritize leads based on their responses"
            ),
            "Customer support": (
                "- Help resolve customer issues and complaints\n"
                "- Troubleshoot common problems step by step\n"
                "- Escalate to a human agent for complex issues"
            ),
            "Order status": (
                "- Help callers check the status of their orders\n"
                "- Ask for order number or account details\n"
                "- Provide clear updates on shipping and delivery"
            ),
            "Survey/feedback": (
                "- Conduct satisfaction surveys after service interactions\n"
                "- Ask clear, concise questions and record responses\n"
                "- Thank the caller for their time and feedback"
            ),
        }
        task_lines = []
        for task in tasks:
            detail = task_details.get(task, f"- Handle {task} requests professionally")
            task_lines.append(f"### {task}\n{detail}")
        sections.append("CAPABILITIES:\n" + "\n\n".join(task_lines))

    # Voice-specific rules (critical for natural voice agents)
    sections.append(
        "VOICE CONVERSATION RULES:\n"
        "- Keep EVERY response to 1-2 SHORT sentences maximum (this is a phone call!)\n"
        "- Never use bullet points, numbered lists, or formatted text\n"
        "- Never use emojis, markdown, or special characters\n"
        "- Ask ONE question at a time and wait for a response\n"
        "- Use natural speech patterns — contractions, fillers, and pauses\n"
        "- If the caller is silent, gently prompt them\n"
        "- If the caller wants to end the call, wrap up gracefully\n"
        "- Never reveal that you are an AI unless directly asked"
    )

    # Agent type specifics
    if agent_type == "outbound":
        sections.append(
            "OUTBOUND CALL PROTOCOL:\n"
            "- Always introduce yourself and state the purpose of the call immediately\n"
            "- Be respectful of the caller's time — get to the point\n"
            "- If they are not interested, thank them and end the call gracefully\n"
            "- Never be pushy or aggressive"
        )
    elif agent_type == "inbound":
        sections.append(
            "INBOUND CALL PROTOCOL:\n"
            "- Greet the caller warmly and ask how you can help\n"
            "- Listen carefully to understand their needs before responding\n"
            "- If you need to transfer or escalate, explain why"
        )
    elif agent_type == "support":
        sections.append(
            "SUPPORT PROTOCOL:\n"
            "- Start by understanding the issue before jumping to solutions\n"
            "- Walk the caller through solutions step by step\n"
            "- Confirm the issue is resolved before ending the call\n"
            "- If unresolved, escalate with full context"
        )

    # Custom instructions
    if custom_instructions:
        sections.append(f"ADDITIONAL INSTRUCTIONS:\n{custom_instructions}")

    # Final reminder
    sections.append(
        "IMPORTANT: You are on a live voice call. Be brief, be natural, sound human. "
        "Never output anything that wouldn't work in spoken conversation."
    )

    return "\n\n".join(sections)


def build_first_message(config: dict) -> str:
    """Generate the agent's opening greeting."""
    name = config.get("name", "your assistant")
    business_name = config.get("business_name", "")
    agent_type = config.get("type", "inbound")

    if agent_type == "outbound":
        if business_name:
            return f"Hi there! This is {name} calling from {business_name}. Do you have a quick moment?"
        return f"Hi there! This is {name}. Do you have a quick moment?"

    if business_name:
        return f"Hi! Thanks for calling {business_name}. I'm {name}. How can I help you today?"
    return f"Hello! I'm {name}. How can I help you today?"


# ── Wizard Question Flow ──
WIZARD_STEPS = [
    {
        "id": "type",
        "question": "What type of agent would you like to create?",
        "options": [
            {"value": "inbound", "label": "Inbound", "description": "Handle incoming calls from customers", "icon": "📞"},
            {"value": "outbound", "label": "Outbound", "description": "Make outgoing calls to leads or customers", "icon": "📱"},
            {"value": "support", "label": "Support", "description": "Provide customer support and troubleshooting", "icon": "🎧"},
        ],
        "allow_custom": False,
    },
    {
        "id": "language",
        "question": "What language(s) should your agent speak? (Powered by Sarvam AI)",
        "options": [
            {"value": "English (Indian)|en-IN", "label": "English (Indian)", "description": "English with Indian accent", "icon": "🇮🇳"},
            {"value": "Hinglish|hi-IN", "label": "Hinglish", "description": "Mix of Hindi & English (Latin alphabet)", "icon": "🇮🇳"},
            {"value": "Hindi|hi-IN", "label": "Hindi", "description": "हिन्दी — Native Hindi", "icon": "🇮🇳"},
            {"value": "Tamil|ta-IN", "label": "Tamil", "description": "தமிழ் — Native Tamil", "icon": "🇮🇳"},
            {"value": "Telugu|te-IN", "label": "Telugu", "description": "తెలుగు — Native Telugu", "icon": "🇮🇳"},
            {"value": "Bengali|bn-IN", "label": "Bengali", "description": "বাংলা — Native Bengali", "icon": "🇮🇳"},
            {"value": "Kannada|kn-IN", "label": "Kannada", "description": "ಕನ್ನಡ — Native Kannada", "icon": "🇮🇳"},
            {"value": "Malayalam|ml-IN", "label": "Malayalam", "description": "മലയാളം — Native Malayalam", "icon": "🇮🇳"},
            {"value": "Marathi|mr-IN", "label": "Marathi", "description": "मराठी — Native Marathi", "icon": "🇮🇳"},
            {"value": "Gujarati|gu-IN", "label": "Gujarati", "description": "ગુજરાતી — Native Gujarati", "icon": "🇮🇳"},
            {"value": "Punjabi|pa-IN", "label": "Punjabi", "description": "ਪੰਜਾਬੀ — Native Punjabi", "icon": "🇮🇳"},
            {"value": "Odia|od-IN", "label": "Odia", "description": "ଓଡ଼ିଆ — Native Odia", "icon": "🇮🇳"},
        ],
        "allow_custom": False,
    },
    {
        "id": "voice_gender",
        "question": "Would you like a Male or Female voice?",
        "options": [
            {"value": "female", "label": "Female Voice", "description": "Clear and natural female voice", "icon": "👩"},
            {"value": "male", "label": "Male Voice", "description": "Clear and natural male voice", "icon": "👨"},
        ],
        "allow_custom": False,
    },
    {
        "id": "tasks",
        "question": "What should your agent do?",
        "multi_select": True,
        "options": [
            {"value": "Schedule appointments", "label": "Schedule appointments", "description": "Book meetings, schedule visits, confirm slots", "icon": "📅"},
            {"value": "Reschedule/cancel", "label": "Reschedule/cancel", "description": "Modify existing bookings and manage changes", "icon": "🔄"},
            {"value": "Answer FAQs", "label": "Answer FAQs", "description": "Handle common questions and inquiries", "icon": "❓"},
            {"value": "Route to staff", "label": "Route to staff", "description": "Transfer to the right department or person", "icon": "👥"},
            {"value": "Lead qualification", "label": "Lead qualification", "description": "Qualify and prioritize sales leads", "icon": "🎯"},
            {"value": "Customer support", "label": "Customer support", "description": "Resolve issues and troubleshoot problems", "icon": "🛠️"},
        ],
        "allow_custom": True,
        "custom_placeholder": "Something else...",
    },
    {
        "id": "tone",
        "question": "What tone should the agent use?",
        "options": [
            {"value": "Warm & Friendly", "label": "Warm & Friendly", "description": "Approachable and welcoming", "icon": "😊"},
            {"value": "Professional", "label": "Professional", "description": "Polished and businesslike", "icon": "💼"},
            {"value": "Empathetic", "label": "Empathetic", "description": "Understanding and compassionate", "icon": "💚"},
            {"value": "Concise", "label": "Concise", "description": "Direct and efficient", "icon": "⚡"},
        ],
        "allow_custom": False,
    },
    {
        "id": "business_info",
        "question": "Tell me about your business (name and what you do).",
        "type": "text",
        "placeholder": "e.g., 'Bright Dental — a family dental clinic in downtown Austin'",
    },
    {
        "id": "agent_name",
        "question": "What should we name your agent?",
        "type": "text",
        "placeholder": "e.g., Sarah, Alex, or leave blank for a default",
        "suggestions": ["Sarah", "Alex", "Jordan", "Maya", "Kai"],
    },
    {
        "id": "custom_instructions",
        "question": "Any specific instructions for your agent? (optional)",
        "type": "text",
        "placeholder": "e.g., 'Always offer a free consultation' or 'Operating hours are 9am-5pm EST'",
        "optional": True,
    },
]
