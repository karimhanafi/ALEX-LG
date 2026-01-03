import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid
from datetime import datetime
import time

# ==========================================
# 1. VISUAL SETUP (FORCED DARK THEME)
# ==========================================
st.set_page_config(page_title="IC Audit Pro", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    /* FORCE DARK BACKGROUND */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(to bottom right, #0f172a, #1e293b);
        color: #e2e8f0;
    }
    
    /* INPUTS */
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input {
        background-color: #334155 !important; 
        color: white !important; 
        border: 1px solid #475569;
    }
    
    /* HEADERS (GOLD) */
    h1, h2, h3 {color: #fbbf24 !important;}
    
    /* METRICS */
    div[data-testid="metric-container"] {
        background-color: #1e293b;
        border-left: 5px solid #fbbf24;
        padding: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricValue"] {color: #fbbf24 !important;}
    
    /* BUTTONS */
    .stButton>button {
        background-color: #d97706; color: white; border: none; font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #b45309; color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. GOOGLE SHEETS ENGINE
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_connection():
    try:
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        return client.open_by_url(sheet_url).sheet1
    except Exception as e:
        st.error(f"🔥 Connection Failed: {e}")
        st.stop()

# ALL COLUMNS
COLUMNS = [
    "task_id", "assigned_date", "branch", "post_type", "inputter", 
    "req_type", "cif", "applicant", "beneficiary", "amount", "current_total", "currency", 
    "lg_number", "lg_type", "cbe_serial", "authorizer", "md_ref", 
    "postage_number", "comm_amount", "comm_status", "comm_chg_ref", "status", 
    "pending_reason", "to_be_started_on", "file_sent", "original_recvd", "original_recv_date"
]

COMM_OPTS = ["", "Collected", "Pending", "Due Comm."]

def load_data():
    try:
        wks = get_connection()
        data = wks.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame(columns=COLUMNS)
        
        # Ensure all columns exist
        for col in COLUMNS:
            if col not in df.columns: df[col] = ""
            
        # Strict Numeric Conversion
        for col in ['amount', 'current_total', 'file_sent', 'original_recvd']:
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
             
        return df.astype(str)
    except:
        return pd.DataFrame(columns=COLUMNS)

def save_data(df):
    try:
        wks = get_connection()
        wks.clear()
        df_clean = df.fillna("")
        wks.append_row(df_clean.columns.tolist())
        wks.append_rows(df_clean.values.tolist())
        st.toast("☁️ Sync Complete!", icon="✅")
        time.sleep(1)
    except Exception as e:
        st.error(f"Save Error: {e}")

# --- HELPERS ---
def get_current_date(): return datetime.now().strftime("%d/%b/%Y")

def get_unique(df, col):
    if col in df.columns:
        vals = [x for x in df[col].unique() if x and str(x) != "nan" and str(x) != ""]
        return sorted(vals)
    return []

def get_index(options, value):
    try:
        return options.index(str(value))
    except ValueError:
        return 0

# ==========================================
# 3. VIEWS
# ==========================================

def authorizer_view(user):
    st.title(f"🛡️ Authorizer Command Center")
    df = load_data()
    
    # METRICS
    today_str = get_current_date()
    daily_lgs = len(df[df['assigned_date'] == today_str])
    global_pend = len(df[df['status'] == 'Pending'])
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📅 Daily LGs (Today)", daily_lgs)
    m2.metric("⚠️ Global Pendings", global_pend)
    m3.metric("📢 Ready for Auth", len(df[(df['authorizer']==user) & (df['status']=='Ready for Auth')]))
    m4.metric("📊 Total Database", len(df))
    
    st.divider()
    
    # TABS
    tabs = st.tabs([
        "➕ Create Task", 
        "⚡ Manage Active", 
        "✅ Review & Approve", 
        "📂 Global Pendings", 
        "📦 Missing Originals",
        "📊 Master Data"
    ])

    # --- TAB 1: CREATE TASK ---
    with tabs[0]:
        c_search, _ = st.columns([1, 2])
        lg_search = c_search.text_input("🔍 Search History (Enter LG #):")
        
        d_br = d_cif = d_app = d_ben = d_req = d_amt = d_curr = d_type = d_md = ""
        prev_total = 0.0
        
        if lg_search and not df.empty:
            hist = df[df['lg_number'] == lg_search]
            if not hist.empty:
                last_rec = hist.iloc[-1]
                d_br = str(last_rec['branch'])
                d_cif = str(last_rec['cif'])
                d_app = str(last_rec['applicant'])
                d_ben = str(last_rec['beneficiary'])
                d_curr = str(last_rec['currency'])
                d_type = str(last_rec['lg_type'])
                d_md = str(last_rec['md_ref'])
                try:
                    prev_total = float(last_rec['current_total'])
                    if prev_total == 0: prev_total = float(last_rec['amount'])
                except: prev_total = 0.0
                st.toast(f"Found history! Current Value: {prev_total:,.2f}", icon="ℹ️")

        st.subheader("1. Client Info")
        c1, c2, c3 = st.columns(3)
        with c1:
            br_opts = get_unique(df, "branch") + ["New"]
            br = st.selectbox("Branch", br_opts, index=get_index(br_opts, d_br))
            if br == "New": br = st.text_input("New Branch Name")
            
            cif_opts = get_unique(df, "cif") + ["New"]
            cif = st.selectbox("CIF", cif_opts, index=get_index(cif_opts, d_cif))
            if cif == "New": cif = st.text_input("New CIF")
            
        with c2:
            app_opts = get_unique(df, "applicant") + ["New"]
            app = st.selectbox("Applicant", app_opts, index=get_index(app_opts, d_app))
            if app == "New": app = st.text_input("New Applicant")
            
            ben_opts = get_unique(df, "beneficiary") + ["New"]
            ben = st.selectbox("Beneficiary", ben_opts, index=get_index(ben_opts, d_ben))
            if ben == "New": ben = st.text_input("New Beneficiary")

        with c3:
            req_opts = get_unique(df, "req_type") + ["New"]
            req = st.selectbox("Request Type", req_opts)
            if req == "New": req = st.text_input("New Request Type")

        st.subheader("2. Financials")
        c4, c5 = st.columns(2)
        with c4:
            is_inc = "Increase" in req
            is_dec = "Decrease" in req
            if is_inc or is_dec:
                st.info(f"💰 Previous Total: {prev_total:,.2f}")
                txn_amount = st.number_input("Change Amount (Delta)", min_value=0.0, step=100.0)
                new_total_calc = prev_total + txn_amount if is_inc else prev_total - txn_amount
                st.metric("New LG Total", f"{new_total_calc:,.2f}")
                final_amt_to_save = txn_amount
                final_total_to_save = new_total_calc
            else:
                final_amt_to_save = st.number_input("Amount", value=float(d_amt) if d_amt else 0.0)
                final_total_to_save = final_amt_to_save
                
        with c5:
            curr_opts = ["EGP", "USD", "EUR", "GBP", "SAR"]
            curr = st.selectbox("Currency", curr_opts, index=get_index(curr_opts, d_curr))

        st.subheader("3. LG Details")
        c6, c7, c8 = st.columns(3)
        with c6:
            new_lg = st.text_input("LG Number", value=lg_search)
            lg_types = ["Bid Bond", "Performance", "Advance Payment", "Retention", "Final", "Other"]
            lgt = st.selectbox("LG Type", lg_types, index=get_index(lg_types, d_type))
        with c7:
            ptype = st.radio("Post Type", ["Original", "Copy"], horizontal=True)
            md = st.text_input("MD Ref", value=d_md)
        with c8:
            inp = st.selectbox("Assign To", ["inp1", "inp2"])
            comm_chg = st.text_input("Comm CHG Ref (Optional)")

        st.divider()
        if st.button("🚀 Assign Task", type="primary"):
            if not new_lg:
                st.error("LG Number is required")
            else:
                new_row = pd.DataFrame([{
                    "task_id": str(uuid.uuid4()), "assigned_date": today_str,
                    "lg_number": new_lg, "lg_type": lgt, "branch": br, "cif": cif,
                    "applicant": app, "beneficiary": ben, "inputter": inp, "authorizer": user,
                    "req_type": req, "amount": final_amt_to_save, 
                    "current_total": final_total_to_save, "currency": curr, "post_type": ptype,
                    "md_ref": md, "comm_chg_ref": comm_chg, "status": "Active", 
                    "file_sent": 0, "original_recvd": 0, "original_recv_date": "",
                    "pending_reason": "", "to_be_started_on": "", "comm_amount": "", "comm_status": "", "cbe_serial": "", "postage_number": ""
                }])
                updated_df = pd.concat([df, new_row], ignore_index=True)
                save_data(updated_df)
                st.success("Task Assigned!")
                time.sleep(1)
                st.rerun()

    # --- TAB 2: MANAGE ACTIVE ---
    with tabs[1]:
        active_tasks = df[df['status'] == 'Active']
        if active_tasks.empty:
            st.info("No active tasks.")
        else:
            st.dataframe(active_tasks[['lg_number', 'inputter', 'applicant', 'amount']], use_container_width=True)
            sel_act = st.selectbox("Select Active Task to Amend", active_tasks['lg_number'].unique())
            
            idx = df[df['lg_number'] == sel_act].index[0]
            row = df.iloc[idx]
            
            with st.form("amend_full"):
                st.write(f"Editing **{sel_act}**")
                c_a1, c_a2, c_a3 = st.columns(3)
                with c_a1:
                    n_inp = st.selectbox("Inputter", ["inp1", "inp2"], index=get_index(["inp1", "inp2"], row['inputter']))
                    n_md = st.text_input("MD Ref", value=row['md_ref'])
                    n_comm_chg = st.text_input("Comm CHG Ref", value=row['comm_chg_ref'])
                with c_a2:
                    n_cbe = st.text_input("CBE Serial", value=row['cbe_serial'])
                    n_pno = st.text_input("Postage No", value=row['postage_number'])
                    n_fs = st.selectbox("File Sent?", [0, 1], index=int(float(row['file_sent'])))
                with c_a3:
                    n_comm = st.text_input("Comm Amt", value=row['comm_amount'])
                    n_stat = st.selectbox("Comm Status", COMM_OPTS, index=get_index(COMM_OPTS, row['comm_status']))
                    n_pend = st.text_input("Pending Reason", value=row['pending_reason'])
                
                if st.form_submit_button("💾 Save All Amendments"):
                    df.at[idx, 'inputter'] = n_inp
                    df.at[idx, 'md_ref'] = n_md
                    df.at[idx, 'comm_chg_ref'] = n_comm_chg
                    df.at[idx, 'cbe_serial'] = n_cbe
                    df.at[idx, 'postage_number'] = n_pno
                    df.at[idx, 'file_sent'] = n_fs
                    df.at[idx, 'comm_amount'] = n_comm
                    df.at[idx, 'comm_status'] = n_stat
                    df.at[idx, 'pending_reason'] = n_pend
                    save_data(df)
                    st.success("Task Updated!")
                    st.rerun()

    # --- TAB 3: REVIEW ---
    with tabs[2]:
        mask = (df['authorizer'] == user) & (df['status'] == 'Ready for Auth')
        my_tasks = df[mask]
        
        if my_tasks.empty:
            st.info("No tasks waiting.")
        else:
            st.dataframe(my_tasks[['lg_number', 'applicant', 'amount']], use_container_width=True)
            sel_lg = st.selectbox("Select LG to Action", my_tasks['lg_number'].unique())
            task_row = my_tasks[my_tasks['lg_number'] == sel_lg].iloc[0]
            
            with st.form("auth_dec"):
                c_e1, c_e2, c_e3 = st.columns(3)
                with c_e1:
                    e_md = st.text_input("MD Ref", value=task_row['md_ref'])
                    e_cbe = st.text_input("CBE Serial", value=task_row['cbe_serial'])
                    e_comm_chg = st.text_input("Comm CHG Ref", value=task_row['comm_chg_ref'])
                with c_e2:
                    e_post = st.text_input("Postage", value=task_row['postage_number'])
                    e_start = st.text_input("Start Date", value=task_row['to_be_started_on'])
                with c_e3:
                    e_comm = st.text_input("Comm Amt", value=task_row['comm_amount'])
                    e_stat = st.selectbox("Comm Status", COMM_OPTS, index=get_index(COMM_OPTS, task_row['comm_status']))

                st.divider()
                c_dec1, c_dec2 = st.columns([2, 1])
                with c_dec1:
                    dec = st.radio("Decision", ["Approve", "Pending", "Return"], horizontal=True)
                    reas = st.text_input("Reason")
                with c_dec2:
                    chk = st.checkbox("File Sent?")
                
                if st.form_submit_button("Execute"):
                    idx = df[df['task_id'] == task_row['task_id']].index[0]
                    df.at[idx, 'md_ref'] = e_md; df.at[idx, 'cbe_serial'] = e_cbe; df.at[idx, 'comm_chg_ref'] = e_comm_chg
                    df.at[idx, 'postage_number'] = e_post; df.at[idx, 'to_be_started_on'] = e_start
                    df.at[idx, 'comm_amount'] = e_comm; df.at[idx, 'comm_status'] = e_stat

                    if dec == "Approve":
                        if not chk: st.error("Confirm File Sent!")
                        else:
                            df.at[idx, 'status'] = 'Completed'
                            df.at[idx, 'file_sent'] = 1
                            save_data(df)
                            st.balloons(); st.rerun()
                    elif dec == "Pending":
                        df.at[idx, 'status'] = 'Pending'; df.at[idx, 'pending_reason'] = reas
                        save_data(df); st.rerun()
                    elif dec == "Return":
                        df.at[idx, 'status'] = 'Active'; df.at[idx, 'pending_reason'] = reas
                        save_data(df); st.rerun()

    # --- TAB 4: GLOBAL PENDINGS (SUPER EDIT POWER) ---
    with tabs[3]:
        pendings = df[df['status'] == 'Pending']
        
        if pendings.empty:
            st.success("Clean Sheet! No pending tasks.")
        else:
            st.dataframe(pendings[['lg_number', 'pending_reason', 'inputter', 'authorizer']], use_container_width=True)
            for i, row in pendings.iterrows():
                with st.expander(f"⚙️ Manage {row['lg_number']} ({row['inputter']})"):
                    # GLOBAL EDIT FORM
                    c_p1, c_p2, c_p3 = st.columns(3)
                    with c_p1:
                        n_md = st.text_input("MD Ref", value=row['md_ref'], key=f"md_{row['task_id']}")
                        n_cbe = st.text_input("CBE Serial", value=row['cbe_serial'], key=f"cbe_{row['task_id']}")
                        n_start = st.text_input("Start On", value=row['to_be_started_on'], key=f"st_{row['task_id']}")
                    with c_p2:
                        n_comm = st.text_input("Comm Amt", value=row['comm_amount'], key=f"cam_{row['task_id']}")
                        n_stat = st.selectbox("Comm Status", COMM_OPTS, index=get_index(COMM_OPTS, row['comm_status']), key=f"cst_{row['task_id']}")
                        n_post = st.text_input("Postage", value=row['postage_number'], key=f"pos_{row['task_id']}")
                    with c_p3:
                        n_fs = st.checkbox("File Sent", value=(float(row['file_sent'])==1), key=f"fs_{row['task_id']}")
                        n_or = st.checkbox("Original Recvd", value=(float(row['original_recvd'])==1), key=f"or_{row['task_id']}")
                        new_reas = st.text_input("Edit Reason", value=row['pending_reason'], key=f"r_{row['task_id']}")

                    dest = st.radio("Re-Activate To:", ["Inputter", "Authorizer"], key=f"d_{row['task_id']}")
                    
                    if st.button(f"Update & Release {row['lg_number']}", key=f"b_{row['task_id']}"):
                        idx = df[df['task_id'] == row['task_id']].index[0]
                        # Save all fields
                        df.at[idx, 'md_ref'] = n_md
                        df.at[idx, 'cbe_serial'] = n_cbe
                        df.at[idx, 'to_be_started_on'] = n_start
                        df.at[idx, 'comm_amount'] = n_comm
                        df.at[idx, 'comm_status'] = n_stat
                        df.at[idx, 'postage_number'] = n_post
                        df.at[idx, 'file_sent'] = 1 if n_fs else 0
                        df.at[idx, 'original_recvd'] = 1 if n_or else 0
                        df.at[idx, 'pending_reason'] = new_reas
                        df.at[idx, 'status'] = 'Active' if dest == "Inputter" else 'Ready for Auth'
                        save_data(df)
                        st.rerun()

    # --- TAB 5: MISSING ORIGINALS (FIXED: SEARCHABLE) ---
    with tabs[4]:
        df['original_recvd'] = pd.to_numeric(df['original_recvd'], errors='coerce').fillna(0)
        mask_miss = (df['post_type'] == 'Copy') & (df['original_recvd'] == 0)
        missing = df[mask_miss]
        
        if missing.empty:
            st.success("All originals received.")
        else:
            st.warning(f"Total Missing: {len(missing)}")
            st.dataframe(missing[['lg_number', 'branch', 'inputter', 'assigned_date']], use_container_width=True)
            
            # --- FIXED: FILTER LOGIC ---
            st.markdown("---")
            st.subheader("🔎 Search & Update")
            
            # 1. Search Box
            search_q = st.text_input("Type LG Number to Filter List:", key="auth_miss_search")
            
            # 2. Filter Dropdown based on Search
            all_missing_lgs = missing['lg_number'].unique()
            if search_q:
                # Show only LGs that contain the search text
                filtered_lgs = [lg for lg in all_missing_lgs if search_q.lower() in lg.lower()]
            else:
                filtered_lgs = all_missing_lgs
            
            if len(filtered_lgs) == 0:
                st.info("No matching LG found.")
            else:
                rec_lg = st.selectbox("Select LG to Mark Received:", filtered_lgs)
                rec_date = st.date_input("Date Received")
                
                if st.button("Confirm Original Received"):
                    idx = df[df['lg_number'] == rec_lg].index[0]
                    df.at[idx, 'original_recvd'] = 1
                    df.at[idx, 'original_recv_date'] = str(rec_date)
                    df.at[idx, 'post_type'] = "Original" 
                    save_data(df)
                    st.success("Updated!")
                    st.rerun()

    # --- TAB 6: MASTER DATA ---
    with tabs[5]:
        st.dataframe(df, use_container_width=True)

def inputter_view(user):
    st.title(f"⚡ Inputter Portal: {user}")
    df = load_data()
    
    st.metric("Tasks Waiting", len(df[(df['inputter']==user) & (df['status']=='Active')]))
    
    # INPUTTER HAS 3 TABS NOW
    tab1, tab2, tab3 = st.tabs(["🚀 Active Tasks", "⏳ My Watchlist (Edit)", "📦 Missing Originals"])
    
    with tab1:
        mask = (df['inputter'] == user) & (df['status'] == 'Active')
        active = df[mask]
        
        if active.empty: st.info("No active tasks.")
        else:
            st.dataframe(active[['lg_number', 'req_type', 'amount']], use_container_width=True)
            sel_lg = st.selectbox("Process Task", active['lg_number'].unique())
            task_row = active[active['lg_number'] == sel_lg].iloc[0]
            
            st.markdown(f"**Processing: {sel_lg}**")
            
            # INPUTTER SELECTS AUTHORIZER
            c_auth, _ = st.columns(2)
            with c_auth:
                curr_auth = task_row['authorizer']
                auth_opts = ["auth1", "auth2"]
                idx_auth = get_index(auth_opts, curr_auth)
                sel_auth = st.selectbox("Send to Authorizer:", auth_opts, index=idx_auth)
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Send Task", type="primary"):
                    idx = df[df['task_id'] == task_row['task_id']].index[0]
                    df.at[idx, 'status'] = 'Ready for Auth'
                    df.at[idx, 'authorizer'] = sel_auth
                    save_data(df)
                    st.rerun()
            with c2:
                p_reas = st.text_input("Pending Reason")
                if st.button("Mark Pending"):
                    idx = df[df['task_id'] == task_row['task_id']].index[0]
                    df.at[idx, 'status'] = 'Pending'
                    df.at[idx, 'pending_reason'] = p_reas
                    save_data(df)
                    st.rerun()

    # --- TAB 2: WATCHLIST (FIXED: EDITABLE MD/COMM/CHG) ---
    with tab2:
        my_p = df[(df['inputter']==user) & (df['status']=='Pending')]
        
        if my_p.empty:
            st.info("Watchlist empty.")
        else:
            st.dataframe(my_p[['lg_number', 'pending_reason']], use_container_width=True)
            sel_p = st.selectbox("Select Pending Task to Fix:", my_p['lg_number'].unique())
            p_row = my_p[my_p['lg_number'] == sel_p].iloc[0]
            
            with st.form("fix_pending"):
                st.write(f"Fixing **{sel_p}**")
                
                # BASIC FIXES
                c_f1, c_f2 = st.columns(2)
                with c_f1:
                    n_app = st.text_input("Applicant", value=p_row['applicant'])
                    n_amt = st.number_input("Amount", value=float(p_row['amount']))
                with c_f2:
                    n_reas = st.text_input("Update Reason", value=p_row['pending_reason'])
                
                # REQUESTED EDITABLE FIELDS FOR WATCHLIST
                st.markdown("---")
                st.caption("Technical Amendments")
                c_t1, c_t2, c_t3 = st.columns(3)
                with c_t1:
                    n_md = st.text_input("MD Ref", value=p_row['md_ref'])
                with c_t2:
                    n_stat = st.selectbox("Comm Status", COMM_OPTS, index=get_index(COMM_OPTS, p_row['comm_status']))
                with c_t3:
                    n_chg = st.text_input("Comm CHG Ref", value=p_row['comm_chg_ref'])

                if st.form_submit_button("💾 Fix & Resubmit"):
                    idx = df[df['task_id'] == p_row['task_id']].index[0]
                    df.at[idx, 'applicant'] = n_app
                    df.at[idx, 'amount'] = n_amt
                    df.at[idx, 'pending_reason'] = n_reas
                    df.at[idx, 'md_ref'] = n_md
                    df.at[idx, 'comm_status'] = n_stat
                    df.at[idx, 'comm_chg_ref'] = n_chg
                    
                    df.at[idx, 'status'] = 'Ready for Auth' # Send back to Auth
                    save_data(df)
                    st.success("Resubmitted!")
                    st.rerun()
    
    # --- TAB 3: MISSING ORIGINALS (INPUTTER ACCESS - FIXED SEARCH) ---
    with tab3:
        df['original_recvd'] = pd.to_numeric(df['original_recvd'], errors='coerce').fillna(0)
        mask_miss = (df['post_type'] == 'Copy') & (df['original_recvd'] == 0)
        missing = df[mask_miss]
        
        if missing.empty:
            st.success("All originals received.")
        else:
            st.warning(f"Total Missing: {len(missing)}")
            st.dataframe(missing[['lg_number', 'branch', 'inputter', 'assigned_date']], use_container_width=True)
            
            # --- FIXED: FILTER LOGIC FOR INPUTTER ---
            st.markdown("---")
            st.subheader("🔎 Search & Update")
            
            inp_search = st.text_input("Type LG Number to Filter:", key="inp_miss_search")
            
            all_lgs = missing['lg_number'].unique()
            if inp_search:
                filtered = [lg for lg in all_lgs if inp_search.lower() in lg.lower()]
            else:
                filtered = all_lgs

            if len(filtered) == 0:
                st.info("No matching LG.")
            else:
                rec_lg = st.selectbox("Select LG Received:", filtered, key="inp_lg")
                rec_date = st.date_input("Date Received", key="inp_date")
                
                if st.button("Confirm Original Received", key="inp_btn"):
                    idx = df[df['lg_number'] == rec_lg].index[0]
                    df.at[idx, 'original_recvd'] = 1
                    df.at[idx, 'original_recv_date'] = str(rec_date)
                    df.at[idx, 'post_type'] = "Original" 
                    save_data(df)
                    st.success("Updated!")
                    st.rerun()

def admin_view():
    st.title("📊 Admin Tower")
    df = load_data()
    st.dataframe(df)

def main():
    if "username" not in st.session_state:
        st.session_state["username"] = ""
        st.session_state["role"] = ""

    if not st.session_state["username"]:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.title("🔐 IC Audit Pro")
            with st.form("login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    users = {"admin": "Admin", "auth1": "Authorizer", "auth2": "Authorizer", "inp1": "Inputter", "inp2": "Inputter"}
                    if u in users and p == "123":
                        st.session_state["username"] = u
                        st.session_state["role"] = users[u]
                        st.rerun()
                    else: st.error("Invalid")
    else:
        with st.sidebar:
            st.write(f"User: {st.session_state['username']}")
            if st.button("Logout"):
                st.session_state["username"] = ""
                st.rerun()
        
        role = st.session_state["role"]
        if role == "Authorizer": authorizer_view(st.session_state["username"])
        elif role == "Inputter": inputter_view(st.session_state["username"])
        elif role == "Admin": admin_view()

if __name__ == "__main__":
    main()
