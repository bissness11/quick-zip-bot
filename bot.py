import os
import logging
import time
import zipfile
from pathlib import Path
from shutil import rmtree
from asyncio import get_running_loop, gather
from functools import partial

import aiofiles
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# Load environment variables
load_dotenv()

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 30))
STORAGE = Path('./files/')

# Set up logging
logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)

# Dictionary to keep track of tasks (files and total size)
tasks = {}

# Initialize the bot
bot = Client('quick-zip-bot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def add_to_zip(zip_file, file_path):
    with zipfile.ZipFile(zip_file, 'a') as zipf:
        zipf.write(file_path, arcname=file_path.name)

async def progress_bar(current, total, message, progress_bar):
    percentage = int((current / total) * 100)
    progress_bar_text = f"Zipping: {percentage}% ({current:.2f}/{total:.2f} MB)"
    await message.edit_text(progress_bar_text)

async def download_file(client, file_id, file_path):
    await client.download_media(file_id, file_path=file_path)

async def zip_handler(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text('Please provide a name for the zip file.')
        return

    if message.from_user.id not in tasks:
        await message.reply_text('You must use /add first.')
        return

    if not tasks[message.from_user.id]['files']:
        await message.reply_text('You must send me some files first.')
        return

    zip_name = f'{message.command[1]}.zip'
    total_size = tasks[message.from_user.id]['total_size']

    if total_size > 1024 * 1024 * 2000:  # zip_size > 1.95 GB approximately
        await message.reply_text('Total filesize must not exceed 2.0 GB.')
        return

    root = STORAGE / f'{message.from_user.id}/'
    zip_path = root / zip_name

    # Create root directory if it doesn't exist
    root.mkdir(parents=True, exist_ok=True)

    progress_bar_msg = await message.reply_text("Zipping files...")

    async with aiofiles.open(zip_path, 'wb') as zip_file:
        current_size = 0
        for file_id, file_size, file_name in tasks[message.from_user.id]['files']:
            file_path = root / file_name
            await download_file(client, file_id, file_path)
            add_to_zip(zip_file, file_path)
            current_size += file_size
            await progress_bar(current_size, total_size, progress_bar_msg, progress_bar)

    await message.reply_document(zip_path)
    await progress_bar_msg.delete()

    await get_running_loop().run_in_executor(None, rmtree, root)
    tasks.pop(message.from_user.id)

# ... rest of your code ...

if __name__ == '__main__':
    bot.run()
