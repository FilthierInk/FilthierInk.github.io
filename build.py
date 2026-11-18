import os
import requests
from dotenv import load_dotenv
import re
import unicodedata
from html import escape
from pathlib import Path
from urllib.parse import urlparse
import shutil
from datetime import date
from jinja2 import Environment, FileSystemLoader
import json

load_dotenv()

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATA_SOURCE_ID = "afc1b57b-d2fb-4784-b11d-d47287f36dcc"
API = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2025-09-03",
    "Content-Type": "application/json",
}
OUT = Path("dist")
IMG_DIR = OUT / "assets" / "img"
LANGS = ("es", "en")
PREFIX = {"es": "", "en": "/en"}
I18N = {lang: json.loads(Path(f"i18n/{lang}.json").read_text(encoding="utf-8")) for lang in LANGS}
TIPOS_WEB = ("proyecto", "experiencia", "educacion", "certificacion")
RUTAS = {"proyecto": "proyectos", "experiencia": "experiencia", "educacion": "educacion"}

MESES = {
    "es": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}

PROFILE = {
    "nombre": "Jorge Abel",
    "ubicacion": "Ciudad, País",
    "foto": "/assets/img/foto.jpg",
    "linkedin": "https://www.linkedin.com/in/tu-usuario/",
    "email": "tu@correo.com",
}
PROFILE_I18N = {
    "es": {
        "titular": "Hola, soy Jorge.<br>Diseño, analizo y fabrico.",
        "etiqueta": "Ingeniería · Diseño · Manufactura",
        "bio": "Tu presentación en 2–3 líneas.",
        "sobre_mi": "Tu bio en un párrafo.",
    },
    "en": {
        "titular": "Hi, I'm Jorge.<br>I design, analyze and build.",
        "etiqueta": "Engineering · Design · Manufacturing",
        "bio": "Your 2–3 line introduction.",
        "sobre_mi": "Your bio in one paragraph.",
    },
}


def notion_all(method, path, body=None):
    body = dict(body or {})
    results = []
    while True:
        if method == "GET":
            r = requests.get(API + path, headers=HEADERS, params=body)
        else:
            r = requests.post(API + path, headers=HEADERS, json=body)
        r.raise_for_status()
        data = r.json()
        results.extend(data["results"])
        if not data["has_more"]:
            return results
        body["start_cursor"] = data["next_cursor"]


def query_published():
    body = {
        "filter": {"property": "Publicado", "checkbox": {"equals": True}},
        "page_size": 100,
    }
    return notion_all("POST", f"/data_sources/{DATA_SOURCE_ID}/query", body)

def plain_text(rich):
    return "".join(part["plain_text"] for part in rich)


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def text_of(p, name):
    prop = p.get(name)
    if not prop:
        return ""
    return plain_text(prop[prop["type"]])


def select_name(p, name):
    value = p.get(name, {}).get("select")
    return value["name"] if value else None

def files_of(p, name):
    prop = p.get(name)
    if not prop:
        return []
    return [f[f["type"]]["url"] for f in prop["files"]]

def read_entry(page):
    p = page["properties"]
    fecha = p["Fecha"]["date"] or {}
    nombre = text_of(p, "Nombre")
    descripcion = text_of(p, "Descripción")
    return {
        "id": page["id"],
        "nombre": nombre,
        "nombre_en": text_of(p, "Titulo EN") or nombre,
        "slug": slugify(nombre),
        "descripcion": descripcion,
        "descripcion_en": text_of(p, "Descripcion EN") or descripcion,
        "tipo": select_name(p, "Tipo"),
        "categoria": select_name(p, "Categoria"),
        "organizacion": select_name(p, "Organizacion"),
        "herramientas": [t["name"] for t in p["Herramientas"]["multi_select"]],
        "link": p["Link"]["url"],
        "destacado": p["Destacado"]["checkbox"],
        "imagenes": files_of(p, "gallery"),
        "inicio": fecha.get("start"),
        "fin": fecha.get("end"),
    }

def get_blocks(block_id):
    return notion_all("GET", f"/blocks/{block_id}/children", {"page_size": 100})


def section_lang(name):
    words = name.lower().split()
    if len(words) == 2 and words[0] in ("portafolio", "portfolio") and words[1] in ("es", "en"):
        return words[1]
    return None


def find_writeups(page_id):
    found = {}
    current = None
    for block in get_blocks(page_id):
        if block["type"] == "heading_1":
            h = block["heading_1"]
            current = section_lang(plain_text(h["rich_text"]))
            if current and h.get("is_toggleable"):
                found[current] = get_blocks(block["id"])
                current = None
            elif current:
                found[current] = []
            continue
        if current:
            found[current].append(block)
    return found

def download_image(url, name):
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(urlparse(url).path).suffix.lower() or ".jpg"
    path = IMG_DIR / f"{name}{ext}"
    if not path.exists():
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        path.write_bytes(r.content)
    return f"/assets/img/{path.name}"

def fecha_corta(iso, lang="es"):
    if not iso:
        return ""
    return f"{MESES[lang][int(iso[5:7]) - 1]} {iso[:4]}"

def rango(e, lang="es"):
    ini, fin = fecha_corta(e["inicio"], lang), fecha_corta(e["fin"], lang)
    return f"{ini} – {fin}" if fin and fin != ini else ini


def url_for(e, lang="es"):
    if e["tipo"] in RUTAS:
        return f"{PREFIX[lang]}/{RUTAS[e['tipo']]}/{e['slug']}/"
    return e["link"] or f"{PREFIX[lang]}/#certificaciones"

def localize(e, lang):
    if lang == "es":
        return e
    return {**e, "nombre": e["nombre_en"], "descripcion": e["descripcion_en"]}

def build_skills(entries):
    count = {}
    for e in entries:
        if e["tipo"] in TIPOS_WEB:
            for tool in e["herramientas"]:
                count[tool] = count.get(tool, 0) + 1

    groups = {}
    for e in entries:
        if e["tipo"] == "herramienta":
            cat = e["categoria"] or "Otras"
            groups.setdefault(cat, []).append({"nombre": e["nombre"], "n": count.get(e["nombre"], 0)})

    for items in groups.values():
        items.sort(key=lambda t: t["n"], reverse=True)
    return groups




env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
env.filters["fecha"] = fecha_corta
env.globals["url_for"] = url_for
env.filters["rango"] = rango
env.globals["year"] = date.today().year


def render(template_name, out_path, **data):
    html = env.get_template(template_name).render(**data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

def download_images(e):
    urls = e["imagenes"]
    paths = [download_image(url, f"{e['id']}-{i}") for i, url in enumerate(urls)]
    e["portada"] = paths[0] if paths else None
    e["galeria"] = paths[1:]

def rich_to_html(rich):
    out = ""
    for part in rich:
        text = escape(part["plain_text"])
        a = part["annotations"]
        if a["code"]:
            text = f"<code>{text}</code>"
        if a["bold"]:
            text = f"<strong>{text}</strong>"
        if a["italic"]:
            text = f"<em>{text}</em>"
        if part.get("href"):
            text = f'<a href="{escape(part["href"])}">{text}</a>'
        out += text
    return out

def blocks_to_html(blocks):
    html = []
    open_list = None
    for b in blocks:
        t = b["type"]
        data = b[t]
        list_tag = {"bulleted_list_item": "ul", "numbered_list_item": "ol"}.get(t)
        if open_list and open_list != list_tag:
            html.append(f"</{open_list}>")
            open_list = None
        if list_tag and not open_list:
            html.append(f"<{list_tag}>")
            open_list = list_tag
        if t == "paragraph":
            text = rich_to_html(data["rich_text"])
            if text:
                html.append(f"<p>{text}</p>")
        elif t in ("heading_2", "heading_3"):
            tag = "h2" if t == "heading_2" else "h3"
            html.append(f"<{tag}>{rich_to_html(data['rich_text'])}</{tag}>")
        elif list_tag:
            html.append(f"<li>{rich_to_html(data['rich_text'])}</li>")
        elif t == "quote":
            html.append(f"<blockquote>{rich_to_html(data['rich_text'])}</blockquote>")
        elif t == "image":
            src = download_image(data[data["type"]]["url"], b["id"])
            caption = escape(plain_text(data.get("caption", [])))
            html.append(f'<figure><img src="{src}" alt="{caption}"><figcaption>{caption}</figcaption></figure>')
        elif t == "divider":
            html.append("<hr>")
    if open_list:
        html.append(f"</{open_list}>")
    return "\n".join(html)

def group(entries):
    by_type = {}
    for e in entries:
        by_type.setdefault(e["tipo"], []).append(e)
    return by_type


def other_lang(lang):
    return "en" if lang == "es" else "es"


def page_context(lang, alt_url):
    return {"lang": lang, "t": I18N[lang], "root": PREFIX[lang], "alt_url": alt_url}


def build_home(lang, entries):
    local = [localize(e, lang) for e in entries]
    by_type = group(local)
    proyectos = by_type.get("proyecto", [])
    render("home.html", OUT / PREFIX[lang].strip("/") / "index.html",
           **page_context(lang, PREFIX[other_lang(lang)] + "/"),
           profile={**PROFILE, **PROFILE_I18N[lang]},
           recent=[e for e in local if e["tipo"] in TIPOS_WEB][:5],
           experiencia=by_type.get("experiencia", []),
           proyectos=proyectos,
           educacion=by_type.get("educacion", []),
           certificaciones=by_type.get("certificacion", []),
           categorias=sorted({e["categoria"] for e in proyectos if e["categoria"]}),
           skills=build_skills(local),
           total_proyectos=len(proyectos),
           actualizado=date.today().strftime("%d/%m/%Y"))


def build_details(lang, entries):
    by_type = group([localize(e, lang) for e in entries])
    for tipo, carpeta in RUTAS.items():
        items = by_type.get(tipo, [])
        for i, e in enumerate(items):
            blocks = e["writeups"].get(lang) or e["writeups"].get("es", [])
            render("detail.html", OUT / PREFIX[lang].strip("/") / carpeta / e["slug"] / "index.html",
                   **page_context(lang, url_for(e, other_lang(lang))),
                   e=e,
                   etiqueta=I18N[lang]["tipo_" + tipo],
                   seccion=carpeta,
                   contenido=blocks_to_html(blocks),
                   prev=items[i - 1] if i > 0 else None,
                   next=items[i + 1] if i + 1 < len(items) else None)


if __name__ == "__main__":
    entries = [read_entry(page) for page in query_published()]
    entries = [e for e in entries if e["tipo"]]
    for e in entries:
        download_images(e)
        if e["tipo"] in RUTAS:
            e["writeups"] = find_writeups(e["id"])
    entries.sort(key=lambda e: e["inicio"] or "", reverse=True)

    shutil.copytree("assets", OUT / "assets", dirs_exist_ok=True)
    for lang in LANGS:
        build_home(lang, entries)
        build_details(lang, entries)
    print("Listo: dist/ (es + en)")