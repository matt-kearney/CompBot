# This script acts as an interface between the RIOT api and our program

from riotwatcher import LolWatcher, ApiError
from dotenv import load_dotenv
import os, logging, threading, time, queue, math

# import roleml (UNUSED)

import network as ne


# return the current time in milliseconds
def current_time_milli():
    return round(time.time() * 1000)


# GLOBAL VARIABLES

# setup
load_dotenv()
logging.basicConfig(level=logging.INFO)

# API info
api_key = os.getenv("API_KEY")
watcher = LolWatcher(api_key)
my_region = 'na1'

# GLOBAL DATA STRUCTURES

champ_ids = {}
games_to_process = queue.Queue()
matches = []
all_players = []
begin_time = current_time_milli()
players = []

# GLOBAL FILES

match_id_file = open("match_ids.txt", "a")
players_file = open("players.txt", "a")
game_data_file = open("game_data.txt", "a")


def init():
    global champ_ids
    global all_players

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

    all_players = find_all_ranked_players()


def file_init():
    global match_id_file
    global players_file
    global game_data_file

    match_id_file = open("match_ids.txt", "r")
    players_file = open("players.txt", "r")
    game_data_file = open("game_data.txt", "r")

    for match in match_id_file:
        find_and_insert_match(int(match))
    for player in players_file:
        find_and_insert_player(player)
    for game in game_data_file:
        g = Game()
        g.from_file_str(game)
        games_to_process.put(g)

    match_id_file = open("match_ids.txt", "a")
    players_file = open("players.txt", "a")
    game_data_file = open("game_data.txt", "a")


# Game object is the form our data needs to be in so our network is able to process the data
class Game:

    # champs represented as indices of which they would occur on the network
    def __init__(self, match_data=None):
        self.blue_team = []
        self.red_team = []
        self.blue_winner = 0
        self.lanes = {'MID': 0, 'BOT': 0, 'JUN': 0, "SUP": 0, "TOP": 0}
        if match_data is not None:
            if match_data['participants'][0]['stats']['win']:
                self.set_blue_winner(True)
            else:
                self.set_blue_winner(False)
            for player in match_data['participants']:
                if player['teamId'] == 100:
                    self.add_blue(player['championId'], player_to_role(player))
                else:
                    self.add_red(player['championId'], player_to_role(player))

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

    # Game file str is how the Game object is written into a file
    # The format will be the following separated by tab (\t):
    # 0 or 1, indicating blue_team_winner boolean
    # Blue team's champs (as indices) and lanes. Each separated by \t
    # Red team's champs and lanes
    def to_file_str(self):
        if len(self.blue_team) != 5 or len(self.red_team) != 5:
            return "ERROR"
        for lane in self.lanes.keys():
            if self.lanes[lane] != 2:
                return "ERROR"
        str = ""
        if self.blue_winner:
            str += "1\t"
        else:
            str += "0\t"
        for blue in self.blue_team:
            str += "{0}\t{1}\t".format(blue['champ'], blue['lane'])
        for red in self.red_team:
            str += "{0}\t{1}\t".format(red['champ'], red['lane'])
        return str

    # generates a Game object from str. It's assumed that any game object written to the file is valid
    def from_file_str(self, str):
        split = str.split("\t")
        if split[0] == "0":
            self.blue_winner = True
        else:
            self.blue_winner = False
        for a in range(1, 11, 2):
            self.blue_team.append({'champ': split[a], 'lane': split[a + 1]})
            self.lanes[split[a + 1]] += 1
        for a in range(11, 21, 2):
            self.red_team.append({'champ': split[a], 'lane': split[a + 1]})
            self.lanes[split[a + 1]] += 1


# Returns all ranked players in platinum and diamond elo
# TODO: Make this function safe.
def find_all_ranked_players():
    tmp_player_list = []
    for tier in ['DIAMOND', 'PLATINUM']:
        for division in ['I', 'II', 'III', 'IV']:
            tmp_player_list += watcher.league.entries(my_region, "RANKED_SOLO_5x5", tier, division)
    return tmp_player_list


# Attempts to insert a match_id into the list
# If the match_id is already in the list, it returns true. Otherwise, it adds it and returns false.
def find_and_insert_match(match_id):
    start, end = 0, len(matches)
    midpoint = int(len(matches) / 2)
    while start != end and start != end-1:
        print("START: {0}\tMIDPOINT: {1}\tEND: {2}\t".format(start, midpoint, end))
        if matches[midpoint] < match_id:
            start = midpoint
            midpoint = math.floor((start + end) / 2)
        elif matches[midpoint] > match_id:
            end = midpoint
            midpoint = math.floor((start + end) / 2)
        elif matches[midpoint] == match_id:
            return True
    matches.insert(start, match_id)
    return False


# Attempts to insert a player into the list
# If the player is already in the list, it returns true. Otherwise, it adds it and returns false.
# TODO: Optimize this
def find_and_insert_player(player):
    for i in players:
        if player == i:
            return True
    players.append(player)
    return False


# Handle API error
def handle_api_err(err, callback, data):
    code = int(str(err)[0:3])
    if code == 429:
        print("429 Error. Exceeded Rate Limit. ")
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


# function for parsing Riot's data and processing it
def mine_and_process():
    for player in all_players:
        player_id = get_player_ID(player)
        if player_id is None:
            print("ERROR???")
            continue
        match_list = get_player_match_list(player_id)
        for match in match_list:
            match_data = get_match(match)
            if match_data is not None:
                games_to_process.put(match_data)


# function for mining Riot's game data
def mine():
    for player in all_players:
        print("PROCESSING PLAYER: {0}".format(player['summonerName']))
        if not find_and_insert_player(player):
            player_id = get_player_ID(player)
            if player_id is None:
                continue
            match_list = get_player_match_list(player_id)['matches']
            for match in match_list:
                match_data = get_match(match)
                if match_data is not None:
                    print("PROCESSING MATCH: {0}".format(match['gameId']))
                    match_id_file.write(str(match['gameId']) + '\n')
                    game = Game(match_data)
                    write_me = game.to_file_str() + '\n'
                    if write_me == "ERROR\n":
                        continue
                    else:
                        game_data_file.write(write_me)
        players_file.write(player['summonerName'] + '\n')


# start thread
def start():
    process_thread = threading.Thread(target=mine_and_process, daemon=True)
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
        game = Game(parse_me)
        game.push_to_network(network)


# initialize environment for passive mining
def passive_mine_init():
    file_init()
    mine()


# main
if __name__ == "__main__":
    init()
    passive_mine_init()
    # process()
