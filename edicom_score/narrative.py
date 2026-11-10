import numpy as np, pandas as pd
from . import scoring as S

def n_fr(x,dec=0):
    if x is None or (isinstance(x,float) and not np.isfinite(x)): return 'n.d.'
    s=f"{x:,.{dec}f}".replace(',',' ').replace('.',',')   # narrow-nbsp-free simple FR format
    return s.replace('-','−')
def dh(x):
    if x is None or pd.isna(x): return 'n.d.'
    a=abs(x); sg='−' if x<0 else ''
    if a>=1e9: return f"{sg}{n_fr(a/1e9,2)} Md DH"
    if a>=1e6: return f"{sg}{n_fr(a/1e6,2)} M DH"
    if a>=1e3: return f"{sg}{n_fr(a/1e3,0)} k DH"
    return f"{sg}{n_fr(a,0)} DH"
def pct(x,dec=0,sign=False):
    if x is None or pd.isna(x) or not np.isfinite(x): return 'n.d.'
    s=f"{x*100:+.{dec}f}" if sign else f"{x*100:.{dec}f}"
    return s.replace('.',',').replace('-','−')+' %'

def loi(forme):
    return "art. 357 loi 17-95" if str(forme)=='SA' else "art. 86 loi 5-96"

def texts(r):
    """Return dict key -> (good_text, bad_text) using actual numbers. r = row of final scores."""
    h=r['headroom']; a=r['autonomy']; asc=r['assoc']; fr=r['fr_ta']; cr=r['current']; roa=r['roa']; re=r['re_ta']
    f=r.get('E_FORM.JUR'); L=loi(f)
    T={}
    if pd.notna(h):
        if r['CP_cur']<0: T['headroom']=("", f"Capitaux propres négatifs ({dh(r['CP_cur'])}) : ils sont inférieurs au quart du capital social, seuil d'alerte légal ({L}).")
        elif h<0.25: T['headroom']=("", f"Capitaux propres ({dh(r['CP_cur'])}) inférieurs au quart du capital social ({dh(r['capital_cur'])}) : alerte légale ({L}).")
        elif h<1: T['headroom']=("", f"Capitaux propres à {pct(h)} du capital social : le capital est entamé par les pertes.")
        else: T['headroom']=(f"Capitaux propres équivalents à {n_fr(h,1)}× le capital social : marge de sécurité légale confortable.","")
    if pd.notna(a): T['autonomy']=(f"Autonomie financière de {pct(a)} (repère bancaire usuel : ≥ 20 % ; solide : ≥ 30 %).", f"Autonomie financière de {pct(a)} : l'entreprise est financée surtout par des tiers (repère bancaire usuel ≥ 20 %).")
    if pd.notna(asc): T['assoc']=(("Aucun compte d'associés créditeur : pas de dépendance au financement actionnaire." if asc<0.005 else f"Faible dépendance aux comptes d'associés ({pct(asc)} du total bilan)."), f"Comptes d'associés = {pct(asc)} du total bilan : le financement repose fortement sur les actionnaires.")
    if pd.notna(fr): T['fr_ta']=(f"Fonds de roulement positif ({pct(fr,sign=True)} de l'actif) : les ressources stables financent l'actif immobilisé.", f"Fonds de roulement de {pct(fr,sign=True)} de l'actif : les ressources stables ne couvrent pas l'actif immobilisé.")
    if pd.notna(cr): T['current']=(f"Liquidité générale de {n_fr(cr,2)} (repère : ≥ 1,2).", f"Liquidité générale de {n_fr(cr,2)} (< 1) : l'actif à court terme ne couvre pas les dettes à court terme.")
    if pd.notna(roa): T['roa']=(f"Rentabilité de l'actif de {pct(roa,1,True)} (résultat net / total actif).", f"Rentabilité de l'actif négative ({pct(roa,1,True)}) : l'exercice est déficitaire ({dh(r['RN_cur'])}).")
    if pd.notna(re): T['re_ta']=(f"Bénéfices cumulés positifs ({pct(re,sign=True)} de l'actif) : capacité d'autofinancement historique.", f"Bénéfices cumulés négatifs ({pct(re,sign=True)} de l'actif) : pertes accumulées qui ont rongé les fonds propres.")
    if pd.notna(r.get('age')): T['age']=(f"Entreprise établie : créée en {int(r['E_ANNEE CREATION'])} ({int(r['age'])} ans d'existence).", f"Entreprise jeune : créée en {int(r['E_ANNEE CREATION'])} ({int(r['age'])} an(s)) ; les jeunes entreprises sont statistiquement plus vulnérables.")
    T['size_ta']=(f"Taille de bilan supérieure à la majorité du panel ({dh(r['TA_cur'])}).", f"Petite taille de bilan ({dh(r['TA_cur'])}) : moindre capacité d'absorption des chocs.")
    cap=r.get('E_CAPITAL')
    if pd.notna(cap): T['capital']=(f"Capital social élevé au regard du panel ({dh(cap)}).", f"Capital social modeste ({dh(cap)}) : faible coussin de fonds propres.")
    if pd.notna(r.get('ca_band')): T['scale_edicom']=(f"Niveau d'activité élevé (tranche de CA Edicom {r['ca_band']}).", f"Niveau d'activité limité (tranche de CA Edicom {r['ca_band']}, CA < 500 k DH)." if r['ca_band']=='A' else f"Niveau d'activité limité (tranche de CA Edicom {r['ca_band']}).")
    if pd.notna(r.get('d_equity')): T['d_equity']=(f"Capitaux propres en hausse sur l'exercice ({pct(r['d_equity'],sign=True)} du capital).", f"Capitaux propres en baisse sur l'exercice ({pct(r['d_equity'],sign=True)} du capital).")
    if pd.notna(r.get('d_assets')): T['d_assets']=(f"Total bilan en croissance ({pct(r['d_assets'],sign=True)}).", f"Total bilan en forte contraction ({pct(r['d_assets'],sign=True)}).")
    if pd.notna(r.get('loss_streak')): T['loss_streak']=(f"Aucun exercice déficitaire sur {int(r['pfy'])}-{int(r['fy'])}.", f"Résultats déficitaires sur les deux derniers exercices ({int(r['pfy'])} et {int(r['fy'])}).")
    return T

SUBW={'headroom':('P1',.50),'autonomy':('P1',.35),'assoc':('P1',.15),'fr_ta':('P2',.60),'current':('P2',.40),'roa':('P3',.55),'re_ta':('P3',.45),
      'd_equity':('P4',.50),'d_assets':('P4',.25),'loss_streak':('P4',.25),'age':('P5',.25),'size_ta':('P5',.15),'capital':('P5',.25),'scale_edicom':('P5',.25)}
def drivers(r,k=3):
    T=texts(r); items=[]
    for key,(p,w) in SUBW.items():
        s=r.get('s_'+key)
        if pd.isna(s) or key not in T: continue
        eff=(s-50)*S.CONFIG['pillar_w'][p]*w
        items.append((key,s,eff))
    pos=sorted([i for i in items if i[1]>=65],key=lambda x:-x[2])[:k]; neg=sorted([i for i in items if i[1]<=40],key=lambda x:(x[0]!='headroom',x[2]))[:k]
    good=[T[i[0]][0] for i in pos if T[i[0]][0]]; bad=[T[i[0]][1] for i in neg if T[i[0]][1]]
    # special flags
    if pd.notna(r['TN_cur']) and r['TN_cur']<0 and r['TRESO_P_cur']>0: bad.append(f"Trésorerie nette négative ({dh(r['TN_cur'])}) : recours aux crédits de trésorerie / découverts.")
    if r['CP_cur']<0 and r['F6_assoc_cur']>abs(r['CP_cur']): bad.append(f"Déficit de fonds propres entièrement couvert par les comptes d'associés ({dh(r['F6_assoc_cur'])}) : soutien actionnaire à confirmer (blocage, abandon de créance).")
    return good[:k],bad[:k+1]
