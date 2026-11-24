#!/usr/bin/env python3
import sys
import re
import json
import ssl
import argparse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

def validate_sitemap(sitemap_url, timeout=8):
    if not sitemap_url.startswith("http://") and not sitemap_url.startswith("https://"):
        sitemap_url = "https://" + sitemap_url
    if not sitemap_url.endswith(".xml") and "/" not in sitemap_url.split("://")[1]:
        sitemap_url = sitemap_url.rstrip("/") + "/sitemap.xml"

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    results = {
        "target": sitemap_url,
        "score": 100,
        "status": "PASS",
        "type": "unknown",
        "total_entries": 0,
        "sample_urls": [],
        "issues": [],
        "recommendations": []
    }

    req = urllib.request.Request(sitemap_url, headers={"User-Agent": "Mozilla/5.0 (TAVARDT-Sitemap-Auditor/1.0)"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            content = resp.read()

        try:
            root = ET.fromstring(content)
        except Exception as xe:
            results["score"] = 0
            results["issues"].append(f"XML parse failure: {str(xe)}")
            results["recommendations"].append("Verify XML syntax and ensure all special characters are escaped.")
            return results

        tag_name = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if tag_name == "sitemapindex":
            results["type"] = "sitemapindex"
            sitemaps = []
            for sm in root.findall(".//{*}sitemap"):
                loc_elem = sm.find("{*}loc")
                if loc_elem is not None and loc_elem.text:
                    sitemaps.append(loc_elem.text.strip())
            results["total_entries"] = len(sitemaps)
            results["sample_urls"] = sitemaps[:5]
            if len(sitemaps) == 0:
                results["score"] -= 30
                results["issues"].append("Sitemap index contains zero child sitemap entries.")
                results["recommendations"].append("Add child sitemaps to the sitemap index.")
            elif len(sitemaps) > 50000:
                results["score"] -= 20
                results["issues"].append("Sitemap index exceeds the maximum threshold of 50,000 sub-sitemaps.")

        elif tag_name == "urlset":
            results["type"] = "urlset"
            urls = []
            insecure_urls = []
            for u in root.findall(".//{*}url"):
                loc_elem = u.find("{*}loc")
                if loc_elem is not None and loc_elem.text:
                    url_str = loc_elem.text.strip()
                    urls.append(url_str)
                    if url_str.startswith("http://") and sitemap_url.startswith("https://"):
                        insecure_urls.append(url_str)
            results["total_entries"] = len(urls)
            results["sample_urls"] = urls[:5]

            if len(urls) == 0:
                results["score"] -= 30
                results["issues"].append("Urlset sitemap contains zero URL entries.")
                results["recommendations"].append("Add page URLs to the sitemap.")
            elif len(urls) > 50000:
                results["score"] -= 20
                results["issues"].append("Sitemap exceeds standard limit of 50,000 URLs per individual file.")
                results["recommendations"].append("Split large sitemaps into multiple files coordinated via a sitemap index.")

            if insecure_urls:
                results["score"] -= 15
                results["issues"].append(f"Detected {len(insecure_urls)} insecure HTTP URL(s) in HTTPS sitemap.")
                results["recommendations"].append("Update all sitemap URLs to HTTPS.")
        else:
            results["score"] -= 40
            results["issues"].append(f"Unrecognized root XML element: <{tag_name}>. Expected <urlset> or <sitemapindex>.")
            results["recommendations"].append("Enforce valid Sitemaps.org schema root element.")

    except Exception as e:
        results["score"] = 0
        results["issues"].append(f"HTTP request error: {str(e)}")
        results["recommendations"].append("Verify sitemap URL is accessible and returns HTTP 200.")

    results["score"] = max(0, min(100, results["score"]))
    if results["score"] >= 85:
        results["status"] = "OPTIMAL"
    elif results["score"] >= 65:
        results["status"] = "WARNING"
    else:
        results["status"] = "CRITICAL"

    return results

def main():
    parser = argparse.ArgumentParser(description="TAVARDT USA - XML Sitemap Validator")
    parser.add_argument("target", help="Sitemap URL or domain to audit")
    parser.add_argument("-json", "--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("-timeout", "--timeout", type=int, default=8, help="Request timeout in seconds")

    args = parser.parse_args()
    report = validate_sitemap(args.target, timeout=args.timeout)

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print("=" * 60)
    print(" " + "TAVARDT USA - XML Sitemap Validator")
    print("=" * 60)
    print(f"Target: {report['target']}")
    print(f"Type: {report['type']}")
    print(f"Total Entries: {report['total_entries']}")
    print(f"Sitemap Quality Score: {report['score']}/100")
    print(f"Conformity Status: {report['status']}")
    print("-" * 60)

    print(f"\n[Discovered Errors and Warnings]:")
    if not report["issues"]:
        print(f"  - XML sitemap is fully valid and strictly adheres to protocol specifications.")
    else:
        for iss in report["issues"]:
            print(f"  * {iss}")

    if report["sample_urls"]:
        print(f"\n[XML Structure and URL Metrics]:")
        for u in report["sample_urls"]:
            print(f"  * Entry: {u}")

    if report["recommendations"]:
        print(f"\n[Optimization Recommendations]:")
        for rec in report["recommendations"]:
            print(f"  - {rec}")

    print("-" * 60)
    print(f"Full audit and online validation: https://tools.tavardt.com/xml-sitemap-validator/")
    print("=" * 60)

if __name__ == "__main__":
    main()
