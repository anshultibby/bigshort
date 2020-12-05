import pandas as pd
import numpy as np
import inspect
from openpyxl import load_workbook


def main():
    path = "purchasing.xlsx"
    book = load_workbook(path)
    reader = pd.ExcelWriter(path, engine = 'openpyxl')

    xls = pd.ExcelFile(path)

    path = "summary.xlsx"
    writer = pd.ExcelWriter(path, engine = 'openpyxl')


    date_aggregate = {"Date": [], "Qty": [], "Total Cost": [], "avg day cost": []}
    for sheet_name in xls.sheet_names:
        if sheet_name != "summary":
            s1 = pd.read_excel(reader, sheet_name=sheet_name).fillna(0)
            s1["Date"] = sheet_name
            sums, computed = aggregate_costs(s1)
            computed.to_excel(writer, sheet_name=sheet_name)

            day_agg = computed.loc[computed["Particular "] == "Sum"].reset_index()
            date_aggregate["Date"].append(day_agg.Date[0])
            date_aggregate["Qty"].append(day_agg.Qty[0])
            date_aggregate["Total Cost"].append(day_agg.Total[0])
            date_aggregate["avg day cost"].append(day_agg.Total[0] / day_agg.Qty[0])

    date_aggregate["Date"].append("Month")
    total_q = np.sum(date_aggregate["Qty"])
    date_aggregate["Qty"].append(total_q)
    total_c = np.sum(date_aggregate["Total Cost"])
    date_aggregate["Total Cost"].append(total_c)
    date_aggregate["avg day cost"].append(total_c / total_q)

    summary = pd.DataFrame.from_dict(date_aggregate)
    summary.to_excel(writer, sheet_name="Summary")
    writer.save()


def aggregate_costs(s1):
    s1["Value"] = s1.Qty * s1.Rate
    sums = s1.groupby("Particular ").sum()
    sums["Dealer Total"] = sums["Value"] + sums["Fright"] + sums["Expenses"] + sums["R/off"]
    sums["Avg Cost"] = sums["Total"] / sums["Qty"]
    sums["Particular "] = sums.index

    for i, p in enumerate(s1["Particular "]):
        customer_cost = sums.loc[sums["Particular "] == p]["Avg Cost"][0]
        s1["Avg Cost"][i] = customer_cost

    s1["Cost per lot"] = s1["Avg Cost"] * s1["Qty"]
    s1 = add_sum_and_mean(s1)
    return sums, s1


def get_mean_by_qty(df):
    df = df.copy()
    qty = df["Qty"]
    for i in list(df.keys()):
        try:
            df[i] = df[i] / qty
        except(TypeError):
            df[i] = df[i]
    return df


def add_sum_and_mean(s1):
    s1_sum = s1.sum()
    s1_sum["Particular "] = "Sum"
    s1_sum["Date"] = s1.Date[0]

    s1_mean = get_mean_by_qty(s1_sum)
    s1_mean["Particular "] = "Mean"

    s2 = s1.append(s1_sum, ignore_index=True)
    s2 = s2.append(s1_mean, ignore_index=True)
    return s2

if __name__ == "__main__":
    main()