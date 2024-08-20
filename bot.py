import os
import logging
from pathlib import Path
from shutil import rmtree
from asyncio import get_running_loop
from functools import partial
import aiofiles
from pyrogram.types import Message, InlineKeyboardMarkup, CallbackQuery, InlineKeyboardButton
from dotenv import load_dotenv
from pyrogram import Client, filters

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


@bot.on_message(filters.command('add'))
async def start_task_handler(client: Client, message: Message):
    """Notifies the bot that the user is going to send the media."""
    tasks.setdefault(message.from_user.id, []).append(message)  # Use setdefault for efficient list creation
    await message.reply_text('OK, send me some files.')

@bot.on_message(filters.media)
async def handle_media(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in tasks:
        media = message.document or message.video or message.audio
        tasks[user_id].append(media)
        await asyncio.sleep(3)  # Delay for 3 seconds
        total_size = sum(file.file_size for file in tasks[user_id])
        total_size_mb = total_size / (1024 * 1024)  # Convert bytes to MB
        await message.reply_text(
            f"Received {len(tasks[user_id])} files, total size: {total_size_mb:.2f} MB"
        )


@bot.on_message(filters.private & filters.media)
async def add_file_handler(client: Client, message: Message):
    """
    Stores the ID of messages sent with files by this user.
    """
    if message.from_user.id in tasks:
        tasks[message.from_user.id].append(message)  # Store message object


@bot.on_message(filters.command('zip'))
async def zip_handler(client: Client, message: Message):
    progress = 0
    files = tasks.get(message.from_user.id, [])  # Use get with default to handle missing key
    total_files = len(files)

    # ... (rest of your code remains the same)
    root = STORAGE / f'{message.from_user.id}/'
    zip_name = root / (message.command[1] + '.zip')
    progress_msg = await message.reply_text('Zipping files... (0%)', reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton('Show Progress', callback_data='show_progress')]
    ]))

    async def download_files_async(messages, root):
        await download_files(messages, root)  # Assuming download_files works

    async def download_and_zip():
        nonlocal progress
        for file in files:
            # Download file
            messages = [await client.get_messages(message.chat.id, msg.message_id) for msg in file]
            progress += 1
            await progress_msg.edit_text(f'Downloading files... ({progress / total_files * 100:.2f}%)')

            # Zip files
            progress = 0
            await download_files_async(messages, root)  # Call the download function

            for file in os.listdir(root):
                await get_running_loop().run_in_executor(None, partial(add_to_zip, zip_name, root / file))
