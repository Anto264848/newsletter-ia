from __future__ import annotations

from conftest import NOW, make_article

from newsletter.select import canonical_url, dedupe, rank, shortlist
from newsletter.state import History
from newsletter.textutils import contains_any, title_similarity


def test_canonical_url_removes_tracking():
    a = canonical_url("http://www.Site.com/article/?utm_source=rss&id=3#comments")
    assert a == "https://site.com/article?id=3"


def test_dedupe_same_url():
    a1 = make_article(1)
    a2 = make_article(1, source="autre")
    a2.url = a1.url + "?utm_medium=feed"
    assert len(dedupe([a1, a2])) == 1


def test_dedupe_similar_titles_groups_and_counts_coverage():
    a = make_article(1, "Jensen Huang says he's willing to return as Nvidia CEO", "verge", 1.2)
    b = make_article(2, "Jensen Huang would be 'honored' to return as Nvidia CEO", "techcrunch", 1.0)
    c = make_article(3, "Nvidia : Jensen Huang envisage un retour à la direction", "lmi", 1.0)
    d = make_article(4, "Mistral AI ouvre un bureau à Singapour", "numerama", 1.0)
    res = dedupe([a, b, c, d], threshold=0.4)
    assert len(res) == 2
    rep = next(r for r in res if "Jensen" in r.title)
    assert rep.coverage == 3
    assert rep.source_id == "verge"  # source au plus fort poids
    assert sorted(rep.related_sources) == ["Lmi", "Techcrunch"]


def test_dedupe_keeps_distinct_titles_with_generic_words():
    a = make_article(1, "Introducing Gemini 4 Hydrogen")
    b = make_article(2, "Introducing OpenAI for Chile")
    c = make_article(3, "Introducing ChatGPT Wallet")
    assert len(dedupe([a, b, c], threshold=0.4)) == 3


def test_title_similarity_bounds():
    assert title_similarity("Le même titre exactement", "Le même titre exactement") == 1.0
    assert title_similarity("Apple sort un iPhone", "La météo de demain à Paris") < 0.2
    assert title_similarity("", "abc") == 0.0


def test_rank_prefers_recent_covered_general_public():
    old = make_article(1, "Benchmark obscur de modèle", days_ago=6)
    fresh = make_article(2, "ChatGPT arrive sur tous les smartphones", days_ago=0.5)
    fresh.coverage = 3
    ranked = rank([old, fresh], ["chatgpt", "smartphone"], NOW)
    assert ranked[0] is fresh and ranked[0].score > ranked[1].score


def test_shortlist_excludes_history(settings, tmp_path):
    history = History(tmp_path)
    arts = [make_article(i) for i in range(1, 6)]
    history.add_issue([arts[0].url], [arts[1].title], "", "")
    result = shortlist(arts, settings, history, NOW)
    urls = {a.url for a in result}
    assert arts[0].url not in urls  # URL déjà publiée
    assert arts[1].url not in urls  # sujet déjà publié
    assert len(result) == 3


def test_contains_any_word_boundaries():
    kws = [" ia ", "intelligence artificielle", "l'ia"]
    assert contains_any("Une IA qui dessine", kws)
    assert contains_any("Comment l’IA change l'école", kws)
    assert not contains_any("La Via Ferrata de Chamonix", kws)
