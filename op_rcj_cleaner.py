import pandas as pd

def transform_other_payable_rcj(df):
    # Clean columns
    df.columns = df.columns.str.strip()

    # Ensure numeric
    df["Debit"] = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
    df["Credit"] = pd.to_numeric(df["Credit"], errors="coerce").fillna(0)

    grouped = []
    for trans_no, group in df.groupby("Trans No"):
        base_row = group.iloc[0]
        amount = group.loc[group["Account Name"] == "Other Payable", "Debit"].sum()
        exch_loss = -group.loc[group["Account Name"] == "Exchange Loss", "Debit"].sum()
        exch_gain = group.loc[group["Account Name"] == "Exchange Gain", "Credit"].sum()
        exchange_gain_loss = exch_loss + exch_gain
        amount_after = group.loc[group["Account Name"] == "Other Payable (Revcomm Japan)", "Credit"].sum()

        payment_amount = ""  # Leave blank for now
        outstanding = amount - amount if payment_amount == "" else amount - payment_amount

        grouped.append({
            "Date": base_row["Date"],
            "Voucher No": trans_no,
            "Company Name": "RevComm Japan",
            "Description": base_row["Description"],
            "Currency": "IDR",
            "Amount": amount if amount != 0 else "",
            "Exchange Gain/Loss": exchange_gain_loss if exchange_gain_loss != 0 else "",
            "Amount After Exchange Gain/Loss": amount_after if amount_after != 0 else "",
            "Payment Date": "",
            "Payment Voucher No": "",
            "Payment Amount": payment_amount,
            "Outstanding": (amount if payment_amount == "" else amount - payment_amount),
            "Remark": ""
        })

    df_cleaned = pd.DataFrame(grouped)

    # Add total row
    total_row = pd.DataFrame([{
        "Date": "TOTAL",
        "Voucher No": "",
        "Company Name": "",
        "Description": "",
        "Currency": "",
        "Amount": df_cleaned["Amount"].replace("", 0).sum(),
        "Exchange Gain/Loss": df_cleaned["Exchange Gain/Loss"].replace("", 0).sum(),
        "Amount After Exchange Gain/Loss": df_cleaned["Amount After Exchange Gain/Loss"].replace("", 0).sum(),
        "Payment Date": "",
        "Payment Voucher No": "",
        "Payment Amount": "",
        "Outstanding": df_cleaned["Outstanding"].replace("", 0).sum(),
        "Remark": ""
    }])

    return pd.concat([df_cleaned, total_row], ignore_index=True)
