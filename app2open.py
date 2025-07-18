import streamlit as st
import pandas as pd
from io import BytesIO

# --------------------
# Helper Functions
# --------------------

def clean_ar_data(df):
    """Cleans AR data exported from Accurate Accounting"""
    df = df.copy()
    df.columns = df.columns.str.strip()
    df = df[df["Date"].notna() & df["Customer"].notna()]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    numeric_cols = ["Original Amount", "Rate", "Amount", "Payment Amount", "Ending Balance"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

def generate_voucher_numbers(df, date_col="Date"):
    df = df.copy()
    df["YearMonth"] = pd.to_datetime(df[date_col]).dt.strftime("%y-%m")
    df = df.sort_values(by=["YearMonth", date_col])
    counters = {}
    voucher_numbers = []
    for ym in df["YearMonth"]:
        counters[ym] = counters.get(ym, 0) + 1
        voucher_numbers.append(f"AR-{ym}-{counters[ym]:03d}")
    df["Sales Invoice Voucher No"] = voucher_numbers
    df.drop(columns=["YearMonth"], inplace=True)
    return df

def transform_account_receivable(df):
    df = clean_ar_data(df)
    df_transformed = pd.DataFrame({
        "Sales Invoice Date": pd.to_datetime(df["Date"]).dt.date,
        "Sales Invoice No": df["Invoice No"],
        "Customer": df["Customer"],
        "Sales Invoice Description": df["Description"],
        "Currency": "IDR",
        "Sales Invoice Amount": df["Original Amount"],
        "Rate": df["Rate"],
        "Amount": df["Original Amount"].round()
    })
    df_transformed = pd.concat([df_transformed, df[["Date"]]], axis=1)
    df_transformed = generate_voucher_numbers(df_transformed, date_col="Date")
    df_transformed.drop(columns=["Date"], inplace=True)
    df_transformed["Sales Receipt Date"] = df["Payment Date"]
    df_transformed["Sales Receipt Voucher No"] = df["Voucher No"]
    df_transformed["Sales Receipt Amount"] = df["Payment Amount"]
    df_transformed["Ending Balance"] = df["Ending Balance"]
    return df_transformed

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:  # ✅ changed to openpyxl
        df.to_excel(writer, index=False, sheet_name="AR_Keystone")
    return output.getvalue()

# --------------------
# Streamlit App
# --------------------

def main():
    st.set_page_config(page_title="Data Cleanup Wizard", layout="wide")
    st.title("🧹 Internal Data Cleanup Wizard")

    step = st.sidebar.radio("Select Process Type", [
        "Advance Payment", "Other Payable", "Account Payable",
        "Temporary Receipt", "Advance Sales", "Account Receivable", "Other Receivable"
    ])

    if step == "Account Receivable":
        st.subheader("📥 Upload AR File")
        uploaded_file = st.file_uploader("Upload AR.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to AR Keystone Format"):
                transformed_df = transform_account_receivable(df)
                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head())
                st.download_button(
                    label="📥 Download AR Keystone Excel",
                    data=to_excel(transformed_df),
                    file_name="AR_Keystone_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload AR.xlsx to proceed.")
    else:
        st.warning(f"⚠️ The '{step}' process is not implemented yet.")


if __name__ == "__main__":
    main()