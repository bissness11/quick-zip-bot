import os
import logging
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
CONC_MAX = int(os.environ.get('CONC_MAX'))
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


@bot.on_message(filters.command('add'))
async def start_task_handler(client: Client, message: Message):
    """
    Notifies the bot that the user is going to send the media.
    """
    tasks[message.from_user.id] = {'files': [], 'total_size': 0}
    await message.reply_text('OK, send me some files.')


@bot.on_message(filters.private & filters.media)
async def add_file_handler(client: Client, message: Message):
    """
    Stores the ID, size, and filename of messages sent with files by this user.
    """
    if message.from_user.id in tasks:
        file_size = message.document.file_size
        file_name = message.document.file_name
        tasks[message.from_user.id]['files'].append((message.id, file_size, file_name))
        tasks[message.from_user.id]['total_size'] += file_size


@bot.on_message(filters.command('total'))
async def show_total_handler(client: Client, message: Message):
    """
    Displays the total file size and count for the user's current task.
    """
    if message.from_user.id not in tasks:
        await message.reply_text('No files added yet.')
        return

    total_size = tasks[message.from_user.id]['total_size']
    file_count = len(tasks[message.from_user.id]['files'])

    # Format file size human-readable
    human_size = f"{total_size / (1024 * 1024):.2f} MB" if total_size > 1024 * 1024 else f"{total_size / 1024:.2f} KB"

    await message.reply_text(f"Total size: {human_size}, Total files: {file_count}")


@bot.on_message(filters.command('zip'))
async def zip_handler(client: Client, message: Message):
    """
    Zips the media of messages corresponding to the IDs saved for this user in tasks.
    The zip filename must be provided in the command. Shows progress during zipping.
    """
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
