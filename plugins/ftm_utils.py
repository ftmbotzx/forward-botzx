import re
import logging
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait
import asyncio

logger = logging.getLogger(__name__)

async def safe_copy_message(from_chat_id, to_chat_id, message_id, bot, custom_caption=None, protect_content=False, reply_markup=None):
    """
    Safely copy a message with error handling
    
    Returns:
        tuple: (success: bool, result: str/object)
    """
    try:
        result = await bot.copy_message(
            chat_id=to_chat_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
            caption=custom_caption,
            protect_content=protect_content,
            reply_markup=reply_markup
        )
        return True, result
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        # Retry once after flood wait
        try:
            result = await bot.copy_message(
                chat_id=to_chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
                caption=custom_caption,
                protect_content=protect_content,
                reply_markup=reply_markup
            )
            return True, result
        except Exception as retry_err:
            return False, f"Retry failed after FloodWait: {retry_err}"
    except UnicodeDecodeError as unicode_err:
        logger.error(f"Unicode error copying message {message_id}: {unicode_err}")
        return False, f"Unicode encoding error: {unicode_err}"
    except Exception as e:
        logger.error(f"Error copying message {message_id}: {e}")
        return False, str(e)

async def safe_forward_message(from_chat_id, to_chat_id, message_id, bot, protect_content=False):
    """
    Safely forward a message with error handling
    
    Returns:
        tuple: (success: bool, result: str/object)
    """
    try:
        result = await bot.forward_messages(
            chat_id=to_chat_id,
            from_chat_id=from_chat_id,
            message_ids=message_id,
            protect_content=protect_content
        )
        return True, result
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
        # Retry once after flood wait
        try:
            result = await bot.forward_messages(
                chat_id=to_chat_id,
                from_chat_id=from_chat_id,
                message_ids=message_id,
                protect_content=protect_content
            )
            return True, result
        except Exception as retry_err:
            return False, f"Retry failed after FloodWait: {retry_err}"
    except UnicodeDecodeError as unicode_err:
        logger.error(f"Unicode error forwarding message {message_id}: {unicode_err}")
        return False, f"Unicode encoding error: {unicode_err}"
    except Exception as e:
        logger.error(f"Error forwarding message {message_id}: {e}")
        return False, str(e)

def format_caption_safely(caption, filename=None, size=None, original_caption=None):
    """
    Safely format a caption with file info and original caption
    
    Args:
        caption: Custom caption template
        filename: File name if available
        size: File size if available  
        original_caption: Original message caption
        
    Returns:
        str: Formatted caption
    """
    try:
        if not caption:
            return original_caption or ""
            
        # Safe encoding for all text components
        from .regix import safe_encode_text
        
        formatted_caption = safe_encode_text(caption)
        
        # Replace placeholders safely
        if filename:
            formatted_caption = formatted_caption.replace('{filename}', safe_encode_text(filename))
        if size:
            formatted_caption = formatted_caption.replace('{size}', safe_encode_text(str(size)))
        if original_caption:
            formatted_caption = formatted_caption.replace('{caption}', safe_encode_text(original_caption))
            
        return formatted_caption
        
    except Exception as e:
        logger.error(f"Error formatting caption: {e}")
        # Fallback to original caption if formatting fails
        return original_caption or ""

def create_source_link(chat_id, message_id):
    """Create a source message link"""
    if str(chat_id).startswith('-100'):
        # Channel/Supergroup
        channel_id = str(chat_id)[4:]  # Remove -100 prefix
        return f"https://t.me/c/{channel_id}/{message_id}"
    else:
        # Private chat or bot
        return f"https://t.me/{chat_id}/{message_id}"

def create_target_link(chat_id, message_id):
    """Create a target message link"""
    if str(chat_id).startswith('-100'):
        # Channel/Supergroup
        channel_id = str(chat_id)[4:]  # Remove -100 prefix
        return f"https://t.me/c/{channel_id}/{message_id}"
    else:
        # Private chat or bot
        return f"https://t.me/{chat_id}/{message_id}"

def add_ftm_caption(original_caption, source_link):
    """Add FTM mode information to caption"""
    ftm_info = f"\n\n🔥 <b>FTM MODE</b> 🔥\n📤 <b>Source:</b> <a href='{source_link}'>Original Message</a>"


    if original_caption:
        return original_caption + ftm_info
    else:
        return ftm_info.strip()

def create_ftm_button(source_link):
    """Create FTM mode button with source link"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Source Link", url=source_link)]
    ])

def combine_buttons(ftm_button, existing_buttons=None):
    """Combine FTM button with existing buttons"""
    if not existing_buttons:
        return ftm_button

    # If existing buttons exist, add FTM button at the top
    ftm_row = ftm_button.inline_keyboard[0]
    new_keyboard = [ftm_row] + existing_buttons.inline_keyboard
    return InlineKeyboardMarkup(new_keyboard)