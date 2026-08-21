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
    # Get binary info using samloader request module
    # binaryinfo(client, fwver, model, region)
    xml_data = request.binaryinfo(client, fw_ver, model, region)
    root = ET.fromstring(xml_data)

    latest = root.find("./version/latest")
    if latest is not None and latest.text != fw_ver:
        log(f"[warn] Requested version {fw_ver} differs from latest server version {latest.text}")

    path = root.find("./binary/path").text
    filename = root.find("./binary/filename").text
    size = int(root.find("./binary/filesize").text)

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
        request.initdownload(client, filename)

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
    enc_ver = 2 if filename.endswith(".enc2") else 4
    if enc_ver == 4:
        crypt.decrypt4(enc_file, dec_file, fw_ver)
    else:
        crypt.decrypt2(enc_file, dec_file, fw_ver)

    log(f"Decryption successful: {dec_file}")
    return dec_file
