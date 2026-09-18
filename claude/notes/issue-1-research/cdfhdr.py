"""Minimal NetCDF classic/64-bit-offset header parser (no data read)."""
import struct, requests, sys, json
B="https://hycom-gofs-3pt1-reanalysis.s3.us-west-2.amazonaws.com/"
NCT={1:("i1",1),2:("S1",1),3:(">i2",2),4:(">i4",4),5:(">f4",4),6:(">f8",8)}
class R:
    def __init__(s,b): s.b=b; s.p=0
    def i4(s): v=struct.unpack(">i",s.b[s.p:s.p+4])[0]; s.p+=4; return v
    def i8(s): v=struct.unpack(">q",s.b[s.p:s.p+8])[0]; s.p+=8; return v
    def name(s):
        n=s.i4(); v=s.b[s.p:s.p+n].decode(); s.p+=(n+3)//4*4; return v
    def vals(s,t,n):
        dt,sz=NCT[t]; raw=s.b[s.p:s.p+n*sz]; s.p+=(n*sz+3)//4*4
        if t==2: return raw.decode("latin1")
        import numpy as np; return np.frombuffer(raw,dt).tolist()
    def atts(s):
        tag=s.i4(); n=s.i4(); out={}
        for _ in range(n):
            k=s.name(); t=s.i4(); m=s.i4(); out[k]=s.vals(t,m)
        return out
def parse(b):
    r=R(b); magic=b[:4]; r.p=4; ver=magic[3]
    numrecs=r.i4(); tag=r.i4(); nd=r.i4(); dims=[]
    for _ in range(nd): dims.append((r.name(),r.i4()))
    gatts=r.atts(); tag=r.i4(); nv=r.i4(); vs={}
    for _ in range(nv):
        nm=r.name(); k=r.i4(); did=[r.i4() for _ in range(k)]; a=r.atts(); t=r.i4(); vsize=r.i4()
        begin=r.i8() if ver==2 else r.i4()
        vs[nm]=dict(dims=[dims[i][0] for i in did],shape=[dims[i][1] for i in did],dtype=NCT[t][0],vsize=vsize,begin=begin,attrs=a)
    return dict(magic=magic,numrecs=numrecs,dims=dims,gatts=gatts,vars=vs,header_len=r.p)
def fetch(key,n=65536):
    x=requests.get(B+key,headers={"Range":f"bytes=0-{n-1}"},timeout=60); assert x.status_code==206,x.status_code
    return x.content
if __name__=="__main__":
    h=parse(fetch(sys.argv[1]))
    print("magic",h["magic"],"numrecs",h["numrecs"],"header_len",h["header_len"]); print("dims",h["dims"])
    print("global attrs:"); [print("  ",k,"=",repr(v)[:200]) for k,v in h["gatts"].items()]
    for n,v in h["vars"].items():
        print(f"{n}: dims={v['dims']} shape={v['shape']} {v['dtype']} vsize={v['vsize']} begin={v['begin']}")
        for k,a in v["attrs"].items(): print("     ",k,"=",repr(a)[:160])
