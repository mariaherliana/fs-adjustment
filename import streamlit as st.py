import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
from io import BytesIO

# === Excel-Consistent PV Calculation ===
def calculate_pv_excel(rate, nper, payment, when=1):
    """
    Matches Excel PV function exactly.
    rate  : periodic interest rate (e.g., IB Rate per payment period)
    nper  : number of periods
    payment: payment amount (positive)
    when  : 1 = beginning of period (annuity due), 0 = end of period (ordinary annuity)
    """
    return abs(npf.pv(rate, nper, -payment, fv=0, when=when))

# === Excel Export (Two Sheets) ===
def to_excel_two_versions(df_ifrs, df_keystone, sheet1_name="IFRS", sheet2_name="Keystone"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_ifrs.to_excel(writer, index=False, sheet_name=sheet1_name)
        df_keystone.to_excel(writer, index=False, sheet_name=sheet2_name)
    return output.getvalue()

def transform_rou_calculator():
    st.subheader("🏢 ROU (Right of Use) Calculator – IFRS vs Keystone")

    # === Collapsible Explanation ===
    with st.expander("ℹ️ How does this calculator work?"):
        st.markdown("""
        **1. IFRS (Accounting Standard)**  
        - PV of all future lease payments discounted using IBR.  
        - Interest Expense = Opening ROU × IB Rate per period.  
        - Principal = Payment – Interest.  
        - Ending ROU = Opening ROU – Principal.  

        **2. Keystone (Consultant)**  
        - PV calculated per payment using `=PV()` like in Google Sheets.  
        - Interest Expense = Payment – PV (per period).  
        - Principal = PV (per period).  
        - Ending ROU decreases by Principal per period.
        """)

    # === User Inputs ===
    col1, col2 = st.columns(2)
    with col1:
        total_term = st.number_input("Total Lease Term (months)", min_value=1, value=24, step=1)
        payment_interval = st.number_input("Payment Interval (months)", min_value=1, value=6, step=1)
        ib_rate_annual = st.number_input("Incremental Borrowing Rate (annual, %)", min_value=0.0, value=10.0, step=0.1)
        ib_rate = ib_rate_annual / 100  # keep the original annual rate in decimal
    with col2:
        start_date = st.date_input("Lease Start Date")
        st.info("✅ IB Rate automatically adjusted for payment intervals")

    # ✅ Correct IB Rate per Payment Period (IFRS logic)
    ib_rate_per_period = (1 + ib_rate) ** (payment_interval / 12) - 1
    st.caption(f"**IB Rate per Payment Period:** {ib_rate_per_period * 100:.4f}%")

    # === Dynamic Rent Per Year ===
    num_years = (total_term // 12) + (1 if total_term % 12 else 0)
    rates_per_year = []
    for i in range(num_years):
        rate = st.number_input(f"Rent per Month (Year {i+1})", min_value=0.0, value=12000000.0, step=100000.0)
        rates_per_year.append(rate)

    if st.button("Calculate ROU & Interest"):
        # === Payment Schedule ===
        periods = total_term // payment_interval
        monthly_ibr = (1 + ib_rate) ** (payment_interval / 12) - 1

        payments, payment_dates = [], []
        for p in range(periods):
            current_month = p * payment_interval
            current_year = min(current_month // 12, len(rates_per_year) - 1)
            payment_amount = rates_per_year[current_year] * payment_interval
            payments.append(payment_amount)

            start = pd.to_datetime(start_date) + pd.DateOffset(months=p * payment_interval)
            end = start + pd.DateOffset(months=payment_interval) - pd.DateOffset(days=1)
            payment_dates.append((start.strftime("%b %Y"), end.strftime("%b %Y")))

        # === IFRS Calculation ===
        ifrs_rows, remaining_rou_ifrs = [], 0
        ifrs_pvs = [calculate_pv_excel(monthly_ibr, i, p, when=1) for i, p in enumerate(payments, start=1)]
        remaining_rou_ifrs = sum(ifrs_pvs)

        for i, (payment, date_range) in enumerate(zip(payments, payment_dates), start=1):
            interest_exp = remaining_rou_ifrs * monthly_ibr
            principal = payment - interest_exp
            remaining_rou_ifrs -= principal

            ifrs_rows.append({
                "Period": i,
                "Start-End": f"{date_range[0]} - {date_range[1]}",
                "Payment": payment,
                "PV (ROU)": round(ifrs_pvs[i-1], 2),
                "Interest Expense": round(interest_exp, 2),
                "Principal": round(principal, 2),
                "Ending ROU": round(remaining_rou_ifrs, 2)
            })
        ifrs_df = pd.DataFrame(ifrs_rows)

        # === Keystone Calculation ===
        keystone_rows = []
        keystone_pvs = [calculate_pv_excel(monthly_ibr, 1, p, when=1) for p in payments]
        remaining_rou_keystone = sum(keystone_pvs)

        for i, (payment, date_range, pv) in enumerate(zip(payments, payment_dates, keystone_pvs), start=1):
            interest_exp = payment - pv
            principal = pv
            remaining_rou_keystone -= principal

            keystone_rows.append({
                "Period": i,
                "Start-End": f"{date_range[0]} - {date_range[1]}",
                "Payment": payment,
                "PV (ROU)": round(pv, 2),
                "Interest Expense": round(interest_exp, 2),
                "Principal": round(principal, 2),
                "Ending ROU": round(remaining_rou_keystone, 2)
            })
        keystone_df = pd.DataFrame(keystone_rows)

        # === Side-by-Side Display ===
        col1, col2 = st.columns(2)
        with col1:
            st.write("### 📊 IFRS Amortization Table")
            st.dataframe(ifrs_df)
            st.write(f"**Total Beginning ROU (IFRS): Rp {sum(ifrs_pvs):,.2f}**")
        with col2:
            st.write("### 📊 Keystone (Consultant) Amortization Table")
            st.dataframe(keystone_df)
            st.write(f"**Total Beginning ROU (Keystone): Rp {sum(keystone_pvs):,.2f}**")

        # === Excel Download ===
        st.download_button(
            label="📥 Download IFRS vs Keystone Excel",
            data=to_excel_two_versions(ifrs_df, keystone_df),
            file_name="ROU_IFRS_vs_Keystone.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
