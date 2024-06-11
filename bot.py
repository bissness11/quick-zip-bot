from functools import partial
from asyncio import get_running_loop
from shutil import rmtree
from pathlib import Path
import logging
import os
import time

from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message

from utils import download_files, add_to_zip

load_dotenv()

API_ID = os.environ['API_ID']
API_HASH = os.environ['API_HASH']
BOT_TOKEN = os.environ['BOT_TOKEN']
CONC_MAX = int(os.environ.get('CONC_MAX', 3))
STORAGE = Path('./files/')

logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(name)s: %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
    ]
)

# dict to keep track of tasks for every user
tasks: dict[int, list[int]] = {}

bot = Client(
    'quick-zip-bot', api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN
)


@bot.on_message(filters.command('start'))
async def start_cmd_handler(client, message: Message):
    """
    Sends a welcome message to the user.
    """
    await message.reply_text('Hello! Use /add to start sending files.')


@bot.on_message(filters.command('add'))
async def start_task_handler(client, message: Message):
    """
    Notifies the bot that the user is going to send the media.
    """
    tasks[message.from_user.id] = []

    await message.reply_text('OK, send me some files.')


@bot.on_message(filters.document | filters.video | filters.audio | filters.photo & filters.create(lambda _, __, m: m.from_user.id in tasks))
async def add_file_handler(client, message: Message):
    """
    Stores the ID of messages sent with files by this user.
    """
    tasks[message.from_user.id].append(message.id)
    await message.reply_text(f'File received: {message.document.file_name}')


@bot.on_message(filters.command('zip'))
async def zip_handler(client, message: Message):
    """
    Zips the media of messages corresponding to the IDs saved for this user in
    tasks. The zip filename must be provided in the command.
    """
    user_id = message.from_user.id
    if user_id not in tasks:
        await message.reply_text('You must use /add first.')
        return

    if not tasks[user_id]:
        await message.reply_text('You must send me some files first.')
        return

    zip_name_match = message.text.split(' ', 1)
    if len(zip_name_match) < 2:
        await message.reply_text('You must provide a name for the zip file.')
        return

    zip_name = zip_name_match[1]
    messages = await client.get_messages(chat_id=user_id, message_ids=tasks[user_id])
    zip_size = sum([msg.document.file_size for msg in messages])

    if zip_size > 1024 * 1024 * 2000:  # zip_size > 1.95 GB approximately
        await message.reply_text('Total filesize must not exceed 2.0 GB.')
        return

    root = STORAGE / f'{user_id}/'
    zip_file_name = root / (zip_name + '.zip')

    # Inform the user about the start of the zipping process
    progress_message = await message.reply_text('Starting to download and zip your files...')

    try:
        start_time = time.time()
        async for file in download_files(messages, CONC_MAX, root, progress_message):
            await get_running_loop().run_in_executor(None, partial(add_to_zip, zip_file_name, file))
            await progress_message.edit_text(f'Zipping: {file.name}')

        end_time = time.time()
        duration = end_time - start_time

        await message.reply_document(zip_file_name, caption=f'Done! Zipped in {duration:.2f} seconds.')

    except Exception as e:
        logging.error(f"Error while zipping files: {e}")
        await message.reply_text(f'An error occurred: {e}')

    finally:
        await get_running_loop().run_in_executor(None, rmtree, STORAGE / str(user_id))
        tasks.pop(user_id)
        await progress_message.delete()


@bot.on_message(filters.command('cancel'))
async def cancel_handler(client, message: Message):
    """
    Cleans the list of tasks for the user.
    """
    try:
        tasks.pop(message.from_user.id)
    except KeyError:
        pass

    await message.reply_text('Canceled zip. For a new one, use /add.')


if __name__ == '__main__':
    bot.run()
