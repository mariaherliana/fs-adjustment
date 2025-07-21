import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import numpy_financial as npf

def to_excel_two_sheets(df1, df2, sheet1_name="IFRS_Amortization", sheet2_name="Keystone_Amortization"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df1.to_excel(writer, index=False, sheet_name=sheet1_name)
        df2.to_excel(writer, index=False, sheet_name=sheet2_name)
    return output.getvalue()

def transform_rou_calculator():
    st.subheader("🏢 ROU (Right of Use) Calculator")
    st.markdown("""
    This tool calculates **Right of Use (ROU)** and **Interest Expense** under two methods:  
    ✅ **IFRS Standard** (Present Value with payments at beginning of period)  
    ✅ **Keystone (Consultant) Method** (PV using Google Sheets-style `PV` logic)  
    """)

    # === USER INPUTS ===
    col1, col2 = st.columns(2)
    with col1:
        total_term = st.number_input("Total Lease Term (months)", min_value=1, value=24, step=1)
        payment_interval = st.number_input("Payment Interval (months)", min_value=1, value=6, step=1)
        ib_rate_annual = st.number_input("Incremental Borrowing Rate (annual, %)", min_value=0.0, value=10.0, step=0.1)
        ib_rate = ib_rate_annual / 100
    with col2:
        start_date = st.date_input("Lease Start Date")

    # === LIVE IB RATE PER PAYMENT PERIOD ===
    periods = total_term / payment_interval if payment_interval else 1
    ib_rate_per_period_key = ib_rate_annual / periods
    ib_rate_per_period_ifrs = (1 + ib_rate) ** (payment_interval / 12) - 1

    st.metric(
        label="📉 IB Rate per Payment Period (Keystone style, %)",
        value=f"{ib_rate_per_period_key:.4f}%",
        delta=f"{ib_rate_annual:.2f}% annually"
    )

    st.info("""
    **Keystone**: IB Rate per Payment Period = Annual IBR ÷ (Total Lease Term ÷ Payment Interval)  
    **IFRS**: Uses compounding: (1 + annual IBR) ^ (payment interval ÷ 12) - 1
    """)

    # === RENT INPUTS ===
    num_years = (total_term // 12) + (1 if total_term % 12 else 0)
    rates_per_year = []
    for i in range(num_years):
        rate = st.number_input(f"Rent per Month (Year {i+1})", min_value=0.0, value=12000000.0, step=100000.0)
        rates_per_year.append(rate)

    # === CALCULATION BUTTON ===
    if st.button("Calculate ROU & Interest"):
        periods_count = int(total_term // payment_interval)
        payments = []
        payment_dates = []

        for p in range(periods_count):
            current_month = p * payment_interval
            current_year = min(current_month // 12, len(rates_per_year) - 1)
            payment_amount = rates_per_year[current_year] * payment_interval
            payments.append(payment_amount)

            start = pd.to_datetime(start_date) + pd.DateOffset(months=p * payment_interval)
            end = start + pd.DateOffset(months=payment_interval) - pd.DateOffset(days=1)
            payment_dates.append((start.strftime("%b %Y"), end.strftime("%b %Y")))

        # === AMORTIZATION TABLES ===
        amort_ifrs = []
        amort_key = []

        # === IFRS CALCULATION ===
        rou_pv_total_ifrs = sum(payment / ((1 + ib_rate_per_period_ifrs) ** (i - 1)) for i, payment in enumerate(payments, start=1))
        remaining_rou_ifrs = rou_pv_total_ifrs
        for i, (payment, date_range) in enumerate(zip(payments, payment_dates), start=1):
            interest_exp = remaining_rou_ifrs * ib_rate_per_period_ifrs
            principal = payment - interest_exp
            remaining_rou_ifrs -= principal
            amort_ifrs.append({
                "Period": i,
                "Start-End": f"{date_range[0]} - {date_range[1]}",
                "Payment": payment,
                "PV (ROU)": round(payment / ((1 + ib_rate_per_period_ifrs) ** (i - 1)), 2),
                "Interest Expense": round(interest_exp, 2),
                "Principal": round(principal, 2),
                "Ending ROU": round(remaining_rou_ifrs, 2)
            })

        # === KEYSTONE (CONSULTANT) CALCULATION - EXACT SHEETS LOGIC (TYPE 1) ===
        rou_pv_total_key = 0
        pv_rows = []

        for i, payment in enumerate(payments, start=1):
            # Google Sheets PV logic (type=1, beginning of period)
            pv_payment = payment / ((1 + (ib_rate_per_period_key / 100)) ** (i - 1))
            pv_payment = round(pv_payment, 2)  # round immediately like Sheets
            rou_pv_total_key += pv_payment
            pv_rows.append(pv_payment)

        remaining_rou_key = rou_pv_total_key
        amort_key = []

        for i, (payment, date_range, pv_payment) in enumerate(zip(payments, payment_dates, pv_rows), start=1):
            principal = pv_payment  # Consultant treats PV as principal repayment
            interest_exp = payment - principal  # Consultant's version
            remaining_rou_key = round(remaining_rou_key - principal, 2)

            amort_key.append({
                "Period": i,
                "Start-End": f"{date_range[0]} - {date_range[1]}",
                "Payment": round(payment, 2),
                "ROU (Keystone)": pv_payment,
                "Interest Expense": interest_exp,
                "Principal": principal,
                "Ending ROU": remaining_rou_key
            })

        # === DATAFRAMES ===
        amort_df_ifrs = pd.DataFrame(amort_ifrs)
        amort_df_key = pd.DataFrame(amort_key)

        col_ifrs, col_key = st.columns(2)
        with col_ifrs:
            st.write("### IFRS Amortization Table")
            st.dataframe(amort_df_ifrs)
            st.write(f"**Beginning ROU (IFRS): Rp {rou_pv_total_ifrs:,.2f}**")

        with col_key:
            st.write("### Keystone (Consultant) Amortization Table")
            st.dataframe(amort_df_key)
            st.write(f"**Beginning ROU (Keystone): Rp {rou_pv_total_key:,.2f}**")

        st.download_button(
            label="📥 Download Comparison Excel",
            data=to_excel_two_sheets(amort_df_ifrs, amort_df_key),
            file_name="ROU_IFRS_vs_Keystone.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # === SUBSEQUENT MEASUREMENT TABLE (NEW) ===
        st.write("## 📊 Subsequent Measurement Table")

        total_months = total_term
        dates = pd.date_range(start=start_date, periods=total_months, freq='MS')

        # Variables for Subsequent Measurement
        beg_rou = rou_pv_total_key  # Use Keystone ROU (consultant basis)
        lease_liab_cf = rou_pv_total_key
        depre_rou = beg_rou / total_term
        depre_fiscal = sum(payments[:12]) / 12 if total_term >= 12 else sum(payments) / total_term

        sub_measure = []
        for month in range(total_months):
            date = dates[month]
            total_month = month
            payment = -payments[month // payment_interval] if month % payment_interval == 0 else 0
            interest = lease_liab_cf * (ib_rate / 12)
            principal = -payment - interest if payment != 0 else 0
            lease_liab_cf = lease_liab_cf - principal
            ending_rou = beg_rou - depre_rou

            sub_measure.append({
                "Date": date.strftime("%b %Y"),
                "Total Months": total_month,
                "Payment": round(payment, 2),
                "Interest": round(interest, 2),
                "Principal": round(principal, 2),
                "Lease Liability C/F": round(lease_liab_cf, 2),
                "Beg ROU": round(beg_rou, 2),
                "Depre ROU": round(depre_rou, 2),
                "Ending ROU": round(ending_rou, 2),
                "Depre Fiscal": round(depre_fiscal, 2)
            })

            beg_rou = ending_rou

        sub_df = pd.DataFrame(sub_measure)
        st.dataframe(sub_df)
