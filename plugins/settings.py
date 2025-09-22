import asyncio
from database import db
from config import Config
from translation import Translation
from pyrogram import Client, filters, enums
from .test import get_configs, update_configs, CLIENT, parse_buttons
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CLIENT = CLIENT()

# Force subscribe buttons
force_sub_buttons = [[
        InlineKeyboardButton('📜 Join Support Group', url=Config.SUPPORT_GROUP),
        InlineKeyboardButton('🤖 Join Update Channel', url=Config.UPDATE_CHANNEL)
        ],[
        InlineKeyboardButton('✅ Check Subscription', callback_data='check_subscription')
        ]]

# /FTM command - redirect to FTM Manager
@Client.on_message(filters.command(['FTM', 'ftm']))
async def ftm_command(client, message):
    user_id = message.from_user.id
    
    # Check force subscribe for non-sudo users
    if not Config.is_sudo_user(user_id):
        subscription_status = await db.check_force_subscribe(user_id, client)
        if not subscription_status['all_subscribed']:
            force_sub_text = (
                "🔒 <b>Subscribe Required!</b>\n\n"
                "To use this bot, you must join our official channels:\n\n"
                "📜 <b>Support Group:</b> Get help and updates\n"
                "🤖 <b>Update Channel:</b> Latest features and announcements\n\n"
                "After joining both channels, click '✅ Check Subscription' to continue."
            )
            await message.delete()
            return await message.reply_text(
                text=force_sub_text,
                reply_markup=InlineKeyboardMarkup(force_sub_buttons)
            )

    await message.delete()
    
    # Create FTM Manager direct access buttons
    user_can_use_ftm = await db.can_use_ftm_mode(user_id)
    user_can_use_alpha = await db.can_use_ftm_alpha_mode(user_id)

    buttons = []

    if user_can_use_ftm:
        buttons.append([InlineKeyboardButton('🔥 FTM Delta Mode', callback_data='settings#ftm_delta')])
    else:
        buttons.append([InlineKeyboardButton('🔥 FTM Delta Mode (Pro Only)', callback_data='settings#ftm_delta_pro_info')])

    # FTM Event section
    buttons.append([
        InlineKeyboardButton('🎪 FTM Event', callback_data='settings#ftm_event')
    ])
    
    # Future Updates section
    buttons.append([
        InlineKeyboardButton('✨ Future Updates ✨', callback_data='settings#future_updates')
    ])

    buttons.append([InlineKeyboardButton('⚙️ Settings', callback_data='settings#main')])
    buttons.append([InlineKeyboardButton('🔙 Back to Menu', callback_data='settings#main')])

    await message.reply_text(
        f"<b><u>🚀 FTM MANAGER 🚀</u></b>\n\n"
        f"<b>🔥 FTM Delta Mode:</b>\n"
        f"• Adds source tracking to forwarded messages\n"
        f"• Creates 'Source Link' buttons\n"
        f"• Embeds original message links\n\n"
        f"<b>🎪 FTM Events:</b>\n"
        f"• Participate in subscription events\n"
        f"• Claim rewards and redeem codes\n"
        f"• Access exclusive user benefits\n\n"
        f"<b>✨ Future Updates: COMING SOON! ✨</b>\n"
        f"• Get ready for a new FTM Alpha Mode!\n"
        f"• Specially for our free users - unlock advanced features without premium!\n\n"
        f"<b>Stay tuned for more!</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )

@Client.on_message(filters.command('settings'))
async def settings(client, message):
   user_id = message.from_user.id

   # Check force subscribe for non-sudo users
   if not Config.is_sudo_user(user_id):
       subscription_status = await db.check_force_subscribe(user_id, client)
       if not subscription_status['all_subscribed']:
           force_sub_text = (
               "🔒 <b>Subscribe Required!</b>\n\n"
               "To use this bot, you must join our official channels:\n\n"
               "📜 <b>Support Group:</b> Get help and updates\n"
               "🤖 <b>Update Channel:</b> Latest features and announcements\n\n"
               "After joining both channels, click '✅ Check Subscription' to continue."
           )
           await message.delete()
           return await message.reply_text(
               text=force_sub_text,
               reply_markup=InlineKeyboardMarkup(force_sub_buttons)
           )

   await message.delete()
   await message.reply_text(
     "<b>change your settings as your wish</b>",
     reply_markup=main_buttons()
     )

@Client.on_callback_query(filters.regex(r'^settings'))
async def settings_query(bot, query):
  user_id = query.from_user.id

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
          return await query.message.edit_text(
              text=force_sub_text,
              reply_markup=InlineKeyboardMarkup(force_sub_buttons)
          )

  i, type = query.data.split("#")
  buttons = [[InlineKeyboardButton('↩ Back', callback_data="settings#main")]]

  if type=="main":
     await query.message.edit_text(
       "<b>change your settings as your wish</b>",
       reply_markup=main_buttons())

  elif type=="bots":
     buttons = []
     _bot = await db.get_bot(user_id)
     if _bot is not None:
        buttons.append([InlineKeyboardButton(_bot['name'],
                         callback_data=f"settings#editbot")])
     else:
        buttons.append([InlineKeyboardButton('✚ Add bot ✚',
                         callback_data="settings#addbot")])
        buttons.append([InlineKeyboardButton('✚ Add User bot (Session) ✚',
                         callback_data="settings#adduserbot")])
        buttons.append([InlineKeyboardButton('✚ Add User bot (Phone) ✚',
                         callback_data="settings#addphonebot")])
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
       "<b><u>My Bots</b></u>\n\n<b>You can manage your bots in here</b>",
       reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addbot":
     await query.message.delete()
     bot = await CLIENT.add_bot(bot, query)
     if bot != True: return

     # Send notification for bot addition
     try:
         from utils.notifications import NotificationManager
         notify = NotificationManager(query.message._client)
         await notify.notify_user_action(user_id, "Added Bot Token", "Bot token successfully added to database", "Bot Management")
     except Exception as notify_err:
         print(f"Failed to send bot addition notification: {notify_err}")

     await query.message.reply_text(
        "<b>bot token successfully added to db</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="adduserbot":
     await query.message.delete()
     user = await CLIENT.add_session(bot, query)
     if user != True: return

     # Send notification for userbot session addition
     try:
         from utils.notifications import NotificationManager
         notify = NotificationManager(query.message._client)
         await notify.notify_user_action(user_id, "Added Userbot Session", "Userbot session successfully added to database", "Bot Management")
     except Exception as notify_err:
         print(f"Failed to send userbot session addition notification: {notify_err}")

     await query.message.reply_text(
        "<b>session successfully added to db</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addphonebot":
     await query.message.delete()
     user = await CLIENT.add_phone_login(bot, query)
     if user != True: return

     # Send notification for phone bot addition
     try:
         from utils.notifications import NotificationManager
         notify = NotificationManager(query.message._client)
         await notify.notify_user_action(user_id, "Added Phone Bot", "Userbot successfully logged in via phone and added to database", "Bot Management")
     except Exception as notify_err:
         print(f"Failed to send phone bot addition notification: {notify_err}")

     await query.message.reply_text(
        "<b>user bot successfully logged in and added to db</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="channels":
     buttons = []
     channels = await db.get_user_channels(user_id)
     for channel in channels:
        buttons.append([InlineKeyboardButton(f"{channel['title']}",
                         callback_data=f"settings#editchannels_{channel['chat_id']}")])
     buttons.append([InlineKeyboardButton('✚ Add Channel ✚',
                      callback_data="settings#addchannel")])
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
       "<b><u>My Channels</b></u>\n\n<b>you can manage your target chats in here</b>",
       reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addchannel":
     await query.message.delete()
     try:
         text = await bot.send_message(user_id, "<b>❪ SET TARGET CHAT ❫\n\nForward a message from Your target chat\n/cancel - cancel this process</b>")
         chat_ids = await bot.listen(chat_id=user_id, timeout=300)
         if chat_ids.text=="/cancel":
            await chat_ids.delete()
            return await text.edit_text(
                  "<b>process canceled</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
         elif not chat_ids.forward_date:
            await chat_ids.delete()
            return await text.edit_text("**This is not a forward message**")
         else:
            chat_id = chat_ids.forward_from_chat.id
            title = chat_ids.forward_from_chat.title
            username = chat_ids.forward_from_chat.username
            username = "@" + username if username else "private"
         chat = await db.add_channel(user_id, chat_id, title, username)
         await chat_ids.delete()

         # Send notification for channel addition
         if chat:  # Only if channel was actually added (not already existing)
             try:
                 from utils.notifications import NotificationManager
                 notify = NotificationManager(bot)
                 await notify.notify_user_action(user_id, "Added Channel", f"Channel: {title} (ID: {chat_id})")
             except Exception as notify_err:
                 print(f"Failed to send channel addition notification: {notify_err}")

         await text.edit_text(
            "<b>Successfully updated</b>" if chat else "<b>This channel already added</b>",
            reply_markup=InlineKeyboardMarkup(buttons))
     except asyncio.exceptions.TimeoutError:
         await text.edit_text('Process has been automatically cancelled', reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="editbot":
     bot = await db.get_bot(user_id)
     TEXT = Translation.BOT_DETAILS if bot['is_bot'] else Translation.USER_DETAILS
     buttons = [[InlineKeyboardButton('❌ Remove ❌', callback_data=f"settings#removebot")
               ],
               [InlineKeyboardButton('↩ Back', callback_data="settings#bots")]]
     await query.message.edit_text(
        TEXT.format(bot['name'], bot['id'], bot['username']),
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="removebot":
     # Get bot details before removal for notification
     bot_details = await db.get_bot(user_id)
     await db.remove_bot(user_id)

     # Send notification for bot removal
     try:
         from utils.notifications import NotificationManager
         notify = NotificationManager(query.message._client)
         bot_info = f"Bot: {bot_details['name']}" if bot_details else "Bot removed"
         await notify.notify_user_action(user_id, "Removed Bot", bot_info)
     except Exception as notify_err:
         print(f"Failed to send bot removal notification: {notify_err}")

     await query.message.edit_text(
        "<b>successfully updated</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type.startswith("editchannels"):
     chat_id = type.split('_')[1]
     chat = await db.get_channel_details(user_id, chat_id)
     buttons = [[InlineKeyboardButton('❌ Remove ❌', callback_data=f"settings#removechannel_{chat_id}")
               ],
               [InlineKeyboardButton('↩ Back', callback_data="settings#channels")]]
     await query.message.edit_text(
        f"<b><u>📄 CHANNEL DETAILS</b></u>\n\n<b>- TITLE:</b> <code>{chat['title']}</code>\n<b>- CHANNEL ID: </b> <code>{chat['chat_id']}</code>\n<b>- USERNAME:</b> {chat['username']}",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type.startswith("removechannel"):
     chat_id = type.split('_')[1]
     # Get channel details before removal for notification
     channel_details = await db.get_channel_details(user_id, chat_id)
     await db.remove_channel(user_id, chat_id)

     # Send notification for channel removal
     try:
         from utils.notifications import NotificationManager
         notify = NotificationManager(query.message._client)
         channel_info = f"Channel: {channel_details['title']} (ID: {chat_id})" if channel_details else f"Channel removed (ID: {chat_id})"
         await notify.notify_user_action(user_id, "Removed Channel", channel_info)
     except Exception as notify_err:
         print(f"Failed to send channel removal notification: {notify_err}")

     await query.message.edit_text(
        "<b>successfully updated</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="caption":
     buttons = []
     data = await get_configs(user_id)
     caption = data['caption']
     if caption is None:
        buttons.append([InlineKeyboardButton('✚ Add Caption ✚',
                      callback_data="settings#addcaption")])
     else:
        buttons.append([InlineKeyboardButton('See Caption',
                      callback_data="settings#seecaption")])
        buttons[-1].append(InlineKeyboardButton('🗑️ Delete Caption',
                      callback_data="settings#deletecaption"))
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
        "<b><u>CUSTOM CAPTION</b></u>\n\n<b>You can set a custom caption to videos and documents. Normaly use its default caption</b>\n\n<b><u>AVAILABLE FILLINGS:</b></u>\n- <code>{filename}</code> : Filename\n- <code>{size}</code> : File size\n- <code>{caption}</code> : default caption",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="seecaption":
     data = await get_configs(user_id)
     buttons = [[InlineKeyboardButton('🖋️ Edit Caption',
                  callback_data="settings#addcaption")
               ],[
               InlineKeyboardButton('↩ Back',
                 callback_data="settings#caption")]]
     await query.message.edit_text(
        f"<b><u>YOUR CUSTOM CAPTION</b></u>\n\n<code>{data['caption']}</code>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="deletecaption":
     await update_configs(user_id, 'caption', None)
     await query.message.edit_text(
        "<b>successfully updated</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addcaption":
     await query.message.delete()
     try:
         text = await bot.send_message(query.message.chat.id, "Send your custom caption\n/cancel - <code>cancel this process</code>")
         caption = await bot.listen(chat_id=user_id, timeout=300)
         if caption.text=="/cancel":
            await caption.delete()
            return await text.edit_text(
                  "<b>process canceled !</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
         try:
            caption.text.format(filename='', size='', caption='')
         except KeyError as e:
            await caption.delete()
            return await text.edit_text(
               f"<b>wrong filling {e} used in your caption. change it</b>",
               reply_markup=InlineKeyboardMarkup(buttons))
         await update_configs(user_id, 'caption', caption.text)
         await caption.delete()
         await text.edit_text(
            "<b>successfully updated</b>",
            reply_markup=InlineKeyboardMarkup(buttons))
     except asyncio.exceptions.TimeoutError:
         await text.edit_text('Process has been automatically cancelled', reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="button":
     buttons = []
     button = (await get_configs(user_id))['button']
     if button is None:
        buttons.append([InlineKeyboardButton('✚ Add Button ✚',
                      callback_data="settings#addbutton")])
     else:
        buttons.append([InlineKeyboardButton('👀 See Button',
                      callback_data="settings#seebutton")])
        buttons[-1].append(InlineKeyboardButton('🗑️ Remove Button ',
                      callback_data="settings#deletebutton"))
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
        "<b><u>CUSTOM BUTTON</b></u>\n\n<b>You can set a inline button to messages.</b>\n\n<b><u>FORMAT:</b></u>\n`[Forward bot][buttonurl:https://t.me/devgaganbot]`\n",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addbutton":
     await query.message.delete()
     try:
         txt = await bot.send_message(user_id, text="**Send your custom button.\n\nFORMAT:**\n`[forward bot][buttonurl:https://t.me/devgaganbot]`\n")
         ask = await bot.listen(chat_id=user_id, timeout=300)
         button = parse_buttons(ask.text.html)
         if not button:
            await ask.delete()
            return await txt.edit_text("**INVALID BUTTON**")
         await update_configs(user_id, 'button', ask.text.html)
         await ask.delete()
         await txt.edit_text("**Successfully button added**",
            reply_markup=InlineKeyboardMarkup(buttons))
     except asyncio.exceptions.TimeoutError:
         await txt.edit_text('Process has been automatically cancelled', reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="seebutton":
      button = (await get_configs(user_id))['button']
      button = parse_buttons(button, markup=False)
      button.append([InlineKeyboardButton("↩ Back", "settings#button")])
      await query.message.edit_text(
         "**YOUR CUSTOM BUTTON**",
         reply_markup=InlineKeyboardMarkup(button))

  elif type=="deletebutton":
     await update_configs(user_id, 'button', None)
     await query.message.edit_text(
        "**Successfully button deleted**",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="database":
     buttons = []
     db_uri = (await get_configs(user_id))['db_uri']
     if db_uri is None:
        buttons.append([InlineKeyboardButton('✚ Add Url ✚',
                      callback_data="settings#addurl")])
     else:
        buttons.append([InlineKeyboardButton('👀 See Url',
                      callback_data="settings#seeurl")])
        buttons[-1].append(InlineKeyboardButton('🗑️ Remove Url ',
                      callback_data="settings#deleteurl"))
     buttons.append([InlineKeyboardButton('↩ Back',
                      callback_data="settings#main")])
     await query.message.edit_text(
        "<b><u>DATABASE</u>\n\nDatabase is required for store your duplicate messages permenant. other wise stored duplicate media may be disappeared when after bot restart.</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="addurl":
     await query.message.delete()
     uri = await bot.ask(user_id, "<b>please send your mongodb url.</b>\n\n<i>get your Mongodb url from [here](https://mongodb.com)</i>", disable_web_page_preview=True)
     if uri.text=="/cancel":
        return await uri.reply_text(
                  "<b>process canceled !</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
     if not uri.text.startswith("mongodb+srv://") and not uri.text.endswith("majority"):
        return await uri.reply("<b>Invalid Mongodb Url</b>",
                   reply_markup=InlineKeyboardMarkup(buttons))
     await update_configs(user_id, 'db_uri', uri.text)
     await uri.reply("**Successfully database url added**",
             reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="seeurl":
     db_uri = (await get_configs(user_id))['db_uri']
     await query.answer(f"DATABASE URL: {db_uri}", show_alert=True)

  elif type=="deleteurl":
     await update_configs(user_id, 'db_uri', None)
     await query.message.edit_text(
        "**Successfully your database url deleted**",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="filters":
     await query.message.edit_text(
        "<b><u>💠 CUSTOM FILTERS 💠</b></u>\n\n**configure the type of messages which you want forward**",
        reply_markup=await filters_buttons(user_id))

  elif type=="nextfilters":
     await query.edit_message_reply_markup(
        reply_markup=await next_filters_buttons(user_id))

  elif type.startswith("updatefilter"):
     i, key, value = type.split('-')
     if value=="True":
        await update_configs(user_id, key, False)
     else:
        await update_configs(user_id, key, True)
     if key in ['poll', 'protect']:
        return await query.edit_message_reply_markup(
           reply_markup=await next_filters_buttons(user_id))
     await query.edit_message_reply_markup(
        reply_markup=await filters_buttons(user_id))

  elif type.startswith("file_size"):
    settings = await get_configs(user_id)
    size = settings.get('file_size', 0)
    i, limit = size_limit(settings['size_limit'])
    await query.message.edit_text(
       f'<b><u>SIZE LIMIT</b></u><b>\n\nyou can set file size limit to forward\n\nStatus: files with {limit} `{size} MB` will forward</b>',
       reply_markup=size_button(size))

  elif type.startswith("update_size"):
    size = int(query.data.split('-')[1])
    if 0 < size > 2000:
      return await query.answer("size limit exceeded", show_alert=True)
    await update_configs(user_id, 'file_size', size)
    i, limit = size_limit((await get_configs(user_id))['size_limit'])
    await query.message.edit_text(
       f'<b><u>SIZE LIMIT</b></u><b>\n\nyou can set file size limit to forward\n\nStatus: files with {limit} `{size} MB` will forward</b>',
       reply_markup=size_button(size))

  elif type.startswith('update_limit'):
    i, limit, size = type.split('-')
    limit, sts = size_limit(limit)
    await update_configs(user_id, 'size_limit', limit)
    await query.message.edit_text(
       f'<b><u>SIZE LIMIT</b></u><b>\n\nyou can set file size limit to forward\n\nStatus: files with {sts} `{size} MB` will forward</b>',
       reply_markup=size_button(int(size)))

  elif type == "add_extension":
    await query.message.delete()
    ext = await bot.ask(user_id, text="**please send your extensions (seperete by space)**")
    if ext.text == '/cancel':
       return await ext.reply_text(
                  "<b>process canceled</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
    extensions = ext.text.split(" ")
    extension = (await get_configs(user_id))['extension']
    if extension:
        for extn in extensions:
            extension.append(extn)
    else:
        extension = extensions
    await update_configs(user_id, 'extension', extension)
    await ext.reply_text(
        f"**successfully updated**",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type == "get_extension":
    extensions = (await get_configs(user_id))['extension']
    btn = extract_btn(extensions)
    btn.append([InlineKeyboardButton('✚ ADD ✚', 'settings#add_extension')])
    btn.append([InlineKeyboardButton('Remove all', 'settings#rmve_all_extension')])
    btn.append([InlineKeyboardButton('↩ Back', 'settings#main')])
    await query.message.edit_text(
        text='<b><u>EXTENSIONS</u></b>\n\n**Files with these extiontions will not forward**',
        reply_markup=InlineKeyboardMarkup(btn))

  elif type == "rmve_all_extension":
    await update_configs(user_id, 'extension', None)
    await query.message.edit_text(text="**successfully deleted**",
                                   reply_markup=InlineKeyboardMarkup(buttons))
  elif type == "add_keyword":
    await query.message.delete()
    ask = await bot.ask(user_id, text="**please send the keywords (seperete by space)**")
    if ask.text == '/cancel':
       return await ask.reply_text(
                  "<b>process canceled</b>",
                  reply_markup=InlineKeyboardMarkup(buttons))
    keywords = ask.text.split(" ")
    keyword = (await get_configs(user_id))['keywords']
    if keyword:
        for word in keywords:
            keyword.append(word)
    else:
        keyword = keywords
    await update_configs(user_id, 'keywords', keyword)
    await ask.reply_text(
        f"**successfully updated**",
        reply_markup=InlineKeyboardMarkup(buttons))

  elif type == "get_keyword":
    keywords = (await get_configs(user_id))['keywords']
    btn = extract_btn(keywords)
    btn.append([InlineKeyboardButton('✚ ADD ✚', 'settings#add_keyword')])
    btn.append([InlineKeyboardButton('Remove all', 'settings#rmve_all_keyword')])
    btn.append([InlineKeyboardButton('↩ Back', 'settings#main')])
    await query.message.edit_text(
        text='<b><u>KEYWORDS</u></b>\n\n**File with these keywords in file name will forwad**',
        reply_markup=InlineKeyboardMarkup(btn))

  elif type == "rmve_all_keyword":
    await update_configs(user_id, 'keywords', None)
    await query.message.edit_text(text="**successfully deleted**",
                                   reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="ftmmanager":
     # FTM Modes menu
     user_can_use_ftm = await db.can_use_ftm_mode(user_id)
     user_can_use_alpha = await db.can_use_ftm_alpha_mode(user_id)

     buttons = []

     if user_can_use_ftm:
         buttons.append([InlineKeyboardButton('🔥 FTM Delta Mode', callback_data='settings#ftm_delta')])
     else:
         # Placeholder for Pro Only Delta Mode
         buttons.append([InlineKeyboardButton('🔥 FTM Delta Mode (Pro Only)', callback_data='settings#ftm_delta_pro_info')])

     # FTM Event section
     buttons.append([
         InlineKeyboardButton('🎪 FTM Event', callback_data='settings#ftm_event')
     ])
     
     # New section for Future Updates  
     buttons.append([
         InlineKeyboardButton('✨ Future Updates ✨', callback_data='settings#future_updates')
     ])

     buttons.append([InlineKeyboardButton('↩ Back', callback_data="settings#main")])

     await query.message.edit_text(
        f"<b><u>🚀 FTM MANAGER 🚀</u></b>\n\n"
        f"<b>🔥 FTM Delta Mode:</b>\n"
        f"• Adds source tracking to forwarded messages\n"
        f"• Creates 'Source Link' buttons\n"
        f"• Embeds original message links\n\n"
        f"<b>✨ Future Updates: COMING SOON! ✨</b>\n"
        f"• Get ready for a new FTM Alpha Mode!\n"
        f"• Specially for our free users - unlock advanced features without premium!\n\n"
        f"<b>Stay tuned for more!</b>",
        reply_markup=InlineKeyboardMarkup(buttons))

  # Handler for FTM Delta Mode Pro info
  elif type=="ftm_delta_pro_info":
      buttons = [[
            InlineKeyboardButton('💎 Upgrade to Pro Plan',
                        callback_data='premium#main')
            ],[
            InlineKeyboardButton('↩ Back',
                        callback_data="settings#ftmmanager")
            ]]
      await query.message.edit_text(
            f"<b><u>🔥 FTM DELTA MODE 🔥</u></b>\n\n<b>⚠️ Pro Plan Required</b>\n\nFTM Delta Mode is a premium feature available only to Pro plan users.\n\n<b>Pro Plan Benefits:</b>\n• FTM Delta Mode with source tracking\n• Unlimited forwarding\n• Priority support\n\n<b>Pricing:</b>\n• 15 days: ₹299\n• 30 days: ₹549",
            reply_markup=InlineKeyboardMarkup(buttons))

  # Handler for Future Updates section
  elif type=="future_updates":
      buttons = [
          [InlineKeyboardButton('↩ Back', callback_data="settings#ftmmanager")]
      ]
      await query.message.edit_text(
          "<b><u>✨ FUTURE UPDATES ✨</u></b>\n\n"
          "<b>Get ready for the upcoming FTM Alpha Mode!</b>\n\n"
          "This update is specially designed for our valuable free users who want to experience powerful features without a premium subscription.\n\n"
          "<b>FTM Alpha Mode Features (Secret Reveal):</b>\n"
          "• <spoiler>Real-time auto-forwarding between channels</spoiler>\n"
          "• <spoiler>Live sync of all new incoming posts</spoiler>\n"
          "• <spoiler>No 'Forwarded from' tags (bot-uploaded)</spoiler>\n"
          "• <spoiler>Requires bot admin in both channels</spoiler>\n\n"
          "<b>fascinating text with small caps as text</b>\n"
          "stay tuned for the official release date!",
          reply_markup=InlineKeyboardMarkup(buttons)
      )

  # Handler for FTM Event section
  elif type=="ftm_event":
      buttons = [
          [InlineKeyboardButton('🎪 Navratri Event', callback_data='event#navratri_event')],
          [InlineKeyboardButton('↩ Back', callback_data="settings#ftmmanager")]
      ]
      await query.message.edit_text(
          "<b><u>🎪 FTM EVENT SYSTEM 🎪</u></b>\n\n"
          "<b>🎉 Available Events:</b>\n\n"
          "<b>🕉️ Navratri Event</b>\n"
          "• Free users → 10 days Plus subscription\n"
          "• Plus users → 10 days Pro subscription\n"
          "• Pro users → 10 days Pro subscription extension\n\n"
          "<b>How to participate:</b>\n"
          "• Click on an event to view details\n"
          "• Claim your subscription reward\n"
          "• Use /redeem command with event codes\n\n"
          "<i>More events coming soon!</i>",
          reply_markup=InlineKeyboardMarkup(buttons),
          parse_mode=enums.ParseMode.HTML
      )

  elif type=="toggle_ftmmode":
     user_can_use_ftm = await db.can_use_ftm_mode(user_id)

     if not user_can_use_ftm:
         buttons = [[
            InlineKeyboardButton('💎 Upgrade to Pro Plan',
                        callback_data='premium#main')
            ],[
            InlineKeyboardButton('↩ Back',
                        callback_data="settings#main")
            ]]
         await query.message.edit_text(
            f"<b><u>🔥 FTM MODE 🔥</u></b>\n\n<b>⚠️ Pro Plan Required</b>\n\nFTM Mode is a premium feature available only to Pro plan users.\n\n<b>Pro Plan Benefits:</b>\n• FTM Mode with source tracking\n• Unlimited forwarding\n• Priority support\n\n<b>Pricing:</b>\n• 15 days: ₹299\n• 30 days: ₹549",
            reply_markup=InlineKeyboardMarkup(buttons))
     else:
         current_mode = (await get_configs(user_id))['ftm_mode']
         new_mode = not current_mode
         await update_configs(user_id, 'ftm_mode', new_mode)
         status = "🟢 Enabled" if new_mode else "🔴 Disabled"
         buttons = [[
            InlineKeyboardButton('✅ Enable' if not new_mode else '❌ Disable',
                        callback_data=f'settings#toggle_ftmmode')
            ],[
            InlineKeyboardButton('↩ Back',
                        callback_data="settings#main")
            ]]
         await query.message.edit_text(
            f"<b><u>🔥 FTM MODE 🔥</u></b>\n\n<b>Status:</b> {status}\n\n<b>When FTM Mode is enabled:</b>\n• Each forwarded message will have a 'Source Link' button\n• Original message link will be added to caption\n• Target message link will be embedded in caption\n\n<b>Note:</b> This mode adds source tracking to all forwarded messages.",
            reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="ftm_alpha":
     # FTM Alpha Mode settings (new real-time forwarding)
     alpha_config = await db.get_alpha_config(user_id)
     user_can_use_alpha = await db.can_use_ftm_alpha_mode(user_id)

     if not user_can_use_alpha:
         buttons = [[
            InlineKeyboardButton('💎 Upgrade to Pro Plan',
                        callback_data='premium#main')
            ],[
            InlineKeyboardButton('↩ Back',
                        callback_data="settings#ftmmanager")
            ]]
         await query.message.edit_text(
            f"<b><u>⚡ FTM ALPHA MODE ⚡</u></b>\n\n<b>⚠️ Pro Plan Required</b>\n\nFTM Alpha Mode is an advanced premium feature available only to Pro plan users.\n\n<b>Alpha Mode Features:</b>\n• Real-time auto-forwarding between channels\n• Live sync of all new incoming posts\n• No 'Forwarded from' tags (bot-uploaded)\n• Requires bot admin in both channels\n\n<b>🚀 Fun Warning:</b> We're launching an Ultra plan for Alpha mode soon! 😉\n\n<b>Pricing:</b>\n• 15 days: ₹299\n• 30 days: ₹549",
            reply_markup=InlineKeyboardMarkup(buttons))
     else:
         status = "🟢 Enabled" if alpha_config['enabled'] else "🔴 Disabled"
         source_info = f"📤 Source: {alpha_config['source_chat']}" if alpha_config['source_chat'] else "📤 Source: Not configured"
         target_info = f"📥 Target: {alpha_config['target_chat']}" if alpha_config['target_chat'] else "📥 Target: Not configured"

         buttons = []
         if alpha_config['enabled']:
             buttons.append([InlineKeyboardButton('❌ Disable Alpha Mode', callback_data='settings#toggle_ftm_alpha')])
         else:
             buttons.append([InlineKeyboardButton('✅ Enable Alpha Mode', callback_data='settings#toggle_ftm_alpha')])

         buttons.extend([
             [InlineKeyboardButton('📤 Set Source Channel', callback_data='settings#set_alpha_source')],
             [InlineKeyboardButton('📥 Set Target Channel', callback_data='settings#set_alpha_target')],
             [InlineKeyboardButton('↩ Back', callback_data="settings#ftmmanager")]
         ])

         await query.message.edit_text(
            f"<b><u>⚡ FTM ALPHA MODE ⚡</u></b>\n\n<b>Status:</b> {status}\n\n{source_info}\n{target_info}\n\n<b>When Alpha Mode is enabled:</b>\n• All new messages from source channel are auto-forwarded\n• Messages are forwarded instantly in real-time\n• No 'Forwarded from' tag (bot-uploaded)\n• Bot must be admin in both channels\n\n<b>⚠️ Note:</b> This feature requires bot admin permissions in both channels.",
            reply_markup=InlineKeyboardMarkup(buttons))

  elif type=="toggle_ftm_alpha":
     # Show confirmation notification for FTM Alpha mode
     user_can_use_alpha = await db.can_use_ftm_alpha_mode(user_id)

     if not user_can_use_alpha:
         return await query.answer("❌ FTM Alpha Mode requires Pro plan!", show_alert=True)

     alpha_config = await db.get_alpha_config(user_id)
     new_status = not alpha_config['enabled']

     if new_status:
         # Check if channels are configured before enabling
         if not alpha_config['source_chat'] or not alpha_config['target_chat']:
             return await query.answer("❌ Please configure source and target channels first!", show_alert=True)

         # Show confirmation notification with direct add-bot links
         confirm_buttons = [
             [InlineKeyboardButton('✅ Yes, Enable', callback_data='settings#confirm_alpha_enable')],
             [InlineKeyboardButton('❌ Cancel', callback_data='settings#ftm_alpha')]
         ]

         # Create direct add-to-channel links
         bot_username = bot.username
         add_bot_url = f"https://t.me/{bot_username}?startchannel&admin=post_messages+delete_messages+restrict_members"

         await query.message.edit_text(
             f"<b>⚡ ENABLE FTM ALPHA MODE ⚡</b>\n\n"
             f"<b>⚠️ Important Notice:</b>\n\n"
             f"FTM Alpha Mode will enable real-time auto-forwarding from your source channel to target channel.\n\n"
             f"<b>Before enabling, the system will verify:</b>\n"
             f"📤 Source: {alpha_config['source_chat']}\n"
             f"📥 Target: {alpha_config['target_chat']}\n\n"
             f"<b>🤖 Bot to Add: @{bot_username}</b>\n\n"
             f"<b>Permission Requirements:</b>\n"
             f"• Bot: Must be admin in both channels\n"
             f"• Userbot: Must be member in both channels\n"
             f"• Target channel: Must have posting rights\n\n"
             f"<b>📱 Quick Add Bot:</b>\n"
             f"<a href='{add_bot_url}'>🔗 Click here to add @{bot_username} to channels</a>\n"
             f"(Make sure to grant admin rights with posting permissions)\n\n"
             f"<b>Do you want to proceed with permission verification?</b>",
             reply_markup=InlineKeyboardMarkup(confirm_buttons)
         )
     else:
         # Disable directly without confirmation
         await db.set_alpha_config(user_id, enabled=False)
         await query.answer("✅ FTM Alpha Mode disabled!", show_alert=True)

         # Reload configurations
         from plugins.ftm_alpha import load_alpha_configs, validate_and_filter_configs
         await load_alpha_configs()
         await validate_and_filter_configs(bot)

         # Refresh the settings
         await settings_query(bot, query) # Use settings_query to refresh

  elif type=="confirm_alpha_enable":
     # Confirm and enable FTM Alpha with comprehensive permission checking
     user_can_use_alpha = await db.can_use_ftm_alpha_mode(user_id)

     if not user_can_use_alpha:
         return await query.answer("❌ FTM Alpha Mode requires Pro plan!", show_alert=True)

     alpha_config = await db.get_alpha_config(user_id)

     # Show checking message
     await query.message.edit_text(
         "<b>⚡ ENABLING FTM ALPHA MODE ⚡</b>\n\n"
         "🔍 Verifying permissions...\n\n"
         "Please wait while we check:"
         "\n• Bot/Userbot status in source channel"
         "\n• Bot/Userbot status in target channel"
         "\n• Posting rights in target channel"
     )

     # Perform comprehensive permission checking
     try:
         source_chat = alpha_config['source_chat']
         target_chat = alpha_config['target_chat']

         # Check if bot or userbot
         is_bot = bot.me.is_bot
         bot_id = bot.me.id

         permission_errors = []

         # Check source channel permissions
         try:
             source_member = await bot.get_chat_member(source_chat, bot_id)
             if is_bot:
                 # For bots, require admin status
                 if source_member.status not in ['administrator', 'creator']:
                     permission_errors.append(f"❌ Bot is not admin in source channel ({source_member.status})")
             else:
                 # For userbots, require at least member status
                 if source_member.status in ['kicked', 'left']:
                     permission_errors.append(f"❌ Userbot is not a member of source channel ({source_member.status})")
         except Exception as e:
             permission_errors.append(f"❌ Cannot access source channel: {str(e)}")

         # Check target channel permissions
         try:
             target_member = await bot.get_chat_member(target_chat, bot_id)
             if is_bot:
                 # For bots, require admin status with posting rights
                 if target_member.status not in ['administrator', 'creator']:
                     permission_errors.append(f"❌ Bot is not admin in target channel ({target_member.status})")
                 elif target_member.status == 'administrator':
                     # Check specific posting permissions for admin bots
                     if not target_member.privileges or not target_member.privileges.can_post_messages:
                         permission_errors.append("❌ Bot admin lacks posting rights in target channel")
             else:
                 # For userbots, require at least member status
                 if target_member.status in ['kicked', 'left']:
                     permission_errors.append(f"❌ Userbot is not a member of target channel ({target_member.status})")
                 elif target_member.status == 'restricted':
                     # Check if userbot can send messages
                     if not target_member.permissions or not target_member.permissions.can_send_messages:
                         permission_errors.append("❌ Userbot is restricted from posting in target channel")
         except Exception as e:
             permission_errors.append(f"❌ Cannot access target channel: {str(e)}")

         # Test posting rights by attempting to get chat info
         try:
             target_info = await bot.get_chat(target_chat)
             if not target_info:
                 permission_errors.append("❌ Cannot access target channel information")
         except Exception as e:
             permission_errors.append(f"❌ Cannot verify target channel: {str(e)}")

         if permission_errors:
             # Show permission errors with direct add-bot links
             bot_username = bot.username
             add_bot_url = f"https://t.me/{bot_username}?startchannel&admin=post_messages+delete_messages+restrict_members"

             error_text = "<b>⚡ FTM ALPHA MODE - PERMISSION ERRORS ⚡</b>\n\n"
             error_text += "<b>❌ Permission verification failed:</b>\n\n"
             error_text += "\n".join(permission_errors)
             error_text += "\n\n<b>🤖 Bot to Add: @{}</b>\n\n".format(bot_username)
             error_text += "<b>💡 Solutions:</b>\n"
             if is_bot:
                 error_text += "• Make sure bot is admin in both channels\n"
                 error_text += "• Grant posting rights to bot in target channel\n\n"
                 error_text += "<b>📱 Quick Add Bot:</b>\n"
                 error_text += "<a href='{}'>🔗 Click here to add @{} to channels</a>\n".format(add_bot_url, bot_username)
                 error_text += "(Grant admin rights with posting permissions)\n\n"
                 error_text += "<b>📋 Steps:</b>\n"
                 error_text += "1. Click the link above\n"
                 error_text += "2. Select your source channel\n"
                 error_text += "3. Make bot admin with all permissions\n"
                 error_text += "4. Repeat for target channel\n"
                 error_text += "5. Try enabling Alpha mode again"
             else:
                 error_text += "• Make sure userbot is member of both channels\n"
                 error_text += "• Ensure userbot can post in target channel"

             back_buttons = [
                 [InlineKeyboardButton('🔄 Try Again', callback_data='settings#confirm_alpha_enable')],
                 [InlineKeyboardButton('↩ Back to Settings', callback_data='settings#ftm_alpha')]
             ]

             await query.message.edit_text(
                 error_text,
                 reply_markup=InlineKeyboardMarkup(back_buttons)
             )
         else:
             # All permissions verified - enable Alpha mode
             await db.set_alpha_config(user_id, enabled=True)

             # Reload configurations
             from plugins.ftm_alpha import load_alpha_configs, validate_and_filter_configs
             await load_alpha_configs()
             await validate_and_filter_configs(bot)

             # Show success message
             await query.message.edit_text(
                 "<b>⚡ FTM ALPHA MODE ENABLED ⚡</b>\n\n"
                 "<b>✅ All permissions verified successfully!</b>\n\n"
                 "<b>Status:</b> 🟢 Active\n"
                 f"<b>Source:</b> {source_chat}\n"
                 f"<b>Target:</b> {target_chat}\n\n"
                 "<b>🚀 Real-time forwarding is now active!</b>\n\n"
                 "All new messages from the source channel will be automatically copied to the target channel without any modifications.",
                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('↩ Back to Settings', callback_data='settings#ftm_alpha')]])
             )

     except Exception as e:
         # Handle unexpected errors
         await query.message.edit_text(
             f"<b>⚡ FTM ALPHA MODE - ERROR ⚡</b>\n\n"
             f"<b>❌ An error occurred during permission verification:</b>\n\n"
             f"{str(e)}\n\n"
             f"Please try again or contact support if the issue persists.",
             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('↩ Back to Settings', callback_data='settings#ftm_alpha')]])
         )

  elif type=="set_alpha_source":
     # Set Alpha mode source channel
     user_can_use_alpha = await db.can_use_ftm_alpha_mode(user_id)
     if not user_can_use_alpha:
         return await query.answer("❌ FTM Alpha Mode requires Pro plan!", show_alert=True)

     await query.message.delete()
     try:
         source_msg = await bot.ask(user_id,
             "<b>📤 SET ALPHA SOURCE CHANNEL</b>\n\n"
             "Please send the <b>last message link</b> from your source channel OR forward the last message from the source channel.\n\n"
             "<b>Example:</b> https://t.me/channelname/123\n\n"
             "/cancel - cancel this process")

         if source_msg.text and source_msg.text == "/cancel":
             return await source_msg.reply(
                 "<b>Process cancelled!</b>")

         source_chat_id = None
         last_msg_id = None

         # Handle forwarded message
         if source_msg.forward_date and source_msg.forward_from_chat:
             source_chat_id = source_msg.forward_from_chat.id
             last_msg_id = source_msg.forward_from_message_id
             channel_title = "Alpha Source"  # Use Alpha Source as name

         # Handle message link
         elif source_msg.text:
             import re
             regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
             match = regex.match(source_msg.text.replace("?single", ""))
             if not match:
                 return await source_msg.reply("❌ Invalid link format!")

             chat_id = match.group(4)
             last_msg_id = int(match.group(5))

             if chat_id.isnumeric():
                 source_chat_id = int(("-100" + chat_id))
             else:
                 source_chat_id = chat_id

             channel_title = "Alpha Source"  # Use Alpha Source as name
         else:
             return await source_msg.reply("❌ Please send a valid message link or forward a message!")

         # Save the Alpha source configuration
         await db.set_alpha_config(user_id, source_chat=source_chat_id)

         # Also save the last message ID for tracking
         await db.update_user_config(user_id, 'alpha_source_last_msg_id', last_msg_id)

         # Reload Alpha mode configurations to pick up new source
         from plugins.ftm_alpha import load_alpha_configs, validate_and_filter_configs
         await load_alpha_configs()
         await validate_and_filter_configs(bot)

         buttons = [[InlineKeyboardButton('↩ Back to Alpha Settings', callback_data='settings#ftm_alpha')]]
         await source_msg.reply(
             f"✅ <b>Alpha Source Channel Set!</b>\n\n"
             f"<b>Channel:</b> {channel_title}\n"
             f"<b>Chat ID:</b> <code>{source_chat_id}</code>\n"
             f"<b>Starting from message:</b> {last_msg_id}\n\n"
             f"All new messages after this point will be forwarded when Alpha Mode is enabled.",
             reply_markup=InlineKeyboardMarkup(buttons))

     except Exception as e:
         return await bot.send_message(user_id, f'❌ Source setup failed: {e}')

  elif type=="set_alpha_target":
     # Set Alpha mode target channel
     user_can_use_alpha = await db.can_use_ftm_alpha_mode(user_id)
     if not user_can_use_alpha:
         return await query.answer("❌ FTM Alpha Mode requires Pro plan!", show_alert=True)

     await query.message.delete()
     try:
         target_msg = await bot.ask(user_id,
             "<b>📥 SET ALPHA TARGET CHANNEL</b>\n\n"
             "Please send the <b>last message link</b> from your target channel OR forward the last message from the target channel.\n\n"
             "<b>Example:</b> https://t.me/channelname/123\n\n"
             "/cancel - cancel this process")

         if target_msg.text and target_msg.text == "/cancel":
             return await target_msg.reply(
                 "<b>Process cancelled!</b>")

         target_chat_id = None
         last_msg_id = None

         # Handle forwarded message
         if target_msg.forward_date and target_msg.forward_from_chat:
             target_chat_id = target_msg.forward_from_chat.id
             last_msg_id = target_msg.forward_from_message_id
             channel_title = "Alpha Target"  # Use Alpha Target as name

         # Handle message link
         elif target_msg.text:
             import re
             regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
             match = regex.match(target_msg.text.replace("?single", ""))
             if not match:
                 return await target_msg.reply("❌ Invalid link format!")

             chat_id = match.group(4)
             last_msg_id = int(match.group(5))

             if chat_id.isnumeric():
                 target_chat_id = int(("-100" + chat_id))
             else:
                 target_chat_id = chat_id

             channel_title = "Alpha Target"  # Use Alpha Target as name
         else:
             return await target_msg.reply("❌ Please send a valid message link or forward a message!")

         # Save the Alpha target configuration
         await db.set_alpha_config(user_id, target_chat=target_chat_id)

         # Also save the last message ID for tracking
         await db.update_user_config(user_id, 'alpha_target_last_msg_id', last_msg_id)

         # Reload Alpha mode configurations to pick up new target
         from plugins.ftm_alpha import load_alpha_configs, validate_and_filter_configs
         await load_alpha_configs()
         await validate_and_filter_configs(bot)

         buttons = [[InlineKeyboardButton('↩ Back to Alpha Settings', callback_data='settings#ftm_alpha')]]
         await target_msg.reply(
             f"✅ <b>Alpha Target Channel Set!</b>\n\n"
             f"<b>Channel:</b> {channel_title}\n"
             f"<b>Chat ID:</b> <code>{target_chat_id}</code>\n"
             f"<b>Last message reference:</b> {last_msg_id}\n\n"
             f"Messages will be forwarded to this channel when Alpha Mode is enabled.",
             reply_markup=InlineKeyboardMarkup(buttons))

     except Exception as e:
         return await bot.send_message(user_id, f'❌ Target setup failed: {e}')


  elif type.startswith("alert"):
    alert = type.split('_')[1]
    await query.answer(alert, show_alert=True)

def main_buttons():
  buttons = [[
       InlineKeyboardButton('🤖 Bᴏᴛs',
                    callback_data=f'settings#bots'),
       InlineKeyboardButton('🏷 Cʜᴀɴɴᴇʟs',
                    callback_data=f'settings#channels')
       ],[
       InlineKeyboardButton('🖋️ Cᴀᴘᴛɪᴏɴ',
                    callback_data=f'settings#caption'),
       InlineKeyboardButton('🗃 MᴏɴɢᴏDB',
                    callback_data=f'settings#database')
       ],[
       InlineKeyboardButton('🕵‍♀ Fɪʟᴛᴇʀs 🕵‍♀',
                    callback_data=f'settings#filters'),
       InlineKeyboardButton('⏹ Bᴜᴛᴛᴏɴ',
                    callback_data=f'settings#button')
       ],[
       InlineKeyboardButton('🔥 FTM Manager',
                    callback_data='settings#ftmmanager'),
       InlineKeyboardButton('Exᴛʀᴀ Sᴇᴛᴛɪɴɢs 🧪',
                    callback_data='settings#nextfilters')
       ],[
       InlineKeyboardButton('⫷ Bᴀᴄᴋ', callback_data='back')
       ]]
  return InlineKeyboardMarkup(buttons)

def size_limit(limit):
   if str(limit) == "None":
      return None, ""
   elif str(limit) == "True":
      return True, "more than"
   else:
      return False, "less than"

def extract_btn(datas):
    i = 0
    btn = []
    if datas:
       for data in datas:
         if i >= 5:
            i = 0
         if i == 0:
            btn.append([InlineKeyboardButton(data, f'settings#alert_{data}')])
            i += 1
            continue
         elif i > 0:
            btn[-1].append(InlineKeyboardButton(data, f'settings#alert_{data}'))
            i += 1
    return btn

def size_button(size):
  buttons = [[
       InlineKeyboardButton('+',
                    callback_data=f'settings#update_limit-True-{size}'),
       InlineKeyboardButton('=',
                    callback_data=f'settings#update_limit-None-{size}'),
       InlineKeyboardButton('-',
                    callback_data=f'settings#update_limit-False-{size}')
       ],[
       InlineKeyboardButton('+1',
                    callback_data=f'settings#update_size-{size + 1}'),
       InlineKeyboardButton('-1',
                    callback_data=f'settings#update_size_-{size - 1}')
       ],[
       InlineKeyboardButton('+5',
                    callback_data=f'settings#update_size-{size + 5}'),
       InlineKeyboardButton('-5',
                    callback_data=f'settings#update_size_-{size - 5}')
       ],[
       InlineKeyboardButton('+10',
                    callback_data=f'settings#update_size-{size + 10}'),
       InlineKeyboardButton('-10',
                    callback_data=f'settings#update_size_-{size - 10}')
       ],[
       InlineKeyboardButton('+50',
                    callback_data=f'settings#update_size-{size + 50}'),
       InlineKeyboardButton('-50',
                    callback_data=f'settings#update_size_-{size - 50}')
       ],[
       InlineKeyboardButton('+100',
                    callback_data=f'settings#update_size-{size + 100}'),
       InlineKeyboardButton('-100',
                    callback_data=f'settings#update_size_-{size - 100}')
       ],[
       InlineKeyboardButton('↩ Back',
                    callback_data="settings#main")
     ]]
  return InlineKeyboardMarkup(buttons)

async def filters_buttons(user_id):
  filter = await get_configs(user_id)
  filters = filter['filters']
  buttons = [[
       InlineKeyboardButton('🏷️ Forward tag',
                    callback_data=f'settings_#updatefilter-forward_tag-{filter["forward_tag"]}'),
       InlineKeyboardButton('✅' if filter['forward_tag'] else '❌',
                    callback_data=f'settings#updatefilter-forward_tag-{filter["forward_tag"]}')
       ],[
       InlineKeyboardButton('🖍️ Texts',
                    callback_data=f'settings_#updatefilter-text-{filters["text"]}'),
       InlineKeyboardButton('✅' if filters['text'] else '❌',
                    callback_data=f'settings#updatefilter-text-{filters["text"]}')
       ],[
       InlineKeyboardButton('📁 Documents',
                    callback_data=f'settings_#updatefilter-document-{filters["document"]}'),
       InlineKeyboardButton('✅' if filters['document'] else '❌',
                    callback_data=f'settings#updatefilter-document-{filters["document"]}')
       ],[
       InlineKeyboardButton('🎞️ Videos',
                    callback_data=f'settings_#updatefilter-video-{filters["video"]}'),
       InlineKeyboardButton('✅' if filters['video'] else '❌',
                    callback_data=f'settings#updatefilter-video-{filters["video"]}')
       ],[
       InlineKeyboardButton('📷 Photos',
                    callback_data=f'settings_#updatefilter-photo-{filters["photo"]}'),
       InlineKeyboardButton('✅' if filters['photo'] else '❌',
                    callback_data=f'settings#updatefilter-photo-{filters["photo"]}')
       ],[
       InlineKeyboardButton('🎧 Audios',
                    callback_data=f'settings_#updatefilter-audio-{filters["audio"]}'),
       InlineKeyboardButton('✅' if filters['audio'] else '❌',
                    callback_data=f'settings#updatefilter-audio-{filters["audio"]}')
       ],[
       InlineKeyboardButton('🎤 Voices',
                    callback_data=f'settings_#updatefilter-voice-{filters["voice"]}'),
       InlineKeyboardButton('✅' if filters['voice'] else '❌',
                    callback_data=f'settings#updatefilter-voice-{filters["voice"]}')
       ],[
       InlineKeyboardButton('🎭 Animations',
                    callback_data=f'settings_#updatefilter-animation-{filters["animation"]}'),
       InlineKeyboardButton('✅' if filters['animation'] else '❌',
                    callback_data=f'settings#updatefilter-animation-{filters["animation"]}')
       ],[
       InlineKeyboardButton('🃏 Stickers',
                    callback_data=f'settings_#updatefilter-sticker-{filters["sticker"]}'),
       InlineKeyboardButton('✅' if filters['sticker'] else '❌',
                    callback_data=f'settings#updatefilter-sticker-{filters["sticker"]}')
       ],[
       InlineKeyboardButton('▶️ Skip duplicate',
                    callback_data=f'settings_#updatefilter-duplicate-{filter["duplicate"]}'),
       InlineKeyboardButton('✅' if filter['duplicate'] else '❌',
                    callback_data=f'settings#updatefilter-duplicate-{filter["duplicate"]}')
       ],[
       InlineKeyboardButton('🖼️📝 Image+Text',
                    callback_data=f'settings_#updatefilter-image_text-{filters["image_text"]}'),
       InlineKeyboardButton('✅' if filters['image_text'] else '❌',
                    callback_data=f'settings#updatefilter-image_text-{filters["image_text"]}')
       ],[
       InlineKeyboardButton('⫷ back',
                    callback_data="settings#main")
       ]]
  return InlineKeyboardMarkup(buttons)

async def next_filters_buttons(user_id):
  filter = await get_configs(user_id)
  filters = filter['filters']
  buttons = [[
       InlineKeyboardButton('📊 Poll',
                    callback_data=f'settings_#updatefilter-poll-{filters["poll"]}'),
       InlineKeyboardButton('✅' if filters['poll'] else '❌',
                    callback_data=f'settings#updatefilter-poll-{filters["poll"]}')
       ],[
       InlineKeyboardButton('🔒 Secure message',
                    callback_data=f'settings_#updatefilter-protect-{filter["protect"]}'),
       InlineKeyboardButton('✅' if filter['protect'] else '❌',
                    callback_data=f'settings#updatefilter-protect-{filter["protect"]}')
       ],[
       InlineKeyboardButton('🛑 size limit',
                    callback_data='settings#file_size')
       ],[
       InlineKeyboardButton('💾 Extension',
                    callback_data='settings#get_extension')
       ],[
       InlineKeyboardButton('♦️ keywords ♦️',
                    callback_data='settings#get_keyword')
       ],[
       InlineKeyboardButton('⫷ back',
                    callback_data="settings#main")
       ]]
  return InlineKeyboardMarkup(buttons)