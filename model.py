import time
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)


class Challenge:
    def __init__(self, c_info):
        self.id = c_info["id"]
        self.rated = c_info["rated"]
        self.variant = c_info["variant"]["key"]
        self.perf_name = c_info["perf"]["name"]
        self.speed = c_info["speed"]
        self.increment = c_info.get("timeControl", {}).get("increment", -1)
        self.base = c_info.get("timeControl", {}).get("limit", -1)
        self.challenger = c_info.get("challenger", {})
        self.challenger_title = self.challenger.get("title")
        self.challenger_is_bot = self.challenger_title == "BOT"
        self.challenger_master_title = self.challenger_title if not self.challenger_is_bot else None
        self.challenger_name = self.challenger.get("name", "Anonymous")
        self.challenger_rating_int = self.challenger.get("rating", 0)
        self.challenger_rating = self.challenger_rating_int or "?"

    def is_supported_variant(self, challenge_cfg):
        return self.variant in challenge_cfg["variants"]

    def is_supported_time_control(self, challenge_cfg):
        speeds = challenge_cfg["time_controls"]
        increment_max = challenge_cfg.get("max_increment", 180)
        increment_min = challenge_cfg.get("min_increment", 0)
        base_max = challenge_cfg.get("max_base", 315360000)
        base_min = challenge_cfg.get("min_base", 0)

        if self.increment < 0:
            return self.speed in speeds

        return (self.speed in speeds
                and increment_min <= self.increment <= increment_max
                and base_min <= self.base <= base_max)

    def is_supported_mode(self, challenge_cfg):
        return ("rated" if self.rated else "casual") in challenge_cfg["modes"]

    def is_supported(self, config):
        try:
            if not config.get("accept_bot", False) and self.challenger_is_bot:
                return False, "noBot"

            if config.get("only_bot", False) and not self.challenger_is_bot:
                return False, "onlyBot"

            if not self.is_supported_time_control(config):
                return False, "timeControl"

            if not self.is_supported_variant(config):
                return False, "variant"

            if not self.is_supported_mode(config):
                return False, ("casual" if self.rated else "rated")

            return True, None

        except Exception:
            logger.exception("Error while checking challenge:")
            return False, "generic"

    def score(self):
        rated_bonus = 200 if self.rated else 0
        titled_bonus = 200 if self.challenger_master_title else 0
        return self.challenger_rating_int + rated_bonus + titled_bonus

    def mode(self):
        return "rated" if self.rated else "casual"

    def challenger_full_name(self):
        return f'{self.challenger_title or ""} {self.challenger_name}'.strip()

    def __str__(self):
        return f"{self.perf_name} {self.mode()} challenge from {self.challenger_full_name()}({self.challenger_rating})"

    def __repr__(self):
        return self.__str__()


class Game:
    def __init__(self, json, username, base_url, abort_time):
        self.username = username
        self.id = json.get("id")
        self.speed = json.get("speed")
        clock = json.get("clock") or {}
        ten_years_in_ms = 1000 * 3600 * 24 * 365 * 10
        self.clock_initial = clock.get("initial", ten_years_in_ms)
        self.clock_increment = clock.get("increment", 0)
        self.perf_name = json.get("perf", {}).get("name", "{perf?}")
        self.variant_name = json.get("variant")["name"]
        self.white = Player(json.get("white"))
        self.black = Player(json.get("black"))
        self.initial_fen = json.get("initialFen")
        self.state = json.get("state")
        self.is_white = bool(self.white.name and self.white.name.lower() == username.lower())
        self.my_color = "white" if self.is_white else "black"
        self.opponent_color = "black" if self.is_white else "white"
        self.me = self.white if self.is_white else self.black
        self.opponent = self.black if self.is_white else self.white
        self.base_url = base_url
        self.white_starts = self.initial_fen == "startpos" or self.initial_fen[0] == "W"
        self.abort_at = time.time() + abort_time
        self.terminate_at = time.time() + (self.clock_initial + self.clock_increment) / 1000 + abort_time + 60
        self.disconnect_at = time.time()

    def url(self):
        return urljoin(self.base_url, f"{self.id}/{self.my_color}")

    def is_abortable(self):
        return len(self.state["moves"]) < 6

    def ping(self, abort_in, terminate_in, disconnect_in):
        if self.is_abortable():
            self.abort_at = time.time() + abort_in
        self.terminate_at = time.time() + terminate_in
        self.disconnect_at = time.time() + disconnect_in

    def should_abort_now(self):
        return self.is_abortable() and time.time() > self.abort_at

    def should_terminate_now(self):
        return time.time() > self.terminate_at

    def should_disconnect_now(self):
        return time.time() > self.disconnect_at

    def my_remaining_seconds(self):
        return (self.state["wtime"] if self.is_white else self.state["btime"]) / 1000

    def __str__(self):
        return f"{self.url()} {self.perf_name} vs {self.opponent.__str__()}"

    def __repr__(self):
        return self.__str__()


class Player:
    def __init__(self, json):
        self.id = json.get("id")
        self.name = json.get("name")
        self.title = json.get("title")
        self.rating = json.get("rating")
        self.provisional = json.get("provisional")
        self.aiLevel = json.get("aiLevel")

    def __str__(self):
        if self.aiLevel:
            return f"AI level {self.aiLevel}"
        else:
            rating = f'{self.rating}{"?" if self.provisional else ""}'
            return f'{self.title or ""} {self.name}({rating})'.strip()

    def __repr__(self):
        return self.__str__()
