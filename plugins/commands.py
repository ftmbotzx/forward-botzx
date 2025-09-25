import os
import sys
import asyncio 
import logging
import psutil
import speedtest
import platform
import subprocess
from datetime import datetime
from database import db, mongodb_version
from config import Config, temp
from platform import python_version
from translation import Translation
from utils.notifications import NotificationManager
from pyrogram import filters, enums, __version__ as pyrogram_version
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaDocument
from pyrogram import Client
# Setup logging
logger = logging.getLogger(__name__)

main_buttons = [[
        InlineKeyboardButton('📜 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ ', url=Config.SUPPORT_GROUP),
        InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ  ', url=Config.UPDATE_CHANNEL)
        ],[
        InlineKeyboardButton('🎁 Get Free Trial', callback_data='get_free_trial'),
        InlineKeyboardButton('📊 My Plan', callback_data='my_plan')
        ],[
        InlineKeyboardButton('💎 Premium Plans', callback_data='premium_plans'),
        InlineKeyboardButton('🙋‍♂️ ʜᴇʟᴘ', callback_data='help')
        ],[
        InlineKeyboardButton('💁‍♂️ ᴀʙᴏᴜᴛ ', callback_data='about'),
        InlineKeyboardButton('⚙️ sᴇᴛᴛɪɴɢs ⚙️', callback_data='settings#main')
        ],[
        InlineKeyboardButton('📄 Updates', callback_data='updates_menu'),
        InlineKeyboardButton('📞 Contact Admin', callback_data='contact_admin')
        ]]

# Force subscribe buttons
force_sub_buttons = [[
        InlineKeyboardButton('📜 Join Support Group', url=Config.SUPPORT_GROUP),
        InlineKeyboardButton('🤖 Join Update Channel', url=Config.UPDATE_CHANNEL)
        ],[
        InlineKeyboardButton('✅ Check Subscription', callback_data='check_subscription')
        ]]


#===================Start Function===================#
@Client.on_message(filters.command("start"))
async def startsss(client, message):
    user = message.from_user
    logger.info(f"Start command from user {user.id} ({user.first_name})")

    try:
        # Send initial processing message
        processing_msg = await message.reply_text("🔄 Processing your request...", quote=True)
        
        if not await db.is_user_exist(user.id):
            await db.add_user(user.id, user.first_name)
            logger.info(f"New user added: {user.id}")

            # Notify about new user
            try:
                notify = NotificationManager(client)
                await notify.notify_user_action(user.id, "New User Registration", f"User: {user.first_name}")
            except Exception as notify_err:
                logger.error(f"Notification error: {notify_err}")

        # Auto-grant premium to sudo users (owners and admins)
        if Config.is_sudo_user(user.id):
            if not await db.is_premium_user(user.id):
                from datetime import datetime, timedelta
                # Grant unlimited premium to sudo users (expires in 10 years)
                await db.add_premium_user(user.id, "pro", 3650, 0)
                logger.info(f"Auto-granted premium to sudo user: {user.id}")

        # Check force subscribe for non-sudo users only
        if not Config.is_sudo_user(user.id):
            try:
                subscription_status = await db.check_force_subscribe(user.id, client)
                if not subscription_status.get('all_subscribed', True):
                    force_sub_text = (
                        "🔒 <b>Subscribe Required!</b>\n\n"
                        "To use this bot, you must join our official channels:\n\n"
                        "📜 <b>Support Group:</b> Get help and updates\n"
                        "🤖 <b>Update Channel:</b> Latest features and announcements\n\n"
                        "After joining both channels, click '✅ Check Subscription' to continue."
                    )
                    await processing_msg.edit_text(
                        text=force_sub_text,
                        reply_markup=InlineKeyboardMarkup(force_sub_buttons),
                        parse_mode=enums.ParseMode.HTML
                    )
                    return
            except Exception as sub_err:
                logger.error(f"Force subscribe check error: {sub_err}")
                # Continue with normal flow if force subscribe fails

        reply_markup = InlineKeyboardMarkup(main_buttons)
        
        # Try to send sticker, but don't fail if it doesn't work
        try:
            jishubotz = await message.reply_sticker("CAACAgUAAxkBAAECEEBlLA-nYcsWmsNWgE8-xqIkriCWAgACJwEAAsiUZBTiPWKAkUSmmh4E")
            await asyncio.sleep(2)
            await jishubotz.delete()
        except Exception as sticker_err:
            logger.error(f"Sticker error: {sticker_err}")

        text = Translation.START_TXT.format(user.mention)
        await processing_msg.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        logger.info(f"Start message sent to user {user.id}")
        
    except Exception as e:
        logger.error(f"Error in start command for user {user.id}: {e}", exc_info=True)
        try:
            await message.edit_text(
                "❌ An error occurred. Please try again.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data='back')]])
            )
        except:
            await message.reply_text(
                "❌ An error occurred. Please try again.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data='back')]])
            )

# Force subscribe callback handler
@Client.on_callback_query(filters.regex(r'^check_subscription$'))
async def check_subscription_callback(client, callback_query):
    user_id = callback_query.from_user.id

    try:
        # Check if user is now subscribed
        subscription_status = await db.check_force_subscribe(user_id, client)

        if subscription_status['all_subscribed']:
            await callback_query.answer("✅ Subscription verified! Welcome!", show_alert=True)

            # Show main menu
            reply_markup = InlineKeyboardMarkup(main_buttons)
            text = f"🎉 <b>Welcome {callback_query.from_user.first_name}!</b>\n\n" + Translation.START_TXT.format(callback_query.from_user.mention)

            await callback_query.message.edit_text(
                text=text,
                reply_markup=reply_markup
            )
        else:
            missing = []
            if not subscription_status['update_channel']:
                missing.append("Update Channel")
            if not subscription_status['support_group']:
                missing.append("Support Group")

            await callback_query.answer(f"❌ Please join: {', '.join(missing)}", show_alert=True)

    except Exception as e:
        await callback_query.answer("❌ Error checking subscription. Please try again.", show_alert=True)

# Premium plans callback handler
@Client.on_callback_query(filters.regex(r'^premium'))
async def premium_callback(client, callback_query):
    user_id = callback_query.from_user.id
    callback_data = callback_query.data

    if callback_data in ['premium_plans', 'premium#plans', 'premium#main']:
        # Get user's current plan
        current_plan = "FREE"
        plan_details = await db.get_premium_user_details(user_id)

        if plan_details:
            current_plan = plan_details.get('plan_type', 'FREE').upper()

        plans_text = (
            "💎 <b>Premium Plans</b>\n\n"
            f"👤 <b>Your Current Plan:</b> {current_plan}\n"
        )

        if plan_details and plan_details.get('expires_at'):
            from datetime import datetime
            expires_at = plan_details['expires_at']
            if expires_at > datetime.utcnow():
                plans_text += f"⏰ <b>Expires:</b> {expires_at.strftime('%Y-%m-%d %H:%M')}\n"

        plans_text += (
            "\n📋 <b>Available Plans:</b>\n\n"
            "🆓 <b>FREE PLAN</b>\n"
            "• 1 forwarding process per month\n"
            "• Basic features only\n"
            "• No FTM mode\n\n"

            "✨ <b>PLUS PLAN</b>\n"
            "• Unlimited forwarding processes\n"
            "• All basic features\n"
            "• No FTM mode\n"
            "• 15 days: ₹199\n"
            "• 30 days: ₹299\n\n"

            "🏆 <b>PRO PLAN</b>\n"
            "• Unlimited forwarding processes\n"
            "• FTM mode enabled\n"
            "• Priority support\n"
            "• All premium features\n"
            "• 15 days: ₹299\n"
            "• 30 days: ₹549\n\n"

            "💳 <b>Payment:</b> UPI - 6354228145@axl\n"
            "📸 <b>After payment, send screenshot with /verify</b>"
        )

        plans_buttons = [
            [
                InlineKeyboardButton("✨ Plus 15 Days (₹199)", callback_data="buy_plus_15"),
                InlineKeyboardButton("✨ Plus 30 Days (₹299)", callback_data="buy_plus_30")
            ],
            [
                InlineKeyboardButton("🏆 Pro 15 Days (₹299)", callback_data="buy_pro_15"),
                InlineKeyboardButton("🏆 Pro 30 Days (₹549)", callback_data="buy_pro_30")
            ],
            [
                InlineKeyboardButton("📊 My Plan Details", callback_data="my_plan"),
                InlineKeyboardButton("🔙 Back", callback_data="back")
            ]
        ]

        await callback_query.message.edit_text(
            text=plans_text,
            reply_markup=InlineKeyboardMarkup(plans_buttons)
        )



#==================Restart Function==================#

@Client.on_message(filters.private & filters.command(['restart', "r"]) & filters.user(Config.OWNER_ID))
async def restart(client, message):
    msg = await message.reply_text(
        text="<i>Trying To Restarting.....</i>",
        quote=True
    )
    await asyncio.sleep(5)
    await msg.edit("<i>Server Restarted Successfully ✅</i>")
    os.execl(sys.executable, sys.executable, *sys.argv)



#==================Callback Functions==================#

#==================Test Command==================#

@Client.on_message(filters.private & filters.command(['test', 'ping']))
async def test_command(client, message):
    """Simple test command to check if bot is responding"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    logger.info(f"Test command from user {user_id} ({user_name})")
    
    try:
        await message.reply_text(
            f"✅ <b>Bot is working!</b>\n\n"
            f"<b>User:</b> {user_name}\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n"
            f"<b>Is Admin:</b> {'Yes' if Config.is_sudo_user(user_id) else 'No'}\n"
            f"<b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
    except Exception as e:
        logger.error(f"Error in test command: {e}")
        await message.reply_text("❌ Error in test command", quote=True)

#==================Help Command==================#

@Client.on_message(filters.private & filters.command(['help']))
async def help_command(client, message):
    user_id = message.from_user.id
    logger.info(f"Help command from user {user_id}")

    try:
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
                return await message.reply_text(
                    text=force_sub_text,
                    reply_markup=InlineKeyboardMarkup(force_sub_buttons),
                    quote=True
                )

        # Check if user is admin to show admin commands
        is_admin = Config.is_sudo_user(user_id)

        # Create help buttons
        buttons = [[
            InlineKeyboardButton('🛠️ How To Use Me 🛠️', callback_data='how_to_use')
        ],[
            InlineKeyboardButton('⚙️ Settings ⚙️', callback_data='settings#main'),
            InlineKeyboardButton('📊 Stats 📊', callback_data='status')
        ],[
            InlineKeyboardButton('💬 Contact Admin', callback_data='contact_admin')
        ]]

        # Add admin commands button for admins only
        if is_admin:
            buttons.append([InlineKeyboardButton('👨‍💻 Admin Commands 👨‍💻', callback_data='admin_commands')])

        buttons.append([InlineKeyboardButton('🔙 Back', callback_data='back')])

        await message.reply_text(
            text=Translation.HELP_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        logger.debug(f"Help message sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error in help command for user {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ An error occurred. Please try again.")

@Client.on_callback_query(filters.regex(r'^help$'))
async def helpcb(bot, query):
    user_id = query.from_user.id
    logger.info(f"Help callback from user {user_id}")

    try:
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

        # Check if user is admin to show admin commands
        is_admin = Config.is_sudo_user(user_id)

        # Create help buttons
        buttons = [[
            InlineKeyboardButton('🛠️ How To Use Me 🛠️', callback_data='how_to_use')
        ],[
            InlineKeyboardButton('⚙️ Settings ⚙️', callback_data='settings#main'),
            InlineKeyboardButton('📊 Stats 📊', callback_data='status')
        ],[
            InlineKeyboardButton('💬 Contact Admin', callback_data='contact_admin')
        ]]

        # Add admin commands button for admins only
        if is_admin:
            buttons.append([InlineKeyboardButton('👨‍💻 Admin Commands 👨‍💻', callback_data='admin_commands')])

        buttons.append([InlineKeyboardButton('🔙 Back', callback_data='back')])

        await query.message.edit_text(
            text=Translation.HELP_TXT,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        logger.debug(f"Help message sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error in help callback for user {user_id}: {e}", exc_info=True)


@Client.on_callback_query(filters.regex(r'^admin_commands$'))
async def admin_commands_callback(bot, query):
    user_id = query.from_user.id
    logger.info(f"Admin commands callback from user {user_id}")

    # Double-check admin status
    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to access admin commands!", show_alert=True)

    try:
        admin_buttons = [[
            InlineKeyboardButton('💎 Add Premium', callback_data='admin_add_premium'),
            InlineKeyboardButton('❌ Remove Premium', callback_data='admin_remove_premium')
        ],[
            InlineKeyboardButton('👥 Premium Users', callback_data='admin_premium_users'),
            InlineKeyboardButton('💰 Change Price', callback_data='admin_change_price')
        ],[
            InlineKeyboardButton('💬 Start Chat', callback_data='admin_start_chat'),
            InlineKeyboardButton('📊 System Info', callback_data='admin_system')
        ],[
            InlineKeyboardButton('⚡ Speed Test', callback_data='admin_speedtest'),
            InlineKeyboardButton('🔄 Restart Bot', callback_data='admin_restart')
        ],[
            InlineKeyboardButton('🗑️ Reset All Users', callback_data='admin_resetall_info'),
            InlineKeyboardButton('🔙 Back to Help', callback_data='help')
        ]]

        await query.message.edit_text(
            text="<b>🔧 Admin Commands Panel</b>\n\n"
                 "<b>Premium Management Commands:</b>\n"
                 "• <code>/add_premium [user_id] [plan_type] [days]</code>\n"
                 "  Plan types: <b>plus</b> or <b>pro</b>\n"
                 "  Example: <code>/add_premium 123456789 pro 30</code>\n"
                 "• <code>/remove_premium [user_id]</code>\n\n"
                 "<b>User Management:</b>\n"
                 "• <code>/users</code> - List all registered users\n\n"
                 "<b>System Tools:</b> Monitor server performance\n"
                 "<b>User Support:</b> Direct chat with users\n"
                 "<b>Bot Control:</b> Restart and configuration\n\n"
                 "<i>These commands are only visible to admins and owners.</i>",
            reply_markup=InlineKeyboardMarkup(admin_buttons)
        )
        logger.debug(f"Admin commands panel sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error in admin commands callback for user {user_id}: {e}", exc_info=True)


@Client.on_callback_query(filters.regex(r'^how_to_use'))
async def how_to_use(bot, query):
    user_id = query.from_user.id
    logger.info(f"How to use callback from user {user_id}")

    try:
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

        await query.message.edit_text(
            text=Translation.HOW_USE_TXT,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data='help')]]),
            disable_web_page_preview=True
        )
        logger.debug(f"How to use message sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error in how_to_use callback for user {user_id}: {e}", exc_info=True)



@Client.on_callback_query(filters.regex(r'^back'))
async def back(bot, query):
    user_id = query.from_user.id
    logger.info(f"Back callback from user {user_id}")

    try:
        reply_markup = InlineKeyboardMarkup(main_buttons)
        await query.message.edit_text(
           reply_markup=reply_markup,
           text=Translation.START_TXT.format(
                    query.from_user.first_name))
        logger.debug(f"Back to main menu for user {user_id}")
    except Exception as e:
        logger.error(f"Error in back callback for user {user_id}: {e}", exc_info=True)



@Client.on_callback_query(filters.regex(r'^about'))
async def about(bot, query):
    user_id = query.from_user.id
    logger.info(f"About callback from user {user_id}")

    try:
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

        await query.message.edit_text(
            text=Translation.ABOUT_TXT,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data='back')]]),
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML,
        )
        logger.debug(f"About message sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error in about callback for user {user_id}: {e}", exc_info=True)



@Client.on_callback_query(filters.regex(r'^status'))
async def status(bot, query):
    user_id = query.from_user.id
    logger.info(f"Status callback from user {user_id}")

    try:
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

        users_count, bots_count = await db.total_users_bots_count()
        total_channels = await db.total_channels()
        await query.message.edit_text(
            text=Translation.STATUS_TXT.format(users_count, bots_count, temp.forwardings, total_channels),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data='help')]]),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
        )
        logger.debug(f"Status message sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error in status callback for user {user_id}: {e}", exc_info=True)


#==================Speedtest Command==================#

@Client.on_message(filters.private & filters.command(['speedtest', 'speed']))
async def speed_test_command(client, message):
    user_id = message.from_user.id
    logger.info(f"Speedtest command from user {user_id}")

    # Check if user is sudo user (owner or admin)
    if not Config.is_sudo_user(user_id):
        return await message.reply_text("❌ This command is only available for administrators.")

    status_msg = await message.reply_text("🔄 <b>Running Network Speed Test...</b>\n⏳ Please wait, this may take a moment.")

    try:
        # Initialize speedtest
        st = speedtest.Speedtest()

        # Update status
        await status_msg.edit_text("🔄 <b>Finding best server...</b>\n⏳ Please wait.")

        # Get best server
        st.get_best_server()

        # Update status
        await status_msg.edit_text("🔄 <b>Testing download speed...</b>\n⏳ Please wait.")

        # Test download speed
        download_speed = st.download()

        # Update status  
        await status_msg.edit_text("🔄 <b>Testing upload speed...</b>\n⏳ Please wait.")

        # Test upload speed
        upload_speed = st.upload()

        # Get ping
        ping = st.results.ping

        # Get server info
        server = st.get_best_server()

        # Convert bytes to Mbps
        download_mbps = download_speed / 1024 / 1024
        upload_mbps = upload_speed / 1024 / 1024

        # Format the result
        speed_text = f"""<b>🌐 Bot Server Network Speed Test</b>

<b>📡 Server Connection Info:</b>
├ <b>ISP:</b> <code>{server.get('sponsor', 'Unknown')}</code>
├ <b>Server Location:</b> <code>{server.get('name', 'Unknown')}, {server.get('country', 'Unknown')}</code>
├ <b>Distance:</b> <code>{server.get('d', 0):.1f} km</code>

<b>🚀 Bot Server Speed Results:</b>
├ <b>📥 Download:</b> <code>{download_mbps:.2f} Mbps</code>
├ <b>📤 Upload:</b> <code>{upload_mbps:.2f} Mbps</code>
├ <b>📶 Ping:</b> <code>{ping:.1f} ms</code>

<b>📊 Test Information:</b>
├ <b>Test Date:</b> <code>{st.results.timestamp}</code>
├ <b>Note:</b> <code>Shows bot server network, not your location</code>
└ <b>Share URL:</b> <a href="{st.results.share()}">View Results</a>"""

        await status_msg.edit_text(speed_text, disable_web_page_preview=True)
        logger.info(f"Speedtest completed for user {user_id}")

    except Exception as e:
        error_msg = f"❌ <b>Speed Test Failed</b>\n\n<b>Error:</b> <code>{str(e)}</code>"
        await status_msg.edit_text(error_msg)
        logger.error(f"Speedtest error for user {user_id}: {e}", exc_info=True)


#==================System Info Command==================#

@Client.on_message(filters.private & filters.command(['system', 'sys', 'sysinfo']))
async def system_info_command(client, message):
    user_id = message.from_user.id
    logger.info(f"System info command from user {user_id}")

    # Check if user is sudo user (owner or admin)  
    if not Config.is_sudo_user(user_id):
        return await message.reply_text("❌ This command is only available for administrators.")

    status_msg = await message.reply_text("🔄 <b>Gathering system information...</b>")

    try:
        # Get system info
        uname = platform.uname()

        # Get CPU info
        cpu_count = psutil.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq()

        # Get memory info
        memory = psutil.virtual_memory()
        memory_total = memory.total / (1024**3)  # GB
        memory_used = memory.used / (1024**3)   # GB
        memory_percent = memory.percent

        # Get disk info
        disk = psutil.disk_usage('/')
        disk_total = disk.total / (1024**3)  # GB
        disk_used = disk.used / (1024**3)    # GB
        disk_percent = (disk.used / disk.total) * 100

        # Get network info
        net_io = psutil.net_io_counters()
        bytes_sent = net_io.bytes_sent / (1024**2)  # MB
        bytes_recv = net_io.bytes_recv / (1024**2)  # MB

        # Get boot time
        boot_time = psutil.boot_time()

        # Get process info
        process_count = len(psutil.pids())

        # Get Python info
        python_ver = python_version()

        # Format uptime
        import datetime
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(boot_time)
        uptime_str = str(uptime).split('.')[0]

        # Get load average (Unix-like systems)
        try:
            load_avg = os.getloadavg()
            load_str = f"{load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}"
        except:
            load_str = "Not Available"

        system_text = f"""<b>🖥️ Bot Server System Information</b>

<b>💻 Server System Details:</b>
├ <b>OS:</b> <code>{uname.system} {uname.release}</code>
├ <b>Architecture:</b> <code>{uname.machine}</code>
├ <b>Hostname:</b> <code>{uname.node}</code>
├ <b>Kernel:</b> <code>{uname.version}</code>

<b>🔧 Server Hardware Info:</b>
├ <b>CPU Cores:</b> <code>{cpu_count} cores</code>
├ <b>CPU Usage:</b> <code>{cpu_percent}%</code>
├ <b>CPU Frequency:</b> <code>{cpu_freq.current:.0f} MHz</code> (Max: <code>{cpu_freq.max:.0f} MHz</code>)
├ <b>Load Average:</b> <code>{load_str}</code>

<b>💾 Server Memory Info:</b>
├ <b>Total RAM:</b> <code>{memory_total:.2f} GB</code>
├ <b>Used RAM:</b> <code>{memory_used:.2f} GB ({memory_percent}%)</code>
├ <b>Available RAM:</b> <code>{(memory_total - memory_used):.2f} GB</code>

<b>💿 Server Storage Info:</b>
├ <b>Total Disk:</b> <code>{disk_total:.2f} GB</code>
├ <b>Used Disk:</b> <code>{disk_used:.2f} GB ({disk_percent:.1f}%)</code>
├ <b>Free Disk:</b> <code>{(disk_total - disk_used):.2f} GB</code>

<b>🌐 Server Network Usage:</b>
├ <b>Data Sent:</b> <code>{bytes_sent:.2f} MB</code>
├ <b>Data Received:</b> <code>{bytes_recv:.2f} MB</code>

<b>⚡ Bot Runtime Info:</b>
├ <b>Python Version:</b> <code>v{python_ver}</code>
├ <b>Pyrogram Version:</b> <code>v{pyrogram_version}</code>
├ <b>Active Processes:</b> <code>{process_count}</code>
├ <b>Server Uptime:</b> <code>{uptime_str}</code>
├ <b>Note:</b> <code>Shows bot server stats, not your device</code>
└ <b>Bot Status:</b> <code>Running ✅</code>"""

        await status_msg.edit_text(system_text)
        logger.info(f"System info sent to user {user_id}")

    except Exception as e:
        error_msg = f"❌ <b>System Info Failed</b>\n\n<b>Error:</b> <code>{str(e)}</code>"
        await status_msg.edit_text(error_msg)
        logger.error(f"System info error for user {user_id}: {e}", exc_info=True)


#==================Admin Callback Functions==================#

@Client.on_callback_query(filters.regex(r'^admin_change_price$'))
async def admin_change_price_callback(bot, query):
    user_id = query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to use this command!", show_alert=True)

    try:
        await query.message.edit_text(
            text=f"<b>💰 Current Premium Price</b>\n\n"
                 f"<b>Current Price:</b> ₹{Config.PREMIUM_PRICE}/month\n\n"
                 f"<b>To change the price:</b>\n"
                 f"1. Update the PREMIUM_PRICE environment variable\n"
                 f"2. Restart the bot to apply changes\n\n"
                 f"<i>Note: Price changes require bot restart</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^admin_system$'))
async def admin_system_callback(bot, query):
    user_id = query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to use this command!", show_alert=True)

    # Redirect to existing system info command logic
    await system_info_command(bot, query.message)

@Client.on_callback_query(filters.regex(r'^admin_speedtest$'))
async def admin_speedtest_callback(bot, query):
    user_id = query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to use this command!", show_alert=True)

    # Redirect to existing speedtest command logic
    await speed_test_command(bot, query.message)

@Client.on_callback_query(filters.regex(r'^admin_restart$'))
async def admin_restart_callback(bot, query):
    user_id = query.from_user.id

    if user_id not in Config.OWNER_ID:
        return await query.answer("❌ Only owners can restart the bot!", show_alert=True)

    try:
        await query.message.edit_text(
            text="<b>🔄 Bot Restart</b>\n\n"
                 "<b>⚠️ Are you sure you want to restart the bot?</b>\n\n"
                 "<i>This will stop all ongoing processes!</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('✅ Yes, Restart', callback_data='confirm_restart'),
                InlineKeyboardButton('❌ Cancel', callback_data='admin_commands')
            ]])
        )
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^confirm_restart$'))
async def confirm_restart_callback(bot, query):
    user_id = query.from_user.id

    if user_id not in Config.OWNER_ID:
        return await query.answer("❌ Only owners can restart the bot!", show_alert=True)

    await query.message.edit_text("🔄 <b>Restarting bot...</b>\n\n<i>Please wait...</i>")
    await restart(bot, query.message)

@Client.on_callback_query(filters.regex(r'^admin_add_premium$'))
async def admin_add_premium_callback(bot, query):
    user_id = query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to use this command!", show_alert=True)

    try:
        await query.message.edit_text(
            text="<b>💎 Add Premium User</b>\n\n"
                 "<b>How to add premium:</b>\n\n"
                 "1. Use command: <code>/add_premium [user_id] [days]</code>\n"
                 "2. Example: <code>/add_premium 123456789 30</code>\n\n"
                 "<b>Default:</b> 30 days if days not specified\n\n"
                 "<i>Use this command in chat, not through buttons</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^admin_remove_premium$'))
async def admin_remove_premium_callback(bot, query):
    user_id = query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to use this command!", show_alert=True)

    try:
        await query.message.edit_text(
            text="<b>❌ Remove Premium User</b>\n\n"
                 "<b>How to remove premium:</b>\n\n"
                 "1. Use command: <code>/remove_premium [user_id]</code>\n"
                 "2. Example: <code>/remove_premium 123456789</code>\n\n"
                 "<i>Use this command in chat, not through buttons</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^admin_premium_users$'))
async def admin_premium_users_callback(bot, query):
    user_id = query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to use this command!", show_alert=True)

    try:
        await query.message.edit_text(
            text="<b>👥 Premium Users List</b>\n\n"
                 "<b>How to view premium users:</b>\n\n"
                 "1. Use command: <code>/pusers</code>\n\n"
                 "<i>Use this command in chat for detailed list</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^admin_start_chat$'))
async def admin_start_chat_callback(bot, query):
    user_id = query.from_user.id

    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to use this command!", show_alert=True)

    try:
        await query.message.edit_text(
            text="<b>💬 Start Admin Chat</b>\n\n"
                 "<b>How to start chat with user:</b>\n\n"
                 "1. Use command: <code>/chat [user_id]</code>\n"
                 "2. Example: <code>/chat 123456789</code>\n\n"
                 "<b>To end chat:</b> <code>/endchat</code>\n\n"
                 "<i>Use these commands in chat, not through buttons</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^admin_resetall_info$'))
async def admin_resetall_info_callback(bot, query):
    user_id = query.from_user.id

    if user_id not in Config.OWNER_ID:
        return await query.answer("❌ Only owners can reset all users!", show_alert=True)

    try:
        await query.message.edit_text(
            text="<b>🗑️ Reset Commands Information</b>\n\n"
                 "<b>Available Reset Commands:</b>\n\n"
                 "<b>1. Individual User Reset:</b>\n"
                 "• Command: <code>/reset</code>\n"
                 "• Resets your own data only\n"
                 "• Available to all users\n\n"
                 "<b>2. Reset All Users (Owner Only):</b>\n"
                 "• Command: <code>/resetall</code>\n"
                 "• Resets ALL users' data\n"
                 "• Only available to owners\n\n"
                 "<b>⚠️ Warning:</b> Reset commands will permanently delete:\n"
                 "• All configurations\n"
                 "• All bot connections\n"
                 "• All channel settings\n"
                 "• All custom preferences\n\n"
                 "<b>❗ These actions cannot be undone!</b>\n\n"
                 "<i>Use these commands in chat for full functionality</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('🔙 Back to Admin', callback_data='admin_commands')
            ]])
        )
    except Exception as e:
        await query.answer(f"Error: {str(e)}", show_alert=True)

#==================Free Trial & Contact Handlers==================#

@Client.on_callback_query(filters.regex(r'^get_free_trial$'))
async def get_free_trial_callback(bot, query):
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    logger.info(f"Free trial requested by user {user_id} ({user_name})")

    try:
        # Check if user can use free trial (1 per month)
        can_process, reason = await db.can_user_process(user_id)

        if not can_process and reason == "monthly_limit_reached":
            await query.answer(
                "❌ You have already used your free trial this month!\n"
                "💎 Upgrade to Premium for unlimited access.",
                show_alert=True
            )
            return

        if await db.is_premium_user(user_id):
            await query.answer(
                "✅ You already have Premium access!\n"
                "No need for free trial - you have unlimited processes.",
                show_alert=True
            )
            return

        # Grant the free trial (add 1 extra process - total 2 for this month)
        trial_granted = await db.add_trial_processes(user_id, 1)

        if not trial_granted:
            await query.answer(
                "❌ You have already claimed your free trial this month!\n"
                "💎 Upgrade to Premium for unlimited access.",
                show_alert=True
            )
            return

        # Send notification to admins
        try:
            notify = NotificationManager(bot)
            await notify.notify_free_trial_activity(
                user_id=user_id, 
                action="activated free trial", 
                remaining_usage=1  # User now has 2 total processes (1 base + 1 trial)
            )
        except Exception as notify_err:
            logger.error(f"Failed to send free trial notification: {notify_err}")

        # Send confirmation message to user
        await query.message.edit_text(
            text="<b>🎉 Free Trial Activated!</b>\n\n"
                 "<b>✅ You have received +1 additional process for this month!</b>\n\n"
                 "<b>📋 Your monthly allowance:</b>\n"
                 "• Base free plan: 1 process\n"
                 "• Trial bonus: +1 process\n"
                 "• <b>Total available: 2 processes</b>\n\n"
                 "<b>What you can do:</b>\n"
                 "• Use /forward to start forwarding messages\n"
                 "• Process two forwarding jobs this month\n\n"
                 "<b>💎 Want unlimited access?</b>\n"
                 "Upgrade to Premium:\n"
                 "• <b>Plus Plan:</b> ₹199/15d, ₹299/30d - Unlimited forwarding\n"
                 "• <b>Pro Plan:</b> ₹299/15d, ₹549/30d - Unlimited + FTM Mode + Priority support\n\n"
                 "<b>🗓️ Resets:</b> 1st of next month",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('🚀 Start Forwarding', callback_data='settings#main')],
                [InlineKeyboardButton('💎 Upgrade to Premium', callback_data='premium_info')],
                [InlineKeyboardButton('🔙 Back to Menu', callback_data='back')]
            ])
        )

        logger.info(f"Free trial granted to user {user_id}")

    except Exception as e:
        logger.error(f"Error in free trial callback for user {user_id}: {e}", exc_info=True)
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r'^contact_admin$'))
async def contact_admin_callback(bot, query):
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    user_username = f"@{query.from_user.username}" if query.from_user.username else ""
    logger.info(f"Contact admin callback from user {user_id} ({user_name})")

    try:
        # Check if user already has a pending chat request
        existing_request = await db.get_pending_chat_request(user_id)
        if existing_request:
            await query.answer(
                "⏳ You already have a pending chat request.\n"
                "Please wait for admin approval.",
                show_alert=True
            )
            return

        # Check if user is already in an active chat
        active_chat = await db.get_active_chat_for_user(user_id)
        if active_chat:
            await query.answer(
                "💬 You already have an active chat session with admin!\n"
                "Just send your message and it will be forwarded.",
                show_alert=True
            )
            return

        # Create chat request
        request_id = await db.create_chat_request(user_id)

        # Notification for contact request
        try:
            from utils.notifications import NotificationManager
            notification_manager = NotificationManager(bot)
            await notification_manager.notify_contact_request(
                user_id=user_id,
                request_type="general support",
                status="submitted"
            )
        except Exception as notif_err:
            logger.error(f"Failed to send contact request notification: {notif_err}")

        await query.message.edit_text(
            text="<b>💬 Contact Request Submitted!</b>\n\n"
                 "<b>Your request to contact admin has been submitted.</b>\n"
                 "<b>⏳ Please wait for admin approval.</b>\n\n"
                 f"<b>Request ID:</b> <code>{request_id}</code>\n"
                 "<b>💬 You will be notified once an admin accepts your request.</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('🔙 Back to Menu', callback_data='back')]
            ])
        )

        # Send notification to all sudo users (admin + owner) with accept/deny options
        sudo_users = Config.OWNER_ID + Config.ADMIN_ID

        for sudo_id in sudo_users:
            try:
                buttons = [
                    [
                        InlineKeyboardButton("✅ Accept Chat", callback_data=f"accept_chat_{request_id}"),
                        InlineKeyboardButton("❌ Deny", callback_data=f"deny_chat_{request_id}")
                    ]
                ]

                await bot.send_message(
                    sudo_id,
                    f"<b>💬 New Contact Request</b>\n\n"
                    f"<b>User:</b> {user_name} {user_username}\n"
                    f"<b>User ID:</b> <code>{user_id}</code>\n"
                    f"<b>Request ID:</b> <code>{request_id}</code>\n"
                    f"<b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                    f"<b>Choose an action:</b>",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception as send_err:
                logger.error(f"Failed to send contact request to admin {sudo_id}: {send_err}")

        logger.info(f"Contact request created: {request_id} for user {user_id}")

    except Exception as e:
        logger.error(f"Error in contact admin callback for user {user_id}: {e}", exc_info=True)
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r'^premium_info$'))
async def premium_info_callback(bot, query):
    user_id = query.from_user.id
    logger.info(f"Premium info callback from user {user_id}")

    try:
        # Notification for plan exploration
        try:
            from utils.notifications import NotificationManager
            notification_manager = NotificationManager(bot)
            await notification_manager.notify_plan_exploration(
                user_id=user_id, 
                plan_type="Premium Plan Information", 
                action="viewed premium info", 
                source="main menu button"
            )
        except Exception as notif_err:
            logger.error(f"Failed to send plan exploration notification: {notif_err}")

        await query.message.edit_text(
            text=Translation.PLAN_INFO_MSG,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('📊 Check My Plan', callback_data='my_plan')],
                [InlineKeyboardButton('💬 Contact Admin', callback_data='contact_admin')],
                [InlineKeyboardButton('🔙 Back to Menu', callback_data='back')]
            ])
        )
    except Exception as e:
        logger.error(f"Error in premium info callback for user {user_id}: {e}", exc_info=True)

@Client.on_callback_query(filters.regex(r'^future_updates$'))
async def future_updates_callback(bot, query):
    user_id = query.from_user.id
    logger.info(f"Future updates callback from user {user_id}")

    try:
        # Professional and exciting future updates text
        future_updates_text = """<b>🚀 ғᴜᴛᴜʀᴇ ᴜᴘᴅᴀᴛᴇs - ᴄᴏᴍɪɴɢ ᴠᴇʀʏ sᴏᴏɴ! 🚀</b>

<b>📅 ɴᴇxᴛ ᴍᴀᴊᴏʀ ᴜᴘᴅᴀᴛᴇ</b>
<i>specially designed for our beloved free users! 💝</i>

<b>🎯 ᴡʜᴀᴛ's ᴄᴏᴍɪɴɢ:</b>
• enhanced user experience for everyone
• improved performance optimizations
• new features accessible to all users
• revolutionary forwarding capabilities

<b>⚡ ғᴛᴍ ᴀʟᴘʜᴀ ᴍᴏᴅᴇ ᴠ2.0</b>
<blockquote expandable>🔥 <b>revolutionary real-time auto-forwarding system</b>

<b>🌟 amazing features:</b>
• lightning-fast real-time message sync
• zero-delay forwarding between channels
• smart duplicate detection & filtering  
• advanced message customization
• intelligent rate limiting system
• cross-platform compatibility
• enhanced security protocols

<b>🎁 secret bonus:</b>
<blockquote>this update includes special tier access for free users! selected free users will get limited alpha mode access through our community program. stay tuned for announcements! 🤫✨</blockquote>

<b>💡 technical highlights:</b>
• powered by next-gen pyrogram v2 architecture
• supports 50+ simultaneous channel connections
• ai-powered content filtering
• blockchain-inspired message verification
• quantum-resistant encryption protocols</blockquote>

<b>📢 ᴇxᴄɪᴛɪɴɢ ɴᴇᴡs!</b>
this update is specially crafted for users who want premium features but can't afford subscriptions. we believe everyone deserves access to powerful tools! 

<b>🗓️ ᴇxᴘᴇᴄᴛᴇᴅ ʀᴇʟᴇᴀsᴇ:</b> very soon™️
<b>🎯 ᴛᴀʀɢᴇᴛ ᴀᴜᴅɪᴇɴᴄᴇ:</b> free users & community members
<b>💖 ᴘʀɪᴏʀɪᴛʏ:</b> making premium features accessible to all

<i>stay connected to our support group for exclusive early access! 🌟</i>"""

        # Add exciting buttons with proper spacing
        buttons = [
            [InlineKeyboardButton('🔔 ɢᴇᴛ ɴᴏᴛɪғɪᴇᴅ', callback_data='notify_updates')],
            [InlineKeyboardButton('📱 ᴊᴏɪɴ ᴄᴏᴍᴍᴜɴɪᴛʏ', url=Config.SUPPORT_GROUP)],
            [InlineKeyboardButton('🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ', callback_data='back')]
        ]

        await query.message.edit_text(
            text=future_updates_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

        # Notification for future updates interest
        try:
            from utils.notifications import NotificationManager
            notification_manager = NotificationManager(bot)
            await notification_manager.notify_plan_exploration(
                user_id=user_id, 
                plan_type="Future Updates", 
                action="viewed upcoming features", 
                source="future updates menu"
            )
        except Exception as notif_err:
            logger.error(f"Failed to send future updates notification: {notif_err}")

    except Exception as e:
        logger.error(f"Error in future updates callback for user {user_id}: {e}", exc_info=True)
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r'^notify_updates$'))
async def notify_updates_callback(bot, query):
    user_id = query.from_user.id

    try:
        await query.answer(
            "🔔 You'll be notified about exciting updates!\n"
            "💡 Join our support group for exclusive early access to alpha features.",
            show_alert=True
        )
    except Exception as e:
        logger.error(f"Error in notify updates callback: {e}")

# =================== Updates Menu Functions ===================

@Client.on_callback_query(filters.regex(r'^updates_menu$'))
async def updates_menu_callback(bot, query):
    user_id = query.from_user.id
    logger.info(f"Updates menu callback from user {user_id}")

    try:
        updates_menu_text = """<b>📄 Developer Updates</b>

<b>Stay informed about latest changes and upcoming features!</b>

<b>📋 Available Options:</b>
• <b>This Update</b> - View current update changes
• <b>Upcoming Update</b> - Preview future features

<i>Select an option to continue:</i>"""

        buttons = [
            [InlineKeyboardButton('📊 This Update', callback_data='this_update')],
            [InlineKeyboardButton('🚀 Upcoming Update', callback_data='upcoming_update')],
            [InlineKeyboardButton('🔙 Back to Menu', callback_data='back')]
        ]

        await query.message.edit_text(
            text=updates_menu_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Error in updates menu callback for user {user_id}: {e}", exc_info=True)
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r'^this_update$'))
async def this_update_callback(bot, query):
    user_id = query.from_user.id
    logger.info(f"This update callback from user {user_id}")

    try:
        this_update_text = """<b>📊 Current Update - FTM Manager & Events System</b>

<b>🎉 What's New in This Update:</b>

<b>🔧 FTM Manager Updates:</b>
• Renamed "FTM Mode" → "FTM Manager"
• Added new "FTM Event" feature in FTM Manager
• Enhanced navigation and user experience

<b>🎪 Event System Features:</b>
• Pre-loaded <b>Navratri Event</b> with subscription rewards
• Admin event creation system with /event command
• Discount events and Redeem code system
• Group-based redemption (Free/Plus/Pro users)

<b>🎁 Subscription Rewards:</b>
• Free users → 10 days Plus subscription
• Plus users → 10 days Pro subscription  
• Pro users → 10 days Pro subscription extension

<b>⚙️ Admin Features:</b>
• Event scheduling and management
• Code generation with redemption tracking
• Comprehensive logging system

<b>🔗 Access Methods:</b>
• Use /FTM command or Settings → FTM Manager
• View events in FTM Manager → FTM Event
• Redeem codes with /redeem command

<i>This update enhances your bot experience with powerful event management capabilities!</i>"""

        buttons = [
            [InlineKeyboardButton('⚙️ Go to Settings', callback_data='settings#main')],
            [InlineKeyboardButton('🔙 Back to Updates', callback_data='updates_menu')]
        ]

        await query.message.edit_text(
            text=this_update_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Error in this update callback for user {user_id}: {e}", exc_info=True)
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r'^upcoming_update$'))
async def upcoming_update_callback(bot, query):
    user_id = query.from_user.id
    logger.info(f"Upcoming update callback from user {user_id}")

    try:
        upcoming_update_text = """<b>🚀 Upcoming Updates - Coming Very Soon!</b>

<b>📅 Next Major Update</b>
<i>Specially designed for our beloved free users! 💝</i>

<b>🎯 What's Coming:</b>
• Enhanced user experience for everyone
• Improved performance optimizations
• New features accessible to all users
• Revolutionary forwarding capabilities

<b>⚡ FTM Alpha Mode V2.0</b>
<blockquote expandable>🔥 <b>Revolutionary real-time auto-forwarding system</b>

<b>🌟 Amazing Features:</b>
• Lightning-fast real-time message sync
• Zero-delay forwarding between channels
• Smart duplicate detection & filtering  
• Advanced message customization
• Intelligent rate limiting system
• Cross-platform compatibility
• Enhanced security protocols

<b>🎁 Secret Bonus:</b>
<blockquote>This update includes special tier access for free users! Selected free users will get limited alpha mode access through our community program. Stay tuned for announcements! 🤫✨</blockquote>

<b>💡 Technical Highlights:</b>
• Powered by next-gen pyrogram v2 architecture
• Supports 50+ simultaneous channel connections
• AI-powered content filtering
• Blockchain-inspired message verification
• Quantum-resistant encryption protocols</blockquote>

<b>📢 Exciting News!</b>
This update is specially crafted for users who want premium features but can't afford subscriptions. We believe everyone deserves access to powerful tools! 

<b>🗓️ Expected Release:</b> Very Soon™️
<b>🎯 Target Audience:</b> Free users & community members
<b>💖 Priority:</b> Making premium features accessible to all

<i>Stay connected to our support group for exclusive early access! 🌟</i>"""

        buttons = [
            [InlineKeyboardButton('🔔 Get Notified', callback_data='notify_updates')],
            [InlineKeyboardButton('📱 Join Community', url=Config.SUPPORT_GROUP)],
            [InlineKeyboardButton('🔙 Back to Updates', callback_data='updates_menu')]
        ]

        await query.message.edit_text(
            text=upcoming_update_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )

        # Notification for future updates interest
        try:
            from utils.notifications import NotificationManager
            notification_manager = NotificationManager(bot)
            await notification_manager.notify_plan_exploration(
                user_id=user_id, 
                plan_type="Future Updates", 
                action="viewed upcoming features", 
                source="upcoming updates menu"
            )
        except Exception as notif_err:
            logger.error(f"Failed to send upcoming updates notification: {notif_err}")

    except Exception as e:
        logger.error(f"Error in upcoming update callback for user {user_id}: {e}", exc_info=True)
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r'^my_plan$'))
async def my_plan_callback(bot, query):
    user_id = query.from_user.id
    logger.info(f"My plan callback from user {user_id}")

    try:
        # Notification for plan exploration
        try:
            from utils.notifications import NotificationManager
            notification_manager = NotificationManager(bot)
            await notification_manager.notify_plan_exploration(
                user_id=user_id, 
                plan_type="Current Plan Status", 
                action="checked current plan", 
                source="premium info menu"
            )
        except Exception as notif_err:
            logger.error(f"Failed to send plan exploration notification: {notif_err}")

        # Check user's plan status
        premium_info = await db.get_premium_user_details(user_id)
        daily_usage = await db.get_daily_usage(user_id)
        usage_count = daily_usage.get('processes', 0)

        if premium_info:
            # User has active premium plan
            plan_type = premium_info.get('plan_type', 'unknown')
            expires_at = premium_info.get('expires_at', 'Unknown')
            # Calculate days remaining
            from datetime import datetime
            expires_at_obj = premium_info.get('expires_at', datetime.utcnow())
            if isinstance(expires_at_obj, datetime):
                days_remaining = max(0, (expires_at_obj - datetime.utcnow()).days)
            else:
                days_remaining = 0

            if plan_type.lower() == 'plus':
                plan_text = f"""<b>✨ Your Plus Plan</b>

<b>✅ Status:</b> Plus Plan Active
<b>📅 Plan Type:</b> Plus (15-30 days)
<b>⏰ Expires:</b> {expires_at}
<b>⏱️ Days Left:</b> {days_remaining} days
<b>📊 This Month:</b> {usage_count} processes used

<b>🎯 Plus Plan Features:</b>
• ♾️ Unlimited forwarding processes
• ⚡ Standard processing speed
• 🔄 Basic filtering options
• 📱 Standard support

<b>💡 Upgrade to Pro for:</b>
• 🔥 FTM Mode with source tracking
• 🛡️ Priority support
• 🚀 Enhanced performance"""
            elif plan_type.lower() == 'pro':
                plan_text = f"""<b>🔥 Your Pro Plan</b>

<b>✅ Status:</b> Pro Plan Active
<b>📅 Plan Type:</b> Pro (15-30 days)
<b>⏰ Expires:</b> {expires_at}
<b>⏱️ Days Left:</b> {days_remaining} days
<b>📊 This Month:</b> {usage_count} processes used

<b>🚀 Pro Plan Features:</b>
• ♾️ Unlimited forwarding processes
• 🔥 FTM Mode with source tracking
• ⚡ Priority processing speed
• 🛠️ Advanced filtering options
• 🛡️ Priority customer support
• 📈 Enhanced performance"""
            else:
                plan_text = f"""<b>💎 Your Premium Plan</b>

<b>✅ Status:</b> Premium Active
<b>📅 Plan Type:</b> {plan_type}
<b>⏰ Expires:</b> {expires_at}
<b>🔄 Usage:</b> Unlimited processes
<b>📊 This Month:</b> {usage_count} processes used

<b>🎉 You have access to premium features!</b>"""
        else:
            # User is on free plan - check if trial was used
            trial_status = await db.get_trial_status(user_id)
            total_processes = 1  # Base free process
            trial_text = ""
            if trial_status and trial_status.get('used', False):
                total_processes = 2  # Base + trial
                trial_text = " (1 base + 1 trial)"

            plan_text = f"""<b>🆓 Your Free Plan</b>

<b>📊 Status:</b> Free User
<b>🔄 Monthly Usage:</b> {usage_count}/{total_processes} processes
<b>🗓️ Usage Resets:</b> 1st of each month
<b>📈 Remaining:</b> {max(0, total_processes - usage_count)} free processes

<b>💡 Current Features:</b>
• {total_processes}️⃣ {total_processes} free process{'es' if total_processes > 1 else ''} per month{trial_text}
• 🔄 Basic forwarding functionality
• 📋 Standard filtering options

<b>🚀 Available Plans:</b>
<b>✨ Plus Plan:</b> ₹199/15d, ₹299/30d
• Unlimited forwarding

<b>🔥 Pro Plan:</b> ₹299/15d, ₹549/30d  
• Unlimited forwarding + FTM Mode + Priority support"""

        buttons = []
        if not premium_info:
            # Free user - show upgrade options
            buttons.append([InlineKeyboardButton('💎 Upgrade Now', callback_data='premium#main')])
        elif premium_info.get('plan_type', '').lower() == 'plus':
            # Plus user - show Pro upgrade option
            buttons.append([InlineKeyboardButton('🔥 Upgrade to Pro', callback_data='premium#main')])

        buttons.extend([
            [InlineKeyboardButton('💬 Contact Admin', callback_data='contact_admin')],
            [InlineKeyboardButton('🔙 Back to Menu', callback_data='back')]
        ])

        await query.message.edit_text(
            text=plan_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    except Exception as e:
        logger.error(f"Error in my plan callback for user {user_id}: {e}", exc_info=True)
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

# /info command for users to get all their information
@Client.on_message(filters.private & filters.command(['info']))
async def info_command(client, message):
    user = message.from_user
    user_id = user.id
    logger.info(f"Info command from user {user_id}")

    try:
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
                return await message.reply_text(
                    text=force_sub_text,
                    reply_markup=InlineKeyboardMarkup(force_sub_buttons),
                    quote=True
                )

        # Get user information
        premium_info = await db.get_premium_user_details(user_id)
        daily_usage = await db.get_daily_usage(user_id)
        monthly_usage = await db.get_monthly_usage(user_id)
        user_data = await db.get_user(user_id)

        # Format join date
        from datetime import datetime
        join_date = user_data.get('joined_date', datetime.utcnow()) if user_data else datetime.utcnow()
        if isinstance(join_date, datetime):
            join_date_str = join_date.strftime('%Y-%m-%d %H:%M:%S')
        else:
            join_date_str = "Unknown"

        # Build user info text
        info_text = f"<b>👤 Your Account Information</b>\n\n"
        info_text += f"<b>📋 Basic Details:</b>\n"
        info_text += f"• <b>Name:</b> {user.first_name}"
        if user.last_name:
            info_text += f" {user.last_name}"
        info_text += f"\n• <b>Username:</b> @{user.username}" if user.username else "\n• <b>Username:</b> Not set"
        info_text += f"\n• <b>User ID:</b> <code>{user_id}</code>"
        info_text += f"\n• <b>Joined:</b> {join_date_str}\n\n"

        # Subscription status
        if premium_info:
            plan_type = premium_info.get('plan_type', 'unknown').upper()
            expires_at = premium_info.get('expires_at', 'Unknown')
            if isinstance(expires_at, datetime):
                expires_at_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
                days_remaining = max(0, (expires_at - datetime.utcnow()).days)
            else:
                expires_at_str = str(expires_at)
                days_remaining = 0

            info_text += f"<b>💎 Subscription Status:</b>\n"
            info_text += f"• <b>Plan:</b> {plan_type} Plan ✅\n"
            info_text += f"• <b>Expires:</b> {expires_at_str}\n"
            info_text += f"• <b>Days Left:</b> {days_remaining} days\n\n"
        else:
            info_text += f"<b>🆓 Subscription Status:</b>\n"
            info_text += f"• <b>Plan:</b> Free User\n"
            info_text += f"• <b>Limit:</b> 1 process per month\n\n"

        # Usage statistics
        info_text += f"<b>📊 Usage Statistics:</b>\n"
        info_text += f"• <b>This Month:</b> {monthly_usage.get('processes', 0)} processes\n"
        info_text += f"• <b>Today:</b> {daily_usage.get('processes', 0)} processes\n"

        # Get forwarding limit
        limit = await db.get_forwarding_limit(user_id)
        if limit == -1:
            info_text += f"• <b>Limit:</b> Unlimited processes ♾️\n\n"
        else:
            remaining = max(0, limit - monthly_usage.get('processes', 0))
            info_text += f"• <b>Monthly Limit:</b> {limit} processes\n"
            info_text += f"• <b>Remaining:</b> {remaining} processes\n\n"

        info_text += f"<b>Use /myplan for subscription details and upgrade options.</b>"

        await message.reply_text(
            text=info_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('💎 My Plan', callback_data='my_plan')],
                [InlineKeyboardButton('⚙️ Settings', callback_data='settings#main')],
                [InlineKeyboardButton('🔙 Main Menu', callback_data='back')]
            ]),
            quote=True
        )

    except Exception as e:
        logger.error(f"Error in info command for user {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ An error occurred while fetching your information. Please try again.")

# /users command for admins to get list of all registered users
@Client.on_message(filters.private & filters.command(['users']))
async def users_command(client, message):
    user_id = message.from_user.id
    logger.info(f"Users command from admin {user_id}")

    if not Config.is_sudo_user(user_id):
        return await message.reply_text("❌ You don't have permission to use this command!")

    try:
        # Get all users from database
        all_users = await db.get_all_users()

        if not all_users:
            return await message.reply_text("📋 No registered users found.")

        users_text = f"<b>👥 All Registered Users</b>\n\n"
        users_text += f"<b>Total Users:</b> {len(all_users)}\n\n"

        premium_count = 0
        free_count = 0

        for i, user_info in enumerate(all_users[:50], 1):  # Show first 50 users
            user_id_info = user_info.get('id', 'Unknown')
            user_name = user_info.get('name', 'Unknown')
            joined_date = user_info.get('joined_date', 'Unknown')

            # Check if user has premium
            premium_info = await db.get_premium_user_details(user_id_info)
            if premium_info:
                status = f"💎 {premium_info.get('plan_type', 'premium').upper()}"
                premium_count += 1
            else:
                status = "🆓 FREE"
                free_count += 1

            # Format join date
            if isinstance(joined_date, datetime):
                join_str = joined_date.strftime('%Y-%m-%d')
            else:
                join_str = str(joined_date)[:10] if joined_date != 'Unknown' else 'Unknown'

            users_text += f"<b>{i}.</b> {user_name}\n"
            users_text += f"    ID: <code>{user_id_info}</code>\n"
            users_text += f"    Status: {status}\n"
            users_text += f"    Joined: {join_str}\n\n"

        if len(all_users) > 50:
            users_text += f"<i>... and {len(all_users) - 50} more users</i>\n\n"

        users_text += f"<b>📊 Summary:</b>\n"
        users_text += f"• Premium Users: {premium_count}\n"
        users_text += f"• Free Users: {free_count}\n"
        users_text += f"• Total: {len(all_users)} users"

        # Send with admin buttons
        buttons = [
            [InlineKeyboardButton('refresh', callback_data='admin_refresh_users')],
            [InlineKeyboardButton('💎 Premium Users', callback_data='admin_premium_users')],
            [InlineKeyboardButton('🔙 Admin Menu', callback_data='admin_commands')]
        ]

        await message.reply_text(
            text=users_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )

    except Exception as e:
        logger.error(f"Error in users command for admin {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ An error occurred while fetching users list. Please try again.")


#===================Event Management Command===================#

@Client.on_message(filters.private & filters.command(['event']))
async def event_command(client, message):
    """Event management command for pseudo-users (admins)"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    logger.info(f"Event command from user {user_id} ({user_name})")

    # Check if user is pseudo-user (admin/owner)
    if not Config.is_sudo_user(user_id):
        await message.reply_text(
            "❌ <b>Access Denied</b>\n\n"
            "This command is only available for administrators.\n"
            "If you're looking for events, use /start and go to FTM Manager → FTM Event.",
            parse_mode=enums.ParseMode.HTML
        )
        return

    try:
        # Check force subscribe even for admins
        if not Config.is_sudo_user(user_id):
            subscription_status = await db.check_force_subscribe(user_id, client)
            if not subscription_status['all_subscribed']:
                force_sub_text = (
                    "🔒 <b>Subscribe Required!</b>\n\n"
                    "To use this bot, you must join our official channels:\n\n"
                    f"• Support Group\n"
                    f"• Update Channel\n\n"
                    "Click the buttons below to join and then check your subscription."
                )
                await message.reply_text(
                    text=force_sub_text,
                    reply_markup=InlineKeyboardMarkup(force_sub_buttons),
                    parse_mode=enums.ParseMode.HTML
                )
                return

        # Event management main menu
        buttons = [
            [InlineKeyboardButton('🎉 Create New Event', callback_data='event_create#main')],
            [InlineKeyboardButton('📊 Manage Events', callback_data='event_manage#main')],
            [InlineKeyboardButton('📈 Event Statistics', callback_data='event_stats#main')],
            [InlineKeyboardButton('🔙 Close', callback_data='delete_message')]
        ]

        await message.reply_text(
            text="<b>🎭 Event Management Panel</b>\n\n"
                 "<b>Welcome to the Event Management System!</b>\n\n"
                 "Here you can:\n"
                 "• Create new events with custom rewards\n"
                 "• Manage existing events (start/stop/edit)\n"
                 "• View event statistics and redemptions\n"
                 "• Monitor user participation\n\n"
                 "<i>Select an option below to get started:</i>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Error in event command for user {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ An error occurred while loading event management. Please try again.")


#===================Updates Command===================#

@Client.on_message(filters.private & filters.command(['updates']))
async def updates_command(client, message):
    """Updates command to show bot updates and changelog"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    logger.info(f"Updates command from user {user_id} ({user_name})")
    
    try:
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
                return await message.reply_text(
                    text=force_sub_text,
                    reply_markup=InlineKeyboardMarkup(force_sub_buttons),
                    parse_mode=enums.ParseMode.HTML,
                    quote=True
                )
        
        # Show updates menu directly
        updates_menu_text = """<b>📄 Developer Updates</b>

<b>Stay informed about latest changes and upcoming features!</b>

<b>📋 Available Options:</b>
• <b>This Update</b> - View current update changes
• <b>Upcoming Update</b> - Preview future features

<i>Select an option to continue:</i>"""

        buttons = [
            [InlineKeyboardButton('📊 This Update', callback_data='this_update')],
            [InlineKeyboardButton('🚀 Upcoming Update', callback_data='upcoming_update')],
            [InlineKeyboardButton('🔙 Back to Menu', callback_data='back')]
        ]

        await message.reply_text(
            text=updates_menu_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
        
        logger.info(f"Updates menu sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error in updates command for user {user_id}: {e}", exc_info=True)
        await message.reply_text(
            "❌ An error occurred while loading updates. Please try again.",
            quote=True
        )


#===================Debug Message Handler===================#

@Client.on_message(filters.private & ~filters.command(["start", "help", "test", "ping", "info", "users", "speedtest", "speed", "system", "sys", "sysinfo", "event", "updates", "myid", "userid", "restart", "r", "redeem"]))
async def debug_message_handler(client, message):
    """Debug handler for non-command messages"""
    user_id = message.from_user.id
    logger.info(f"Non-command message from user {user_id}: {message.text[:50] if message.text else 'Non-text message'}")
    
    try:
        await message.reply_text(
            "ℹ️ <b>Bot Commands</b>\n\n"
            "Available commands:\n"
            "• /start - Start the bot\n"
            "• /test or /ping - Test if bot is working\n"
            "• /help - Get help\n"
            "• /info - Your account info\n\n"
            "Or use /start to access the main menu.",
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
    except Exception as e:
        logger.error(f"Error in debug message handler: {e}")

#===================Debug Commands===================#

@Client.on_message(filters.private & filters.command(['myid', 'userid']))
async def my_id_command(client, message):
    """Command to show user their Telegram ID for debugging permissions"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    username = message.from_user.username or "No username"
    
    # Check if user is already an admin
    is_owner = user_id in Config.OWNER_ID
    is_admin = user_id in Config.ADMIN_ID
    is_sudo = Config.is_sudo_user(user_id)
    
    status = "👤 Regular User"
    if is_owner:
        status = "👑 Owner"
    elif is_admin:
        status = "🛡️ Admin"
    elif is_sudo:
        status = "⚡ Sudo User"
    
    info_text = f"""<b>🆔 Your Telegram Information</b>

<b>👤 Basic Info:</b>
• <b>Name:</b> {user_name}
• <b>Username:</b> @{username}
• <b>User ID:</b> <code>{user_id}</code>
• <b>Status:</b> {status}

<b>🔐 Permission Status:</b>
• <b>Owner Access:</b> {"✅ Yes" if is_owner else "❌ No"}
• <b>Admin Access:</b> {"✅ Yes" if is_admin else "❌ No"}
• <b>Sudo Access:</b> {"✅ Yes" if is_sudo else "❌ No"}

<b>📋 Current Configuration:</b>
• <b>Configured Owners:</b> {Config.OWNER_ID}
• <b>Configured Admins:</b> {Config.ADMIN_ID}

<i>If you should have admin access but don't, share your User ID with the developer to update the configuration.</i>"""

    await message.reply_text(
        text=info_text,
        parse_mode=enums.ParseMode.HTML,
        quote=True
    )
    
    logger.info(f"User ID info sent to {user_id} ({user_name}) - Status: {status}")


@Client.on_callback_query(filters.regex(r'^delete_message$'))
async def delete_message_callback(bot, query):
    """Delete the message"""
    try:
        await query.message.delete()
    except:
        await query.answer("Message deleted!", show_alert=False)


#===================Redeem Command===================#

@Client.on_message(filters.private & filters.command(['redeem']))
async def redeem_command(client, message):
    """Redeem command for users to redeem event codes"""
    user = message.from_user
    user_id = user.id
    logger.info(f"Redeem command from user {user_id} ({user.first_name})")
    
    try:
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
                return await message.reply_text(
                    text=force_sub_text,
                    reply_markup=InlineKeyboardMarkup(force_sub_buttons),
                    parse_mode=enums.ParseMode.HTML,
                    quote=True
                )
        
        # Check if command has a code argument
        command_parts = message.text.split()
        if len(command_parts) < 2:
            # No code provided, show usage instructions
            redeem_text = """<b>🎁 Redeem Event Code</b>

<b>How to redeem:</b>
• Type: <code>/redeem YOUR_CODE</code>
• Example: <code>/redeem ABC123</code>

<b>📋 Available Events:</b>
• Check FTM Manager → FTM Event for active events
• Codes are case-sensitive
• Each code can only be used once per user

<b>🎯 Rewards vary by your current plan:</b>
• <b>Free users:</b> Get Plus subscription
• <b>Plus users:</b> Get Pro subscription upgrade  
• <b>Pro users:</b> Get subscription extension

<i>Enter your redeem code using the format above!</i>"""
            
            buttons = [
                [InlineKeyboardButton('🎪 View Events', callback_data='settings#ftm_event')],
                [InlineKeyboardButton('🔙 Back to Menu', callback_data='back')]
            ]
            
            return await message.reply_text(
                text=redeem_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
        
        # Get the redeem code from command
        redeem_code = command_parts[1].upper().strip()
        
        if len(redeem_code) != 6:
            return await message.reply_text(
                "❌ <b>Invalid code format!</b>\n\n"
                "Redeem codes must be exactly 6 characters long.\n"
                "Example: <code>/redeem ABC123</code>",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
        
        # Show processing message
        processing_msg = await message.reply_text(
            "🔄 <b>Processing redeem code...</b>\n⏳ Please wait...",
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
        
        # Get user's current plan
        premium_info = await db.get_premium_user_details(user_id)
        if premium_info:
            user_plan = premium_info.get('plan_type', 'free')
        else:
            user_plan = 'free'
        
        # Validate and redeem the code
        code_doc, error_msg = await db.validate_redeem_code(redeem_code, user_plan)
        
        if not code_doc:
            await processing_msg.edit_text(
                f"❌ <b>Redemption Failed</b>\n\n{error_msg}",
                parse_mode=enums.ParseMode.HTML
            )
            return
        
        # Attempt to redeem the code
        success, redeem_msg = await db.redeem_event_code(user_id, redeem_code, user_plan)
        
        if success:
            # Get event details
            event = await db.get_event_by_id(code_doc['event_id'])
            event_name = event.get('event_name', 'Unknown Event') if event else 'Unknown Event'
            
            success_text = f"""✅ <b>Code Redeemed Successfully!</b>

<b>🎉 Event:</b> {event_name}
<b>🎁 Reward:</b> {redeem_msg}
<b>📅 Redeemed:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<b>🎯 Your Benefits:</b>
• Premium features activated
• Extended subscription period
• Priority support access

<i>Thank you for participating in our event! 🎊</i>"""
            
            buttons = [
                [InlineKeyboardButton('💎 My Plan', callback_data='my_plan')],
                [InlineKeyboardButton('📊 Account Info', callback_data='info_callback')]
            ]
            
            await processing_msg.edit_text(
                text=success_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
            
            # Notify admin about redemption
            try:
                notify = NotificationManager(client)
                await notify.notify_user_action(
                    user_id, 
                    "Code Redemption", 
                    f"User: {user.first_name} | Code: {redeem_code} | Event: {event_name}"
                )
            except Exception as notify_err:
                logger.error(f"Notification error: {notify_err}")
                
            logger.info(f"Code {redeem_code} redeemed by user {user_id} for event {event_name}")
            
        else:
            await processing_msg.edit_text(
                f"❌ <b>Redemption Failed</b>\n\n{redeem_msg}",
                parse_mode=enums.ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Error in redeem command for user {user_id}: {e}", exc_info=True)
        await message.reply_text(
            "❌ An error occurred while processing your redeem code. Please try again.",
            quote=True
        )
