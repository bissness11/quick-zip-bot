import os
import logging
from pathlib import Path
from shutil import rmtree
from asyncio import get_running_loop
from functools import partial
import aiofiles
from pyrogram.types import Message, InlineKeyboardMarkup, CallbackQuery,InlineKeyboardButton
from dotenv import load_dotenv
from pyrogram import Client, filters
from utils import download_files, add_to_zip  # Assuming these are compatible with Pyrogram
import asyncio
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
    tasks[((message.from_user.id))] = []
    await message.reply_text('OK, send me some files.')

@bot.on_message(filters.media)
async def handle_media(client: Client, message: Message):
    user_id = ((message.from_user.id))
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
        tasks[message.from_user.id].append(message.id)




@bot.on_message(filters.command('zip'))
async def zip_handler(client: Client, message: Message):
    """
    Zips the media of messages corresponding to the IDs saved for this user in
    tasks. The zip filename must be provided in the command.
    """
    if len(message.command) < 2:
        await message.reply_text('Please provide a name for the zip file.')
        return

    if message.from_user.id not in tasks:
        await message.reply_text('You must use /add first.')
        return

    if not tasks[message.from_user.id]:
        await message.reply_text('You must send me some files first.')
        return

    messages = [await client.get_messages(message.chat.id, msg_id) for msg_id in tasks[message.from_user.id]]
    zip_size = sum([msg.document.file_size for msg in messages if msg.document])

    if zip_size > 1024 * 1024 * 2000:  # zip_size > 1.95 GB approximately
        await message.reply_text('Total filesize must not exceed 2.0 GB.')
        return

    root = STORAGE / f'{message.from_user.id}/'
    zip_name = root / (message.command[1] + '.zip')

    # Create root directory if it doesn't exist
    root.mkdir(parents=True, exist_ok=True)
    # ... (rest of your code remains the same)

    # Create a progress message
    progress_msg = await message.reply_text('Zipping files... (0%)')

    # Zip files with progress
    total_files = len(messages)
    progress = 0
    for file in os.listdir(root):
        await get_running_loop().run_in_executor(None, partial(add_to_zip, zip_name, root / file))
        progress += 1
        await progress_msg.edit_text(f'Zipping files... ({progress / total_files * 100:.2f}%)')

    # Add a button to show progress
    inline_keyboard = [[InlineKeyboardButton("Show Progress", callback_data='show_progress')]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)
    await progress_msg.edit_text(f'Zipping files... (100%)', reply_markup=reply_markup)

    # ... (rest of your code remains the same)

@bot.on_callback_query(filters.regex('show_progress'))
async def show_progress(client: Client, callback_query: CallbackQuery):
    # Get the progress message
    progress_msg = callback_query.message

    # Get the current progress
    progress_text = progress_msg.text
    progress = float(progress_text.split('(')[1].split('%')[0])

    # Calculate the total file size of the zip file
    total_size = sum([msg.document.file_size for msg in messages if msg.document])
    total_size_mb = total_size / (1024 * 1024)  # Convert bytes to MB

    # Show the progress and total file size
    await progress_msg.edit_text(f'Zipping files... ({progress:.2f}%) - Total size: {total_size_mb:.2f} MB')

@bot.on_message(filters.command('help'))
async def start_handler(client: Client, message: Message):
    """
    Handles the /start command, displaying a welcome message with a group join button.
    """
    # Replace 'your_group_link' with your actual group link
    inline_keyboard = [[InlineKeyboardButton("Join Our Channel", url="https://t.me/animecolony")]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard)
    await message.reply_text("Welcome to our bot! Available commands.\n /start \n /help \n /add (send before Adding files \n /zip (/zip filename of the zip file without extension)) \n", reply_markup=reply_markup)


@bot.on_message(filters.command('cancel'))
async def cancel_handler(client: Client, message: Message):
    """
    Cleans the list of tasks for the user.
    """
    tasks.pop(message.from_user.id, None)
    await message.reply_text('Canceled zip. For a new one, use /add.')


if __name__ == '__main__':
    bot.run()
