import fitz  # PyMuPDF
import os

def extract_text_from_pdf(file_path: str) -> str:
    """Extracts text from a local PDF file."""
    text = ""
    try:
        with fitz.open(file_path) as pdf:
            for page in pdf:
                text += page.get_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

async def download_telegram_file(file_id: str, bot, save_path: str):
    """Helper to download a file from Telegram servers."""
    file = await bot.get_file(file_id)
    await file.download_to_drive(save_path)
    return save_path
