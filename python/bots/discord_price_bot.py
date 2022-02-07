import logging
import logging.handlers
import os
import signal
import subprocess

import discord
from discord.ext import tasks, commands

from bots import util

BEANSTALK_GUILD_ID = 880413392916054098

class DiscordPriceClient(discord.ext.commands.Bot):

    def __init__(self, prod=False):
        super().__init__(command_prefix=commands.when_mentioned_or("!"))
        # There is only production for this bot.
        logging.info('Configured as a production instance.')

        self.nickname = ''
        self.status_text = ''
        self.price_monitor = util.PreviewMonitor(
            self.set_nickname, self.set_status)
        self.price_monitor.start()

        # Ignore exceptions of this type and retry. Note that no logs will be generated.
        self._update_naming.add_exception_type(discord.errors.DiscordServerError)
        # Start the price display task in the background.
        self._update_naming.start()

    def stop(self):
        self.price_monitor.stop()

    def set_nickname(self, text):
        """Set bot server nickname."""
        self.nickname = text

    def set_status(self, text):
        """Set bot custom status text."""
        self.status_text = text

    async def on_ready(self):
        # Log the commit of this run.
        logging.info('Git commit is ' + subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=os.path.dirname(os.path.realpath(__file__))
            ).decode('ascii').strip())

        self.user_id = self.user.id
        self.beanstalk_guild = self.get_guild(BEANSTALK_GUILD_ID)

    @tasks.loop(seconds=0.1, reconnect=True)
    async def _update_naming(self):
        if self.nickname:
            # Note(funderberker): Is this rate limited?
            await self.beanstalk_guild.me.edit(nick=self.nickname)
            logging.info(f'Bot nickname changed to {self.nickname}')
            self.nickname = ''
        if self.status_text:
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,
                                                                 name=self.status_text))
            logging.info(f'Bot status changed to {self.status_text}')
            self.status_text = ''

    @_update_naming.before_loop
    async def before__update_nickname_loop(self):
        """Wait until the bot logs in."""
        await self.wait_until_ready()

if __name__ == '__main__':
    logging.basicConfig(format='Discord Price Bot : %(levelname)s : %(asctime)s : %(message)s',
                        level=logging.INFO, handlers=[
                            logging.handlers.RotatingFileHandler(
                                "discord_price_bot.log", maxBytes=util.FIVE_HUNDRED_MEGABYTES/5),
                            logging.StreamHandler()])
    signal.signal(signal.SIGTERM, util.handle_sigterm)

    util.configure_main_thread_exception_logging()

    price_bot_token= os.environ["DISCORD_PRICE_BOT_TOKEN_PROD"]

    discord_price_client = DiscordPriceClient()

    try:
        discord_price_client.run(price_bot_token)
    except (KeyboardInterrupt, SystemExit):
        pass
    # Note that discord bot cannot send shutting down messages in its channel, due to lib impl.
    discord_price_client.stop()
