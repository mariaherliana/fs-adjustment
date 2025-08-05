import pandas as pd
import numpy as np
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from statistics import mode

def transform_advance_sales(df):
    df = df.copy()

    # ✅ Normalize & ensure required columns
    df = df[[
        "Customer", "Date", "Inv No", "Tenant ID", "Start Month", "End Month",
        "Number of Months", "Total Price"
    ]].rename(columns={
        "Customer": "Company Name",
        "Date": "Invoice Date",
        "Inv No": "Invoice",
        "Tenant ID": "Tenant_ID",
        "Start Month": "Start_Month",
        "End Month": "End_Month",
        "Number of Months": "Total_Term",
        "Total Price": "Amount"
    })

    # ✅ Fix date format for Invoice Date
    df["Invoice Date"] = pd.to_datetime(df["Invoice Date"], errors="coerce").dt.date

    # ✅ Clean month format
    def clean_month_format(val):
        if pd.isna(val) or str(val).strip() in ["-", ""]:
            return pd.NaT
        val = str(val).strip().replace("/", "-")
        return pd.to_datetime(val, format="%m-%Y", errors="coerce")

    df["Start_Month"] = df["Start_Month"].apply(clean_month_format)
    df["End_Month"] = df["End_Month"].apply(clean_month_format)

    # ✅ Replace missing End_Month for single-term invoices
    df["End_Month"] = df.apply(
        lambda r: r["Start_Month"] if pd.isna(r["End_Month"]) else r["End_Month"], axis=1
    )

    # ✅ Merge items per invoice (combine tenant IDs if needed)
    def join_tenant_ids(x):
        return ", ".join(sorted(set(x.dropna().astype(str))))

    grouped = df.groupby(["Company Name", "Invoice", "Invoice Date"], as_index=False).agg({
        "Tenant_ID": join_tenant_ids,
        "Start_Month": "min",
        "End_Month": "max",
        "Total_Term": lambda x: mode(x),  # ✅ use most common term, not sum
        "Amount": "sum"
    })

    # ✅ Period (01-start to end-of-month end)
    def format_period(start, end):
        start_str = start.strftime("%d-%m-%Y")
        last_day = (end + pd.offsets.MonthEnd(0)).date()
        return f"{start_str} - {last_day.strftime('%d-%m-%Y')}"

        # ✅ Separate out single-month, same-month invoices
    def is_same_month(r):
        return (
            r["Total_Term"] == 1 and
            r["Invoice Date"].month == r["Start_Month"].month and
            r["Invoice Date"].year == r["Start_Month"].year
        )

    single_term_same_month = grouped[grouped.apply(is_same_month, axis=1)].copy()
    grouped = grouped[~grouped.apply(is_same_month, axis=1)].copy()

    grouped["Period"] = grouped.apply(lambda r: format_period(r["Start_Month"], r["End_Month"]), axis=1)

     # ✅ Monthly Sales Recognition
    grouped["Monthly Sales Recognition"] = (grouped["Amount"] / grouped["Total_Term"]).round(2)

    # ✅ Build period allocations with improved logic
    all_periods = []

    for i, row in grouped.iterrows():
        start = row["Start_Month"]
        end = row["End_Month"]
        invoice_date = pd.to_datetime(row["Invoice Date"])
        monthly_amount = row["Monthly Sales Recognition"]

        periods = pd.date_range(start=start, end=end, freq="MS")

        row_data = {
            "Date": row["Invoice Date"],
            "Voucher No": f"AR-{row['Invoice Date'].strftime('%y-%m')}-{str(i+1).zfill(3)}",
            "Company Name": row["Company Name"],
            "Tenant ID": row["Tenant_ID"],
            "Invoice": row["Invoice"],
            "Period": row["Period"],
            "Total Term": row["Total_Term"],
            "Amount": row["Amount"],
            "Monthly Sales Recognition": monthly_amount
        }

        # ✅ Rule 2: Skip monthly allocation if invoice = start month and term = 1
        if row["Total_Term"] == 1 and invoice_date.month == start.month and invoice_date.year == start.year:
            for p in periods:
                col_name = p.strftime("%m-%Y")
                row_data[col_name] = 0
        else:

            for j, p in enumerate(periods):
                    col_name = p.strftime("%m-%Y")

                    if p < start:
                        row_data[col_name] = 0

                    elif p < invoice_date.replace(day=1):
                        # Before invoice month: defer to catch-up
                        row_data[col_name] = 0

                    elif p == invoice_date.replace(day=1):
                        # Catch-up: include all unrecognized months before this
                        catch_up_months = [q for q in periods if start <= q < p]
                        catch_up_total = len(catch_up_months) * monthly_amount
                        row_data[col_name] = monthly_amount + catch_up_total

                    else:
                        # Normal monthly allocation
                        row_data[col_name] = monthly_amount

        # --- Fiscal Year Totals ---
        fy_totals = {}
        for fy_start in [2024, 2025, 2026]:
            fy_start_date = datetime(fy_start, 7, 1)
            fy_end_date = datetime(fy_start + 1, 6, 30)
            fy_periods = [p for p in periods if fy_start_date <= p <= fy_end_date]
            fy_total = sum([row_data.get(p.strftime("%m-%Y"), 0) for p in fy_periods])
            fy_totals[f"Total Acc Sales Recognition FY {fy_start}"] = fy_total

        row_data.update(fy_totals)

        # --- Sales Recognition as of End of Month & Ending Balance ---
        total_sales_recognition = sum(fy_totals.values())
        row_data["Sales Recognition as of end of month"] = total_sales_recognition
        row_data["Ending Balance"] = row["Amount"] - total_sales_recognition

        all_periods.append(row_data)

    final_df = pd.DataFrame(all_periods)

    # ✅ Replace NaN with 0 for monthly periods
    period_cols = [c for c in final_df.columns if re.match(r"\d{2}-\d{4}", c)]
    final_df[period_cols] = final_df[period_cols].fillna(0)

    # ✅ Rearrange columns dynamically
    sorted_periods = sorted(period_cols, key=lambda x: datetime.strptime(x, "%m-%Y"))
    ordered_cols = [
        "Date", "Voucher No", "Company Name", "Tenant ID", "Invoice", "Period",
        "Total Term", "Amount", "Monthly Sales Recognition"
    ]

    fy_years = [2024, 2025, 2026]
    for p in sorted_periods:
        ordered_cols.append(p)
        p_date = datetime.strptime(p, "%m-%Y")
        for fy in fy_years:
            if p_date.month == 6 and p_date.year == fy + 1:
                fy_col = f"Total Acc Sales Recognition FY {fy}"
                if fy_col in final_df.columns and fy_col not in ordered_cols:
                    ordered_cols.append(fy_col)

    ending_cols = [
        "Sales Recognition as of end of month",
        "Ending Balance"
    ]
    for col in final_df.columns:
        if col not in ordered_cols and col not in ending_cols:
            ordered_cols.append(col)
    ordered_cols += ending_cols
    ordered_cols = [c for c in ordered_cols if c in final_df.columns]

    final_df = final_df[ordered_cols]

    # ✅ Add TOTAL row
    total_row = {}
    for col in final_df.columns:
        if pd.api.types.is_numeric_dtype(final_df[col]):
            total_row[col] = final_df[col].sum()
        else:
            total_row[col] = ""  # leave text columns empty
    total_row["Company Name"] = "TOTAL"
    final_df = pd.concat([final_df, pd.DataFrame([total_row])], ignore_index=True)

    return final_df, single_term_same_month
