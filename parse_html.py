from bs4 import BeautifulSoup
import re

def extract_kupa_contacts(outro_text):
    kupa_contacts = {
        "מכבי": {"phones": set(), "links": []},
        "מאוחדת": {"phones": set(), "links": []},
        "כללית": {"phones": set(), "links": []}
    }
    for line in outro_text.split("\n"):
        line_lower = line.lower().strip()
        if "http" in line_lower:
            url_match = re.search(r'(https?://[^\s:]+)', line)
            if url_match:
                url = url_match.group(1)
                if "maccabi" in url and not kupa_contacts["מכבי"]["links"]:
                    kupa_contacts["מכבי"]["links"].append(url)
                elif "meuhedet" in url and not kupa_contacts["מאוחדת"]["links"]:
                    kupa_contacts["מאוחדת"]["links"].append(url)
                elif "clalit" in url and not kupa_contacts["כללית"]["links"]:
                    kupa_contacts["כללית"]["links"].append(url)
    kupa_contacts["מכבי"]["phones"].add("*3555")
    kupa_contacts["מאוחדת"]["phones"].add("*3833")
    kupa_contacts["כללית"]["phones"].add("*2700")
    for k in kupa_contacts:
        kupa_contacts[k]["phones"] = sorted(list(kupa_contacts[k]["phones"]))
    return kupa_contacts

def parse_services_html(file_path):
    """
    Parse an Israeli HMO services HTML file.
    Each service will include also the intro text of the page under the key 'intro'.
    The first line of the intro will also be appended to the 'service' field (in order to improve retrieval)
    """
    with open(file_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    all_chunks = []
    intro_text = ""

    tables = soup.find_all("table")
    first_table = tables[0] if tables else None
    last_table = tables[-1] if tables else None

    # Extract intro text (before first table)
    if first_table:
        intro = ""
        for elem in first_table.find_all_previous():
            if elem.name == 'body':
                break
            if elem.string and elem.string.strip():
                intro = elem.string.strip() + "\n" + intro
        if intro.strip():
            intro_text = intro.strip()
            all_chunks.append({
                "chunk_type": "intro",
                "text": intro_text
            })

    # Extract first line/title from intro
    intro_title = intro_text.splitlines()[0].strip() if intro_text else ""

    # Parse all tables (service chunks)
    for table in tables:
        headers = [th.text.strip() for th in table.find_all("th")]
        if not any(kupa in headers for kupa in ["מכבי", "מאוחדת", "כללית"]):
            continue
        rows = table.find_all("tr")[1:]
        for row in rows:
            cells = row.find_all("td")
            if not cells or len(cells) != 4:
                continue
            base_service = cells[0].text.strip()
            # Appending the intro title to the service
            service_with_intro = base_service
            if intro_title and intro_title not in base_service:
                service_with_intro = f"{base_service} {intro_title}"
            for i, kupa in enumerate(["מכבי", "מאוחדת", "כללית"]):
                raw_txt = cells[i+1].text.strip().replace("\n", " ")
                for maslul in ["זהב", "כסף", "ארד"]:
                    match = re.search(rf"{maslul}:(.*?)(?:(?:זהב|כסף|ארד):|$)", raw_txt)
                    if match:
                        benefit = match.group(1).strip().replace("•", "-")
                        all_chunks.append({
                            "chunk_type": "service",
                            "kupa": kupa,
                            "maslul": maslul,
                            "service": service_with_intro,   # <<-- Here!
                            "benefit": benefit,
                            "intro": intro_text
                        })

    # Extract outro text (after last table)
    outro = ""
    if last_table:
        for elem in last_table.find_all_next():
            if elem.name == 'body':
                break
            if elem.name in ['p', 'div'] and elem.get_text(strip=True):
                outro += elem.get_text(strip=True) + "\n"
            if elem.name == 'a' and elem.get('href'):
                link_text = elem.get_text(strip=True)
                link_url = elem.get('href')
                outro += f"{link_text}: {link_url}\n"
        if outro.strip():
            all_chunks.append({
                "chunk_type": "outro",
                "text": outro.strip()
            })

    kupa_contacts = extract_kupa_contacts(outro)
    for chunk in all_chunks:
        if chunk.get("chunk_type") == "service":
            chunk["kupa_contacts"] = kupa_contacts.get(chunk["kupa"], {})

    return all_chunks

