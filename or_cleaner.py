import pandas as pd

def transform_other_receivable(df):
    # === Normalize columns ===
    df.columns = df.columns.str.strip()

    # Convert to numeric
    df["Debit"] = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
    df["Credit"] = pd.to_numeric(df["Credit"], errors="coerce").fillna(0)

    # Separate OR (debit) and payments (credit)
    ors = df[df["Debit"] > 0].copy().reset_index(drop=True)
    payments = df[df["Credit"] > 0].copy().reset_index(drop=True)

    used_payments = set()
    output_rows = []

    for _, or_row in ors.iterrows():
        or_amount = round(or_row["Debit"])
        matched = False

        for idx, pay_row in payments.iterrows():
            pay_amount = round(pay_row["Credit"])

            # STRICT match: only when amounts equal and not used before
            if pay_amount == or_amount and idx not in used_payments:
                used_payments.add(idx)
                output_rows.append({
                    "Date": or_row["Date"],
                    "Inv No": "",
                    "Voucher No": or_row.get("Trans No", ""),
                    "Company Name": or_row.get("Vendor/Client", ""),
                    "Description": or_row.get("Description", ""),
                    "Currency": "IDR",
                    "Original Amount": or_row["Debit"],
                    "Original Rate": 1,
                    "Amount": or_amount,
                    "Payment Date": pay_row["Date"],
                    "Payment Voucher No": pay_row.get("Trans No", ""),
                    "Payment Amount": pay_amount,
                    "Ending Balance": 0
                })
                matched = True
                break

        if not matched:
            output_rows.append({
                "Date": or_row["Date"],
                "Inv No": "",
                "Voucher No": or_row.get("Trans No", ""),
                "Company Name": or_row.get("Vendor/Client", ""),
                "Description": or_row.get("Description", ""),
                "Currency": "IDR",
                "Original Amount": or_row["Debit"],
                "Original Rate": 1,
                "Amount": or_amount,
                "Payment Date": "",
                "Payment Voucher No": "",
                "Payment Amount": 0,
                "Ending Balance": or_amount
            })

    result_df = pd.DataFrame(output_rows)

    # === Add TOTAL row ===
    total_row = {
        "Date": "TOTAL",
        "Inv No": "",
        "Voucher No": "",
        "Company Name": "",
        "Description": "",
        "Currency": "",
        "Original Amount": result_df["Original Amount"].sum(),
        "Original Rate": "",
        "Amount": result_df["Amount"].sum(),
        "Payment Date": "",
        "Payment Voucher No": "",
        "Payment Amount": result_df["Payment Amount"].sum(),
        "Ending Balance": result_df["Ending Balance"].sum()
    }
    result_df = pd.concat([result_df, pd.DataFrame([total_row])], ignore_index=True)

    return result_df
