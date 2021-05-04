# This script acts as an interface between the RIOT api and our program

from riotwatcher import LolWatcher, ApiError
from dotenv import load_dotenv
import os

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