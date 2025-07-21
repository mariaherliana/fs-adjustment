import pandas as pd

def transform_temp_receipt(df):
    # Normalize column names to lowercase for consistency
    df = df.rename(columns={
        "Date": "date",
        "Vendor/Client": "company",
        "Trans No": "voucher",
        "Description": "description",
        "Debit": "debit",
        "Credit": "credit"
    })
    
    # Ensure numeric columns are numbers (remove commas, convert to int)
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0)

    # Separate Temporary Receipt (Credit) and Payments (Debit)
    tr_df = df[df["credit"] > 0].copy()
    pay_df = df[df["debit"] > 0].copy()

    matched_rows = []
    used_payment_idx = set()

    for idx, tr_row in tr_df.iterrows():
        tr_amount = tr_row["credit"]
        
        # Find first available matching payment (exact amount match)
        payment_match = pay_df[
            (pay_df["debit"] == tr_amount) &
            (~pay_df.index.isin(used_payment_idx))
        ]

        if not payment_match.empty:
            pay_idx = payment_match.index[0]
            pay_row = pay_df.loc[pay_idx]

            matched_rows.append({
                "TR Date": tr_row["date"],
                "TR Voucher": tr_row["voucher"],
                "Company Name": tr_row["company"],
                "TR Description": tr_row["description"],
                "TR Amount": tr_amount,
                "Payment Date": pay_row["date"],
                "Payment Voucher": pay_row["voucher"],
                "Payment Amount": pay_row["debit"],
                "Outstanding": tr_amount - pay_row["debit"]
            })

            used_payment_idx.add(pay_idx)
        else:
            # No payment match found
            matched_rows.append({
                "TR Date": tr_row["date"],
                "TR Voucher": tr_row["voucher"],
                "Company Name": tr_row["company"],
                "TR Description": tr_row["description"],
                "TR Amount": tr_amount,
                "Payment Date": "",
                "Payment Voucher": "",
                "Payment Amount": 0,
                "Outstanding": tr_amount
            })

    result_df = pd.DataFrame(matched_rows)

    # ✅ Add Total Row
    total_row = {
        "TR Date": "TOTAL",
        "TR Voucher": "",
        "Company Name": "",
        "TR Description": "",
        "TR Amount": result_df["TR Amount"].sum(),
        "Payment Date": "",
        "Payment Voucher": "",
        "Payment Amount": result_df["Payment Amount"].sum(),
        "Outstanding": result_df["Outstanding"].sum()
    }
    result_df = pd.concat([result_df, pd.DataFrame([total_row])], ignore_index=True)

    return result_df


if __name__ == "__main__":
    # Example usage
    input_file = "temporary_receipt.xlsx"  # Update with your input file
    output_file = "temporary_receipt_matched.xlsx"

    df_input = pd.read_excel(input_file)
    result_df = transform_temp_receipt(df_input)

    result_df.to_excel(output_file, index=False)
    print(f"✅ Matching completed! Result saved to: {output_file}")
