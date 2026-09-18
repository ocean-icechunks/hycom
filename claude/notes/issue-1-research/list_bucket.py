import requests, re, csv, collections
B="https://hycom-gofs-3pt1-reanalysis.s3.us-west-2.amazonaws.com"
tok=None; rows=[]
s=requests.Session()
while True:
    p={"list-type":"2","max-keys":"1000"}
    if tok: p["continuation-token"]=tok
    t=s.get(B,params=p,timeout=60).text
    rows+=re.findall(r"<Key>([^<]*)</Key><LastModified>([^<]*)</LastModified><ETag>[^<]*</ETag><Size>(\d+)",t)
    m=re.search(r"<NextContinuationToken>([^<]*)<",t)
    if not m: break
    tok=m.group(1)
with open("bucket_listing.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(["key","last_modified","size"]); w.writerows(rows)
nc=[r for r in rows if r[0].endswith(".nc")]
print("objects",len(rows),"nc",len(nc),"TB",sum(int(r[2]) for r in nc)/1e12)
print("non-nc:",[r for r in rows if not r[0].endswith(".nc")][:40])
print("sizes:",collections.Counter(r[2] for r in nc).most_common(10))
print("expts:",sorted(collections.Counter(re.search(r"_(\d{3})_",r[0]).group(1) for r in nc).items()))
print("per year:",sorted(collections.Counter(r[0][:4] for r in nc).items()))
print("tNNN:",sorted(collections.Counter(r[0][-7:-3] for r in nc).items()))
