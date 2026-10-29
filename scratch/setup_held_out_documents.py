import shutil
from pathlib import Path

val_dir = Path("data/validation_notices")
docs_dir = Path("data/documents")

extra_files = [
    ("notice_23_nta_cuet_ug_cancellation.pdf", "123069cdad7a47318ff24734891b0cf34c67ec928fc8364c125df934f039a738.pdf"),
    ("notice_24_nta_deputation_extension.pdf", "4d04d7b9671e55fd62db37fc9f7cd82554b104a73fdb89ec4c1207b409592863.pdf"),
    ("notice_25_ssc_revised_je_capf_dates.pdf", "009a5b07560ffa9f4eac6cec4821e5b76e6dc2af8b389e98f1f508868c683ca4.pdf"),
    ("notice_26_tnpsc_group_2_services.pdf", "2da28762e530a4ce195587957b5703390e950c3cc1ac71579362a8a16782e85b.pdf"),
    ("notice_27_upsc_geo_scientist_time_table.html", "eeef2eff1c2f9d14f796671f3bda171d88a4a66464bf4aa6b63c284569d05918.html"),
    ("notice_28_upsc_cds_ii_written_result.html", "9eaeadab2583f7686746140961515f83aa5cef2a3feffc602459104d256090b4.html"),
    ("notice_29_uppsc_samiksha_adhikari_session.html", "33d243aec92d822f01e6f21c359f71422245f08e41ac311eb8314ca05f052493.html"),
    ("notice_30_upsc_app_delhi_scanned.pdf", "27aced11b082adda3920ea2f71a413290831d36711fa91bca6df95d1e363bc07.pdf"),
    ("notice_31_ssc_tentative_vacancies_je.pdf", "84f9c79be72d3f2ec8c983cba36bbaae46c2415156a5dc4dbff27a4e69d76378.pdf"),
    ("notice_32_upsc_cancellation_advt_13.pdf", "3f118317887e0fa80a65191fb3e617d33d9eb7362df243878772023026cff643.pdf"),
]

for target_name, src_hash in extra_files:
    src_path = docs_dir / src_hash
    target_path = val_dir / target_name
    if src_path.exists():
        shutil.copy2(src_path, target_path)
        print(f"Copied {src_hash} -> {target_name} ({target_path.stat().st_size} bytes)")
    else:
        print(f"WARNING: Source {src_hash} not found in {docs_dir}")

all_val = sorted(list(val_dir.glob("notice_*")))
print(f"\nTotal official documents in validation pool: {len(all_val)}")
