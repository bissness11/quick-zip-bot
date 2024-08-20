import os
import logging
from pathlib import Path
from shutil import rmtree
from functools import partial

import aiofiles
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import DownloadProgressError

# Load environment variables
load_dotenv()

API_ID = int(os.environ['API_ID'])
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 3))
STORAGE = Path('./files/')

# Set up logging
logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)

# Dictionary to keep track of tasks for every user
tasks = {}

# Initialize the bot
bot = Client('quick-zip-bot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Dictionary to keep track of download progress
download_progress = {}

def get_download_progress_keyboard(file_id=None, progress=0):
    if file_id:
        text = f"Downloading... {progress}%"
    else:
        text = "Downloading..."
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data="download_progress")]])

async def update_download_progress(client, message, file_id):
    while file_id in download_progress:
        try:
            progress = download_progress[file_id]
            await message.edit_reply_markup(get_download_progress_keyboard(file_id, progress))
            await asyncio.sleep(1)  # Update progress every second
        except Exception as e:
            logging.error(f"Error updating download progress for {file_id}: {e}")
            break

async def download_file(client, file_id, file_path):
    try:
        await client.download_media(file_id, file_path=file_path, progress=download_progress.setdefault(file_id, 0))
        del download_progress[file_id]
    except DownloadProgressError as e:
        logging.error(f"Download error for {file_id}: {e}")

@bot.on_message(filters.command('add'))
async def start_task_handler(client: Client, message: Message):
    """
    Notifies the bot that the user is going to send the media.
    """
    tasks[message.from_user.id] = []
    await message.reply_text('OK, send me some files. I will show you their download progress.',
                              reply_markup=get_download_progress_keyboard())

@bot.on_message(filters.private & filters.media)
async def add_file_handler(client: Client, message: Message):
    """
    Stores the ID of messages sent with files by this user and updates download progress.
    """
    if message.from_user.id in tasks:
        tasks[message.from_user.id].append(message.id)
        file_id = message.message_id
        file_path = STORAGE / f'{message.from_user.id}/{file_id}'
        download_task = get_running_loop().create_task(download_file(client, file_id, file_path))
        download_task.set_name(f"Download task {file_id}")

        update_progress_task = get_running_loop().create_task(update_download_progress(client, message, file_id))
        update_progress_task.set_name(f"Progress update task {file_id}")

@bot.on_message(filters.command('zip'))
async def zip_handler(client: Client, message: Message):
    """
    Zips the media of messages corresponding to the IDs saved for this user in tasks.
    The zip filename must be provided in the command.
    """
    # ... (rest of your zip_handler code)

# ... (rest of your code)

if __name__ == '__main__':
    bot.run()
