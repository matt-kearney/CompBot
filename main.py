# python imports
import os
import sys

# discord imports
import discord
from discord.ext import commands

# dotenv
from dotenv import load_dotenv

# local imports
from riotbot import RiotBot, User, ClashGame
from util import debug, role_text, valid_lane

# initialize the bot object and env
riot_bot = RiotBot()
load_dotenv()

# check if in debug mode
if len(sys.argv) > 1:
    if sys.argv[1] == '-d':
        os.environ["DEBUG"] = "True"

client = commands.Bot(command_prefix="=")
token = os.getenv("DISCORD_BOT_TOKEN")


@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.idle, activity=discord.Game("Ready to Jihu"))
    print("RiotBot online")


@client.command()
async def clash(ctx):
    riot_bot.create_clash(ctx.message.author.name)
    riot_bot.set_query(ctx, "=fp")
    await ctx.send(f"Comp Bot Initialized! Welcome Summoner!")


@client.command()
async def fp(ctx, arg="DEFAULT"):
    if not riot_bot.check_query(ctx):
        await ctx.send(f"Expected: {riot_bot.get_expected_query(ctx)} [yes/no]")
        return
    if arg.upper() == "YES":
        riot_bot.set_first_pick(ctx, True)
    elif arg.upper() == "NO":
        riot_bot.set_first_pick(ctx, False)
    else:
        await ctx.send(f"Expected: {riot_bot.get_expected_query(ctx)} [yes/no]")
        return
    riot_bot.update_user_query(ctx)

@client.command()
async def ban(ctx, champion="NULL"):
    if not riot_bot.check_query(ctx) or champion == "NULL":
        await ctx.send(f"Expected: {riot_bot.get_expected_query(ctx)} [champion]")
        return
    riot_bot.get_user(ctx).clash_game.add_ban(champion)
    riot_bot.update_user_query(ctx)
    await ctx.send(f"Successfully banned {champion}")


@client.command()
async def enemy(ctx, champion="NULL", role="NULL"):
    if not riot_bot.check_query(ctx) or (champion == "NULL" or role == "NULL") or valid_lane(role):
        await ctx.send(f"Expected: {riot_bot.get_expected_query(ctx)} [champion, role]")
        return
    riot_bot.get_user(ctx).clash_game.enemy_team_add(champion, role)
    riot_bot.update_user_query(ctx)
    await ctx.send(f"Successfully added enemy {champion} at {role_text(role)}")


@client.command()
async def team(ctx, champion="NULL", role="NULL"):
    if not riot_bot.check_query(ctx) or (champion == "NULL" or role == "NULL") or valid_lane(role):
        await ctx.send(f"Expected: {riot_bot.get_expected_query(ctx)} [champion, role]")
        return
    riot_bot.get_user(ctx).clash_game.my_team_add(champion, role)
    riot_bot.update_user_query(ctx)
    await ctx.send(f"Successfully added friendly {champion} at {role_text(role)}")


@client.command()
async def finish(ctx):
    if not riot_bot.is_user_finished(ctx):
        await ctx.send(f"Expected: {riot_bot.get_expected_query(ctx)}")
        return
    riot_bot.finish(ctx)
    await ctx.send(f"Thank you for using the RiotBot! Good luck!")


client.run(token)
