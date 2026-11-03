from susa import db
from susa.extract import html_to_canonical, markdown_to_canonical, normalize_target
from susa.fetch import classify_response
from susa.versions import add_version, current_version, read_text

HTML = ('<h2>Titel</h2><p>Erster   Absatz mit <a href="https://arxiv.org/abs/2601.01234v2">Link</a>.</p>'
        '<blockquote><p>Fremdes Zitat.</p></blockquote><div class="subscription-widget-wrap"><p>Subscribe</p></div>'
        '<ul><li>Punkt eins</li></ul><p>Manche schreiben: „Modelle leiden.“ Ich nicht.</p>')


def test_anchors_are_exact():
    ex = html_to_canonical(HTML)
    for p in ex.paragraphs:
        assert ex.text[p.start:p.end] == ex.text[p.start:p.end].strip()
    assert "Subscribe" not in ex.text
    assert [p.kind for p in ex.paragraphs] == ["h", "p", "p", "li", "p"]
    assert ex.paragraphs[2].speaker_hint == "quoted_other"
    (ln,) = ex.links
    assert ex.text[ln.start:ln.end] == "Link"
    assert ln.target == "arxiv:2601.01234"
    assert "Erster Absatz" in ex.text  # Leerraum zusammengefasst


def test_normalize_target_variants():
    assert normalize_target("https://www.arxiv.org/pdf/2601.01234v1") == normalize_target("http://arxiv.org/abs/2601.01234/")
    assert normalize_target("https://doi.org/10.1000/ABC") == "doi:10.1000/abc"
    assert normalize_target("https://Example.org/a/?utm_source=x") == "example.org/a"
    assert normalize_target("https://example.org/a?id=5&utm_medium=y") == "example.org/a?id=5"
    # verschiedene Videos dürfen nicht zu einer Quelle verschmelzen
    assert normalize_target("https://www.youtube.com/watch?v=AAA") != normalize_target("https://www.youtube.com/watch?v=BBB")
    assert normalize_target("https://youtu.be/AAA") == normalize_target("https://www.youtube.com/watch?v=AAA&t=10")


def test_markdown_import():
    ex = markdown_to_canonical("# Kopf\n\nText mit [Quelle](https://example.org/x).\n\n> Zitat")
    assert [p.kind for p in ex.paragraphs] == ["h", "p", "p"]
    assert ex.paragraphs[2].speaker_hint == "quoted_other"
    assert ex.text[ex.links[0].start:ex.links[0].end] == "Quelle"


def _doc(conn, did="synthetic:t:A"):
    ts = db.now()
    conn.execute("INSERT INTO documents(id, origin, is_synthetic, first_seen_at, updated_at) VALUES(?,?,?,?,?)", (did, "synthetic", 1, ts, ts))
    return did


def test_versions_dedupe_and_supersede(env):
    cfg, conn = env
    did = _doc(conn)
    v1, c1 = add_version(cfg, conn, did, source="synthetic_fixture", source_url=None, status="synthetic_fixture",
                         availability="full", extracted=html_to_canonical("<p>Alpha.</p>"))
    v1b, c1b = add_version(cfg, conn, did, source="synthetic_fixture", source_url=None, status="synthetic_fixture",
                           availability="full", extracted=html_to_canonical("<p>Alpha.</p>"))
    assert c1 and not c1b and v1 == v1b
    v2, c2 = add_version(cfg, conn, did, source="synthetic_fixture", source_url=None, status="synthetic_fixture",
                         availability="full", extracted=html_to_canonical("<p>Beta.</p>"))
    assert c2 and current_version(conn, did)["id"] == v2
    old = conn.execute("SELECT * FROM document_versions WHERE id=?", (v1,)).fetchone()
    assert old["is_current"] == 0 and read_text(cfg, old) == "Alpha."  # alte Version bleibt erhalten
    assert conn.execute("SELECT COUNT(*) FROM revisions WHERE entity_type='document_text'").fetchone()[0] == 1
    # Fehlgeschlagener Neuabruf überschreibt den vorhandenen Text nicht
    v3, c3 = add_version(cfg, conn, did, source="substack_api", source_url="x", status="http_error", availability="unavailable")
    assert not c3 and current_version(conn, did)["id"] == v2


def test_classify_response():
    assert classify_response(404, b"", None)[0] == "not_found"
    assert classify_response(200, b"<html>login</html>", None)[0] == "login_or_error_page"
    assert classify_response(200, b'{"audience":"only_paid","body_html":""}', None)[0] == "paywalled_preview"
    body = b'{"audience":"everyone","wordcount":100,"body_html":"<p>' + b"wort " * 30 + b'</p>"}'
    assert classify_response(200, body, None)[0] == "partial_suspected"
    body = b'{"audience":"everyone","wordcount":30,"body_html":"<p>' + b"wort " * 30 + b'</p>"}'
    assert classify_response(200, body, None)[0] == "ok_full"
    assert classify_response(200, b'{"body_html":"<p>' + b"a " * 5 + b'</p>"}', None)[0] == "ok_unverified_length"
