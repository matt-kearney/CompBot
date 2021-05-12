# This script acts as an interface between the RIOT api and our program

from riotwatcher import LolWatcher, ApiError
from dotenv import load_dotenv
import os, logging, threading, time, queue

# import roleml (UNUSED)

import Server.network as ne


# return the current time in milliseconds
def current_time_milli():
    return round(time.time() * 1000)


watcher = None
my_region = None
champ_ids = {}
games_to_process = queue.Queue()
matches = []
all_players = []
begin_time = current_time_milli()


def init():
    global watcher
    global my_region
    global champ_ids
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
# TODO: Make this function safe.
def find_all_ranked_players():
    players = []
    for tier in ['DIAMOND', 'PLATINUM']:
        for division in ['I', 'II', 'III', 'IV']:
            players += watcher.league.entries(my_region, "RANKED_SOLO_5x5", tier, division)
    return players


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


def handle_api_err(err, callback, data):
    global begin_time
    code = int(str(err)[0:3])
    if code == 429:
        time_to_sleep = 24 - (current_time_milli() - begin_time) * 1000
        print("429 Error. Exceeded Rate Limit. Sleeping for {0} seconds.".format(time_to_sleep))
        time.sleep(time_to_sleep)
        begin_time = current_time_milli()
        return callback(data)
    elif code == 400:
        print("400 Error. Bad request.")
    elif code == 403:
        print("403 Error. Renew API.")
    else:
        print("{0} Error. Look it up.".format(code))
    return None


# Obtains a players ID. Returns None if HTTP error.
def get_player_ID(player):
    try:
        return watcher.summoner.by_name(my_region, player['summonerName'])['accountId']
    except ApiError as err:
        return handle_api_err(err, get_player_ID, player)


# Obtains a players match history for ranked solo/duo and flex. Returns None if HTTP error.
def get_player_match_list(accountID):
    try:
        return watcher.match.matchlist_by_account(region=my_region, encrypted_account_id=accountID, queue=[420, 440])
    except ApiError as err:
        return handle_api_err(err, get_player_match_list, accountID)


# Obtain the match data from the API. Returns None if HTTP error or match was already processed.
def get_match(match):
    if not find_and_insert_match(int(match['gameId'])):
        try:
            return watcher.match.by_id(my_region, match['gameId'])
        except ApiError as err:
            return handle_api_err(err, get_match, match)
    return None


# function for mining Riot's data
def game_miner():
    for player in all_players:
        player_id = get_player_ID(player)
        if player_id is None:
            print("ERROR???")
        match_list = get_player_match_list(player_id)
        for match in match_list:
            match_data = get_match(match)
            if match_data is not None:
                games_to_process.put(match_data)


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


# process
def process():
    global all_players
    init()
    all_players = find_all_ranked_players()
    logging.info("Interface    : players recieved.")
    start()
    network = ne.Network()
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


# main
if __name__ == "__main__":
    process()
