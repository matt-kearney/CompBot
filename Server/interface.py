# This script acts as an interface between the RIOT api and our program

from riotwatcher import LolWatcher, ApiError
from dotenv import load_dotenv
import os
import logging
import threading
import time

import network

# setup
load_dotenv()
logging.basicConfig(level=logging.INFO)

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


# Returns all ranked players in platinum and diamond elo
def find_all_ranked_players():
    players = []
    for tier in ['PLATINUM', 'DIAMOND']:
        for division in ['I', 'II', 'III', 'IV']:
            players += watcher.league.entries(my_region, "RANKED_SOLO_5x5", tier, division)
    return players


games_to_process = []
matches = []


# Attempts to insert a match_id into the list
# If the match_id is already in the list, it returns true. Otherwise, it adds it and returns false.
def find_and_insert_match(match_id):
    start, end = 0, len(matches)
    midpoint = len(matches) / 2
    while start != end:
        if matches[midpoint] < match_id:
            start = midpoint
            midpoint = (start + end) / 2
        elif matches[midpoint] > match_id:
            end = midpoint
            midpoint = (start + end) / 2
        elif matches[midpoint] == match_id:
            return True
    matches.insert(start, match_id)
    return False


def current_time_milli():
    return round(time.time() * 1000)


def game_miner():
    begin_time = current_time_milli()
    for player in all_players:
        try:
            accountID = watcher.summoner.by_name(my_region, 'mediocrebeandip' )['accountId'] #player['summonerName']
            match_list = watcher.match.matchlist_by_account(region=my_region, encrypted_account_id=accountID, queue=[420,440])
            for match in match_list['matches']:
                print(match)
                print(champ_ids[match['champion']]['name'])
        except ApiError as err:
            # Handle HTTP error codes
            code = int(str(err)[0:3])
            if code == 400:
                logging.info("400 Error. Bad Request.")
            elif code == 429:
                # sleep for 2 minutes since we reached max # of requests
                logging.info("429 Error. Exceeded Rate Limit. Sleeping.")
                time.sleep(120000 - (current_time_milli() - begin_time))
                begin_time = current_time_milli()
            elif code == 403:
                logging.info("403 Error. Renew API Key")
            else:
                logging.info(code)

        exit()


def start():
    process_thread = threading.Thread(target=game_miner)
    process_thread.start()

if __name__ == "__main__":
    all_players = find_all_ranked_players()
    logging.info("Interface    : players recieved.")
    start()
