import os
import asyncio
import nest_asyncio
from dotenv import load_dotenv

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ─── Games ──────────────────────────────────────────────────────────────
from housebal import housebal_command, sethousebal_command
import dice as dice_game
import darts as darts_game

# Slots
from slots import (
    slots_command,
    next_combos_handler,
    start_handler,
    combos_handler,
    bet_handler,
    spin_handler,
    replay_handler,
    double_handler,
)

# Roulette
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from roulette import roulette_command, cb_router

# Dice (extra import, specific handlers)
from dice import (
    dice_command,
    mode_handler,
    points_handler,
    confirm_handler,
    accept_handler,
    handle_user_rolls,
    action_handler,
    replay_handler,
    double_handler,
)

# Level Up Bonus
from levelup import levelup_bonus_view, level_claim_handler, noop_locked_handler
from levels import levels_command, levels_callback_handler

# Darts
from darts import (
    dart_command,
    mode_handler as darts_mode_handler,
    points_handler as darts_points_handler,
    confirm_handler as darts_confirm_handler,
    accept_handler as darts_accept_handler,
    handle_user_throws,
    action_handler as darts_action_handler,
    replay_handler as darts_replay_handler,
    double_handler as darts_double_handler,
)

# Basketball
from basket import (
    bask_command,
    bask_mode_handler,
    bask_points_handler,
    bask_confirm_handler,
    bask_accept_handler,
    bask_start_round,
    handle_user_shots,
    bask_action_handler,
    bask_replay_handler,
    bask_double_handler,
    bask_cancel_handler,
)

# Core Features
from start import (
    start,
    play_menu,
    more_content_menu,
    deposit_menu,
    withdraw_menu,
    main_menu_callback,
)
from bonus import bonus_menu
from bowl import (
    bowl_command,
    bowl_mode_handler,
    bowl_points_handler,
    bowl_confirm_handler,
    bowl_accept_handler,
    bowl_start_round,
    handle_user_bowls,
    bowl_action_handler,
    bowl_replay_handler,
    bowl_double_handler,
    bowl_cancel_handler,
)
from football import (
    ball_command,
    ball_mode_handler,
    ball_points_handler,
    ball_confirm_handler,
    ball_accept_handler,
    ball_start_round,
    handle_user_kicks,
    ball_action_handler,
    ball_replay_handler,
    ball_double_handler,
    ball_cancel_handler,
)

# Balance
from balance import balance, set_balance, add_balance, drain_balance

# Tips / Stats
from tip import tip_command, tip_confirmation_handler, tiplog_command, tiplog_page_handler
from stats import stats_command

# Bonus
from bonus import bonus_command, bonus_menu, weekly_bonus, claim_bonus, try_to_double

# Leaderboard
from leaderboard import leaderboard_command, leaderboard_callback

# Prediction
from predict import predict_command, predict_router

# Events
from events import (
    raffle_command,
    buyraffle_command,
    startraffle_command,
    endraffle_command,
    raffle_rules,
    raffle_history,
    raffle_back,
)

# Coinflip
from coinflip import (
    coin_command,
    coin_side_handler,
    coin_accept_friend_handler,
    coin_accept_bot_handler,
    coin_cancel_handler,
    coin_flip_handler,
    coin_verify_handler,
)

# User count


# Matches
from matches import matches_command, matches_page_cb

# Help & Support
from helpsupport import news_command, help_command, back_to_menu_handler

# Tower
from tower import (
    tower_command,
    tower_play,
    tower_rules,
    tower_diff_left,
    tower_diff_right,
    tower_start,
    tower_pick,
    tower_cashout,
    tower_none,
)

# Wheel
from wheel import (
    wheel_command,
    wheel_play_handler,
    wheel_start_handler,
    wheel_half_handler,
    wheel_double_handler,
    wheel_verify_handler,
    wheel_back_handler,
)

# Referral
from referral import (
    initialize_referral_db,
    createreferralcode_command,
    referral_command,
    usecode_command,
    delete_referral_command,
    referralstats_command,
    track_referral_event,
)

# Database
from models import initialize_database


# ─── Config & Entrypoint ──────────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN not set in .env")


async def main():
    # Init DBs
    initialize_database()
    initialize_referral_db()

    # Build App
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # /start
    app.add_handler(CommandHandler("start", start))

    # Football handlers
    app.add_handler(CommandHandler("ball", ball_command))
    app.add_handler(CallbackQueryHandler(ball_mode_handler, pattern=r"^ball_mode:"))
    app.add_handler(CallbackQueryHandler(ball_points_handler, pattern=r"^ball_points:"))
    app.add_handler(CallbackQueryHandler(ball_confirm_handler, pattern=r"^ball_confirm:"))
    app.add_handler(CallbackQueryHandler(ball_accept_handler, pattern=r"^ball_accept:"))
    app.add_handler(CallbackQueryHandler(ball_action_handler, pattern=r"^ball_action:"))
    app.add_handler(CallbackQueryHandler(ball_replay_handler, pattern=r"^ball_replay:"))
    app.add_handler(CallbackQueryHandler(ball_double_handler, pattern=r"^ball_double:"))
    app.add_handler(CallbackQueryHandler(ball_cancel_handler, pattern=r"^ball_cancel$"))
    app.add_handler(MessageHandler(filters.Dice.FOOTBALL, handle_user_kicks))

    # Basketball
    app.add_handler(CommandHandler("bask", bask_command))
    app.add_handler(CallbackQueryHandler(bask_mode_handler, pattern=r"^bask_mode:"))
    app.add_handler(CallbackQueryHandler(bask_points_handler, pattern=r"^bask_points:"))
    app.add_handler(CallbackQueryHandler(bask_confirm_handler, pattern=r"^bask_confirm:"))
    app.add_handler(CallbackQueryHandler(bask_accept_handler, pattern=r"^bask_accept:"))
    app.add_handler(CallbackQueryHandler(bask_action_handler, pattern=r"^bask_action:"))
    app.add_handler(CallbackQueryHandler(bask_replay_handler, pattern=r"^bask_replay:"))
    app.add_handler(CallbackQueryHandler(bask_double_handler, pattern=r"^bask_double:"))
    app.add_handler(CallbackQueryHandler(bask_cancel_handler, pattern=r"^bask_cancel$"))
    app.add_handler(MessageHandler(filters.Dice.BASKETBALL, handle_user_shots))

    # Bowling
    app.add_handler(CommandHandler("bowl", bowl_command))
    app.add_handler(CallbackQueryHandler(bowl_mode_handler, pattern=r"^bowl_mode:"))
    app.add_handler(CallbackQueryHandler(bowl_points_handler, pattern=r"^bowl_points:"))
    app.add_handler(CallbackQueryHandler(bowl_confirm_handler, pattern=r"^bowl_confirm:"))
    app.add_handler(CallbackQueryHandler(bowl_accept_handler, pattern=r"^bowl_accept:"))
    app.add_handler(CallbackQueryHandler(bowl_action_handler, pattern=r"^bowl_action:"))
    app.add_handler(CallbackQueryHandler(bowl_replay_handler, pattern=r"^bowl_replay:"))
    app.add_handler(CallbackQueryHandler(bowl_double_handler, pattern=r"^bowl_double:"))
    app.add_handler(CallbackQueryHandler(bowl_cancel_handler, pattern=r"^bowl_cancel$"))
    app.add_handler(MessageHandler(filters.Dice.BOWLING, handle_user_bowls))

    # Balance
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("bal", balance))
    app.add_handler(CommandHandler("setbalance", set_balance))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CommandHandler("drainbalance", drain_balance))

    # Tips
    app.add_handler(CommandHandler("tip", tip_command))
    app.add_handler(CallbackQueryHandler(tip_confirmation_handler, pattern="^tip_"))
    app.add_handler(CommandHandler("tiplog", tiplog_command))
    app.add_handler(CallbackQueryHandler(tiplog_page_handler, pattern="^tiplog:"))

    # Stats
    app.add_handler(CommandHandler("stats", stats_command))

    # Bonus
    app.add_handler(CommandHandler("bonus", bonus_command))
    app.add_handler(CallbackQueryHandler(bonus_menu, pattern="^bonus_menu$"))
    app.add_handler(CallbackQueryHandler(weekly_bonus, pattern="^bonus_weekly$"))
    app.add_handler(CallbackQueryHandler(claim_bonus, pattern="^claim_bonus$"))
    app.add_handler(CallbackQueryHandler(try_to_double, pattern="^try_double$"))

    # Coinflip
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CallbackQueryHandler(coin_side_handler, pattern="^coin_side:"))
    app.add_handler(CallbackQueryHandler(coin_accept_friend_handler, pattern="^coin_accept_friend$"))
    app.add_handler(CallbackQueryHandler(coin_accept_bot_handler, pattern="^coin_accept_bot$"))
    app.add_handler(CallbackQueryHandler(coin_cancel_handler, pattern="^coin_cancel$"))
    app.add_handler(CallbackQueryHandler(coin_flip_handler, pattern="^coin_flip$"))
    app.add_handler(CallbackQueryHandler(coin_verify_handler, pattern="^coin_verify$"))

    # Referral
    app.add_handler(CommandHandler("createreferralcode", createreferralcode_command))
    app.add_handler(CommandHandler(["referral", "ref"], referral_command))
    app.add_handler(CommandHandler("code", usecode_command))
    app.add_handler(CommandHandler("delrefcode", delete_referral_command))
    app.add_handler(CommandHandler("referralstats", referralstats_command))

    # Leaderboard
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CallbackQueryHandler(leaderboard_callback, pattern="^leaderboard_"))

    # Matches
    app.add_handler(CommandHandler("matches", matches_command))
    app.add_handler(CallbackQueryHandler(matches_page_cb, pattern=r"^matches:\d+$"))

    # Levels
    app.add_handler(CommandHandler("levels", levels_command))
    app.add_handler(CallbackQueryHandler(levels_callback_handler, pattern="^levels_"))

    # Help
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(back_to_menu_handler, pattern="^back_to_menu$"))

    # Prediction
    app.add_handler(CommandHandler("predict", predict_command))
    app.add_handler(
        CallbackQueryHandler(
            predict_router, pattern="^(predict_action|predict_mode|predict_opt|predict_bet):"
        )
    )

    # Slots
    app.add_handler(CommandHandler("slots", slots_command))
    app.add_handler(CallbackQueryHandler(next_combos_handler, pattern="^slots:next$"))
    app.add_handler(CallbackQueryHandler(start_handler, pattern="^slots:start$"))
    app.add_handler(CallbackQueryHandler(combos_handler, pattern="^slots:combos$"))
    app.add_handler(CallbackQueryHandler(bet_handler, pattern="^slots:bet"))
    app.add_handler(CallbackQueryHandler(spin_handler, pattern="^slots:spin$"))
    app.add_handler(CallbackQueryHandler(replay_handler, pattern="^slots:replay"))
    app.add_handler(CallbackQueryHandler(double_handler, pattern="^slots:double"))

    # Dice
    app.add_handler(CommandHandler("dice", dice_game.dice_command))
    app.add_handler(CallbackQueryHandler(dice_game.mode_handler, pattern=r"^mode:"))
    app.add_handler(CallbackQueryHandler(dice_game.points_handler, pattern=r"^points:"))
    app.add_handler(CallbackQueryHandler(dice_game.confirm_handler, pattern=r"^confirm:"))
    app.add_handler(CallbackQueryHandler(dice_game.accept_handler, pattern=r"^accept:"))
    app.add_handler(CallbackQueryHandler(dice_game.action_handler, pattern=r"^action:"))
    app.add_handler(CallbackQueryHandler(dice_game.replay_handler, pattern=r"^replay:"))
    app.add_handler(CallbackQueryHandler(dice_game.double_handler, pattern=r"^double:"))
    app.add_handler(MessageHandler(filters.Dice.DICE, dice_game.handle_user_rolls))

    # Darts
    app.add_handler(CommandHandler("darts", darts_game.dart_command))
    app.add_handler(CallbackQueryHandler(darts_game.mode_handler, pattern=r"^dart:mode:"))
    app.add_handler(CallbackQueryHandler(darts_game.points_handler, pattern=r"^dart:points:"))
    app.add_handler(CallbackQueryHandler(darts_game.confirm_handler, pattern=r"^dart:confirm:"))
    app.add_handler(CallbackQueryHandler(darts_game.accept_handler, pattern=r"^dart:accept:"))
    app.add_handler(CallbackQueryHandler(darts_game.action_handler, pattern=r"^dart:action:"))
    app.add_handler(CallbackQueryHandler(darts_game.replay_handler, pattern=r"^dart:replay:"))
    app.add_handler(CallbackQueryHandler(darts_game.double_handler, pattern=r"^dart:double:"))
    app.add_handler(MessageHandler(filters.Dice.DARTS, darts_game.handle_user_throws))

    # House balance
    app.add_handler(CommandHandler("housebal", housebal_command))
    app.add_handler(CommandHandler("sethousebal", sethousebal_command))

    # Tower
    app.add_handler(CommandHandler("tower", tower_command))
    app.add_handler(CallbackQueryHandler(tower_play, pattern="^tower_play$"))
    app.add_handler(CallbackQueryHandler(tower_rules, pattern="^tower_rules$"))
    app.add_handler(CallbackQueryHandler(tower_diff_left, pattern="^tower_diff_left$"))
    app.add_handler(CallbackQueryHandler(tower_diff_right, pattern="^tower_diff_right$"))
    app.add_handler(CallbackQueryHandler(tower_start, pattern="^tower_start$"))
    app.add_handler(CallbackQueryHandler(tower_pick, pattern=r"^tower_pick:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(tower_cashout, pattern="^tower_cashout$"))
    app.add_handler(CallbackQueryHandler(tower_none, pattern="^tower_none$"))

    # Levelup
    app.add_handler(CallbackQueryHandler(levelup_bonus_view, pattern="^bonus_levelup$"))
    app.add_handler(CallbackQueryHandler(level_claim_handler, pattern="^level_claim$"))
    app.add_handler(CallbackQueryHandler(noop_locked_handler, pattern="^noop_locked$"))

    # Menus
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(play_menu, pattern="^play$"))
    app.add_handler(CallbackQueryHandler(bonus_menu, pattern="^bonuses$"))
    app.add_handler(CallbackQueryHandler(more_content_menu, pattern="^more_content$"))
    app.add_handler(CallbackQueryHandler(deposit_menu, pattern="^deposit$"))
    app.add_handler(CallbackQueryHandler(withdraw_menu, pattern="^withdraw$"))







# Roulette command
    app.add_handler(CommandHandler(["roul", "roulette"], roulette_command))

# Roulette buttons
    app.add_handler(CallbackQueryHandler(cb_router))


    await app.run_polling()
    print("✅ Bot is running…")


if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
