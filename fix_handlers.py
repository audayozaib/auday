import re
import os

def fix_handler_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Add MessageHandler import if not present
    if 'from pyrogram.handlers import MessageHandler' not in content:
        content = content.replace(
            'from pyrogram import Client, filters',
            'from pyrogram import Client, filters\nfrom pyrogram.handlers import MessageHandler, CallbackQueryHandler'
        )

    # Fix app.add_handler calls - pattern 1: simple case
    content = re.sub(
        r'app\.add_handler\(\s*filters\.',
        r'app.add_handler(MessageHandler(',
        content
    )

    # Fix app.add_handler calls - pattern 2: with filters.create
    pattern = r'app\.add_handler\(\s*filters\.create\(([^)]+)\)([^,]+),\s*(\w+)\s*\)'

    def replace_handler(match):
        filter_lambda = match.group(1)
        additional_filters = match.group(2)
        handler_name = match.group(3)
        return f'app.add_handler(MessageHandler({handler_name}, filters.create({filter_lambda}){additional_filters}))'

    content = re.sub(pattern, replace_handler, content)

    with open(filepath, 'w') as f:
        f.write(content)

    print(f"Fixed: {filepath}")

# Fix all handler files
handler_files = [
    'handlers/start.py',
    'handlers/add_channel.py',
    'handlers/manage_channels.py',
    'handlers/create_giveaway.py',
    'handlers/giveaway_callbacks.py',
    'handlers/dashboard.py',
    'handlers/help_support.py'
]

for filepath in handler_files:
    full_path = os.path.join('/tmp/cc-agent/58099855/project', filepath)
    if os.path.exists(full_path):
        fix_handler_file(full_path)
    else:
        print(f"Not found: {full_path}")
