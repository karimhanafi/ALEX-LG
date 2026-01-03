import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid
from datetime import datetime
import time

# ==========================================
# 1. VISUAL SETUP
# ==========================================
st.set_page_config(page_title="IC Audit Pro", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    /* MIDNIGHT BLUE THEME */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(to bottom right, #0f172a, #1e293b);
        color: #e2e8f0;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input {
        background-color: #334155 !important; color: white !important; border: 1px solid #475569;
    }
    h1, h2, h3 {color: #fbbf24 !important;}
    div[data-testid="metric-container"] {
        background-color: #1e293b; border-left: 5px solid #fbbf24; padding: 10px;
    }
    div[data-testid="stMetricValue"] {color: #fbbf24 !important;}
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

def get_client():
    try:
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"🔥 Connection Failed: {e}")
        st.stop()

def get_main_sheet():
    client = get_client()
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    return client.open_by_url(sheet_url).sheet1

def get_users_sheet():
    client = get_client()
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    try:
        return client.open_by_url(sheet_url).worksheet("Users")
    except:
        st.error("⚠️ 'Users' tab not found in Google Sheet. Please create it.")
        st.stop()

# --- DATA LOADERS ---
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
        wks = get_main_sheet()
        data = wks.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame(columns=COLUMNS)
        for col in COLUMNS:
            if col not in df.columns: df[col] = ""
        for col in ['amount', 'current_total', 'file_sent', 'original_recvd']:
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df.astype(str)
    except: return pd.DataFrame(columns=COLUMNS)

def save_data(df):
    try:
        wks = get_main_sheet()
        wks.clear()
        df_clean = df.fillna("")
        wks.append_row(df_clean.columns.tolist())
        wks.append_rows(df_clean.values.tolist())
        st.toast("☁️ Sync Complete!", icon="✅")
        time.sleep(1)
    except Exception as e: st.error(f"Save Error: {e}")

# --- USER LOADING (FIXED FOR TEXT/NUMBER BUG) ---
def load_users():
    try:
        wks = get_users_sheet()
        data = wks.get_all_records()
        df = pd.DataFrame(data)
        
        # CRITICAL FIX: Convert everything to string to prevent mismatch
        df = df.astype(str)
        
        # Remove accidental spaces
        if 'username' in df.columns: df['username'] = df['username'].str.strip()
        if 'password' in df.columns: df['password'] = df['password'].str.strip()
        return df
    except: 
        return pd.DataFrame(columns=["username", "password", "role", "name"])

def get_users_by_role(role_name):
    users_df = load_users()
    if not users_df.empty and "role" in users_df.columns:
        return users_df[users_df["role"] == role_name]["username"].tolist()
    return []

# --- HELPERS ---
def get_current_date(): return datetime.now().strftime("%d/%b/%Y")
def get_unique(df, col):
    if col in df.columns:
        vals = [x for x in df[col].unique() if x and str(x) != "nan" and str(x) != ""]
        return sorted(vals)
    return []
def get_index(options, value):
    try: return options.index(str(value))
    except: return 0

# ==========================================
# 3. ROLE VIEWS
# ==========================================

def authorizer_view(user):
    st.title(f"🛡️ Authorizer: {user}")
    df = load_data()
    
    # METRICS
    daily = len(df[df['assigned_date'] == get_current_date()])
    pend = len(df[df['status'] == 'Pending'])
    my_ready = len(df[(df['authorizer']==user) & (df['status']=='Ready for Auth')])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's LGs", daily)
    c2.metric("Global Pending", pend)
    c3.metric("Your Actions", my_ready)
    c4.metric("Total DB", len(df))
    
    tabs = st.tabs(["➕ Create", "⚡ Active", "✅ Review", "📂 Pendings", "📦 Originals", "📊 Master"])

    # 1. CREATE TASK
    with tabs[0]:
        c_s, _ = st.columns([1,2])
        lg_search = c_s.text_input("Search History (LG #):")
        
        # Defaults
        d_br=d_cif=d_app=d_ben=d_curr=d_type=d_md=d_req=d_amt=""; prev_tot=0.0
        if lg_search and not df.empty:
            hist = df[df['lg_number'] == lg_search]
            if not hist.empty:
                last = hist.iloc[-1]
                d_br=str(last['branch']); d_cif=str(last['cif']); d_app=str(last['applicant'])
                d_ben=str(last['beneficiary']); d_curr=str(last['currency']); d_type=str(last['lg_type'])
                d_md=str(last['md_ref']); d_req=str(last['req_type'])
                try: prev_tot = float(last['current_total'])
                except: prev_tot = 0.0
                if prev_tot == 0: prev_tot = float(last['amount']) if last['amount'] else 0
                st.toast(f"Found History. Current Total: {prev_tot:,.2f}")

        st.subheader("Client Info")
        col1, col2, col3 = st.columns(3)
        with col1:
            br_opts = get_unique(df, "branch") + ["New"]; br = st.selectbox("Branch", br_opts, index=get_index(br_opts, d_br))
            if br=="New": br=st.text_input("New Branch")
            cif_opts = get_unique(df, "cif") + ["New"]; cif = st.selectbox("CIF", cif_opts, index=get_index(cif_opts, d_cif))
            if cif=="New": cif=st.text_input("New CIF")
        with col2:
            app_opts = get_unique(df, "applicant") + ["New"]; app = st.selectbox("Applicant", app_opts, index=get_index(app_opts, d_app))
            if app=="New": app=st.text_input("New Applicant")
            ben_opts = get_unique(df, "beneficiary") + ["New"]; ben = st.selectbox("Beneficiary", ben_opts, index=get_index(ben_opts, d_ben))
            if ben=="New": ben=st.text_input("New Beneficiary")
        with col3:
            req_opts = get_unique(df, "req_type") + ["New"]; req = st.selectbox("Req Type", req_opts)
            if req=="New": req=st.text_input("New Req Type")

        st.subheader("Financials")
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            if "Increase" in req or "Decrease" in req:
                st.info(f"Prev Total: {prev_tot:,.2f}")
                txn_amt = st.number_input("Delta Amount", min_value=0.0)
                new_tot = prev_tot + txn_amt if "Increase" in req else prev_tot - txn_amt
                st.metric("New Total", f"{new_tot:,.2f}")
                final_amt=txn_amt; final_tot=new_tot
            else:
                final_amt = st.number_input("Amount", value=float(d_amt) if d_amt else 0.0)
                final_tot = final_amt
        with c_f2:
            curr_opts=["EGP","USD","EUR","GBP","SAR"]; curr=st.selectbox("Currency", curr_opts, index=get_index(curr_opts, d_curr))

        st.subheader("Details")
        c_d1, c_d2, c_d3 = st.columns(3)
        with c_d1:
            new_lg = st.text_input("LG Number", value=lg_search)
            types=["Bid Bond","Performance","Advance Payment","Retention","Final","Other"]
            lgt=st.selectbox("LG Type", types, index=get_index(types, d_type))
        with c_d2:
            ptype=st.radio("Post Type", ["Original", "Copy"], horizontal=True)
            md=st.text_input("MD Ref", value=d_md)
        with c_d3:
            # DYNAMIC INPUTTER LIST
            inputters_list = get_users_by_role("Inputter")
            if not inputters_list: inputters_list = ["No Inputters Found"]
            inp = st.selectbox("Assign To", inputters_list)
            comm_chg = st.text_input("Comm CHG Ref")

        if st.button("🚀 Assign Task", type="primary"):
            if not new_lg: st.error("LG # Required")
            else:
                new_row = pd.DataFrame([{
                    "task_id": str(uuid.uuid4()), "assigned_date": get_current_date(),
                    "lg_number": new_lg, "lg_type": lgt, "branch": br, "cif": cif,
                    "applicant": app, "beneficiary": ben, "inputter": inp, "authorizer": user,
                    "req_type": req, "amount": final_amt, "current_total": final_tot, "currency": curr,
                    "post_type": ptype, "md_ref": md, "comm_chg_ref": comm_chg, "status": "Active",
                    "file_sent": 0, "original_recvd": 0, "original_recv_date": "", "pending_reason": "", 
                    "to_be_started_on": "", "comm_amount": "", "comm_status": "", "cbe_serial": "", "postage_number": ""
                }])
                save_data(pd.concat([df, new_row], ignore_index=True))
                st.success("Assigned!"); time.sleep(1); st.rerun()

    # 2. MANAGE ACTIVE
    with tabs[1]:
        act = df[df['status']=='Active']
        if act.empty: st.info("No active tasks")
        else:
            st.dataframe(act[['lg_number','inputter','applicant']], use_container_width=True)
            sel = st.selectbox("Edit Active Task", act['lg_number'].unique())
            idx = df[df['lg_number']==sel].index[0]; row = df.iloc[idx]
            with st.form("edit_active"):
                c1, c2, c3 = st.columns(3)
                all_inps = get_users_by_role("Inputter")
                with c1: n_inp=st.selectbox("Inputter", all_inps, index=get_index(all_inps, row['inputter'])); n_md=st.text_input("MD", row['md_ref']); n_chg=st.text_input("Comm CHG", row['comm_chg_ref'])
                with c2: n_cbe=st.text_input("CBE", row['cbe_serial']); n_comm=st.text_input("Comm Amt", row['comm_amount']); n_fs=st.checkbox("File Sent", value=(float(row['file_sent'])==1))
                with c3: n_stat=st.selectbox("Status", COMM_OPTS, index=get_index(COMM_OPTS, row['comm_status'])); n_pno=st.text_input("Postage", row['postage_number'])
                
                if st.form_submit_button("Save"):
                    df.at[idx,'inputter']=n_inp; df.at[idx,'md_ref']=n_md; df.at[idx,'comm_chg_ref']=n_chg
                    df.at[idx,'cbe_serial']=n_cbe; df.at[idx,'comm_amount']=n_comm; df.at[idx,'file_sent']=1 if n_fs else 0
                    df.at[idx,'comm_status']=n_stat; df.at[idx,'postage_number']=n_pno
                    save_data(df); st.rerun()

    # 3. REVIEW
    with tabs[2]:
        my_tasks = df[(df['authorizer']==user) & (df['status']=='Ready for Auth')]
        if my_tasks.empty: st.info("Nothing to approve")
        else:
            sel = st.selectbox("Select to Action", my_tasks['lg_number'].unique())
            row = my_tasks[my_tasks['lg_number']==sel].iloc[0]; idx = df[df['task_id']==row['task_id']].index[0]
            with st.form("review_form"):
                c1, c2, c3 = st.columns(3)
                with c1: e_md=st.text_input("MD", row['md_ref']); e_comm=st.text_input("Comm", row['comm_amount']); e_chg=st.text_input("Comm CHG", row['comm_chg_ref'])
                with c2: e_st=st.selectbox("Comm Stat", COMM_OPTS, index=get_index(COMM_OPTS, row['comm_status'])); e_fs=st.checkbox("File Sent?")
                with c3: e_post=st.text_input("Postage", row['postage_number']); e_start=st.text_input("Start Date", row['to_be_started_on'])
                
                dec = st.radio("Decision", ["Approve", "Pending", "Return"], horizontal=True)
                reas = st.text_input("Reason")
                
                if st.form_submit_button("Execute"):
                    df.at[idx,'md_ref']=e_md; df.at[idx,'comm_amount']=e_comm; df.at[idx,'comm_status']=e_st; df.at[idx,'comm_chg_ref']=e_chg
                    df.at[idx,'postage_number']=e_post; df.at[idx,'to_be_started_on']=e_start
                    if dec=="Approve":
                        if not e_fs: st.error("Check File Sent")
                        else: df.at[idx,'status']='Completed'; df.at[idx,'file_sent']=1; save_data(df); st.rerun()
                    else:
                        df.at[idx,'status']='Pending' if dec=="Pending" else 'Active'
                        df.at[idx,'pending_reason']=reas; save_data(df); st.rerun()

    # 4. GLOBAL PENDINGS (SUPER EDIT)
    with tabs[3]:
        pends = df[df['status']=='Pending']
        st.dataframe(pends[['lg_number','pending_reason','inputter']], use_container_width=True)
        for i, row in pends.iterrows():
            with st.expander(f"Manage {row['lg_number']}"):
                c1, c2 = st.columns(2)
                with c1: 
                    n_md = st.text_input("MD", row['md_ref'], key=f"p_md{i}")
                    n_cbe = st.text_input("CBE", row['cbe_serial'], key=f"p_cb{i}")
                    n_comm = st.text_input("Comm", row['comm_amount'], key=f"p_cm{i}")
                with c2:
                    n_fs = st.checkbox("File Sent", value=(float(row['file_sent'])==1), key=f"p_fs{i}")
                    n_or = st.checkbox("Orig Recvd", value=(float(row['original_recvd'])==1), key=f"p_or{i}")
                    n_reas = st.text_input("Reason", row['pending_reason'], key=f"p_r{i}")
                
                dest = st.radio("To", ["Inputter","Authorizer"], key=f"d{i}")
                if st.button("Release", key=f"b{i}"):
                    idx = df[df['task_id']==row['task_id']].index[0]
                    df.at[idx,'md_ref']=n_md; df.at[idx,'cbe_serial']=n_cbe; df.at[idx,'comm_amount']=n_comm
                    df.at[idx,'file_sent']=1 if n_fs else 0; df.at[idx,'original_recvd']=1 if n_or else 0
                    df.at[idx,'pending_reason']=n_reas
                    df.at[idx,'status']='Active' if dest=="Inputter" else 'Ready for Auth'
                    save_data(df); st.rerun()

    # 5. MISSING ORIGINALS (SEARCHABLE)
    with tabs[4]:
        miss = df[(df['post_type']=='Copy') & (pd.to_numeric(df['original_recvd'])==0)]
        search = st.text_input("Search Missing LG:")
        opts = [l for l in miss['lg_number'].unique() if search.lower() in l.lower()] if search else miss['lg_number'].unique()
        
        if len(opts)>0:
            sel = st.selectbox("Mark Received", opts)
            dt = st.date_input("Date")
            if st.button("Confirm"):
                idx=df[df['lg_number']==sel].index[0]
                df.at[idx,'original_recvd']=1; df.at[idx,'original_recv_date']=str(dt); df.at[idx,'post_type']='Original'
                save_data(df); st.rerun()
        else: st.info("No matches")

    with tabs[5]: st.dataframe(df)

def inputter_view(user):
    st.title(f"⚡ Inputter: {user}")
    df = load_data()
    
    st.metric("Tasks", len(df[(df['inputter']==user) & (df['status']=='Active')]))
    tabs = st.tabs(["Tasks", "Watchlist", "Originals"])

    with tabs[0]:
        act = df[(df['inputter']==user) & (df['status']=='Active')]
        if not act.empty:
            sel = st.selectbox("Process", act['lg_number'].unique())
            row = act[act['lg_number']==sel].iloc[0]; idx=df[df['task_id']==row['task_id']].index[0]
            
            # DYNAMIC AUTHORIZER LIST
            auths_list = get_users_by_role("Authorizer")
            cur_auth = row['authorizer']
            n_auth = st.selectbox("To Authorizer", auths_list, index=get_index(auths_list, cur_auth))
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Send"):
                df.at[idx,'status']='Ready for Auth'; df.at[idx,'authorizer']=n_auth; save_data(df); st.rerun()
            
            reas = c2.text_input("Pending Reason")
            if c2.button("Mark Pending"):
                df.at[idx,'status']='Pending'; df.at[idx,'pending_reason']=reas; save_data(df); st.rerun()
        else: st.info("Done!")

    with tabs[1]:
        mine = df[(df['inputter']==user) & (df['status']=='Pending')]
        if not mine.empty:
            sel = st.selectbox("Fix", mine['lg_number'].unique())
            row = mine[mine['lg_number']==sel].iloc[0]; idx=df[df['task_id']==row['task_id']].index[0]
            with st.form("fix"):
                n_md=st.text_input("MD", row['md_ref']); n_st=st.selectbox("Stat", COMM_OPTS, index=get_index(COMM_OPTS, row['comm_status']))
                n_chg=st.text_input("Comm CHG", row['comm_chg_ref'])
                if st.form_submit_button("Resubmit"):
                    df.at[idx,'md_ref']=n_md; df.at[idx,'comm_status']=n_st; df.at[idx,'comm_chg_ref']=n_chg
                    df.at[idx,'status']='Ready for Auth'
                    save_data(df); st.rerun()
        else: st.info("Empty")

    with tabs[2]:
        miss = df[(df['post_type']=='Copy') & (pd.to_numeric(df['original_recvd'])==0)]
        search = st.text_input("Search Missing:", key="inps")
        opts = [l for l in miss['lg_number'].unique() if search.lower() in l.lower()] if search else miss['lg_number'].unique()
        if len(opts)>0:
            sel = st.selectbox("Found", opts, key="inpm")
            dt = st.date_input("Date", key="inpd")
            if st.button("Receive", key="inpb"):
                 idx=df[df['lg_number']==sel].index[0]
                 df.at[idx,'original_recvd']=1; df.at[idx,'original_recv_date']=str(dt); df.at[idx,'post_type']='Original'
                 save_data(df); st.rerun()

def admin_view():
    st.title("⚙️ Admin Panel")
    st.subheader("📊 App Data")
    df = load_data()
    st.dataframe(df, height=200)
    st.divider()
    st.subheader("👥 User Management")
    users_sheet = get_users_sheet()
    users_df = pd.DataFrame(users_sheet.get_all_records()).astype(str)
    
    t1, t2 = st.tabs(["View Users", "Add New User"])
    with t1:
        st.dataframe(users_df, use_container_width=True)
        st.info("Edit users directly in Google Sheets.")
    with t2:
        with st.form("add_user"):
            new_u = st.text_input("Username"); new_p = st.text_input("Password")
            new_r = st.selectbox("Role", ["Authorizer", "Inputter", "Admin"]); new_n = st.text_input("Full Name")
            if st.form_submit_button("Add User"):
                if new_u and new_p:
                    # Force password to string by adding a quote prefix or just relying on pandas read
                    users_sheet.append_row([str(new_u), str(new_p), str(new_r), str(new_n)])
                    st.success(f"User {new_u} added!"); time.sleep(1); st.rerun()
                else: st.error("Required fields missing")

def main():
    if "user" not in st.session_state: st.session_state.user = None
    
    if not st.session_state.user:
        c1,c2,c3 = st.columns([1,2,1])
        with c2:
            st.title("🔐 IC Audit Pro")
            with st.form("login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    users_df = load_users()
                    if not users_df.empty:
                        # STRING MATCHING
                        match = users_df[(users_df['username'] == str(u)) & (users_df['password'] == str(p))]
                        if not match.empty:
                            user_role = match.iloc[0]['role']
                            st.session_state.user = u
                            st.session_state.role = user_role
                            st.rerun()
                        else: st.error("Invalid Credentials")
                    else: st.error("No users found")
    else:
        with st.sidebar:
            st.write(f"User: {st.session_state.user}")
            st.write(f"Role: {st.session_state.role}")
            if st.button("Logout"):
                st.session_state.user = None; st.rerun()
        
        if st.session_state.role == "Admin": admin_view()
        elif st.session_state.role == "Authorizer": authorizer_view(st.session_state.user)
        elif st.session_state.role == "Inputter": inputter_view(st.session_state.user)

if __name__ == "__main__":
    main()
