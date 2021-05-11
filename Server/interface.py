# This script acts as an interface between the RIOT api and our program

from riotwatcher import LolWatcher, ApiError
from dotenv import load_dotenv
import os, logging, threading, time, queue

# import roleml (UNUSED)

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

# process champion IDs
champ_ids = {}
n = 0
file = open('champs.txt', 'w')
for key in static_champ_list['data']:
    champ_ids[int(static_champ_list['data'][key]['key'])] = {'index': n, 'name': key}
    # write to text file for debugging purposes
    file.write('{0}: [{1}, {2}]\n'.format(int(static_champ_list['data'][key]['key']), n, key))
    n += 1


# Game object is the form our data needs to be in so our network is able to process the data
class Game:

    # champs represented as indices of which they would occur on the network
    def __init__(self):
        self.blue_team = []
        self.red_team = []
        self.blue_winner = 0
        self.lanes = {'MID': 0, 'BOT': 0, 'JUN': 0, "SUP": 0, "TOP": 0}

    # add a champion to a specific lane on blue team
    def add_blue(self, champ, lane):
        if lane == "NULL":
            return
        self.blue_team.append({'champ': champ_ids[champ]['index'], 'lane': lane})
        self.lanes[lane] += 1

    # add a champion to a specific lane on blue team
    def add_red(self, champ, lane):
        if lane == "NULL":
            return
        self.red_team.append({'champ': champ_ids[champ]['index'], 'lane': lane})
        self.lanes[lane] += 1

    # 1 for true, -1 for false
    def set_blue_winner(self, win):
        self.blue_winner = win

    # push the current data structure to the network
    def push_to_network(self, network):
        print(self.lanes)
        # we check for cases such as teams not both having 5 members or repeated lanes
        if len(self.blue_team) != 5 or len(self.red_team) != 5:
            print("ERROR")
            return
        for lane in self.lanes.keys():
            if self.lanes[lane] != 2:
                print("Lanes not correct")
                return
        print("Pushing to network!")
        print(self)
        # iterate and set network values
        for a in range(0, 5):
            network.set_lane_value(self.blue_team[a]['lane'], self.blue_team[a]['champ'], 1)
            network.set_lane_value(self.red_team[a]['lane'], self.red_team[a]['champ'], 0)
        network.solve()
        network.backpropagate(int(self.blue_winner))

    def __str__(self):
        return 'BLUE: {0} , RED: {1}, winner: {2}'.format(self.blue_team, self.red_team, self.blue_winner)


# Returns all ranked players in platinum and diamond elo
def find_all_ranked_players():
    players = []
    for tier in ['DIAMOND', 'PLATINUM']:
        for division in ['I', 'II', 'III', 'IV']:
            players += watcher.league.entries(my_region, "RANKED_SOLO_5x5", tier, division)
    return players


games_to_process = queue.Queue()
matches = []


# Attempts to insert a match_id into the list
# If the match_id is already in the list, it returns true. Otherwise, it adds it and returns false.
def find_and_insert_match(match_id):
    start, end = 0, len(matches)
    midpoint = int(len(matches) / 2)
    while start != end:
        if matches[midpoint] < match_id:
            start = midpoint
            midpoint = int((start + end) / 2)
        elif matches[midpoint] > match_id:
            end = midpoint
            midpoint = int((start + end) / 2)
        elif matches[midpoint] == match_id:
            return True
    matches.insert(start, match_id)
    return False


# return the current time in milliseconds
def current_time_milli():
    return round(time.time() * 1000)


# function for mining Riot's data
def game_miner():
    begin_time = current_time_milli()
    for player in all_players:
        try:
            # Iterate through all players and push all their matches onto the queue if the match was not present in
            # the cache
            accountID = watcher.summoner.by_name(my_region, player['summonerName'])['accountId']
            match_list = watcher.match.matchlist_by_account(region=my_region, encrypted_account_id=accountID,
                                                            queue=[420, 440])
            for match in match_list['matches']:
                if not find_and_insert_match(int(match['gameId'])):
                    try:
                        match_data = watcher.match.by_id(my_region, match['gameId'])
                        games_to_process.put(match_data)
                    except ApiError as err:
                        code = int(str(err)[0:3])
                        if code == 429:
                            logging.info("429 Error. Exceeded Rate Limit. Sleeping.")
                            time.sleep(24 - (current_time_milli() - begin_time) * 1000)
                            begin_time = current_time_milli()
        except ApiError as err:
            # Handle HTTP error codes
            code = int(str(err)[0:3])
            if code == 400:
                logging.info("400 Error. Bad Request.")
            elif code == 429:
                # sleep for 1 minute since we reached max # of requests
                # (we hit 20/s once, then 100/ 2 min, so we wait 24 seconds for average)
                logging.info("429 Error. Exceeded Rate Limit. Sleeping.")
                time.sleep(24 - (current_time_milli() - begin_time) * 1000)
                begin_time = current_time_milli()
            elif code == 403:
                logging.info("403 Error. Renew API Key")
            else:
                logging.info(code)

        exit()


# start thread
def start():
    process_thread = threading.Thread(target=game_miner, daemon=True)
    process_thread.setDaemon(True)
    process_thread.start()


# converts a player to their role
def player_to_role(player):
    role = player['timeline']['role']
    lane = player['timeline']['lane']
    if lane == 'BOTTOM':
        if role == 'DUO_CARRY':
            return "BOT"
        else:
            return "SUP"
    elif lane == 'JUNGLE':
        return 'JUN'
    elif lane == 'TOP':
        return "TOP"
    elif lane == 'MIDDLE':
        return "MID"
    else:
        return "NULL"


# main
if __name__ == "__main__":
    all_players = find_all_ranked_players()
    logging.info("Interface    : players recieved.")
    start()
    network = network.Network()
    while True:
        if games_to_process.qsize() == 0:
            logging.info("Cannot parse none. Sleeping for 10s.")
            time.sleep(10)
            continue
        parse_me = games_to_process.get()
        # roleml.predict(parse_me) (UNUSED)
        game = Game()
        if parse_me['participants'][0]['stats']['win']:
            game.set_blue_winner(True)
        else:
            game.set_blue_winner(False)
        for player in parse_me['participants']:
            if player['teamId'] == 100:
                game.add_blue(player['championId'], player_to_role(player))
            else:
                game.add_red(player['championId'], player_to_role(player))
        game.push_to_network(network)
