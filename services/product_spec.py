"""Service for parsing supplier product names into clean, brand-standard titles

and extracting structured duration, warranty, and account type badges.
"""

import functools
import re


class ProductSpecParser:
    BRAND_MAP = [
        (r"\bChat\s*gpt\b", "ChatGPT"),
        (r"\bChatgpt\b", "ChatGPT"),
        (r"\bClaude\b", "Claude"),
        (r"\bGemini\b", "Gemini"),
        (r"\bNetflix\b", "Netflix"),
        (r"\bCapcut\b", "CapCut"),
        (r"\bCanva\b", "Canva"),
        (r"\bNotion\b", "Notion"),
        (r"\bCoursera\b", "Coursera"),
        (r"\bCousera\b", "Coursera"),
        (r"\bDuolingo\b", "Duolingo"),
        (r"\bAutodesk\b", "Autodesk"),
        (r"\bJetBrains\b", "JetBrains"),
        (r"\bSnapchat\b", "Snapchat"),
        (r"\bTrading\s*View\b", "TradingView"),
        (r"\bTradingview\b", "TradingView"),
        (r"\bExpressVPN\b", "ExpressVPN"),
        (r"\bNord\s*Vpn\b", "NordVPN"),
        (r"\bApple\s*Tv\b", "Apple TV+"),
        (r"\bAmazon\s*prime\b", "Amazon Prime Video"),
        (r"\bWordwall\b", "Wordwall"),
        (r"\bQuizlet\b", "Quizlet"),
        (r"\bMeitu\b", "Meitu SVIP"),
        (r"\bShahid\b", "Shahid VIP"),
        (r"\bElevenlabs\b", "ElevenLabs AI"),
        (r"\bGamma\b", "Gamma AI"),
        (r"\bFramer\b", "Framer"),
        (r"\bFigma\b", "Figma"),
        (r"\bReplit\b", "Replit"),
        (r"\bZoom\b", "Zoom"),
        (r"\bScribd\b", "Scribd"),
        (r"\bUpToDate\b", "UpToDate"),
        (r"\bAMBOSS\b", "AMBOSS"),
        (r"\bHBO\s*Max\b", "HBO Max"),
        (r"\bPeacock\b", "Peacock TV"),
        (r"\bMicrosoft\s*365\b", "Microsoft 365"),
        (r"\bOffice\s*365\b", "Microsoft Office 365"),
        (r"\bWindows\s*10\b", "Windows 10 Pro"),
        (r"\bWindows\s*11\b", "Windows 11 Pro"),
        (r"\bWispr\s*Flow\b", "Wispr Flow"),
        (r"\bManus\b", "Manus AI"),
        (r"\bKiro\b", "Kiro AI"),
        (r"\bWink\b", "Wink AI"),
        (r"\bLovalbe\b", "Lovable AI"),
        (r"\biLovePdf\b", "iLovePDF"),
    ]

    @staticmethod
    @functools.lru_cache(maxsize=2048)
    def parse(raw_name: str) -> dict:
        """Parse raw product name and extract clean name and structured spec badges."""
        if not raw_name:
            return {
                "clean_name": "",
                "duration_ar": None,
                "duration_en": None,
                "warranty_ar": None,
                "warranty_en": None,
                "type_ar": None,
                "type_en": None,
            }

        name = raw_name.strip()

        # 1. Check for API Tokens / Credits
        token_tag = None
        m_tok = re.search(r"(\d+[MmkK]?)\s*(Token|Tokens|Credit|Credits)", name, re.IGNORECASE)
        if m_tok:
            token_tag = f"{m_tok.group(1).upper()} Token"

        # 2. Extract Warranty (pure text, no emojis)
        warranty_ar = None
        warranty_en = None
        if re.search(r"\b(NW|No\s*warranty|without\s*warranty)\b", name, re.IGNORECASE):
            warranty_ar = "بدون ضمان"
            warranty_en = "No Warranty"
        elif re.search(r"\b(FW|Full\s*warranty)\b", name, re.IGNORECASE):
            warranty_ar = "ضمان كامل"
            warranty_en = "Full Warranty"
        else:
            m_w = re.search(r"\(?W(\d+)([DH])\)?", name, re.IGNORECASE)
            if m_w:
                num, unit = m_w.group(1), m_w.group(2).upper()
                warranty_ar = f"ضمان {num} يوم" if unit == "D" else f"ضمان {num} ساعة"
                warranty_en = f"{num}D Warranty" if unit == "D" else f"{num}H Warranty"
            else:
                m_w2 = re.search(r"(\d+)\s*([dD]|day|month|year)s?\s*warranty", name, re.IGNORECASE)
                if m_w2:
                    num, unit = m_w2.group(1), m_w2.group(2).lower()
                    if "d" in unit:
                        warranty_ar = f"ضمان {num} يوم"
                        warranty_en = f"{num}D Warranty"
                    elif "month" in unit:
                        warranty_ar = f"ضمان {num} شهر"
                        warranty_en = f"{num}M Warranty"

        # 3. Extract Duration
        duration_ar = None
        duration_en = None
        name_no_tokens = re.sub(r"\d+[MmkK]?\s*(Token|Tokens|Credit|Credits)", "", name, flags=re.IGNORECASE)

        if re.search(r"\b(lifetime)\b", name, re.IGNORECASE):
            duration_ar = "مدى الحياة"
            duration_en = "Lifetime"
        else:
            m_dur = re.search(r"\b(\d+)\s*[-]?\s*(months?|mos?|m|yrs?|years?|days?|d)\b", name_no_tokens, re.IGNORECASE)
            if m_dur:
                val, unit = int(m_dur.group(1)), m_dur.group(2).lower()
                if unit in ("m", "mo", "mos", "month", "months"):
                    if val == 1:
                        duration_ar = "شهر واحد"
                        duration_en = "1 Month"
                    elif val == 12:
                        duration_ar = "سنة كاملة"
                        duration_en = "1 Year"
                    else:
                        duration_ar = f"{val} أشهر" if val <= 10 else f"{val} شهراً"
                        duration_en = f"{val} Months"
                elif unit in ("y", "yr", "yrs", "year", "years"):
                    duration_ar = f"{val} سنة" if val == 1 else f"{val} سنوات"
                    duration_en = f"{val} Year" if val == 1 else f"{val} Years"
                elif unit in ("d", "day", "days"):
                    duration_ar = f"{val} يوم"
                    duration_en = f"{val} Days"

        # 4. Extract Account / Delivery Type
        type_ar = None
        type_en = None
        if re.search(r"\b(link|url)\b", name, re.IGNORECASE) or "(link)" in name.lower():
            type_ar = "رابط تفعيل"
            type_en = "Activation Link"
        elif re.search(r"\b(invite|invitation|slot|family)\b", name, re.IGNORECASE):
            type_ar = "دعوة عائلية"
            type_en = "Family Invite"
        elif re.search(r"\b(key|retail)\b", name, re.IGNORECASE):
            type_ar = "مفتاح ترخيص"
            type_en = "License Key"
        elif token_tag:
            type_ar = token_tag
            type_en = token_tag
        elif re.search(r"\b(private|admin|ready\s*account)\b", name, re.IGNORECASE):
            type_ar = "حساب خاص"
            type_en = "Private Account"
        elif re.search(r"(\d+)\s*profile", name, re.IGNORECASE):
            num_prof = re.search(r"(\d+)\s*profile", name, re.IGNORECASE).group(1)
            type_ar = f"{num_prof} شاشات"
            type_en = f"{num_prof} Profiles"

        # 5. Clean Title
        clean = name
        clean = re.sub(r"[\U00010000-\U0010ffff]", "", clean)
        clean = re.sub(r"[\u2000-\u3300]", "", clean)
        clean = re.sub(r"<tg-emoji[^>]*>.*?</tg-emoji>", "", clean)
        clean = re.sub(r"\(?W\d+[DH]\)?", "", clean, flags=re.IGNORECASE)
        clean = re.sub(
            r"\b(FW|NW|Full\s*warranty|No\s*warranty|available|individual|official\s*subscriptions?|features?)\b",
            "",
            clean,
            flags=re.IGNORECASE,
        )
        clean = re.sub(r"\d+\s*[dDmM]\s*warranty", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\(\s*\d+[dD]\s*warranty\s*\)", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\(\s*(momo pay|Go pay|Apple pay|ready\s*account)\s*\)", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\b(momo pay|Go pay|Apple pay|Gmail)\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\b(ready\s*account|link|access)\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\b\d+\s*(months?|yrs?|years?)\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\b(12M|6M|3M|1M|18M|7D)\b", "", clean)
        clean = re.sub(r"–\s*\d+\s*(month|year)s?", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"—\s*\d+\s*(year|month)s?", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\d+\s*profiles?", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\d+\s*Devices?", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\b(Slot|Admin|Key)\s*[-:]?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"-\s*[A-Za-z0-9\s]+1M.*$", "", clean)
        clean = re.sub(r"\(.*?\)", "", clean)
        clean = re.sub(r"[-–—:–]", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()

        # Re-apply standardized brand name if found
        for pat, brand in ProductSpecParser.BRAND_MAP:
            if re.search(pat, clean, re.IGNORECASE):
                mods = []
                if re.search(r"\b(Plus\+?)\b", clean, re.IGNORECASE):
                    mods.append("Plus")
                if re.search(r"\bPro\b", clean, re.IGNORECASE):
                    mods.append("Pro")
                if re.search(r"\bPremium\b", clean, re.IGNORECASE):
                    mods.append("Premium")
                if re.search(r"\b(4K|UHD)\b", clean, re.IGNORECASE):
                    mods.append("4K")
                if re.search(r"\bFamily\b", clean, re.IGNORECASE):
                    mods.append("Family")
                if re.search(r"\b(Edu|Education)\b", clean, re.IGNORECASE):
                    mods.append("Education")
                if re.search(r"\bBusiness\b", clean, re.IGNORECASE):
                    mods.append("Business")
                if re.search(r"\bSuper\b", clean, re.IGNORECASE):
                    mods.append("Super")
                if re.search(r"\bAPI\b", clean, re.IGNORECASE):
                    mods.append("API")
                if re.search(r"\bDrive\s*5TB\b", clean, re.IGNORECASE):
                    mods.append("+ 5TB Cloud")
                if re.search(r"\b(link|url)\b", name, re.IGNORECASE) or "(link)" in name.lower():
                    mods.append("(رابط تفعيل)")
                mod_str = " ".join(dict.fromkeys(mods))
                for m in mods:
                    if m.lower() in brand.lower():
                        mod_str = mod_str.replace(m, "").strip()
                clean = f"{brand} {mod_str}".strip()
                break

        return {
            "clean_name": clean,
            "duration_ar": duration_ar,
            "duration_en": duration_en,
            "warranty_ar": warranty_ar,
            "warranty_en": warranty_en,
            "type_ar": type_ar,
            "type_en": type_en,
        }

    BRAND_FOLDERS = [
        # AI & Chatbots
        {"key": "chatgpt", "category": "AI & Chatbots", "title_en": "ChatGPT", "title_ar": "ChatGPT", "icon": "🤖", "custom_emoji_id": "5465366406979267927", "priority": 1, "patterns": [r"\bchat\s*gpt\b", r"\bgpt\b"]},
        {"key": "gemini", "category": "AI & Chatbots", "title_en": "Google Gemini", "title_ar": "Google Gemini", "icon": "✨", "custom_emoji_id": "5465366406979267926", "priority": 2, "patterns": [r"\bgemini\b"]},
        {"key": "claude", "category": "AI & Chatbots", "title_en": "Claude AI", "title_ar": "Claude AI", "icon": "🧠", "custom_emoji_id": "5368324170671202286", "priority": 3, "patterns": [r"\bclaude\b"]},
        {"key": "codex", "category": "AI & Chatbots", "title_en": "Codex API", "title_ar": "Codex API", "icon": "💻", "custom_emoji_id": "5465366406979267930", "priority": 4, "patterns": [r"\bcodex\b"]},
        {"key": "gamma", "category": "AI & Chatbots", "title_en": "Gamma AI", "title_ar": "Gamma AI", "icon": "⚡", "custom_emoji_id": "5465366406979267929", "priority": 5, "patterns": [r"\bgamma\b"]},
        {"key": "elevenlabs", "category": "AI & Chatbots", "title_en": "ElevenLabs", "title_ar": "ElevenLabs", "icon": "🎙️", "custom_emoji_id": "5465366406979267931", "priority": 6, "patterns": [r"\belevenlabs\b"]},
        {"key": "grok", "category": "AI & Chatbots", "title_en": "Super Grok", "title_ar": "Super Grok", "icon": "⚡", "custom_emoji_id": "5465366406979267929", "priority": 7, "patterns": [r"\bgrok\b"]},
        {"key": "cursor", "category": "AI & Chatbots", "title_en": "Cursor Pro", "title_ar": "Cursor Pro", "icon": "💻", "custom_emoji_id": "5465366406979267930", "priority": 8, "patterns": [r"\bcursor\b"]},
        {"key": "lovable", "category": "AI & Chatbots", "title_en": "Lovable AI", "title_ar": "Lovable AI", "icon": "❤️", "custom_emoji_id": "5465366406979267926", "priority": 9, "patterns": [r"\blova[bl]e\b", r"\blovalbe\b", r"\blovable\b"]},
        {"key": "manus", "category": "AI & Chatbots", "title_en": "Manus AI", "title_ar": "Manus AI", "icon": "🤖", "custom_emoji_id": "5465366406979267927", "priority": 10, "patterns": [r"\bmanus\b"]},
        {"key": "kiro", "category": "AI & Chatbots", "title_en": "Kiro AI", "title_ar": "Kiro AI", "icon": "⚡", "custom_emoji_id": "5465366406979267929", "priority": 11, "patterns": [r"\bkiro\b"]},
        {"key": "wispr", "category": "AI & Chatbots", "title_en": "Wispr Flow", "title_ar": "Wispr Flow", "icon": "🎙️", "custom_emoji_id": "5465366406979267931", "priority": 12, "patterns": [r"\bwispr\b"]},
        {"key": "magic_patterns", "category": "AI & Chatbots", "title_en": "Magic Patterns", "title_ar": "Magic Patterns", "icon": "🎨", "custom_emoji_id": "5465366406979267932", "priority": 13, "patterns": [r"\bmagic\s*patterns\b"]},

        # Streaming & Entertainment
        {"key": "netflix", "category": "Streaming & Entertainment", "title_en": "Netflix", "title_ar": "Netflix", "icon": "🎬", "custom_emoji_id": "5465366406979267934", "priority": 1, "patterns": [r"\bnetflix\b"]},
        {"key": "hbo_max", "category": "Streaming & Entertainment", "title_en": "HBO Max", "title_ar": "HBO Max", "icon": "🍿", "custom_emoji_id": "5465366406979267936", "priority": 2, "patterns": [r"\bhbo\b", r"\bhbomax\b"]},
        {"key": "amazon_prime", "category": "Streaming & Entertainment", "title_en": "Amazon Prime Video", "title_ar": "Amazon Prime Video", "icon": "📦", "custom_emoji_id": "5465366406979267938", "priority": 3, "patterns": [r"\bamazon\s*prime\b", r"\bprime\s*video\b"]},
        {"key": "apple_tv", "category": "Streaming & Entertainment", "title_en": "Apple TV+", "title_ar": "Apple TV+", "icon": "🍎", "custom_emoji_id": "5465366406979267937", "priority": 4, "patterns": [r"\bapple\s*tv\b"]},
        {"key": "peacock", "category": "Streaming & Entertainment", "title_en": "Peacock TV", "title_ar": "Peacock TV", "icon": "🦚", "custom_emoji_id": "5465366406979267935", "priority": 5, "patterns": [r"\bpeacock\b"]},
        {"key": "paramount", "category": "Streaming & Entertainment", "title_en": "Paramount+", "title_ar": "Paramount+", "icon": "⛰️", "custom_emoji_id": "5465366406979267934", "priority": 6, "patterns": [r"\bparamount\b"]},
        {"key": "spotify", "category": "Streaming & Entertainment", "title_en": "Spotify Premium", "title_ar": "Spotify Premium", "icon": "🎵", "custom_emoji_id": "5465366406979267948", "priority": 7, "patterns": [r"\bspotify\b"]},
        {"key": "shahid", "category": "Streaming & Entertainment", "title_en": "Shahid VIP", "title_ar": "Shahid VIP", "icon": "🍿", "custom_emoji_id": "5465366406979267936", "priority": 8, "patterns": [r"\bshahid\b"]},

        # Design & Creative
        {"key": "canva", "category": "Design & Creative", "title_en": "Canva Pro", "title_ar": "Canva Pro", "icon": "🖌️", "custom_emoji_id": "5465366406979267952", "priority": 1, "patterns": [r"\bcanva\b"]},
        {"key": "capcut", "category": "Design & Creative", "title_en": "CapCut Pro", "title_ar": "CapCut Pro", "icon": "✂️", "custom_emoji_id": "5465366406979267957", "priority": 2, "patterns": [r"\bcapcut\b"]},
        {"key": "adobe_express", "category": "Design & Creative", "title_en": "Adobe Express", "title_ar": "Adobe Express", "icon": "🔴", "custom_emoji_id": "5465366406979267953", "priority": 3, "patterns": [r"\badobe\b"]},
        {"key": "autodesk", "category": "Design & Creative", "title_en": "Autodesk", "title_ar": "Autodesk", "icon": "📐", "custom_emoji_id": "5465366406979267954", "priority": 4, "patterns": [r"\bautodesk\b"]},
        {"key": "figma", "category": "Design & Creative", "title_en": "Figma", "title_ar": "Figma", "icon": "🎨", "custom_emoji_id": "5465366406979267954", "priority": 5, "patterns": [r"\bfigma\b"]},
        {"key": "framer", "category": "Design & Creative", "title_en": "Framer", "title_ar": "Framer", "icon": "🖼️", "custom_emoji_id": "5465366406979267955", "priority": 6, "patterns": [r"\bframer\b"]},
        {"key": "envato", "category": "Design & Creative", "title_en": "Envato Elements", "title_ar": "Envato Elements", "icon": "🍃", "custom_emoji_id": "5465366406979267952", "priority": 7, "patterns": [r"\benvato\b"]},
        {"key": "mobbin", "category": "Design & Creative", "title_en": "Mobbin", "title_ar": "Mobbin", "icon": "📱", "custom_emoji_id": "5465366406979267954", "priority": 8, "patterns": [r"\bmobbin\b"]},
        {"key": "meitu", "category": "Design & Creative", "title_en": "Meitu SVIP", "title_ar": "Meitu SVIP", "icon": "✨", "custom_emoji_id": "5465366406979267926", "priority": 9, "patterns": [r"\bmeitu\b"]},
        {"key": "descript", "category": "Design & Creative", "title_en": "Descript", "title_ar": "Descript", "icon": "🎙️", "custom_emoji_id": "5465366406979267931", "priority": 10, "patterns": [r"\bdescript\b", r"\bsupercut\b"]},
        {"key": "wink", "category": "Design & Creative", "title_en": "Wink AI", "title_ar": "Wink AI", "icon": "😉", "custom_emoji_id": "5465366406979267926", "priority": 11, "patterns": [r"\bwink\b"]},

        # Office & Productivity
        {"key": "office365", "category": "Office & Productivity", "title_en": "Microsoft 365 / Office", "title_ar": "Microsoft 365 / Office", "icon": "💼", "custom_emoji_id": None, "priority": 1, "patterns": [r"\bmicrosoft\s*365\b", r"\boffice\s*365\b", r"\bmicrosoft\s*office\b"]},

        # Productivity
        {"key": "notion", "category": "Productivity", "title_en": "Notion", "title_ar": "Notion", "icon": "📝", "custom_emoji_id": "5465366406979267956", "priority": 1, "patterns": [r"\bnotion\b"]},
        {"key": "miro", "category": "Productivity", "title_en": "Miro", "title_ar": "Miro", "icon": "📋", "custom_emoji_id": "5465366406979267956", "priority": 2, "patterns": [r"\bmiro\b"]},
        {"key": "linear", "category": "Productivity", "title_en": "Linear", "title_ar": "Linear", "icon": "🎯", "custom_emoji_id": "5465366406979267956", "priority": 3, "patterns": [r"\blinear\b"]},
        {"key": "brain_fm", "category": "Productivity", "title_en": "Brain.fm", "title_ar": "Brain.fm", "icon": "🎧", "custom_emoji_id": "5465366406979267948", "priority": 4, "patterns": [r"\bbrain\.fm\b"]},
        {"key": "tradingview", "category": "Productivity", "title_en": "TradingView", "title_ar": "TradingView", "icon": "📈", "custom_emoji_id": "5465366406979267956", "priority": 5, "patterns": [r"\btrading\s*view\b"]},

        # Software Keys
        {"key": "windows", "category": "Software Keys", "title_en": "Windows Licenses", "title_ar": "Windows Licenses", "icon": "🪟", "custom_emoji_id": None, "priority": 1, "patterns": [r"\bwindows\b"]},
        {"key": "jetbrains", "category": "Software Keys", "title_en": "JetBrains", "title_ar": "JetBrains", "icon": "💻", "custom_emoji_id": "5465366406979267930", "priority": 2, "patterns": [r"\bjetbrains\b"]},
        {"key": "replit", "category": "Software Keys", "title_en": "Replit Core", "title_ar": "Replit Core", "icon": "💻", "custom_emoji_id": "5465366406979267930", "priority": 3, "patterns": [r"\breplit\b"]},
        {"key": "warp", "category": "Software Keys", "title_en": "Warp / Railway", "title_ar": "Warp / Railway", "icon": "⚙️", "custom_emoji_id": None, "priority": 4, "patterns": [r"\bwarp\b", r"\brailway\b"]},

        # Education
        {"key": "coursera", "category": "Education", "title_en": "Coursera", "title_ar": "Coursera", "icon": "🎓", "custom_emoji_id": None, "priority": 1, "patterns": [r"\bcours?era\b"]},
        {"key": "duolingo", "category": "Education", "title_en": "Duolingo Super", "title_ar": "Duolingo Super", "icon": "🦉", "custom_emoji_id": None, "priority": 2, "patterns": [r"\bduolingo\b"]},
        {"key": "ilovepdf", "category": "Education", "title_en": "iLovePDF", "title_ar": "iLovePDF", "icon": "📄", "custom_emoji_id": None, "priority": 3, "patterns": [r"\bilovepdf\b"]},
        {"key": "quizlet", "category": "Education", "title_en": "Quizlet", "title_ar": "Quizlet", "icon": "📚", "custom_emoji_id": None, "priority": 4, "patterns": [r"\bquizlet\b"]},
        {"key": "wordwall", "category": "Education", "title_en": "Wordwall", "title_ar": "Wordwall", "icon": "🎮", "custom_emoji_id": None, "priority": 5, "patterns": [r"\bwordwall\b"]},
        {"key": "scribd", "category": "Education", "title_en": "Scribd", "title_ar": "Scribd", "icon": "📖", "custom_emoji_id": None, "priority": 6, "patterns": [r"\bscribd\b"]},
        {"key": "edx", "category": "Education", "title_en": "edX", "title_ar": "edX", "icon": "🎓", "custom_emoji_id": None, "priority": 7, "patterns": [r"\bedx\b"]},

        # VPN & Security
        {"key": "nordvpn", "category": "VPN & Security", "title_en": "NordVPN", "title_ar": "NordVPN", "icon": "🛡️", "custom_emoji_id": "5465366406979267942", "priority": 1, "patterns": [r"\bnord\b"]},
        {"key": "protonvpn", "category": "VPN & Security", "title_en": "Proton VPN", "title_ar": "Proton VPN", "icon": "🔒", "custom_emoji_id": "5465366406979267945", "priority": 2, "patterns": [r"\bproton\b"]},
        {"key": "avira", "category": "VPN & Security", "title_en": "Avira Prime", "title_ar": "Avira Prime", "icon": "🛡️", "custom_emoji_id": "5465366406979267942", "priority": 3, "patterns": [r"\bavira\b"]},
        {"key": "hma", "category": "VPN & Security", "title_en": "HMA VPN", "title_ar": "HMA VPN", "icon": "🫏", "custom_emoji_id": "5465366406979267946", "priority": 4, "patterns": [r"\bhma\b"]},

        # Communication
        {"key": "zoom", "category": "Communication", "title_en": "Zoom", "title_ar": "Zoom", "icon": "💬", "custom_emoji_id": None, "priority": 1, "patterns": [r"\bzoom\b"]},

        # Accounts & Email
        {"key": "gmail", "category": "Accounts & Email", "title_en": "Gmail Accounts", "title_ar": "Gmail Accounts", "icon": "📧", "custom_emoji_id": None, "priority": 1, "patterns": [r"\bgmail\b"]},

        # Social Media
        {"key": "snapchat", "category": "Social Media", "title_en": "Snapchat Plus", "title_ar": "Snapchat Plus", "icon": "📱", "custom_emoji_id": None, "priority": 1, "patterns": [r"\bsnapchat\b"]},
    ]

    @classmethod
    def get_folder_info(cls, raw_name: str, custom_name: str = None, category: str = None) -> dict:
        """Detect the brand folder identity and sorting priority for a product."""
        search_str = f"{custom_name or ''} {raw_name or ''}".lower()
        for folder in cls.BRAND_FOLDERS:
            for pat in folder["patterns"]:
                if re.search(pat, search_str, re.IGNORECASE):
                    return {
                        "folder_key": folder["key"],
                        "folder_title_en": folder["title_en"],
                        "folder_title_ar": folder["title_ar"],
                        "icon": folder["icon"],
                        "custom_emoji_id": folder.get("custom_emoji_id"),
                        "priority": folder.get("priority", 50),
                        "matched": True,
                    }

        # Fallback for unmapped products
        specs = cls.parse(raw_name or "")
        base_clean = specs.get("clean_name") or custom_name or raw_name or "Digital Product"
        base_clean = re.sub(r"[\(\[].*?[\)\]]", "", base_clean).strip()
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", base_clean.lower()).strip("_") or "other"
        return {
            "folder_key": slug[:32],
            "folder_title_en": base_clean,
            "folder_title_ar": base_clean,
            "icon": "📦",
            "custom_emoji_id": None,
            "priority": 99,
            "matched": False,
        }

    @classmethod
    def get_clean_variant_title(cls, raw_name: str, custom_name: str = None, specs: dict = None) -> tuple[str, str]:
        """Generate clean, differentiated variant titles (English in all languages).
        If custom_name is explicitly set in database, it takes 100% precedence.
        """
        if custom_name and str(custom_name).strip():
            c_val = str(custom_name).strip()
            return (c_val, c_val)
        if not specs:
            specs = cls.parse(raw_name or "")
        raw_lower = (raw_name or "").lower()
        search_lower = f"{custom_name or ''} {raw_name or ''}".lower()
        dur_en = specs.get("duration_en") or ""
        type_en = specs.get("type_en") or ""

        # 1. Google Gemini Specialization
        if "gemini" in search_lower:
            if "5tb" in search_lower or "drive" in search_lower or "storage" in search_lower:
                title = f"Gemini Pro + 5TB Cloud · {dur_en or '18 Months'}"
                return (title, title)
            if "pro" in search_lower or "link" in search_lower or "رابط" in search_lower:
                title = f"Gemini Pro · {dur_en or '18 Months'} (Activation Link)"
                return (title, title)
            title = f"Gemini Pro · {dur_en or '18 Months'}"
            return (title, title)

        # 2. CapCut Pro Specialization
        if "capcut" in search_lower:
            d_en = dur_en or ("7 Days" if "7d" in search_lower or "7 day" in search_lower else ("6 Months" if "6m" in search_lower or "6 month" in search_lower else "1 Month"))
            title = f"CapCut Pro · {d_en}"
            return (title, title)

        # 3. ChatGPT Specialization
        if "chatgpt" in search_lower or "chat gpt" in search_lower:
            sub = "Private Account"
            if "gopay" in search_lower or "go pay" in search_lower:
                sub = "Private (GoPay)"
            elif "momo" in search_lower:
                sub = "Private (MoMo)"
            elif "apple pay" in search_lower:
                sub = "Private (Apple)"
            d_en = dur_en or "1 Month"
            title = f"ChatGPT Plus · {d_en} ({sub})"
            return (title, title)

        # 4. Netflix Specialization
        if "netflix" in search_lower:
            prof = "5 Profiles"
            m_prof = re.search(r"(\d+)\s*profile", search_lower)
            if m_prof:
                prof = f"{m_prof.group(1)} Profiles"
            d_en = dur_en or "1 Month"
            title = f"Netflix Premium 4K · {d_en} ({prof})"
            return (title, title)

        # 5. Windows Specialization
        if "windows" in search_lower:
            ver = "11 Pro" if "11" in search_lower else "10 Pro"
            title = f"Windows {ver} · Lifetime (Retail Key)"
            return (title, title)

        # 6. Microsoft 365 / Office Specialization
        if "office" in search_lower or "microsoft 365" in search_lower:
            if "family" in search_lower:
                title = f"Microsoft 365 Family · {dur_en or '1 Year'} (Invite)"
            else:
                title = f"Microsoft Office 365 Plus · {dur_en or '1 Year'}"
            return (title, title)

        # 7. Zoom Specialization
        if "zoom" in search_lower:
            d_en = dur_en or "1 Month"
            title = f"Zoom Pro · {d_en} (100 Participants)"
            return (title, title)

        # 8. Claude API Specialization
        if "claude" in search_lower and ("api" in search_lower or "token" in search_lower or "$" in search_lower):
            tok = type_en or (re.search(r"(\$\d+|\d+[MmkK]?\s*Token)", raw_name, re.IGNORECASE).group(1) if re.search(r"(\$\d+|\d+[MmkK]?\s*Token)", raw_name, re.IGNORECASE) else "API")
            d_en = dur_en or ""
            suffix = f" · {d_en}" if d_en else ""
            title = f"Claude API {tok}{suffix}"
            return (title, title)

        # 9. Generic Fallback
        base_title = custom_name or specs.get("clean_name") or raw_name
        base_title = re.sub(r"[\(\[].*?[\)\]]", "", base_title).strip()
        parts = [base_title]
        if dur_en:
            parts.append(dur_en)
        if type_en and type_en.lower() not in base_title.lower():
            parts.append(f"({type_en})")

        title = " · ".join(parts)
        return (title, title)

    @classmethod
    def get_duration_weight(cls, duration_en: str = None, raw_name: str = None) -> int:
        """Return numeric sort weight in days (ascending order)."""
        s = f"{duration_en or ''} {raw_name or ''}".lower()
        if "lifetime" in s or "windows" in s or "retail" in s:
            return 99999
        if "2 yr" in s or "2 year" in s or "2yrs" in s:
            return 730
        if "18 m" in s or "18 month" in s or "18m" in s:
            return 540
        if "12 m" in s or "1 year" in s or "1 yr" in s or "12m" in s:
            return 365
        if "6 m" in s or "6 month" in s or "6m" in s:
            return 180
        if "5 m" in s or "5 month" in s:
            return 150
        if "3 m" in s or "3 month" in s or "3m" in s:
            return 90
        if "1 m" in s or "1 month" in s or "30 d" in s or "30 day" in s or "1m" in s:
            return 30
        if "25 d" in s or "20 d" in s:
            return 20
        if "10 d" in s or "9 d" in s:
            return 10
        if "7 d" in s or "7 day" in s or "7d" in s:
            return 7
        if "3 d" in s or "3 day" in s or "3d" in s:
            return 3
        if "2 d" in s or "2 day" in s or "2d" in s:
            return 2
        if "1 d" in s or "1 day" in s or "24h" in s or "12h" in s:
            return 1
        return 100  # standard fallback

    @classmethod
    def extract_clean_instructions(cls, description: str = None, description_ar: str = None, raw_name: str = "") -> dict:
        """Extract clean, step-by-step activation guidelines for customer post-purchase display."""
        desc_str = f"{description or ''} {raw_name or ''}".lower()

        # Case A: Activation Link / Google One / Gemini / Miro Link
        if "link" in desc_str or "url" in desc_str or "click to activate" in desc_str:
            return {
                "steps_en": [
                    "Open the delivered activation link in your web browser.",
                    "Sign in to your personal account and accept the subscription invite.",
                    "Enjoy full premium access instantly without requiring any VPN or credit card."
                ],
                "steps_ar": [
                    "افتح رابط التفعيل المعتمد المسلم بالأعلى في متصفحك.",
                    "سجل الدخول بحسابك الشخصي واضغط على تأكيد الانضمام للاشتراك.",
                    "تمتع بالميزات فورياً ومباشرة دون الحاجة لأي بطاقة بنكية أو VPN."
                ],
                "type": "activation_link"
            }

        # Case B: License Key / Windows / Software Keys
        if "key" in desc_str or "license" in desc_str or "retail" in desc_str:
            return {
                "steps_en": [
                    "Copy the official product activation key delivered above.",
                    "Go to your software or Windows Settings > System > Activation.",
                    "Enter the key and click Activate for permanent genuine activation."
                ],
                "steps_ar": [
                    "انسخ مفتاح التنشيط الأصلي المسلم بالأعلى.",
                    "توجه إلى إعدادات البرنامج أو النظام > التنشيط (Activation).",
                    "الصق المفتاح واضغط تنشيط لتأكيد الترخيص الدائم عبر الإنترنت."
                ],
                "type": "license_key"
            }

        # Case C: Account / Email & Password (with optional 2FA)
        has_2fa = ("2fa" in desc_str or "2fe" in desc_str or "otp" in desc_str)
        step3_en = "If a 2FA code is requested, open 2fa-auth.com to generate your one-time password." if has_2fa else "Change the account password and secure your profile after your initial login."
        step3_ar = "في حال طلب رمز تحقق، توجه إلى موقع 2fa-auth.com للحصول على رمز الـ OTP فورياً." if has_2fa else "قم بتغيير كلمة المرور وتأمين حسابك بعد تسجيل الدخول الأول."

        return {
            "steps_en": [
                "Sign in to the official service using the delivered email and password.",
                "Select your profile and verify your account access.",
                step3_en
            ],
            "steps_ar": [
                "سجل الدخول للخدمة الرسمية باستخدام البريد الإلكتروني وكلمة المرور المسلمة.",
                "اختر ملفك الشخصي وتأكد من صلاحية الوصول.",
                step3_ar
            ],
            "type": "account"
        }
