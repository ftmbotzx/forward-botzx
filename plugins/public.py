import re
import asyncio
import logging
from .utils import STS
from database import db
from config import temp, Config
from translation import Translation
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate as PrivateChat
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified, ChannelPrivate
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from .test import get_configs
from .regix import safe_decode_caption, safe_encode_text
from .ftm_utils import safe_copy_message, safe_forward_message, format_caption_safely

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force subscribe buttons
force_sub_buttons = [[
        InlineKeyboardButton('📜 Join Support Group', url=Config.SUPPORT_GROUP),
        InlineKeyboardButton('🤖 Join Update Channel', url=Config.UPDATE_CHANNEL)
        ],[
        InlineKeyboardButton('✅ Check Subscription', callback_data='check_subscription')
        ]]

#===================Run Function===================#

@Client.on_message(filters.private & filters.command(["fwd", "forward"]))
async def run(bot, message):
    buttons = []
    btn_data = {}
    user_id = message.from_user.id

    # Check force subscribe for non-sudo users
    if not Config.is_sudo_user(user_id):
        subscription_status = await db.check_force_subscribe(user_id, bot)
        if not subscription_status['all_subscribed']:
            force_sub_text = (
                "🔒 <b>Subscribe Required!</b>\n\n"
                "To use this bot, you must join our official channels:\n\n"
                "📜 <b>Support Group:</b> Get help and updates\n"
                "🤖 <b>Update Channel:</b> Latest features and announcements\n\n"
                "After joining both channels, click '✅ Check Subscription' to continue."
            )
            return await message.reply_text(
                text=force_sub_text,
                reply_markup=InlineKeyboardMarkup(force_sub_buttons),
                quote=True
            )

    _bot = await db.get_bot(user_id)
    if not _bot:
      return await message.reply("<code>You didn't added any bot. Please add a bot using /settings !</code>")
    channels = await db.get_user_channels(user_id)
    if not channels:
       return await message.reply_text("please set a to channel in /settings before forwarding")
    if len(channels) > 1:
       for channel in channels:
          buttons.append([KeyboardButton(f"{channel['title']}")])
          btn_data[channel['title']] = channel['chat_id']
       buttons.append([KeyboardButton("cancel")])
       _toid = await bot.ask(message.chat.id, Translation.TO_MSG.format(_bot['name'], _bot['username']), reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True))
       if _toid.text.startswith(('/', 'cancel')):
          return await message.reply_text(Translation.CANCEL, reply_markup=ReplyKeyboardRemove())
       to_title = _toid.text
       toid = btn_data.get(to_title)
       if not toid:
          return await message.reply_text("wrong channel choosen !", reply_markup=ReplyKeyboardRemove())
    else:
       toid = channels[0]['chat_id']
       to_title = channels[0]['title']
    fromid = await bot.ask(message.chat.id, Translation.FROM_MSG, reply_markup=ReplyKeyboardRemove())
    if fromid.text and fromid.text.startswith('/'):
        await message.reply(Translation.CANCEL)
        return
    if fromid.text and not fromid.forward_date:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(fromid.text.replace("?single", ""))
        if not match:
            return await message.reply('Invalid link')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    elif fromid.forward_from_chat.type in [enums.ChatType.CHANNEL]:
        last_msg_id = fromid.forward_from_message_id
        chat_id = fromid.forward_from_chat.username or fromid.forward_from_chat.id
        if last_msg_id == None:
           return await message.reply_text("**This may be a forwarded message from a group and sended by anonymous admin. instead of this please send last message link from group**")
    else:
        await message.reply_text("**invalid !**")
        return
    try:
        title = (await bot.get_chat(chat_id)).title
  #  except ChannelInvalid:
        #return await fromid.reply("**Given source chat is copyrighted channel/group. you can't forward messages from there**")
    except (PrivateChat, ChannelPrivate, ChannelInvalid):
        title = "private" if fromid.text else fromid.forward_from_chat.title
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        return await message.reply(f'Errors - {e}')
    skipno = await bot.ask(message.chat.id, Translation.SKIP_MSG)
    if skipno.text.startswith('/'):
        await message.reply(Translation.CANCEL)
        return
    forward_id = f"{user_id}-{skipno.id}"
    buttons = [[
        InlineKeyboardButton('Yes', callback_data=f"start_public_{forward_id}"),
        InlineKeyboardButton('No', callback_data="close_btn")
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_text(
        text=Translation.DOUBLE_CHECK.format(botname=_bot['name'], botuname=_bot['username'], from_chat=title, to_chat=to_title, skip=skipno.text),
        disable_web_page_preview=True,
        reply_markup=reply_markup
    )
    STS(forward_id).store(chat_id, toid, int(skipno.text), int(last_msg_id))

@Client.on_callback_query(filters.regex('^start_public'))
async def start_public(bot, callback_query):
    try:
        logger.info("Starting public forwarding process.")
        _id = callback_query.data.split('_')[2]
        
        # Check if STS data exists and is valid
        sts_data = STS(_id).get()
        if not sts_data:
            await callback_query.message.edit("❌ Session data expired. Please start the forwarding process again.")
            return
            
        # Safely unpack the data
        try:
            chat_id, to_chat, skip, last_msg_id = sts_data
        except (ValueError, TypeError):
            await callback_query.message.edit("❌ Invalid session data. Please start the forwarding process again.")
            return
            
        user_id = int(_id.split('-')[0])
        protect = await db.get_protect_content(user_id)
        sent_msg = callback_query.message

        # Get bot details
        bot_obj = await db.get_bot(user_id)
        if not bot_obj:
            await sent_msg.edit("Bot details not found. Please add your bot first using `/settings`.")
            return
        bot_name = bot_obj['name']
        bot_username = bot_obj['username']

        # Get target channel title for confirmation message
        try:
            to_chat_obj = await bot.get_chat(to_chat)
            to_title = to_chat_obj.title if to_chat_obj.title else to_chat_obj.username
        except Exception:
            to_title = str(to_chat)

        deleted = 0
        forwarded = 0
        failed = 0
        
        # Determine if it's a channel message or a user message
        if str(chat_id).startswith('-100'):
            from_chat_obj = await bot.get_chat(chat_id)
            from_title = from_chat_obj.title if from_chat_obj.title else from_chat_obj.username
        else:
            from_title = "Saved Messages"
            
        await sent_msg.edit(f"Starting forward from `{from_title}` to `{to_title}`...\n\n`Processing messages...`")

        async def process_message(msg_id):
            nonlocal deleted, forwarded, failed
            try:
                # Get message with encoding safety
                try:
                    message = await bot.get_messages(chat_id, msg_id)
                    if not message:
                        logger.warning(f"Message {msg_id} not found in chat {chat_id}.")
                        return "deleted"
                except UnicodeDecodeError as unicode_err:
                    logger.error(f"Unicode decode error getting message {msg_id}: {unicode_err}")
                    deleted += 1
                    return "deleted"
                except Exception as get_err:
                    logger.error(f"Error getting message {msg_id}: {get_err}")
                    deleted += 1
                    return "deleted"

                caption = None
                reply_markup = None
                
                if message.caption:
                    caption = message.caption.html
                    
                if message.reply_markup:
                    reply_markup = message.reply_markup

                # Determine if it's a message with caption or a regular message
                if message.caption:
                    # Try to format caption safely
                    try:
                        # Extracting filename and size for caption formatting if available
                        filename, size = None, None
                        if message.document:
                            filename = message.document.file_name
                            size = message.document.file_size
                        elif message.photo:
                            filename = "photo.jpg" # Placeholder for photos
                            size = message.photo.file_size
                        elif message.video:
                            filename = message.video.file_name
                            size = message.video.file_size
                        
                        msg_caption = message.caption.html if message.caption else ""
                        caption = format_caption_safely(caption, filename, size, msg_caption)
                    except Exception as e:
                        logger.error(f"Caption formatting error for message {msg_id}: {e}")
                        caption = safe_encode_text(caption) # Fallback to safe encode

                    # Copy message with custom caption/button using safe method
                    success, result = await safe_copy_message(
                        chat_id, to_chat, msg_id, bot,
                        custom_caption=caption,
                        protect_content=protect,
                        reply_markup=reply_markup
                    )
                else:
                    # Forward message normally using safe method
                    success, result = await safe_forward_message(
                        chat_id, to_chat, msg_id, bot,
                        protect_content=protect
                    )

                if not success:
                    logger.error(f"Failed to copy/forward message {msg_id}: {result}")
                    failed += 1
                    return "failed"
                else:
                    forwarded += 1
                    temp.forwardings += 1
                    return "success"

            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
                # Retry the same message after waiting
                return await process_message(msg_id) 
            except UnicodeDecodeError as unicode_err:
                logger.error(f"Unicode decode error forwarding message {msg_id}: {unicode_err}")
                # Try to handle encoding error gracefully
                try:
                    # Fallback: Copy message with safe encoding and error replacement caption
                    success, result = await safe_copy_message(
                        chat_id, to_chat, msg_id, bot,
                        custom_caption="[Original caption had encoding issues - content preserved]",
                        protect_content=protect
                    )
                    if success:
                        forwarded += 1
                        temp.forwardings += 1
                        return "success" # Count as success if fallback works
                except Exception:
                    pass # If fallback also fails, it will be counted as deleted/failed
                deleted += 1
                return "deleted"
            except Exception as e:
                logger.error(f"Error processing message {msg_id}: {e}")
                deleted += 1
                return "deleted"

        tasks = [process_message(i) for i in range(last_msg_id - int(skip) + 1, last_msg_id + 1)]
        results = await asyncio.gather(*tasks)

        for res in results:
            if res == "deleted":
                deleted += 1
            elif res == "failed":
                failed += 1

        await sent_msg.edit(
            f"Forwarding complete!\n"
            f"From: `{from_title}`\n"
            f"To: `{to_title}`\n\n"
            f"✅ Forwarded: `{forwarded}`\n"
            f"❌ Deleted/Not Found: `{deleted}`\n"
            f"⚠️ Failed: `{failed}`"
        )
        logger.info(f"Forwarding process finished. Forwarded: {forwarded}, Deleted: {deleted}, Failed: {failed}")

    except Exception as e:
        logger.error(f"Error in start_public callback: {e}")
        await callback_query.message.edit(f"An error occurred: {e}")