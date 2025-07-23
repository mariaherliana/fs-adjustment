import pandas as pd
import re
import numpy as np

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

def generate_voucher_numbers_op(df):
    """Generate OP voucher numbers: OP-YY-MM-XXX"""
    df = df.copy()
    df["Other Payable Voucher No"] = None
    counters = {}

    for idx, row in df.iterrows():
        if isinstance(row["Date"], pd.Timestamp):
            date = row["Date"]
        else:
            date = pd.to_datetime(row["Date"], errors="coerce")

        if pd.isna(date):
            continue

        key = (date.year, date.month)
        if key not in counters:
            counters[key] = 1
        else:
            counters[key] += 1

        df.at[idx, "Other Payable Voucher No"] = f"OP-{str(date.year)[-2:]}-{date.month:02d}-{counters[key]:03d}"

    return df


def add_vendor_subtotals_op(df):
    """Add subtotals per Vendor"""
    df = df.copy()
    result = []

    for vendor, group in df.groupby("Company Name", dropna=False):
        result.append(group)
        subtotal_row = pd.Series("", index=df.columns)
        subtotal_row["Company Name"] = f"{vendor} Subtotal"
        for col in ["Original Amount", "Amount", "Payment Amount", "Ending Balance"]:
            if col in df.columns:
                subtotal_row[col] = group[col].sum()
        result.append(pd.DataFrame([subtotal_row], columns=df.columns))

    return pd.concat(result, ignore_index=True)

def transform_other_payable(df):
    df = df.copy()

    # --- Ensure correct columns ---
    df = df[["Date", "Vendor/Client", "Trans No", "Description", "Currency", "Rate", "Debit", "Credit"]]

    # --- Normalize column names ---
    df.rename(columns={
        "Vendor/Client": "Vendor",
        "Trans No": "Trans_No"
    }, inplace=True)

    # --- Separate OP & Payments ---
    df["is_payment"] = df["Trans_No"].str.contains(r"(paid|top\s*up|topup)", case=False, na=False)

    op_df = df[~df["is_payment"]].copy()
    pay_df = df[df["is_payment"]].copy()

    # Clean Trans_No for OP matching (remove "_paid" or "paid")
    def clean_trans_no(t):
        return re.sub(r"(_?paid)", "", str(t), flags=re.IGNORECASE)

    op_df["Clean_Trans_No"] = op_df["Trans_No"].apply(clean_trans_no)
    pay_df["Clean_Trans_No"] = pay_df["Trans_No"].apply(clean_trans_no)

    # --- Expand multiple payments ---
    expanded_payments = []
    for _, row in pay_df.iterrows():
        trans_list = [t.strip() for t in str(row["Clean_Trans_No"]).split(",")]
        for trans in trans_list:
            expanded_payments.append({
                "Clean_Trans_No": trans,
                "Payment Date": row["Date"],
                "Payment Voucher No": row["Trans_No"],
                "Payment Amount": row["Debit"] if not pd.isna(row["Debit"]) else 0
            })
    pay_expanded_df = pd.DataFrame(expanded_payments).drop_duplicates()

    # --- Merge AP with Payments ---
    merged = ap_df.merge(pay_expanded_df, how="left", on="Clean_Trans_No")
    merged = merged.drop_duplicates(subset=["Clean_Trans_No", "Payment Voucher No"], keep="first")

    # --- Fill Columns ---
    merged["Date"] = pd.to_datetime(merged["Date"], errors="coerce").dt.date
    merged["Currency"] = "IDR"  # default
    merged["Rate"] = 1  # default

    # OP Amount = Debit (since Debit = increase OP)
    merged["Amount"] = merged["Debit"].fillna(0).round()

    # If payment exists, Payment Amount = OP Amount (fully paid assumption)
    merged["Payment Amount"] = np.where(
        merged["Payment Voucher No"].notna(),
        merged["Amount"],  # full payment allocation
        0
    )

    # Ending Balance = Payment Amount - Amount
    merged["Ending Balance"] = merged["Payment Amount"] - merged["Amount"]

    # Generate Voucher No for OP (OP-YY-MM-###)
    merged["Voucher No"] = merged.groupby(
        [merged["Date"].apply(lambda x: f"{x:%y-%m}" if pd.notna(x) else "00-00")]
    ).cumcount() + 1
    merged["Voucher No"] = "OP-" + merged["Date"].apply(lambda x: f"{x:%y-%m}" if pd.notna(x) else "00-00") + "-" + \
                           merged["Voucher No"].astype(str).str.zfill(3)

    # --- Build final dataframe ---
    df_transformed = merged[[
        "Date", "Vendor", "Trans_No", "Voucher No", "Description",
        "Currency", "Debit", "Rate", "Amount",
        "Payment Date", "Payment Voucher No", "Payment Amount", "Ending Balance"
    ]]

    # --- Add Subtotals per Vendor or Reimbursement ---
    # --- Filter only reimbursement transactions (excluding Mailjet) ---
    reimb_group = df_transformed[
        df_transformed["Description"].str.contains("reimbursement", case=False, na=False)
        & ~df_transformed["Description"].str.contains("mailjet", case=False, na=False)
    ]

    # --- Filter the rest of the transactions ---
    normal_group = df_transformed.drop(reimb_group.index)

    # --- 1. Separate reimbursement and normal transactions ---
    reimb_group = df_transformed[
        df_transformed["Description"].str.contains("reimbursement", case=False, na=False)
        & ~df_transformed["Description"].str.contains("mailjet", case=False, na=False)
    ]

    normal_group = df_transformed.drop(reimb_group.index)

    # --- 2. Group normal transactions by vendor (with subtotals as before) ---
    grouped_normal = []
    for vendor, group in normal_group.groupby("Vendor", dropna=False):
        grouped_normal.append(group)
        subtotal_row = pd.Series({
            "Date": "Subtotal " + str(vendor),
            "Vendor": "",
            "Trans_No": "",
            "Voucher No": "",
            "Description": "",
            "Currency": "",
            "Debit": group["Debit"].sum(),
            "Rate": "",
            "Amount": group["Amount"].sum(),
            "Payment Date": "",
            "Payment Voucher No": "",
            "Payment Amount": group["Payment Amount"].sum(),
            "Ending Balance": group["Ending Balance"].sum()
        })
        grouped_normal.append(pd.DataFrame([subtotal_row]))

    df_normal_final = pd.concat(grouped_normal, ignore_index=True)

    # --- 3. Combine reimbursement transactions into one group with one subtotal ---
    if not reimb_group.empty:
        subtotal_reimb = pd.Series({
            "Date": "Subtotal Reimbursement",
            "Vendor": "",
            "Trans_No": "",
            "Voucher No": "",
            "Description": "",
            "Currency": "",
            "Debit": reimb_group["Debit"].sum(),
            "Rate": "",
            "Amount": reimb_group["Amount"].sum(),
            "Payment Date": "",
            "Payment Voucher No": "",
            "Payment Amount": reimb_group["Payment Amount"].sum(),
            "Ending Balance": reimb_group["Ending Balance"].sum()
        })
        df_final = pd.concat([df_normal_final, reimb_group, pd.DataFrame([subtotal_reimb])], ignore_index=True)
    else:
        df_final = df_normal_final

    # Replace NaN with empty string for safe Excel export
    df_final = df_final.replace({np.nan: ""})

    # ✅ Rename columns as requested
    df_final.rename(columns={
        "Vendor": "Company Name",
        "Trans_No": "Inv No",
        "Debit": "Original Amount"
    }, inplace=True)

    return df_final

def extract_trans_nos_from_description(desc):
    """
    Extracts Trans Nos like 0001889/AS/III/2025 from payment description.
    Returns a list of Trans Nos.
    """
    if pd.isna(desc):
        return []
    pattern = r"\d{3,}/[A-Z]+/[A-Z]+/[IVX]+/\d{4}"
    return re.findall(pattern, desc)

def transform_account_payable(df):
    df = df.copy()

    # --- Ensure correct columns ---
    df = df[["Date", "Vendor/Client", "Trans No", "Description", "Debit", "Credit"]]

    # --- Normalize column names ---
    df.rename(columns={
        "Vendor/Client": "Vendor",
        "Trans No": "Trans_No"
    }, inplace=True)

    # --- Separate AP & Payments (match Trans No containing "paid") ---
    df["is_payment"] = df["Trans_No"].str.contains(r"paid", case=False, na=False)

    ap_df = df[~df["is_payment"]].copy()   # Invoice rows
    pay_df = df[df["is_payment"]].copy()   # Payment rows

    # --- Clean Trans_No for matching ---
    def clean_trans_no(t):
        return re.sub(r"(_?paid)", "", str(t), flags=re.IGNORECASE).strip()

    ap_df["Clean_Trans_No"] = ap_df["Trans_No"].apply(clean_trans_no)
    pay_df["Clean_Trans_No"] = pay_df["Trans_No"].apply(clean_trans_no)

    # --- Expand multiple payments (comma-separated Trans No in payment rows) ---
    expanded_payments = []
    for _, row in pay_df.iterrows():
        trans_list = [re.sub(r"(_?paid)", "", t.strip(), flags=re.IGNORECASE)
                      for t in str(row["Clean_Trans_No"]).split(",")]

        for i, trans in enumerate(trans_list):
            expanded_payments.append({
                "Clean_Trans_No": trans,
                "Payment Date": row["Date"],
                "Payment Voucher No": row["Trans_No"],
                # ✅ total payment only once, 0 for the rest
                "Payment Amount": row["Debit"] if i == 0 else 0
            })
    pay_expanded_df = pd.DataFrame(expanded_payments).drop_duplicates()

    # --- Merge AP with Payments ---
    merged = ap_df.merge(
        pay_expanded_df,
        how="left",
        on="Clean_Trans_No"
    )

    # --- Fill Columns ---
    merged["Date"] = pd.to_datetime(merged["Date"], errors="coerce").dt.date
    merged["Currency"] = "IDR"  # default
    merged["Rate"] = 1  # default

    merged["Original Amount"] = merged["Credit"].fillna(0)
    merged["Amount"] = merged["Original Amount"].round()

    merged["Payment Amount"] = merged["Payment Amount"].fillna(0)
    merged["Ending Balance"] = merged["Payment Amount"] - merged["Amount"]

    # ✅ --- Proportional Payment Allocation (run AFTER Original Amount exists) ---
    for pay_voucher, group in merged.groupby("Payment Voucher No"):
        if pd.isna(pay_voucher):
            continue
        # ✅ Just copy Original Amount
        for idx in group.index:
            merged.at[idx, "Payment Amount"] = merged.at[idx, "Original Amount"]

    # --- Ending Balance ---
    merged["Ending Balance"] = merged["Payment Amount"] - merged["Amount"]

    # --- Generate AP Voucher No: AP-YY-MM-####
    merged["Voucher No"] = merged.groupby(
        [merged["Date"].apply(lambda x: f"{x:%y-%m}" if pd.notna(x) else "00-00")]
    ).cumcount() + 1
    merged["Voucher No"] = "AP-" + merged["Date"].apply(lambda x: f"{x:%y-%m}" if pd.notna(x) else "00-00") + "-" + \
                           merged["Voucher No"].astype(str).str.zfill(3)

    # --- Build final dataframe ---
    df_transformed = merged[[
        "Date", "Vendor", "Trans_No", "Voucher No", "Description",
        "Currency", "Original Amount", "Rate", "Amount",
        "Payment Date", "Payment Voucher No", "Payment Amount", "Ending Balance"
    ]]

    # --- Add Subtotals per Vendor ---
    grouped = []
    for vendor, group in df_transformed.groupby("Vendor", dropna=False):
        grouped.append(group)
        subtotal_row = pd.Series({
            "Date": f"Subtotal {vendor}",
            "Vendor": "",
            "Trans_No": "",
            "Voucher No": "",
            "Description": "",
            "Currency": "",
            "Original Amount": group["Original Amount"].sum(),
            "Rate": "",
            "Amount": group["Amount"].sum(),
            "Payment Date": "",
            "Payment Voucher No": "",
            "Payment Amount": group["Payment Amount"].sum(),
            "Ending Balance": group["Ending Balance"].sum()
        })
        grouped.append(pd.DataFrame([subtotal_row]))

    df_final = pd.concat(grouped, ignore_index=True)

    # ✅ Rename columns as required
    df_final.rename(columns={
        "Vendor": "Company Name",
        "Trans_No": "Inv No"
    }, inplace=True)

    # Replace NaN with empty string for safe Excel export
    df_final = df_final.replace({np.nan: ""})

    return df_final
