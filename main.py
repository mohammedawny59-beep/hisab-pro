import os,sqlite3,hashlib,json
from flask import Flask,request,jsonify,session,send_file,redirect,Response
from datetime import date
from functools import wraps

app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY','hisab2025')
DB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data','hisab.db')

def db():
    os.makedirs(os.path.dirname(DB),exist_ok=True)
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute("PRAGMA foreign_keys=ON");return c

def q1(sql,p=()):c=db();r=c.execute(sql,p).fetchone();c.close();return r
def qa(sql,p=()):c=db();r=c.execute(sql,p).fetchall();c.close();return r

def init():
    os.makedirs(os.path.dirname(DB),exist_ok=True)
    conn=sqlite3.connect(DB);conn.row_factory=sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS companies(id INTEGER PRIMARY KEY,name TEXT DEFAULT 'شركة الفجر التجارية',currency TEXT DEFAULT 'KWD',address TEXT DEFAULT '',phone TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,company_id INTEGER DEFAULT 1,name TEXT,email TEXT UNIQUE,password_hash TEXT,role TEXT DEFAULT 'accountant',is_active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY,company_id INTEGER DEFAULT 1,code TEXT,name TEXT,type TEXT,parent_id INTEGER,level INTEGER DEFAULT 2,is_active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS journal_entries(id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER DEFAULT 1,number TEXT,date TEXT,description TEXT,type TEXT DEFAULT 'manual',status TEXT DEFAULT 'draft',currency TEXT DEFAULT 'KWD',reference TEXT DEFAULT '',created_by INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS journal_lines(id INTEGER PRIMARY KEY AUTOINCREMENT,entry_id INTEGER,account_id INTEGER,account_text TEXT DEFAULT '',debit REAL DEFAULT 0,credit REAL DEFAULT 0,description TEXT DEFAULT '',cost_center TEXT DEFAULT '',line_order INTEGER DEFAULT 0,FOREIGN KEY(entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS counters(key TEXT PRIMARY KEY,value INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER DEFAULT 1,number TEXT,date TEXT,due_date TEXT,client_name TEXT,client_id INTEGER,description TEXT,amount REAL DEFAULT 0,tax REAL DEFAULT 0,total REAL DEFAULT 0,paid REAL DEFAULT 0,status TEXT DEFAULT 'draft',notes TEXT DEFAULT '',created_by INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS invoice_lines(id INTEGER PRIMARY KEY AUTOINCREMENT,invoice_id INTEGER,description TEXT,qty REAL DEFAULT 1,price REAL DEFAULT 0,total REAL DEFAULT 0,FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER DEFAULT 1,number TEXT,date TEXT,vendor TEXT,category TEXT,description TEXT,amount REAL DEFAULT 0,payment_method TEXT DEFAULT 'cash',account_id INTEGER,status TEXT DEFAULT 'pending',notes TEXT DEFAULT '',created_by INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER DEFAULT 1,type TEXT DEFAULT 'customer',name TEXT,phone TEXT DEFAULT '',email TEXT DEFAULT '',address TEXT DEFAULT '',tax_number TEXT DEFAULT '',notes TEXT DEFAULT '',balance REAL DEFAULT 0,is_active INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS bank_accounts(id INTEGER PRIMARY KEY AUTOINCREMENT,company_id INTEGER DEFAULT 1,name TEXT,bank_name TEXT,account_number TEXT DEFAULT '',currency TEXT DEFAULT 'KWD',balance REAL DEFAULT 0,is_active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS bank_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,bank_account_id INTEGER,date TEXT,description TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,balance REAL DEFAULT 0,reference TEXT DEFAULT '',is_reconciled INTEGER DEFAULT 0,FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id));
    """)
    if not conn.execute("SELECT COUNT(*) n FROM companies").fetchone()['n']:
        seed(conn)
    conn.commit();conn.close()

def seed(conn):
    conn.execute("INSERT INTO companies VALUES(1,'شركة الفجر التجارية','KWD','الكويت','')")
    pw=hashlib.sha256('123456'.encode()).hexdigest()
    conn.execute("INSERT INTO users VALUES(1,1,'أحمد محمد','admin@demo.com',?,'admin',1)",(pw,))
    accs=[('1','الأصول','asset',None,0),('11','الأصول المتداولة','asset',1,1),
          ('1001','الصندوق','asset',2,2),('1002','البنك الأهلي','asset',2,2),
          ('1003','المدينون','asset',2,2),('1004','المخزون','asset',2,2),
          ('12','الأصول الثابتة','asset',1,1),('1201','الأثاث والمعدات','asset',7,2),
          ('1202','مجمع الإهلاك','asset',7,2),
          ('2','الخصوم','liability',None,0),('21','الخصوم المتداولة','liability',10,1),
          ('2001','الدائنون','liability',11,2),('2002','قروض قصيرة الأجل','liability',11,2),
          ('22','الخصوم طويلة الأجل','liability',10,1),('2201','قروض طويلة الأجل','liability',14,2),
          ('3','حقوق الملكية','equity',None,0),('3001','رأس المال','equity',16,2),
          ('3002','الأرباح المحتجزة','equity',16,2),
          ('4','الإيرادات','revenue',None,0),('4001','إيرادات المبيعات','revenue',19,2),
          ('4002','إيرادات الخدمات','revenue',19,2),('4003','إيرادات أخرى','revenue',19,2),
          ('5','المصاريف','expense',None,0),('5001','مصروف الإيجار','expense',23,2),
          ('5002','مصروف الرواتب','expense',23,2),('5003','مصروف الكهرباء','expense',23,2),
          ('5004','مصروف المواصلات','expense',23,2),('5005','مصروف الصيانة','expense',23,2)]
    for i,(code,name,tp,pid,lvl) in enumerate(accs,1):
        conn.execute("INSERT INTO accounts VALUES(?,1,?,?,?,?,?,1)",(i,code,name,tp,pid,lvl))
    entries=[
        ('JE-2025-0001','2025-01-01','إيداع رأس المال','approved',[(3,20000,0),(17,0,20000)]),
        ('JE-2025-0002','2025-01-05','إيجار مكتب يناير','approved',[(24,500,0),(3,0,500)]),
        ('JE-2025-0003','2025-01-10','مبيعات نقدية','approved',[(3,1200,0),(20,0,1200)]),
        ('JE-2025-0004','2025-01-15','فاتورة كهرباء','approved',[(26,45,0),(3,0,45)]),
        ('JE-2025-0005','2025-01-31','رواتب يناير','approved',[(25,3500,0),(4,0,3500)])]
    for num,dt,desc,status,lines in entries:
        conn.execute("INSERT INTO journal_entries(company_id,number,date,description,type,status,created_by)VALUES(1,?,?,?,'manual',?,1)",(num,dt,desc,status))
        eid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for i,(aid,dr,cr) in enumerate(lines):
            conn.execute("INSERT INTO journal_lines(entry_id,account_id,debit,credit,line_order)VALUES(?,?,?,?,?)",(eid,aid,dr,cr,i))
    conn.execute("INSERT OR REPLACE INTO counters VALUES('journal',5)")
    conn.execute("INSERT OR REPLACE INTO counters VALUES('invoice',0)")
    conn.execute("INSERT OR REPLACE INTO counters VALUES('expense',0)")
    # Sample contacts
    conn.execute("INSERT INTO contacts(company_id,type,name,phone,email)VALUES(1,'customer','شركة الغانم للتجارة','22345678','info@ghanim.com')")
    conn.execute("INSERT INTO contacts(company_id,type,name,phone,email)VALUES(1,'customer','مستشفى العدان','23345566','info@adan.com')")
    conn.execute("INSERT INTO contacts(company_id,type,name,phone)VALUES(1,'vendor','شركة الكهرباء','18888888')")
    conn.execute("INSERT INTO contacts(company_id,type,name,phone)VALUES(1,'vendor','مركز الصيانة','22998877')")
    # Sample bank accounts
    conn.execute("INSERT INTO bank_accounts(company_id,name,bank_name,account_number,currency,balance)VALUES(1,'البنك الأهلي الكويتي','البنك الأهلي','1234-5678-90','KWD',18750.000)")
    conn.execute("INSERT INTO bank_accounts(company_id,name,bank_name,account_number,currency,balance)VALUES(1,'بنك الكويت الوطني','بنك الكويت الوطني','9876-5432-10','KWD',5200.000)")
    # Sample invoices
    conn.execute("INSERT INTO invoices(company_id,number,date,due_date,client_name,description,amount,tax,total,paid,status)VALUES(1,'INV-2025-001','2025-01-05','2025-02-05','شركة الغانم للتجارة','خدمات استشارية يناير',3200,0,3200,3200,'paid')")
    conn.execute("INSERT INTO invoices(company_id,number,date,due_date,client_name,description,amount,tax,total,paid,status)VALUES(1,'INV-2025-002','2025-01-10','2025-02-10','مستشفى العدان','خدمات طبية',1500,0,1500,0,'overdue')")
    conn.execute("INSERT INTO invoices(company_id,number,date,due_date,client_name,description,amount,tax,total,paid,status)VALUES(1,'INV-2025-003','2025-01-20','2025-02-20','شركة الغانم للتجارة','توريدات مكتبية',4800,0,4800,2400,'partial')")
    conn.execute("INSERT OR REPLACE INTO counters VALUES('invoice',3)")
    # Sample expenses
    conn.execute("INSERT INTO expenses(company_id,number,date,vendor,category,description,amount,payment_method,status)VALUES(1,'EXP-2025-001','2025-01-03','شركة الكهرباء','مرافق','فاتورة كهرباء يناير',45,'transfer','approved')")
    conn.execute("INSERT INTO expenses(company_id,number,date,vendor,category,description,amount,payment_method,status)VALUES(1,'EXP-2025-002','2025-01-05','مجمع السالمية','إيجار','إيجار مكتب يناير',500,'transfer','approved')")
    conn.execute("INSERT INTO expenses(company_id,number,date,vendor,category,description,amount,payment_method,status)VALUES(1,'EXP-2025-003','2025-01-12','مركز الصيانة','صيانة','صيانة أجهزة الحاسوب',350,'cash','pending')")
    conn.execute("INSERT INTO expenses(company_id,number,date,vendor,category,description,amount,payment_method,status)VALUES(1,'EXP-2025-004','2025-01-31','—','رواتب','رواتب موظفين يناير',3500,'transfer','approved')")
    conn.execute("INSERT OR REPLACE INTO counters VALUES('expense',4)")

def hp(p):return hashlib.sha256(p.encode()).hexdigest()

def auth(f):
    @wraps(f)
    def d(*a,**k):
        if 'uid' not in session:return jsonify({'error':'unauthorized'}),401
        return f(*a,**k)
    return d

def nxt(conn):
    r=conn.execute("SELECT value FROM counters WHERE key='journal'").fetchone()
    n=(r['value'] if r else 0)+1
    conn.execute("INSERT OR REPLACE INTO counters VALUES('journal',?)",(n,))
    return f"JE-{date.today().year}-{n:04d}",n

@app.route('/')
def index():
    if 'uid' not in session:return redirect('/login')
    return send_file('app.html')

@app.route('/login')
def login_page():return send_file('login.html')

@app.route('/logout')
def logout():session.clear();return redirect('/login')

@app.route('/api/login',methods=['POST'])
def api_login():
    d=request.get_json() or {}
    email=(d.get('email') or '').strip().lower()
    pw=d.get('password') or ''
    conn=db()
    u=conn.execute("SELECT u.*,c.name cn,c.currency FROM users u JOIN companies c ON c.id=u.company_id WHERE lower(u.email)=? AND u.is_active=1",(email,)).fetchone()
    conn.close()
    if u and u['password_hash']==hp(pw):
        session.update({'uid':u['id'],'cid':u['company_id'],'uname':u['name'],'coname':u['cn'],'curr':u['currency'],'role':u['role']})
        return jsonify({'success':True})
    return jsonify({'success':False,'error':'البريد الإلكتروني أو كلمة المرور غير صحيحة'})

@app.route('/api/me')
def api_me():
    if 'uid' not in session:return jsonify({'error':'unauthorized'}),401
    return jsonify({'id':session['uid'],'name':session['uname'],'company_name':session['coname'],'currency':session.get('curr','KWD'),'role':session.get('role','accountant')})

@app.route('/api/dashboard/stats')
@auth
def api_stats():
    cid=session['cid']
    r=q1("SELECT COALESCE(SUM(jl.debit),0)td,COALESCE(SUM(jl.credit),0)tc,COUNT(DISTINCT je.id)cnt FROM journal_lines jl JOIN journal_entries je ON je.id=jl.entry_id WHERE je.company_id=?",(cid,))
    exp=qa("SELECT a.name,COALESCE(SUM(jl.debit),0)t FROM journal_lines jl JOIN accounts a ON a.id=jl.account_id JOIN journal_entries je ON je.id=jl.entry_id WHERE je.company_id=? AND a.type='expense' AND jl.debit>0 GROUP BY a.id ORDER BY t DESC LIMIT 6",(cid,))
    td,tc=float(r['td']),float(r['tc'])
    return jsonify({'total_debit':td,'total_credit':tc,'net':tc-td,'count':r['cnt'] or 0,'expenses':[{'name':e['name'],'total':float(e['t'])} for e in exp]})

@app.route('/api/journal')
@auth
def api_journal():
    cid=session['cid']
    yr=request.args.get('year',str(date.today().year))
    q=request.args.get('q','')
    rows=qa("SELECT je.id,je.number,je.date,je.description,je.type,je.status,COALESCE(SUM(jl.debit),0)debit,COALESCE(SUM(jl.credit),0)credit FROM journal_entries je LEFT JOIN journal_lines jl ON jl.entry_id=je.id WHERE je.company_id=? AND strftime('%Y',je.date)=? AND(je.description LIKE ? OR je.number LIKE ?) GROUP BY je.id ORDER BY je.date DESC,je.id DESC",(cid,yr,f'%{q}%',f'%{q}%'))
    return jsonify([dict(r) for r in rows])

@app.route('/api/journal/<int:eid>')
@auth
def api_journal_get(eid):
    cid=session['cid']
    entry=q1("SELECT * FROM journal_entries WHERE id=? AND company_id=?",(eid,cid))
    if not entry:return jsonify({'error':'not found'}),404
    lines=qa("SELECT jl.*,a.code acc_code,a.name acc_name FROM journal_lines jl LEFT JOIN accounts a ON a.id=jl.account_id WHERE jl.entry_id=? ORDER BY jl.line_order",(eid,))
    return jsonify({'entry':dict(entry),'lines':[dict(l) for l in lines]})

@app.route('/api/journal/next-number')
@auth
def api_next():
    conn=db()
    r=conn.execute("SELECT value FROM counters WHERE key='journal'").fetchone()
    n=(r['value'] if r else 0)+1
    conn.close()
    return jsonify({'number':f"JE-{date.today().year}-{n:04d}",'counter':n})

@app.route('/api/journal/save',methods=['POST'])
@auth
def api_save():
    cid=session['cid']
    d=request.get_json() or {}
    desc=(d.get('description') or '').strip()
    if not desc:return jsonify({'success':False,'error':'البيان مطلوب'})
    lines=[l for l in (d.get('lines') or []) if float(l.get('debit',0) or 0)>0 or float(l.get('credit',0) or 0)>0]
    if len(lines)<2:return jsonify({'success':False,'error':'يجب إدخال سطرين على الأقل'})
    dt=d.get('date') or str(date.today())
    etype=d.get('type','manual');curr=d.get('currency','KWD');ref=(d.get('reference') or '').strip()
    eid=d.get('edit_id')
    conn=db()
    try:
        if eid:
            conn.execute("UPDATE journal_entries SET date=?,description=?,type=?,currency=?,reference=? WHERE id=? AND company_id=?",(dt,desc,etype,curr,ref,eid,cid))
            conn.execute("DELETE FROM journal_lines WHERE entry_id=?",(eid,))
            number=d.get('number','')
        else:
            number,_=nxt(conn)
            conn.execute("INSERT INTO journal_entries(company_id,number,date,description,type,status,currency,reference,created_by)VALUES(?,?,?,?,?,?,?,?,?)",(cid,number,dt,desc,etype,'draft',curr,ref,session['uid']))
            eid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for i,l in enumerate(lines):
            aid=l.get('account_id') or None
            atxt=(l.get('account') or '').strip()
            if not aid and atxt:
                code=atxt.split('—')[0].strip().split()[0] if atxt else ''
                row=conn.execute("SELECT id FROM accounts WHERE company_id=? AND code=?",(cid,code)).fetchone()
                if row:aid=row['id']
            conn.execute("INSERT INTO journal_lines(entry_id,account_id,account_text,debit,credit,description,cost_center,line_order)VALUES(?,?,?,?,?,?,?,?)",(eid,aid,atxt,float(l.get('debit',0) or 0),float(l.get('credit',0) or 0),(l.get('description') or ''),(l.get('cost_center') or ''),i))
        conn.commit()
        nnum,nc=nxt(conn);conn.commit()
        return jsonify({'success':True,'number':number,'next_number':nnum,'counter':nc,'id':eid})
    except Exception as e:return jsonify({'success':False,'error':str(e)})
    finally:conn.close()

@app.route('/api/journal/<int:eid>/delete',methods=['POST'])
@auth
def api_del(eid):
    cid=session['cid'];conn=db()
    conn.execute("DELETE FROM journal_entries WHERE id=? AND company_id=?",(eid,cid))
    conn.commit();conn.close()
    return jsonify({'success':True})

@app.route('/api/journal/<int:eid>/print')
@auth
def api_print(eid):
    cid=session['cid'];conn=db()
    entry=conn.execute("SELECT * FROM journal_entries WHERE id=? AND company_id=?",(eid,cid)).fetchone()
    if not entry:conn.close();return "Not found",404
    lines=conn.execute("SELECT jl.*,a.code acc_code,a.name acc_name FROM journal_lines jl LEFT JOIN accounts a ON a.id=jl.account_id WHERE jl.entry_id=? ORDER BY jl.line_order",(eid,)).fetchall()
    co=conn.execute("SELECT * FROM companies WHERE id=?",(cid,)).fetchone()
    conn.close()
    td=sum(float(l['debit'] or 0) for l in lines);tc=sum(float(l['credit'] or 0) for l in lines)
    def fc(v):return f"{float(v or 0):,.3f}" if float(v or 0)>0 else '—'
    rows=''.join(f"<tr><td>{l['description'] or ''}</td><td>{l['cost_center'] or ''}</td><td class='cr'>{fc(l['credit'])}</td><td class='dr'>{fc(l['debit'])}</td><td>{l['acc_name'] or l['account_text'] or '—'}</td><td class='code'>{l['acc_code'] or '—'}</td></tr>" for l in lines)
    return Response(f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>قيد {entry['number']}</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet">
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'IBM Plex Sans Arabic',sans-serif;background:#060d1a;color:#e2e8f0;padding:32px;direction:rtl}}
.nb{{text-align:center;margin-bottom:24px}}.nb button{{background:linear-gradient(135deg,#10B981,#059669);color:white;border:none;padding:14px 48px;border-radius:12px;font-size:16px;cursor:pointer;font-family:inherit;font-weight:700}}
.card{{max-width:900px;margin:0 auto;background:#0a0f1e;border-radius:16px;border:1px solid #1e3a5f;overflow:hidden}}
.hdr{{background:linear-gradient(135deg,#0f1e3c,#1e3a5f);padding:24px 32px;display:flex;justify-content:space-between;align-items:center;border-bottom:3px solid #3B82F6}}
.hdr h1{{font-size:22px;font-weight:800;color:white}}.num{{font-size:32px;font-weight:900;color:#38BDF8}}
.meta{{padding:16px 32px;background:#0d1525;border-bottom:1px solid #1e293b;display:flex;gap:28px;flex-wrap:wrap}}
.meta strong{{color:#cbd5e1;font-size:12px;display:block}}.meta span{{color:#94a3b8;font-size:12px}}
table{{width:100%;border-collapse:collapse}}th{{background:#080f1e;color:#38BDF8;padding:12px;font-size:11px;border-bottom:1px solid #1e3a5f;font-weight:700}}
td{{padding:12px;border-bottom:1px solid rgba(30,41,59,.6);font-size:13px}}tr:nth-child(even) td{{background:rgba(30,41,59,.3)}}
.dr{{color:#4ade80;font-weight:700;text-align:left}}.cr{{color:#f87171;font-weight:700;text-align:left}}.code{{font-family:monospace;color:#818cf8}}
.foot td{{background:#080f1e!important;font-weight:700;border-top:2px solid #1e3a5f;padding:14px 12px}}
.sigs{{display:flex;justify-content:space-around;padding:32px;border-top:1px solid #1e293b}}
.sig{{border-top:1px solid #334155;margin-top:52px;padding-top:8px;font-size:11px;color:#475569;text-align:center;min-width:130px}}
@media print{{.nb{{display:none}}body{{background:#fff;color:#000}}}}</style></head>
<body><div class="nb"><button onclick="window.print()">🖨️ طباعة القيد</button></div>
<div class="card"><div class="hdr"><div><h1>📒 قيد يومي</h1><p style="color:#94a3b8;font-size:12px;margin-top:4px">{co['name'] if co else ''}</p></div><div class="num">{entry['number']}</div></div>
<div class="meta"><div><strong>التاريخ</strong><span>{entry['date']}</span></div><div><strong>البيان</strong><span>{entry['description']}</span></div><div><strong>المرجع</strong><span>{entry['reference'] or '—'}</span></div><div><strong>الحالة</strong><span>{'✅ متوازن' if abs(td-tc)<0.001 else '⚠️'}</span></div></div>
<table><thead><tr><th>ملاحظة</th><th>مركز ت.</th><th>دائن</th><th>مدين</th><th>اسم الحساب</th><th>رقم</th></tr></thead>
<tbody>{rows}</tbody><tfoot><tr class="foot"><td colspan="2"></td><td class="cr">{tc:,.3f}</td><td class="dr">{td:,.3f}</td><td colspan="2" style="text-align:center;color:#94a3b8">الإجمالي</td></tr></tfoot></table>
<div class="sigs"><div><div class="sig">المحاسب</div></div><div><div class="sig">المراجع</div></div><div><div class="sig">المدير المالي</div></div></div></div></body></html>""",mimetype='text/html')

@app.route('/api/accounts/search')
@auth
def api_acc():
    cid=session['cid'];q=request.args.get('q','').strip()
    if q:
        rows=qa("SELECT id,code,name,type FROM accounts WHERE company_id=? AND level=2 AND is_active=1 AND(code LIKE ? OR name LIKE ?) ORDER BY code LIMIT 20",(cid,f'%{q}%',f'%{q}%'))
    else:
        rows=qa("SELECT id,code,name,type FROM accounts WHERE company_id=? AND level=2 AND is_active=1 ORDER BY code LIMIT 30",(cid,))
    return jsonify([{'id':r['id'],'code':r['code'],'name':r['name'],'type':r['type']} for r in rows])


@app.route('/api/accounts')
@auth
def api_all_accounts():
    cid=session['cid']
    rows=qa("SELECT * FROM accounts WHERE company_id=? ORDER BY code",(cid,))
    return jsonify([dict(r) for r in rows])

@app.route('/api/accounts/add',methods=['POST'])
@auth
def api_add_account():
    cid=session['cid']
    d=request.get_json() or {}
    code=(d.get('code') or '').strip()
    name=(d.get('name') or '').strip()
    tp=d.get('type','expense')
    pid=d.get('parent_id') or None
    lvl=int(d.get('level',2))
    if not code or not name: return jsonify({'success':False,'error':'الكود والاسم مطلوبان'})
    conn=db()
    try:
        conn.execute("INSERT INTO accounts(company_id,code,name,type,parent_id,level)VALUES(?,?,?,?,?,?)",(cid,code,name,tp,pid,lvl))
        conn.commit()
        return jsonify({'success':True})
    except Exception as e: return jsonify({'success':False,'error':str(e)})
    finally: conn.close()

@app.route('/api/accounts/<int:aid>/delete',methods=['POST'])
@auth
def api_del_account(aid):
    cid=session['cid']
    conn=db()
    used=conn.execute("SELECT COUNT(*) n FROM journal_lines WHERE account_id=?",(aid,)).fetchone()
    if used['n']>0: conn.close(); return jsonify({'success':False,'error':'لا يمكن حذف حساب له حركات'})
    conn.execute("DELETE FROM accounts WHERE id=? AND company_id=?",(aid,cid))
    conn.commit(); conn.close()
    return jsonify({'success':True})

@app.route('/api/reports/income')
@auth
def api_report_income():
    cid=session['cid']
    rev=qa("SELECT a.name,COALESCE(SUM(jl.credit)-SUM(jl.debit),0)amount FROM accounts a JOIN journal_lines jl ON jl.account_id=a.id JOIN journal_entries je ON je.id=jl.entry_id WHERE je.company_id=? AND a.type='revenue' GROUP BY a.id ORDER BY a.code",(cid,))
    exp=qa("SELECT a.name,COALESCE(SUM(jl.debit)-SUM(jl.credit),0)amount FROM accounts a JOIN journal_lines jl ON jl.account_id=a.id JOIN journal_entries je ON je.id=jl.entry_id WHERE je.company_id=? AND a.type='expense' GROUP BY a.id ORDER BY a.code",(cid,))
    tr=sum(float(r['amount'] or 0) for r in rev); te=sum(float(e['amount'] or 0) for e in exp)
    return jsonify({'revenues':[dict(r) for r in rev],'expenses':[dict(e) for e in exp],'total_rev':tr,'total_exp':te,'net':tr-te})

@app.route('/api/reports/balance-sheet')
@auth
def api_report_balance():
    cid=session['cid']
    def gt(tp): return qa("SELECT a.name,COALESCE(SUM(jl.debit)-SUM(jl.credit),0)amount FROM accounts a LEFT JOIN journal_lines jl ON jl.account_id=a.id LEFT JOIN journal_entries je ON je.id=jl.entry_id AND je.company_id=? WHERE a.company_id=? AND a.type=? AND a.level=2 GROUP BY a.id ORDER BY a.code",(cid,cid,tp))
    assets=gt('asset'); liabilities=gt('liability'); equity=gt('equity')
    return jsonify({'assets':[dict(r) for r in assets],'total_assets':sum(float(r['amount'] or 0) for r in assets),'liabilities':[dict(r) for r in liabilities],'total_liabilities':sum(float(r['amount'] or 0) for r in liabilities),'equity':[dict(r) for r in equity],'total_equity':sum(float(r['amount'] or 0) for r in equity)})

@app.route('/api/reports/trial-balance')
@auth
def api_report_trial():
    cid=session['cid']
    accs=qa("SELECT a.code,a.name,a.type,COALESCE(SUM(jl.debit),0)total_debit,COALESCE(SUM(jl.credit),0)total_credit FROM accounts a LEFT JOIN journal_lines jl ON jl.account_id=a.id LEFT JOIN journal_entries je ON je.id=jl.entry_id AND je.company_id=? WHERE a.company_id=? AND a.level=2 GROUP BY a.id ORDER BY a.code",(cid,cid))
    return jsonify([dict(a) for a in accs])

@app.route('/api/reports/ledger')
@auth
def api_report_ledger():
    cid=session['cid']
    aid=request.args.get('account_id')
    if not aid: return jsonify([])
    rows=qa("SELECT je.number,je.date,je.description,jl.debit,jl.credit FROM journal_lines jl JOIN journal_entries je ON je.id=jl.entry_id WHERE je.company_id=? AND jl.account_id=? ORDER BY je.date,je.id",(cid,aid))
    return jsonify([dict(r) for r in rows])

@app.route('/api/settings',methods=['GET','POST'])
@auth
def api_settings():
    cid=session['cid']
    if request.method=='POST':
        d=request.get_json() or {}
        name=(d.get('company_name') or '').strip()
        curr=d.get('currency','KWD')
        addr=(d.get('address') or '').strip()
        phone=(d.get('phone') or '').strip()
        conn=db()
        if name:
            conn.execute("UPDATE companies SET name=?,currency=?,address=?,phone=? WHERE id=?",(name,curr,addr,phone,cid))
            conn.commit(); session['coname']=name; session['curr']=curr
        conn.close()
        return jsonify({'success':True})
    co=q1("SELECT * FROM companies WHERE id=?",(cid,))
    return jsonify(dict(co) if co else {})

@app.route('/print/income')
@auth
def print_income():
    cid=session['cid']
    co=q1("SELECT * FROM companies WHERE id=?",(cid,))
    rev=qa("SELECT a.name,COALESCE(SUM(jl.credit)-SUM(jl.debit),0)amount FROM accounts a JOIN journal_lines jl ON jl.account_id=a.id JOIN journal_entries je ON je.id=jl.entry_id WHERE je.company_id=? AND a.type='revenue' GROUP BY a.id ORDER BY a.code",(cid,))
    exp=qa("SELECT a.name,COALESCE(SUM(jl.debit)-SUM(jl.credit),0)amount FROM accounts a JOIN journal_lines jl ON jl.account_id=a.id JOIN journal_entries je ON je.id=jl.entry_id WHERE je.company_id=? AND a.type='expense' GROUP BY a.id ORDER BY a.code",(cid,))
    tr=sum(float(r['amount'] or 0) for r in rev); te=sum(float(e['amount'] or 0) for e in exp); net=tr-te
    def f(v): return f"{float(v or 0):,.3f}"
    rr=''.join(f"<tr><td>{r['name']}</td><td class='n'>{f(r['amount'])}</td></tr>" for r in rev)
    er=''.join(f"<tr><td>{e['name']}</td><td class='n'>{f(e['amount'])}</td></tr>" for e in exp)
    return Response(f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>قائمة الدخل</title><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet"><style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'IBM Plex Sans Arabic',sans-serif;background:#060d1a;color:#e2e8f0;padding:32px;direction:rtl}}.nb{{text-align:center;margin-bottom:24px}}.nb button{{background:linear-gradient(135deg,#10B981,#059669);color:white;border:none;padding:14px 48px;border-radius:12px;font-size:16px;cursor:pointer;font-family:inherit;font-weight:700}}.card{{max-width:700px;margin:0 auto;background:#0a0f1e;border-radius:16px;border:1px solid #1e3a5f;padding:32px}}h2{{font-size:20px;font-weight:800;color:white;text-align:center;margin-bottom:6px}}.sub{{text-align:center;color:#94a3b8;font-size:12px;margin-bottom:24px}}.st{{font-weight:700;border-bottom:1px solid #1e293b;padding-bottom:8px;margin-bottom:10px;font-size:14px}}.em{{color:#10B981}}.ro{{color:#F43F5E}}table{{width:100%;border-collapse:collapse;margin-bottom:16px}}td{{padding:7px 12px;border-bottom:1px solid rgba(30,41,59,.6);font-size:13px}}.n{{text-align:left;font-family:monospace;font-weight:600}}.tot td{{background:rgba(255,255,255,.04)!important;font-weight:700;border-top:2px solid #1e3a5f;padding:10px 12px}}.net{{display:flex;justify-content:space-between;padding:16px;background:rgba(56,189,248,.08);border:1px solid rgba(56,189,248,.2);border-radius:12px;font-size:16px;font-weight:700}}@media print{{.nb{{display:none}}}}</style></head><body><div class="nb"><button onclick="window.print()">🖨️ طباعة</button></div><div class="card"><h2>قائمة الدخل</h2><div class="sub">{co['name'] if co else ''}</div><div class="st em">الإيرادات</div><table>{rr}<tr class="tot"><td>إجمالي الإيرادات</td><td class="n em">{f(tr)}</td></tr></table><div class="st ro">المصاريف</div><table>{er}<tr class="tot"><td>إجمالي المصاريف</td><td class="n ro">{f(te)}</td></tr></table><div class="net"><span>💰 صافي الربح</span><span style="color:{'#10B981' if net>=0 else '#F43F5E'}">{f(net)} KWD</span></div></div></body></html>""",mimetype='text/html')

@app.route('/print/balance')
@auth
def print_balance():
    cid=session['cid']
    co=q1("SELECT * FROM companies WHERE id=?",(cid,))
    def gt(tp): return qa("SELECT a.name,COALESCE(SUM(jl.debit)-SUM(jl.credit),0)amount FROM accounts a LEFT JOIN journal_lines jl ON jl.account_id=a.id LEFT JOIN journal_entries je ON je.id=jl.entry_id AND je.company_id=? WHERE a.company_id=? AND a.type=? AND a.level=2 GROUP BY a.id ORDER BY a.code",(cid,cid,tp))
    assets=gt('asset'); liabilities=gt('liability'); equity=gt('equity')
    def f(v): return f"{float(v or 0):,.3f}"
    def sec(title,items,color):
        rows=''.join(f"<tr><td>{i['name']}</td><td class='n'>{f(i['amount'])}</td></tr>" for i in items)
        total=sum(float(i['amount'] or 0) for i in items)
        return f'<div class="st" style="color:{color}">{title}</div><table>{rows}<tr class="tot"><td>الإجمالي</td><td class="n" style="color:{color}">{f(total)}</td></tr></table>'
    return Response(f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>الميزانية العمومية</title><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet"><style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'IBM Plex Sans Arabic',sans-serif;background:#060d1a;color:#e2e8f0;padding:32px;direction:rtl}}.nb{{text-align:center;margin-bottom:24px}}.nb button{{background:linear-gradient(135deg,#10B981,#059669);color:white;border:none;padding:14px 48px;border-radius:12px;font-size:16px;cursor:pointer;font-family:inherit;font-weight:700}}.card{{max-width:700px;margin:0 auto;background:#0a0f1e;border-radius:16px;border:1px solid #1e3a5f;padding:32px}}h2{{font-size:20px;font-weight:800;color:white;text-align:center;margin-bottom:6px}}.sub{{text-align:center;color:#94a3b8;font-size:12px;margin-bottom:24px}}.st{{font-weight:700;border-bottom:1px solid #1e293b;padding-bottom:8px;margin-bottom:10px;font-size:14px}}table{{width:100%;border-collapse:collapse;margin-bottom:16px}}td{{padding:7px 12px;border-bottom:1px solid rgba(30,41,59,.6);font-size:13px}}.n{{text-align:left;font-family:monospace;font-weight:600}}.tot td{{background:rgba(255,255,255,.04)!important;font-weight:700;border-top:2px solid #1e3a5f;padding:10px 12px}}@media print{{.nb{{display:none}}}}</style></head><body><div class="nb"><button onclick="window.print()">🖨️ طباعة</button></div><div class="card"><h2>الميزانية العمومية</h2><div class="sub">{co['name'] if co else ''}</div>{sec('الأصول',assets,'#3B82F6')}{sec('الخصوم',liabilities,'#F43F5E')}{sec('حقوق الملكية',equity,'#10B981')}</div></body></html>""",mimetype='text/html')

@app.route('/print/trial')
@auth
def print_trial():
    cid=session['cid']
    co=q1("SELECT * FROM companies WHERE id=?",(cid,))
    accs=qa("SELECT a.code,a.name,COALESCE(SUM(jl.debit),0)td,COALESCE(SUM(jl.credit),0)tc FROM accounts a LEFT JOIN journal_lines jl ON jl.account_id=a.id LEFT JOIN journal_entries je ON je.id=jl.entry_id AND je.company_id=? WHERE a.company_id=? AND a.level=2 GROUP BY a.id ORDER BY a.code",(cid,cid))
    def f(v): return f"{float(v or 0):,.3f}"
    total_dr=sum(float(a['td'] or 0) for a in accs); total_cr=sum(float(a['tc'] or 0) for a in accs)
    rows=''.join(f"<tr><td style='font-family:monospace;color:#38BDF8'>{a['code']}</td><td>{a['name']}</td><td class='dr'>{f(a['td']) if float(a['td'] or 0)>0 else '—'}</td><td class='cr'>{f(a['tc']) if float(a['tc'] or 0)>0 else '—'}</td></tr>" for a in accs)
    return Response(f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>ميزان المراجعة</title><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;600;700&display=swap" rel="stylesheet"><style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'IBM Plex Sans Arabic',sans-serif;background:#060d1a;color:#e2e8f0;padding:32px;direction:rtl}}.nb{{text-align:center;margin-bottom:24px}}.nb button{{background:linear-gradient(135deg,#10B981,#059669);color:white;border:none;padding:14px 48px;border-radius:12px;font-size:16px;cursor:pointer;font-family:inherit;font-weight:700}}.card{{max-width:800px;margin:0 auto;background:#0a0f1e;border-radius:16px;border:1px solid #1e3a5f;overflow:hidden}}h2{{font-size:20px;font-weight:800;color:white;text-align:center;padding:20px;background:#0f1e3c;border-bottom:3px solid #3B82F6}}table{{width:100%;border-collapse:collapse}}th{{background:#080f1e;color:#38BDF8;padding:12px;font-size:11px;border-bottom:1px solid #1e3a5f;font-weight:700}}td{{padding:11px 12px;border-bottom:1px solid rgba(30,41,59,.6);font-size:13px}}tr:nth-child(even) td{{background:rgba(30,41,59,.3)}}.dr{{text-align:left;color:#4ade80;font-family:monospace;font-weight:600}}.cr{{text-align:left;color:#f87171;font-family:monospace;font-weight:600}}.foot td{{background:#080f1e!important;font-weight:700;border-top:2px solid #1e3a5f;padding:14px 12px}}@media print{{.nb{{display:none}}}}</style></head><body><div class="nb"><button onclick="window.print()">🖨️ طباعة</button></div><div class="card"><h2>ميزان المراجعة — {co['name'] if co else ''}</h2><table><thead><tr><th>الكود</th><th>اسم الحساب</th><th>مدين</th><th>دائن</th></tr></thead><tbody>{rows}</tbody><tfoot><tr class="foot"><td colspan="2">الإجمالي</td><td class="dr">{f(total_dr)}</td><td class="cr">{f(total_cr)}</td></tr></tfoot></table></div></body></html>""",mimetype='text/html')

# ══════════════════════════════════════════════════
# API — INVOICES
# ══════════════════════════════════════════════════
@app.route('/api/invoices')
@auth
def api_invoices():
    cid=session['cid']
    q=request.args.get('q',''); status=request.args.get('status','')
    sql="SELECT * FROM invoices WHERE company_id=?"
    params=[cid]
    if q: sql+=" AND(client_name LIKE ? OR number LIKE ? OR description LIKE ?)"; params+=[f'%{q}%',f'%{q}%',f'%{q}%']
    if status: sql+=" AND status=?"; params.append(status)
    sql+=" ORDER BY date DESC,id DESC"
    rows=qa(sql,params)
    return jsonify([dict(r) for r in rows])

@app.route('/api/invoices/<int:iid>')
@auth
def api_invoice_get(iid):
    cid=session['cid']
    inv=q1("SELECT * FROM invoices WHERE id=? AND company_id=?",(iid,cid))
    if not inv: return jsonify({'error':'not found'}),404
    lines=qa("SELECT * FROM invoice_lines WHERE invoice_id=?",(iid,))
    return jsonify({'invoice':dict(inv),'lines':[dict(l) for l in lines]})

@app.route('/api/invoices/save',methods=['POST'])
@auth
def api_invoice_save():
    cid=session['cid']; d=request.get_json() or {}
    client=(d.get('client_name') or '').strip()
    desc=(d.get('description') or '').strip()
    if not client: return jsonify({'success':False,'error':'اسم العميل مطلوب'})
    dt=d.get('date') or str(date.today())
    due=d.get('due_date') or ''
    lines=d.get('lines') or []
    total=sum(float(l.get('total',0) or 0) for l in lines) or float(d.get('amount',0) or 0)
    tax=float(d.get('tax',0) or 0); grand=total+tax
    paid=float(d.get('paid',0) or 0)
    status='paid' if paid>=grand>0 else 'partial' if paid>0 else d.get('status','draft')
    edit_id=d.get('edit_id')
    conn=db()
    try:
        if edit_id:
            conn.execute("UPDATE invoices SET date=?,due_date=?,client_name=?,description=?,amount=?,tax=?,total=?,paid=?,status=? WHERE id=? AND company_id=?",(dt,due,client,desc,total,tax,grand,paid,status,edit_id,cid))
            conn.execute("DELETE FROM invoice_lines WHERE invoice_id=?",(edit_id,)); iid=edit_id
            number=d.get('number','')
        else:
            r=conn.execute("SELECT value FROM counters WHERE key='invoice'").fetchone()
            n=(r['value'] if r else 0)+1
            conn.execute("INSERT OR REPLACE INTO counters VALUES('invoice',?)",(n,))
            number=f"INV-{date.today().year}-{n:03d}"
            conn.execute("INSERT INTO invoices(company_id,number,date,due_date,client_name,description,amount,tax,total,paid,status,created_by)VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(cid,number,dt,due,client,desc,total,tax,grand,paid,status,session['uid']))
            iid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for l in lines:
            conn.execute("INSERT INTO invoice_lines(invoice_id,description,qty,price,total)VALUES(?,?,?,?,?)",(iid,l.get('description',''),float(l.get('qty',1) or 1),float(l.get('price',0) or 0),float(l.get('total',0) or 0)))
        conn.commit()
        return jsonify({'success':True,'number':number,'id':iid})
    except Exception as e: return jsonify({'success':False,'error':str(e)})
    finally: conn.close()

@app.route('/api/invoices/<int:iid>/delete',methods=['POST'])
@auth
def api_invoice_delete(iid):
    cid=session['cid']; conn=db()
    conn.execute("DELETE FROM invoices WHERE id=? AND company_id=?",(iid,cid))
    conn.commit(); conn.close()
    return jsonify({'success':True})

@app.route('/api/invoices/stats')
@auth
def api_invoice_stats():
    cid=session['cid']
    r=qa("SELECT status,COUNT(*)cnt,COALESCE(SUM(total),0)total FROM invoices WHERE company_id=? GROUP BY status",(cid,))
    stats={row['status']:{'count':row['cnt'],'total':float(row['total'])} for row in r}
    all_total=q1("SELECT COALESCE(SUM(total),0)t,COALESCE(SUM(paid),0)p FROM invoices WHERE company_id=?",(cid,))
    return jsonify({'by_status':stats,'total':float(all_total['t']),'paid':float(all_total['p']),'outstanding':float(all_total['t'])-float(all_total['p'])})

# ══════════════════════════════════════════════════
# API — EXPENSES
# ══════════════════════════════════════════════════
@app.route('/api/expenses')
@auth
def api_expenses():
    cid=session['cid']
    q=request.args.get('q',''); cat=request.args.get('category','')
    sql="SELECT * FROM expenses WHERE company_id=?"
    params=[cid]
    if q: sql+=" AND(vendor LIKE ? OR description LIKE ? OR number LIKE ?)"; params+=[f'%{q}%',f'%{q}%',f'%{q}%']
    if cat: sql+=" AND category=?"; params.append(cat)
    sql+=" ORDER BY date DESC,id DESC"
    return jsonify([dict(r) for r in qa(sql,params)])

@app.route('/api/expenses/save',methods=['POST'])
@auth
def api_expense_save():
    cid=session['cid']; d=request.get_json() or {}
    desc=(d.get('description') or '').strip()
    if not desc: return jsonify({'success':False,'error':'الوصف مطلوب'})
    vendor=(d.get('vendor') or '').strip()
    cat=(d.get('category') or 'عام').strip()
    dt=d.get('date') or str(date.today())
    amount=float(d.get('amount',0) or 0)
    method=d.get('payment_method','cash')
    status=d.get('status','pending')
    edit_id=d.get('edit_id')
    conn=db()
    try:
        if edit_id:
            conn.execute("UPDATE expenses SET date=?,vendor=?,category=?,description=?,amount=?,payment_method=?,status=? WHERE id=? AND company_id=?",(dt,vendor,cat,desc,amount,method,status,edit_id,cid))
            number=d.get('number',''); eid=edit_id
        else:
            r=conn.execute("SELECT value FROM counters WHERE key='expense'").fetchone()
            n=(r['value'] if r else 0)+1
            conn.execute("INSERT OR REPLACE INTO counters VALUES('expense',?)",(n,))
            number=f"EXP-{date.today().year}-{n:03d}"
            conn.execute("INSERT INTO expenses(company_id,number,date,vendor,category,description,amount,payment_method,status,created_by)VALUES(?,?,?,?,?,?,?,?,?,?)",(cid,number,dt,vendor,cat,desc,amount,method,status,session['uid']))
            eid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        return jsonify({'success':True,'number':number,'id':eid})
    except Exception as e: return jsonify({'success':False,'error':str(e)})
    finally: conn.close()

@app.route('/api/expenses/<int:eid>/delete',methods=['POST'])
@auth
def api_expense_delete(eid):
    cid=session['cid']; conn=db()
    conn.execute("DELETE FROM expenses WHERE id=? AND company_id=?",(eid,cid))
    conn.commit(); conn.close()
    return jsonify({'success':True})

@app.route('/api/expenses/stats')
@auth
def api_expense_stats():
    cid=session['cid']
    total=q1("SELECT COALESCE(SUM(amount),0)t,COUNT(*)c FROM expenses WHERE company_id=?",(cid,))
    cats=qa("SELECT category,COALESCE(SUM(amount),0)total FROM expenses WHERE company_id=? GROUP BY category ORDER BY total DESC",(cid,))
    return jsonify({'total':float(total['t']),'count':total['c'],'by_category':[dict(c) for c in cats]})

# ══════════════════════════════════════════════════
# API — CONTACTS
# ══════════════════════════════════════════════════
@app.route('/api/contacts')
@auth
def api_contacts():
    cid=session['cid']
    ctype=request.args.get('type',''); q=request.args.get('q','')
    sql="SELECT * FROM contacts WHERE company_id=? AND is_active=1"
    params=[cid]
    if ctype: sql+=" AND type=?"; params.append(ctype)
    if q: sql+=" AND(name LIKE ? OR phone LIKE ? OR email LIKE ?)"; params+=[f'%{q}%',f'%{q}%',f'%{q}%']
    sql+=" ORDER BY name"
    return jsonify([dict(r) for r in qa(sql,params)])

@app.route('/api/contacts/save',methods=['POST'])
@auth
def api_contact_save():
    cid=session['cid']; d=request.get_json() or {}
    name=(d.get('name') or '').strip()
    if not name: return jsonify({'success':False,'error':'الاسم مطلوب'})
    ctype=d.get('type','customer'); phone=(d.get('phone') or '').strip()
    email=(d.get('email') or '').strip(); addr=(d.get('address') or '').strip()
    notes=(d.get('notes') or '').strip(); edit_id=d.get('edit_id')
    conn=db()
    try:
        if edit_id:
            conn.execute("UPDATE contacts SET type=?,name=?,phone=?,email=?,address=?,notes=? WHERE id=? AND company_id=?",(ctype,name,phone,email,addr,notes,edit_id,cid))
            cid2=edit_id
        else:
            conn.execute("INSERT INTO contacts(company_id,type,name,phone,email,address,notes)VALUES(?,?,?,?,?,?,?)",(cid,ctype,name,phone,email,addr,notes))
            cid2=conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        return jsonify({'success':True,'id':cid2})
    except Exception as e: return jsonify({'success':False,'error':str(e)})
    finally: conn.close()

@app.route('/api/contacts/<int:cid2>/delete',methods=['POST'])
@auth
def api_contact_delete(cid2):
    cid=session['cid']; conn=db()
    conn.execute("UPDATE contacts SET is_active=0 WHERE id=? AND company_id=?",(cid2,cid))
    conn.commit(); conn.close()
    return jsonify({'success':True})

# ══════════════════════════════════════════════════
# API — BANKS
# ══════════════════════════════════════════════════
@app.route('/api/banks')
@auth
def api_banks():
    cid=session['cid']
    accs=qa("SELECT * FROM bank_accounts WHERE company_id=? AND is_active=1 ORDER BY name",(cid,))
    return jsonify([dict(a) for a in accs])

@app.route('/api/banks/<int:bid>/transactions')
@auth
def api_bank_transactions(bid):
    rows=qa("SELECT * FROM bank_transactions WHERE bank_account_id=? ORDER BY date DESC,id DESC LIMIT 50",(bid,))
    return jsonify([dict(r) for r in rows])

@app.route('/api/banks/save',methods=['POST'])
@auth
def api_bank_save():
    cid=session['cid']; d=request.get_json() or {}
    name=(d.get('name') or '').strip()
    if not name: return jsonify({'success':False,'error':'اسم الحساب مطلوب'})
    conn=db()
    try:
        conn.execute("INSERT INTO bank_accounts(company_id,name,bank_name,account_number,currency,balance)VALUES(?,?,?,?,?,?)",(cid,name,(d.get('bank_name') or ''),(d.get('account_number') or ''),(d.get('currency') or 'KWD'),float(d.get('balance',0) or 0)))
        conn.commit()
        return jsonify({'success':True})
    except Exception as e: return jsonify({'success':False,'error':str(e)})
    finally: conn.close()

# ══════════════════════════════════════════════════
# API — USERS MANAGEMENT
# ══════════════════════════════════════════════════
@app.route('/api/users')
@auth
def api_users():
    if session.get('role')!='admin': return jsonify({'error':'forbidden'}),403
    cid=session['cid']
    users=qa("SELECT id,name,email,role,is_active FROM users WHERE company_id=?",(cid,))
    return jsonify([dict(u) for u in users])

@app.route('/api/users/add',methods=['POST'])
@auth
def api_user_add():
    if session.get('role')!='admin': return jsonify({'error':'forbidden'}),403
    cid=session['cid']; d=request.get_json() or {}
    name=(d.get('name') or '').strip(); email=(d.get('email') or '').strip().lower()
    pw=d.get('password') or '123456'; role=d.get('role','accountant')
    if not name or not email: return jsonify({'success':False,'error':'الاسم والبريد مطلوبان'})
    conn=db()
    try:
        conn.execute("INSERT INTO users(company_id,name,email,password_hash,role)VALUES(?,?,?,?,?)",(cid,name,email,hp(pw),role))
        conn.commit()
        return jsonify({'success':True})
    except Exception as e: return jsonify({'success':False,'error':str(e)})
    finally: conn.close()

@app.route('/api/users/<int:uid>/toggle',methods=['POST'])
@auth
def api_user_toggle(uid):
    if session.get('role')!='admin': return jsonify({'error':'forbidden'}),403
    cid=session['cid']; conn=db()
    u=conn.execute("SELECT * FROM users WHERE id=? AND company_id=?",(uid,cid)).fetchone()
    if not u: conn.close(); return jsonify({'error':'not found'}),404
    new_status=0 if u['is_active'] else 1
    conn.execute("UPDATE users SET is_active=? WHERE id=?",(new_status,uid))
    conn.commit(); conn.close()
    return jsonify({'success':True,'is_active':new_status})

with app.app_context():
    init()

if __name__=='__main__':
    port=int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0',port=port,debug=False)
