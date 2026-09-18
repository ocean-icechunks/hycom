"""Feasibility probe: hand-built per-level virtual refs -> local Icechunk -> fresh read."""
import sys, time, shutil, struct, numpy as np, pandas as pd, xarray as xr, zarr, icechunk
from virtualizarr.manifests import ChunkManifest, ManifestArray
from virtualizarr.manifests.utils import create_v3_array_metadata
from cdfhdr import parse, fetch
PREFIX=sys.argv[1]  # s3://hycom-gofs-3pt1-reanalysis/  or https://...amazonaws.com/
zarr.config.set({"async.concurrency":64})
d=pd.read_csv("bucket_listing.csv"); d=d[d.key.str.endswith(".nc")].copy()
m=d.key.str.extract(r"_(\d{10})_t(\d{3})\.nc")
d["time"]=pd.to_datetime(m[0],format="%Y%m%d%H")+pd.to_timedelta(m[1].astype(int),unit="h")
d=d.set_index("time").sort_index()
times=pd.date_range("2004-12-28 06:00","2004-12-28 15:00",freq="3h"); w=d.reindex(times)
print(w[["key","size"]])
hdrs={}; buf={}
for t,k in w.key.dropna().items():
    b=fetch(k,67000); h=parse(b); hdrs[t]=h; buf[t]=b
    tv=struct.unpack(">d",b[h["vars"]["time"]["begin"]:][:8])[0]
    assert pd.Timestamp("2000-01-01")+pd.Timedelta(hours=tv)==t,(t,tv)
    print(k,"hlen",h["header_len"],"water_temp begin",h["vars"]["water_temp"]["begin"])
h0=hdrs[times[0]]; NT=len(times); NZ,NY,NX=40,3251,4500; LVL=NY*NX*2
CODECS=[{"name":"bytes","configuration":{"endian":"big"}}]
def marr(name):
    v=h0["vars"][name]; is4d="depth" in v["dims"]; nz=NZ if is4d else 1
    paths=np.full((NT,nz),"",dtype=np.dtypes.StringDType()); off=np.zeros((NT,nz),"uint64"); ln=np.zeros((NT,nz),"uint64")
    for i,t in enumerate(times):
        if t not in hdrs: continue                     # missing time step -> no ref -> fill value
        beg=hdrs[t]["vars"][name]["begin"]
        paths[i,:]=PREFIX+w.key[t]; off[i,:]=beg+np.arange(nz,dtype="uint64")*LVL; ln[i,:]=LVL
    shape=(NT,NZ,NY,NX) if is4d else (NT,NY,NX); chunks=(1,1,NY,NX) if is4d else (1,NY,NX)
    if not is4d: paths,off,ln=paths[:,0],off[:,0],ln[:,0]
    paths=paths.reshape(paths.shape+(1,1)); off=off.reshape(paths.shape); ln=ln.reshape(paths.shape)
    a=dict(v["attrs"]); fill=a.pop("_FillValue")[0]; a.pop("missing_value",None)
    a={k:(x[0] if isinstance(x,list) and len(x)==1 else x) for k,x in a.items()}
    md=create_v3_array_metadata(shape=shape,data_type=np.dtype(">i2"),chunk_shape=chunks,fill_value=fill,codecs=CODECS,attributes=a,dimension_names=v["dims"])
    return xr.Variable(v["dims"],ManifestArray(metadata=md,chunkmanifest=ChunkManifest.from_arrays(paths=paths,offsets=off,lengths=ln)),attrs=a,encoding={"_FillValue":fill})
b0=buf[times[0]]; cv=lambda n,dt: np.frombuffer(b0[h0["vars"][n]["begin"]:h0["vars"][n]["begin"]+h0["vars"][n]["vsize"]],dt)[:h0["vars"][n]["shape"][0]].astype("f8")
coords={"time":("time",times),"depth":("depth",cv("depth",">f8"),h0["vars"]["depth"]["attrs"]),"lat":("lat",cv("lat",">f8"),h0["vars"]["lat"]["attrs"]),"lon":("lon",cv("lon",">f8"),h0["vars"]["lon"]["attrs"])}
names=[n for n in h0["vars"] if "lat" in h0["vars"][n]["dims"] and len(h0["vars"][n]["dims"])>1]
vds=xr.Dataset({n:marr(n) for n in names},coords=coords,attrs=h0["gatts"])
print(vds)
shutil.rmtree("probe_repo",ignore_errors=True)
cfg=icechunk.RepositoryConfig.default()
store=icechunk.s3_store(region="us-west-2",anonymous=True) if PREFIX.startswith("s3") else icechunk.http_store()
cfg.set_virtual_chunk_container(icechunk.VirtualChunkContainer(url_prefix=PREFIX,store=store))
repo=icechunk.Repository.create(icechunk.local_filesystem_storage("probe_repo"),cfg)
s=repo.writable_session("main"); t0=time.time()
vds.vz.to_icechunk(s.store,encoding={"time":{"chunks":(NT,)}}) if False else vds.vz.to_icechunk(s.store)
print("snapshot",s.commit("probe"),"write s",round(time.time()-t0,2)); repo.save_config()
# ---- fresh read-only open, as a consumer would
creds=icechunk.containers_credentials({PREFIX:icechunk.s3_anonymous_credentials()}) if PREFIX.startswith("s3") else icechunk.containers_credentials({PREFIX:None})
r2=icechunk.Repository.open(icechunk.local_filesystem_storage("probe_repo"),authorize_virtual_chunk_access=creds)
t0=time.time(); ds=xr.open_zarr(r2.readonly_session("main").store,consolidated=False,chunks={}); print("open s",round(time.time()-t0,2)); print(ds.water_temp)
t0=time.time(); lvl=ds.water_temp.isel(time=slice(1,2),depth=slice(5,6)).squeeze(drop=True).load(); print("one level (29MB) s",round(time.time()-t0,2),"mean",float(lvl.mean()),"nan frac",float(lvl.isnull().mean()))
t0=time.time(); ssh=ds.surf_el.isel(time=slice(3,4)).squeeze(drop=True).load(); print("surf_el s",round(time.time()-t0,2))
miss=ds.water_temp.isel(time=slice(2,3),depth=slice(0,1)).load(); print("missing step all-NaN:",bool(miss.isnull().all()))
t0=time.time(); col=ds.water_temp.isel(time=slice(0,1)).sel(lat=slice(30,32),lon=slice(200,204)).load(); print("40-level box (40 chunks) s",round(time.time()-t0,2),col.shape)
np.save("probe_vals.npy",ds.water_temp.isel(time=1,depth=5,lat=slice(1500,1510),lon=slice(2000,2010)).values)
np.save("probe_vals_t3.npy",ds.salinity.isel(time=3,depth=39,lat=slice(1500,1510),lon=slice(2000,2010)).values)
print("du:"); import subprocess; print(subprocess.run("du -sh probe_repo; find probe_repo -type f | wc -l",shell=True,capture_output=True,text=True).stdout)
