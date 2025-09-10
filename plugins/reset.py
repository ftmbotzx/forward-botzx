import logging
from database import db
from config import Config
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Setup logging
logger = logging.getLogger(__name__)

# Default configuration for reset
default_config = {
    'caption': None,
    'button': None,
    'duplicate': True,
    'db_uri': None,
    'forward_tag': False,
    'file_size': 0,
    'size_limit': None,
    'extension': None,
    'keywords': None,
    'ftm_mode': False,
    'protect': None,
    'filters': {
        'text': True,
        'photo': True,
        'video': True,
        'document': True,
        'audio': True,
        'voice': True,
        'animation': True,
        'sticker': True,
        'poll': True,
        'image_text': False
    },
}

@Client.on_message(filters.private & filters.command(['reset']))
async def reset_user_command(client, message):
    """Individual user reset command - available to all users"""
    user_id = message.from_user.id
    logger.info(f"Reset command triggered by user {user_id}")

    try:
        # Add user to database if not exists
        if not await db.is_user_exist(user_id):
            await db.add_user(user_id, message.from_user.first_name)

        # Skip force subscribe check for sudo users
        if Config.is_sudo_user(user_id):
            pass  # Skip force subscribe for admins/owners
        else:
            subscription_status = await db.check_force_subscribe(user_id, client)
            if not subscription_status['all_subscribed']:
                force_sub_text = (
                    "🔒 <b>Subscribe Required!</b>\n\n"
                    "To use this bot, you must join our official channels:\n\n"
                    "📜 <b>Support Group:</b> Get help and updates\n"
                    "🤖 <b>Update Channel:</b> Latest features and announcements\n\n"
                    "After joining both channels, click '✅ Check Subscription' to continue."
                )
                force_sub_buttons = [[
                    InlineKeyboardButton('📜 Join Support Group', url=Config.SUPPORT_GROUP),
                    InlineKeyboardButton('🤖 Join Update Channel', url=Config.UPDATE_CHANNEL)
                ],[
                    InlineKeyboardButton('✅ Check Subscription', callback_data='check_subscription')
                ]]
                return await message.reply_text(
                    text=force_sub_text,
                    reply_markup=InlineKeyboardMarkup(force_sub_buttons),
                    quote=True
                )

        # Show confirmation dialog
        confirmation_text = (
            "<b>⚠️ RESET CONFIRMATION ⚠️</b>\n\n"
            "<b>Are you sure you want to reset all your data?</b>\n\n"
            "<b>This will permanently delete:</b>\n"
            "• All your bot configurations\n"
            "• All your custom settings\n"
            "• All your channel settings\n"
            "• All your filter preferences\n"
            "• All your bot connections\n"
            "• All your forwarding preferences\n\n"
            "<b>❗ This action cannot be undone!</b>\n\n"
            "<b>Choose an option below:</b>"
        )

        confirmation_buttons = [
            [
                InlineKeyboardButton('✅ Yes, Reset Everything', callback_data=f'confirm_reset_{user_id}'),
                InlineKeyboardButton('❌ Cancel', callback_data='cancel_reset')
            ]
        ]

        await message.reply_text(
            text=confirmation_text,
            reply_markup=InlineKeyboardMarkup(confirmation_buttons),
            quote=True
        )

    except Exception as e:
        logger.error(f"Error in reset command for user {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ An error occurred. Please try again.")

@Client.on_callback_query(filters.regex(r'^confirm_reset_(\d+)$'))
async def confirm_reset_callback(client, callback_query):
    """Handle reset confirmation"""
    user_id = int(callback_query.matches[0].group(1))
    requesting_user = callback_query.from_user.id

    # Make sure only the requesting user can confirm their own reset
    if user_id != requesting_user:
        return await callback_query.answer("❌ You can only reset your own data!", show_alert=True)

    try:
        # Update message to show processing
        await callback_query.message.edit_text("🔄 <b>Resetting your data...</b>\n\n<i>Please wait...</i>")

        # Reset user configurations to default
        await db.update_configs(user_id, default_config)

        # Remove user's bot connections
        await db.remove_bot(user_id)

        # Get and remove user's channels
        user_channels = await db.get_user_channels(user_id)
        channels_removed = 0
        for channel in user_channels:
            try:
                await db.remove_channel(user_id, channel['chat_id'])
                channels_removed += 1
            except Exception as e:
                logger.error(f"Error removing channel {channel['chat_id']} for user {user_id}: {e}")

        # Remove from forwarding notifications
        await db.rmve_frwd(user_id)

        # Success message
        success_text = (
            "<b>✅ RESET COMPLETED SUCCESSFULLY!</b>\n\n"
            "<b>🔄 Your data has been reset to default settings.</b>\n\n"
            "<b>📊 Reset Summary:</b>\n"
            f"• <b>Configurations:</b> Reset to default\n"
            f"• <b>Bot Connections:</b> Removed\n"
            f"• <b>Channels:</b> {channels_removed} removed\n"
            f"• <b>Forwarding Status:</b> Cleared\n\n"
            "<b>🎯 You can now:</b>\n"
            "• Use /start to begin fresh\n"
            "• Configure new settings via /settings\n"
            "• Add new bots and channels\n\n"
            "<b>Thank you for using our bot! 🚀</b>"
        )

        await callback_query.message.edit_text(success_text)

        logger.info(f"User {user_id} successfully reset their data")

    except Exception as e:
        logger.error(f"Error in reset confirmation for user {user_id}: {e}", exc_info=True)
        await callback_query.message.edit_text(
            "<b>❌ RESET FAILED</b>\n\n"
            "<b>An error occurred while resetting your data.</b>\n"
            "Please try again or contact support."
        )

@Client.on_callback_query(filters.regex(r'^cancel_reset$'))
async def cancel_reset_callback(client, callback_query):
    """Handle reset cancellation"""
    await callback_query.message.edit_text(
        "<b>❌ RESET CANCELLED</b>\n\n"
        "<b>Your data remains unchanged.</b>\n\n"
        "Use /start to return to the main menu."
    )

@Client.on_message(filters.private & filters.command(['allreset']))
async def reset_all_users_command(client, message):
    """Mass reset command - only for sudo users (admin + owner)"""
    user_id = message.from_user.id

    # Check if user is sudo (admin or owner)
    if not Config.is_sudo_user(user_id):
        return await message.reply_text("❌ Only sudo users (admin + owner) can use this command!")

    logger.info(f"All reset command triggered by sudo user {user_id}")

    try:
        # Double confirmation for mass reset
        confirmation_text = (
            "<b>⚠️ MASS RESET CONFIRMATION ⚠️</b>\n\n"
            "<b>🚨 DANGER: You are about to reset ALL USERS' data!</b>\n\n"
            "<b>This will permanently delete for ALL USERS:</b>\n"
            "• All configurations and settings\n"
            "• All bot connections\n"
            "• All channel settings\n"
            "• All filter preferences\n"
            "• All forwarding preferences\n"
            "• All custom data\n\n"
            "<b>❗ THIS ACTION CANNOT BE UNDONE!</b>\n"
            "<b>❗ THIS WILL AFFECT ALL USERS!</b>\n\n"
            "<b>Are you absolutely sure?</b>"
        )

        confirmation_buttons = [
            [
                InlineKeyboardButton('🚨 YES, RESET ALL USERS', callback_data=f'confirm_allreset_{user_id}'),
                InlineKeyboardButton('❌ Cancel', callback_data='cancel_allreset')
            ]
        ]

        await message.reply_text(
            text=confirmation_text,
            reply_markup=InlineKeyboardMarkup(confirmation_buttons),
            quote=True
        )

    except Exception as e:
        logger.error(f"Error in resetall command for owner {user_id}: {e}", exc_info=True)
        await message.reply_text("❌ An error occurred. Please try again.")

@Client.on_callback_query(filters.regex(r'^confirm_allreset_(\d+)$'))
async def confirm_allreset_callback(client, callback_query):
    """Handle mass reset confirmation"""
    sudo_user_id = int(callback_query.matches[0].group(1))
    requesting_user = callback_query.from_user.id

    # Double check permissions
    if not Config.is_sudo_user(requesting_user) or requesting_user != sudo_user_id:
        return await callback_query.answer("❌ Only sudo users can perform mass reset!", show_alert=True)

    try:
        # Update message to show processing
        await callback_query.message.edit_text(
            "🔄 <b>MASS RESET IN PROGRESS...</b>\n\n"
            "<i>Processing all users... This may take a while.</i>\n\n"
            "<b>⚠️ DO NOT RESTART THE BOT!</b>"
        )

        # Get all users
        users = await db.get_all_users()

        # Initialize counters
        total = 0
        success = 0
        failed = 0
        bots_removed = 0
        channels_removed = 0

        # Process each user
        async for user in users:
            user_id = user['id']
            total += 1

            # Update progress every 10 users
            if total % 10 == 0:
                progress_text = (
                    f"🔄 <b>MASS RESET IN PROGRESS...</b>\n\n"
                    f"<b>Progress:</b> {total} users processed\n"
                    f"<b>Success:</b> {success}\n"
                    f"<b>Failed:</b> {failed}\n\n"
                    "<i>Please wait...</i>"
                )
                try:
                    await callback_query.message.edit_text(progress_text)
                except:
                    pass  # Ignore edit errors during rapid updates

            try:
                # Reset user configurations
                await db.update_configs(user_id, default_config)

                # Remove user's bot connections
                if await db.is_bot_exist(user_id):
                    await db.remove_bot(user_id)
                    bots_removed += 1

                # Remove user's channels
                user_channels = await db.get_user_channels(user_id)
                for channel in user_channels:
                    try:
                        await db.remove_channel(user_id, channel['chat_id'])
                        channels_removed += 1
                    except:
                        pass

                # Remove from forwarding notifications
                await db.rmve_frwd(user_id)

                success += 1

            except Exception as e:
                logger.error(f"Error resetting user {user_id}: {e}")
                failed += 1

        # Clear all forwarding notifications
        await db.rmve_frwd(all=True)

        # Final success message
        final_text = (
            "<b>✅ MASS RESET COMPLETED!</b>\n\n"
            "<b>📊 Final Statistics:</b>\n"
            f"• <b>Total Users:</b> {total}\n"
            f"• <b>Successfully Reset:</b> {success}\n"
            f"• <b>Failed:</b> {failed}\n"
            f"• <b>Bots Removed:</b> {bots_removed}\n"
            f"• <b>Channels Removed:</b> {channels_removed}\n\n"
            "<b>🔄 All user data has been reset to default settings.</b>\n\n"
            "<b>⚠️ Users will need to reconfigure their bots and settings.</b>\n\n"
            "<b>✅ Database cleanup completed successfully!</b>"
        )

        await callback_query.message.edit_text(final_text)

        logger.info(f"Mass reset completed by sudo user {sudo_user_id} - Total: {total}, Success: {success}, Failed: {failed}")

    except Exception as e:
        logger.error(f"Error in mass reset confirmation for sudo user {sudo_user_id}: {e}", exc_info=True)
        await callback_query.message.edit_text(
            "<b>❌ MASS RESET FAILED</b>\n\n"
            "<b>An error occurred during the mass reset process.</b>\n"
            "Some users may have been partially reset.\n\n"
            "Please check logs and try again if needed."
        )

@Client.on_callback_query(filters.regex(r'^cancel_allreset$'))
async def cancel_allreset_callback(client, callback_query):
    """Handle mass reset cancellation"""
    await callback_query.message.edit_text(
        "<b>❌ MASS RESET CANCELLED</b>\n\n"
        "<b>No user data was modified.</b>\n\n"
        "All user configurations remain unchanged."
    )
