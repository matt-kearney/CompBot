from util import debug
from datetime import datetime
from collections import deque

class ClashGame:
    def __init__(self):
        self.my_team = {
            "ADC": None,
            "MID": None,
            "TOP": None,
            "JUN": None,
            "SUP": None,
        }
        self.enemy_team = {
            "ADC": None,
            "MID": None,
            "TOP": None,
            "JUN": None,
            "SUP": None,
        }
        self.bans = []
        self.my_team_first_pick = False

    def my_team_add(self, champion, role):
        self.my_team[role] = champion

    def enemy_team_add(self, champion, role):
        self.enemy_team[role] = champion

    def add_ban(self, champion):
        self.bans.append(champion)

    def swap_enemy_lane(self, role_1, role_2):
        self.enemy_team[role_1], self.enemy_team[role_2] = self.enemy_team[role_2], self.enemy_team[role_1]

    def swap_my_lane(self, role_1, role_2):
        self.my_team[role_1], self.my_team[role_2] = self.my_team[role_2], self.my_team[role_1]

    def set_first_pick(self, fp):
        self.my_team_first_pick = fp


class User:
    def __init__(self, username):
        self.username = username
        self.clash_game = ClashGame()
        self.clash_game_active = True
        self.last_time = datetime.now()
        self.expected_query = ""
        self.query_list = deque()

    def update_time(self):
        self.last_time = datetime.now()

    def init_query_list(self, fp):
        for a in range(0, 6):
            self.query_list.append("=ban")
        if fp:
            self.query_list += ["=team", "=enemy", "=enemy", "=team", "=team", "=enemy"]
        else:
            self.query_list += ["=enemy", "=team", "=team", "=enemy", "=enemy", "=team"]
        for a in range(0, 4):
            self.query_list.append("=ban")
        if fp:
            self.query_list += ["=enemy", "=team", "=team", "=enemy"]
        else:
            self.query_list += ["=team", "=enemy", "=enemy", "=team"]

    def update_query(self):
        self.expected_query = self.query_list.popleft()

    def set_expected_query(self, query):
        self.expected_query = query


# Used as interface between commands and the actual algorithms
class RiotBot:
    def __init__(self):
        debug("Welcome to the Riot Bot!")
        self.active_users = {}

    def create_clash(self, username):
        self.active_users[username] = User(username)

    def update_user_time(self, username):
        if username in self.active_users:
            self.active_users[username].update_time()

    def get_user(self, ctx):
        return self.active_users[ctx.message.author.name]

    def check_query(self, ctx):
        return ctx.message.content.split()[0] == self.get_user(ctx).expected_query

    def set_query(self, ctx, query):
        self.get_user(ctx).set_expected_query(query)

    def get_expected_query(self, ctx):
        debug(self.get_user(ctx).expected_query)
        return self.get_user(ctx).expected_query

    def finish(self, ctx):
        del self.active_users[ctx.message.author.name]

    def set_first_pick(self, ctx, fp):
        self.get_user(ctx).clash_game.my_team_first_pick = fp
        self.get_user(ctx).init_query_list(fp)

    def update_user_query(self, ctx):
        self.get_user(ctx).update_query()

    def is_user_finished(self, ctx):
        return len(self.get_user(ctx).query_list) == 0