import pandas as pd, hashlib, json, struct, numpy as np, requests
from concurrent.futures import ThreadPoolExecutor
from cdfhdr import parse, fetch, B
d=pd.read_csv("bucket_listing.csv"); d=d[d.key.str.endswith(".nc")].copy()
d["expt"]=d.key.str.extract(r"_(\d{3})_")
# stratified sample: 12 per (expt,size) + first/last of each expt
s=pd.concat([g.sample(min(len(g),12),random_state=1) for _,g in d.groupby(["expt","size"])]+[d.groupby("expt").head(1),d.groupby("expt").tail(1)]).drop_duplicates("key")
def one(key):
    b=fetch(key,67000); h=parse(b)
    t,tau=struct.unpack(">dd",b[h["vars"]["time"]["begin"]:h["vars"]["time"]["begin"]+16])
    layout={k:(v["begin"],v["vsize"],v["dtype"],tuple(v["shape"])) for k,v in h["vars"].items()}
    # attrs excluding tau.time_origin which is per-run
    at={k:{a:x for a,x in v["attrs"].items() if not (k=="tau" and a=="time_origin")} for k,v in h["vars"].items()}
    coords=hashlib.md5(b[h["vars"]["depth"]["begin"]:h["vars"]["time"]["begin"]]).hexdigest()
    return dict(key=key,hlen=h["header_len"],numrecs=h["numrecs"],layout=hashlib.md5(repr(sorted(layout.items())).encode()).hexdigest()[:8],
        attrs=hashlib.md5(json.dumps([h["gatts"],at],sort_keys=True).encode()).hexdigest()[:8],coords=coords[:8],time=t,tau=tau,
        tau_origin=h["vars"]["tau"]["attrs"].get("time_origin"),gatts=json.dumps(h["gatts"],sort_keys=True),h=h)
with ThreadPoolExecutor(16) as ex: res=list(ex.map(one,s.key))
r=pd.DataFrame(res).merge(d[["key","size","expt"]],on="key")
m=r.key.str.extract(r"_(\d{10})_t(\d{3})\.nc")
r["fname_time"]=pd.to_datetime(m[0],format="%Y%m%d%H")+pd.to_timedelta(m[1].astype(int),unit="h")
r["file_time"]=pd.Timestamp("2000-01-01")+pd.to_timedelta(r.time,unit="h")
print("n sampled",len(r))
print(r.groupby(["size","hlen","layout","attrs","coords","numrecs"]).agg(n=("key","size"),expts=("expt",lambda x:",".join(sorted(set(x))))))
print("time mismatches (file vs filename):",(r.fname_time!=r.file_time).sum())
print("tau vs tNNN mismatch:",(r.tau!=m[1].astype(int)).sum())
a=r[r["size"]==4827801944].iloc[0]; b=r[r["size"]==4827801984].iloc[0]
print("small:",a.key); print("big:",b.key)
ha,hb=a.h,b.h
print("gatts differ:",{k:(ha["gatts"].get(k),hb["gatts"].get(k)) for k in set(ha["gatts"])|set(hb["gatts"]) if ha["gatts"].get(k)!=hb["gatts"].get(k)})
for v in hb["vars"]:
    if v not in ha["vars"]: print("var missing in small:",v); continue
    for k in set(ha["vars"][v]["attrs"])|set(hb["vars"][v]["attrs"]):
        x,y=ha["vars"][v]["attrs"].get(k),hb["vars"][v]["attrs"].get(k)
        if x!=y: print(" ",v,k,repr(x),"|",repr(y))
    if ha["vars"][v]["begin"]!=hb["vars"][v]["begin"]: print("  begin",v,ha["vars"][v]["begin"],hb["vars"][v]["begin"])
