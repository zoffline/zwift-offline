# Python 3 only (asyncio)

import asyncio
import json
import os
import threading
import time

from configparser import ConfigParser
from urllib import request

import discord
import requests

import zwift_offline


class DiscordBot(discord.Client):
    # TODO: this should be part of __init__()
    def set_vars(self, channel, welcome_msg, help_msg):
        self.channel = channel
        self.welcome_msg = welcome_msg
        self.help_msg = help_msg

    async def on_ready(self):
        self.channel = self.get_channel(self.channel)

    async def on_member_join(self, member):
        if self.welcome_msg:
            await self.channel.send('%s\n%s' % (member.mention, self.welcome_msg))

    async def on_message(self, message):
        if message.author.id == self.user.id:
            return
        if message.content == '!online':
            await message.channel.send('%s riders online' % len(zwift_offline.online))
        elif message.content == '!help' and self.help_msg:
            await message.channel.send(self.help_msg)
        elif message.content == '!ping':
            await message.channel.send('pong')
        elif message.channel == self.channel and not message.author.bot and not message.content.startswith('!'):
            zwift_offline.send_message_to_all_online(message.content, message.author.name)


class DiscordThread(threading.Thread):
    def __init__(self, config_file):
        threading.Thread.__init__(self)
        if not os.path.isfile(config_file):
            raise Exception("DiscordThread invoked without a configuration file")

        self.CONFIG = ConfigParser()
        SECTION = 'discord'
        self.CONFIG.read(config_file)
        self.token = self.CONFIG.get(SECTION, 'token')
        self.webhook = self.CONFIG.get(SECTION, 'webhook')
        self.channel = self.CONFIG.getint(SECTION, 'channel')
        self.welcome_msg = self.CONFIG.get(SECTION, 'welcome_message')
        self.help_msg = self.CONFIG.get(SECTION, 'help_message')

        self.intents = discord.Intents.default()
        self.intents.members = True
        self.intents.message_content = True
        self.loop = asyncio.get_event_loop()
        self.start()

    async def starter(self):
        self.discord_bot = DiscordBot(intents=self.intents)
        self.discord_bot.set_vars(self.channel, self.welcome_msg, self.help_msg)
        await self.discord_bot.start(self.token)

    def run(self):
        try:
            self.loop.run_until_complete(self.starter())
        except BaseException:
            time.sleep(5)

    def send_message(self, message, sender_id=None):
        if sender_id is not None:
            profile = zwift_offline.get_partial_profile(sender_id)
            sender = profile.first_name + ' ' + profile.last_name
        else:
            sender = 'Server'
        data = {}
        data["content"] = message
        data["username"] = sender
        requests.post(self.webhook, data=json.dumps(data), headers={"Content-Type": "application/json"})

    def change_presence(self, n):
        if n > 0:
            activity = discord.Game(name=f"{n} rider{'s'[:n>1]} online")
        else:
            activity = None
        asyncio.run(self.discord_bot.change_presence(activity=activity))
