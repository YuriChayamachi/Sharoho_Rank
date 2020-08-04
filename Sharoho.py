# -*- coding: utf-8 -*-
#
# 使い方:
#   23:59 JST にスクリプトを実行する。
#
# $ python Syaroho.py
#

import locale
import os
import sys
import pytz
from datetime import date, datetime, timedelta
from io import BytesIO
from os import path
from pathlib import Path
from time import sleep

import tweepy
from PIL import Image, ImageDraw, ImageFont
from requests import get as GET
from timeout_decorator import timeout

CONSUMER_KEY = os.environ["CONSUMER_KEY"]
CONSUMER_SECRET = os.environ["CONSUMER_SECRET"]
ACCESS_TOKEN = os.environ["ACCESS_TOKEN"]
ACCESS_TOKEN_SECRET = os.environ["ACCESS_TOKEN_SECRET"]
FONT_PATH = Path("./static/RictyDiminished-Regular.ttf")
IMG_PATH = Path("./static/out_img.jpg")

# StreamListener
class Listener(tweepy.StreamListener):
    def __init__(self, status_list, api):
        tweepy.StreamListener.__init__(self)
        self.status_list = status_list
        self.api = api

    def on_status(self, status):
        if status.created_at.minute > 11:
            sys.exit()
        try:
            record = [s for s in self.status_list if s.author.id == status.author.id][0]
            if record.created_at.minute != 0:
                rank = "フライング"
            else:
                rank_list = [s for s in self.status_list if s.created_at.minute == 0]
                rank = "{rank}位/{total}人".format(
                    rank=str(rank_list.index(record) + 1), total=len(rank_list)
                )
            tweet_text = (
                "@{screen_name} {name}\n".format(
                    screen_name=status.author.screen_name, name=status.author.name
                )
                + "記録: {time}\n".format(
                    time=record.created_at.strftime("%H:%M:%S.%f")[:-3]
                )
                + "順位: {rank}\n".format(rank=rank)
                + "使用クライアント: {client}".format(client=record.source)
            )
            self.api.update_status(tweet_text[:140], in_reply_to_status_id=status.id)
        except:
            self.api.update_status(
                "@{screen_name} 該当データがありませんでした。".format(
                    screen_name=status.author.screen_name
                ),
                in_reply_to_status_id=status.id,
            )
        return True


# Sharoho_bot
class Sharoho:
    def __init__(self):
        locale.setlocale(locale.LC_ALL, "")
        auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        self.api = tweepy.API(auth)
        self.screen_name = self.api.me().screen_name
        self.font_path = path.normpath(FONT_PATH)
        self.img_path = path.normpath(IMG_PATH)
        self.img = Image.new("RGB", (819, 2048), (192, 192, 192))
        self.user_rank = 0
        self.day = datetime.now(pytz.timezone("Asia/Tokyo")).date() + timedelta(days=1)
        title = self.day.strftime(
            "20%y年%m月%d日のしゃろほー集計結果(@{screen_name})".format(screen_name=self.screen_name)
        )
        self.draw_text((44, 17), 30, title)

    def draw_text(self, xy, size, text):
        font = ImageFont.truetype(self.font_path, size)
        ImageDraw.Draw(self.img).text(xy, text, font=font, fill="#000")

    def draw_status(self, status, rank):
        self.draw_text((18, 55 + self.user_rank * 26), 20, rank)
        self.img.paste(
            Image.open(
                BytesIO(GET(status.user.profile_image_url_https).content)
            ).resize((26, 26)),
            (52, 52 + self.user_rank * 26),
        )
        self.draw_text((78, 55 + self.user_rank * 26), 20, status.user.name)
        self.draw_text(
            (540, 59 + self.user_rank * 26),
            13,
            status.created_at.strftime("%H:%M:%S.")
            + "%03d"
            % round(
                datetime.fromtimestamp(
                    ((status.id >> 22) + 1288834974657) / 1000.0
                ).microsecond
                / 1000
            ),
        )
        self.draw_text((633, 59 + self.user_rank * 26), 13, "via " + status.source)
        self.user_rank += 1

    def make_img(self):
        since_date = (
            datetime.now(pytz.timezone("Asia/Tokyo")) - timedelta(days=1)
        ).date()
        print(since_date)
        self.status_list = [
            s
            for s in tweepy.Cursor(
                self.api.search,
                q=f"しゃろほー since:{since_date} until:{since_date + timedelta(days=1)}",
            ).items(200)
            if s.text == "しゃろほー"
        ]
        # 元の created_at は秒単位の精度しかないので id からミリ秒精度の時刻を付け直す
        for status in self.status_list:
            status.created_at = self.id_to_datetime(status.id) + timedelta(hours=9)
        self.status_list = sorted(self.status_list, key=lambda x: x.created_at)
        rank_list = [
            s
            for s in self.status_list
            if s.created_at.minute == 0 and s.created_at.hour == 0
        ]
        dq_list = [
            s
            for s in self.status_list
            if s.created_at.minute == 59 and s.created_at.hour == 23
        ]
        winner_list = [s for s in rank_list if s.created_at == rank_list[0].created_at]
        if len(dq_list):
            rank_list.insert(0, dq_list[-1])
        for winner in winner_list:
            if not winner.user.protected:
                self.api.retweet(winner.id)
        if len(dq_list):
            self.draw_status(rank_list[0], "DQ.")
            for i in range(1, min(len(rank_list), 76)):
                self.draw_status(rank_list[i], str(i))
        else:
            for i in range(1, min(len(rank_list), 76)):
                self.draw_status(rank_list[i - 1], str(i))
        box = (0, 0, 819, 59 + (self.user_rank + 3) * 26)
        self.img = self.img.crop(box)
        self.img.save(self.img_path, "JPEG", quality=100, optimize=True)

    @timeout(60 * 10)
    def reply_to_mention(self):
        listener = Listener(self.status_list, self.api)
        stream = tweepy.Stream(self.api.auth, listener)
        stream.filter(track=["@" + self.screen_name])

    @staticmethod
    def id_to_datetime(status_id):
        return datetime.fromtimestamp(((status_id >> 22) + 1288834974657) / 1000.0)


def main():
    bot = Sharoho()
    bot.api.update_status("しゃろほー観測中")
    sleep(120)
    bot.make_img()
    bot.api.update_with_media(
        bot.img_path, status=bot.day.strftime("20%y年%m月%d日のしゃろほー集計結果")
    )
    IMG_PATH.unlink(missing_ok=True)
    try:
        bot.reply_to_mention()
    except:
        sys.exit()


if __name__ == "__main__":
    main()
