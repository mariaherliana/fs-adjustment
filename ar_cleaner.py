import pandas as pd

def generate_voucher_numbers(df, date_col="Sales Invoice Date"):
    df = df.copy()
    df["YearMonth"] = pd.to_datetime(df[date_col]).dt.strftime("%y-%m")
    df = df.sort_values(by=[date_col])

    counters = {}
    voucher_numbers = []

    for ym in df["YearMonth"]:
        counters[ym] = counters.get(ym, 0) + 1
        voucher_numbers.append(f"AR-{ym}-{counters[ym]:03d}")

    df["Sales Invoice Voucher No"] = voucher_numbers
    df.drop(columns=["YearMonth"], inplace=True)
    return df

def match_sales_receipts(df):
    df = df.copy()

    invoices = df[df["Transaction Type"].str.lower().str.contains("invoice", na=False)].copy()
    receipts = df[df["Transaction Type"].str.lower().str.contains("receipt", na=False)].copy()

    invoices["Sales Receipt Date"] = None
    invoices["Sales Receipt Voucher No"] = None
    invoices["Sales Receipt Amount"] = 0

    print("\n=== DEBUGGING MATCHING RECEIPTS ===")

    for idx, inv_row in invoices.iterrows():
        cust = str(inv_row["Customer"]).strip()
        desc = str(inv_row["Description"]).strip()
        inv_no = str(inv_row["Invoice No"]).strip()

        # Try exact match by Customer and Invoice No in description
        receipt_match = receipts[
            (receipts["Customer"].astype(str).str.strip() == cust) &
            (receipts["Description"].astype(str).str.contains(inv_no, case=False, na=False))
        ]

        if receipt_match.empty:
            print(f"❌ No receipt found for Invoice {inv_no} | Customer: {cust} | Desc: {desc}")
        else:
            first_receipt = receipt_match.iloc[0]
            print(f"✅ MATCH FOUND for Invoice {inv_no}: {first_receipt['Voucher No']} | {first_receipt['Payment Date']}")

            invoices.at[idx, "Sales Receipt Date"] = pd.to_datetime(first_receipt["Date"], errors="coerce").date()
            invoices.at[idx, "Sales Receipt Voucher No"] = first_receipt["Voucher No"]
            invoices.at[idx, "Sales Receipt Amount"] = first_receipt["Payment Amount"]

    return invoices


def add_customer_subtotals(df):
    """Add subtotal rows per customer"""
    groups = []
    for cust, group in df.groupby("Customer"):
        groups.append(group)
        subtotal_row = pd.Series({
            "Sales Invoice Date": None,
            "Sales Invoice No": None,
            "Sales Invoice Voucher No": None,
            "Customer": f"{cust} Subtotal",
            "Sales Invoice Description": None,
            "Currency": "IDR",
            "Sales Invoice Amount": group["Sales Invoice Amount"].sum(),
            "Rate": None,
            "Amount": group["Amount"].sum(),
            "Sales Receipt Date": None,
            "Sales Receipt Voucher No": None,
            "Sales Receipt Amount": group["Sales Receipt Amount"].sum(),
            "Ending Balance": group["Ending Balance"].sum()
        })
        groups.append(pd.DataFrame([subtotal_row]))

    return pd.concat(groups, ignore_index=True)


def transform_account_receivable(df):
    df = df.copy()
    df.columns = df.columns.str.strip()  # remove leading/trailing spaces

    # Filter required columns
    df = df[[
        "Date", "Invoice No", "Transaction Type", "Customer",
        "Description", "Currency", "Original Amount", "Rate",
        "Amount", "Payment Date", "Voucher No", "Payment Amount"
    ]]

    # Match receipts to invoices
    invoices = match_sales_receipts(df)

    # Build transformed dataframe
    df_transformed = pd.DataFrame({
        "Sales Invoice Date": pd.to_datetime(invoices["Date"], errors="coerce").dt.date,
        "Sales Invoice No": invoices["Invoice No"],
        "Customer": invoices["Customer"],
        "Sales Invoice Description": invoices["Description"],
        "Currency": invoices["Currency"].fillna("IDR"),
        "Sales Invoice Amount": invoices["Original Amount"],
        "Rate": 1,
        "Amount": invoices["Original Amount"].round(),
        "Sales Receipt Date": invoices["Sales Receipt Date"],  # ✅ Now already correct
        "Sales Receipt Voucher No": invoices["Sales Receipt Voucher No"],
        "Sales Receipt Amount": invoices["Sales Receipt Amount"],
    })

    # Ending Balance = Payment Amount - Amount
    df_transformed["Ending Balance"] = df_transformed["Sales Receipt Amount"] - df_transformed["Amount"]

    # Generate AR Voucher Numbers
    df_transformed = generate_voucher_numbers(df_transformed)

    # Reorder columns
    df_transformed = df_transformed[[
        "Sales Invoice Date", "Sales Invoice No", "Sales Invoice Voucher No",
        "Customer", "Sales Invoice Description", "Currency",
        "Sales Invoice Amount", "Rate", "Amount",
        "Sales Receipt Date", "Sales Receipt Voucher No", "Sales Receipt Amount",
        "Ending Balance"
    ]]

    # Add subtotals per customer
    df_transformed = add_customer_subtotals(df_transformed)

    return df_transformed