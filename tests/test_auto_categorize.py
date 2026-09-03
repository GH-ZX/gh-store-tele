import pytest
from models.batstore_product import auto_categorize


class TestAutoCategorize:
    def test_chatgpt(self):
        assert auto_categorize("ChatGPT Plus 1 Month") == "AI & Chatbots"

    def test_claude(self):
        assert auto_categorize("Claude Pro Subscription") == "AI & Chatbots"

    def test_vpn(self):
        assert auto_categorize("NordVPN 1 Year") == "VPN & Security"

    def test_netflix(self):
        assert auto_categorize("Netflix Premium") == "Streaming & Entertainment"

    def test_snapchat(self):
        assert auto_categorize("Snapchat Plus") == "Social Media"

    def test_notion(self):
        assert auto_categorize("Notion Plus Plan") == "Productivity"

    def test_figma(self):
        assert auto_categorize("Figma Professional") == "Design & Creative"

    def test_microsoft_office(self):
        assert auto_categorize("Microsoft Office 365") == "Office & Productivity"

    def test_windows(self):
        assert auto_categorize("Windows 11 Pro Key") == "Software Keys"

    def test_zoom(self):
        assert auto_categorize("Zoom Business Plan") == "Communication"

    def test_unknown(self):
        assert auto_categorize("Random Product XYZ") == "Other"

    def test_case_insensitive(self):
        assert auto_categorize("CHATGPT PLUS") == "AI & Chatbots"

    def test_partial_match(self):
        assert auto_categorize("Surfshark VPN Starter") == "VPN & Security"
