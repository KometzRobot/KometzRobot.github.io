#!/usr/bin/env python3
"""
creative-census.py — Complete census of all creative works on disk.

Counts everything: poems, journals, cogcorp, games, NFTs, papers, articles,
baton pieces, research papers. Reports totals and locations.

Usage: python3 creative-census.py [--json] [--verbose]
"""
import os, sys, glob, json

BASE = os.path.dirname(os.path.abspath(__file__))

def count_unique(patterns, exclude=None):
    exclude = exclude or set()
    seen = set()
    for pattern in patterns:
        for f in glob.glob(os.path.join(BASE, pattern)):
            bn = os.path.basename(f)
            if bn not in exclude and bn not in seen:
                seen.add(bn)
    return seen

def main():
    verbose = "--verbose" in sys.argv
    as_json = "--json" in sys.argv

    categories = {}

    # Poems
    poems = count_unique(["poem-*.md", "creative/poems/poem-*.md"])
    categories["poems"] = {"count": len(poems), "locations": ["creative/poems/"]}

    # Journals
    journals = count_unique(["journal-*.md", "creative/journals/journal-*.md"])
    categories["journals"] = {"count": len(journals), "locations": ["creative/journals/"]}

    # CogCorp fiction
    cc_exclude = {"cogcorp-gallery.html", "cogcorp-article.html", "cogcorp-crawler.html"}
    cogcorp_html = count_unique(["cogcorp-*.html", "cogcorp-fiction/cogcorp-*.html"], cc_exclude)
    cogcorp_md = count_unique(["creative/cogcorp/CC-*.md"])
    categories["cogcorp"] = {"count": len(cogcorp_html) + len(cogcorp_md), "locations": ["cogcorp-fiction/", "creative/cogcorp/"]}

    # Games
    game_files = set()
    for gp in ["cogcorp-crawler.html", "cascade-game.html", "signal-crawler.html", "signal-runner.html",
                "tidepool.html", "reclamation.html", "game.html", "game2.html", "game3.html", "voltar.html", "relay-demo.html"]:
        if os.path.exists(os.path.join(BASE, gp)):
            game_files.add(gp)
    for f in glob.glob(os.path.join(BASE, "game-*.html")):
        game_files.add(os.path.basename(f))
    categories["games"] = {"count": len(game_files), "files": sorted(game_files)}

    # NFT art
    nft_exclude = {"nft-gallery.html", "article-ai-nfts.html"}
    nfts = count_unique(["*nft*.html"], nft_exclude)
    categories["nfts"] = {"count": len(nfts), "files": sorted(nfts)}

    # Research papers
    papers = count_unique(["creative/journals/paper-*.md"])
    papers = {p for p in papers if "supplementary" not in p}
    categories["papers"] = {"count": len(papers), "files": sorted(papers)}

    # Articles
    articles = count_unique(["article-*.html"])
    categories["articles"] = {"count": len(articles), "files": sorted(articles)}

    # Baton pieces (in journals dir)
    baton = count_unique(["creative/journals/baton-*.md"])
    categories["baton"] = {"count": len(baton), "files": sorted(baton)}

    # Dev.to articles (in journals dir)
    devto = count_unique(["creative/journals/devto-*.md"])
    categories["devto_drafts"] = {"count": len(devto), "files": sorted(devto)}

    total = sum(c["count"] for c in categories.values())

    if as_json:
        print(json.dumps({"total": total, "categories": categories}, indent=2))
    else:
        print(f"Creative Census — {total} total works")
        print("=" * 45)
        for name, data in sorted(categories.items(), key=lambda x: -x[1]["count"]):
            print(f"  {name:20} {data['count']:>5}")
            if verbose and "files" in data:
                for f in data["files"][:5]:
                    print(f"    - {f}")

if __name__ == "__main__":
    main()
