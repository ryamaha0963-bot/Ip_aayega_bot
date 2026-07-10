"""
IP Grabber Bot - Session Add Command Ke Saath
"""

import asyncio
import json
import logging
import os
import re
import sys
from typing import Optional, Tuple

from pyrogram import Client, idle, filters
from pyrogram.raw import functions, types
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
LOGGER = logging.getLogger(__name__)

# ============================================
# CONFIG
# ============================================
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Session file path
SESSION_FILE = "sessions.txt"

if not all([API_ID, API_HASH, BOT_TOKEN, ADMIN_ID]):
    LOGGER.error("❌ Missing environment variables!")
    sys.exit(1)

# ============================================
# SESSION MANAGER - Bot Ke Through Sessions Save
# ============================================
class SessionManager:
    def __init__(self):
        self.file = "data/sessions.json"
        self.session_file = "data/session_string.txt"
        os.makedirs("data", exist_ok=True)
        self.data = self._load()
        self.session_string = self._load_session_string()
    
    def _load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save(self):
        with open(self.file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def _load_session_string(self):
        """Load saved session string"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r') as f:
                    return f.read().strip()
            except:
                return ""
        return ""
    
    def _save_session_string(self, session_str):
        """Save session string"""
        with open(self.session_file, 'w') as f:
            f.write(session_str)
        self.session_string = session_str
    
    def get_session_string(self):
        """Get current session string"""
        return self.session_string
    
    def set_session_string(self, session_str):
        """Set new session string"""
        if session_str and len(session_str) > 10:
            self._save_session_string(session_str)
            return True
        return False
    
    def add(self, sid, chat_id, name):
        if sid in self.data:
            return False
        self.data[sid] = {"chat_id": chat_id, "name": name, "ip": None, "port": None}
        self._save()
        return True
    
    def get(self, sid):
        return self.data.get(sid)
    
    def update_ip(self, sid, ip, port):
        if sid in self.data:
            self.data[sid]["ip"] = ip
            self.data[sid]["port"] = port
            self._save()
            return True
        return False
    
    def delete(self, sid):
        if sid in self.data:
            del self.data[sid]
            self._save()
            return True
        return False
    
    def list_all(self):
        return self.data

# ============================================
# IP EXTRACTOR - Session String Use Karega
# ============================================
class IPExtractor:
    def __init__(self):
        self.client = None
        self.session_string = None
    
    async def init_client(self, session_string):
        """Initialize user client with session string"""
        if self.client:
            await self.client.stop()
            self.client = None
        
        if not session_string:
            return False
        
        try:
            self.session_string = session_string
            self.client = Client(
                "ip_user",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string
            )
            await self.client.start()
            LOGGER.info("✅ User client started with new session")
            return True
        except Exception as e:
            LOGGER.error(f"❌ Failed to start client: {e}")
            return False
    
    async def extract(self, chat_id: int) -> Tuple[Optional[str], Optional[int]]:
        if not self.client:
            LOGGER.error("❌ No user client! Add session first using /setsession")
            return None, None
        
        try:
            peer = await self.client.resolve_peer(chat_id)
            
            if isinstance(peer, types.InputPeerChannel):
                full = await self.client.invoke(
                    functions.channels.GetFullChannel(
                        channel=types.InputChannel(
                            channel_id=peer.channel_id,
                            access_hash=peer.access_hash
                        )
                    )
                )
            elif isinstance(peer, types.InputPeerChat):
                full = await self.client.invoke(
                    functions.messages.GetFullChat(chat_id=peer.chat_id)
                )
            else:
                return None, None
            
            call = getattr(full.full_chat, "call", None)
            if not call:
                return None, None
            
            group_call = await self.client.invoke(
                functions.phone.GetGroupCall(
                    call=types.InputGroupCall(
                        id=call.id,
                        access_hash=call.access_hash
                    ),
                    limit=100
                )
            )
            
            call_obj = group_call.call
            params_raw = getattr(call_obj, "params", None)
            params_data = getattr(params_raw, "data", "{}") if params_raw else "{}"
            
            try:
                parsed = json.loads(params_data)
            except:
                return None, None
            
            endpoints = parsed.get("endpoints", [])
            for endpoint in endpoints:
                if ":" in endpoint:
                    parts = endpoint.rsplit(":", 1)
                    if len(parts) == 2:
                        ip, port_str = parts
                        try:
                            port = int(port_str)
                            if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                                return ip, port
                        except:
                            continue
            
            return None, None
            
        except Exception as e:
            LOGGER.error(f"Extract error: {e}")
            return None, None

# ============================================
# BOT
# ============================================
class IPBot:
    def __init__(self):
        self.bot = Client(
            "ip_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        
        self.sessions = SessionManager()
        self.extractor = IPExtractor()
        self.admin = ADMIN_ID
        
        # Auto-start user client if session exists
        self.user_started = False
    
    async def start(self):
        LOGGER.info("🚀 Starting IP Grabber Bot...")
        
        await self.bot.start()
        LOGGER.info("✅ Bot started")
        
        # Check if session string exists
        saved_session = self.sessions.get_session_string()
        if saved_session:
            LOGGER.info("🔄 Found saved session, initializing user client...")
            success = await self.extractor.init_client(saved_session)
            if success:
                self.user_started = True
                LOGGER.info("✅ User client started with saved session")
            else:
                LOGGER.warning("⚠️ Saved session is invalid! Use /setsession to add new session")
        
        self._register_handlers()
        
        try:
            await self.bot.send_message(
                self.admin,
                "✅ **IP Grabber Bot Started!**\n\n"
                f"Sessions: {len(self.sessions.list_all())}\n"
                f"User Client: {'✅ Active' if self.user_started else '❌ Not Set'}\n\n"
                "Use /setsession to add your session string\n"
                "Use /help for commands."
            )
        except:
            pass
        
        LOGGER.info("✅ Bot is running!")
        await idle()
        
        await self.bot.stop()
        if self.extractor.client:
            await self.extractor.client.stop()
        LOGGER.info("✅ Bot stopped")
    
    def _register_handlers(self):
        # ============ SESSION ADD COMMAND ============
        @self.bot.on_message(filters.command("setsession"))
        async def setsession_cmd(client, message):
            """Add session string through bot"""
            if message.from_user.id != self.admin:
                await message.reply_text("❌ Only admin can set session!")
                return
            
            args = message.text.split(maxsplit=1)
            if len(args) < 2:
                await message.reply_text(
                    "❌ **Usage:**\n"
                    "/setsession <session_string>\n\n"
                    "**How to get session string:**\n"
                    "1. Run this Python script:\n"
                    "```python\n"
                    "from pyrogram import Client\n"
                    "app = Client('session', api_id=YOUR_API_ID, api_hash='YOUR_API_HASH')\n"
                    "app.start()\n"
                    "print(app.export_session_string())\n"
                    "```\n"
                    "2. Copy the output\n"
                    "3. Paste here: /setsession <session_string>"
                )
                return
            
            session_str = args[1].strip()
            
            if len(session_str) < 20:
                await message.reply_text("❌ Invalid session string! Too short.")
                return
            
            status = await message.reply_text("🔄 Testing session string...")
            
            try:
                # Test session by initializing client
                success = await self.extractor.init_client(session_str)
                
                if success:
                    # Save session
                    self.sessions.set_session_string(session_str)
                    self.user_started = True
                    
                    # Get account info
                    me = await self.extractor.client.get_me()
                    
                    await status.edit_text(
                        f"✅ **Session Added Successfully!**\n\n"
                        f"**Account:** {me.first_name}\n"
                        f"**Username:** @{me.username or 'N/A'}\n"
                        f"**Phone:** {me.phone_number or 'N/A'}\n\n"
                        f"Now use /add to add VC sessions and /get to extract IP!"
                    )
                else:
                    await status.edit_text(
                        "❌ **Invalid Session String!**\n\n"
                        "Make sure:\n"
                        "1. Session string is correct\n"
                        "2. Account is active\n"
                        "3. API_ID and API_HASH are correct"
                    )
            except Exception as e:
                await status.edit_text(f"❌ Error: {e}")
        
        # ============ CHECK SESSION STATUS ============
        @self.bot.on_message(filters.command("checksession"))
        async def checksession_cmd(client, message):
            """Check if session is active"""
            if message.from_user.id != self.admin:
                await message.reply_text("❌ Only admin can check session!")
                return
            
            status = "✅ Active" if self.user_started else "❌ Not Set"
            
            text = f"📊 **Session Status:**\n\n"
            text += f"Status: {status}\n"
            
            if self.user_started and self.extractor.client:
                try:
                    me = await self.extractor.client.get_me()
                    text += f"Account: {me.first_name}\n"
                    text += f"Username: @{me.username or 'N/A'}\n"
                except:
                    text += "⚠️ Session expired! Use /setsession to add new session."
            
            await message.reply_text(text)
        
        # ============ OTHER COMMANDS ============
        @self.bot.on_message(filters.command("start"))
        async def start_cmd(client, message):
            session_status = "✅ Active" if self.user_started else "❌ Not Set"
            await message.reply_text(
                f"🔍 **IP Grabber Bot**\n\n"
                f"**User Client:** {session_status}\n\n"
                "**Commands:**\n"
                "/start - Show this\n"
                "/help - Help\n"
                "/setsession <session_string> - Add session account\n"
                "/checksession - Check session status\n"
                "/add <id> <chat_id> <name> - Add VC session\n"
                "/del <id> - Delete VC session\n"
                "/list - List all VC sessions\n"
                "/get <id> - Extract IP\n"
                "/extract <chat_id> - Direct extract\n\n"
                "**First time?**\n"
                "1. Use /setsession to add your account session\n"
                "2. Use /add to add VC session\n"
                "3. Use /get to extract IP"
            )
        
        @self.bot.on_message(filters.command("help"))
        async def help_cmd(client, message):
            await start_cmd(client, message)
        
        @self.bot.on_message(filters.command("add"))
        async def add_cmd(client, message):
            if message.from_user.id != self.admin:
                await message.reply_text("❌ Admin only!")
                return
            
            if not self.user_started:
                await message.reply_text("❌ No session set! Use /setsession first.")
                return
            
            args = message.text.split()
            if len(args) < 4:
                await message.reply_text("❌ /add <id> <chat_id> <name>")
                return
            
            sid = args[1]
            chat_id = int(args[2])
            name = " ".join(args[3:])
            
            if self.sessions.add(sid, chat_id, name):
                await message.reply_text(f"✅ Session **{sid}** added!\nChat: {name}")
            else:
                await message.reply_text(f"❌ Session {sid} already exists!")
        
        @self.bot.on_message(filters.command("del"))
        async def del_cmd(client, message):
            if message.from_user.id != self.admin:
                await message.reply_text("❌ Admin only!")
                return
            
            args = message.text.split()
            if len(args) < 2:
                await message.reply_text("❌ /del <id>")
                return
            
            sid = args[1]
            if self.sessions.delete(sid):
                await message.reply_text(f"✅ Session {sid} deleted!")
            else:
                await message.reply_text(f"❌ Session {sid} not found!")
        
        @self.bot.on_message(filters.command("list"))
        async def list_cmd(client, message):
            sessions = self.sessions.list_all()
            if not sessions:
                await message.reply_text("📭 No VC sessions!")
                return
            
            text = "📋 **VC Sessions:**\n\n"
            for sid, data in sessions.items():
                ip = data.get('ip', 'Not set')
                port = data.get('port', 'Not set')
                text += f"**{sid}** - {data['name']}\n"
                text += f"   IP: {ip} | Port: {port}\n\n"
            
            await message.reply_text(text)
        
        @self.bot.on_message(filters.command("get"))
        async def get_cmd(client, message):
            if not self.user_started:
                await message.reply_text("❌ No session set! Use /setsession first.")
                return
            
            args = message.text.split()
            if len(args) < 2:
                await message.reply_text("❌ /get <session_id>")
                return
            
            sid = args[1]
            session = self.sessions.get(sid)
            
            if not session:
                await message.reply_text(f"❌ Session {sid} not found!")
                return
            
            status = await message.reply_text(f"🔄 Extracting IP from **{sid}**...")
            
            try:
                ip, port = await self.extractor.extract(session["chat_id"])
                
                if ip and port:
                    self.sessions.update_ip(sid, ip, port)
                    await status.delete()
                    await message.reply_text(
                        f"🎯 **IP Extracted!**\n\n"
                        f"**Session:** {sid}\n"
                        f"**Chat:** {session['name']}\n"
                        f"**IP:** `{ip}`\n"
                        f"**Port:** `{port}`\n\n"
                        f"Copy: `{ip}:{port}`"
                    )
                else:
                    await status.edit_text(
                        f"❌ No IP found for **{sid}**\n\n"
                        "Make sure:\n"
                        "1. Voice chat is active in the group\n"
                        "2. Session account can access the group\n"
                        "3. Try /checksession to verify session status"
                    )
            except Exception as e:
                await status.edit_text(f"❌ Error: {e}")
        
        @self.bot.on_message(filters.command("extract"))
        async def extract_cmd(client, message):
            if not self.user_started:
                await message.reply_text("❌ No session set! Use /setsession first.")
                return
            
            args = message.text.split()
            if len(args) < 2:
                await message.reply_text("❌ /extract <chat_id>")
                return
            
            chat_id = int(args[1])
            status = await message.reply_text(f"🔄 Extracting IP from chat...")
            
            try:
                ip, port = await self.extractor.extract(chat_id)
                
                if ip and port:
                    await status.delete()
                    await message.reply_text(
                        f"🎯 **IP Extracted!**\n\n"
                        f"**Chat ID:** `{chat_id}`\n"
                        f"**IP:** `{ip}`\n"
                        f"**Port:** `{port}`\n\n"
                        f"Copy: `{ip}:{port}`"
                    )
                else:
                    await status.edit_text("❌ No IP found! Voice chat might not be active.")
            except Exception as e:
                await status.edit_text(f"❌ Error: {e}")

# ============================================
# MAIN
# ============================================
async def main():
    bot = IPBot()
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOGGER.info("🛑 Stopped by user")
    except Exception as e:
        LOGGER.error(f"Fatal error: {e}")
        sys.exit(1)
