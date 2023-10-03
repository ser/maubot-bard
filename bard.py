
import re
from bardapi import BardAsync 
from typing import Type

from mautrix.client import Client
from maubot.handlers import command, event
from maubot import Plugin, MessageEvent
from mautrix.types import TextMessageEventContent, EventType, RoomID, UserID, MessageType
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("access_key")
        helper.copy("allowed_users")
        helper.copy("name")
        helper.copy("rooms")

class BardPlugin(Plugin):

    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()
        self.name = self.config['name'] if self.config['name'] else self.client.parse_user_id(self.client.mxid)[0]
        self.rooms = self.config['rooms'] if self.config['rooms'] else None
        self.log.debug(f"Bard(TM) plugin started with bot name: {self.name}")

    @event.on(EventType.ROOM_MESSAGE)
    async def on_message(self, event: MessageEvent) -> None:

        # If there are rooms specified in config, serve only these rooms
        if self.rooms:
            if event.room_id not in self.rooms:
                self.log.debug(f"Current room {event.room_id} is not listed in {self.rooms} so I ignore it.")
                return

        # If the bot sent the message or another command was issued, just pass
        if event.sender == self.client.mxid or event.content.body.startswith('!'):
            return

        joined_members = await self.client.get_joined_members(event.room_id)

        try:
            # Check if the message contains the bot's ID or it's session one-to-one
            match_name = re.search("(^|\s)(@)?" + self.name + "([ :,.!?]|$)",
                    event.content.body, re.IGNORECASE)
            if match_name or len(joined_members) == 2:
                if event.content.msgtype == MessageType.NOTICE:
                    return # don't respond to other bot messages

                if len(self.config['allowed_users']) > 0 and event.sender not in self.config['allowed_users']:
                    await event.respond("Sorry, you're not allowed to use this functionality.")
                    return

                await event.mark_read()
                
                # Call the Bard(TM) to get a response
                await self.client.set_typing(event.room_id, timeout=99999)
                self.log.debug(f"Full event content: {event.content}")

                # Remove bot's name from query
                query = event.content.body.replace(f"{self.name}: ", "")
                self.log.debug(f"You asked: {query}")

                # Ask the question
                response = await self._call_bardapi(query)
                
                # Send the response back to the chat room
                await self.client.set_typing(event.room_id, timeout=0)
                await event.respond(f"{response}")

        except Exception as e:
            self.log.error(f"Something went wrong: {e}")
            pass

    async def _call_bardapi(self, prompt):
        bard = BardAsync(token=self.config['access_key'])
        content = await bard.get_answer(prompt)
        self.log.debug(content)
        return content['content']

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

# the end.
