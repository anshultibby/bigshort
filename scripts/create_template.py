import pandas as pd

def create_template(path, month=11):
    writer = pd.ExcelWriter(path, engine = 'openpyxl')
    columns = {"Date": [], "Particular": [], "Qty": [], "Rate": [], "Value": [],
              "Freight": [], "Expenses": [], "R/off": []}
    empty = pd.DataFrame.from_dict(columns)
    empty.index.name = "Sr. No"
    for i in range(1, 32):
        sheet_name = f"{i}.{month}"
        empty.to_excel(writer, sheet_name=sheet_name)
    writer.save()

def main():
    create_template("test.xls")

if __name__ == "__main__":
    main()