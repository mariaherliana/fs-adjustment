import pandas as pd

def transform_prepaid_pph23(df):
    # === Normalize column names ===
    df.columns = df.columns.str.strip()

    # Drop rows with no Customer Name
    df = df[df["Customer Name"].notna() & (df["Customer Name"].astype(str).str.strip() != "")]

    # Convert numeric columns
    df["WHT Base"] = pd.to_numeric(df.get("WHT Base", 0), errors="coerce").fillna(0)
    df["WHT Rate (%)"] = pd.to_numeric(df.get("WHT Rate (%)", 0), errors="coerce").fillna(0)
    df["WHT Amount (IDR)"] = pd.to_numeric(df.get("WHT Amount (IDR)", 0), errors="coerce").fillna(0)
    df["Refund/Return WHT (IDR)"] = pd.to_numeric(df.get("Refund/Return WHT (IDR)", 0), errors="coerce").fillna(0)

    # Default WHT Rate to 2% if 0 or NaN
    df.loc[df["WHT Rate (%)"] == 0, "WHT Rate (%)"] = 2

    # Compute final Withholding Tax Amount (IDR)
    df["Withholding Tax Amount (IDR)"] = df["WHT Amount (IDR)"] - df["Refund/Return WHT (IDR)"]

    # Default Description → "Sales Invoice to {Customer}"
    df["Description"] = "Sales Invoice to " + df["Customer Name"].astype(str)

    # Map to expected columns
    result_df = pd.DataFrame({
        "Date": df.get("Date", ""),
        "Voucher No": df.get("Voucher No", ""),
        "Invoice No": df.get("Inv No", ""),
        "Company Name": df.get("Customer Name", ""),
        "Description": df["Description"],
        "Bukti Potong": "-",
        "Withholding Article 23 Tax Base": df["WHT Base"],
        "Withholding Tax Article 23 Rate (%)": df["WHT Rate (%)"],
        "Withholding Tax Amount (IDR)": df["Withholding Tax Amount (IDR)"]
    })

    # === Append TOTAL Row ===
    total_row = {
        "Date": "TOTAL",
        "Voucher No": "",
        "Invoice No": "",
        "Company Name": "",
        "Description": "",
        "Bukti Potong": "",
        "Withholding Article 23 Tax Base": result_df["Withholding Article 23 Tax Base"].sum(),
        "Withholding Tax Article 23 Rate (%)": "",
        "Withholding Tax Amount (IDR)": result_df["Withholding Tax Amount (IDR)"].sum()
    }
    result_df = pd.concat([result_df, pd.DataFrame([total_row])], ignore_index=True)

    return result_df
