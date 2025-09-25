
from os import environ 
from config import Config
import motor.motor_asyncio
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta

async def mongodb_version():
    x = MongoClient(Config.DATABASE_URI)
    mongodb_version = x.server_info()['version']
    return mongodb_version

class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.bot = self.db.bots
        self.col = self.db.users
        self.nfy = self.db.notify
        self.chl = self.db.channels
        self.queue_col = self.db.queue  # For crash recovery queue
        self.premium_col = self.db.premium_users  # Premium users collection
        self.payment_col = self.db.payment_verifications  # Payment verification collection
        self.usage_col = self.db.usage_tracking  # Monthly usage tracking
        self.admin_chat_col = self.db.admin_chats  # Admin chat sessions
        self.contact_requests_col = self.db.contact_requests  # Contact requests collection 
        self.chat_requests_col = self.db.chat_requests  # Chat requests collection
        self.events_col = self.db.events  # Events collection for FTM events system
        self.event_redemptions_col = self.db.event_redemptions  # Event redemptions tracking
        self.event_codes_col = self.db.event_codes  # Individual event codes with usage tracking 

    def new_user(self, id, name):
        from datetime import datetime
        return dict(
            id = id,
            name = name,
            joined_date = datetime.utcnow(),
            ban_status=dict(
                is_banned=False,
                ban_reason="",
            ),
        )

    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)

    async def total_users_bots_count(self):
        bcount = await self.bot.count_documents({})
        count = await self.col.count_documents({})
        return count, bcount

    async def total_channels(self):
        count = await self.chl.count_documents({})
        return count

    async def remove_ban(self, id):
        ban_status = dict(
            is_banned=False,
            ban_reason=''
        )
        await self.col.update_one({'id': id}, {'$set': {'ban_status': ban_status}})

    async def ban_user(self, user_id, ban_reason="No Reason"):
        ban_status = dict(
            is_banned=True,
            ban_reason=ban_reason
        )
        await self.col.update_one({'id': user_id}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = dict(
            is_banned=False,
            ban_reason=''
        )
        user = await self.col.find_one({'id':int(id)})
        if not user:
            return default
        return user.get('ban_status', default)

    async def get_all_users(self):
        return await self.col.find({}).to_list(length=1000)

    async def get_user(self, user_id):
        """Get user data by user ID"""
        return await self.col.find_one({'id': int(user_id)})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def get_banned(self):
        users = self.col.find({'ban_status.is_banned': True})
        b_users = [user['id'] async for user in users]
        return b_users

    async def update_configs(self, id, configs):
        await self.col.update_one({'id': int(id)}, {'$set': {'configs': configs}}, upsert=True)

    async def update_user_config(self, user_id, key, value):
        """Update a single configuration key for a user"""
        # Get current configs
        current_configs = await self.get_configs(user_id)
        
        # Handle nested keys like filters.text, filters.photo, etc.
        if '.' in key:
            keys = key.split('.')
            if keys[0] == 'filters' and keys[1] in current_configs.get('filters', {}):
                current_configs['filters'][keys[1]] = value
            else:
                # For other nested keys, update directly
                current_configs[key] = value
        else:
            # Update the specific key
            current_configs[key] = value
        
        # Save back to database
        await self.update_configs(user_id, current_configs)

    async def get_configs(self, id):
        default = {
            'caption': None,
            'button': None,
            'duplicate': True,
            'db_uri': None,
            'forward_tag': False,
            'file_size': 0,
            'size_limit': None,
            'extension': None,
            'keywords': None,
            'ftm_mode': False,  # Now called FTM Delta mode
            'ftm_alpha_mode': False,  # New FTM Alpha mode for real-time forwarding
            'alpha_source_chat': None,  # Source channel for Alpha mode
            'alpha_target_chat': None,  # Target channel for Alpha mode
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
        user = await self.col.find_one({'id':int(id)})
        if user:
            return user.get('configs', default)
        return default 

    async def add_bot(self, datas):
       if not await self.is_bot_exist(datas['user_id']):
          await self.bot.insert_one(datas)

    async def remove_bot(self, user_id):
       await self.bot.delete_many({'user_id': int(user_id)})

    async def get_bot(self, user_id: int):
       bot = await self.bot.find_one({'user_id': user_id})
       return bot if bot else None

    async def is_bot_exist(self, user_id):
       bot = await self.bot.find_one({'user_id': user_id})
       return bool(bot)

    async def in_channel(self, user_id: int, chat_id: int) -> bool:
       channel = await self.chl.find_one({"user_id": int(user_id), "chat_id": int(chat_id)})
       return bool(channel)

    async def add_channel(self, user_id: int, chat_id: int, title, username):
       channel = await self.in_channel(user_id, chat_id)
       if channel:
         return False
       return await self.chl.insert_one({"user_id": user_id, "chat_id": chat_id, "title": title, "username": username})

    async def remove_channel(self, user_id: int, chat_id: int):
       channel = await self.in_channel(user_id, chat_id )
       if not channel:
         return False
       return await self.chl.delete_many({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_channel_details(self, user_id: int, chat_id: int):
       return await self.chl.find_one({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_user_channels(self, user_id: int):
       channels = self.chl.find({"user_id": int(user_id)})
       return [channel async for channel in channels]

    async def get_filters(self, user_id):
       filters = []
       filter = (await self.get_configs(user_id))['filters']
       for k, v in filter.items():
          if v == False:
            filters.append(str(k))
       return filters

    async def add_frwd(self, user_id):
       return await self.nfy.insert_one({'user_id': int(user_id)})

    async def rmve_frwd(self, user_id=0, all=False):
       data = {} if all else {'user_id': int(user_id)}
       return await self.nfy.delete_many(data)

    async def get_all_frwd(self):
       return self.nfy.find({})

    # Queue management for crash recovery
    async def add_queue_item(self, user_id, process_data):
        """Add a forwarding process to the queue"""
        queue_item = {
            'user_id': user_id,
            'status': 'active',
            'created_at': datetime.utcnow(),
            'process_data': process_data
        }
        result = await self.queue_col.insert_one(queue_item)
        return result.inserted_id
    
    async def update_queue_status(self, user_id, status):
        """Update queue status (active, completed, cancelled)"""
        return await self.queue_col.update_one(
            {'user_id': user_id, 'status': 'active'},
            {'$set': {'status': status, 'updated_at': datetime.utcnow()}}
        )
    
    async def get_active_queues(self):
        """Get all active forwarding processes for crash recovery"""
        return await self.queue_col.find({'status': 'active'}).to_list(length=100)
    
    async def remove_completed_queues(self):
        """Clean up completed/cancelled queue items older than 1 day"""
        cutoff = datetime.utcnow() - timedelta(days=1)
        result = await self.queue_col.delete_many({
            'status': {'$in': ['completed', 'cancelled']},
            'updated_at': {'$lt': cutoff}
        })
        return result.deleted_count

    # Premium user management
    async def add_premium_user(self, user_id, plan_type="pro", duration_days=30, amount_paid=None):
        """Add or extend a user's premium subscription with atomic operation"""
        from pymongo import ReturnDocument
        now = datetime.utcnow()
        
        # Use atomic find_one_and_update to handle extension/creation in single operation
        result = await self.premium_col.find_one_and_update(
            {'user_id': int(user_id)},
            [
                {
                    '$set': {
                        'user_id': int(user_id),
                        'plan_type': plan_type,
                        'duration_days': duration_days,
                        'amount_paid': amount_paid,
                        'subscribed_at': {'$ifNull': ['$subscribed_at', now]},
                        'expires_at': {
                            '$cond': {
                                'if': {
                                    '$and': [
                                        {'$ne': ['$expires_at', None]},
                                        {'$gt': ['$expires_at', now]}
                                    ]
                                },
                                'then': {'$dateAdd': {
                                    'startDate': '$expires_at',
                                    'unit': 'day',
                                    'amount': duration_days
                                }},
                                'else': {'$dateAdd': {
                                    'startDate': now,
                                    'unit': 'day', 
                                    'amount': duration_days
                                }}
                            }
                        },
                        'is_active': True,
                        'auto_renew': False,
                        'features': self._get_plan_features(plan_type),
                        'updated_at': now
                    }
                }
            ],
            upsert=True,
            return_document=ReturnDocument.AFTER
        )
        return result
    
    def _get_plan_features(self, plan_type):
        """Get features for a specific plan type"""
        from config import Config
        return Config.PLAN_FEATURES.get(plan_type, Config.PLAN_FEATURES['free'])

    async def remove_premium_user(self, user_id):
        """Remove a user from premium"""
        return await self.premium_col.delete_many({'user_id': int(user_id)})

    async def is_premium_user(self, user_id):
        """Check if user has active premium subscription"""
        user = await self.premium_col.find_one({
            'user_id': int(user_id),
            'is_active': True,
            'expires_at': {'$gt': datetime.utcnow()}
        })
        return bool(user)
    
    async def get_user_plan(self, user_id):
        """Get user's current plan type"""
        user = await self.premium_col.find_one({
            'user_id': int(user_id),
            'is_active': True,
            'expires_at': {'$gt': datetime.utcnow()}
        })
        return user['plan_type'] if user else 'free'
    
    async def get_user_plan_features(self, user_id):
        """Get user's plan features"""
        user = await self.premium_col.find_one({
            'user_id': int(user_id),
            'is_active': True,
            'expires_at': {'$gt': datetime.utcnow()}
        })
        if user:
            plan_type = user.get('plan_type', 'free')
            current_plan_features = self._get_plan_features(plan_type)
            stored_features = user.get('features', {})
            
            # Merge current plan features with stored features (current plan takes precedence for missing keys)
            merged_features = {**current_plan_features, **stored_features}
            
            # If features are missing/outdated, update them in database
            if stored_features != merged_features:
                await self.premium_col.update_one(
                    {'user_id': int(user_id)},
                    {'$set': {'features': merged_features}}
                )
                print(f"✅ Updated features for Pro user {user_id}: added missing keys")
            
            return merged_features
        return self._get_plan_features('free')
    
    async def can_use_ftm_mode(self, user_id):
        """Check if user can use FTM Delta mode (Pro plan only)"""
        features = await self.get_user_plan_features(user_id)
        return features.get('ftm_mode', False)

    async def can_use_ftm_alpha_mode(self, user_id):
        """Check if user can use FTM Alpha mode (Pro plan only)"""
        features = await self.get_user_plan_features(user_id)
        return features.get('ftm_alpha_mode', False)
    
    async def get_forwarding_limit(self, user_id):
        """Get user's daily forwarding limit"""
        features = await self.get_user_plan_features(user_id)
        return features.get('forwarding_limit', 5)
    
    async def has_priority_support(self, user_id):
        """Check if user has priority support"""
        features = await self.get_user_plan_features(user_id)
        return features.get('priority_support', False)

    async def get_premium_user_details(self, user_id):
        """Get premium user details"""
        return await self.premium_col.find_one({'user_id': int(user_id)})
    
    async def get_premium_info(self, user_id):
        """Get premium user info (alias for get_premium_user_details)"""
        return await self.get_premium_user_details(user_id)
    
    async def get_user_usage(self, user_id):
        """Get user's total usage count"""
        daily_usage = await self.get_daily_usage(user_id)
        return daily_usage.get('processes', 0)
    
    async def get_days_remaining(self, user_id):
        """Get days remaining for premium subscription"""
        premium_info = await self.get_premium_user_details(user_id)
        if premium_info and premium_info.get('expires_at'):
            from datetime import datetime
            expires_at = premium_info['expires_at']
            if isinstance(expires_at, datetime):
                days_remaining = max(0, (expires_at - datetime.utcnow()).days)
                return days_remaining
        return 0
    
    async def get_monthly_usage(self, user_id):
        """Get user's usage for current month"""
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = await self.usage_col.find_one({
            'user_id': int(user_id),
            'date': start_of_month
        })
        return usage if usage else {'user_id': int(user_id), 'date': start_of_month, 'processes': 0, 'trial_processes': 0}

    async def add_trial_processes(self, user_id, additional_processes=1):
        """Add trial processes to user's monthly limit"""
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Check if trial already activated this month
        existing = await self.usage_col.find_one({
            'user_id': int(user_id), 
            'date': start_of_month,
            'trial_activated': True
        })
        
        if existing:
            return False  # Trial already claimed this month
            
        await self.usage_col.update_one(
            {'user_id': int(user_id), 'date': start_of_month},
            {
                '$set': {
                    'trial_processes': additional_processes, 
                    'trial_activated': True, 
                    'trial_granted_at': datetime.utcnow()
                },
                '$setOnInsert': {'processes': 0}
            },
            upsert=True
        )
        return True  # Trial successfully granted

    async def get_trial_status(self, user_id):
        """Get user's trial status - whether they have used their free trial"""
        monthly_usage = await self.get_monthly_usage(user_id)
        return {
            'used': monthly_usage.get('trial_activated', False),
            'trial_processes': monthly_usage.get('trial_processes', 0),
            'granted_at': monthly_usage.get('trial_granted_at')
        }

    async def get_alpha_config(self, user_id):
        """Get FTM Alpha mode configuration for user"""
        configs = await self.get_configs(user_id)
        return {
            'enabled': configs.get('ftm_alpha_mode', False),
            'source_chat': configs.get('alpha_source_chat'),
            'target_chat': configs.get('alpha_target_chat')
        }

    async def set_alpha_config(self, user_id, source_chat=None, target_chat=None, enabled=None):
        """Set FTM Alpha mode configuration"""
        current_config = await self.get_configs(user_id)
        
        if source_chat is not None:
            current_config['alpha_source_chat'] = source_chat
        if target_chat is not None:
            current_config['alpha_target_chat'] = target_chat
        if enabled is not None:
            current_config['ftm_alpha_mode'] = enabled
            
        await self.update_configs(user_id, current_config)
        return True

    async def validate_alpha_permissions(self, user_id, bot_client, source_chat, target_chat):
        """Validate if bot is admin in both source and target chats for Alpha mode"""
        try:
            # Check source chat permissions
            source_member = await bot_client.get_chat_member(source_chat, bot_client.me.id)
            if source_member.status not in ['administrator', 'creator']:
                return False, "Bot is not admin in source channel"
            
            # Check target chat permissions
            target_member = await bot_client.get_chat_member(target_chat, bot_client.me.id)
            if target_member.status not in ['administrator', 'creator']:
                return False, "Bot is not admin in target channel"
                
            return True, "Bot has admin permissions in both channels"
        except Exception as e:
            return False, f"Permission check failed: {str(e)}"

    async def get_all_alpha_users(self):
        """Get all users with active Alpha mode for real-time processing"""
        pipeline = [
            {'$match': {'configs.ftm_alpha_mode': True}},
            {'$project': {
                'user_id': '$id',
                'source_chat': '$configs.alpha_source_chat',
                'target_chat': '$configs.alpha_target_chat'
            }}
        ]
        return await self.col.aggregate(pipeline).to_list(length=1000)

    async def get_user_process_limit(self, user_id):
        """Get user's total process limit including trials"""
        base_limit = await self.get_forwarding_limit(user_id)
        if base_limit == -1:  # Premium user
            return -1
        
        # Check for trial processes
        monthly_usage = await self.get_monthly_usage(user_id)
        trial_processes = monthly_usage.get('trial_processes', 0)
        return base_limit + trial_processes

    async def get_all_premium_users(self):
        """Get all premium users"""
        return await self.premium_col.find({'is_active': True}).to_list(length=1000)

    async def cleanup_expired_premium(self):
        """Remove expired premium subscriptions"""
        result = await self.premium_col.update_many(
            {'expires_at': {'$lt': datetime.utcnow()}},
            {'$set': {'is_active': False}}
        )
        return result.modified_count

    # Payment verification system
    async def submit_payment_verification(self, user_id, screenshot_file_id, plan_type='pro', duration_days=30, amount=None):
        """Submit payment verification with plan support"""
        verification_data = {
            'user_id': int(user_id),
            'screenshot_file_id': screenshot_file_id,
            'plan_type': plan_type,
            'duration_days': duration_days,
            'amount': amount,
            'payment_method': '6354228145@axl',
            'submitted_at': datetime.utcnow(),
            'status': 'pending',  # pending, approved, rejected
            'reviewed_by': None,
            'reviewed_at': None,
            'review_notes': None
        }
        result = await self.payment_col.insert_one(verification_data)
        return result.inserted_id

    async def get_pending_verifications(self):
        """Get all pending payment verifications"""
        return await self.payment_col.find({'status': 'pending'}).to_list(length=100)

    async def approve_payment(self, verification_id, admin_id, notes=None):
        """Approve payment verification"""
        result = await self.payment_col.update_one(
            {'_id': verification_id},
            {
                '$set': {
                    'status': 'approved',
                    'reviewed_by': int(admin_id),
                    'reviewed_at': datetime.utcnow(),
                    'review_notes': notes
                }
            }
        )
        
        # Get the verification to add premium subscription
        verification = await self.payment_col.find_one({'_id': verification_id})
        if verification and result.modified_count > 0:
            # Add premium subscription based on plan and duration
            await self.add_premium_user(
                verification['user_id'], 
                verification.get('plan_type', 'pro'),
                verification.get('duration_days', 30),
                verification.get('amount')
            )
        
        return result.modified_count > 0

    async def reject_payment(self, verification_id, admin_id, notes=None):
        """Reject payment verification"""
        result = await self.payment_col.update_one(
            {'_id': verification_id},
            {
                '$set': {
                    'status': 'rejected',
                    'reviewed_by': int(admin_id),
                    'reviewed_at': datetime.utcnow(),
                    'review_notes': notes or 'Payment verification rejected'
                }
            }
        )
        return result.modified_count > 0

    async def get_verification_by_id(self, verification_id):
        """Get verification details by ID"""
        return await self.payment_col.find_one({'_id': verification_id})

    # Usage tracking for daily limits
    async def get_daily_usage(self, user_id):
        """Get user's usage for current day"""
        start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        usage = await self.usage_col.find_one({
            'user_id': int(user_id),
            'date': start_of_day
        })
        return usage if usage else {'user_id': int(user_id), 'date': start_of_day, 'processes': 0}

    async def increment_usage(self, user_id):
        """Increment user's monthly usage"""
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        await self.usage_col.update_one(
            {'user_id': int(user_id), 'date': start_of_month},
            {
                '$inc': {'processes': 1},
                '$set': {'last_used': datetime.utcnow()}
            },
            upsert=True
        )

    async def can_user_process(self, user_id):
        """Check if user can process based on their plan (including trial processes)"""
        # Get user's total forwarding limit (including trial processes)
        limit = await self.get_user_process_limit(user_id)
        
        # Unlimited for premium plans (Plus and Pro)
        if limit == -1:
            return True, "unlimited"
        
        # Check monthly usage for free users
        usage = await self.get_monthly_usage(user_id)
        if usage['processes'] >= limit:
            return False, "monthly_limit_reached"
        
        return True, "allowed"
    
    # Force subscribe functionality
    async def check_force_subscribe(self, user_id, client):
        """Check if user is subscribed to required channels"""
        from config import Config
        
        try:
            update_subscribed = False
            group_subscribed = False
            
            # Check update channel subscription using username (more reliable)
            try:
                member = await client.get_chat_member(f"@{Config.UPDATE_CHANNEL_USERNAME}", user_id)
                update_subscribed = member.status not in ['left', 'kicked']
                print(f"Update channel check: {update_subscribed} for user {user_id}")
            except Exception as e:
                print(f"Error checking update channel: {e}")
                # Fallback to ID if username fails
                try:
                    member = await client.get_chat_member(Config.UPDATE_CHANNEL_ID, user_id)
                    update_subscribed = member.status not in ['left', 'kicked']
                except:
                    update_subscribed = False
            
            # Check support group subscription using username (more reliable)
            try:
                member = await client.get_chat_member(f"@{Config.SUPPORT_GROUP_USERNAME}", user_id)
                group_subscribed = member.status not in ['left', 'kicked']
                print(f"Support group check: {group_subscribed} for user {user_id}")
            except Exception as e:
                print(f"Error checking support group: {e}")
                # Fallback to ID if username fails
                try:
                    member = await client.get_chat_member(Config.SUPPORT_GROUP_ID, user_id)
                    group_subscribed = member.status not in ['left', 'kicked']
                except:
                    group_subscribed = False
                
            result = {
                'update_channel': update_subscribed,
                'support_group': group_subscribed,
                'all_subscribed': update_subscribed and group_subscribed
            }
            print(f"Subscription check result for user {user_id}: {result}")
            return result
            
        except Exception as e:
            print(f"Force subscribe check error: {e}")
            # If there's an error checking, assume not subscribed
            return {
                'update_channel': False,
                'support_group': False,
                'all_subscribed': False
            }

    # Admin chat sessions
    async def start_admin_chat(self, admin_id, target_user_id):
        """Start admin chat session with user"""
        chat_data = {
            'admin_id': int(admin_id),
            'target_user_id': int(target_user_id),
            'started_at': datetime.utcnow(),
            'is_active': True,
            'messages': []
        }
        
        # End any existing chat session for this admin
        await self.admin_chat_col.update_many(
            {'admin_id': int(admin_id), 'is_active': True},
            {'$set': {'is_active': False, 'ended_at': datetime.utcnow()}}
        )
        
        result = await self.admin_chat_col.insert_one(chat_data)
        return result.inserted_id

    async def get_active_admin_chat(self, admin_id):
        """Get active admin chat session"""
        return await self.admin_chat_col.find_one({
            'admin_id': int(admin_id),
            'is_active': True
        })

    async def end_admin_chat(self, admin_id):
        """End admin chat session"""
        return await self.admin_chat_col.update_many(
            {'admin_id': int(admin_id), 'is_active': True},
            {'$set': {'is_active': False, 'ended_at': datetime.utcnow()}}
        )

    async def add_chat_message(self, session_id, from_admin, message_text):
        """Add message to admin chat session"""
        message_data = {
            'from_admin': from_admin,
            'message': message_text,
            'timestamp': datetime.utcnow()
        }
        return await self.admin_chat_col.update_one(
            {'_id': session_id},
            {'$push': {'messages': message_data}}
        )

    async def get_active_chat_for_user(self, user_id):
        """Get active admin chat session for a specific user"""
        return await self.admin_chat_col.find_one({
            'target_user_id': int(user_id),
            'is_active': True
        })
        
    
    # Contact requests methods
    async def create_contact_request(self, user_id):
        """Create a new contact request"""
        contact_data = {
            'user_id': int(user_id),
            'status': 'pending',
            'created_at': datetime.utcnow(),
            'reviewed_at': None,
            'reviewed_by': None
        }
        
        result = await self.contact_requests_col.insert_one(contact_data)
        return result.inserted_id
        
    async def create_chat_request(self, user_id):
        """Create a new chat request"""
        chat_data = {
            'user_id': int(user_id),
            'status': 'pending',
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(hours=24),  # Auto-expire after 24 hours
            'reviewed_at': None,
            'reviewed_by': None,
            'notifications': []  # Store notification message IDs for cleanup
        }
        
        result = await self.chat_requests_col.insert_one(chat_data)
        return result.inserted_id
        
    async def get_pending_chat_request(self, user_id):
        """Get pending chat request for user"""
        return await self.chat_requests_col.find_one({
            'user_id': int(user_id),
            'status': 'pending'
        })
        
    async def get_chat_request_by_id(self, request_id):
        """Get chat request by ID"""
        return await self.chat_requests_col.find_one({
            '_id': ObjectId(request_id)
        })
        
    async def update_chat_request_status(self, request_id, status, admin_id=None):
        """Update chat request status"""
        update_data = {
            'status': status,
            'reviewed_at': datetime.utcnow()
        }
        if admin_id:
            update_data['reviewed_by'] = int(admin_id)
            
        return await self.chat_requests_col.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': update_data}
        )
        
    async def store_chat_notifications(self, request_id, notification_messages):
        """Store notification message IDs for cleanup"""
        return await self.chat_requests_col.update_one(
            {'_id': ObjectId(request_id)},
            {'$set': {'notifications': notification_messages}}
        )
        
    async def cleanup_chat_notifications(self, request_id, client, accepting_admin_id):
        """Delete notifications from all other admins when one admin accepts"""
        try:
            # Get the request to find notification messages
            request = await self.get_chat_request_by_id(request_id)
            if not request or 'notifications' not in request:
                return
            
            # Delete messages from all admins except the one who accepted
            for notification in request['notifications']:
                if notification['admin_id'] != accepting_admin_id:
                    try:
                        await client.delete_messages(
                            chat_id=notification['admin_id'],
                            message_ids=notification['message_id']
                        )
                    except Exception as e:
                        print(f"Failed to delete notification for admin {notification['admin_id']}: {e}")
        except Exception as e:
            print(f"Error cleaning up notifications: {e}")
            
    async def cleanup_expired_chat_requests(self):
        """Remove chat requests and data older than 24 hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Find expired requests
        expired_requests = self.chat_requests_col.find({
            'created_at': {'$lt': cutoff_time}
        })
        
        # Also cleanup any active chat sessions from expired requests
        async for request in expired_requests:
            if request.get('status') == 'accepted':
                # End any active chat sessions
                await self.admin_chat_col.update_many(
                    {'target_user_id': request['user_id'], 'is_active': True},
                    {'$set': {'is_active': False, 'ended_at': datetime.utcnow()}}
                )
        
        # Delete expired chat requests
        result = await self.chat_requests_col.delete_many({
            'created_at': {'$lt': cutoff_time}
        })
        
        return result.deleted_count

    async def get_pending_contact_request(self, user_id):
        """Get pending contact request for user"""
        return await self.contact_requests_col.find_one({
            'user_id': int(user_id),
            'status': 'pending'
        })

    async def get_contact_request_by_id(self, request_id):
        """Get contact request by ID"""
        return await self.contact_requests_col.find_one({
            '_id': ObjectId(request_id)
        })

    async def update_contact_request_status(self, request_id, status):
        """Update contact request status"""
        return await self.contact_requests_col.update_one(
            {'_id': ObjectId(request_id)},
            {
                '$set': {
                    'status': status,
                    'reviewed_at': datetime.utcnow()
                }
            }
        )

    # ===== EVENTS SYSTEM DATABASE OPERATIONS =====
    
    async def create_event(self, event_name, creator_id, duration_days=None, event_type="discount", 
                          discount_percentage=None, reward_config=None, start_date=None, 
                          redeem_codes=None, max_redemptions=None):
        """Create a new FTM event with unique event_id generation"""
        from datetime import datetime, timedelta
        import secrets
        import string
        
        # Generate unique event_id with retry
        max_retries = 5
        for attempt in range(max_retries):
            event_id = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            existing = await self.events_col.find_one({'event_id': event_id})
            if not existing:
                break
        else:
            raise Exception("Failed to generate unique event_id after multiple attempts")
        
        event_data = {
            'event_name': event_name,
            'creator_id': int(creator_id),
            'event_type': event_type,  # 'discount' or 'redeem_code'
            'created_at': datetime.utcnow(),
            'status': 'draft',  # 'draft', 'active', 'completed', 'cancelled'
            'duration_days': duration_days,
            'start_date': start_date or datetime.utcnow(),
            'end_date': start_date + timedelta(days=duration_days) if start_date and duration_days else None,
            'max_redemptions': max_redemptions,
            'total_redemptions': 0,
            'event_id': event_id
        }
        
        # Add discount-specific fields
        if event_type == "discount":
            event_data.update({
                'discount_percentage': discount_percentage,
                'reward_config': reward_config or {
                    'free': {'plan': 'plus', 'duration': 10},
                    'plus': {'plan': 'pro', 'duration': 10},
                    'pro': {'plan': 'pro', 'duration': 10}
                }
            })
        
        # Add redeem code-specific fields
        elif event_type == "redeem_code":
            event_data.update({
                'codes_generated': False,  # Will be set when codes are generated
                'codes_per_group': 0,  # Number of codes per user group
                'code_durations': {}  # Will be set when codes are generated
            })
        
        result = await self.events_col.insert_one(event_data)
        return result.inserted_id
    
    async def get_event_by_id(self, event_id):
        """Get event by event_id"""
        return await self.events_col.find_one({'event_id': event_id})
    
    async def get_event_by_name(self, event_name):
        """Get event by name"""
        return await self.events_col.find_one({'event_name': event_name})
    
    async def get_all_events(self, status=None):
        """Get all events, optionally filtered by status"""
        query = {}
        if status:
            query['status'] = status
        return await self.events_col.find(query).to_list(length=100)
    
    async def get_active_events(self):
        """Get all currently active events"""
        now = datetime.utcnow()
        return await self.events_col.find({
            'status': 'active',
            'start_date': {'$lte': now},
            '$or': [
                {'end_date': {'$gt': now}},
                {'end_date': None}
            ]
        }).to_list(length=50)
    
    async def update_event_status(self, event_id, status):
        """Update event status"""
        return await self.events_col.update_one(
            {'event_id': event_id},
            {'$set': {'status': status, 'updated_at': datetime.utcnow()}}
        )
    
    async def start_event(self, event_id, start_date=None):
        """Start an event (change status to active)"""
        update_data = {
            'status': 'active',
            'start_date': start_date or datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Calculate end_date if duration is specified
        event = await self.get_event_by_id(event_id)
        if event and event.get('duration_days'):
            from datetime import timedelta
            update_data['end_date'] = update_data['start_date'] + timedelta(days=event['duration_days'])
        
        return await self.events_col.update_one(
            {'event_id': event_id},
            {'$set': update_data}
        )
    
    async def schedule_event(self, event_id, start_date):
        """Schedule an event to start at a specific date"""
        from datetime import timedelta
        
        event = await self.get_event_by_id(event_id)
        if not event:
            return False
        
        update_data = {
            'status': 'scheduled',
            'start_date': start_date,
            'updated_at': datetime.utcnow()
        }
        
        # Calculate end_date if duration is specified
        if event.get('duration_days'):
            update_data['end_date'] = start_date + timedelta(days=event['duration_days'])
        
        return await self.events_col.update_one(
            {'event_id': event_id},
            {'$set': update_data}
        )
    
    async def generate_redeem_codes(self, event_id, durations_config, codes_per_group=100):
        """Generate multiple unique redeem codes for each user group in separate collection"""
        import secrets
        import string
        import hashlib
        
        def generate_code():
            return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        
        codes_created = []
        
        for group, duration in durations_config.items():
            for _ in range(codes_per_group):
                code = generate_code()
                code_hash = hashlib.sha256(code.encode()).hexdigest()
                
                code_data = {
                    'event_id': event_id,
                    'user_group': group,
                    'code': code,  # Store original for admin view only
                    'code_hash': code_hash,
                    'duration': duration,
                    'claimed_by': None,
                    'claimed_at': None,
                    'remaining_uses': 1,
                    'created_at': datetime.utcnow()
                }
                codes_created.append(code_data)
        
        # Insert all codes atomically
        if codes_created:
            await self.event_codes_col.insert_many(codes_created)
        
        # Update event with code generation info
        return await self.events_col.update_one(
            {'event_id': event_id},
            {
                '$set': {
                    'code_durations': durations_config,
                    'codes_generated': True,
                    'codes_per_group': codes_per_group,
                    'updated_at': datetime.utcnow()
                }
            }
        )
    
    async def validate_redeem_code(self, code, user_plan):
        """Validate if a redeem code is valid for user's plan using codes collection"""
        import hashlib
        
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        now = datetime.utcnow()
        
        # Find the code in the codes collection
        code_doc = await self.event_codes_col.find_one({
            'code_hash': code_hash,
            'user_group': user_plan,
            'claimed_by': None,
            'remaining_uses': {'$gt': 0}
        })
        
        if not code_doc:
            return None, "Invalid code, already used, or not for your user group"
        
        # Verify the associated event is active
        event = await self.events_col.find_one({
            'event_id': code_doc['event_id'],
            'status': 'active',
            'start_date': {'$lte': now},
            '$or': [
                {'end_date': {'$gt': now}},
                {'end_date': None}
            ]
        })
        
        if not event:
            return None, "Event is not active or has expired"
        
        return event, "Valid code"
    
    async def redeem_event_code(self, user_id, event_id, user_plan, code):
        """Atomically redeem an event code for a user using separate codes collection"""
        import hashlib
        
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        now = datetime.utcnow()
        
        try:
            # First verify event is active and user hasn't already redeemed
            event = await self.events_col.find_one({
                'event_id': event_id,
                'status': 'active',
                'start_date': {'$lte': now},
                '$or': [{'end_date': {'$gt': now}}, {'end_date': None}]
            })
            
            if not event:
                return False, "Event not found or not active"
            
            # Check max redemptions at event level
            if event.get('max_redemptions') and event.get('total_redemptions', 0) >= event['max_redemptions']:
                return False, "Event redemption limit reached"
            
            # Atomically claim a code and check for duplicate user redemption
            code_result = await self.event_codes_col.find_one_and_update(
                {
                    'event_id': event_id,
                    'user_group': user_plan,
                    'code_hash': code_hash,
                    'claimed_by': None,
                    'remaining_uses': {'$gt': 0}
                },
                {
                    '$set': {
                        'claimed_by': int(user_id),
                        'claimed_at': now
                    },
                    '$inc': {'remaining_uses': -1}
                },
                return_document=True
            )
            
            if not code_result:
                return False, "Invalid code, already used, or not for your user group"
            
            # Create redemption record with unique constraint
            redemption_data = {
                'user_id': int(user_id),
                'event_id': event_id,
                'event_name': event['event_name'],
                'user_plan': user_plan,
                'redeemed_code_hash': code_hash,
                'redeemed_at': now,
                'reward_duration': code_result['duration'],
                'status': 'completed'
            }
            
            await self.event_redemptions_col.insert_one(redemption_data)
            
            # Increment event total redemptions
            await self.events_col.update_one(
                {'event_id': event_id},
                {'$inc': {'total_redemptions': 1}}
            )
            
            # Apply premium subscription
            if code_result['duration'] > 0:
                await self.add_premium_user(
                    user_id, 
                    'plus',  # Default to plus for code redemptions
                    code_result['duration']
                )
            
            return True, f"Successfully redeemed! You got {code_result['duration']} days of premium."
            
        except Exception as e:
            if "duplicate key" in str(e).lower():
                return False, "You have already redeemed this event"
            return False, f"Redemption failed: {str(e)}"
    
    async def redeem_discount_event(self, user_id, event_id, user_plan):
        """Atomically redeem a discount event for a user"""
        now = datetime.utcnow()
        
        try:
            # Atomic operation with all validations in a single query
            event_update_result = await self.events_col.find_one_and_update(
                {
                    'event_id': event_id,
                    'status': 'active',
                    'start_date': {'$lte': now},
                    '$or': [{'end_date': {'$gt': now}}, {'end_date': None}],
                    f'reward_config.{user_plan}': {'$exists': True},
                    '$or': [
                        {'max_redemptions': None},
                        {'$expr': {'$lt': ['$total_redemptions', '$max_redemptions']}}
                    ]
                },
                {'$inc': {'total_redemptions': 1}},
                return_document=True
            )
            
            if not event_update_result:
                return False, "Event not active, no reward for your plan, or redemption limit reached"
            
            # Get reward configuration
            user_reward = event_update_result['reward_config'][user_plan]
            
            # Create redemption record with unique constraint
            redemption_data = {
                'user_id': int(user_id),
                'event_id': event_id,
                'event_name': event_update_result['event_name'],
                'user_plan': user_plan,
                'redeemed_at': now,
                'reward_plan': user_reward['plan'],
                'reward_duration': user_reward['duration'],
                'status': 'completed'
            }
            
            await self.event_redemptions_col.insert_one(redemption_data)
            
            # Apply the reward (add/extend premium subscription)
            if user_reward['plan'] in ['plus', 'pro']:
                await self.add_premium_user(
                    user_id, 
                    user_reward['plan'], 
                    user_reward['duration']
                )
            
            return True, f"Successfully redeemed! You got {user_reward['duration']} days of {user_reward['plan'].title()} plan."
            
        except Exception as e:
            if "duplicate key" in str(e).lower():
                return False, "You have already redeemed this event"
            return False, f"Redemption failed: {str(e)}"
    
    async def get_user_redemptions(self, user_id):
        """Get all redemptions for a user"""
        return await self.event_redemptions_col.find({
            'user_id': int(user_id)
        }).to_list(length=50)
    
    async def get_event_redemptions(self, event_id):
        """Get all redemptions for an event"""
        return await self.event_redemptions_col.find({
            'event_id': event_id
        }).to_list(length=100)
    
    async def check_user_event_redemption(self, user_id, event_id):
        """Check if user has already redeemed a specific event"""
        redemption = await self.event_redemptions_col.find_one({
            'user_id': int(user_id),
            'event_id': event_id
        })
        return redemption is not None
    
    async def get_event_stats(self, event_id):
        """Get statistics for an event"""
        event = await self.get_event_by_id(event_id)
        if not event:
            return None
        
        # Count redemptions by user plan
        redemptions_by_plan = {}
        async for redemption in self.event_redemptions_col.find({'event_id': event_id}):
            plan = redemption.get('user_plan', 'unknown')
            redemptions_by_plan[plan] = redemptions_by_plan.get(plan, 0) + 1
        
        return {
            'event': event,
            'total_redemptions': event.get('total_redemptions', 0),
            'redemptions_by_plan': redemptions_by_plan,
            'max_redemptions': event.get('max_redemptions'),
            'redemption_percentage': (
                (event.get('total_redemptions', 0) / event.get('max_redemptions', 1)) * 100
                if event.get('max_redemptions') else 0
            )
        }
    
    async def cleanup_expired_events(self):
        """Mark expired events as completed"""
        now = datetime.utcnow()
        result = await self.events_col.update_many(
            {
                'status': 'active',
                'end_date': {'$lt': now}
            },
            {
                '$set': {
                    'status': 'completed',
                    'updated_at': now
                }
            }
        )
        return result.modified_count
    
    async def activate_scheduled_events(self):
        """Activate events that are scheduled to start"""
        now = datetime.utcnow()
        result = await self.events_col.update_many(
            {
                'status': 'scheduled',
                'start_date': {'$lte': now}
            },
            {
                '$set': {
                    'status': 'active',
                    'updated_at': now
                }
            }
        )
        return result.modified_count

    async def initialize_events_indexes(self):
        """Initialize database indexes for events system"""
        try:
            # Events collection indexes
            await self.events_col.create_index('event_id', unique=True)
            await self.events_col.create_index([('status', 1), ('start_date', 1), ('end_date', 1)])
            await self.events_col.create_index('created_at')
            
            # Event redemptions collection indexes
            await self.event_redemptions_col.create_index(
                [('event_id', 1), ('user_id', 1)], 
                unique=True
            )
            await self.event_redemptions_col.create_index('user_id')
            await self.event_redemptions_col.create_index('event_id')
            await self.event_redemptions_col.create_index('redeemed_at')
            
            # Event codes collection indexes
            await self.event_codes_col.create_index('code_hash', unique=True)
            await self.event_codes_col.create_index([('event_id', 1), ('user_group', 1)])
            await self.event_codes_col.create_index([('event_id', 1), ('claimed_by', 1)])
            await self.event_codes_col.create_index('claimed_by')
            await self.event_codes_col.create_index('remaining_uses')
            
            print("✅ Events system database indexes initialized successfully")
        except Exception as e:
            print(f"⚠️ Events indexes initialization warning: {e}")
    
    async def process_scheduled_events(self):
        """Process scheduled events and status transitions"""
        now = datetime.utcnow()
        
        # Activate scheduled events that should start now
        activated = await self.activate_scheduled_events()
        
        # Complete expired active events
        completed = await self.cleanup_expired_events()
        
        return {'activated': activated, 'completed': completed}
    
    async def initialize_navratri_event(self):
        """Initialize the pre-loaded Navratri Event"""
        try:
            # Check if Navratri event already exists
            existing_event = await self.get_event_by_name("Navratri Event")
            if existing_event:
                print("✅ Navratri Event already exists")
                return existing_event['event_id']
            
            # Create Navratri Event with discount type
            navratri_config = {
                'free': {'plan': 'plus', 'duration': 10},
                'plus': {'plan': 'pro', 'duration': 10}, 
                'pro': {'plan': 'pro', 'duration': 10}
            }
            
            event_id = await self.create_event(
                event_name="Navratri Event",
                creator_id=0,  # System created
                duration_days=None,  # Ongoing event
                event_type="discount",
                discount_percentage=100,  # Free subscription reward
                reward_config=navratri_config,
                start_date=datetime.utcnow(),
                max_redemptions=None  # Unlimited redemptions
            )
            
            # Get the created event by name (more reliable) and activate it
            created_event = await self.get_event_by_name("Navratri Event")
            if created_event:
                await self.update_event_status(created_event['event_id'], 'active')
                print(f"✅ Navratri Event activated with ID: {created_event['event_id']}")
                return created_event['event_id']
            else:
                print("⚠️ Failed to activate Navratri Event - event not found after creation")
                return None
            
        except Exception as e:
            print(f"⚠️ Failed to initialize Navratri Event: {e}")
            return None

    # User State Management
    async def set_user_state(self, user_id, state_data):
        """Set user state for multi-step operations"""
        try:
            return await self.col.update_one(
                {'id': int(user_id)},
                {
                    '$set': {
                        'current_state': state_data,
                        'state_updated_at': datetime.utcnow()
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"Error setting user state for {user_id}: {e}")
            return None
    
    async def get_user_state(self, user_id):
        """Get user's current state"""
        try:
            user = await self.col.find_one({'id': int(user_id)})
            return user.get('current_state') if user else None
        except Exception as e:
            print(f"Error getting user state for {user_id}: {e}")
            return None
    
    async def clear_user_state(self, user_id):
        """Clear user's current state"""
        try:
            return await self.col.update_one(
                {'id': int(user_id)},
                {
                    '$unset': {
                        'current_state': '',
                        'state_updated_at': ''
                    }
                }
            )
        except Exception as e:
            print(f"Error clearing user state for {user_id}: {e}")
            return None

db = Database(Config.DATABASE_URI, Config.DATABASE_NAME)
