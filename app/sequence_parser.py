"""Parse FASTA + GenBank into a normalized form for the plasmid DB.

We don't pull in BioPython for this — a single-purpose ~150-line parser
covers our needs (display in SeqViz, store features), and avoids a 50+ MB
dep on numpy + biopython.

Output shape (also what gets handed to SeqViz):
{
  "sequence": "ATGCGTGCAT...",
  "is_circular": True,
  "format": "genbank",
  "name": "pCAG-GFP",
  "features": [
    {"name": "EGFP", "start": 0, "end": 720, "type": "CDS",
     "direction": 1, "color": "#a4d4a4", "notes": ""},
    ...
  ]
}
"""
from __future__ import annotations

import re

# Pastel colors used to tint features by type. Same palette SnapGene-ish
# uses; SeqViz will apply these via feature.color directly.
FEATURE_TYPE_COLORS = {
    "CDS": "#a4d4a4",
    "gene": "#a4d4a4",
    "promoter": "#ffd86b",
    "terminator": "#ff9b6b",
    "rep_origin": "#c8a4d4",
    "polyA_signal": "#ffb8d4",
    "primer_bind": "#9bb8e0",
    "regulatory": "#ffd86b",
    "misc_feature": "#d0d0d0",
    "5'UTR": "#e0c89b",
    "3'UTR": "#e0c89b",
    "exon": "#a4d4a4",
    "intron": "#d4c8a4",
    "source": "#e0e0e0",
    "tag": "#ff6b6b",
    "tRNA": "#9bb8e0",
    "rRNA": "#9bb8e0",
    "enhancer": "#ffd86b",
}


def parse_fasta(raw: str) -> dict | None:
    raw = raw.strip()
    if not raw.startswith(">"):
        return None
    lines = raw.splitlines()
    name = lines[0][1:].strip().split()[0] if lines[0][1:].strip() else "sequence"
    seq = "".join(l.strip() for l in lines[1:] if not l.startswith(">"))
    seq = re.sub(r"[^ACGTNUacgtnu]", "", seq).upper()
    return {
        "sequence": seq,
        "is_circular": False,  # FASTA gives no topology hint; default linear
        "format": "fasta",
        "name": name,
        "features": [],
    }


# GenBank LOCUS line: "LOCUS       name      length bp    DNA     circular ..."
_LOCUS_NAME_RE = re.compile(r"^LOCUS\s+(\S+)\s+\d+\s+bp", re.IGNORECASE)
_LOCUS_TOPO_RE = re.compile(r"\b(linear|circular)\b", re.IGNORECASE)


def parse_genbank(raw: str) -> dict | None:
    if "LOCUS" not in raw or "ORIGIN" not in raw:
        return None

    name = ""
    is_circular = False
    seq = ""
    features: list[dict] = []

    lines = raw.splitlines()
    state = "header"
    current_feature: dict | None = None
    pending_qualifier_key: str | None = None
    pending_qualifier_value: list[str] = []

    def flush_qualifier():
        nonlocal pending_qualifier_key, pending_qualifier_value
        if current_feature and pending_qualifier_key:
            val = " ".join(pending_qualifier_value).strip().strip('"')
            current_feature.setdefault("qualifiers", {})[pending_qualifier_key] = val
        pending_qualifier_key = None
        pending_qualifier_value = []

    def flush_feature():
        if current_feature:
            features.append(current_feature)

    for raw_line in lines:
        if state == "header":
            m = _LOCUS_NAME_RE.match(raw_line)
            if m:
                name = m.group(1) or name
                topo = _LOCUS_TOPO_RE.search(raw_line)
                if topo:
                    is_circular = topo.group(1).lower() == "circular"
            if raw_line.startswith("FEATURES"):
                state = "features"
                continue
            if raw_line.startswith("ORIGIN"):
                state = "origin"
                continue

        elif state == "features":
            if raw_line.startswith("ORIGIN"):
                flush_qualifier()
                flush_feature()
                current_feature = None
                state = "origin"
                continue
            # Feature line: 5-char indent, type starting at col 5
            if raw_line.startswith("     ") and len(raw_line) >= 22 and raw_line[5] != " ":
                # New feature row.
                flush_qualifier()
                flush_feature()
                current_feature = {}
                ftype = raw_line[5:20].strip()
                location = raw_line[21:].strip()
                current_feature["type"] = ftype
                current_feature["location_raw"] = location
                # Continue reading location across continuation lines.
                pending_qualifier_key = None
            elif raw_line.startswith("                     "):
                # Continuation (col 21+). Either qualifier (/key=val) or
                # continuation of location.
                content = raw_line[21:].rstrip()
                if content.startswith("/"):
                    flush_qualifier()
                    if "=" in content:
                        k, v = content[1:].split("=", 1)
                    else:
                        k, v = content[1:], ""
                    pending_qualifier_key = k.strip()
                    pending_qualifier_value = [v.strip()]
                elif pending_qualifier_key:
                    pending_qualifier_value.append(content.strip())
                elif current_feature is not None:
                    # Continuation of the location string.
                    current_feature["location_raw"] += content.strip()

        elif state == "origin":
            # Sequence lines: " 1 atgc gtgc atcg ..."
            if raw_line.startswith("//"):
                break
            # Strip leading position number + whitespace.
            cleaned = re.sub(r"\d+", "", raw_line).replace(" ", "").strip()
            seq += cleaned

    seq = re.sub(r"[^ACGTNUacgtnu]", "", seq).upper()

    # Normalize features: parse the location into start/end + direction.
    normalized = []
    for feat in features:
        if feat.get("type") in ("source", ""):
            # Source covers the whole sequence — skip in feature display.
            continue
        start, end, direction = _parse_location(feat.get("location_raw", ""))
        if start is None or end is None:
            continue
        # Pick a feature name in priority order.
        q = feat.get("qualifiers", {})
        name_val = (
            q.get("label")
            or q.get("gene")
            or q.get("product")
            or q.get("note")
            or feat.get("type")
            or "feature"
        ).split(";")[0][:80]
        normalized.append({
            "name": name_val,
            "start": start,
            "end": end,
            "type": feat.get("type", "misc_feature"),
            "direction": direction,
            "color": FEATURE_TYPE_COLORS.get(feat.get("type", ""), "#d0d0d0"),
            "notes": (q.get("note") or "")[:200],
        })

    return {
        "sequence": seq,
        "is_circular": is_circular,
        "format": "genbank",
        "name": name,
        "features": normalized,
    }


_LOC_NUM = re.compile(r"(\d+)\s*\.\.\s*(\d+)")


def _parse_location(loc: str) -> tuple[int | None, int | None, int]:
    """Parse a GenBank location string. Returns (start, end, direction) where
    indices are 0-based inclusive ends as in SeqViz expectations."""
    if not loc:
        return None, None, 1
    direction = -1 if "complement" in loc else 1
    # Find the first numeric range. Joins / orders are folded to the outer
    # min..max bounds (good enough for visualization).
    matches = _LOC_NUM.findall(loc)
    if not matches:
        # Single position like "123"
        m = re.search(r"\d+", loc)
        if not m:
            return None, None, direction
        pos = int(m.group(0)) - 1
        return pos, pos, direction
    starts = [int(a) for a, _ in matches]
    ends = [int(b) for _, b in matches]
    return min(starts) - 1, max(ends) - 1, direction


def parse_sequence_text(raw: str) -> dict | None:
    """Auto-detect FASTA vs GenBank vs raw-bases input and parse."""
    raw_strip = raw.strip()
    if raw_strip.startswith(">"):
        return parse_fasta(raw)
    if raw_strip.upper().startswith("LOCUS"):
        return parse_genbank(raw)
    # Treat as raw bases.
    cleaned = re.sub(r"[^ACGTNUacgtnu]", "", raw_strip)
    if not cleaned:
        return None
    return {
        "sequence": cleaned.upper(),
        "is_circular": False,
        "format": "raw",
        "name": "",
        "features": [],
    }


# ---------------------------------------------------------------------------
# SnapGene .dna binary format.
#
# Format (reverse-engineered, used by many open-source readers):
#
#   - Bytes 0..8: magic "cookie" — starts with byte 0x09, then 8 bytes
#     including the ASCII string "SnapGene".
#   - Then a series of chunks, each:
#       1 byte: type
#       4 bytes: length (big-endian uint32)
#       N bytes: payload
#
#   Types we care about:
#     0x00 — DNA sequence chunk:
#       1 byte flags (bit 0 set = circular topology)
#       N-1 bytes: sequence (ASCII)
#     0x05 — Primers (XML, optional)
#     0x06 — Notes (HTML/XML)
#     0x0A — Features (XML with <Features><Feature>... </Feature></Features>)
#
# We extract sequence + topology from 0x00 and features from 0x0A. The
# features XML is parsed with xml.etree (stdlib) — no extra dep.
# ---------------------------------------------------------------------------

import struct
import xml.etree.ElementTree as _ET


def parse_snapgene_dna(raw_bytes: bytes) -> dict | None:
    if len(raw_bytes) < 14 or raw_bytes[0] != 0x09:
        return None
    # The first chunk is the cookie chunk; spec says length = 14, payload
    # ends with "SnapGene" or the like. We just skip past it by reading the
    # standard chunk header.
    pos = 0
    sequence = ""
    is_circular = False
    features_xml: str | None = None
    name = ""

    while pos + 5 <= len(raw_bytes):
        chunk_type = raw_bytes[pos]
        chunk_length = struct.unpack(">I", raw_bytes[pos + 1 : pos + 5])[0]
        pos += 5
        end = pos + chunk_length
        if end > len(raw_bytes):
            break
        payload = raw_bytes[pos:end]
        pos = end

        if chunk_type == 0x00 and len(payload) >= 1:
            flags = payload[0]
            is_circular = bool(flags & 0x01)
            try:
                sequence = payload[1:].decode("ascii", errors="ignore")
            except Exception:
                sequence = ""
        elif chunk_type == 0x0A:
            try:
                features_xml = payload.decode("utf-8", errors="ignore")
            except Exception:
                features_xml = None

    if not sequence:
        return None

    sequence = re.sub(r"[^ACGTNUacgtnu]", "", sequence).upper()
    features = _parse_snapgene_features_xml(features_xml) if features_xml else []

    return {
        "sequence": sequence,
        "is_circular": is_circular,
        "format": "snapgene",
        "name": name,
        "features": features,
    }


def _parse_snapgene_features_xml(xml_text: str) -> list[dict]:
    """Parse the <Features> XML chunk from a SnapGene .dna file."""
    features: list[dict] = []
    try:
        root = _ET.fromstring(xml_text)
    except _ET.ParseError:
        return features

    # XML structure: <Features><Feature name="..." type="..." directionality="...">
    #   <Segment range="start-end" color="#rrggbb"/>
    #   <Q name="note"><V text="..."/></Q>
    # </Feature></Features>
    for f in root.iter("Feature"):
        fname = f.attrib.get("name") or f.attrib.get("type") or "feature"
        ftype = f.attrib.get("type", "misc_feature")
        # SnapGene directionality: 1 = forward, 2 = reverse, 3 = both, 0 = none.
        d_raw = f.attrib.get("directionality", "0")
        try:
            d_int = int(d_raw)
        except ValueError:
            d_int = 0
        direction = -1 if d_int == 2 else (1 if d_int == 1 else 0)

        # Collect all segments to find the overall span. SnapGene uses
        # 1-based inclusive coordinates in "start-end" format.
        starts: list[int] = []
        ends: list[int] = []
        seg_color = ""
        for seg in f.iter("Segment"):
            rng = seg.attrib.get("range", "")
            if not rng:
                continue
            try:
                s, e = rng.split("-", 1)
                starts.append(int(s) - 1)
                ends.append(int(e) - 1)
            except ValueError:
                continue
            seg_color = seg_color or seg.attrib.get("color", "")
        if not starts:
            continue
        start = min(starts)
        end = max(ends)

        note_text = ""
        for q in f.iter("Q"):
            if q.attrib.get("name") == "note":
                v = q.find("V")
                if v is not None:
                    note_text = (v.attrib.get("text") or "").strip()[:200]

        features.append({
            "name": (fname or "feature")[:80],
            "start": start,
            "end": end,
            "type": ftype,
            "direction": direction,
            "color": seg_color or FEATURE_TYPE_COLORS.get(ftype, "#d0d0d0"),
            "notes": note_text,
        })
    return features


def parse_sequence_bytes(raw_bytes: bytes, filename: str = "") -> dict | None:
    """Top-level dispatcher that handles both text and binary uploads.

    SnapGene .dna files are binary; FASTA/GenBank are text. We detect by
    looking at the magic byte (0x09 for .dna) before falling back to text
    decode.
    """
    if not raw_bytes:
        return None
    # SnapGene .dna magic.
    if raw_bytes[:1] == b"\x09":
        parsed = parse_snapgene_dna(raw_bytes)
        if parsed:
            return parsed
    # Text fallback.
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw_bytes.decode("latin-1")
        except UnicodeDecodeError:
            return None
    return parse_sequence_text(text)
