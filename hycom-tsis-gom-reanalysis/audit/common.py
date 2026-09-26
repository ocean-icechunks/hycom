"""Shared helpers for the GOMb0.01 audit (issue #8).

Every request goes to data.hycom.org, one connection unless a script says otherwise.
tds.hycom.org is not used for data: its ranged responses are chunked with no
Content-Length, which Icechunk's HTTP reader rejects (see report.md, F1).
"""
import fsspec, h5py, requests
from virtualizarr.manifests.utils import create_v3_array_metadata

PREFIX = "https://data.hycom.org/datasets/GOMb0.01/reanalysis/data/"
_fs = fsspec.filesystem("https")


def h5open(url, block_size=2**20):
    """h5py over HTTP. The size comes from a 1-byte ranged GET's Content-Range, because
    HEAD on tds.hycom.org carries no Content-Length and fsspec then refuses to seek."""
    size = int(requests.get(url, headers={"Range": "bytes=0-0"}).headers["content-range"].split("/")[1])
    return h5py.File(_fs.open(url, size=size, block_size=block_size, cache_type="blockcache"))


def chunks_of(d):
    """{logical chunk offset: (byte offset, stored size)} for a chunked HDF5 dataset."""
    out = {}
    for i in range(d.id.get_num_chunks()):
        c = d.id.get_chunk_info(i)
        out[c.chunk_offset] = (c.byte_offset, c.size)
    return out


def layout(url):
    """Shape, chunking, compression, fill, attributes and every chunk's byte range, per variable."""
    out = {"vars": {}}
    with h5open(url) as h:
        out["size"] = h.id.get_filesize()
        for k, d in h.items():
            if not isinstance(d, h5py.Dataset):
                continue
            offs = list(chunks_of(d).values()) if d.chunks else [(d.id.get_offset(), d.id.get_storage_size())]
            out["vars"][k] = dict(shape=d.shape, chunks=d.chunks, comp=d.compression, fill=str(d.fillvalue),
                                  attrs={a: str(d.attrs[a]) for a in d.attrs if a not in ("DIMENSION_LIST", "REFERENCE_LIST")},
                                  offs=offs)
        out["gattrs"] = {a: str(h.attrs[a]) for a in h.attrs}
    return out


def meta(shape, chunk, dims, dtype, fill):
    """Zarr v3 metadata for an uncompressed little-endian float32 array (no codecs but `bytes`)."""
    assert dtype.byteorder in "<=", dtype
    return create_v3_array_metadata(shape=shape, chunk_shape=chunk, data_type=dtype.newbyteorder("="),
                                    codecs=[{"name": "bytes", "configuration": {"endian": "little"}}],
                                    fill_value=fill, dimension_names=dims)
