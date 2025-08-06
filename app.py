import streamlit as st
import pandas as pd
from io import BytesIO
import numpy as np
from ar_cleaner import transform_account_receivable, transform_other_payable, transform_account_payable
from as_cleaner import transform_advance_sales
from temp_receipt_cleaner import transform_temp_receipt
from adv_payment_cleaner import transform_advance_payment
from prepaid_pph23_cleaner import transform_prepaid_pph23
from or_cleaner import transform_other_receivable
from op_rcj_cleaner import transform_other_payable_rcj
from rou_calculator import transform_rou_calculator
from deferral_revenue import transform_deferral_revenue
from customer_dict import customer_dict
from exchange_rate_calculator import get_exchange_rates

def to_excel(df, engine="xlsxwriter"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine=engine) as writer:
        df.to_excel(writer, index=False, sheet_name="Report", startrow=1)

        if engine == "xlsxwriter":
            workbook = writer.book
            worksheet = writer.sheets["Report"]

            # === Payment Header Merged ===
            if "Payment Date" in df.columns and "Payment Amount" in df.columns:
                payment_format = workbook.add_format({
                    "bold": True,
                    "align": "center",
                    "valign": "vcenter",
                    "border": 1,
                    "bg_color": "#D9EAD3"  # Light green
                })
                payment_start_col = df.columns.get_loc("Payment Date")
                payment_end_col = df.columns.get_loc("Payment Amount")
                worksheet.merge_range(
                    0, payment_start_col, 0, payment_end_col,
                    "Payment", payment_format
                )

            # === Normal Header ===
            header_format = workbook.add_format({
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "border": 1
            })
            for col_num, value in enumerate(df.columns):
                worksheet.write(1, col_num, value, header_format)

            # === Subtotal Row Formatting (Black bg + White font) ===
            subtotal_format = workbook.add_format({
                "bold": True,
                "font_color": "white",
                "bg_color": "black",
                "border": 1,
                "num_format": "#,##0.00"
            })

            # === TOTAL Row Formatting (Yellow bg + Black font) ===
            total_format = workbook.add_format({
                "bold": True,
                "font_color": "black",
                "bg_color": "yellow",
                "border": 1,
                "num_format": "#,##0.00"
            })

            last_row_idx = len(df) + 1  # +1 because headers start at row 1

            # Write rows (apply different formatting if needed)
            for row_num, row_data in enumerate(df.itertuples(index=False), start=2):
                is_subtotal = (
                    isinstance(row_data[0], str) and "Subtotal" in row_data[0]
                )
                for col_num, cell_value in enumerate(row_data):
                    if pd.isna(cell_value):
                        cell_value = ""
                    if is_subtotal:
                        worksheet.write(row_num, col_num, cell_value, subtotal_format)
                    elif row_num == last_row_idx:
                        worksheet.write(row_num, col_num, cell_value, total_format)

            # Auto-adjust column widths
            for i, col in enumerate(df.columns):
                max_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, max_width)

    return output.getvalue()

def main():
    st.set_page_config(page_title="Accuria", layout="wide")
    st.title("🧹 Accuria Data Cleanup")
    st.markdown("""
    Welcome to **Accuria Data Cleanup**!  
    This tool helps you clean and transform accounting data from Accurate Accounting, including:
    - **Advance Sales Adjustments**
    - **Account Receivable & Payable Reports**
    - **Other Payable Cleanups**

    👉 **Upload your file on the left panel to get started.**
    """)
    st.warning("Make sure your file format matches the required template before uploading.")

    step = st.sidebar.radio("Select Process Type", [
        "Advance Payment",
        "Other Payable",
        "Other Payable(RCJ)",
        "Account Payable",
        "Temporary Receipt",
        "Advance Sales",
        "Deferral Revenue",
        "Account Receivable",
        "Other Receivable",
        "Prepaid PPh 23",
        "Exchange Rate Calculator",
        "ROU Calculator",
    ])

    if step == "Account Receivable":
        st.subheader("📥 Upload AR File")
        uploaded_file = st.file_uploader("Upload AR.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to AR Format"):
                transformed_df = transform_account_receivable(df)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download AR Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="AR_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload AR.xlsx to proceed.")
    elif step == "Other Payable":
        st.subheader("📥 Upload Other Payable File")
        uploaded_file = st.file_uploader("Upload OP.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to OP Format"):
                transformed_df = transform_other_payable(df)
                transformed_df.rename(columns={"Debit": "Original Amount"}, inplace=True)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                # Split out unmatched payments if they exist
                unmatched = transformed_df[transformed_df["Date"] == "Unmatched Payments"]
                if not unmatched.empty:
                    st.warning("⚠️ Unmatched payments detected!")
                    st.write("### Unmatched Payments")
                    st.dataframe(unmatched)

                # Main transformed file download
                st.download_button(
                    label="📥 Download OP Excel",
                    data=to_excel(transformed_df),
                    file_name="OP_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload OP.xlsx to proceed.")

    elif step == "Account Payable":
        st.subheader("📥 Upload Account Payable File")
        uploaded_file = st.file_uploader("Upload AP.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to AP Format"):
                transformed_df = transform_account_payable(df)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download AP Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="AP_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload AP.xlsx to proceed.")
    elif step == "Advance Sales":
        st.subheader("📥 Upload Advance Sales File")
        uploaded_file = st.file_uploader("Upload AS.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to AS Format"):
                transformed_df, single_term_df = transform_advance_sales(df)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download AS Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="AS_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload AS.xlsx to proceed.")
    elif step == "Deferral Revenue":
        st.subheader("📥 Upload Deferral Revenue File")
        uploaded_file = st.file_uploader("Upload DR.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to DR Format"):
                transformed_df = transform_deferral_revenue(df, customer_dict)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download DR Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="DR_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload DR.xlsx to proceed.")
    elif step == "Temporary Receipt":
        st.subheader("📥 Upload Temporary Receipt File")
        uploaded_file = st.file_uploader("Upload TR.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to TR Format"):
                transformed_df = transform_temp_receipt(df)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download TR Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="TR_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload AS.xlsx to proceed.")
    elif step == "Advance Payment":
        st.subheader("📥 Upload Advance Payment File")
        uploaded_file = st.file_uploader("Upload Adv. Payment.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to Adv. Payment Format"):
                transformed_df = transform_advance_payment(df)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download Adv. Payment Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="Adv_Payment_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload Adv. Payment.xlsx to proceed.")
    elif step == "Prepaid PPh 23":
        st.subheader("📥 Upload Prepaid PPh 23 File")
        st.markdown("""
        Wanna clean up your Prepaid PPh 23? Go try this!
        """)
        uploaded_file = st.file_uploader("Upload Prepaid PPh23.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to Prepaid PPh 23 Format"):
                transformed_df = transform_prepaid_pph23(df)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download Prepaid PPh 23 Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="Prepaid_PPh23_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload Prepaid PPh 23.xlsx to proceed.")
    elif step == "Other Receivable":
        st.subheader("📥 Upload Other Receivable File")
        uploaded_file = st.file_uploader("Upload OR.xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to OR Format"):
                transformed_df = transform_other_receivable(df)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download OR Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="OR_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload OR.xlsx to proceed.")
    elif step == "Other Payable(RCJ)":
        st.subheader("📥 Upload OP(RCJ) File")
        uploaded_file = st.file_uploader("Upload OP(RCJ).xlsx", type=["xlsx"])

        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.write("### Preview of Uploaded Data")
            st.dataframe(df.head())

            if st.button("Transform to OP(RCJ) Format"):
                transformed_df = transform_other_payable_rcj(df)

                st.success("✅ Data transformed successfully!")
                st.write("### Transformed Data Preview")
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download OP(RCJ) Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="OP(RCJ)_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload OP(RCJ).xlsx to proceed.")
    elif step == "ROU Calculator":
        transform_rou_calculator()
    elif step == "Exchange Rate Calculator":
        st.subheader("💱 Exchange Rate Calculator")

        # User Inputs
        currency = st.selectbox("Select Currency", ["USD", "SGD", "JPY", "EUR", "AUD"])
        date = st.date_input("Select Date", value=pd.Timestamp.today())

        if st.button("Get Exchange Rates"):
            rates = get_exchange_rates(currency, str(date))

            st.success(f"✅ Exchange Rates for {currency} on {date}")
            st.write(f"**KMK Rate**: {rates['KMK Rate']} IDR/{currency}" if rates['KMK Rate'] else "KMK Rate not available")
            st.write(f"**BI Rate**: {rates['BI Rate']} IDR/{currency}" if rates['BI Rate'] else "BI Rate not available")
    else:
        st.warning(f"⚠️ The '{step}' process is not implemented yet.")

if __name__ == "__main__":
    main()
