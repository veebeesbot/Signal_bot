import os,requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application,CommandHandler,ContextTypes

A={"EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","AUDUSD":"AUDUSD=X","USDCAD":"USDCAD=X","BTCUSD":"BTC-USD","ETHUSD":"ETH-USD","GOLD":"GC=F","SILVER":"SI=F","OIL":"CL=F"}
T={"1m":("1m","1d"),"5m":("5m","5d"),"15m":("15m","5d"),"1h":("1h","30d")}

def f(sym,tf):
    try:
        iv,rg=T.get(tf,("5m","5d"))
        r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={iv}&range={rg}",headers={"User-Agent":"Mozilla/5.0"},timeout=15)
        if r.status_code!=200:return None
        j=r.json()["chart"]["result"][0]["indicators"]["quote"][0]
        return[{k:j[k][i]for k in ["open","high","low","close","volume"]}for i in range(len(j["close"]))if j["close"][i]is not None]
    except:return None

def ema(v,n):
    m=2/(n+1);r=[v[0]]
    for i in range(1,len(v)):r.append(v[i]*m+r[-1]*(1-m))
    return r

def rsi(c,p=14):
    g=[max(c[i]-c[i-1],0)for i in range(1,len(c))]
    l=[max(c[i-1]-c[i],0)for i in range(1,len(c))]
    if len(g)<p:return[None]*len(c)
    ag,al=sum(g[:p])/p,sum(l[:p])/p
    rs=[None]*len(c);rs[p]=100-(100/(1+ag/al))if al else 100
    for i in range(p,len(g)):
        ag,al=(ag*(p-1)+g[i])/p,(al*(p-1)+l[i])/p
        rs[i+1]=100-(100/(1+ag/al))if al else 100
    return rs

def sma(v,n):
    return[sum(v[i-n+1:i+1])/n if i>=n-1 else None for i in range(len(v))]

def std(v,n):
    r=[]
    for i in range(len(v)):
        if i<n-1:r.append(None)
        else:
            s=v[i-n+1:i+1];m=sum(s)/n
            r.append((sum((x-m)**2 for x in s)/n)**0.5)
    return r

def an(a,tf="5m"):
    a=a.upper()
    if a not in A:return{"e":f"'{a}' not found"}
    d=f(A[a],tf)
    if not d or len(d)<50:return{"e":"No data"}
    c=[x["close"]for x in d];h=[x["high"]for x in d];l=[x["low"]for x in d]
    rv=rsi(c,14);ef=ema(c,9);es=ema(c,21)
    e12,e26=ema(c,12),ema(c,26);md=[e12[i]-e26[i]for i in range(len(c))]
    ms,mh=ema(md,9),[md[i]-ms[i]for i in range(len(md))]
    ma20,sd20=sma(c,20),std(c,20)
    bu=[ma20[i]+2*sd20[i]if ma20[i]else None for i in range(len(c))]
    bl=[ma20[i]-2*sd20[i]if ma20[i]else None for i in range(len(c))]
    fb,fr=[0]*len(d),[0]*len(d)
    for i in range(2,len(d)-2):
        if l[i]<min(l[i-2:i])and l[i]<min(l[i+1:i+3]):fb[i]=1
        if h[i]>max(h[i-2:i])and h[i]>max(h[i+1:i+3]):fr[i]=1
    la,pr=len(d)-1,la-1
    cs=ps=0;rs=[]
    if rv[la]is not None:
        if rv[la]<30:cs+=2;rs.append(f"RSI oversold({rv[la]:.1f})")
        elif rv[la]>70:ps+=2;rs.append(f"RSI overbought({rv[la]:.1f})")
        elif rv[la]<45:cs+=0.5
        elif rv[la]>55:ps+=0.5
    if ef[la]>es[la]:cs+=1.5;rs.append("EMA golden cross"if ef[pr]<=es[pr]else"EMA bullish")
    else:ps+=1.5;rs.append("EMA death cross"if ef[pr]>=es[pr]else"EMA bearish")
    if md[la]>ms[la]:cs+=1;rs.append("MACD bull cross")if md[pr]<=ms[pr]else None
    else:ps+=1;rs.append("MACD bear cross")if md[pr]>=ms[pr]else None
    if mh[la]>mh[pr]:cs+=0.5
    else:ps+=0.5
    if bu[la]:
        if c[la]<bl[la]:cs+=1;rs.append("Below lower BB")
        elif c[la]>bu[la]:ps+=1;rs.append("Above upper BB")
    rc,brc=fb[-10:],fr[-10:];bc,br=sum(rc),sum(brc)
    if bc>0:
        dba=len(rc)-list(reversed(rc)).index(1)-1 if 1 in rc else 999
        if dba<=3:cs+=1.5;rs.append(f"Bull fractal {dba}b ago")
        else:cs+=0.5;rs.append(f"Bull fractal({bc})")
    if br>0:
        dbr=len(brc)-list(reversed(brc)).index(1)-1 if 1 in brc else 999
        if dbr<=3:ps+=1.5;rs.append(f"Bear fractal {dbr}b ago")
        else:ps+=0.5;rs.append(f"Bear fractal({br})")
    rs=[x for x in rs if x]
    if cs>=3 and cs>ps:sig,conf="CALL",min(cs/5.5*100,100)
    elif ps>=3 and ps>cs:sig,conf="PUT",min(ps/5.5*100,100)
    else:sig,conf="NEUTRAL",0
    ch=((c[la]-c[la-5])/c[la-5]*100)if len(c)>=5 else 0
    return{"a":a,"tf":tf,"s":sig,"co":round(conf,1),"p":round(c[la],5),"ch":round(ch,3),"r":round(rv[la],1)if rv[la]else"--","ef":round(ef[la],5),"es":round(es[la],5),"md":round(md[la],5),"bb":"Lower"if c[la]<bl[la]else"Upper"if c[la]>bu[la]else"Middle","bf":bc,"br":br,"rs":rs,"cs":round(cs,1),"ps":round(ps,1),"ts":datetime.now().strftime("%H:%M:%S")}

def fm(s):
    if"e"in s:return f"❌Error\n{s['e']}"
    em={"CALL":"🟢","PUT":"🔴","NEUTRAL":"⚪"};e=em.get(s["s"],"⚪")
    fx=""
    if s["bf"]>0 or s["br"]>0:
        p=[]
        if s["bf"]>0:p.append(f"🐂{s['bf']}bull")
        if s["br"]>0:p.append(f"🐻{s['br']}bear")
        fx="\n🌀Fractals:"+"|".join(p)+"\n"
    lines=[f"{e}*{s['a']}*|`{s['tf']}`|{s['ts']}","",f"📊*Signal:{s['s']}*({s['co']}%)",f"💰`{s['p']}`",f"📈{s['ch']}%","",f"📉RSI:`{s['r']}`",f"📊EMA:`{s['ef']}`/`{s['es']}`",f"📉MACD:`{s['md']}`",f"🎯BB:{s['bb']}",fx]
    if s["rs"]:lines.append("📝*Reasons:*");[lines.append(f"  •{x}")for x in s["rs"]]
    else:lines.append("📝No confluence")
    lines+=["",f"⚖️Bull:{s['cs']}|Bear:{s['ps']}","","⚠️Educational only"]
    return"\n".join(lines)

async def st(u:Update,c:ContextTypes.DEFAULT_TYPE):await u.message.reply_text("👋*Signal Bot*\nIndicators:RSI,EMA,MACD,BB,*Fractals*\n\n`/signal EURUSD 5m`\n`/scan`\n`/assets`",parse_mode="Markdown")
async def hp(u:Update,c:ContextTypes.DEFAULT_TYPE):await u.message.reply_text("📖`/signal<asset><tf>`—e.g.`/signal EURUSD 5m`\n`/scan`—best signals\n`/assets`—list assets\nTFs:1m,5m,15m,1h",parse_mode="Markdown")
async def ast(u:Update,c:ContextTypes.DEFAULT_TYPE):await u.message.reply_text("📋"+"\n".join([f"`{k}`"for k in A.keys()]),parse_mode="Markdown")
async def sg(u:Update,c:ContextTypes.DEFAULT_TYPE):
    a=c.args;asset=(a[0].upper()if a else"EURUSD");tf=a[1]if len(a)>1 else"5m"
    if tf not in T:await u.message.reply_text(f"❌Bad tf`{tf}`.Use:1m,5m,15m,1h",parse_mode="Markdown");return
    await c.bot.send_chat_action(chat_id=u.effective_chat.id,action="typing")
    await u.message.reply_text(fm(an(asset,tf)),parse_mode="Markdown")
async def sc(u:Update,c:ContextTypes.DEFAULT_TYPE):
    await c.bot.send_chat_action(chat_id=u.effective_chat.id,action="typing")
    sigs=[]
    for asset in A.keys():
        r=an(asset,"5m")
        if"e"not in r and r["s"]in["CALL","PUT"]and r["co"]>=60:sigs.append(r)
    sigs.sort(key=lambda x:x["co"],reverse=True)
    if not sigs:await u.message.reply_text("🔍No strong signals now.",parse_mode="Markdown");return
    lines=[f"🎯*Top Signals*({len(sigs)})\n"]
    for s in sigs[:10]:
        e="🟢"if s["s"]=="CALL"else"🔴";fx=" 🐂"if s["bf"]>0 else" 🐻"if s["br"]>0 else""
        lines.append(f"{e}`{s['a']}`:*{s['s']}*({s['co']}%)`{s['p']}`")
    lines.append("\nUse`/signal<asset>5m`for details.")
    await u.message.reply_text("\n".join(lines),parse_mode="Markdown")

def main():
    t=os.environ.get("TELEGRAM_BOT_TOKEN")
    if not t:print("❌Set TELEGRAM_BOT_TOKEN first");return
    print("🚀Signal Bot with Fractals starting...")
    app=Application.builder().token(t).build()
    app.add_handler(CommandHandler("start",st))
    app.add_handler(CommandHandler("help",hp))
    app.add_handler(CommandHandler("assets",ast))
    app.add_handler(CommandHandler("signal",sg))
    app.add_handler(CommandHandler("scan",sc))
    app.run_polling()
if __name__=="__main__":main()
