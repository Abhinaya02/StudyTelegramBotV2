import re
import html

MAX_LEN = 3500

def to_telegram_html(text: str) -> str:
    """Passes through Gemini HTML output safely for Telegram HTML parse mode."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

def markdown_bold_to_html(text: str) -> str:
    """Converts **bold** markdown to <b>bold</b> HTML."""
    if not text:
        return ""
    # Convert bold markdown
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

def split_by_length(text: str, maxlen: int = MAX_LEN):
    """Yields chunks no longer than maxlen characters."""
    for i in range(0, len(text), maxlen):
        yield text[i:i + maxlen]
