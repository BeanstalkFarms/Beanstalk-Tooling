import logging
import logging.handlers
import os
import signal

import telebot
from telebot import apihelper

from bots import util
from constants.config import *
from constants.channels import *
from constants.addresses import *

from monitors.peg_cross import PegCrossMonitor
from monitors.seasons import SeasonsMonitor
from monitors.well import WellsMonitor
from monitors.beanstalk import BeanstalkMonitor
from monitors.market import MarketMonitor
from monitors.barn import BarnRaiseMonitor

class TelegramBot(object):
    def __init__(self, token, prod=False, dry_run=None):
        if prod:
            self._chat_id = BS_TELE_CHAT_ID_PRODUCTION
            logging.info("Configured as a production instance.")
        else:
            self._chat_id = BS_TELE_CHAT_ID_STAGING
            logging.info("Configured as a staging instance.")

        apihelper.SESSION_TIME_TO_LIVE = 5 * 60
        self.tele_bot = telebot.TeleBot(token, parse_mode="Markdown")

        self.peg_cross_monitor = PegCrossMonitor(self.send_msg, prod=prod)
        self.peg_cross_monitor.start()

        self.sunrise_monitor = SeasonsMonitor(self.send_msg, prod=prod, dry_run=dry_run)
        self.sunrise_monitor.start()

        self.wells_monitor = WellsMonitor(
            self.send_msg, WHITELISTED_WELLS, bean_reporting=True, prod=prod, dry_run=dry_run
        )
        self.wells_monitor.start()

        self.beanstalk_monitor = BeanstalkMonitor(self.send_msg, prod=prod, dry_run=dry_run)
        self.beanstalk_monitor.start()

        self.market_monitor = MarketMonitor(self.send_msg, prod=prod, dry_run=dry_run)
        self.market_monitor.start()

        self.barn_raise_monitor = BarnRaiseMonitor(self.send_msg, prod=prod, dry_run=dry_run)
        self.barn_raise_monitor.start()

    def send_msg(self, msg):
        # Ignore empty messages.
        if not msg:
            return
        # Remove URL pointy brackets used by md formatting to suppress link previews.
        msg_split = msg.rsplit("<http", 1)
        if len(msg_split) == 2:
            msg = msg_split[0] + "http" + msg_split[1].replace(">", "")
        # Replace all brackets with double bracket to avoid markdown formatting.
        # Note that Telegram handles brackets differently when they are in italics.
        # msg = msg.replace("[", "[[").replace("]", "]]")
        # Note that Telegram uses pseudo md style and must use '_' for italics, rather than '*'.
        self.tele_bot.send_message(chat_id=self._chat_id, text=msg, disable_web_page_preview=True)
        logging.info(f"Message sent:\n{msg}\n")

    def stop(self):
        self.peg_cross_monitor.stop()
        self.sunrise_monitor.stop()
        self.wells_monitor.stop()
        self.beanstalk_monitor.stop()
        self.market_monitor.stop()
        self.barn_raise_monitor.stop()


if __name__ == "__main__":
    """Quick test and demonstrate functionality."""
    logging.basicConfig(
        format=f"Telegram Bot : {LOGGING_FORMAT_STR_SUFFIX}",
        level=logging.INFO,
        handlers=[
            logging.handlers.RotatingFileHandler(
                "logs/telegram_bot.log", maxBytes=ONE_HUNDRED_MEGABYTES, backupCount=1
            ),
            logging.StreamHandler(),
        ],
    )
    signal.signal(signal.SIGTERM, util.handle_sigterm)

    util.configure_main_thread_exception_logging()

    token = os.environ["TELEGRAM_BS_BOT_TOKEN"]
    prod = os.environ["IS_PROD"].lower() == "true"
    dry_run = os.environ.get("DRY_RUN")
    if dry_run:
        dry_run = dry_run.split(',')

    bot = TelegramBot(token=token, prod=prod, dry_run=dry_run)
    try:
        bot.tele_bot.infinity_polling()
    except (KeyboardInterrupt, SystemExit):
        pass
    bot.stop()
