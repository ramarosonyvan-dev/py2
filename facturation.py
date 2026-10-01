import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3, os, sys
from datetime import date, datetime
from pathlib import Path

APP_NAME = "Facturation Yvan"
DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "FacturationYvan"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "facturation.db"

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS invoices(
        id INTEGER PRIMARY KEY AUTOINCREMENT, number TEXT UNIQUE, inv_date TEXT,
        client TEXT, rc TEXT, nif TEXT, address TEXT, phone TEXT,
        payment TEXT, tva REAL DEFAULT 0, total_ht REAL, total_ttc REAL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS lines(
        id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER,
        article TEXT, description TEXT, qty REAL, price REAL, total REAL)""")
    con.commit()
    return con

def money(n):
    return f"{n:,.0f}".replace(",", " ") + " Ar"

class InvoiceApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1100x760")
        self.root.minsize(900, 620)
        self.lines = []
        self.setup_style()
        self.build()
        self.new_invoice()
        self.refresh_history()

    def setup_style(self):
        s = ttk.Style()
        try: s.theme_use("clam")
        except tk.TclError: pass
        s.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#173b65")
        s.configure("Head.TLabel", font=("Segoe UI", 11, "bold"))
        s.configure("Treeview", rowheight=27, font=("Segoe UI", 10))
        s.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def build(self):
        top = ttk.Frame(self.root, padding=14)
        top.pack(fill="x")
        ttk.Label(top, text="FACTURATION", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="Gestion locale des factures", foreground="#566579").pack(side="left", padx=16, pady=(8,0))
        tabs = ttk.Notebook(self.root)
        tabs.pack(fill="both", expand=True, padx=12, pady=(0,12))
        self.page = ttk.Frame(tabs, padding=12)
        self.history = ttk.Frame(tabs, padding=12)
        tabs.add(self.page, text="Nouvelle facture")
        tabs.add(self.history, text="Historique")
        self.build_invoice()
        self.build_history()

    def build_invoice(self):
        p = self.page
        client = ttk.LabelFrame(p, text="Informations du client", padding=10)
        client.pack(fill="x")
        self.vars = {}
        fields = [("Client","client"),("RC","rc"),("NIF","nif"),("Téléphone","phone"),("Adresse","address")]
        for i,(label,key) in enumerate(fields):
            r,c = divmod(i,3)
            cell = ttk.Frame(client); cell.grid(row=r,column=c,sticky="ew",padx=5,pady=4)
            ttk.Label(cell,text=label).pack(anchor="w")
            v=tk.StringVar(); self.vars[key]=v
            ttk.Entry(cell,textvariable=v,width=35).pack(fill="x")
        for c in range(3): client.columnconfigure(c,weight=1)
        meta=ttk.Frame(p); meta.pack(fill="x",pady=9)
        ttk.Label(meta,text="N° facture").pack(side="left")
        self.number=tk.StringVar(); ttk.Entry(meta,textvariable=self.number,width=18,state="readonly").pack(side="left",padx=6)
        ttk.Label(meta,text="Date").pack(side="left",padx=(18,0))
        self.invdate=tk.StringVar(value=date.today().isoformat())
        ttk.Entry(meta,textvariable=self.invdate,width=14).pack(side="left",padx=6)
        ttk.Label(meta,text="Paiement").pack(side="left",padx=(18,0))
        self.payment=tk.StringVar(value="Espèces")
        ttk.Combobox(meta,textvariable=self.payment,values=["Espèces","Mobile Money","Virement","Carte","À crédit"],state="readonly",width=17).pack(side="left",padx=6)

        items=ttk.LabelFrame(p,text="Articles",padding=9); items.pack(fill="both",expand=True)
        headers=("article","description","qty","price","total")
        self.tree=ttk.Treeview(items,columns=headers,show="headings",height=9)
        for col,label,w,anchor in [("article","Article",140,"w"),("description","Description",370,"w"),("qty","Qté",75,"e"),("price","Prix unitaire",130,"e"),("total","Total",140,"e")]:
            self.tree.heading(col,text=label); self.tree.column(col,width=w,anchor=anchor)
        self.tree.pack(fill="both",expand=True)
        add=ttk.Frame(items); add.pack(fill="x",pady=(8,0))
        self.item_vars={k:tk.StringVar() for k in ["article","description","qty","price"]}
        for key,label,width in [("article","Article",16),("description","Description",34),("qty","Qté",8),("price","Prix unitaire",14)]:
            ttk.Label(add,text=label).pack(side="left",padx=(0,3))
            ttk.Entry(add,textvariable=self.item_vars[key],width=width).pack(side="left",padx=(0,8))
        ttk.Button(add,text="Ajouter",command=self.add_line).pack(side="left")
        ttk.Button(add,text="Retirer la ligne",command=self.remove_line).pack(side="left",padx=6)

        bottom=ttk.Frame(p); bottom.pack(fill="x",pady=10)
        left=ttk.Frame(bottom); left.pack(side="left",fill="x",expand=True)
        ttk.Label(left,text="TVA (%)").pack(side="left")
        self.tva=tk.StringVar(value="0")
        ttk.Entry(left,textvariable=self.tva,width=7).pack(side="left",padx=5)
        ttk.Button(left,text="Nouvelle facture",command=self.new_invoice).pack(side="left",padx=5)
        ttk.Button(left,text="Enregistrer",command=self.save_invoice).pack(side="left",padx=5)
        ttk.Button(left,text="Enregistrer + PDF",command=self.save_pdf).pack(side="left",padx=5)
        totals=ttk.Frame(bottom); totals.pack(side="right")
        self.ht_label=ttk.Label(totals,text="Total HT : 0 Ar",style="Head.TLabel"); self.ht_label.pack(anchor="e")
        self.tax_label=ttk.Label(totals,text="TVA : 0 Ar"); self.tax_label.pack(anchor="e")
        self.ttc_label=ttk.Label(totals,text="Total TTC : 0 Ar",style="Head.TLabel"); self.ttc_label.pack(anchor="e")

    def next_number(self):
        con=db()
        n=con.execute("SELECT COUNT(*) n FROM invoices").fetchone()["n"]+1
        con.close()
        return "FAC-" + date.today().strftime("%Y%m") + f"-{n:04d}"

    def new_invoice(self):
        for v in getattr(self,"vars",{}).values(): v.set("")
        if hasattr(self,"number"): self.number.set(self.next_number())
        if hasattr(self,"invdate"): self.invdate.set(date.today().isoformat())
        if hasattr(self,"payment"): self.payment.set("Espèces")
        if hasattr(self,"tree"):
            self.tree.delete(*self.tree.get_children())
            self.lines=[]
            self.tva.set("0")
            self.update_totals()

    def add_line(self):
        try:
            article=self.item_vars["article"].get().strip()
            desc=self.item_vars["description"].get().strip()
            qty=float(self.item_vars["qty"].get().replace(",","."))
            price=float(self.item_vars["price"].get().replace(",","."))
            if not article and not desc: raise ValueError()
            if qty<=0 or price<0: raise ValueError()
        except (ValueError,KeyError):
            messagebox.showwarning("Vérification","Saisis un article, une quantité positive et un prix valide.")
            return
        total=qty*price
        self.lines.append((article,desc,qty,price,total))
        self.tree.insert("", "end", values=(article,desc,qty,money(price),money(total)))
        for v in self.item_vars.values(): v.set("")
        self.update_totals()

    def remove_line(self):
        selected=self.tree.selection()
        if not selected: return
        indexes=[self.tree.index(i) for i in selected]
        for i in sorted(indexes,reverse=True): self.lines.pop(i)
        for i in selected: self.tree.delete(i)
        self.update_totals()

    def totals(self):
        ht=sum(x[4] for x in self.lines)
        try: rate=float(self.tva.get().replace(",",".") or 0)
        except ValueError: rate=0
        tax=ht*rate/100
        return ht,tax,ht+tax,rate

    def update_totals(self):
        ht,tax,ttc,_=self.totals()
        self.ht_label.config(text="Total HT : "+money(ht))
        self.tax_label.config(text="TVA : "+money(tax))
        self.ttc_label.config(text="Total TTC : "+money(ttc))

    def save_invoice(self):
        if not self.vars["client"].get().strip():
            messagebox.showwarning("Client requis","Saisis le nom du client."); return False
        if not self.lines:
            messagebox.showwarning("Articles requis","Ajoute au moins un article."); return False
        try:
            datetime.strptime(self.invdate.get(),"%Y-%m-%d")
            ht,tax,ttc,rate=self.totals()
            con=db()
            cur=con.execute("""INSERT INTO invoices(number,inv_date,client,rc,nif,address,phone,payment,tva,total_ht,total_ttc)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(self.number.get(),self.invdate.get(),self.vars["client"].get(),self.vars["rc"].get(),self.vars["nif"].get(),self.vars["address"].get(),self.vars["phone"].get(),self.payment.get(),rate,ht,ttc))
            iid=cur.lastrowid
            con.executemany("INSERT INTO lines(invoice_id,article,description,qty,price,total) VALUES(?,?,?,?,?,?)",
                [(iid,a,d,q,pr,t) for a,d,q,pr,t in self.lines])
            con.commit(); con.close()
            messagebox.showinfo("Enregistrée",f"Facture {self.number.get()} enregistrée.")
            self.refresh_history()
            self.number.set(self.next_number())
            return True
        except sqlite3.IntegrityError:
            messagebox.showerror("Numéro déjà utilisé","Clique sur Nouvelle facture puis réessaie."); return False
        except Exception as e:
            messagebox.showerror("Erreur",str(e)); return False

    def save_pdf(self):
        # Save first, then create a printable PDF if reportlab is installed.
        if not self.save_invoice(): return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet
            path=filedialog.asksaveasfilename(defaultextension=".pdf",initialfile=self.number.get()+".pdf",filetypes=[("PDF","*.pdf")])
            if not path: return
            styles=getSampleStyleSheet(); doc=SimpleDocTemplate(path,pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36)
            ht,tax,ttc,rate=self.totals()
            story=[Paragraph("FACTURE",styles["Title"]),Paragraph("N° "+self.number.get(),styles["Heading2"]),
                Paragraph("Date : "+self.invdate.get(),styles["Normal"]),Spacer(1,10),
                Paragraph("<b>Client :</b> "+self.vars["client"].get(),styles["Normal"]),
                Paragraph("RC : "+self.vars["rc"].get()+" | NIF : "+self.vars["nif"].get(),styles["Normal"]),
                Paragraph("Téléphone : "+self.vars["phone"].get(),styles["Normal"]),
                Paragraph("Adresse : "+self.vars["address"].get(),styles["Normal"]),Spacer(1,16)]
            data=[["Article","Description","Qté","Prix unitaire","Total"]]
            data += [[a,d,str(q),money(pr),money(t)] for a,d,q,pr,t in self.lines]
            data += [["","","","Total HT",money(ht)],["","","",f"TVA ({rate:g}%)",money(tax)],["","","","Total TTC",money(ttc)]]
            table=Table(data,colWidths=[75,190,45,95,95],repeatRows=1)
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#173b65")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.grey),("ALIGN",(2,1),(-1,-1),"RIGHT"),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("PADDING",(0,0),(-1,-1),7)]))
            story += [table,Spacer(1,12),Paragraph("Mode de paiement : "+self.payment.get(),styles["Normal"])]
            doc.build(story)
            messagebox.showinfo("PDF créé","Le PDF a été créé :\n"+path)
        except ImportError:
            messagebox.showwarning("PDF indisponible","Le module PDF n'est pas installé. Relance build_windows.bat pour installer les dépendances.")
        except Exception as e: messagebox.showerror("Erreur PDF",str(e))

    def build_history(self):
        f=self.history
        bar=ttk.Frame(f); bar.pack(fill="x",pady=(0,8))
        ttk.Label(bar,text="Historique des factures",style="Head.TLabel").pack(side="left")
        ttk.Button(bar,text="Actualiser",command=self.refresh_history).pack(side="right")
        cols=("number","date","client","ht","ttc","payment")
        self.hist=ttk.Treeview(f,columns=cols,show="headings")
        for col,label,w in [("number","N° facture",170),("date","Date",120),("client","Client",260),("ht","Total HT",150),("ttc","Total TTC",150),("payment","Paiement",140)]:
            self.hist.heading(col,text=label); self.hist.column(col,width=w,anchor="w" if col in ("number","date","client","payment") else "e")
        self.hist.pack(fill="both",expand=True)
        ttk.Label(f,text="Les données sont enregistrées sur cet ordinateur. Pense à effectuer des sauvegardes régulières.",foreground="#5a6573").pack(anchor="w",pady=8)

    def refresh_history(self):
        if not hasattr(self,"hist"): return
        self.hist.delete(*self.hist.get_children())
        con=db()
        for r in con.execute("SELECT * FROM invoices ORDER BY id DESC"):
            self.hist.insert("","end",values=(r["number"],r["inv_date"],r["client"],money(r["total_ht"]),money(r["total_ttc"]),r["payment"]))
        con.close()

if __name__=="__main__":
    root=tk.Tk()
    InvoiceApp(root)
    root.mainloop()
