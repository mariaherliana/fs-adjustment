import pandas as pd

def transform_advance_payment(df):
    # Normalize column names
    df.columns = df.columns.str.strip()

    # Convert Debit & Credit to numbers
    df["Debit"] = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
    df["Credit"] = pd.to_numeric(df["Credit"], errors="coerce").fillna(0)

    # Split debit (advances) and credit (payments)
    advances = df[df["Debit"] > 0].copy()
    payments = df[df["Credit"] > 0].copy()

    used_payment_indices = set()
    output_rows = []

    for _, adv in advances.iterrows():
        adv_date = adv["Date"]
        adv_voucher = adv.get("Trans No", "")
        adv_company = adv.get("Vendor/Client", "")
        adv_desc = adv.get("Description", "")
        adv_amount = adv["Debit"]

        matched = False

        for i, pay in payments.iterrows():
            if i not in used_payment_indices and adv_amount == pay["Credit"]:
                # Strict match found (amount only)
                output_rows.append({
                    "Date": adv_date,
                    "Voucher No": adv_voucher,
                    "Company Name": adv_company,
                    "Description": adv_desc,
                    "Amount": adv_amount,
                    "Payment Date": pay["Date"],
                    "Payment Voucher No": pay.get("Trans No", ""),
                    "Payment Amount": pay["Credit"],
                    "Outstanding": 0
                })
                used_payment_indices.add(i)
                matched = True
                break

        if not matched:
            # No matching payment found
            output_rows.append({
                "Date": adv_date,
                "Voucher No": adv_voucher,
                "Company Name": adv_company,
                "Description": adv_desc,
                "Amount": adv_amount,
                "Payment Date": "",
                "Payment Voucher No": "",
                "Payment Amount": 0,
                "Outstanding": adv_amount
            })

    result_df = pd.DataFrame(output_rows)

    # === Append TOTAL row ===
    total_row = {
        "Date": "TOTAL",
        "Voucher No": "",
        "Company Name": "",
        "Description": "",
        "Amount": result_df["Amount"].sum(),
        "Payment Date": "",
        "Payment Voucher No": "",
        "Payment Amount": result_df["Payment Amount"].sum(),
        "Outstanding": result_df["Outstanding"].sum()
    }
    result_df = pd.concat([result_df, pd.DataFrame([total_row])], ignore_index=True)

    return result_df
