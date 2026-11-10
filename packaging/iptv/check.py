#!/usr/bin/env python3
"""Check the channel list, XMLTV associations and each channel's TS output."""
import argparse
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def check(base_url):
    base_url = base_url.rstrip("/")
    with urllib.request.urlopen(base_url + "/api/iptv/playlist", timeout=60) as response:
        playlist = response.read().decode("utf-8")
    assert playlist.startswith("#EXTM3U"), "Invalid M3U playlist"
    entries = []
    for line in playlist.splitlines():
        if line.startswith("#EXTINF:"):
            match = re.search(r'tvg-id="([0-9]+)"', line)
            assert match, "Missing XMLTV channel ID"
            channel_id, name = match[1], line.split(",", 1)[1].strip()
        elif line.startswith("http"):
            assert urllib.parse.urlsplit(line).netloc == urllib.parse.urlsplit(base_url).netloc
            entries.append((channel_id, name, line))
    assert entries, "No channels discovered"
    assert len({entry[0] for entry in entries}) == len(entries), "Duplicate channels"
    with urllib.request.urlopen(base_url + "/api/iptv/xmltv", timeout=60) as response:
        guide = ET.fromstring(response.read())
    channels = {channel.attrib["id"] for channel in guide.findall("channel")}
    programmes = guide.findall("programme")
    covered = {programme.attrib["channel"] for programme in programmes}
    for channel_id, name, url in entries:
        assert channel_id in channels, f"{name}: missing XMLTV channel"
        assert channel_id in covered, f"{name}: no programme information"
        started = time.monotonic()
        with urllib.request.urlopen(url, timeout=60) as response:
            assert response.status == 200, f"{name}: stream unavailable"
            first = response.read(188)
            first_ts_seconds = time.monotonic() - started
            packets = first + response.read(188 * 63)
        assert len(packets) == 188 * 64, f"{name}: no TS output"
        assert all(packets[offset] == 0x47 for offset in range(0, len(packets), 188)), name
        print(f"PASS {name}: guide and TS, first TS {first_ts_seconds:.3f}s", flush=True)
    print(f"PASS {len(entries)} channels, {len(programmes)} programmes", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", help="e.g. http://192.168.1.16:40772")
    check(parser.parse_args().base_url)
