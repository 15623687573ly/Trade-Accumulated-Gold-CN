"""微信推送：优先 PushPlus（免费额度大），其次 Server酱（免费版每天条数很少）。都没配置时只打日志。"""

from __future__ import annotations

import logging

import requests

from .config import Settings

log = logging.getLogger("monitor.notify")

PUSHPLUS_URL = "https://www.pushplus.plus/send"
SERVERCHAN_URL = "https://sctapi.ftqq.com/{key}.send"


class Notifier:
    def __init__(self, settings: Settings, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run

    @property
    def channel(self) -> str:
        if self.dry_run:
            return "dry-run"
        if self.settings.pushplus_token:
            return "pushplus"
        if self.settings.serverchan_sendkey:
            return "serverchan"
        return "log-only"

    def send(self, title: str, body_markdown: str) -> bool:
        """返回是否真正送达微信。"""
        title = title[:32]
        channel = self.channel
        if channel in ("dry-run", "log-only"):
            log.info("[%s] %s\n%s", channel, title, body_markdown)
            return False
        try:
            if channel == "pushplus":
                resp = requests.post(
                    PUSHPLUS_URL,
                    json={"token": self.settings.pushplus_token, "title": title,
                          "content": body_markdown, "template": "markdown"},
                    timeout=15,
                )
                ok = resp.ok and resp.json().get("code") == 200
            else:
                resp = requests.post(
                    SERVERCHAN_URL.format(key=self.settings.serverchan_sendkey),
                    data={"title": title, "desp": body_markdown},
                    timeout=15,
                )
                ok = resp.ok and resp.json().get("code") == 0
            if not ok:
                log.warning("推送失败 [%s]: %s", channel, resp.text[:300])
            return ok
        except Exception as exc:
            log.warning("推送异常 [%s]: %s", channel, exc)
            return False
