import os
from pypdf import PdfReader

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts text from a local PDF file."""
    text = ""
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

async def download_telegram_file(file_id: str, bot, save_path: str):
    """Helper to download a file from Telegram servers."""
    file = await bot.get_file(file_id)
    await file.download_to_drive(save_path)
    return save_path
