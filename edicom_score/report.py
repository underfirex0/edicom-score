"""PDF renderer: 3-page A4 report (1 page when not rated) with health score + activity status."""
from __future__ import annotations
import io, datetime, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Wedge, Rectangle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from . import pipeline as F, narrative as N, activity as A
from .config import FONT_DIR
from .narrative import pct

FD = str(FONT_DIR) + "/"
pdfmetrics.registerFont(TTFont('Body',FD+'LiberationSans-Regular.ttf')); pdfmetrics.registerFont(TTFont('Body-B',FD+'LiberationSans-Bold.ttf'))
pdfmetrics.registerFont(TTFont('Body-I',FD+'LiberationSans-Italic.ttf'))
pdfmetrics.registerFont(TTFont('Head',FD+'Poppins-Medium.ttf')); pdfmetrics.registerFont(TTFont('Head-B',FD+'Poppins-Bold.ttf')); pdfmetrics.registerFont(TTFont('Head-L',FD+'Poppins-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Sym',FD+'DejaVuSans.ttf'))
registerFontFamily('Body',normal='Body',bold='Body-B',italic='Body-I',boldItalic='Body-B')
for _f in ('LiberationSans-Regular.ttf','LiberationSans-Bold.ttf','Poppins-Bold.ttf','Poppins-Medium.ttf'): fm.fontManager.addfont(FD+_f)
plt.rcParams['font.family']='Liberation Sans'

NAVY=colors.HexColor('#0B2545'); TEAL=colors.HexColor('#13A89E'); INK=colors.HexColor('#1F2937'); MUTED=colors.HexColor('#6B7280'); LINE=colors.HexColor('#E5E7EB'); SOFT=colors.HexColor('#F3F6FA')
CLS_COL={'A':'#1E9E5A','B':'#7CB518','C':'#F2A900','D':'#E8590C','E':'#C92A2A','NR':'#9CA3AF'}
def hx(c): return colors.HexColor(CLS_COL[c])
W,H=A4; LM=RM=15*mm

def st(name,**kw):
    base=dict(fontName='Body',fontSize=8.6,leading=11.4,textColor=INK); base.update(kw); return ParagraphStyle(name,**base)
S_BODY=st('b'); S_SMALL=st('s',fontSize=7.2,leading=9.4,textColor=MUTED); S_H2=st('h2',fontName='Head',fontSize=10.5,leading=13,textColor=NAVY,spaceBefore=7,spaceAfter=3)
S_NAME=st('n',fontName='Head-B',fontSize=17,leading=20,textColor=NAVY); S_META=st('m',fontSize=8.4,leading=11.5,textColor=MUTED)
S_BUL=st('bul',fontSize=8.5,leading=11.2,leftIndent=9,bulletIndent=0); S_CELL=st('c',fontSize=8,leading=10); S_CELLR=st('cr',fontSize=8,leading=10,alignment=TA_RIGHT); S_CELLB=st('cb',fontName='Body-B',fontSize=8,leading=10)
S_TH=st('th',fontName='Body-B',fontSize=7.6,leading=9.5,textColor=colors.white); S_THR=st('thr',fontName='Body-B',fontSize=7.6,leading=9.5,textColor=colors.white,alignment=TA_RIGHT)

# ------------------------------------------------------------------ charts
def fig_bytes(fig,dpi=260):
    b=io.BytesIO(); fig.savefig(b,format='png',dpi=dpi,bbox_inches='tight',transparent=True); plt.close(fig); b.seek(0); return b
def gauge(score,cls):
    fig,ax=plt.subplots(figsize=(3.3,2.25)); ax.set_xlim(-1.25,1.25); ax.set_ylim(-0.55,1.2); ax.axis('off'); ax.set_aspect('equal')
    segs=[(0,30,'E'),(30,45,'D'),(45,60,'C'),(60,75,'B'),(75,100,'A')]
    for a,b,c in segs:
        th1=180-b*1.8; th2=180-a*1.8
        ax.add_patch(Wedge((0,0),1.0,th1,th2,width=0.26,facecolor=CLS_COL[c],edgecolor='white',linewidth=2.0,alpha=1 if (score is not None and a<=score<b+(0.001 if b==100 else 0)) else .55))
        mid=np.deg2rad(180-(a+b)/2*1.8); ax.text(1.14*np.cos(mid),1.14*np.sin(mid),c,ha='center',va='center',fontsize=7.5,color='#4B5563',fontweight='bold')
    if score is not None:
        ang=np.deg2rad(180-score*1.8); ax.plot([0,0.66*np.cos(ang)],[0,0.66*np.sin(ang)],color='#0B2545',lw=2.6,solid_capstyle='round'); ax.add_patch(plt.Circle((0,0),0.05,color='#0B2545'))
        ax.text(0,-0.36,f"{score:.0f}",ha='center',va='center',fontsize=30,fontweight='bold',color='#0B2545',family='Poppins')
    else:
        ax.text(0,-0.05,'NR',ha='center',va='center',fontsize=30,fontweight='bold',color='#9CA3AF',family='Poppins')
    return fig_bytes(fig)
def pillar_chart(r):
    names=[('P1','Solvabilité & capitalisation',.30),('P2','Liquidité & équilibre financier',.10),('P3','Rentabilité & capacité bénéficiaire',.28),('P4',f"Dynamique {int(r['pfy'])} → {int(r['fy'])}",.10),('P5','Profil & substance (Edicom)',.22)]
    fig,ax=plt.subplots(figsize=(6.9,2.35)); ys=np.arange(len(names))[::-1]
    for y,(p,n,w) in zip(ys,names):
        v=r[p]; ax.barh(y,100,color='#EEF2F7',height=.56,zorder=1)
        if pd.notna(v):
            c='#1E9E5A' if v>=75 else '#7CB518' if v>=60 else '#F2A900' if v>=45 else '#E8590C' if v>=30 else '#C92A2A'
            ax.barh(y,v,color=c,height=.56,zorder=2); ax.text(min(v+1.5,92),y,f"{v:.0f}",va='center',ha='left',fontsize=9,fontweight='bold',color='#1F2937',zorder=3)
        else: ax.text(2,y,'non disponible',va='center',fontsize=8,color='#9CA3AF',style='italic')
        ax.text(-2,y,n,ha='right',va='center',fontsize=8.6,color='#1F2937'); ax.text(103,y,f"{int(w*100)} %",ha='left',va='center',fontsize=8,color='#6B7280')
    ax.axvline(50,color='#9CA3AF',lw=.8,ls=(0,(3,3)),zorder=0); ax.set_xlim(0,100); ax.set_ylim(-.6,len(names)-.4); ax.axis('off')
    ax.text(103,len(names)-.35,'poids',fontsize=7,color='#6B7280',ha='left'); 
    return fig_bytes(fig)
def structure_chart(r):
    TA=r['TA_cur']
    emplois=[('Immobilisations nettes',r['AI_cur']),('Stocks',r['STOCKS_cur']),('Créances',r['AC_cur']-r['STOCKS_cur']),('Trésorerie',r['TRESO_A_cur'])]
    resources=[('Capitaux propres',r['CP_cur']+r['CPA_cur']),('Dettes de financement',r['DFIN_LT_cur']),("Comptes d'associés",r['F6_assoc_cur']),('Dettes fournisseurs',r['F1_fourn_cur']),('Crédits de trésorerie',r['TRESO_P_cur'])]
    other=TA-sum(v for _,v in resources if pd.notna(v)); resources.append(('Autres dettes',other))
    fig,axs=plt.subplots(1,2,figsize=(6.9,2.1))
    for ax,items,title,col in [(axs[0],emplois,'Emplois (actif) — % du total bilan','#13A89E'),(axs[1],resources,'Ressources (passif) — % du total bilan','#0B2545')]:
        vals=[(n,(v/TA if pd.notna(v) and TA else 0)) for n,v in items]; ys=np.arange(len(vals))[::-1]
        for y,(n,v) in zip(ys,vals):
            cc='#C92A2A' if v<0 else col; ax.barh(y,v*100,color=cc,height=.58); ax.text(v*100+(2 if v>=0 else -2),y,f"{v*100:.0f} %",va='center',ha='left' if v>=0 else 'right',fontsize=7.6,color='#1F2937')
        ax.set_yticks(ys); ax.set_yticklabels([n for n,_ in vals],fontsize=7.6); ax.set_title(title,fontsize=8.2,color='#0B2545',loc='left',fontweight='bold')
        lo=min([v for _,v in vals]+[0])*100; hi=max([v for _,v in vals]+[0])*100; ax.set_xlim(min(lo-18,-5),max(hi+22,60)); ax.axvline(0,color='#9CA3AF',lw=.8)
        for s in ('top','right','bottom'): ax.spines[s].set_visible(False)
        ax.tick_params(axis='x',length=0,labelbottom=False); ax.tick_params(axis='y',length=0)
    fig.tight_layout(w_pad=2.0); return fig_bytes(fig)
def history_chart(r):
    s18,s19=r['score_prev'],r['score_cur_static']
    fig,ax=plt.subplots(figsize=(2.9,1.7))
    for a,b,c in [(0,30,'E'),(30,45,'D'),(45,60,'C'),(60,75,'B'),(75,100,'A')]: ax.axhspan(a,b,color=CLS_COL[c],alpha=.13,lw=0)
    xs=[0,1]; ys=[s18,s19]
    if pd.notna(s18) and pd.notna(s19):
        ax.plot(xs,ys,color='#0B2545',lw=2.2,marker='o',ms=7)
        for x,y in zip(xs,ys): ax.text(x,y+5.5,f"{y:.0f}",ha='center',fontsize=9,fontweight='bold',color='#0B2545')
    elif pd.notna(s19): ax.plot([1],[s19],marker='o',ms=7,color='#0B2545'); ax.text(1,s19+5.5,f"{s19:.0f}",ha='center',fontsize=9,fontweight='bold',color='#0B2545')
    ax.set_xlim(-.4,1.4); ax.set_ylim(0,100); ax.set_xticks(xs); ax.set_xticklabels([f"Exercice {int(r['pfy'])}",f"Exercice {int(r['fy'])}"],fontsize=8); ax.set_xlabel('Score comparable (hors pilier dynamique)',fontsize=6.8,color='#6B7280'); ax.set_yticks([0,30,45,60,75,100]); ax.tick_params(axis='y',labelsize=7,length=0); ax.tick_params(axis='x',length=0)
    for s in ('top','right','left','bottom'): ax.spines[s].set_visible(False)
    return fig_bytes(fig)

# ------------------------------------------------------------------ page chrome
def chrome(canv,doc,r,datestr,meta):
    canv.saveState()
    canv.setFillColor(NAVY); canv.rect(0,H-17*mm,W,17*mm,stroke=0,fill=1)
    canv.setFillColor(TEAL); canv.rect(0,H-17*mm,W,1.1*mm,stroke=0,fill=1)
    canv.setFillColor(colors.white); canv.setFont('Head-B',14); canv.drawString(LM,H-11.2*mm,'EDICOM')
    canv.setFont('Head-L',8.5); canv.drawString(LM+27*mm,H-11.0*mm,'Score Entreprise · Santé financière & statut d\'activité')
    canv.setFont('Body',7.6); canv.drawRightString(W-RM,H-8.0*mm,f"Édité le {datestr}"); canv.drawRightString(W-RM,H-12.3*mm,f"Réf. {r.name} · Exercice analysé {int(r['fy'])}")
    canv.setStrokeColor(LINE); canv.line(LM,13*mm,W-RM,13*mm)
    canv.setFillColor(MUTED); canv.setFont('Body',6.6)
    canv.drawString(LM,9.2*mm,f"Sources : états de synthèse OMPIC (exercices {int(r['pfy'])} et {int(r['fy'])}) · base Edicom (CA, effectif, coordonnées). Modèles Edicom v0.2.")
    canv.drawString(LM,6.2*mm,f"Information fournie à titre indicatif ; elle ne constitue ni un conseil en crédit ni une garantie. Les comptes arrêtés au 31/12/{int(r['fy'])} peuvent ne plus refléter la situation actuelle.")
    canv.drawRightString(W-RM,9.2*mm,f"Page {doc.page}")
    canv.restoreState()

def kv_table(rows,colw,style_extra=None):
    t=Table(rows,colWidths=colw); base=[('FONTNAME',(0,0),(-1,-1),'Body'),('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),1.6),('BOTTOMPADDING',(0,0),(-1,-1),1.6),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),4)]
    t.setStyle(TableStyle(base+(style_extra or []))); return t

def pastille(score):
    if pd.isna(score): return '–'
    return '●'
def score_color(v):
    if pd.isna(v): return MUTED
    return hx('A') if v>=75 else hx('B') if v>=60 else hx('C') if v>=45 else hx('D') if v>=30 else hx('E')

ACT_COL={'ACTIVE':'#1E9E5A','PROBABLE':'#13A89E','VERIFY':'#F2A900','INACTIVE':'#C92A2A'}
def ev_list(a,r):
    ca=pd.to_numeric(r['E_CA'],errors='coerce'); return [(sg,t.replace('{CA}',N.dh(ca))) for sg,t in a['evidence']]
def ev_par(sg,t,sty=None):
    sym,col={'+':('✓','#1E9E5A'),'-':('✗','#C92A2A'),'=':('•','#9CA3AF')}[sg]
    return Paragraph(f'<font name="Sym" color="{col}">{sym}</font>&nbsp; {t}',sty or st('ev',fontSize=7.9,leading=10.3,leftIndent=9,firstLineIndent=-9))
def proof_line(a):
    if a['last_proof_year']: 
        n=a['age_years']; return f"Dernière preuve d'activité : <b>{a['last_proof_year']}</b>"+(f" (il y a {n} an{'s' if n>1 else ''})" if n is not None and n>0 else '')
    return "Dernière preuve d'activité : <b>aucune</b>"
def act_banner(a,r):
    col=ACT_COL[a['code']]; ev=ev_list(a,r)[:6]
    lw=46*mm; rw=W-LM-RM-lw
    left=[Paragraph('<font name="Body-B" size="6.6" color="#FFFFFF">STATUT D\'ACTIVITÉ</font>',st('l1',leading=8)),Spacer(1,2),Paragraph(f'<font name="Head-B" size="12.2" color="#FFFFFF">{a["label"]}</font>',st('l2',leading=14.5)),Spacer(1,2.5),Paragraph(f'<font size="7.2" color="#FFFFFF">Fiabilité de l\'indication : <b>{a["confidence"]}</b></font>',st('l3',leading=9))]
    half=(len(ev)+1)//2; c1=[ev_par(*e) for e in ev[:half]]; c2=[ev_par(*e) for e in ev[half:]]
    inner=Table([[c1,c2]],colWidths=[rw/2-6*mm,rw/2-6*mm]); inner.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    right=[Paragraph(f"<b>{a['line']}</b>",st('r1',fontSize=8.3,leading=10.8)),Spacer(1,1.5),Paragraph(proof_line(a),st('r2',fontSize=7.9,leading=10,textColor=MUTED)),Spacer(1,3),inner]
    t=Table([[left,right]],colWidths=[lw,rw]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),colors.HexColor(col)),('BACKGROUND',(1,0),(1,0),SOFT),('VALIGN',(0,0),(0,0),'MIDDLE'),('VALIGN',(1,0),(1,0),'TOP'),('LEFTPADDING',(0,0),(0,0),9),('RIGHTPADDING',(0,0),(0,0),6),('LEFTPADDING',(1,0),(1,0),9),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    return t
def dorm_chart(a):
    p=a['p_dormant']*100
    fig,ax=plt.subplots(figsize=(6.9,0.95)); ax.set_xlim(0,100); ax.set_ylim(-1.6,1.6); ax.axis('off')
    for lo,hi,c,t in [(0,30,'#1E9E5A','Bilan opérationnel'),(30,60,'#F2A900','Bilan ambigu'),(60,100,'#C92A2A','Bilan de type dormant')]:
        ax.add_patch(Rectangle((lo,-.35),hi-lo,.7,facecolor=c,edgecolor='white',lw=2,alpha=.85)); ax.text((lo+hi)/2,-1.05,t,ha='center',va='center',fontsize=7.6,color='#374151')
    ax.plot([p],[0.55],marker='v',ms=10,color='#0B2545'); ax.text(min(max(p,6),94),1.25,f"{p:.0f} %",ha='center',va='center',fontsize=9.5,fontweight='bold',color='#0B2545')
    return fig_bytes(fig)
def reco_text(cls,a,r):
    base=F.RECO[cls]
    if a['code']=='INACTIVE': return "Ne pas engager d'exposition sans avoir vérifié l'existence et l'activité de la société (Registre du commerce, ICE, attestation de régularité fiscale)."
    if a['code']=='VERIFY': return base+" Vérifier au préalable que la société est bien en activité (RC, ICE)."
    if a['code']=='PROBABLE': return base+f" Statut d'activité à reconfirmer (dernière preuve : {a['last_proof_year'] or int(r['fy'])})."
    return base
def page3(r,a,name,meta):
    el=[Paragraph('Statut d\'activité : preuves et lecture',S_H2)]
    src={'+':'Favorable','-':'Défavorable','=':'Neutre'}
    rows=[[Paragraph('Indice',S_TH),Paragraph('Constat',S_TH),Paragraph('Lecture',S_TH)]]
    for sg,t in ev_list(a,r): rows.append([Paragraph(('Chiffre d\'affaires' if t.lower().startswith(("chiffre","dernier chiffre","aucun chiffre")) else f"Bilan OMPIC {int(r['fy'])}" if any(k in t for k in ('Bilan','Résultat net','Total bilan')) else 'Effectif' if t.startswith('Effectif') else 'Coordonnées' if ('oordonn' in t) else 'Autre'),S_CELL),Paragraph(t,S_CELL),Paragraph(f'<font color="{ {"+":"#1E9E5A","-":"#C92A2A","=":"#6B7280"}[sg]}"><b>{src[sg]}</b></font>',S_CELL)])
    t=Table(rows,colWidths=[32*mm,120*mm,28*mm],repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('LINEBELOW',(0,1),(-1,-1),.3,LINE),('TOPPADDING',(0,0),(-1,-1),2.6),('BOTTOMPADDING',(0,0),(-1,-1),2.6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,SOFT]),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    el+=[t,Spacer(1,6),Paragraph(f"Ressemblance du bilan {int(r['fy'])} à celui d'une société dormante",S_H2),Image(dorm_chart(a),width=W-LM-RM,height=(W-LM-RM)*0.14),
         Paragraph(f"Parmi les entreprises du panel dont le bilan présentait un profil comparable, <b>{a['cal_rate']*100:.0f} %</b> n'avaient aucun chiffre d'affaires enregistré. L'indice combine la présence d'un cycle d'exploitation (clients, fournisseurs, stocks, CNSS, fiscal, immobilisations), un résultat nul, un bilan figé ou minuscule et des pertes répétées (modèle validé : AUC 0,90).",S_BODY),Spacer(1,6)]
    defs=[['Entreprise active',f"Un chiffre d'affaires récent (moins de {meta['recent_window']} ans) a été déclaré (donnée Edicom)."],
          ['Probablement active',f"CA et bilan opérationnels en {int(r['fy'])}, sans donnée plus récente. Dans le panel, {meta['reconfirm_rate']*100:.0f} % des entreprises avec un CA positif ont un CA récent déclaré ; les autres sont soit arrêtées, soit non mises à jour : la reconfirmation est recommandée."],
          ['Activité non confirmée',"Signaux contradictoires (ex. CA enregistré mais bilan type dormant) ou insuffisants ; bilan substantiel (1 M DH ou plus) sans CA, typique d'un projet en développement ; société patrimoniale ou immobilière sans CA."],
          ['Probablement inactive',"Aucun chiffre d'affaires, bilan de type dormant (ressemblance de 60 % ou plus) et total bilan inférieur à 1 M DH : peu d'éléments d'une exploitation réelle."]]
    rows=[[Paragraph('Statut',S_TH),Paragraph('Définition retenue',S_TH)]]+[[Paragraph(f'<b>{x}</b>',S_CELL),Paragraph(y,S_CELL)] for x,y in defs]
    t2=Table(rows,colWidths=[38*mm,142*mm],repeatRows=1); t2.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('LINEBELOW',(0,1),(-1,-1),.3,LINE),('TOPPADDING',(0,0),(-1,-1),2.6),('BOTTOMPADDING',(0,0),(-1,-1),2.6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,SOFT])]))
    el+=[Paragraph('Définition des statuts',S_H2),t2,Spacer(1,6),Paragraph('Vérifications officielles recommandées',S_H2)]
    ver=[[Paragraph('Source',S_TH),Paragraph('Ce qu\'elle permet de vérifier',S_TH)],
         [Paragraph('<b>ice.gov.ma</b> (DGI — « Recherche entreprise »)',S_CELL),Paragraph("Validité de l'ICE à partir du nom ou du numéro de RC. Une entreprise inscrite au registre des inactifs de la DGI (aucune déclaration ni opération pendant trois exercices consécutifs) perd son ICE.",S_CELL)],
         [Paragraph('<b>Registre central du commerce</b> (OMPIC)',S_CELL),Paragraph("Statut au registre : en activité, en dissolution ou radiée. La radiation intervient après la dissolution puis la liquidation.",S_CELL)],
         [Paragraph('<b>Attestations</b> DGI (régularité fiscale) et CNSS',S_CELL),Paragraph("Preuves de déclaration et de paiement récentes, à demander directement à l'entreprise avant tout engagement significatif.",S_CELL)]]
    t3=Table(ver,colWidths=[52*mm,128*mm],repeatRows=1); t3.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('LINEBELOW',(0,1),(-1,-1),.3,LINE),('TOPPADDING',(0,0),(-1,-1),2.6),('BOTTOMPADDING',(0,0),(-1,-1),2.6),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,SOFT])]))
    el+=[t3,Spacer(1,3),Paragraph("Une immatriculation au registre du commerce ne prouve pas l'activité : selon un rapport de la Banque mondiale et de l'Observatoire marocain de la TPME, 7,3 % des entreprises marocaines sont restées inactives au moins deux ans sans être dissoutes. Le statut ci-dessus est donc une inférence à partir des données disponibles ; il ne remplace pas ces vérifications.",S_SMALL),Spacer(1,6)]
    hist=Table([[Image(history_chart(r),width=58*mm,height=34*mm),Paragraph(f"<b>Comment lire le score.</b> Le score (0-100) agrège cinq piliers : solvabilité (30 %), rentabilité (28 %), profil Edicom (22 %), liquidité (10 %) et dynamique (10 %). Il est plafonné à 45 lorsque les capitaux propres passent sous le quart du capital social (alerte légale) et à 30 lorsqu'ils sont négatifs. Les repères proviennent des pratiques d'analyse financière CGNC, du modèle Altman Z'' (marchés émergents) et de la littérature sur le risque des PME ; les seuils ont été calibrés sur {meta['n_firms']} entreprises marocaines (test {meta['backtest']}). Le statut d'activité est évalué séparément et n'entre pas dans le calcul du score.",S_BODY)]],colWidths=[62*mm,W-LM-RM-62*mm]); hist.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    el+=[Paragraph('Évolution du score & méthode',S_H2),hist]
    return el

def build_pdf(r,meta,target,today=None):
    """Render the report for one firm row (Series indexed like the scores frame, name = Code Firme) to `target` (path or file-like)."""
    code=r.name; med=meta['medians']; a=A.status(r,today); datestr=(pd.Timestamp(today) if today is not None else pd.Timestamp.today()).strftime('%d/%m/%Y'); cls=r['classe']; name=str(r['E_Raison Sociale']).strip() if pd.notna(r['E_Raison Sociale']) else code
    doc=BaseDocTemplate(target,pagesize=A4,leftMargin=LM,rightMargin=RM,topMargin=22*mm,bottomMargin=17*mm,title=f"Score Edicom – {name}",author='Edicom')
    fr=Frame(LM,17*mm,W-LM-RM,H-22*mm-17*mm,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='p',frames=[fr],onPage=lambda c,d:chrome(c,d,r,datestr,meta))])
    el=[]
    # --- identity
    forme=r['E_FORM.JUR'] if pd.notna(r['E_FORM.JUR']) else 'Forme n.d.'
    ville=r['E_VILLE RC'] if pd.notna(r['E_VILLE RC']) else ''
    crea=f"créée en {int(r['E_ANNEE CREATION'])}" if pd.notna(r['E_ANNEE CREATION']) and r['E_ANNEE CREATION']>1900 else ''
    el+= [Paragraph(name,S_NAME), Paragraph(' · '.join([x for x in [forme,ville and f"RC {ville}",crea,f"ICE {r['E_ICE']}" if pd.notna(r['E_ICE']) else ''] if x]),S_META),Spacer(1,3)]
    dirig=str(r['E_Dirigeant']).strip() if pd.notna(r['E_Dirigeant']) else ''; fonc=str(r['E_Fonction']).strip() if pd.notna(r['E_Fonction']) else ''
    eff=int(r['E_EFFECTIF']) if pd.notna(r['E_EFFECTIF']) and r['E_EFFECTIF']>0 else None
    ca=pd.to_numeric(r['E_CA'],errors='coerce'); caY=r['E_ANNEE CA']
    contact=' · '.join([str(x) for x in [r['E_TEL 1'],r['E_EMAIL'],r['E_WEB']] if pd.notna(x)]) or 'n.d.'
    cap=pd.to_numeric(r['E_CAPITAL'],errors='coerce')
    left=[[Paragraph('<b>Dirigeant</b>',S_CELL),Paragraph((dirig+(f" ({fonc})" if fonc else '')) or 'n.d.',S_CELL)],
          [Paragraph('<b>Effectif</b>',S_CELL),Paragraph(f"{eff} salariés" if eff else 'non communiqué',S_CELL)],
          [Paragraph('<b>Capital social</b>',S_CELL),Paragraph(N.dh(cap),S_CELL)]]
    right=[[Paragraph('<b>CA (Edicom)</b>',S_CELL),Paragraph((N.dh(ca)+f" ({int(caY)})") if pd.notna(ca) and ca>0 and pd.notna(caY) else 'non communiqué',S_CELL)],
           [Paragraph('<b>Contact</b>',S_CELL),Paragraph(contact,S_CELL)],
           [Paragraph('<b>Fiabilité des données</b>',S_CELL),Paragraph((f"{r['fiabilite']} ({int(r['fiabilite_pts'])}/100)") if cls!='NR' else 'Sans objet (non noté)',S_CELL)]]
    idt=Table([[kv_table(left,[24*mm,62*mm]),kv_table(right,[27*mm,63*mm])]],colWidths=[(W-LM-RM)/2]*2); idt.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('BOX',(0,0),(-1,-1),0,colors.white),('BACKGROUND',(0,0),(-1,-1),SOFT),('LEFTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
    el+=[idt,Spacer(1,6),act_banner(a,r),Spacer(1,7)]
    lab,rk=F.CLASS_LABEL[cls]
    if cls=='NR':
        why=[]
        if pd.isna(r['TA_cur']) or r['TA_cur']<10000: why.append(f"le total du bilan {int(r['fy'])} est de {N.dh(r['TA_cur'])}, inférieur au seuil de significativité (10 k DH) : activité apparente nulle ou marginale")
        if not r['actif_ok_cur']: why.append(f"l'actif du bilan {int(r['fy'])} est manquant")
        incons = (eff is not None and pd.notna(r['TA_cur']) and r['TA_cur']<10000)
        box=Table([[Image(gauge(None,'NR'),width=50*mm,height=31*mm),[Paragraph('<font name="Head-B" size="13" color="#6B7280">Entreprise non notée</font>',S_BODY),Spacer(1,3),Paragraph("Aucun score n'est calculé : "+' ; '.join(why)+".",S_BODY),Spacer(1,4),Paragraph("<b>Recommandation indicative :</b> "+reco_text('NR',a,r),S_BODY)]+([Spacer(1,4),Paragraph(f"<b>Incohérence à vérifier :</b> la base Edicom indique {eff} salarié(s) alors que le bilan 2019 est quasi nul — l'entreprise a pu cesser, réduire ou transférer son activité, ou les comptes déposés sont incomplets.",S_BODY)] if incons else [])]],colWidths=[58*mm,W-LM-RM-58*mm]); box.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')])); el+=[box,Spacer(1,6)]
        el+=[Paragraph(f"Données disponibles (OMPIC {int(r['fy'])})",S_H2)]
        rows=[[Paragraph('Total bilan',S_CELL),Paragraph(N.dh(r['TA_cur']),S_CELLR)],[Paragraph('Capitaux propres',S_CELL),Paragraph(N.dh(r['CP_cur']),S_CELLR)],[Paragraph('Capital social',S_CELL),Paragraph(N.dh(r['capital_cur']),S_CELLR)],[Paragraph('Résultat net',S_CELL),Paragraph(N.dh(r['RN_cur']),S_CELLR)]]
        t=Table(rows,colWidths=[60*mm,40*mm]); t.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),.3,LINE)])); el+=[t,Spacer(1,6),Paragraph("Les ratios ne sont pas interprétables lorsque le bilan est de taille négligeable ; une demande des derniers états de synthèse est recommandée avant toute exposition.",S_SMALL)]
        doc.build(el); return
    # --- score block
    facts=[[Paragraph('<b>Classe</b>',S_CELL),Paragraph(f'<font color="{CLS_COL[cls]}"><b>{cls} — {lab}</b></font>',S_CELL)],
           [Paragraph('<b>Niveau de risque</b>',S_CELL),Paragraph(rk,S_CELL)],
           [Paragraph('<b>Position</b>',S_CELL),Paragraph(f"Mieux noté que <b>{r['percentile']:.0f} %</b> des {meta['n_scorable']:,} entreprises du panel".replace(',',' '),S_CELL)],
           [Paragraph('<b>Perspective</b>',S_CELL),Paragraph(r['perspective']+(f" (score comparable : {r['score_prev']:.0f} en {int(r['pfy'])} → {r['score_cur_static']:.0f} en {int(r['fy'])})" if pd.notna(r['score_prev']) else ''),S_CELL)],
           [Paragraph('<b>Historique de la classe</b>',S_CELL),Paragraph(f"Dans le test rétrospectif {meta['backtest']}, <b>{meta['observed_adverse_rate'][cls]*100:.0f} %</b> des entreprises de classe {cls} étaient en situation défavorable un an plus tard*",S_CELL)]]
    if a['code']=='INACTIVE': facts.append([Paragraph('<b>Attention</b>',S_CELL),Paragraph('<font color="#C92A2A"><b>Société probablement inactive</b></font> : ce score décrit les comptes '+str(int(r['fy']))+' et n\'a qu\'une valeur indicative.',S_CELL)])
    ft=Table(facts,colWidths=[30*mm,W-LM-RM-58*mm-30*mm]); ft.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),2.2),('BOTTOMPADDING',(0,0),(-1,-1),2.2),('LINEBELOW',(0,0),(-1,-2),.3,LINE),('LEFTPADDING',(0,0),(-1,-1),2)]))
    sb=Table([[Image(gauge(r['score'],cls),width=54*mm,height=34*mm),ft]],colWidths=[58*mm,W-LM-RM-58*mm]); sb.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    el+=[sb,Spacer(1,5),Paragraph('Décomposition du score par pilier',S_H2),Image(pillar_chart(r),width=W-LM-RM,height=(W-LM-RM)*0.34),Spacer(1,2)]
    good,bad=N.drivers(r)
    def bl(items,sym,col): return [Paragraph(f'<font name="Sym" color="{col}">{sym}</font>&nbsp; {t}',S_BUL) for t in items] or [Paragraph('<i>Aucun élément saillant.</i>',S_BODY)]
    pt=Table([[Paragraph('<font name="Head" size="9.5" color="#1E9E5A">Points forts</font>',S_BODY),Paragraph('<font name="Head" size="9.5" color="#C92A2A">Points de vigilance</font>',S_BODY)],[bl(good,'✓','#1E9E5A'),bl(bad,'!','#C92A2A')]],colWidths=[(W-LM-RM)/2-3*mm,(W-LM-RM)/2+3*mm])
    pt.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),2),('LINEBELOW',(0,0),(-1,0),.6,LINE)]))
    el+=[pt,Spacer(1,6)]
    rb=Table([[Paragraph('<b>Recommandation indicative</b>',st('rb',textColor=colors.white,fontName='Body-B',fontSize=8.6)),Paragraph(reco_text(cls,a,r),st('rb2',textColor=colors.white,fontSize=8.6))]],colWidths=[40*mm,W-LM-RM-40*mm]); rb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),hx(cls)),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    el+=[rb,Spacer(1,3),Paragraph("* Taux de situations défavorables = capitaux propres inférieurs au quart du capital social, ou effondrement/arrêt apparent de l'activité (actif divisé par 2 ou &lt; 10 k DH) à l'exercice suivant. Calculé sur le panel de 3 787 entreprises ; indicatif, non transposable à toute population.",S_SMALL)]
    el.append(PageBreak())
    # --- page 2 : financial detail
    ta19=r['TA_cur']
    def var(a,b):
        if pd.isna(a) or pd.isna(b) or b==0: return '–'
        v=(a-b)/abs(b); return f"{v*100:+.0f} %".replace('-','−') if abs(v)<10 else '>+1000 %'
    items=[('Total bilan','TA'),('Capitaux propres','CP'),('Capital social','capital'),('Résultat net','RN'),('Fonds de roulement','FR'),('Besoin en fonds de roulement','BFR'),('Trésorerie nette','TN'),("Comptes d'associés (créditeurs)",'F6_assoc')]
    hdr=[Paragraph('Synthèse financière (DH)',S_TH),Paragraph(str(int(r['pfy'])),S_THR),Paragraph(str(int(r['fy'])),S_THR),Paragraph('Variation',S_THR)]
    rows=[hdr]+[[Paragraph(n,S_CELL),Paragraph(N.dh(r[k+'_prev']),S_CELLR),Paragraph(N.dh(r[k+'_cur']),S_CELLR),Paragraph(var(r[k+'_cur'],r[k+'_prev']) if k not in('capital',) else '–',S_CELLR)] for n,k in items]
    t=Table(rows,colWidths=[62*mm,38*mm,38*mm,42*mm-0*mm],repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('LINEBELOW',(0,1),(-1,-1),.3,LINE),('TOPPADDING',(0,0),(-1,-1),2.6),('BOTTOMPADDING',(0,0),(-1,-1),2.6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,SOFT])]))
    el+=[Paragraph('Lecture du bilan',S_H2),t,Spacer(1,4)]
    # key ratios
    def fmtv(k,v):
        if pd.isna(v): return 'n.d.'
        return {'headroom':pct(v),'autonomy':pct(v),'assoc':pct(v),'fr_ta':pct(v,sign=True),'current':N.n_fr(v,2),'roa':pct(v,1,True),'re_ta':pct(v,sign=True),'tn_ta':pct(v,sign=True)}[k]
    spec=[('headroom','Capitaux propres / capital social','≥ 100 % ; < 25 % : alerte légale'),('autonomy','Autonomie financière (CP / total bilan)','≥ 30 % solide ; < 20 % fragile'),('assoc',"Comptes d'associés / total bilan",'< 30 %'),
          ('fr_ta','Fonds de roulement / total bilan','> 0 ; ≥ 20 % confortable'),('current','Liquidité générale','≥ 1,2'),('roa','Rentabilité de l\'actif (RN / total bilan)','> 2 % ; ≥ 5 % bon'),('re_ta','Bénéfices cumulés / total bilan','> 5 %'),('tn_ta','Trésorerie nette / total bilan (info)','> 0')]
    hdr=[Paragraph('Indicateur',S_TH),Paragraph('Valeur',S_THR),Paragraph('Repère',S_TH),Paragraph('Médiane panel',S_THR),Paragraph('Sous-score',S_THR)]
    rows=[hdr]
    for k,n,ref in spec:
        sv=r.get('s_'+k) if k!='tn_ta' else np.nan
        sp=Paragraph(f'<font color="{score_color(sv).hexval().replace("0x","#")}"><b>● {sv:.0f}</b></font>',S_CELLR) if pd.notna(sv) else Paragraph('–',S_CELLR)
        rows.append([Paragraph(n,S_CELL),Paragraph(f"<b>{fmtv(k,r[k])}</b>",S_CELLR),Paragraph(ref,S_CELL),Paragraph(fmtv(k,med[k]),S_CELLR),sp])
    t2=Table(rows,colWidths=[58*mm,24*mm,52*mm,26*mm,20*mm],repeatRows=1); t2.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('LINEBELOW',(0,1),(-1,-1),.3,LINE),('TOPPADDING',(0,0),(-1,-1),2.6),('BOTTOMPADDING',(0,0),(-1,-1),2.6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,SOFT]),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    el+=[Paragraph('Indicateurs clés',S_H2),t2,Spacer(1,5),Paragraph(f"Structure financière au 31/12/{int(r['fy'])}",S_H2),Image(structure_chart(r),width=W-LM-RM,height=(W-LM-RM)*0.30),Spacer(1,3)]
    # activity block (only when CA year matches)
    act=[]
    if pd.notna(ca) and ca>0 and caY==int(r['fy']):
        dso=r['CLIENTS_cur']/ca*360; ros=r['RN_cur']/ca; turn=ca/ta19
        act=[[Paragraph("Délai clients (jours de CA)",S_CELL),Paragraph(f"<b>{dso:.0f} j</b>",S_CELLR),Paragraph("Délai légal par défaut : 60 j ; moyenne nationale observée par Bank Al-Maghrib : ~98 j (2024)",S_CELL)],
             [Paragraph("Marge nette (RN / CA)",S_CELL),Paragraph(f"<b>{pct(ros,1,True)}</b>",S_CELLR),Paragraph(f"Calculée avec le CA Edicom {int(caY)} (même exercice que le bilan)",S_CELL)],
             [Paragraph("Rotation de l'actif (CA / total bilan)",S_CELL),Paragraph(f"<b>{N.n_fr(turn,2)}×</b>",S_CELLR),Paragraph("Information ; non intégrée au score",S_CELL)]]
        ta_=Table(act,colWidths=[58*mm,24*mm,98*mm]); ta_.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),.3,LINE),('TOPPADDING',(0,0),(-1,-1),2.4),('BOTTOMPADDING',(0,0),(-1,-1),2.4)]))
        el+=[Paragraph(f"Indicateurs d'activité (CA Edicom {int(caY)})",S_H2),ta_,Spacer(1,3)]
    elif pd.notna(ca) and ca>0:
        el+=[Paragraph("Indicateurs d'activité",S_H2),Paragraph(f"Le CA Edicom disponible ({N.dh(ca)}) porte sur {int(caY)}, exercice différent du bilan analysé ({int(r['fy'])}) : les ratios d'activité (délai clients, marge) ne sont pas calculés afin de ne pas mélanger deux exercices.",S_BODY),Spacer(1,3)]
    el.append(PageBreak()); el+=page3(r,a,name,meta)
    doc.build(el)

def render_report(r,meta,today=None) -> bytes:
    buf=io.BytesIO(); build_pdf(r,meta,buf,today); return buf.getvalue()

def safe_name(name:str)->str:
    return ''.join(ch if ch.isalnum() else '_' for ch in str(name))[:40]
