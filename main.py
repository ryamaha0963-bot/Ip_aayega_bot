"""
Simple IP Grabber Bot - Railway Working Version
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

# Setup logging
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
SESSION_STRING = os.getenv("SESSION_STRING", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

if not all([API_ID, API_HASH, BOT_TOKEN, ADMIN_ID]):
    LOGGER.error("❌ Missing environment variables!")
    sys.exit(1)

# ============================================
# SESSION MANAGER
# ============================================
class SessionManager:
    def __init__(self):
        self.file = "sessions.json"
        self.data = self._load()
    
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
# IP EXTRACTOR
# ============================================
class IPExtractor:
    def __init__(self, client):
        self.client = client
    
    async def extract(self, chat_id: int) -> Tuple[Optional[str], Optional[int]]:
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
        
        if SESSION_STRING:
            self.user = Client(
                "ip_user",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=SESSION_STRING
            )
        else:
            self.user = self.bot
        
        self.sessions = SessionManager()
        self.extractor = IPExtractor(self.user)
        self.admin = ADMIN_ID
    
    async def start(self):
        LOGGER.info("🚀 Starting IP Grabber Bot...")
        
        await self.bot.start()
        LOGGER.info("✅ Bot started")
        
        if SESSION_STRING:
            await self.user.start()
            LOGGER.info("✅ User client started")
        
        self._register_handlers()
        
        try:
            await self.bot.send_message(
                self.admin,
                "✅ **IP Grabber Bot Started!**\n\n"
                f"Sessions: {len(self.sessions.list_all())}\n"
                "Use /help for commands."
            )
        except:
            pass
        
        LOGGER.info("✅ Bot is running!")
        await idle()
        
        await self.bot.stop()
        if SESSION_STRING:
            await self.user.stop()
        LOGGER.info("✅ Bot stopped")
    
    def _register_handlers(self):
        @self.bot.on_message(filters.command("start"))
        async def start_cmd(client, message):
            await message.reply_text(
                "🔍 **IP Grabber Bot**\n\n"
                "**Commands:**\n"
                "/start - Show this\n"
                "/help - Help\n"
                "/add <id> <chat_id> <name> - Add session\n"
                "/del <id> - Delete session\n"
                "/list - List all sessions\n"
                "/get <id> - Extract IP\n"
                "/extract <chat_id> - Direct extract\n\n"
                "**Example:**\n"
                "/add S10 -1003329480093 Damon Holiday"
            )
        
        @self.bot.on_message(filters.command("help"))
        async def help_cmd(client, message):
            await start_cmd(client, message)
        
        @self.bot.on_message(filters.command("add"))
        async def add_cmd(client, message):
            if message.from_user.id != self.admin:
                await message.reply_text("❌ Admin only!")
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
                await message.reply_text("📭 No sessions!")
                return
            
            text = "📋 **Sessions:**\n\n"
            for sid, data in sessions.items():
                ip = data.get('ip', 'Not set')
                port = data.get('port', 'Not set')
                text += f"**{sid}** - {data['name']}\n"
                text += f"   IP: {ip} | Port: {port}\n\n"
            
            await message.reply_text(text)
        
        @self.bot.on_message(filters.command("get"))
        async def get_cmd(client, message):
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
                        "Make sure voice chat is active!"
                    )
            except Exception as e:
                await status.edit_text(f"❌ Error: {e}")
        
        @self.bot.on_message(filters.command("extract"))
        async def extract_cmd(client, message):
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
