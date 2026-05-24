import streamlit as st

main_page = st.Page("streamlit_app.py", title="Data loading", icon="🏠", default=True)
exploration = st.Page("pages/0_🔍Exploration.py", title="Exploration")
dq_report = st.Page("pages/1_📊_DQ_Report.py", title="DQ Report")
cleaning = st.Page("pages/2_🧹_Cleaning.py", title="Cleaning")
antifraud = st.Page("pages/3_🚨_Antifraud_Demo.py", title="Antifraud Demo")
recommendations = st.Page("pages/4_💡_Recommendations.py", title="Recommendations")
pg = st.navigation([main_page, exploration, dq_report, cleaning, antifraud, recommendations])
pg.run()