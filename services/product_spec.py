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
            m_dur = re.search(r"\b(\d+)\s*(months?|m|yrs?|years?|days?|d)\b", name_no_tokens, re.IGNORECASE)
            if m_dur:
                val, unit = int(m_dur.group(1)), m_dur.group(2).lower()
                if unit in ("m", "month", "months"):
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
