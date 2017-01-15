import asyncio
import discord
import re
import os
import yaml

from guilty_spark import get_resource
from guilty_spark.plugin_system.data import CachedDict, plugin_file
from guilty_spark.plugin_system.plugin import Plugin

usage = '''Usage:
    !bindmeme [in/is]::[trigger]::[meme]
    !unbindmeme [trigger]
    !listmemes
    !searchmemes [trigger]
'''


class Memes(Plugin):
    def __init__(self, name, bot):
        super().__init__(
            name, bot, commands=[
                'bindmeme',
                'unbindmeme',
                'listmemes',
                'searchmemes',
            ]
        )
        self._memes = CachedDict('shitposts')
        self.server_id = 0
        self.load_memes()

    def _migrate_memes(self):
        try:
            with plugin_file('shitpost.yml') as memes:
                old_memes = yaml.load(memes)
                if not old_memes:
                    return
                for key, value in old_memes.items():
                    self._memes[key] = value
            yield from self.cache_memes()
            os.remove(get_resource('plugin_data', 'shitpost.yml'))
        except IOError:
            return

    @asyncio.coroutine
    def on_load(self):
        yield from super().on_load()
        yield from self._memes.load()
        yield from self._migrate_memes()

    @property
    def memes(self):
        try:
            return self._memes[self.server_id]
        except KeyError:
            self._memes[self.server_id] = {
                'in': {},
                'is': {},
                're': {}
            }
            return self._memes[self.server_id]

    @asyncio.coroutine
    def load_memes(self):
        yield from self._memes.load()

    @asyncio.coroutine
    def cache_memes(self):
        yield from self._memes.cache()

    @asyncio.coroutine
    def delete_meme(self, trigger: str):
        for key in self.memes:
            if trigger in self.memes[key]:
                del self.memes[key][trigger]
                yield from self.cache_memes()
                return True
        return False

    def help(self, _):
        yield from self.bot.code(
            '\n'.join([
                '-Retune the dank emitters to recognize new memes\n',
                '-' + usage.replace('\n', '\n+') + '\n',
                '-Triggers:',
                '+    in: trigger is anywhere in the message',
                '+    is: is exactly equal to trigger',
                '+    re: RegEx matching\n',
                '-I also support various tags you can use:',
                '+    <user>    | The user that triggered the message',
                '+    <channel> | The channel the message was triggered in',
                '+    <server>  | The server the message was triggered in\n',
                '-Examples:',
                '+    !bindmeme is::kthx::bai <user>',
                '+    !bindmeme re::(?i)regex::Case insensitive meme!',
             ]), language='diff')
        return

    def bind_meme(self, content: str):
        content = content.replace(self.bot.prefix + 'bindmeme', '')
        args = content.split('::')
        if len(args) != 3:
            yield from self.bot.code(usage)
            return
        meme_type, trigger, meme = [a.strip() for a in args]
        if meme_type not in ['in', 'is', 're']:
            yield from self.bot.code(usage)
            return
        if len(trigger) < 3:
            yield from self.bot.say('Trigger needs to be more then 3 characters')
            return
        if trigger.startswith(self.bot.prefix):
            yield from self.bot.say(
                'Trigger can\'t begin with "{}"'.format(self.bot.prefix))

        try:
            self.memes[meme_type][trigger] = meme
        except KeyError:
            self.memes[meme_type] = {}
            self.memes[meme_type][trigger] = meme

        yield from self.cache_memes()
        yield from self.bot.say('Meme bound')

    def unbind_meme(self, content: str):
        content = content.replace(self.bot.prefix + 'unbindmeme', '')
        arg = content.strip()

        if not arg:
            yield from self.bot.code(usage)

        deleted = yield from self.delete_meme(arg)
        if deleted:
            yield from self.bot.say('Meme unbound')
        else:
            yield from self.bot.say('You have given me stale memes')
        return

    def list_memes(self):
        memes = []
        for section, data in self.memes.items():
            memes.append('\n- {:_^25} \n'.format(section))
            for trigger, dank in data.items():
                memes.append('+ {:<25} | {}'.format(trigger, dank))

        memes = '\n'.join(memes)

        links = re.findall(r'[^<](http[^ \n]+)', memes)

        replaced = []
        for link in links:
            if link not in replaced:
                memes = memes.replace(link, '<{}>'.format(link))
            replaced.append(link)

        memes = memes.replace('```', '')

        yield from self.bot.code(memes, language='diff')

    def format_tag(self, autism: str, message: discord.Message):
        if '<user>' in autism:
            autism = autism.replace('<user>', message.author.display_name)

        if '<channel>' in autism:
            autism = autism.replace('<channel>', str(message.channel))

        if '<server>' in autism:
            autism = autism.replace('<server>', str(message.server))

        return autism

    def set_server_id(self, message: discord.Message):
        if message.server:
            self.server_id = message.server.id
        else:
            self.server_id = message.channel.id

    def get_meme(self, message: str):
        memes = self.memes
        dank = ""
        maymay = ""
        if message in memes['is']:
            dank = memes['is'][message]
            maymay = message

        else:
            for meme, autism in memes['in'].items():
                if meme in message:
                    dank = autism
                    maymay = meme

            for meme, autism in memes['re'].items():
                try:
                    if re.search(meme, message):
                        dank = autism
                        maymay = meme
                except:
                    self.delete_meme(meme)
        return dank, maymay

    def search_memes(self, content):
        content = ' '.join(content.split()[1:])
        if not content:
            yield from self.bot.code(usage)
            return

        dank, meme = self.get_meme(content)
        dank = dank.replace('```', '')
        yield from self.bot.code('+{:<25}| {}'.format(meme, dank), language='diff')

    @asyncio.coroutine
    def on_command(self, command, message: discord.Message):
        self.set_server_id(message)
        command = command[1:]
        if 'bindmeme' == command:
            yield from self.bind_meme(message.content)

        elif 'unbindmeme' == command:
            yield from self.unbind_meme(message.content)

        elif 'listmemes' == command:
            yield from self.list_memes()

        elif 'searchmemes' == command:
            yield from self.search_memes(message.content)


    @asyncio.coroutine
    def on_message(self, message: discord.Message):
        self.set_server_id(message)

        dank, _ = self.get_meme(message.content)

        if dank:
            if re.search(r'<(user|channel|server)>', dank):
                dank = self.format_tag(dank, message)

            yield from self.bot.say(dank)
