
import asyncio
import logging
from datetime import datetime, timedelta
from bson import ObjectId
from database import db
from config import Config
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# Event creation callback handlers
@Client.on_callback_query(filters.regex(r'^event_create#'))
async def event_create_callbacks(bot, query):
    """Handle event creation callbacks"""
    user_id = query.from_user.id
    callback_data = query.data
    
    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission to create events!", show_alert=True)
    
    try:
        if callback_data == "event_create#main":
            # Start event creation process
            await query.message.edit_text(
                text="<b>🎉 Create New Event</b>\n\n"
                     "<b>Step 1: Event Name</b>\n\n"
                     "Enter a name for your event:\n"
                     "<i>Type your event name and send it as a message</i>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('❌ Cancel', callback_data='event_manage#main')]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
            
            # Set user state for event creation
            await db.set_user_state(user_id, {
                'action': 'event_create_name',
                'step': 'waiting_name'
            })
            
        elif callback_data == "event_create#duration":
            # Handle duration selection
            user_state = await db.get_user_state(user_id)
            if not user_state or 'event_data' not in user_state:
                await query.answer("❌ Event creation session expired. Please start again.", show_alert=True)
                return
                
            await query.message.edit_text(
                text=f"<b>🎉 Create Event: {user_state['event_data']['name']}</b>\n\n"
                     "<b>Step 2: Event Duration</b>\n\n"
                     "Choose event duration or enter custom days:\n"
                     "<i>Select a preset or type number of days</i>",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton('⏰ 7 Days', callback_data='event_duration#7'),
                        InlineKeyboardButton('📅 15 Days', callback_data='event_duration#15')
                    ],
                    [
                        InlineKeyboardButton('🗓️ 30 Days', callback_data='event_duration#30'),
                        InlineKeyboardButton('♾️ Unlimited', callback_data='event_duration#unlimited')
                    ],
                    [InlineKeyboardButton('❌ Cancel', callback_data='event_manage#main')]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
            
        elif callback_data == "event_create#type":
            # Handle event type selection
            user_state = await db.get_user_state(user_id)
            if not user_state or 'event_data' not in user_state:
                await query.answer("❌ Event creation session expired. Please start again.", show_alert=True)
                return
            
            event_data = user_state['event_data']
            duration_text = f"{event_data['duration_days']} days" if event_data.get('duration_days') else "Unlimited"
            
            await query.message.edit_text(
                text=f"<b>🎉 Create Event: {event_data['name']}</b>\n\n"
                     f"<b>Duration:</b> {duration_text}\n\n"
                     "<b>Step 3: Event Type</b>\n\n"
                     "Choose the type of event:\n\n"
                     "<b>🎁 Discount Event:</b> Free subscription rewards for all users\n"
                     "<b>🎫 Redeem Code Event:</b> Generate codes for users to redeem",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('🎁 Discount Event', callback_data='event_type#discount')],
                    [InlineKeyboardButton('🎫 Redeem Code Event', callback_data='event_type#redeem')],
                    [InlineKeyboardButton('❌ Cancel', callback_data='event_manage#main')]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Error in event creation callback: {e}", exc_info=True)
        await query.answer("❌ An error occurred. Please try again.", show_alert=True)

@Client.on_callback_query(filters.regex(r'^event_duration#'))
async def event_duration_callback(bot, query):
    """Handle event duration selection"""
    user_id = query.from_user.id
    duration_value = query.data.split('#')[1]
    
    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission!", show_alert=True)
    
    try:
        user_state = await db.get_user_state(user_id)
        if not user_state or 'event_data' not in user_state:
            await query.answer("❌ Event creation session expired. Please start again.", show_alert=True)
            return
        
        event_data = user_state['event_data']
        
        if duration_value == "unlimited":
            event_data['duration_days'] = None
        else:
            event_data['duration_days'] = int(duration_value)
        
        # Update state and proceed to type selection
        await db.set_user_state(user_id, {
            'action': 'event_create_type',
            'step': 'selecting_type',
            'event_data': event_data
        })
        
        await event_create_callbacks(bot, type('obj', (object,), {
            'data': 'event_create#type',
            'from_user': query.from_user,
            'message': query.message,
            'answer': query.answer
        })())
        
    except Exception as e:
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^event_type#'))
async def event_type_callback(bot, query):
    """Handle event type selection"""
    user_id = query.from_user.id
    event_type = query.data.split('#')[1]
    
    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission!", show_alert=True)
    
    try:
        user_state = await db.get_user_state(user_id)
        if not user_state or 'event_data' not in user_state:
            await query.answer("❌ Event creation session expired. Please start again.", show_alert=True)
            return
        
        event_data = user_state['event_data']
        event_data['event_type'] = event_type
        
        duration_text = f"{event_data['duration_days']} days" if event_data.get('duration_days') else "Unlimited"
        
        if event_type == "discount":
            # For discount events, proceed to final creation
            await query.message.edit_text(
                text=f"<b>🎉 Create Event: {event_data['name']}</b>\n\n"
                     f"<b>Duration:</b> {duration_text}\n"
                     f"<b>Type:</b> Discount Event\n\n"
                     "<b>Step 4: Confirm Creation</b>\n\n"
                     "<b>Discount Event Details:</b>\n"
                     "• Free subscription rewards for all user groups\n"
                     "• Free → 10 days Plus plan\n"
                     "• Plus → 10 days Pro plan\n"
                     "• Pro → 10 days Pro plan extension\n\n"
                     "<b>Ready to create this event?</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('✅ Create Event', callback_data='event_confirm#discount')],
                    [InlineKeyboardButton('❌ Cancel', callback_data='event_manage#main')]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
            
        elif event_type == "redeem":
            # For redeem code events, get code configuration
            await query.message.edit_text(
                text=f"<b>🎉 Create Event: {event_data['name']}</b>\n\n"
                     f"<b>Duration:</b> {duration_text}\n"
                     f"<b>Type:</b> Redeem Code Event\n\n"
                     "<b>Step 4: Code Configuration</b>\n\n"
                     "Configure redeem codes:\n"
                     "Enter reward days for each user group separated by commas\n"
                     "<b>Format:</b> free_days,plus_days,pro_days\n"
                     "<b>Example:</b> 15,20,25\n\n"
                     "<i>Type the configuration and send as message:</i>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('❌ Cancel', callback_data='event_manage#main')]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
            
            # Update state for code configuration
            await db.set_user_state(user_id, {
                'action': 'event_create_codes',
                'step': 'waiting_code_config',
                'event_data': event_data
            })
        
    except Exception as e:
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^event_confirm#'))
async def event_confirm_callback(bot, query):
    """Handle event creation confirmation"""
    user_id = query.from_user.id
    confirm_type = query.data.split('#')[1]
    
    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission!", show_alert=True)
    
    try:
        user_state = await db.get_user_state(user_id)
        if not user_state or 'event_data' not in user_state:
            await query.answer("❌ Event creation session expired. Please start again.", show_alert=True)
            return
        
        event_data = user_state['event_data']
        
        if confirm_type == "discount":
            # Create discount event
            reward_config = {
                'free': {'plan': 'plus', 'duration': 10},
                'plus': {'plan': 'pro', 'duration': 10},
                'pro': {'plan': 'pro', 'duration': 10}
            }
            
            event_id = await db.create_event(
                event_name=event_data['name'],
                creator_id=user_id,
                duration_days=event_data.get('duration_days'),
                event_type="discount",
                reward_config=reward_config,
                start_date=datetime.utcnow()
            )
            
            # Get created event and activate it
            created_event = await db.get_event_by_name(event_data['name'])
            if created_event:
                await db.update_event_status(created_event['event_id'], 'active')
                
                # Send admin notification
                admin_name = query.from_user.first_name
                try:
                    from utils.notifications import NotificationManager
                    notify = NotificationManager(bot)
                    await notify.notify_admin_action(
                        user_id, 
                        "Event Created", 
                        f"Discount Event: {event_data['name']}", 
                        f"Creator: {admin_name}, Duration: {event_data.get('duration_days', 'Unlimited')} days"
                    )
                except Exception as notify_err:
                    logger.error(f"Failed to send event creation notification: {notify_err}")
                
                await query.message.edit_text(
                    text=f"<b>✅ Event Created Successfully!</b>\n\n"
                         f"<b>Event Name:</b> {event_data['name']}\n"
                         f"<b>Event ID:</b> <code>{created_event['event_id']}</code>\n"
                         f"<b>Type:</b> Discount Event\n"
                         f"<b>Status:</b> Active\n"
                         f"<b>Duration:</b> {event_data.get('duration_days', 'Unlimited')} days\n\n"
                         "<b>🎉 Users can now participate in this event!</b>\n"
                         "<b>They will receive free subscription rewards when they redeem.</b>",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton('📊 Event Stats', callback_data=f'event_stats#{created_event["event_id"]}')],
                        [InlineKeyboardButton('🔙 Event Manager', callback_data='event_manage#main')]
                    ]),
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                await query.answer("❌ Event created but activation failed!", show_alert=True)
        
        # Clear user state
        await db.clear_user_state(user_id)
        
    except Exception as e:
        logger.error(f"Error confirming event creation: {e}", exc_info=True)
        await query.answer(f"❌ Error creating event: {str(e)}", show_alert=True)
        await db.clear_user_state(user_id)

# Event management callbacks
@Client.on_callback_query(filters.regex(r'^event_manage#'))
async def event_manage_callbacks(bot, query):
    """Handle event management callbacks"""
    user_id = query.from_user.id
    callback_data = query.data
    
    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission!", show_alert=True)
    
    try:
        if callback_data == "event_manage#main":
            # Show event management main menu
            events = await db.get_all_events()
            active_events = [e for e in events if e.get('status') == 'active']
            
            manage_text = "<b>📊 Event Management</b>\n\n"
            manage_text += f"<b>Total Events:</b> {len(events)}\n"
            manage_text += f"<b>Active Events:</b> {len(active_events)}\n\n"
            
            if active_events:
                manage_text += "<b>🎉 Currently Active:</b>\n"
                for event in active_events[:3]:
                    manage_text += f"• {event['event_name']} ({event.get('event_type', 'unknown')})\n"
                if len(active_events) > 3:
                    manage_text += f"• ... and {len(active_events) - 3} more\n"
            else:
                manage_text += "<b>📭 No active events</b>\n"
            
            manage_text += "\n<b>Choose a management option:</b>"
            
            buttons = [
                [InlineKeyboardButton('🎉 Create New Event', callback_data='event_create#main')],
                [InlineKeyboardButton('📋 List All Events', callback_data='event_list#all')],
                [InlineKeyboardButton('🎯 Active Events', callback_data='event_list#active')],
                [InlineKeyboardButton('📈 Event Statistics', callback_data='event_stats#overview')],
                [InlineKeyboardButton('🔙 Close', callback_data='delete_message')]
            ]
            
            await query.message.edit_text(
                text=manage_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
            
    except Exception as e:
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^event_list#'))
async def event_list_callback(bot, query):
    """Handle event listing callbacks"""
    user_id = query.from_user.id
    list_type = query.data.split('#')[1]
    
    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission!", show_alert=True)
    
    try:
        if list_type == "all":
            events = await db.get_all_events()
            title = "📋 All Events"
        elif list_type == "active":
            events = await db.get_active_events()
            title = "🎯 Active Events"
        else:
            return await query.answer("❌ Invalid list type!", show_alert=True)
        
        if not events:
            await query.message.edit_text(
                text=f"<b>{title}</b>\n\n<b>No events found.</b>\n\nCreate your first event to get started!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('🎉 Create Event', callback_data='event_create#main')],
                    [InlineKeyboardButton('🔙 Back', callback_data='event_manage#main')]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
            return
        
        list_text = f"<b>{title}</b>\n\n"
        
        for i, event in enumerate(events[:10], 1):  # Show max 10 events
            event_name = event['event_name']
            event_type = event.get('event_type', 'unknown')
            status = event.get('status', 'unknown')
            created_date = event.get('created_at', 'Unknown').strftime('%Y-%m-%d') if event.get('created_at') else 'Unknown'
            
            list_text += f"<b>{i}. {event_name}</b>\n"
            list_text += f"   Type: {event_type}\n"
            list_text += f"   Status: {status}\n"
            list_text += f"   Created: {created_date}\n"
            list_text += f"   ID: <code>{event.get('event_id', 'Unknown')}</code>\n\n"
        
        if len(events) > 10:
            list_text += f"<i>... and {len(events) - 10} more events</i>"
        
        # Create buttons for individual event management
        buttons = []
        for event in events[:5]:  # Show buttons for first 5 events
            buttons.append([
                InlineKeyboardButton(
                    f"📊 {event['event_name'][:20]}...", 
                    callback_data=f"event_stats#{event.get('event_id', '')}"
                )
            ])
        
        buttons.append([InlineKeyboardButton('🔙 Back', callback_data='event_manage#main')])
        
        await query.message.edit_text(
            text=list_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
        
    except Exception as e:
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)

@Client.on_callback_query(filters.regex(r'^event_stats#'))
async def event_stats_callback(bot, query):
    """Handle event statistics callbacks"""
    user_id = query.from_user.id
    event_ref = query.data.split('#')[1]
    
    if not Config.is_sudo_user(user_id):
        return await query.answer("❌ You don't have permission!", show_alert=True)
    
    try:
        if event_ref == "overview":
            # Show overall statistics
            all_events = await db.get_all_events()
            active_events = await db.get_active_events()
            
            total_redemptions = 0
            for event in all_events:
                total_redemptions += event.get('total_redemptions', 0)
            
            stats_text = "<b>📈 Event Statistics Overview</b>\n\n"
            stats_text += f"<b>📊 Overall Stats:</b>\n"
            stats_text += f"• Total Events: {len(all_events)}\n"
            stats_text += f"• Active Events: {len(active_events)}\n"
            stats_text += f"• Total Redemptions: {total_redemptions}\n\n"
            
            if active_events:
                stats_text += "<b>🎯 Active Events Performance:</b>\n"
                for event in active_events[:5]:
                    redemptions = event.get('total_redemptions', 0)
                    stats_text += f"• {event['event_name']}: {redemptions} redemptions\n"
            
            await query.message.edit_text(
                text=stats_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton('📋 View All Events', callback_data='event_list#all')],
                    [InlineKeyboardButton('🔙 Back', callback_data='event_manage#main')]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
        else:
            # Show specific event statistics
            event_stats = await db.get_event_stats(event_ref)
            
            if not event_stats:
                await query.answer("❌ Event not found!", show_alert=True)
                return
            
            event = event_stats['event']
            redemptions_by_plan = event_stats['redemptions_by_plan']
            total_redemptions = event_stats['total_redemptions']
            
            stats_text = f"<b>📊 Event Statistics</b>\n\n"
            stats_text += f"<b>Event:</b> {event['event_name']}\n"
            stats_text += f"<b>Type:</b> {event.get('event_type', 'Unknown')}\n"
            stats_text += f"<b>Status:</b> {event.get('status', 'Unknown')}\n"
            stats_text += f"<b>Total Redemptions:</b> {total_redemptions}\n\n"
            
            if redemptions_by_plan:
                stats_text += "<b>📋 Redemptions by Plan:</b>\n"
                for plan, count in redemptions_by_plan.items():
                    stats_text += f"• {plan.upper()}: {count} redemptions\n"
            else:
                stats_text += "<b>📭 No redemptions yet</b>\n"
            
            # Event management buttons
            buttons = []
            if event.get('status') == 'active':
                buttons.append([InlineKeyboardButton('🛑 Stop Event', callback_data=f'event_stop#{event_ref}')])
            elif event.get('status') in ['draft', 'scheduled']:
                buttons.append([InlineKeyboardButton('▶️ Start Event', callback_data=f'event_start#{event_ref}')])
            
            buttons.extend([
                [InlineKeyboardButton('📋 View Redemptions', callback_data=f'event_redemptions#{event_ref}')],
                [InlineKeyboardButton('🔙 Back', callback_data='event_manage#main')]
            ])
            
            await query.message.edit_text(
                text=stats_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
            
    except Exception as e:
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)

# Message handler for event creation steps
@Client.on_message(filters.private & ~filters.command(['start', 'help', 'settings', 'forward', 'fwd', 'event', 'redeem', 'updates', 'ftm', 'users', 'info', 'speedtest', 'system', 'verify', 'chat', 'contact', 'endchat', 'add_premium', 'remove_premium', 'pusers', 'plan', 'myplan', 'chatuser']))
async def handle_event_creation_messages(client, message):
    """Handle messages during event creation process"""
    user_id = message.from_user.id
    
    # Only handle for sudo users in event creation state
    if not Config.is_sudo_user(user_id):
        return
    
    try:
        user_state = await db.get_user_state(user_id)
        if not user_state:
            return
        
        action = user_state.get('action')
        step = user_state.get('step')
        
        if action == 'event_create_name' and step == 'waiting_name':
            # Handle event name input
            event_name = message.text.strip()
            
            if len(event_name) < 3:
                return await message.reply_text("❌ Event name must be at least 3 characters long. Try again.")
            
            if len(event_name) > 50:
                return await message.reply_text("❌ Event name too long (max 50 characters). Try again.")
            
            # Check if event name already exists
            existing_event = await db.get_event_by_name(event_name)
            if existing_event:
                return await message.reply_text("❌ An event with this name already exists. Choose a different name.")
            
            # Store event data and proceed to duration
            event_data = {'name': event_name}
            await db.set_user_state(user_id, {
                'action': 'event_create_duration',
                'step': 'selecting_duration',
                'event_data': event_data
            })
            
            buttons = [
                [
                    InlineKeyboardButton('⏰ 7 Days', callback_data='event_duration#7'),
                    InlineKeyboardButton('📅 15 Days', callback_data='event_duration#15')
                ],
                [
                    InlineKeyboardButton('🗓️ 30 Days', callback_data='event_duration#30'),
                    InlineKeyboardButton('♾️ Unlimited', callback_data='event_duration#unlimited')
                ],
                [InlineKeyboardButton('❌ Cancel', callback_data='event_manage#main')]
            ]
            
            await message.reply_text(
                text=f"<b>🎉 Create Event: {event_name}</b>\n\n"
                     "<b>Step 2: Event Duration</b>\n\n"
                     "Choose event duration or type custom days:\n"
                     "<i>Select a preset or type number of days</i>",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
            
        elif action == 'event_create_codes' and step == 'waiting_code_config':
            # Handle redeem code configuration
            try:
                config_parts = message.text.strip().split(',')
                if len(config_parts) != 3:
                    return await message.reply_text(
                        "❌ Invalid format! Please use: free_days,plus_days,pro_days\n"
                        "Example: 15,20,25"
                    )
                
                free_days, plus_days, pro_days = map(int, config_parts)
                
                if any(days <= 0 or days > 365 for days in [free_days, plus_days, pro_days]):
                    return await message.reply_text("❌ Days must be between 1 and 365. Try again.")
                
                # Get event data and create redeem code event
                event_data = user_state['event_data']
                
                event_id = await db.create_event(
                    event_name=event_data['name'],
                    creator_id=user_id,
                    duration_days=event_data.get('duration_days'),
                    event_type="redeem_code",
                    start_date=datetime.utcnow()
                )
                
                # Generate redeem codes
                durations_config = {
                    'free': free_days,
                    'plus': plus_days,
                    'pro': pro_days
                }
                
                # Get created event and generate codes
                created_event = await db.get_event_by_name(event_data['name'])
                if created_event:
                    await db.generate_redeem_codes(
                        created_event['event_id'], 
                        durations_config, 
                        codes_per_group=50  # Generate 50 codes per group
                    )
                    
                    await db.update_event_status(created_event['event_id'], 'active')
                    
                    # Send admin notification
                    admin_name = message.from_user.first_name
                    try:
                        from utils.notifications import NotificationManager
                        notify = NotificationManager(client)
                        await notify.notify_admin_action(
                            user_id, 
                            "Redeem Code Event Created", 
                            f"Event: {event_data['name']}", 
                            f"Creator: {admin_name}, Codes: 150 total (50 per group)"
                        )
                    except Exception as notify_err:
                        logger.error(f"Failed to send event creation notification: {notify_err}")
                    
                    await message.reply_text(
                        text=f"<b>✅ Redeem Code Event Created!</b>\n\n"
                             f"<b>Event Name:</b> {event_data['name']}\n"
                             f"<b>Event ID:</b> <code>{created_event['event_id']}</code>\n"
                             f"<b>Type:</b> Redeem Code Event\n"
                             f"<b>Status:</b> Active\n\n"
                             f"<b>🎫 Generated Codes:</b>\n"
                             f"• Free Users: 50 codes ({free_days} days each)\n"
                             f"• Plus Users: 50 codes ({plus_days} days each)\n"
                             f"• Pro Users: 50 codes ({pro_days} days each)\n\n"
                             "<b>Users can now redeem codes using /redeem command!</b>",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton('📊 Event Stats', callback_data=f'event_stats#{created_event["event_id"]}')],
                            [InlineKeyboardButton('🔙 Event Manager', callback_data='event_manage#main')]
                        ]),
                        parse_mode=enums.ParseMode.HTML
                    )
                else:
                    await message.reply_text("❌ Event created but activation failed!")
                
                # Clear user state
                await db.clear_user_state(user_id)
                
            except ValueError:
                await message.reply_text("❌ Invalid numbers! Please enter valid day amounts. Try again.")
            except Exception as e:
                await message.reply_text(f"❌ Error creating event: {str(e)}")
                await db.clear_user_state(user_id)
        
    except Exception as e:
        logger.error(f"Error handling event creation message: {e}", exc_info=True)
        await db.clear_user_state(user_id)
