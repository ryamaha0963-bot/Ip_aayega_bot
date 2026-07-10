"""
ULTIMATE IP GRABBER BOT - Telethon Version
Session add, VC join, IP extract - Sab kuch!
"""

import asyncio
import json
import logging
import os
import re
import sys
from typing import Optional, Tuple

from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.functions.phone import GetGroupCallRequest, JoinGroupCallRequest, LeaveGroupCallRequest
from telethon.tl.types import InputGroupCall, InputPeerChannel, InputPeerChat, DataJSON
from dotenv import load_dotenv

load_dotenv()

# ============================================
# LOGGING
# ============================================
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

if not all([API_ID, API_HASH, BOT_TOKEN, ADMIN_ID]):
    LOGGER.error("❌ Missing environment variables!")
    sys.exit(1)

# ============================================
# SESSION MANAGER
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
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r') as f:
                    return f.read().strip()
            except:
                return ""
        return ""
    
    def _save_session_string(self, session_str):
        with open(self.session_file, 'w') as f:
            f.write(session_str)
        self.session_string = session_str
    
    def get_session_string(self):
        return self.session_string
    
    def set_session_string(self, session_str):
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
# IP GRABBER - Telethon Version
# ============================================
class IPGrabber:
    def __init__(self):
        self.client = None
        self.session_string = None
        self.is_connected = False
    
    async def init_client(self, session_string):
        """Initialize user client with Telethon"""
        if self.client:
            try:
                await self.client.disconnect()
            except:
                pass
            self.client = None
            self.is_connected = False
        
        if not session_string:
            return False
        
        try:
            self.session_string = session_string
            self.client = TelegramClient(
                StringSession(session_string),
                API_ID,
                API_HASH
            )
            await self.client.connect()
            
            # Check if session is valid
            me = await self.client.get_me()
            self.is_connected = True
            
            LOGGER.info(f"✅ Telethon client started: {me.first_name}")
            return True
            
        except Exception as e:
            LOGGER.error(f"❌ Failed to start client: {e}")
            return False
    
    async def extract_ip(self, chat_id: int) -> Tuple[Optional[str], Optional[int]]:
        """Extract IP from voice chat using Telethon"""
        if not self.is_connected or not self.client:
            LOGGER.error("❌ Client not connected!")
            return None, None
        
        try:
            LOGGER.info(f"🔍 Extracting IP from chat: {chat_id}")
            
            # Resolve peer
            entity = await self.client.get_entity(chat_id)
            LOGGER.info(f"✅ Entity resolved: {entity.title if hasattr(entity, 'title') else entity}")
            
            # Get full chat
            if hasattr(entity, 'channel_id'):  # Channel/Supergroup
                full = await self.client(GetFullChannelRequest(
                    channel=entity
                ))
                chat_full = full.full_chat
            else:  # Basic group
                full = await self.client(GetFullChatRequest(
                    chat_id=entity.id
                ))
                chat_full = full.full_chat
            
            # Check for active call
            call = getattr(chat_full, 'call', None)
            if not call:
                LOGGER.warning("⚠️ No active voice call found!")
                return None, None
            
            LOGGER.info(f"✅ Voice call found: {call.id}")
            
            # Get group call details
            try:
                group_call = await self.client(GetGroupCallRequest(
                    call=InputGroupCall(
                        id=call.id,
                        access_hash=call.access_hash
                    ),
                    limit=100
                ))
            except Exception as e:
                LOGGER.error(f"❌ Failed to get group call: {e}")
                return None, None
            
            call_obj = group_call.call
            
            # Get params
            params = getattr(call_obj, 'params', None)
            if params and hasattr(params, 'data'):
                try:
                    params_data = json.loads(params.data)
                    LOGGER.info(f"📦 Params: {json.dumps(params_data, indent=2)[:500]}")
                    
                    # Extract IP from endpoints
                    endpoints = params_data.get('endpoints', [])
                    for endpoint in endpoints:
                        if ':' in endpoint:
                            parts = endpoint.rsplit(':', 1)
                            if len(parts) == 2:
                                ip, port_str = parts
                                try:
                                    port = int(port_str)
                                    if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                                        LOGGER.info(f"✅ IP found in endpoints: {ip}:{port}")
                                        return ip, port
                                except:
                                    continue
                    
                    # Extract IP from servers
                    servers = params_data.get('servers', [])
                    for server in servers:
                        if isinstance(server, dict):
                            ip = server.get('ip')
                            port = server.get('port', 0)
                            if ip and port:
                                LOGGER.info(f"✅ IP found in servers: {ip}:{port}")
                                return ip, port
                    
                    # Extract IP from other fields
                    for key in ['ip', 'host', 'address', 'connection_ip']:
                        ip = params_data.get(key)
                        if ip and re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                            port = params_data.get('port', 0)
                            LOGGER.info(f"✅ IP found in {key}: {ip}:{port}")
                            return ip, port
                            
                except json.JSONDecodeError:
                    LOGGER.warning("⚠️ Failed to parse params JSON")
            
            # Try to get IP from participants
            try:
                participants = getattr(group_call, 'participants', [])
                for participant in participants:
                    if hasattr(participant, 'video'):
                        video = participant.video
                        if video and hasattr(video, 'endpoint'):
                            endpoint = video.endpoint
                            if endpoint and ':' in endpoint:
                                parts = endpoint.rsplit(':', 1)
                                if len(parts) == 2:
                                    ip, port_str = parts
                                    try:
                                        port = int(port_str)
                                        if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                                            LOGGER.info(f"✅ IP found in participant: {ip}:{port}")
                                            return ip, port
                                    except:
                                        continue
            except:
                pass
            
            LOGGER.warning("⚠️ No IP found in any source")
            return None, None
            
        except Exception as e:
            LOGGER.error(f"❌ Error extracting IP: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    async def join_and_extract(self, chat_id: int) -> Tuple[Optional[str], Optional[int]]:
        """Join voice chat and extract IP"""
        if not self.is_connected or not self.client:
            return None, None
        
        try:
            entity = await self.client.get_entity(chat_id)
            
            # Get call
            if hasattr(entity, 'channel_id'):
                full = await self.client(GetFullChannelRequest(channel=entity))
            else:
                full = await self.client(GetFullChatRequest(chat_id=entity.id))
            
            call = getattr(full.full_chat, 'call', None)
            if not call:
                return None, None
            
            # Get me
            me = await self.client.get_me()
            
            # Join call
            try:
                LOGGER.info("🔊 Joining voice call...")
                await self.client(JoinGroupCallRequest(
                    call=InputGroupCall(id=call.id, access_hash=call.access_hash),
                    join_as=me,
                    params=call.params,
                    muted=True,
                    video_stopped=True
                ))
                LOGGER.info("✅ Joined voice call")
                await asyncio.sleep(2)
            except Exception as e:
                LOGGER.info(f"⚠️ Join call: {e}")
            
            # Extract IP
            ip, port = await self.extract_ip(chat_id)
            
            # Leave call
            try:
                LOGGER.info("🔇 Leaving voice call...")
                await self.client(LeaveGroupCallRequest(
                    call=InputGroupCall(id=call.id, access_hash=call.access_hash),
                    source=0
                ))
                LOGGER.info("✅ Left voice call")
            except:
                pass
            
            return ip, port
            
        except Exception as e:
            LOGGER.error(f"❌ Join extract error: {e}")
            return None, None

# ============================================
# BOT - Telethon
# ============================================
class IPBot:
    def __init__(self):
        self.bot = TelegramClient(
            'ip_bot',
            API_ID,
            API_HASH
        ).start(bot_token=BOT_TOKEN)
        
        self.sessions = SessionManager()
        self.grabber = IPGrabber()
        self.admin = ADMIN_ID
        self.user_connected = False
    
    async def start(self):
        LOGGER.info("🚀 Starting IP Grabber Bot...")
        
        await self.bot.start()
        LOGGER.info("✅ Bot started")
        
        # Load saved session
        saved_session = self.sessions.get_session_string()
        if saved_session:
            LOGGER.info("🔄 Loading saved session...")
            success = await self.grabber.init_client(saved_session)
            if success:
                self.user_connected = True
                LOGGER.info("✅ User session loaded")
        
        # Register handlers
        self._register_handlers()
        
        # Send startup message
        try:
            await self.bot.send_message(
                self.admin,
                f"✅ **IP Grabber Bot Started!**\n\n"
                f"User Client: {'✅ Active' if self.user_connected else '❌ Not Set'}\n"
                f"Sessions: {len(self.sessions.list_all())}\n\n"
                "Use /setsession to add your session string"
            )
        except:
            pass
        
        LOGGER.info("✅ Bot is running!")
        await self.bot.run_until_disconnected()
    
    def _register_handlers(self):
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_cmd(event):
            status = '✅ Active' if self.user_connected else '❌ Not Set'
            await event.reply(
                f"🔍 **IP Grabber Bot**\n\n"
                f"**User Client:** {status}\n\n"
                f"**Commands:**\n"
                f"/setsession <session> - Add session account\n"
                f"/checksession - Check session status\n"
                f"/add <id> <chat_id> <name> - Add VC session\n"
                f"/del <id> - Delete VC session\n"
                f"/list - List all VC sessions\n"
                f"/get <id> - Extract IP\n"
                f"/extract <chat_id> - Direct extract"
            )
        
        @self.bot.on(events.NewMessage(pattern='/help'))
        async def help_cmd(event):
            await start_cmd(event)
        
        # ============ SET SESSION ============
        @self.bot.on(events.NewMessage(pattern='/setsession(?:\\s+(.*))?'))
        async def setsession_cmd(event):
            if event.sender_id != self.admin:
                await event.reply("❌ Admin only!")
                return
            
            args = event.pattern_match.group(1)
            if not args:
                await event.reply(
                    "❌ **Usage:** /setsession <session_string>\n\n"
                    "**How to get session string:**\n"
                    "```python\n"
                    "from telethon import TelegramClient\n"
                    "from telethon.sessions import StringSession\n\n"
                    "client = TelegramClient(StringSession(), API_ID, API_HASH)\n"
                    "client.start()\n"
                    "print(client.session.save())\n"
                    "```"
                )
                return
            
            session_str = args.strip()
            if len(session_str) < 20:
                await event.reply("❌ Invalid session string!")
                return
            
            status = await event.reply("🔄 Testing session...")
            
            try:
                success = await self.grabber.init_client(session_str)
                
                if success:
                    self.sessions.set_session_string(session_str)
                    self.user_connected = True
                    
                    me = await self.grabber.client.get_me()
                    await status.edit(
                        f"✅ **Session Added!**\n\n"
                        f"Account: {me.first_name}\n"
                        f"Username: @{me.username or 'N/A'}\n"
                        f"Phone: {me.phone or 'N/A'}\n\n"
                        f"Now use /add to add VC sessions!"
                    )
                else:
                    await status.edit("❌ Invalid session string!")
            except Exception as e:
                await status.edit(f"❌ Error: {e}")
        
        # ============ CHECK SESSION ============
        @self.bot.on(events.NewMessage(pattern='/checksession'))
        async def checksession_cmd(event):
            if event.sender_id != self.admin:
                await event.reply("❌ Admin only!")
                return
            
            if not self.user_connected or not self.grabber.client:
                await event.reply("❌ No session connected! Use /setsession")
                return
            
            try:
                me = await self.grabber.client.get_me()
                await event.reply(
                    f"✅ **Session Active!**\n\n"
                    f"Account: {me.first_name}\n"
                    f"Username: @{me.username or 'N/A'}\n"
                    f"Phone: {me.phone or 'N/A'}"
                )
            except:
                await event.reply("❌ Session expired! Use /setsession again")
                self.user_connected = False
        
        # ============ ADD SESSION ============
        @self.bot.on(events.NewMessage(pattern='/add(?:\\s+(\\S+)\\s+(\\S+)\\s+(.*))?'))
        async def add_cmd(event):
            if event.sender_id != self.admin:
                await event.reply("❌ Admin only!")
                return
            
            if not self.user_connected:
                await event.reply("❌ No user session! Use /setsession first")
                return
            
            args = event.pattern_match.groups()
            if not args or not all(args):
                await event.reply("❌ /add <id> <chat_id> <name>\nExample: /add S1 -1001234567890 MyGroup")
                return
            
            sid, chat_id_str, name = args
            try:
                chat_id = int(chat_id_str)
            except:
                await event.reply("❌ Invalid chat_id! Must be number")
                return
            
            if self.sessions.add(sid, chat_id, name):
                await event.reply(f"✅ Session **{sid}** added!\nChat: {name}")
            else:
                await event.reply(f"❌ Session {sid} already exists!")
        
        # ============ DELETE SESSION ============
        @self.bot.on(events.NewMessage(pattern='/del(?:\\s+(\\S+))?'))
        async def del_cmd(event):
            if event.sender_id != self.admin:
                await event.reply("❌ Admin only!")
                return
            
            args = event.pattern_match.group(1)
            if not args:
                await event.reply("❌ /del <id>")
                return
            
            if self.sessions.delete(args):
                await event.reply(f"✅ Session {args} deleted!")
            else:
                await event.reply(f"❌ Session {args} not found!")
        
        # ============ LIST SESSIONS ============
        @self.bot.on(events.NewMessage(pattern='/list'))
        async def list_cmd(event):
            sessions = self.sessions.list_all()
            if not sessions:
                await event.reply("📭 No sessions!")
                return
            
            text = "📋 **VC Sessions:**\n\n"
            for sid, data in sessions.items():
                ip = data.get('ip', 'Not set')
                port = data.get('port', 'Not set')
                text += f"**{sid}** - {data['name']}\n"
                text += f"   IP: {ip} | Port: {port}\n\n"
            
            await event.reply(text)
        
        # ============ GET IP ============
        @self.bot.on(events.NewMessage(pattern='/get(?:\\s+(\\S+))?'))
        async def get_cmd(event):
            if not self.user_connected:
                await event.reply("❌ No user session! Use /setsession first")
                return
            
            args = event.pattern_match.group(1)
            if not args:
                await event.reply("❌ /get <session_id>")
                return
            
            session = self.sessions.get(args)
            if not session:
                await event.reply(f"❌ Session {args} not found!")
                return
            
            status = await event.reply(f"🔄 Extracting IP from **{args}**...")
            
            try:
                # Try to join and extract
                ip, port = await self.grabber.join_and_extract(session["chat_id"])
                
                if ip and port:
                    self.sessions.update_ip(args, ip, port)
                    await status.edit(
                        f"🎯 **IP Extracted!**\n\n"
                        f"**Session:** {args}\n"
                        f"**Chat:** {session['name']}\n"
                        f"**IP:** `{ip}`\n"
                        f"**Port:** `{port}`\n\n"
                        f"Copy: `{ip}:{port}`"
                    )
                else:
                    await status.edit(
                        f"❌ **No IP found for {args}**\n\n"
                        f"Make sure:\n"
                        f"1. Voice chat is active\n"
                        f"2. Session account can access the group\n"
                        f"3. Try /checksession to verify session"
                    )
            except Exception as e:
                await status.edit(f"❌ Error: {e}")
        
        # ============ DIRECT EXTRACT ============
        @self.bot.on(events.NewMessage(pattern='/extract(?:\\s+(\\S+))?'))
        async def extract_cmd(event):
            if not self.user_connected:
                await event.reply("❌ No user session! Use /setsession first")
                return
            
            args = event.pattern_match.group(1)
            if not args:
                await event.reply("❌ /extract <chat_id>")
                return
            
            try:
                chat_id = int(args)
            except:
                await event.reply("❌ Invalid chat_id!")
                return
            
            status = await event.reply(f"🔄 Extracting IP from chat...")
            
            try:
                ip, port = await self.grabber.join_and_extract(chat_id)
                
                if ip and port:
                    await status.edit(
                        f"🎯 **IP Extracted!**\n\n"
                        f"**Chat ID:** `{chat_id}`\n"
                        f"**IP:** `{ip}`\n"
                        f"**Port:** `{port}`\n\n"
                        f"Copy: `{ip}:{port}`"
                    )
                else:
                    await status.edit("❌ No IP found! Voice chat might not be active.")
            except Exception as e:
                await status.edit(f"❌ Error: {e}")

# ============================================
# MAIN
# ============================================
from telethon.sessions import StringSession

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
