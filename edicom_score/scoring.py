"""
EDICOM FINANCIAL HEALTH SCORE  (v0.1 - prototype)
Pure functions: take the derived balance-sheet features (features.py) + Edicom record -> pillar scores, score, class.
All thresholds live in CONFIG so they can be tuned/versioned without touching code.
"""
import numpy as np, pandas as pd

CONFIG = {
 'min_total_assets': 10_000,        # below this the balance sheet is not meaningful (shell / dormant)
 # ---- anchors: (x points, score 0-100 at those points), linear interpolation, clipped at ends
 'anchors': {
   'headroom':   ([0, 0.25, 0.5, 1.0, 1.5, 3.0],            [0, 10, 30, 60, 80, 100]),   # CP / capital social  (legal 1/4 rule)
   'autonomy':   ([-0.5, 0, 0.10, 0.20, 0.30, 0.50],        [0,  5, 30, 50, 70, 95]),    # CP / total actif
   'assoc':      ([0.15, 0.30, 0.50, 0.80, 1.2],            [100, 80, 50, 25, 0]),       # comptes d'associes / total actif
   'current':    ([0.5, 0.8, 1.0, 1.2, 1.5, 2.0],           [0, 25, 45, 65, 85, 100]),   # liquidite generale
   'fr_ta':      ([-0.5, 0, 0.20, 0.40],                    [0, 40, 75, 100]),           # fonds de roulement / total actif
   'roa':        ([-0.15, -0.05, 0, 0.02, 0.05, 0.10],      [0, 25, 45, 55, 75, 100]),   # resultat net / total actif
   're_ta':      ([-0.3, -0.1, 0, 0.05, 0.2, 0.4],          [0, 25, 45, 60, 85, 100]),   # benefices cumules / total actif (Altman X2)
   'age':        ([1, 2, 3, 5, 8, 12, 20],                  [10, 25, 35, 55, 70, 85, 100]),
   'size_ta':    ([5e4, 2.5e5, 1e6, 5e6, 2e7],              [10, 35, 60, 85, 100]),      # total actif (DH)
   'capital':    ([1e4, 1e5, 5e5, 2e6],                     [20, 40, 70, 100]),
   'd_equity':   ([-0.5, 0, 0.5],                           [0, 50, 100]),               # (CP_t - CP_t-1)/capital
   'd_assets':   ([-0.5, -0.2, 0, 0.3, 1.0],                [0, 40, 60, 100, 80]),       # TA growth
 },
 'ca_band': {'A':30,'B':45,'C':60,'D':75,'E':85,'F':90,'G':95,'H':100,'I':100,'J':100},
 'form':    {'SA':80,'SARL':55,'SARLAU':50},
 # ---- sub-indicator weights inside each pillar
 'sub_w': {
   'P1': {'headroom':.50,'autonomy':.35,'assoc':.15},
   'P2': {'fr_ta':.60,'current':.40},
   'P3': {'roa':.55,'re_ta':.45},
   'P4': {'d_equity':.50,'d_assets':.25,'loss_streak':.25},
   'P5': {'age':.25,'size_ta':.15,'capital':.25,'scale_edicom':.25,'form':.05,'visibility':.05},
 },
 'pillar_w': {'P1':.30,'P2':.10,'P3':.28,'P4':.10,'P5':.22},
 'caps': {'neg_equity':30,'legal_alert':45},
}
PILLAR_NAMES={'P1':'Solvabilité & capitalisation','P2':'Liquidité & équilibre financier','P3':'Rentabilité & capacité bénéficiaire','P4':'Dynamique (N-1 → N)','P5':'Profil & substance de l\'entreprise'}

def interp(name,x,cfg=CONFIG):
    xs,ys=cfg['anchors'][name]; x=pd.to_numeric(x,errors='coerce').astype(float)
    out=np.interp(x.fillna(np.nan),xs,ys); out=np.where(x.isna()|~np.isfinite(x),np.nan,out); return pd.Series(out,index=x.index)

def ratio(n,d): 
    d=d.where(d.abs()>0); return (n/d).replace([np.inf,-np.inf],np.nan)

def compute_indicators(cur, prev=None, edi=None):
    """cur/prev: DataFrames indexed by firm code (features.derive output). edi: Edicom frame indexed by Code Firme."""
    I=pd.DataFrame(index=cur.index); TA=cur.TA
    I['TA']=TA; I['capital']=cur.capital
    I['headroom']=ratio(cur.CP,cur.capital.where(cur.capital>0))
    I['autonomy']=ratio(cur.CP,TA)
    I['assoc']=ratio(cur.F6_assoc.clip(lower=0),TA)
    cl=cur.CL.where(cur.CL>0)
    I['current']=(cur.CA_liq/cl).replace([np.inf,-np.inf],np.nan).clip(upper=10)
    I.loc[~cur.actif_ok,'current']=np.nan
    I['fr_ta']=ratio(cur.FR,TA); I.loc[~cur.actif_ok,'fr_ta']=np.nan
    I['roa']=ratio(cur.RN,TA); I['re_ta']=ratio(cur.RE,TA)
    I['tn_ta']=ratio(cur.TN,TA); I['cash_ta']=ratio(cur.TRESO_A,TA)
    I['fin_ta']=ratio(cur.DFIN_LT+cur.TRESO_P,TA)
    if prev is not None:
        p=prev.reindex(cur.index)
        I['d_equity']=ratio(cur.CP-p.CP,cur.capital.where(cur.capital>0))
        I['d_assets']=ratio(TA-p.TA,p.TA.where(p.TA>0))
        l_now=(cur.RN<0).astype(float); l_prev=(p.RN<0).astype(float).where(p.RN.notna())
        I['loss_streak']=np.where(l_prev.isna(),np.nan,l_now+l_prev)           # 0,1,2 losses in the 2 years
        I['loss_streak_score']=I['loss_streak'].map({0:100,1:45,2:0})
    else:
        for c in ('d_equity','d_assets','loss_streak','loss_streak_score'): I[c]=np.nan
    if edi is not None:
        e=edi.reindex(cur.index); yr=int(cur.year.iloc[0])
        I['age']=(yr-pd.to_numeric(e['ANNEE CREATION'],errors='coerce').where(lambda s:s>1900))
        I['effectif']=e['EFFECTIF']; I['ca_band']=e['GAME CA']; I['forme']=e['FORM.JUR']
        I['ca_edi']=pd.to_numeric(e['CA'],errors='coerce'); I['ca_year']=e['ANNEE CA']
        I['edi_capital']=pd.to_numeric(e['CAPITAL'],errors='coerce')
        I['visibility']=(e['TEL 1'].notna().astype(int)+e['EMAIL'].notna().astype(int)+e['WEB'].notna().astype(int)+e['Fonction'].notna().astype(int))
    return I

def sub_scores(I,cfg=CONFIG):
    S=pd.DataFrame(index=I.index)
    for k in ('headroom','autonomy','assoc','current','fr_ta','roa','re_ta','d_equity','d_assets'): S[k]=interp(k,I[k],cfg)
    S['loss_streak']=I['loss_streak_score']
    if 'age' in I:
        S['age']=interp('age',I['age'],cfg); S['size_ta']=interp('size_ta',I['TA'],cfg)
        cap=I['edi_capital'].where(I['edi_capital']>0).fillna(I['capital'].where(I['capital']>0))
        S['capital']=interp('capital',cap,cfg)
        scale=I['ca_band'].map(cfg['ca_band'])
        e=pd.to_numeric(I['effectif'],errors='coerce'); eff=pd.Series(np.interp(e.fillna(0),[1,5,20,50,100],[50,60,80,92,100]),index=I.index).where(e>0)
        S['scale_edicom']=scale.combine_first(eff)
        S['form']=I['forme'].map(cfg['form'])
        S['visibility']=I['visibility'].map({0:20,1:45,2:65,3:85,4:100})
    return S

def pillar_scores(S,cfg=CONFIG):
    P=pd.DataFrame(index=S.index); cov={}
    for p,ws in cfg['sub_w'].items():
        num=0; den=0
        for k,w in ws.items():
            if k in S:
                v=S[k]; num=num+np.where(v.notna(),v*w,0); den=den+np.where(v.notna(),w,0)
        P[p]=np.where(den>0,num/np.where(den>0,den,1),np.nan); cov[p]=den/sum(ws.values())
    return P,pd.DataFrame(cov,index=S.index)

def overall(P,cfg=CONFIG):
    w=cfg['pillar_w']; num=0; den=0
    for p,ww in w.items():
        v=P[p]; num=num+np.where(v.notna(),v*ww,0); den=den+np.where(v.notna(),ww,0)
    return pd.Series(np.where(den>0,num/np.where(den>0,den,1),np.nan),index=P.index),pd.Series(den/sum(w.values()),index=P.index)

def apply_caps(score,cur,cfg=CONFIG):
    s=score.copy(); flag=pd.Series('',index=s.index)
    legal=(cur.CP<0.25*cur.capital)&(cur.capital>0); neg=cur.CP<0
    s=np.where(legal,np.minimum(s,cfg['caps']['legal_alert']),s); s=pd.Series(s,index=score.index)
    s=np.where(neg,np.minimum(s,cfg['caps']['neg_equity']),s); s=pd.Series(s,index=score.index)
    return s

def altman_z2(cur):
    """Altman Z'' (emerging markets) with net result as EBIT proxy (no CPC available) -- benchmark only."""
    TA=cur.TA.where(cur.TA.abs()>0); wc=cur.CA_liq-cur.CL
    x1=wc/TA; x2=cur.RE/TA; x3=cur.RN/TA; x4=cur.CP/(cur.TA-cur.CP).where((cur.TA-cur.CP).abs()>0)
    return 3.25+6.56*x1+3.26*x2+6.72*x3+1.05*x4

def score_year(cur,prev=None,edi=None,cfg=CONFIG,caps=True):
    cur=cur.set_index('F') if 'F' in cur.columns else cur
    if prev is not None and 'F' in prev.columns: prev=prev.set_index('F')
    I=compute_indicators(cur,prev,edi); S=sub_scores(I,cfg); P,cov=pillar_scores(S,cfg)
    raw,conf=overall(P,cfg); sc=apply_caps(raw,cur,cfg) if caps else raw
    out=pd.concat([I,S.add_prefix('s_'),P],axis=1); out['raw_score']=raw; out['score']=sc; out['coverage']=conf
    out['scorable']=(cur.TA>=cfg['min_total_assets'])&cur.TA.notna()
    out.loc[~out.scorable,'score']=np.nan
    return out
