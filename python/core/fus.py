# SPDX-License-Identifier: MIT
"""
Samsung FUS Firmware Downloader core wrapper using samloader.
Provides programmatic check-update, download, and auto-decryption for Samsung firmware.
"""

import os
import xml.etree.ElementTree as ET
from samloader import fusclient
from samloader import versionfetch
from samloader import crypt
from samloader import request


def check_latest_version(model: str, region: str) -> str:
    """Check the latest available firmware version for a model and region."""
    model = model.strip().upper()
    region = region.strip().upper()
    return versionfetch.getlatestver(model, region)


def list_all_versions(model: str, region: str) -> list:
    """
    List all available firmware versions for a model and region.
    Returns list of dicts: [{'version': '...', 'size': int, 'rcount': int}, ...]
    """
    model = model.strip().upper()
    region = region.strip().upper()
    import requests
    url = f"https://fota-cloud-dn.ospserver.net/firmware/{region}/{model}/version.xml"
    req = requests.get(url, timeout=15)
    if req.status_code == 403:
        raise Exception("Model or region not found (403)")
    req.raise_for_status()
    root = ET.fromstring(req.text)
    versions = []
    for val in root.findall(".//upgrade/value"):
        ver = val.text
        size = int(val.get("fwsize", 0))
        rcount = int(val.get("rcount", 0))
        if ver:
            versions.append({"version": ver, "size": size, "rcount": rcount})
    return versions


def get_firmware_details(model: str, region: str) -> dict:
    """SamFW-style firmware record for a model+region, without downloading.

    Queries version.xml for the latest version code, matches its size from
    the version list, and asks BinaryInform for the exact server filename
    and byte size. BinaryInform/size lookups are best-effort - the version
    code itself is the load-bearing field.

    Returns {model, region, version, pda, csc, cp, size_bytes|None,
             filename|None}.
    """
    model = model.strip().upper()
    region = region.strip().upper()
    ver = check_latest_version(model, region)
    parts = ver.split("/")
    pda = parts[0] if len(parts) > 0 else ver
    csc = parts[1] if len(parts) > 1 else ""
    cp = parts[2] if len(parts) > 2 else ""
    size = None
    try:
        for v in list_all_versions(model, region):
            entry = (v.get("version") or "")
            if versionfetch.normalizevercode(entry) == ver or entry.split("/")[0] == pda:
                size = int(v.get("size") or 0) or None
                break
    except Exception:
        pass
    filename = None
    try:
        client = fusclient.FUSClient()
        _path, filename, size = _binary_inform(client, ver, model, region)
    except Exception:
        pass
    return {
        "model": model,
        "region": region,
        "version": ver,
        "pda": pda,
        "csc": csc,
        "cp": cp,
        "size_bytes": size,
        "filename": filename,
    }


def _binary_inform(client, fw_ver: str, model: str, region: str):
    """(path, filename, size) for a firmware version via DownloadBinaryInform.

    Wraps the real samloader 0.4.1 flow: binaryinform request +
    NF_DownloadBinaryInform.do, with the Status==200 guard. Raises
    RuntimeError when Samsung reports the bundle as unavailable.
    """
    req = request.binaryinform(fw_ver, model, region, client.nonce)
    resp = client.makereq("NF_DownloadBinaryInform.do", req)
    root = ET.fromstring(resp)
    status = root.find("./FUSBody/Results/Status")
    if status is None or int(status.text) != 200:
        raise RuntimeError(
            f"DownloadBinaryInform failed for {model} ({region}) v{fw_ver} - "
            "firmware bundle not found on Samsung servers?"
        )
    filename = root.find("./FUSBody/Put/BINARY_NAME/Data").text
    size = int(root.find("./FUSBody/Put/BINARY_BYTE_SIZE/Data").text)
    path = root.find("./FUSBody/Put/MODEL_PATH/Data").text
    if not filename:
        raise RuntimeError("DownloadBinaryInform returned no firmware bundle")
    return path, filename, size


def _init_download(client, filename: str) -> None:
    """Open the server-side download session (NF_DownloadBinaryInitForMass)."""
    req = request.binaryinit(filename, client.nonce)
    client.makereq("NF_DownloadBinaryInitForMass.do", req)


def download_and_decrypt_firmware(
    model: str,
    region: str,
    fw_ver: str,
    out_dir: str,
    progress_callback=None,
    log_callback=None,
) -> str:
    """
    Download and automatically decrypt firmware for a Samsung device.
    model: e.g. SM-S918B
    region: e.g. EUX
    fw_ver: e.g. S918BXXU3BWCV/S918BOXM3BWCV/S918BXXU3BWCV
    out_dir: destination directory
    progress_callback: callable(bytes_downloaded, total_bytes)
    log_callback: callable(str)
    Returns absolute path of the final decrypted .tar.md5 file.
    """
    model = model.strip().upper()
    region = region.strip().upper()
    fw_ver = fw_ver.strip()
    os.makedirs(out_dir, exist_ok=True)

    def log(msg):
        if log_callback:
            log_callback(msg)

    log(f"Initializing FUS client for {model} ({region}) v{fw_ver}...")
    client = fusclient.FUSClient()

    log("Requesting binary information from Samsung FUS servers...")
    try:
        latest_ver = check_latest_version(model, region)
        if latest_ver != fw_ver:
            log(f"[warn] Requested version {fw_ver} differs from latest server version {latest_ver}")
    except Exception:
        pass
    path, filename, size = _binary_inform(client, fw_ver, model, region)

    enc_file = os.path.join(out_dir, filename)
    
    log(f"Target file: {filename} ({size / (1024*1024):.1f} MB)")

    dloffset = 0
    if os.path.exists(enc_file):
        existing_size = os.path.getsize(enc_file)
        if existing_size == size:
            log("Encrypted file already fully downloaded.")
            dloffset = size
        elif existing_size < size:
            log(f"Resuming download from {existing_size} bytes...")
            dloffset = existing_size

    if dloffset < size:
        log("Initializing download session...")
        _init_download(client, filename)

        log("Starting stream download...")
        r = client.downloadfile(path + filename, dloffset)
        
        mode = "ab" if dloffset >  0 else "wb"
        with open(enc_file, mode) as fd:
            downloaded = dloffset
            chunk_size = 0x10000
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    fd.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, size)
        log("Download complete.")

    # Determine output decrypted filename (.tar.md5)
    # Encrypted file is typically .enc2 or .enc4
    dec_filename = filename
    for ext in [".enc4", ".enc2", ".enc"]:
        if dec_filename.endswith(ext):
            dec_filename = dec_filename[:-len(ext)]
            break
    if not dec_filename.endswith(".tar.md5") and not dec_filename.endswith(".tar"):
        dec_filename += ".tar.md5"

    dec_file = os.path.join(out_dir, dec_filename)

    if os.path.exists(dec_file) and os.path.getsize(dec_file) > 0:
        log(f"Decrypted file already exists: {dec_file}")
        return dec_file

    log(f"Decrypting firmware file into {dec_filename}...")
    # Determine encryption version (version 4 for modern devices, version 2 for older)
    getkey = crypt.getv2key if filename.endswith(".enc2") else crypt.getv4key
    key = getkey(fw_ver, model, region)
    length = os.path.getsize(enc_file)
    with open(enc_file, "rb") as inf:
        with open(dec_file, "wb") as outf:
            crypt.decrypt_progress(inf, outf, key, length)

    log(f"Decryption successful: {dec_file}")
    return dec_file
