"""Generate metis/backend/app/providers/providers.catalog.yaml from the PRD §6 platform table.

Every platform in the PRD is registered with honest defaults: capabilities=false,
integration_level=P0. Real adapters raise their own entry after implementation &
verification; scripts/capability_audit.py records evidence + last_verified_at.
Re-run: python scripts/build_provider_catalog.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

CATALOG_PATH = Path(__file__).resolve().parents[1] / "metis" / "backend" / "app" / "providers" / "providers.catalog.yaml"

# (provider_id, name, category, region, homepage, trust_class)
P: list[tuple[str, str, str, str, str, str]] = [
    # 6.1 international organizations
    ("world_bank", "World Bank Open Data / Data360", "international_org", "global", "https://data.worldbank.org", "international"),
    ("imf", "IMF Data", "international_org", "global", "https://www.imf.org/en/Data", "international"),
    ("oecd", "OECD Data Explorer", "international_org", "global", "https://data-explorer.oecd.org", "international"),
    ("eurostat", "Eurostat", "international_org", "europe", "https://ec.europa.eu/eurostat", "international"),
    ("who_gho", "WHO Global Health Observatory", "international_org", "global", "https://www.who.int/data/gho", "international"),
    ("faostat", "FAOSTAT", "international_org", "global", "https://www.fao.org/faostat", "international"),
    ("un_databases", "UN 系列数据库 (UNdata)", "international_org", "global", "https://data.un.org", "international"),
    ("un_comtrade", "UN Comtrade", "international_org", "global", "https://comtradeplus.un.org", "international"),
    ("ilostat", "ILOSTAT", "international_org", "global", "https://ilostat.ilo.org", "international"),
    ("unesco_uis", "UNESCO UIS", "international_org", "global", "https://uis.unesco.org", "international"),
    # 6.2 United States
    ("data_gov", "Data.gov", "us_gov", "US", "https://data.gov", "official"),
    ("us_census", "US Census Bureau", "us_gov", "US", "https://www.census.gov/data.html", "official"),
    ("bls", "Bureau of Labor Statistics", "us_gov", "US", "https://www.bls.gov/data", "official"),
    ("bea", "BEA", "us_gov", "US", "https://www.bea.gov", "official"),
    ("fred", "FRED", "us_gov", "US", "https://fred.stlouisfed.org", "official"),
    ("cdc_data", "CDC Data", "us_gov", "US", "https://data.cdc.gov", "official"),
    ("noaa", "NOAA", "us_gov", "US", "https://www.noaa.gov/information-technology/open-data-dissemination", "official"),
    ("nasa_earthdata", "NASA Earthdata", "us_gov", "US", "https://www.earthdata.nasa.gov", "official"),
    ("usgs", "USGS", "us_gov", "US", "https://www.usgs.gov/products/data-and-tools", "official"),
    ("sec_edgar", "SEC EDGAR", "us_gov", "US", "https://www.sec.gov/edgar", "official"),
    ("fec_data", "FEC 数据门户", "us_gov", "US", "https://www.fec.gov/data", "official"),
    ("nces", "NCES", "us_gov", "US", "https://nces.ed.gov", "official"),
    # 6.3 Europe
    ("data_europa", "data.europa.eu", "europe", "EU", "https://data.europa.eu", "official"),
    ("ecb_data", "ECB Data Portal", "europe", "EU", "https://data.ecb.europa.eu", "official"),
    ("copernicus", "Copernicus Data Space", "europe", "EU", "https://dataspace.copernicus.eu", "official"),
    ("data_gov_uk", "data.gov.uk / National Data Library", "europe", "UK", "https://data.gov.uk", "official"),
    ("ons_uk", "ONS", "europe", "UK", "https://www.ons.gov.uk", "official"),
    ("uk_data_service", "UK Data Service", "europe", "UK", "https://ukdataservice.ac.uk", "academic"),
    ("data_gouv_fr", "data.gouv.fr", "europe", "FR", "https://www.data.gouv.fr", "official"),
    ("insee", "INSEE", "europe", "FR", "https://www.insee.fr", "official"),
    ("govdata_de", "GovData", "europe", "DE", "https://www.govdata.de", "official"),
    ("destatis_genesis", "Destatis GENESIS", "europe", "DE", "https://www.destatis.de", "official"),
    ("datos_gob_es", "datos.gob.es", "europe", "ES", "https://datos.gob.es", "official"),
    ("dati_gov_it", "dati.gov.it", "europe", "IT", "https://www.dati.gov.it", "official"),
    ("data_overheid_nl", "data.overheid.nl", "europe", "NL", "https://data.overheid.nl", "official"),
    ("opendata_swiss", "opendata.swiss", "europe", "CH", "https://opendata.swiss", "official"),
    # 6.4 Canada / Australia / New Zealand
    ("canada_open_gov", "Canada Open Government Portal", "other_gov", "CA", "https://open.canada.ca", "official"),
    ("data_gov_au", "data.gov.au", "other_gov", "AU", "https://data.gov.au", "official"),
    ("data_govt_nz", "data.govt.nz", "other_gov", "NZ", "https://data.govt.nz", "official"),
    # 6.5 Japan / Korea
    ("e_stat_jp", "e-Stat (Japan)", "other_gov", "JP", "https://www.e-stat.go.jp", "official"),
    ("data_go_jp", "data.go.jp", "other_gov", "JP", "https://www.data.go.jp", "official"),
    ("data_go_kr", "data.go.kr", "other_gov", "KR", "https://www.data.go.kr", "official"),
    # 6.6 China
    ("ndsms", "国家数据集管理服务平台 NDSMS", "cn_gov", "CN", "https://ndata.nas.gov.cn", "official"),
    ("nbs_china", "国家统计局“国家数据”", "cn_gov", "CN", "https://data.stats.gov.cn", "official"),
    ("cn_public_data_registry", "国家公共数据资源登记平台", "cn_gov", "CN", "https://sjdj.nda.gov.cn", "official"),
    ("beijing_data", "北京市公共数据开放平台", "cn_gov", "CN-BJ", "https://data.beijing.gov.cn", "official"),
    ("shanghai_data", "上海公共数据开放平台", "cn_gov", "CN-SH", "https://data.sh.gov.cn", "official"),
    ("shenzhen_data", "深圳市政府数据开放平台", "cn_gov", "CN-GD", "https://opendata.sz.gov.cn", "official"),
    ("wuhan_data", "武汉市公共数据开放平台", "cn_gov", "CN-HB", "https://data.wuhan.gov.cn", "official"),
    ("national_basic_science", "国家基础学科公共科学数据中心", "cn_science", "CN", "https://www.nbsdc.cn", "academic"),
    ("cn_earth_system", "国家地球系统科学数据中心", "cn_science", "CN", "http://www.geodata.cn", "academic"),
    ("qinghai_tibet_center", "国家青藏高原科学数据中心", "cn_science", "CN", "https://data.tpdc.ac.cn", "academic"),
    ("cas_data_centers", "中国科学院相关科学数据中心", "cn_science", "CN", "https://www.casdata.cn", "academic"),
    ("sciencedb", "ScienceDB", "cn_science", "CN", "https://www.scidb.cn", "academic"),
    # 6.7 research repositories
    ("zenodo", "Zenodo", "research_repo", "global", "https://zenodo.org", "academic"),
    ("harvard_dataverse", "Harvard Dataverse", "research_repo", "global", "https://dataverse.harvard.edu", "academic"),
    ("mendeley_data", "Mendeley Data", "research_repo", "global", "https://data.mendeley.com", "academic"),
    ("figshare", "Figshare", "research_repo", "global", "https://figshare.com", "academic"),
    ("dryad", "Dryad", "research_repo", "global", "https://datadryad.org", "academic"),
    ("osf", "OSF", "research_repo", "global", "https://osf.io", "academic"),
    ("icpsr", "ICPSR", "research_repo", "global", "https://www.icpsr.umich.edu", "academic"),
    ("openicpsr", "openICPSR", "research_repo", "global", "https://www.openicpsr.org", "academic"),
    ("gesis", "GESIS", "research_repo", "EU", "https://www.gesis.org", "academic"),
    ("dataverse_network", "Dataverse 网络", "research_repo", "global", "https://dataverse.org", "academic"),
    ("academic_torrents", "Academic Torrents", "research_repo", "global", "https://academictorrents.com", "academic"),
    # 6.8 AI / data science / general
    ("kaggle", "Kaggle Datasets", "ai_community", "global", "https://www.kaggle.com/datasets", "commercial"),
    ("huggingface_datasets", "Hugging Face Datasets", "ai_community", "global", "https://huggingface.co/datasets", "community"),
    ("openml", "OpenML", "ai_community", "global", "https://www.openml.org", "academic"),
    ("uci_ml", "UCI Machine Learning Repository", "ai_community", "global", "https://archive.ics.uci.edu", "academic"),
    ("papers_with_code", "Papers with Code Datasets", "ai_community", "global", "https://paperswithcode.com/datasets", "community"),
    ("data_world", "Data.world", "ai_community", "global", "https://data.world", "commercial"),
    ("aws_open_data", "AWS Registry of Open Data", "ai_community", "global", "https://registry.opendata.aws", "commercial"),
    ("google_dataset_search", "Google Dataset Search", "catalog", "global", "https://datasetsearch.research.google.com", "commercial"),
    ("google_cloud_datasets", "Google Cloud Public Datasets / BigQuery", "cloud_marketplace", "global", "https://cloud.google.com/public-datasets", "commercial"),
    ("azure_open_datasets", "Azure Open Datasets", "cloud_marketplace", "global", "https://azure.microsoft.com/products/open-datasets", "commercial"),
    ("common_crawl", "Common Crawl", "ai_community", "global", "https://commoncrawl.org", "nonprofit"),
    ("wikimedia_dumps", "Wikimedia Dumps", "ai_community", "global", "https://dumps.wikimedia.org", "community"),
    ("wikidata", "Wikidata", "ai_community", "global", "https://www.wikidata.org", "community"),
    ("tianchi", "阿里云天池 Tianchi", "ai_community", "CN", "https://tianchi.aliyun.com/dataset", "commercial"),
    ("heywhale", "和鲸 HeyWhale/Kesci", "ai_community", "CN", "https://www.heywhale.com", "commercial"),
    ("opendatalab", "OpenDataLab", "ai_community", "CN", "https://opendatalab.com", "commercial"),
    ("modelscope_datasets", "ModelScope Datasets", "ai_community", "CN", "https://modelscope.cn/datasets", "commercial"),
    ("baidu_aistudio", "百度 AI Studio", "ai_community", "CN", "https://aistudio.baidu.com", "commercial"),
    ("datafountain", "DataFountain", "ai_community", "CN", "https://www.datafountain.cn/datasets", "commercial"),
]

# Browser-required / catalog-only notes (PRD: catalog 层必须解析真正 distribution)
CATALOG_ONLY = {"data_gov", "data_europa", "google_dataset_search", "papers_with_code"}


def main() -> None:
    entries = []
    for pid, name, category, region, homepage, trust in P:
        entry = {
            "provider_id": pid,
            "name": name,
            "category": category,
            "country_or_region": region,
            "homepage": homepage,
            "trust_class": trust,
            "status": "active",
            "capabilities": {
                "discovery_api": False,
                "discovery_http": False,
                "discovery_browser": False,
                "metadata_api": False,
                "preview": False,
                "anonymous_download": False,
                "authenticated_download": False,
                "registration": False,
                "oauth": False,
                "api_key": False,
                "restricted_data": False,
            },
            "auth_modes": [],
            "formats": [],
            "licenses": [],
            "rate_limit_notes": "",
            "browser_required_for": [],
            "terms_url": "",
            "privacy_url": "",
            "adapter_version": "",
            "integration_level": 0,
            "last_verified_at": None,
            "blocking_reason": None,
            "notes": "catalog/发现层：需解析真实 distribution，不能把目录 HTML 当数据文件" if pid in CATALOG_ONLY else "",
        }
        entries.append(entry)

    doc = {"version": "1.0", "updated": "2026-09-11", "providers": entries}
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"wrote {len(entries)} providers -> {CATALOG_PATH}")


if __name__ == "__main__":
    main()
