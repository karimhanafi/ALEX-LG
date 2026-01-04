import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid
from datetime import datetime
import time
import pytz

# ==========================================
# 1. VISUAL SETUP
# ==========================================
st.set_page_config(page_title="Alex LG Workflow", layout="wide", page_icon="🏦")

st.markdown("""
    <style>
    /* MIDNIGHT BLUE THEME */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(to bottom right, #0f172a, #1e293b);
        color: #e2e8f0;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input, .stDateInput>div>div>input {
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
    /* Danger Button Style */
    div[data-testid="stExpander"] details summary p {
        color: #ef4444; 
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. GOOGLE SHEETS ENGINE
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource(ttl=600)
def get_client():
    try:
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"🔥 Network Error: {e}")
        return None

def get_main_sheet():
    client = get_client()
    if client:
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        return client.open_by_url(sheet_url).sheet1
    return None

def get_users_sheet():
    client = get_client()
    if client:
        sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        try:
            return client.open_by_url(sheet_url).worksheet("Users")
        except:
            return None
    return None

# --- DATA LOADERS ---
# UPDATED ORDER: LG_NUMBER IS NOW 3RD (Index 2)
COLUMNS = [
    "task_id", "assigned_date", "lg_number", "branch", "post_type", "inputter", 
    "req_type", "cif", "applicant", "in_favor_of", "beneficiary", "amount", "current_total", "currency", 
    "lg_type", "cbe_serial", "authorizer", "md_ref", 
    "postage_number", "comm_amount", "comm_status", "comm_chg_ref", "status", 
    "pending_reason", "to_be_started_on", "file_sent", "original_recvd", "original_recv_date"
]
COMM_OPTS = ["", "Collected", "Pending", "Due Comm."]

@st.cache_data(ttl=2) 
def load_data():
    try:
        wks = get_main_sheet()
        if not wks: return pd.DataFrame(columns=COLUMNS)
        
        data = wks.get_all_records()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame(columns=COLUMNS)
        
        for col in COLUMNS:
            if col not in df.columns: df[col] = ""
            
        for col in ['amount', 'current_total', 'file_sent', 'original_recvd', 'comm_amount']:
             if df[col].dtype == object:
                 df[col] = df[col].astype(str).str.replace(",", "")
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        df = df.astype(str)
        for col in ['status', 'lg_number', 'req_type', 'cif', 'applicant']:
            df[col] = df[col].str.strip()
            
        return df
    except: return pd.DataFrame(columns=COLUMNS)

def save_data(df):
    try:
        wks = get_main_sheet()
        if wks:
            wks.clear()
            df_clean = df.fillna("")
            wks.append_row(df_clean.columns.tolist())
            wks.append_rows(df_clean.values.tolist())
            load_data.clear()
            st.toast("☁️ Saved!", icon="✅")
            time.sleep(0.5)
    except Exception as e: st.error(f"Save Error: {e}")

# --- USER LOADING ---
@st.cache_data(ttl=300) 
def get_cached_users():
    try:
        wks = get_users_sheet()
        if not wks: return pd.DataFrame(columns=["username", "password", "role", "name"])
        data = wks.get_all_records()
        df = pd.DataFrame(data).astype(str)
        if 'username' in df.columns: df['username'] = df['username'].str.strip()
        if 'password' in df.columns: df['password'] = df['password'].str.strip()
        return df
    except: 
        return pd.DataFrame(columns=["username", "password", "role", "name"])

def get_users_by_role(role_name):
    try:
        users_df = get_cached_users()
        if not users_df.empty and "role" in users_df.columns:
            return users_df[users_df["role"] == role_name]["username"].tolist()
        return []
    except: return []

# --- HELPERS ---
def get_cairo_time(): return datetime.now(pytz.timezone('Africa/Cairo'))
def get_current_date(): return get_cairo_time().strftime("%d-%b-%Y")

def generate_task_id(df):
    today_str = get_current_date()
    if 'task_id' not in df.columns: return f"{today_str}-001"
    count_today = df['task_id'].astype(str).str.startswith(today_str).sum()
    new_seq = count_today + 1
    return f"{today_str}-{new_seq:03d}"

def get_unique(df, col):
    if col in df.columns:
        vals = [x for x in df[col].unique() if x and str(x) != "nan" and str(x) != ""]
        return sorted(vals)
    return []

def get_index(options, value):
    try: return options.index(str(value))
    except: return 0

# SMART SEARCH: Displays detailed info in dropdown
def smart_select_task(label, df_subset, key_suffix):
    task_map = {}
    for i, row in df_subset.iterrows():
        # MORE DETAILS ADDED TO LABEL
        display_label = f"{row['lg_number']} | {row['assigned_date']} | {row['branch']} | {row['beneficiary']} | {row['cif']}"
        task_map[display_label] = row['task_id']
    
    if not task_map: return None
    sel_label = st.selectbox(label, list(task_map.keys()), key=key_suffix)
    return task_map.get(sel_label)

# ==========================================
# 3. ROLE VIEWS
# ==========================================

def authorizer_view(user):
    st.title(f"🛡️ Authorizer: {user}")
    df = load_data()
    
    today_str = get_current_date()
    daily = len(df[df['assigned_date'] == today_str])
    pends = df[df['status'] == 'Pending']
    my_ready = len(df[(df['authorizer']==user) & (df['status']=='Ready for Auth')])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Today's LGs", daily)
    c2.metric("Global Pending", len(pends))
    c3.metric("Your Actions", my_ready)
    c4.metric("Total DB", len(df))
    
    # ADDED "DAILY REPORT" TAB
    tabs = st.tabs(["➕ Create", "⚡ Active", "✅ Review", "📂 Pendings", "📈 Daily Reports", "🛠️ Master Manager", "📦 Doc Tracking", "📊 Database"])

    # 1. CREATE TASK
    with tabs[0]:
        c_s, _ = st.columns([1,2])
        lg_search = c_s.text_input("Search History (LG #):")
        
        d_br=d_cif=d_app=d_fav=d_ben=d_curr=d_type=d_md=d_req=d_amt=""; prev_tot=0.0
        
        if lg_search and not df.empty:
            hist = df[df['lg_number'] == lg_search]
            if not hist.empty:
                last = hist.iloc[-1]
                d_br=str(last['branch']); d_cif=str(last['cif']); d_app=str(last['applicant'])
                d_ben=str(last['beneficiary']); d_fav=str(last.get('in_favor_of', ''))
                d_curr=str(last['currency']); d_type=str(last['lg_type'])
                d_md=str(last['md_ref']); d_req=str(last['req_type'])
                
                try: 
                    raw_curr = str(last['current_total']).replace(",","").strip()
                    prev_tot = float(raw_curr)
                except: prev_tot = 0.0
                if prev_tot == 0:
                    try: prev_tot = float(str(last['amount']).replace(",","").strip()) 
                    except: prev_tot = 0.0
                
                st.toast(f"History Found. Previous Total: {prev_tot:,.2f}")

        st.subheader("Client Info")
        col1, col2, col3 = st.columns(3)
        with col1:
            br_opts = get_unique(df, "branch") + ["New"]; br = st.selectbox("Branch", br_opts, index=get_index(br_opts, d_br))
            if br=="New": br=st.text_input("New Branch")
            
            cif_opts = get_unique(df, "cif") + ["New"]; cif = st.selectbox("CIF", cif_opts, index=get_index(cif_opts, d_cif))
            if cif=="New": cif=st.text_input("New CIF")
            
        with col2:
            # BIDIRECTIONAL LOGIC
            auto_app = d_app
            if cif != "New" and cif in df['cif'].values:
                match = df[df['cif']==cif]
                if not match.empty: auto_app = match.iloc[-1]['applicant']
            
            app_opts = get_unique(df, "applicant") + ["New"]
            app = st.selectbox("Applicant", app_opts, index=get_index(app_opts, auto_app))
            if app=="New": app=st.text_input("New Applicant")
            
            # Reverse: If Applicant selected, find CIF
            if app != "New" and app in df['applicant'].values:
                match_c = df[df['applicant']==app]
                if not match_c.empty: 
                    found_cif = match_c.iloc[-1]['cif']
                    if cif != found_cif: st.info(f"💡 Suggested CIF for {app}: {found_cif}")

            ben_opts = get_unique(df, "beneficiary") + ["New"]; ben = st.selectbox("Beneficiary", ben_opts, index=get_index(ben_opts, d_ben))
            if ben=="New": ben=st.text_input("New Beneficiary")
            
        with col3:
            fav_opts = get_unique(df, "in_favor_of") + ["New"]
            fav = st.selectbox("In Favor Of", fav_opts, index=get_index(fav_opts, d_fav))
            if fav=="New": fav=st.text_input("New In Favor Of")
            
            req_opts = get_unique(df, "req_type") + ["New"]; req = st.selectbox("Req Type", req_opts)
            if req=="New": req=st.text_input("New Req Type")

        st.subheader("Financials")
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            if "Increase" in req or "Decrease" in req:
                st.info(f"Base Value: {prev_tot:,.2f}")
                txn_amt = st.number_input("Delta Amount", min_value=0.0)
                new_tot = prev_tot + txn_amt if "Increase" in req else prev_tot - txn_amt
                st.metric("New Total", f"{new_tot:,.2f}")
                final_amt = prev_tot; final_tot = new_tot
            else:
                final_amt = st.number_input("Amount", value=prev_tot)
                final_tot = final_amt
        with c_f2:
            curr_opts=["EGP","USD","EUR","GBP","SAR"]; curr=st.selectbox("Currency", curr_opts, index=get_index(curr_opts, d_curr))

        st.subheader("Details")
        c_d1, c_d2, c_d3 = st.columns(3)
        with c_d1:
            new_lg = st.text_input("LG Number", value=lg_search)
            types=["Bid Bond","Performance (Final)","Advance Payment","Others"]
            lgt=st.selectbox("LG Type", types, index=get_index(types, d_type))
        with c_d2:
            ptype=st.radio("Post Type", ["Original", "Copy"], horizontal=True)
            md=st.text_input("MD Ref", value=d_md)
        with c_d3:
            inputters_list = get_users_by_role("Inputter")
            if not inputters_list: inputters_list = ["No Inputters Found"]
            inp = st.selectbox("Assign To", inputters_list)
            comm_chg = st.text_input("Comm CHG Ref")

        if st.button("🚀 Assign Task", type="primary"):
            if not new_lg: st.error("LG # Required")
            else:
                new_id = generate_task_id(df)
                new_row = pd.DataFrame([{
                    "task_id": new_id, "assigned_date": today_str,
                    "lg_number": new_lg, "lg_type": lgt, "branch": br, "cif": cif,
                    "applicant": app, "in_favor_of": fav, "beneficiary": ben, "inputter": inp, "authorizer": user,
                    "req_type": req, "amount": final_amt, "current_total": final_tot, "currency": curr,
                    "post_type": ptype, "md_ref": md, "comm_chg_ref": comm_chg, "status": "Active",
                    "file_sent": 0, "original_recvd": 0, "original_recv_date": "", "pending_reason": "", 
                    "to_be_started_on": "", "comm_amount": 0, "comm_status": "", "cbe_serial": "", "postage_number": ""
                }])
                save_data(pd.concat([df, new_row], ignore_index=True))
                st.success(f"Assigned! Task ID: {new_id}"); time.sleep(1); st.rerun()

    # 2. MANAGE ACTIVE
    with tabs[1]:
        act = df[df['status']=='Active']
        if act.empty: st.info("No active tasks")
        else:
            st.dataframe(act[['lg_number','req_type', 'amount', 'current_total', 'inputter']], use_container_width=True)
            sel_id = smart_select_task("Select Task to Edit", act, "act_sel")
            if sel_id:
                idx = df[df['task_id']==sel_id].index[0]; row = df.iloc[idx]
                st.info(f"ℹ️ Base Amount: {float(row['amount']):,.2f} | New Total: {float(row['current_total']):,.2f}")
                
                with st.form("edit_active"):
                    c1, c2, c3 = st.columns(3)
                    all_inps = get_users_by_role("Inputter")
                    with c1: n_inp=st.selectbox("Inputter", all_inps, index=get_index(all_inps, row['inputter'])); n_md=st.text_input("MD", row['md_ref']); n_chg=st.text_input("Comm CHG", row['comm_chg_ref'])
                    with c2: n_cbe=st.text_input("CBE", row['cbe_serial']); n_comm=st.number_input("Comm Amt", value=float(row['comm_amount'])); n_fs=st.checkbox("File Sent", value=(float(row['file_sent'])==1))
                    with c3: n_stat=st.selectbox("Status", COMM_OPTS, index=get_index(COMM_OPTS, row['comm_status'])); n_pno=st.text_input("Postage", row['postage_number'])
                    if st.form_submit_button("Save Changes"):
                        df.at[idx,'inputter']=n_inp; df.at[idx,'md_ref']=n_md; df.at[idx,'comm_chg_ref']=n_chg
                        df.at[idx,'cbe_serial']=n_cbe; df.at[idx,'comm_amount']=n_comm; df.at[idx,'file_sent']=1 if n_fs else 0
                        df.at[idx,'comm_status']=n_stat; df.at[idx,'postage_number']=n_pno
                        save_data(df); st.rerun()

                st.markdown("---")
                with st.expander("🗑️ Danger Zone"):
                    if st.button("Permanently Delete Task", type="primary"):
                        new_df = df[df['task_id'] != sel_id]
                        save_data(new_df); st.success("Task Deleted!"); time.sleep(1); st.rerun()

    # 3. REVIEW (Commission Math Added)
    with tabs[2]:
        my_tasks = df[(df['authorizer']==user) & (df['status']=='Ready for Auth')]
        if my_tasks.empty: st.info("Nothing to approve")
        else:
            sel_id = smart_select_task("Select to Action", my_tasks, "rev_sel")
            if sel_id:
                idx = df[df['task_id']==sel_id].index[0]; row = df.iloc[idx]
                with st.form("review_form"):
                    st.write(f"Actioning: **{row['lg_number']}** | {row['req_type']}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1: 
                        e_md=st.text_input("MD", row['md_ref'])
                        
                        # COMM MATH
                        st.caption("Commission Calculation")
                        base_comm = st.number_input("Base Comm", value=float(row['comm_amount']))
                        pend_comm = st.number_input("Pending Comm (+)", value=0.0)
                        
                        e_chg=st.text_input("Comm CHG", row['comm_chg_ref'])
                    with c2: 
                        e_cbe=st.text_input("CBE Serial", row['cbe_serial'])
                        e_st=st.selectbox("Comm Stat", COMM_OPTS, index=get_index(COMM_OPTS, row['comm_status']))
                    with c3: 
                        e_post=st.text_input("Postage Number", row['postage_number'])
                        e_start=st.text_input("To be done on", row['to_be_started_on'])
                    
                    st.divider()
                    dec = st.radio("Decision", ["Approve", "Pending", "Return"], horizontal=True)
                    reas = st.text_input("Reason")
                    
                    if st.form_submit_button("Execute"):
                        total_comm_calc = base_comm + pend_comm # SUM
                        
                        df.at[idx,'md_ref']=e_md; df.at[idx,'comm_amount']=total_comm_calc; df.at[idx,'comm_status']=e_st
                        df.at[idx,'comm_chg_ref']=e_chg; df.at[idx,'cbe_serial']=e_cbe
                        df.at[idx,'postage_number']=e_post; df.at[idx,'to_be_started_on']=e_start
                        
                        if dec=="Approve":
                            df.at[idx,'status']='Completed'
                            save_data(df); st.success(f"Approved! Total Comm: {total_comm_calc}"); time.sleep(1); st.rerun()
                        else:
                            df.at[idx,'status']='Pending' if dec=="Pending" else 'Active'
                            df.at[idx,'pending_reason']=reas; save_data(df); st.rerun()

    # 4. GLOBAL PENDINGS
    with tabs[3]:
        st.dataframe(pends[['lg_number','pending_reason','inputter','authorizer']], use_container_width=True)
        for i, row in pends.iterrows():
            with st.expander(f"Manage {row['lg_number']} ({row['authorizer']})"):
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

    # 5. DAILY REPORTS (NEW)
    with tabs[4]:
        st.subheader(f"📊 Daily Report: {today_str}")
        
        today_df = df[df['assigned_date'] == today_str]
        
        if not today_df.empty:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Transactions", len(today_df))
            
            # Calc Total Comm
            total_comm_today = today_df['comm_amount'].sum()
            m2.metric("Total Comm Collected", f"{total_comm_today:,.2f}")
            
            # Modes
            top_inp = today_df['inputter'].mode()[0] if not today_df['inputter'].mode().empty else "N/A"
            top_auth = today_df['authorizer'].mode()[0] if not today_df['authorizer'].mode().empty else "N/A"
            m3.metric("Top Inputter", top_inp)
            m4.metric("Top Authorizer", top_auth)
            
            st.divider()
            
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                st.markdown("**By Request Type**")
                st.dataframe(today_df['req_type'].value_counts(), use_container_width=True)
            with c_r2:
                st.markdown("**By LG Type**")
                st.dataframe(today_df['lg_type'].value_counts(), use_container_width=True)
        else:
            st.info("No transactions today.")

    # 6. MASTER MANAGER (UPDATED WITH NEW FIELDS)
    with tabs[5]:
        st.subheader("🛠️ Master Task Manager")
        search_q = st.text_input("Search Anything:", placeholder="LG, CIF, etc.")
        
        if search_q:
            mask = df.apply(lambda x: x.astype(str).str.contains(search_q, case=False)).any(axis=1)
            results = df[mask]
            
            if not results.empty:
                st.dataframe(results[['lg_number', 'status', 'applicant']], use_container_width=True)
                sel_m_id = smart_select_task("Select to Manage", results, "master_sel")
                
                if sel_m_id:
                    idx = df[df['task_id']==sel_m_id].index[0]; row = df.iloc[idx]
                    
                    with st.form("master_edit"):
                        # ALL FIELDS
                        mc1, mc2, mc3 = st.columns(3)
                        with mc1:
                            m_stat = st.selectbox("Status", ["Active", "Ready for Auth", "Pending", "Completed"], index=get_index(["Active", "Ready for Auth", "Pending", "Completed"], row['status']))
                            m_auth = st.selectbox("Authorizer", get_users_by_role("Authorizer"), index=get_index(get_users_by_role("Authorizer"), row['authorizer']))
                            m_post = st.text_input("Postage 1", row['postage_number']) # Can handle multi via text
                            m_post2 = st.text_input("Postage 2 (Optional)", "") # Extra field, can append to Postage 1 if needed or just display
                            m_start = st.text_input("To be done on", row['to_be_started_on'])
                        with mc2:
                            m_inp = st.selectbox("Inputter", get_users_by_role("Inputter"), index=get_index(get_users_by_role("Inputter"), row['inputter']))
                            m_cbe = st.text_input("CBE", row['cbe_serial'])
                            m_md = st.text_input("MD", row['md_ref'])
                            m_amt = st.number_input("Amount", float(row['amount']))
                        with mc3:
                            m_comm = st.number_input("Comm Amt", float(row['comm_amount']))
                            m_chg = st.text_input("Comm CHG", row['comm_chg_ref'])
                            m_curr = st.number_input("Current Total", float(row['current_total']))
                            m_fs = st.checkbox("File Sent", value=(float(row['file_sent'])==1))
                            m_or = st.checkbox("Orig Recvd", value=(float(row['original_recvd'])==1))

                        c_del, c_save = st.columns([1, 2])
                        with c_del: delete = st.checkbox("DELETE PERMANENTLY")
                        with c_save:
                            if st.form_submit_button("Update Task"):
                                if delete:
                                    new_df = df[df['task_id'] != sel_m_id]
                                    save_data(new_df); st.success("Deleted!"); time.sleep(1); st.rerun()
                                else:
                                    # Combine postage if needed or just save 1
                                    final_post = m_post + (f" | {m_post2}" if m_post2 else "")
                                    df.at[idx,'status']=m_stat; df.at[idx,'authorizer']=m_auth; df.at[idx,'postage_number']=final_post
                                    df.at[idx,'inputter']=m_inp; df.at[idx,'cbe_serial']=m_cbe; df.at[idx,'md_ref']=m_md
                                    df.at[idx,'comm_amount']=m_comm; df.at[idx,'file_sent']=1 if m_fs else 0; df.at[idx,'original_recvd']=1 if m_or else 0
                                    df.at[idx,'amount']=m_amt; df.at[idx,'current_total']=m_curr; df.at[idx,'comm_chg_ref']=m_chg
                                    df.at[idx,'to_be_started_on']=m_start
                                    save_data(df); st.success("Updated!"); time.sleep(1); st.rerun()
            else: st.info("No tasks found.")

    # 7. DOC TRACKING
    with tabs[6]:
        st.subheader("📦 Document Tracking")
        pending_sent = df[(df['status']=='Completed') & (pd.to_numeric(df['file_sent'])==0)]
        with st.expander(f"📤 Pending File Sent ({len(pending_sent)})", expanded=True):
            if not pending_sent.empty:
                st.dataframe(pending_sent[['lg_number', 'applicant', 'inputter']], use_container_width=True)
                sent_id = smart_select_task("Mark File Sent", pending_sent, "fs_sel")
                if sent_id:
                    if st.button("Confirm File Sent"):
                        idx = df[df['task_id']==sent_id].index[0]
                        df.at[idx, 'file_sent'] = 1
                        save_data(df); st.success("Updated!"); st.rerun()
            else: st.success("All approved files sent.")
            
        st.divider()

        miss = df[(df['post_type']=='Copy') & (pd.to_numeric(df['original_recvd'])==0)]
        with st.expander(f"📥 Missing Originals ({len(miss)})", expanded=True):
            if not miss.empty:
                st.dataframe(miss[['lg_number', 'branch', 'inputter']], use_container_width=True)
                search = st.text_input("Search Missing LG:")
                opts = miss
                if search: opts = miss[miss['lg_number'].str.contains(search, case=False)]
                
                miss_id = smart_select_task("Mark Original Received", opts, "miss_sel")
                if miss_id:
                    dt = st.date_input("Date Received")
                    if st.button("Confirm Original Received"):
                        idx=df[df['task_id']==miss_id].index[0]
                        df.at[idx,'original_recvd']=1; df.at[idx,'original_recv_date']=str(dt); df.at[idx,'post_type']='Original'
                        save_data(df); st.rerun()
            else: st.success("All originals received.")

    # 8. DATABASE (Master Table Back)
    with tabs[7]: 
        st.dataframe(df, use_container_width=True)

def inputter_view(user):
    st.title(f"⚡ Inputter: {user}")
    df = load_data()
    
    st.metric("Tasks", len(df[(df['inputter']==user) & (df['status']=='Active')]))
    tabs = st.tabs(["Tasks", "Watchlist", "Doc Tracking"])

    with tabs[0]:
        act = df[(df['inputter']==user) & (df['status']=='Active')]
        if not act.empty:
            st.dataframe(act[['lg_number','req_type', 'beneficiary', 'amount']], use_container_width=True)
            sel_id = smart_select_task("Process Task", act, "inp_act_sel")
            
            if sel_id:
                idx = df[df['task_id']==sel_id].index[0]; row = df.iloc[idx]
                st.info(f"ℹ️ Base: {row['amount']} | New Total: {row['current_total']}")
                
                auths_list = get_users_by_role("Authorizer")
                cur_auth = row['authorizer']
                
                c_md, c_auth = st.columns(2)
                with c_md: new_md = st.text_input("MD Ref", value=row['md_ref'])
                with c_auth: n_auth = st.selectbox("To Authorizer", auths_list, index=get_index(auths_list, cur_auth))
                
                c1, c2 = st.columns(2)
                if c1.button("✅ Send"):
                    df.at[idx,'status']='Ready for Auth'; df.at[idx,'authorizer']=n_auth; df.at[idx,'md_ref']=new_md
                    save_data(df); st.rerun()
                
                reas = c2.text_input("Pending Reason")
                if c2.button("Mark Pending"):
                    df.at[idx,'status']='Pending'; df.at[idx,'pending_reason']=reas; save_data(df); st.rerun()
        else: st.info("Done!")

    with tabs[1]:
        mine = df[(df['inputter']==user) & (df['status']=='Pending')]
        if not mine.empty:
            sel_id = smart_select_task("Fix Task", mine, "inp_watch_sel")
            if sel_id:
                idx = df[df['task_id']==sel_id].index[0]; row = df.iloc[idx]
                with st.form("fix"):
                    n_md=st.text_input("MD", row['md_ref']); n_st=st.selectbox("Stat", COMM_OPTS, index=get_index(COMM_OPTS, row['comm_status']))
                    n_chg=st.text_input("Comm CHG", row['comm_chg_ref'])
                    if st.form_submit_button("Resubmit"):
                        df.at[idx,'md_ref']=n_md; df.at[idx,'comm_status']=n_st; df.at[idx,'comm_chg_ref']=n_chg
                        df.at[idx,'status']='Ready for Auth'
                        save_data(df); st.rerun()
        else: st.info("Empty")

    with tabs[2]:
        st.subheader("📦 Document Tracking")
        pending_sent = df[(df['status']=='Completed') & (pd.to_numeric(df['file_sent'])==0)]
        with st.expander(f"📤 Pending File Sent ({len(pending_sent)})", expanded=True):
            if not pending_sent.empty:
                st.dataframe(pending_sent[['lg_number', 'applicant', 'inputter']], use_container_width=True)
                sent_id = smart_select_task("Mark File Sent", pending_sent, "inp_fs_sel")
                if sent_id:
                    if st.button("Confirm File Sent"):
                        idx = df[df['task_id']==sent_id].index[0]
                        df.at[idx, 'file_sent'] = 1
                        save_data(df); st.success("Updated!"); st.rerun()
            else: st.success("All approved files sent.")
            
        st.divider()

        miss = df[(df['post_type']=='Copy') & (pd.to_numeric(df['original_recvd'])==0)]
        with st.expander(f"📥 Missing Originals ({len(miss)})", expanded=True):
            if not miss.empty:
                st.dataframe(miss[['lg_number', 'branch', 'inputter']], use_container_width=True)
                search = st.text_input("Search Missing:", key="inps")
                opts = miss
                if search: opts = miss[miss['lg_number'].str.contains(search, case=False)]
                
                miss_id = smart_select_task("Found Original", opts, "inp_miss_sel")
                if miss_id:
                    dt = st.date_input("Date", key="inpd")
                    if st.button("Receive", key="inpb"):
                         idx=df[df['task_id']==miss_id].index[0]
                         df.at[idx,'original_recvd']=1; df.at[idx,'original_recv_date']=str(dt); df.at[idx,'post_type']='Original'
                         save_data(df); st.rerun()
            else: st.success("All originals received.")

def admin_view():
    st.title("⚙️ Admin Panel")
    st.subheader("📊 App Data")
    df = load_data()
    st.dataframe(df, height=200)
    st.divider()
    st.subheader("👥 User Management")
    users_df = get_cached_users()
    t1, t2 = st.tabs(["View Users", "Add New User"])
    with t1:
        st.dataframe(users_df, use_container_width=True)
        st.info("Edit users directly in Google Sheets.")
    with t2:
        with st.form("add_user"):
            new_u = st.text_input("Username"); new_p = st.text_input("Password")
            new_r = st.selectbox("Role", ["Authorizer", "Inputter", "Admin"]); new_n = st.text_input("Full Name")
            if st.form_submit_button("Add User"):
                wks = get_users_sheet()
                if wks and new_u and new_p:
                    wks.append_row([str(new_u), str(new_p), str(new_r), str(new_n)])
                    st.success(f"User {new_u} added!"); get_cached_users.clear(); time.sleep(1); st.rerun()
                else: st.error("Error connecting or missing fields")

def main():
    if "user" not in st.session_state: st.session_state.user = None
    
    if not st.session_state.user:
        c1,c2,c3 = st.columns([1,2,1])
        with c2:
            st.title("🔐 Alex LG Workflow")
            with st.form("login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    users_df = get_cached_users()
                    if not users_df.empty:
                        match = users_df[(users_df['username'] == str(u)) & (users_df['password'] == str(p))]
                        if not match.empty:
                            user_role = match.iloc[0]['role']
                            st.session_state.user = u
                            st.session_state.role = user_role
                            st.rerun()
                        else: st.error("Invalid Credentials")
                    else: st.error("System Error: Check Users Sheet")
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
