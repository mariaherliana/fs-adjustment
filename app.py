import streamlit as st
import pandas as pd
from io import BytesIO
from ar_cleaner import transform_account_receivable

def to_excel(df, engine="xlsxwriter"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine=engine) as writer:
        df.to_excel(writer, index=False, sheet_name="AR_Keystone", startrow=1)

        if engine == "xlsxwriter":
            workbook = writer.book
            worksheet = writer.sheets["AR_Keystone"]

            # --- Merge Header for Payment ---
            payment_format = workbook.add_format({
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "bg_color": "#D9EAD3"  # Light green, optional
            })

            # Find the exact columns for Payment section
            payment_start_col = df.columns.get_loc("Sales Receipt Date")
            payment_end_col = df.columns.get_loc("Sales Receipt Amount")

            # Merge the header row above the payment columns
            worksheet.merge_range(
                0, payment_start_col, 0, payment_end_col,
                "Payment",
                payment_format
            )

            # --- Header formatting ---
            header_format = workbook.add_format({
                "bold": True, "align": "center", "valign": "vcenter", "border": 1
            })
            for col_num, value in enumerate(df.columns):
                worksheet.write(1, col_num, value, header_format)

            # --- Auto-adjust column widths ---
            for i, col in enumerate(df.columns):
                max_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, max_width)

            # --- Subtotal row formatting ---
            subtotal_format = workbook.add_format({
                "bold": True,
                "font_color": "white",
                "bg_color": "black"
            })

            for row_num, value in enumerate(df["Customer"], start=2):  # +2 because data starts at row 2
                if isinstance(value, str) and "Subtotal" in value:
                    worksheet.set_row(row_num, None, subtotal_format)

    return output.getvalue()

def main():
    st.set_page_config(page_title="Data Cleanup Wizard", layout="wide")
    st.title("🧹 Internal Data Cleanup Wizard")

    step = st.sidebar.radio("Select Process Type", [
        "Advance Payment",
        "Other Payable",
        "Account Payable",
        "Temporary Receipt",
        "Advance Sales",
        "Account Receivable",
        "Other Receivable"
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
                st.dataframe(transformed_df.head(50))

                st.download_button(
                    label="📥 Download AR Keystone Excel",
                    data=to_excel(transformed_df, engine="xlsxwriter"),
                    file_name="AR_Keystone_Formatted.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Please upload AR.xlsx to proceed.")
    else:
        st.warning(f"⚠️ The '{step}' process is not implemented yet.")


if __name__ == "__main__":
    main()