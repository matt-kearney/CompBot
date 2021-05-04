# This script acts as an interface between the RIOT api and our program

from riotwatcher import LolWatcher, ApiError
from dotenv import load_dotenv
import os

import network

load_dotenv()

# API info
api_key = os.getenv("API_KEY")
watcher = LolWatcher(api_key)
my_region = 'na1'

# obtain static champ list for pre-processing
latest = watcher.data_dragon.versions_for_region(my_region)['n']['champion']
static_champ_list = watcher.data_dragon.champions(latest, False, 'en_US')

champ_ids = {}
n = 0
for key in static_champ_list['data']:
    champ_ids[int(static_champ_list['data'][key]['key'])] = {'index': n, 'name': key}
    n += 1


class Game:

    # champs represented as indices of which they would occur on the network
    def __init__(self):
        self.blue_team = []
        self.red_team = []
        self.blue_winner = 0

    def add_blue(self, champ, lane):
        self.blue_team.append({'champ': champ, 'lane': lane})

    def add_red(self, champ, lane):
        self.red_team.append({'champ': champ, 'lane': lane})

    # 1 for true, -1 for false
    def set_blue_winner(self, win):
        self.blue_winner = win

    def push_to_network(self, network):
        if len(self.blue_team) != 5 or len(self.red_team) != 5:
            print("ERROR")
            return
        for a in range(0, 5):
            network.set_lane_value(self.blue_team[a]['lane'], self.blue_team[a]['champ'], 1)
            network.set_lane_value(self.red_team[a]['lane'], self.red_team[a]['champ'], -1)
        network.solve()
        network.backpropagate(self.blue_winner)
