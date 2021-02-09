import robin_stocks as r
import numpy as np
import pandas as pd
from datetime import datetime as dt


def isfloat(value):
  try:
    float(value)
    return True
  except ValueError:
    return False


# # Create a csv of current portfolio with different params as cols(loss, profit, market value)
def create_open_options_df():
    positions = r.options.get_open_option_positions()
    df = {}

    positions = positions
    for p in positions:
        df = append_dicts(df, p)

        market_data = r.get_option_market_data_by_id(p["option_id"])
        df = append_dicts(df, market_data[0])

        instrument_data = r.get_option_instrument_data_by_id(p["option_id"])
        instrument_keys = ["expiration_date", "issue_date", "strike_price"]
        instrument_data = {k: instrument_data[k] for k in instrument_keys}
        df = append_dicts(df, instrument_data)
    df = pd.DataFrame(df)
    return df


def append_dicts(base_dict, add_dict):
    for key in add_dict.keys():
        value = add_dict[key]

        if type(value) is dict:
            value = 0
        if value is None:
            value = 0

        if isfloat(value):
            value = float(value)

        if key in base_dict:
            base_dict[key].append(value)
        else:
            base_dict[key] = [value]
    return base_dict


def calc_expiration_days(expire, today):
    expire = dt.fromisoformat(expire)
    today = dt.fromisoformat(today)
    return expire - today
