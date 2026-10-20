"""Search the JLCPCB parts library (same Cxxxxx codes as LCSC) and read lcsc.com stock and price ladders.

Usage: python3 jlc_lookup.py "keyword" [n]          code, MPN, maker, package, Basic/Ext (P = preferred), stock
       python3 jlc_lookup.py --json "keyword" [n]   same as JSON
       python3 jlc_lookup.py --lcsc C25744          lcsc.com stock and price ladder for one code

These are the public endpoints the JLCPCB and LCSC websites call. They are undocumented and can change; be gentle
(a few requests per second at most) and verify anything you order on the website itself.
"""
import json, sys, time, urllib.request

JLC_URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
LCSC_URL = "https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={}"
UA = {"User-Agent": "Mozilla/5.0"}


def search(kw, n=6):
    req = urllib.request.Request(JLC_URL, data=json.dumps({"keyword": kw, "currentPage": 1, "pageSize": n}).encode(),
                                 headers={"Content-Type": "application/json", **UA})
    d = json.load(urllib.request.urlopen(req, timeout=40))
    info = (d.get("data") or {}).get("componentPageInfo") or {}
    return [{"lcsc": c["componentCode"], "mpn": c["componentModelEn"], "maker": c["componentBrandEn"],
             "pkg": c["componentSpecificationEn"],
             "type": {"base": "Basic", "expand": "Ext"}.get(c["componentLibraryType"], c["componentLibraryType"]),
             "pref": bool(c.get("preferredComponentFlag")), "stock": c["stockCount"], "desc": c.get("describe", ""),
             "prices": [(p["startNumber"], p["productPrice"]) for p in c.get("componentPrices") or []]}
            for c in info.get("list") or []]


def lcsc(code, tries=4):
    """(stock, [(min qty, unit USD), ...]) on lcsc.com. JLC stock and lcsc.com stock are separate pools."""
    for i in range(tries):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(LCSC_URL.format(code), headers=UA), timeout=30))
            r = d.get("result") or {}
            return r.get("stockNumber"), [(p["ladder"], p["usdPrice"]) for p in r.get("productPriceList") or []]
        except Exception:
            time.sleep(2 + 3 * i)
    return None, []


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--lcsc" in sys.argv:
        stock, ladder = lcsc(args[0])
        print(f"{args[0]} stock {stock}", " ".join(f"{q}+ ${p}" for q, p in ladder))
        sys.exit()
    rows = search(args[0], int(args[1]) if len(args) > 1 else 6)
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=1))
        sys.exit()
    for r in rows:
        print(f"{r['lcsc']:<10} {r['mpn'][:28]:<28} {r['maker'][:14]:<14} {r['pkg'][:16]:<16} "
              f"{r['type']:<5}{'P' if r['pref'] else ' '} {r['stock']:>7}  {r['desc'][:70]}")
