import math

import numpy as np
import pandas as pd
import robin_stocks as r
import datetime as dt


def remove_unviable_trades(df):
    viable = df.loc[df.sell_bid_price > 0]
    viable = viable.loc[viable.viable > 0.1]
    viable = viable.loc[viable.sell_bid_price > 0]
    viable = viable.loc[viable.expected_loss < 60]
    viable = viable.loc[viable.debit < 0.75 * viable.exit_value]
    illegal = []
    viable = viable.reset_index()
    for i, exit in enumerate(viable.exit_value):
        if exit < 0 and viable.debit[i] < 0:
            illegal.append(-1)
        else:
            illegal.append(1)
    viable["illegal"] = np.array(illegal)
    viable = viable.loc[viable.illegal > 0]
    return viable


def find_weekly_movement(symbol, interval="week", span="3month"):
    history = r.stocks.get_stock_historicals(symbol, interval, span)
    moves = []
    for i, h in enumerate(history):
        if i == 0:
            opening = h["open_price"]
        else:
            opening = closing

        closing = h["close_price"]
        move = float(closing) - float(opening)
        moves.append(move)

    return np.mean(moves), np.std(moves), np.sum(moves)


def find_viable_options(price, price_search, options):
    viable = []
    for option in options:
        strike = float(option["strike_price"])
        if (price - price_search) <= strike <= (price + price_search):
            viable.append(option)
    return viable


# create a list of dicts containing instrument and market data
def get_market_data(symbol, viable, expiration):
    buy_options = []
    for option in viable:
        option_info = dict()
        option_info["instrument"] = option
        option_info["strike"] = float(option["strike_price"])
        market = r.options.get_option_market_data(symbol, expiration,
                                                  option["strike_price"], "call")[0][0]
        option_info["market"] = market

        market_keys = ["bid_price", "ask_price", "chance_of_profit_long",
                       "chance_of_profit_short", "delta", "gamma", "implied_volatility",
                       "rho", "theta", "vega", "ask_size", "bid_size",
                       'low_fill_rate_buy_price', 'low_fill_rate_sell_price']
        for key in market_keys:
            if market[key] is None:
                option_info[key] = 0
            else:
                option_info[key] = float(market[key])

        buy_options.append(option_info)
    return buy_options


def extract_possible_trades(buy_options, sell_options):
    orders = ["buy", "sell"]
    metrics = ['strike', 'ask_price', 'bid_price', 'chance_of_profit_long',
               'chance_of_profit_short', 'low_fill_rate_buy_price',
               'low_fill_rate_sell_price', 'delta']
    possible = dict()
    for order in orders:
        for m in metrics:
            possible[f"{order}_{m}"] = []

    for buy in buy_options:
        for sell in sell_options:
            option_types = [buy, sell]
            for i in range(2):
                for m in metrics:
                    key = f"{orders[i]}_{m}"
                    possible[key].append(option_types[i][m])

    possible = pd.DataFrame(possible)
    return possible


# http://tastytradenetwork.squarespace.com/tt/blog/probability-of-profit
def compute_profitability(possible, price, mean_move):
    buy_deltas = {}
    for i, strike in enumerate(possible["buy_strike"]):
        buy_deltas[strike] = possible["buy_delta"][i]

    buy_price = possible["buy_low_fill_rate_buy_price"]
    sell_price = possible["sell_low_fill_rate_sell_price"]

    possible["exercise_probs"] = possible["sell_delta"]
    calendar_probs = []
    calendar_moves = []
    for strike in possible["buy_strike"]:
        calendar = strike + abs(mean_move)
        while calendar not in buy_deltas:
            calendar -= 0.5
            if calendar < 0:
                break
        if calendar not in buy_deltas:
            calendar_probs.append(0)
            calendar_moves.append(0)
        else:
            calendar_probs.append(buy_deltas[calendar])
            calendar_moves.append(calendar - strike)
    calendar_probs = np.array(calendar_probs)
    possible["loss_probs"] = (1 - possible.exercise_probs) * (1 - calendar_probs)
    possible["calendar_probs"] = (1 - possible.exercise_probs) * calendar_probs
    possible["calendar_moves"] = calendar_moves

    possible['debit'] = buy_price - sell_price
    possible['price'] = price
    possible['exit_value'] = possible['sell_strike'] - possible['buy_strike']
    possible['viable'] = possible['exit_value'] - possible['debit']
    possible['odds'] = possible['exit_value'] / possible['debit']
    possible['price_distance'] = possible['buy_strike'] - price
    possible['exercise_profit'] = ((possible['exit_value'] * 100 / possible.debit))
    possible['calendar_profit'] = ((possible.buy_strike - price + possible.calendar_moves + sell_price) * 100) / possible.debit
    possible['loss'] = 100

    # 100 - [(the max profit / strike price width) x 100].
    possible["pop"] = possible["sell_delta"]
    possible["pol"] = 1 - possible["pop"]

    possible['expected_calendar'] = possible.calendar_probs * possible.calendar_profit
    possible['expected_loss'] = possible.loss_probs * possible.loss
    possible['expected_exercise'] = possible.exercise_probs * possible.exercise_profit

    possible['EV'] = possible["expected_exercise"] + possible["expected_calendar"] - possible["expected_loss"]
    best_bets = possible.sort_values(by="EV")
    best_bets = possible
    return possible, best_bets


def find_debit_spread_profitability(symbol, calendar_start=0, calendar_duration=1, buy_options=None, sell_options=None):
    # indentify a stock
    duration = calendar_start + calendar_duration  # how many option expiries in between calendar
    avg_move, std_move, _ = find_weekly_movement(symbol, interval="week", span="month")
    price_search = math.ceil(avg_move + std_move / 2)
    print(f"Avg move of stock is {avg_move} and std_move is {std_move}")

    # get current stock price
    price = float(r.stocks.get_latest_price(symbol)[0])
    print(f"{symbol} has curr price: {price} and price_search_criteria: {price_search}")

    # get relevant chains
    chains = r.options.get_chains(symbol)
    expirations = chains["expiration_dates"]

    buy_expiration = expirations[duration]
    sell_expiration = expirations[calendar_start]
    start_date = dt.date.fromisoformat(expirations[0])
    buy_date = dt.date.fromisoformat(buy_expiration)
    diff_days = (buy_date - start_date).days
    price_search = price_search * (diff_days / 7)
    print(f"Price search criteria adjusted to {price_search} as buy and sell have gap of {diff_days} days")

    # select buy and sell orders for debit spread
    buy = r.options.find_tradable_options(symbol, buy_expiration, optionType="call")
    print(f"Buy call for {expirations[duration]}")
    sell = r.options.find_tradable_options(symbol, sell_expiration, optionType="call")
    print(f"Sell call for {expirations[calendar_start]}")

    # find all viable trades based on price move range
    print("get viable option trades")
    viable_buy = find_viable_options(price, price_search, buy)
    viable_sell = find_viable_options(price, price_search, sell)

    # get market data for viables
    print("get market data for options to buy")
    if buy_options is None:
        buy_options = get_market_data(symbol, viable_buy, buy_expiration)
    print("get market data for options to sell")
    if sell_options is None:
        sell_options = get_market_data(symbol, viable_sell, sell_expiration)

    # find profitability table
    print("find profitability")
    possible = extract_possible_trades(buy_options, sell_options)
    possible, best_bets = compute_profitability(possible, price, round(price_search))
    return possible, best_bets, buy_options, sell_options
