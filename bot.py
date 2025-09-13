import requests
import asyncio
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ----------------- CONFIG -----------------
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY"
API_FOOTBALL_KEY = "YOUR_API_FOOTBALL_KEY"
CHANNEL_ID = "UCakjz6EexQFvM7PZtUXy9GQ"  # SportyTV Africa
BANNER_URL = "https://i.ibb.co/f1hJQ0w/football-banner.jpg"

subscribers = set()
followers = {}   # {chat_id: [teams]}
last_live_video_id = None
sent_lineups = set()
sent_events = {}   # {fixture_id: set(event_ids)}

# ----------------- HELPERS -----------------

def check_live_stream():
    url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&channelId={CHANNEL_ID}&eventType=live&type=video&key={YOUTUBE_API_KEY}"
    )
    response = requests.get(url).json()
    if "items" in response and len(response["items"]) > 0:
        live_video = response["items"][0]
        video_id = live_video["id"]["videoId"]
        title = live_video["snippet"]["title"]
        link = f"https://www.youtube.com/watch?v={video_id}"
        return title, link, video_id
    return None

def get_lineup_message(team_name):
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}&team={team_name}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    fixtures = requests.get(url, headers=headers).json()["response"]

    if not fixtures:
        return None

    fixture_id = fixtures[0]["fixture"]["id"]
    url = f"https://v3.football.api-sports.io/fixtures/lineups?fixture={fixture_id}"
    lineups = requests.get(url, headers=headers).json()["response"]

    if not lineups:
        return None

    msg = f"👥 {team_name} Lineup\n\n"
    for lineup in lineups:
        if lineup["team"]["name"].lower() == team_name.lower():
            msg += "🟢 *Starting XI:*\n"
            for p in lineup["startXI"]:
                player = p["player"]
                msg += f"{player['pos']}: #{player['number']} {player['name']}\n"
            msg += "\n⚪ *Bench:*\n"
            for p in lineup["substitutes"]:
                player = p["player"]
                msg += f"{player['pos']}: #{player['number']} {player['name']}\n"
    return msg

# ----------------- INLINE BUTTONS -----------------

def main_menu_buttons(live_video=None):
    if live_video:
        title, link, _ = live_video
        keyboard = [
            [InlineKeyboardButton("📺 Watch Live", url=link)],
            [
                InlineKeyboardButton("📅 Fixtures", callback_data="fixtures"),
                InlineKeyboardButton("📡 Live Scores", callback_data="livescores"),
            ],
            [
                InlineKeyboardButton("👥 Lineups", callback_data="lineups"),
                InlineKeyboardButton("ℹ️ About", callback_data="about"),
            ],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("❌ No Live Now", callback_data="watch")],
            [
                InlineKeyboardButton("📅 Fixtures", callback_data="fixtures"),
                InlineKeyboardButton("📡 Live Scores", callback_data="livescores"),
            ],
            [
                InlineKeyboardButton("👥 Lineups", callback_data="lineups"),
                InlineKeyboardButton("ℹ️ About", callback_data="about"),
            ],
        ]
    return InlineKeyboardMarkup(keyboard)

# ----------------- COMMANDS -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = check_live_stream()
    caption = "⚽ *Welcome to Sporty Bot!*"
    if video:
        title, _, _ = video
        caption += f"\n\n✅ SportyTV is live now:\n*{title}*"
    else:
        caption += "\n\n❌ SportyTV is not live at the moment."

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=BANNER_URL,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=main_menu_buttons(video),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Use:\n"
        "/watch /fixtures /livescores /lineups /about /subscribe\n"
        "/follow TeamName /unfollow TeamName",
        reply_markup=main_menu_buttons(),
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🤖 *Sporty Bot*\n\n"
        "🎥 SportyTV live alerts\n"
        "📅 Fixtures & Live scores\n"
        "👥 Lineups & Auto push\n"
        "⚽ Goal + 🟥 Red card alerts\n\n"
        "Powered by API-Football + YouTube API"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    subscribers.add(chat_id)
    await update.message.reply_text("✅ Subscribed! You’ll get SportyTV live alerts.")

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = check_live_stream()
    if video:
        title, link, _ = video
        keyboard = [[InlineKeyboardButton("📺 Watch Live", url=link)]]
        await update.message.reply_text(
            f"✅ SportyTV is live now:\n*{title}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await update.message.reply_text("❌ SportyTV is not live now.")

async def fixtures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    response = requests.get(url, headers=headers).json()

    if not response["response"]:
        await update.message.reply_text("📅 No matches today.")
        return

    message = "📅 *Today's Fixtures:*\n\n"
    for match in response["response"][:10]:
        league = match["league"]["name"]
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        time = match["fixture"]["date"][11:16]
        message += f"{time} | {league}: {home} vs {away}\n"

    await update.message.reply_text(message, parse_mode="Markdown")

async def livescores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    response = requests.get(url, headers=headers).json()

    if not response["response"]:
        await update.message.reply_text("📡 No live matches now.")
        return

    message = "📡 *Live Scores:*\n\n"
    for match in response["response"][:10]:
        league = match["league"]["name"]
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        score = match["goals"]
        minute = match["fixture"]["status"]["elapsed"]
        message += f"{league}: {home} {score['home']} - {score['away']} {away} ({minute}')\n"

    await update.message.reply_text(message, parse_mode="Markdown")

async def follow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /follow TeamName")
        return
    team = " ".join(context.args)
    followers.setdefault(chat_id, []).append(team)
    await update.message.reply_text(f"✅ You are now following {team}.")

async def unfollow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /unfollow TeamName")
        return
    team = " ".join(context.args)
    if chat_id in followers and team in followers[chat_id]:
        followers[chat_id].remove(team)
        await update.message.reply_text(f"❌ You unfollowed {team}.")
    else:
        await update.message.reply_text(f"You were not following {team}.")

async def lineups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /lineups TeamName")
        return
    team = " ".join(context.args)
    msg = get_lineup_message(team)
    if msg:
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ No lineup for {team} now.")

# ----------------- CALLBACK HANDLER -----------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "watch":
        await watch(query, context)
    elif query.data == "fixtures":
        await fixtures(query, context)
    elif query.data == "livescores":
        await livescores(query, context)
    elif query.data == "lineups":
        await query.message.reply_text("👉 Use /lineups TeamName")
    elif query.data == "about":
        await about(query, context)

# ----------------- AUTO NOTIFY -----------------

async def notify_task(app: Application):
    global last_live_video_id, sent_lineups, sent_events
    while True:
        # SportyTV Live
        video = check_live_stream()
        if video:
            title, link, video_id = video
            if video_id != last_live_video_id:
                last_live_video_id = video_id
                keyboard = [[InlineKeyboardButton("📺 Watch Live", url=link)]]
                for chat_id in subscribers:
                    try:
                        await app.bot.send_message(
                            chat_id,
                            f"📡 SportyTV is LIVE!\n*{title}*",
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(keyboard),
                        )
                    except: pass

        # Fixtures
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"https://v3.football.api-sports.io/fixtures?date={today}"
        headers = {"x-apisports-key": API_FOOTBALL_KEY}
        fixtures = requests.get(url, headers=headers).json()["response"]

        for match in fixtures:
            fixture_id = match["fixture"]["id"]
            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]

            # Lineups
            if fixture_id not in sent_lineups:
                for chat_id, teams in followers.items():
                    if any(t.lower() in [home.lower(), away.lower()] for t in teams):
                        url2 = f"https://v3.football.api-sports.io/fixtures/lineups?fixture={fixture_id}"
                        lineups = requests.get(url2, headers=headers).json()["response"]
                        if lineups:
                            sent_lineups.add(fixture_id)
                            for lineup in lineups:
                                team_name = lineup["team"]["name"]
                                msg = f"👥 *{team_name} Official Lineup*\n\n"
                                msg += "🟢 *Starting XI:*\n"
                                for p in lineup["startXI"]:
                                    pl = p["player"]
                                    msg += f"{pl['pos']}: #{pl['number']} {pl['name']}\n"
                                msg += "\n⚪ *Bench:*\n"
                                for p in lineup["substitutes"]:
                                    pl = p["player"]
                                    msg += f"{pl['pos']}: #{pl['number']} {pl['name']}\n"
                                try:
                                    await app.bot.send_message(chat_id, msg, parse_mode="Markdown")
                                except: pass

            # Match events (Goals & Red cards)
            url3 = f"https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}"
            events = requests.get(url3, headers=headers).json()["response"]

            for ev in events:
                event_id = f"{fixture_id}-{ev['time']['elapsed']}-{ev['team']['id']}-{ev['player']['id']}-{ev['type']}"
                if fixture_id not in sent_events:
                    sent_events[fixture_id] = set()
                if event_id in sent_events[fixture_id]:
                    continue

                sent_events[fixture_id].add(event_id)

                team = ev["team"]["name"]
                player = ev["player"]["name"]
                minute = ev["time"]["elapsed"]

                if ev["type"] == "Goal":
                    msg = f"⚽ GOAL! {team} - {player} ({minute}')"
                elif ev["type"] == "Card" and ev["detail"] == "Red Card":
                    msg = f"🟥 RED CARD! {team} - {player} ({minute}')"
                else:
                    continue

                for chat_id, teams in followers.items():
                    if any(t.lower() == team.lower() for t in teams):
                        try:
                            await app.bot.send_message(chat_id, msg)
                        except: pass

        await asyncio.sleep(180)

# ----------------- MAIN -----------------

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("fixtures", fixtures))
    app.add_handler(CommandHandler("livescores", livescores))
    app.add_handler(CommandHandler("follow", follow))
    app.add_handler(CommandHandler("unfollow", unfollow))
    app.add_handler(CommandHandler("lineups", lineups))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.job_queue.run_once(lambda _: asyncio.create_task(notify_task(app)), 0)

    app.run_polling()

if __name__ == "__main__":
    main()
