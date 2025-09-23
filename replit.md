# Overview

This is a Telegram Auto-Forward Bot (V2) built with Python and Pyrogram. The bot enables users to automatically forward messages from one Telegram channel/chat to another with advanced filtering, customization options, and premium subscription tiers. The system supports both bot tokens and user sessions for authentication, provides comprehensive message filtering capabilities, and includes features like duplicate detection, file size limits, custom captions, and real-time forwarding modes.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **Core Framework**: Pyrogram (v2.0.93) for Telegram Bot API interactions with asyncio-based asynchronous programming
- **Architecture Pattern**: Plugin-based modular architecture with separate files for different functionalities
- **Concurrency**: 50 workers configured for handling multiple simultaneous requests
- **Process Management**: Flask web server integration for deployment monitoring and uptime checks on port 5000

## Authentication & User Management
- **Multi-Bot Support**: Users can add multiple bots or userbots to their account with session management
- **Authentication Methods**: Support for bot tokens, user session strings, and direct phone number authentication
- **Access Control**: Owner-based permissions with configurable admin IDs and sudo user privileges
- **Force Subscribe**: Mandatory subscription to support group and update channel for non-sudo users

## Message Processing Engine
- **Forward Engine**: Custom forwarding logic with source and target chat validation
- **FTM Modes**: 
  - FTM Delta Mode with source link tracking and attribution
  - FTM Alpha Mode for real-time auto-forwarding (Premium feature)
- **Filter System**: Comprehensive filtering by message type (text, photo, video, document, audio, voice, animation, sticker, poll)
- **Duplicate Detection**: MongoDB-based tracking to prevent redundant message forwards
- **File Processing**: Size filtering, extension-based filtering, and custom caption support

## Premium Subscription System
- **Three-Tier Structure**: Free, Plus, and Pro plans with different feature sets
- **Pricing Model**: 
  - Plus: ₹199 (15 days), ₹299 (30 days)
  - Pro: ₹299 (15 days), ₹549 (30 days)
- **Payment Integration**: UPI-based payment system with manual verification process
- **Feature Gating**: Unlimited forwarding, priority support, and advanced modes based on subscription tier

## Configuration Management
- **Settings System**: Per-user configurable settings including filters, captions, buttons, and forwarding preferences
- **Environment Variables**: Centralized configuration through environment variables for API credentials
- **Dynamic Configuration**: Runtime configuration updates through inline keyboard interfaces
- **State Management**: User state tracking for multi-step operations and command flows

## User Interface & Commands
- **Command System**: Comprehensive command set including `/start`, `/forward`, `/settings`, `/reset`, `/ftm`
- **Inline Keyboards**: Rich interactive menus for settings management and bot configuration
- **Callback Handlers**: Event-driven interface updates and setting modifications
- **Progress Tracking**: Real-time status updates during forwarding operations

## Administrative Features
- **Broadcast System**: Admin-only message broadcasting to all users with delivery tracking
- **Event Management**: Event creation and redemption system for promotional activities
- **Contact System**: Admin contact request handling with chat session management
- **System Monitoring**: Network speed testing, system information, and performance metrics

# External Dependencies

## Database
- **MongoDB**: Primary database using Motor async driver for non-blocking operations
- **Collections**: 
  - `users`: User data and ban status management
  - `bots`: Bot configurations and credentials storage
  - `channels`: Channel/chat configurations and settings
  - `premium_users`: Premium subscription tracking
  - `payment_verifications`: Payment verification records
  - `usage_tracking`: Monthly usage statistics
  - `events`: Event management system
  - `admin_chats`: Admin communication sessions

## Telegram APIs
- **Pyrogram**: Main library for Telegram Bot API interactions (v2.0.93)
- **API Credentials**: Telegram API ID and hash for bot authentication
- **Bot Token**: BotFather-generated token for bot operations

## External Services
- **UPI Payment System**: Manual payment verification using UPI ID `6354228145@axl`
- **Flask Web Server**: Health check endpoint for deployment platforms
- **Speedtest Integration**: Network performance monitoring capabilities

## Development Tools
- **Logging**: Comprehensive logging system with file-based configuration
- **Error Handling**: FloodWait management and graceful error recovery
- **Rate Limiting**: Built-in rate limiting for API calls and message forwarding
- **Cleanup Tasks**: Automated cleanup of expired data and sessions